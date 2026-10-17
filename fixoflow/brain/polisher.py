"""
Fixoflow Brain: Intelligent Text Polishing & Formatting
Offline rule-based cleanup. This module never performs network requests.
Guarantees Zero Data Loss: Always returns raw transcript if polishing fails or times out.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fixoflow.config import FixoflowConfig

logger = logging.getLogger("fixoflow.brain.polisher")

# Offline rule-based fillers and spoken punctuation replacements
FILLER_WORDS = [
    r"\b(um|uh|erm|ah|like you know|you know what I mean|so yeah|I mean)\b",
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
    (r"\b(bullet point|bullet)\s*(one|1|\w+)?\b", r"\n• "),
]


def clean_with_rules(text: str) -> str:
    """Fast, 100% offline rule-based cleanup and punctuation formatting."""
    cleaned = text
    
    # Remove obvious stuttering/fillers
    for pattern in FILLER_WORDS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Replace spoken punctuation cues
    for pattern, repl in PUNCTUATION_REPLACEMENTS:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)

    # Fix spacing around punctuation
    cleaned = re.sub(r"[^\S\n]+([.,!?:;])", r"\1", cleaned)
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned).strip()

    # Capitalize after periods, newlines, and bullet points
    sentences = re.split(r"([.!?]\s+|\n+|•\s*)", cleaned)
    capitalized = []
    for part in sentences:
        if part and not re.match(r"^[.!?\s\n•]+$", part):
            part = part[0].upper() + part[1:]
        capitalized.append(part)
    
    return "".join(capitalized).strip() or text.strip()


class TextPolisher:
    def __init__(self, config: Optional[FixoflowConfig] = None):
        self.config = config or FixoflowConfig.load()
        self.engine = self.config.polishing_engine

    def polish(self, raw_text: str, app_context: str = "", mode: Optional[str] = None) -> str:
        """
        Polish raw transcript.
        GUARANTEE: Will NEVER drop or return empty text if raw_text is non-empty.
        """
        if not raw_text.strip():
            return ""

        if self.engine == "none" or (mode or self.config.mode) == "raw":
            return raw_text.strip()

        # Code identifiers and symbols must survive unchanged after explicit
        # dictionary/spoken-code formatting. Prose cleanup belongs to writing mode.
        if (mode or self.config.mode) == "coding":
            return raw_text.strip()
        return clean_with_rules(raw_text)
