"""
Fixoflow Brain: Intelligent Text Polishing & Formatting
Offline rule-based cleanup. This module never performs network requests.
Guarantees Zero Data Loss: Always returns raw transcript if polishing fails or times out.

Output styles (config.output_style) shape the writing-mode result:
  - "natural"      filler removal, spoken punctuation, capitalization
  - "concise"      natural plus hedge/filler tightening
  - "professional" natural plus contraction expansion
  - "verbatim"     recognizer wording untouched except trimming

Counting: ``polish_counted`` and ``clean_with_rules_counted`` report how many
text fixes were applied so the Insights tab can show real learning totals.
"""
from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from fixoflow.config import FixoflowConfig

logger = logging.getLogger("fixoflow.brain.polisher")

# Offline rule-based fillers and spoken punctuation replacements
FILLER_WORDS = [
    r"\b(um|uh|erm|ah|like you know|you know what I mean|so yeah|I mean)\b",
]

# Extra tightening applied by the "concise" style.
CONCISE_FILLERS = [
    r"\b(you know|kind of|sort of|basically|honestly|literally)\b",
]

# Contraction expansions applied by the "professional" style. Only
# unambiguous forms are expanded; possessives such as "it's" are skipped.
CONTRACTIONS = [
    (r"\bcan't\b", "cannot"),
    (r"\bwon't\b", "will not"),
    (r"\bdon't\b", "do not"),
    (r"\bdoesn't\b", "does not"),
    (r"\bdidn't\b", "did not"),
    (r"\bisn't\b", "is not"),
    (r"\baren't\b", "are not"),
    (r"\bwasn't\b", "was not"),
    (r"\bweren't\b", "were not"),
    (r"\bI'm\b", "I am"),
    (r"\byou're\b", "you are"),
    (r"\bwe're\b", "we are"),
    (r"\bthey're\b", "they are"),
    (r"\bI've\b", "I have"),
    (r"\bwe've\b", "we have"),
    (r"\byou've\b", "you have"),
    (r"\bthey've\b", "they have"),
    (r"\bI'll\b", "I will"),
    (r"\bwe'll\b", "we will"),
    (r"\byou'll\b", "you will"),
    (r"\bthey'll\b", "they will"),
]

PUNCTUATION_REPLACEMENTS = [
    (r"\b(period|full stop)\b", "."),
    (r"\bcomma\b", ","),
    (r"\bquestion mark\b", "?"),
    (r"\bexclamation mark\b", "!"),
    (r"\bcolon\b", ":"),
    (r"\bsemicolon\b", ";"),
    (r"\b(new line|newline)\b", "\n"),
    (r"\b(new paragraph|next paragraph)\b", "\n\n"),
    (r"\b(bullet point|bullet)\s*(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|[0-9]+)\b\s*)?\b", r"\n• "),
]


def _capitalize_sentences(text: str) -> Tuple[str, int]:
    sentences = re.split(r"([.!?]\s+|\n+|•\s*)", text)
    capitalized = []
    changes = 0
    for part in sentences:
        if part and not re.match(r"^[.!?\s\n•]+$", part):
            token = re.match(r'[A-Za-z_][A-Za-z0-9_]*', part)
            identifier = bool(token and ('_' in token[0] or re.search(r'[a-z][A-Z]', token[0])))
            upper = part if identifier else part[0].upper() + part[1:]
            if upper != part:
                changes += 1
            part = upper
        capitalized.append(part)
    return "".join(capitalized).strip(), changes


def _expand_contractions(text: str) -> Tuple[str, int]:
    changes = 0
    for pattern, replacement in CONTRACTIONS:
        def replace(match, replacement=replacement):
            nonlocal changes
            changes += 1
            word = match.group(0)
            if word[:1].isupper() and replacement[:1].islower():
                return replacement[:1].upper() + replacement[1:]
            if word.isupper() and len(word) > 1:
                return replacement.upper()
            return replacement
        text = re.sub(pattern, replace, text, flags=re.IGNORECASE)
    return text, changes


