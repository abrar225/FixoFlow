"""
Fixoflow Adaptive Learner & Formatting Engine
Owns the personal dictionary, spoken-code transformations, context-aware
formatting for coding tools (Claude Code, Antigravity, Codex) and the decoder
prompt conditioning synthesized from approved vocabulary.

Learning is explicit: only user dictionary entries become authoritative
corrections. Model output is never promoted into the dictionary automatically.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Optional

from fixoflow.storage.db import FixoflowDB

logger = logging.getLogger("fixoflow.brain.learner")

# Spoken code transformations
SPOKEN_CODE_PATTERNS = [
    # camelCase: "camel case foo bar" -> "fooBar"
    (r"\bcamel case\s+([a-zA-Z0-9_\s]+?)(?=[,\.\?!]|$)", lambda m: _to_camel_case(m.group(1))),
    # snake_case: "snake case foo bar" -> "foo_bar"
    (r"\bsnake case\s+([a-zA-Z0-9_\s]+?)(?=[,\.\?!]|$)", lambda m: _to_snake_case(m.group(1))),
    # kebab-case: "kebab case foo bar" -> "foo-bar"
    (r"\bkebab case\s+([a-zA-Z0-9_\s]+?)(?=[,\.\?!]|$)", lambda m: _to_kebab_case(m.group(1))),
    # CLI flags: "dash dash [word]" -> "--word"
    (r"\bdash dash\s+([a-zA-Z0-9_-]+)", r"--\1"),
    (r"\bdouble dash\s+([a-zA-Z0-9_-]+)", r"--\1"),
    (r"\bsingle dash\s+([a-zA-Z0-9])", r"-\1"),
    # Code operators
    (r"\bequals equals\b", "=="),
    (r"\bnot equals\b", "!="),
    (r"\bgreater than or equal to\b", ">="),
    (r"\bless than or equal to\b", "<="),
    (r"\barrow function\b", "=>"),
    (r"\bopen paren\b", "("),
    (r"\bclose paren\b", ")"),
    (r"\bopen bracket\b", "["),
    (r"\bclose bracket\b", "]"),
    (r"\bopen curly bracket\b", "{"),
    (r"\bclose curly bracket\b", "}"),
    (r"\btriple backtick\b", "```"),
    (r"\bbacktick\b", "`"),
]


def _to_camel_case(text: str) -> str:
    words = text.strip().split()
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def _to_snake_case(text: str) -> str:
    words = text.strip().split()
    return "_".join(w.lower() for w in words)


def _to_kebab_case(text: str) -> str:
    words = text.strip().split()
    return "-".join(w.lower() for w in words)


class AdaptiveLearner:
    def __init__(self, db: Optional[FixoflowDB] = None):
        self.db = db or FixoflowDB.get_instance()
    def is_coding_context(self, app_name: str) -> bool:
        """Whether the active application is a coding / terminal / agent environment."""
        coding_apps = [
            "code", "cursor", "terminal", "iterm", "alacritty", "kitty",
            "xcode", "warp", "pycharm", "webstorm", "sublime", "zed",
            "antigravity", "claude", "chatgpt"
        ]
        app_lower = app_name.lower()
        return any(candidate in app_lower for candidate in coding_apps)

    def effective_mode(self, mode: str, app_name: str) -> str:
        if mode == "auto":
            return "coding" if self.is_coding_context(app_name) else "writing"
        return mode

    def format_for_mode(self, text: str, mode: str, app_name: str, spoken_commands: bool = True) -> str:
        """Apply personal-dictionary replacements and coding transformations."""
        formatted, _ = self.format_for_mode_counted(text, mode=mode, app_name=app_name, spoken_commands=spoken_commands)
        return formatted

    def format_for_mode_counted(self, text: str, mode: str, app_name: str, spoken_commands: bool = True):
        """Apply dictionary/coding formatting and count the fixes applied.

        The count feeds the Insights tab as "Fixes made by Fixoflow":
        each personal-dictionary substitution and each spoken-code
        transformation counts once.
        """
        if mode == "raw":
            return text, 0

        effective_mode = self.effective_mode(mode, app_name)
        fixes = 0

        dictionary = self.db.get_dictionary(limit=None)
        # Compile against original input once: generated corrections must never
        # trigger another rule. Longest phrase wins regardless of usage order.
        by_phrase = {}
        for entry in sorted(dictionary, key=lambda e: (-len(e["phrase"]), e["phrase"].casefold(), e["phrase"])):
            by_phrase.setdefault(entry["phrase"].casefold(), entry)
        if by_phrase:
            entries = {f'word{i}':entry for i,entry in enumerate(by_phrase.values())}
            def word_character(char):return bool(char) and (unicodedata.category(char)[0] in 'LMN' or char=='_')
            def unspaced(char):return bool(char) and ('\u3040'<=char<='\u30ff' or '\u3400'<=char<='\u9fff')
            # Boundaries belong in the matching grammar. Rejecting a longer
            # phrase in a replacement callback hides valid shorter matches.
            # Only characters present in this original input can border a
            # match; include combining marks, unlike Python's default \w.
            characters=re.escape(''.join(sorted({c for c in text if word_character(c)})))
            boundary=f'[{characters}]' if characters else r'(?!)'
            alternatives=[]
            for key,entry in entries.items():
                left='' if unspaced(entry['phrase'][0]) else f'(?<!{boundary})'
                right='' if unspaced(entry['phrase'][-1]) else f'(?!{boundary})'
                alternatives.append(left+f'(?P<{key}>{re.escape(entry["phrase"])})'+right)
            pattern=re.compile('|'.join(alternatives),re.IGNORECASE)
            used = set()
            def replace(match):
                nonlocal fixes
                entry = entries[match.lastgroup]
                fixes += 1
                used.add(entry["phrase"])
                return entry["replacement"]
            text = pattern.sub(replace, text)
            for phrase in used:
                self.db.increment_word_usage(phrase)

        if effective_mode == "coding" and spoken_commands:
            for pattern, replacement in SPOKEN_CODE_PATTERNS:
                text, count = re.subn(pattern, replacement, text, flags=re.IGNORECASE)
                fixes += count

        return text, fixes

    def get_dynamic_prompt_conditioning(self, app_name: str, mode: str = "auto") -> str:
        """Synthesize the Whisper initial prompt from approved vocabulary."""
        top_terms = self.db.get_vocabulary_prompt_terms(limit=25)
        terms = list(dict.fromkeys(top_terms))
        terms_str = ", ".join(terms[:25])

        if mode == "coding" or (mode == "auto" and self.is_coding_context(app_name)):
            return f"Coding and AI prompt context: {terms_str}. Clean, precise code symbols and terminology."
        return f"Vocabulary: {terms_str}." if terms_str else ""
