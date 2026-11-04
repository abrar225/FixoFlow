"""Platform-neutral delivery result."""
from dataclasses import dataclass


@dataclass(frozen=True)
class InsertionOutcome:
    inserted: bool
    copied: bool
    reason: str
    clipboard_restore_pending: bool = False
    clipboard_restore_unavailable: str = ''