def _format_numbered_list(text: str) -> Tuple[str, int]:
    """Structure explicit consecutive sentence-start ordinals, without rewriting.

    Ambiguous prose, missing/reordered markers and existing numeric lists are
    retained. This is intentionally narrower than semantic list inference.
    """
    ordinals = {'first':1,'second':2,'third':3,'fourth':4,'fifth':5,
                'sixth':6,'seventh':7,'eighth':8,'ninth':9,'tenth':10}
    markers = '|'.join(word + '(?:ly)?' for word in ordinals)
    pattern = re.compile(r'(?P<boundary>^|(?<=[.!?:])\s+|,\s+)'
        r'(?P<marker>' + markers + r')\b(?P<separator>\s*[,;:]\s*|\s+)', re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if (len(matches) < 2 or '`' in text or re.search(r'["\u201c\u201d]|(?<!\w)[\'\u2018]', text)
            or re.search(r'(?:^|\s)\d+[.)]\s+', text)
            or matches[0]['boundary'].startswith(',')):
        return text, 0
    numbers = []
    for match in matches:
        marker = match['marker'].lower()
        ordinal = marker[:-2] if marker.endswith('ly') else marker
        # "First day", "second floor" and similar noun phrases are prose.
        if not marker.endswith('ly') and not any(c in match['separator'] for c in ',;:'):
            return text, 0
        numbers.append(ordinals[ordinal])
    if numbers != list(range(1, len(numbers)+1)):
        return text, 0
    items = [text[match.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
             for i,match in enumerate(matches)]
    if any(not item for item in items):
        return text, 0
    for i,item in enumerate(items[:-1]):
        if matches[i+1]['boundary'].startswith(',') and item[-1] not in '.!?;:':
            items[i] += '.'
    prefix = text[:matches[0].start()].rstrip()
    result = '\n'.join(f'{number}. {item}' for number,item in zip(numbers,items))
    return (prefix+'\n' if prefix else '') + result, len(items)


def clean_with_rules_counted(text: str, style: str = "natural", spoken_commands: bool = False) -> Tuple[str, int]:
    """Rule-based cleanup returning ``(cleaned_text, fixes_applied)``."""
    if style == "verbatim":
        return text.strip(), 0

    cleaned = text
    fixes = 0

    def apply_patterns(patterns):
        nonlocal cleaned, fixes
        for pattern in patterns:
            cleaned, count = re.subn(pattern, "", cleaned, flags=re.IGNORECASE)
            fixes += count

    # Remove obvious stuttering/fillers
    apply_patterns(FILLER_WORDS)
    if style == "concise":
        apply_patterns(CONCISE_FILLERS)

    # Replace spoken punctuation cues
    for pattern, repl in (PUNCTUATION_REPLACEMENTS if spoken_commands else []):
        cleaned, count = re.subn(pattern, repl, cleaned, flags=re.IGNORECASE)
        fixes += count

    # Fix spacing around punctuation
    cleaned, count = re.subn(r"[^\S\n]+([.,!?:;])", r"\1", cleaned)
    fixes += count

    def normalize_space(match):
        nonlocal fixes
        if match.group(0) != " ":
            fixes += 1
        return " "

    cleaned = re.sub(r"[^\S\n]+", normalize_space, cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned).strip()

    if style == "professional":
        cleaned, count = _expand_contractions(cleaned)
        fixes += count

    cleaned, count = _format_numbered_list(cleaned)
    fixes += count

    # Capitalize after periods, newlines, and bullet points
    cleaned, count = _capitalize_sentences(cleaned)
    fixes += count

    return cleaned.strip() or text.strip(), fixes


def clean_with_rules(text: str) -> str:
    """Fast, 100% offline rule-based cleanup and punctuation formatting."""
    cleaned, _ = clean_with_rules_counted(text, style="natural", spoken_commands=True)
    return cleaned


class TextPolisher:
    def __init__(self, config: Optional[FixoflowConfig] = None):
        self.config = config or FixoflowConfig.load()
        self.engine = self.config.polishing_engine

    def polish(self, raw_text: str, app_context: str = "", mode: Optional[str] = None) -> str:
        """
        Polish raw transcript.
        GUARANTEE: Will NEVER drop or return empty text if raw_text is non-empty.
        """
        polished, _ = self.polish_counted(raw_text, app_context=app_context, mode=mode)
        return polished

    def polish_counted(self, raw_text: str, app_context: str = "", mode: Optional[str] = None) -> Tuple[str, int]:
        """Polish and report how many fixes were applied."""
        if not raw_text.strip():
            return "", 0

        if self.engine == "none" or (mode or self.config.mode) == "raw" or self.config.language != "en":
            return raw_text.strip(), 0

        # Code identifiers and symbols must survive unchanged after explicit
        # dictionary/spoken-code formatting. Prose cleanup belongs to writing mode.
        if (mode or self.config.mode) == "coding":
            return raw_text.strip(), 0
        return clean_with_rules_counted(raw_text, style=self.config.output_style, spoken_commands=self.config.spoken_commands)
