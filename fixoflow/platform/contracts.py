"""Platform-neutral delivery result."""
from dataclasses import dataclass


@dataclass(frozen=True)
class InsertionOutcome:
    inserted: bool
    copied: bool
    reason: str
