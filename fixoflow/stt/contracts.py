"""Portable capability metadata. Absent scores are not probabilities."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RecognitionCapabilities:
    backend: str
    vocabulary_hints: bool = True
    segment_cancellation: bool = True
    interrupt_native_decode: bool = False
    streaming_output: bool = False
    calibrated_confidence: bool = False
    local_only: bool = True
