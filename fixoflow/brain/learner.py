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
from typing import Optional

from fixoflow.storage.db import FixoflowDB

logger = logging.getLogger("fixoflow.brain.learner")

VOCABULARY_SEEDED_META_KEY = "vocabulary_seeded"

# Built-in developer & AI agent seed vocabulary
DEFAULT_DEV_VOCABULARY = [
    ("antigravity", "Antigravity", "ai"),
    ("claude code", "Claude Code", "ai"),
    ("chatgpt", "ChatGPT", "ai"),
    ("codex", "Codex", "ai"),
    ("gemini flash", "Gemini Flash", "ai"),
    ("mlx whisper", "mlx-whisper", "code"),
    ("pyobjc", "PyObjC", "code"),
    ("pytorch", "PyTorch", "code"),
    ("fastapi", "FastAPI", "code"),
    ("sqlite", "SQLite", "code"),
    ("docker", "Docker", "code"),
    ("kubernetes", "Kubernetes", "code"),
    ("kubectl", "kubectl", "code"),
    ("git commit", "git commit", "code"),
    ("git checkout", "git checkout", "code"),
    ("github", "GitHub", "dev"),
    ("vscode", "VS Code", "dev"),
    ("pull request", "Pull Request", "dev"),
    ("json", "JSON", "code"),
    ("yaml", "YAML", "code"),
    ("sdk", "SDK", "code"),
    ("api", "API", "code"),
    ("cli", "CLI", "code"),
]

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


def _literal_replacement(replacement: str):
    """Return a regex replacement that treats user text as literal.

    Dictionary replacements are data, not templates: backslashes and group
    references must never be interpreted by `re.sub`.
    """
    return lambda match: replacement


class AdaptiveLearner:
    def __init__(self, db: Optional[FixoflowDB] = None):
        self.db = db or FixoflowDB.get_instance()
        self._ensure_seed_vocabulary()

    def _ensure_seed_vocabulary(self) -> None:
        """Seed built-in vocabulary once; user deletions stay deleted."""
        if self.db.get_meta(VOCABULARY_SEEDED_META_KEY) == "1":
            return
        logger.info("Seeding developer and AI agent dictionary")
        for phrase, replacement, category in DEFAULT_DEV_VOCABULARY:
            self.db.seed_word(phrase, replacement, category=category)
        self.db.set_meta(VOCABULARY_SEEDED_META_KEY, "1")

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

    def format_for_mode(self, text: str, mode: str, app_name: str) -> str:
        """Apply personal-dictionary replacements and coding transformations."""
        if mode == "raw":
            return text

        effective_mode = self.effective_mode(mode, app_name)

        dictionary = self.db.get_dictionary(limit=200)
        for entry in dictionary:
            phrase = entry["phrase"]
            replacement = entry["replacement"]
            pattern = rf"\b{re.escape(phrase)}\b"
            if re.search(pattern, text, re.IGNORECASE):
                text = re.sub(pattern, _literal_replacement(replacement), text, flags=re.IGNORECASE)
                self.db.increment_word_usage(phrase)

        if effective_mode == "coding":
            for pattern, replacement in SPOKEN_CODE_PATTERNS:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text

    def get_dynamic_prompt_conditioning(self, app_name: str, mode: str = "auto") -> str:
        """Synthesize the Whisper initial prompt from approved vocabulary."""
        top_terms = self.db.get_vocabulary_prompt_terms(limit=25)
        terms = list(dict.fromkeys(["Claude Code", "Antigravity", "Codex", "ChatGPT", *top_terms]))
        terms_str = ", ".join(terms[:25])

        if mode == "coding" or (mode == "auto" and self.is_coding_context(app_name)):
            return f"Coding and AI prompt context: {terms_str}. Clean, precise code symbols and terminology."
        return f"Professional spoken English: {terms_str}. Clean, well-punctuated speech."
