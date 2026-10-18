"""
Fixoflow Audio Slicer
Splits long audio into bounded adjacent segments using minimum-energy splits.
Retaining all samples does not guarantee perfect word continuity at a boundary.
"""
from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np

logger = logging.getLogger("fixoflow.audio.slicer")


def find_pause_split_point(
    audio: np.ndarray,
    sample_rate: int,
    search_start_sec: float,
    search_end_sec: float,
    window_ms: int = 100,
) -> int:
    """
    Search within [search_start_sec, search_end_sec] for the point of minimum energy (quietest pause).
    Returns sample index where the split should occur.
    """
    start_sample = int(search_start_sec * sample_rate)
    end_sample = min(int(search_end_sec * sample_rate), len(audio))
    
    if start_sample >= end_sample:
        return end_sample

    window_size = int(sample_rate * (window_ms / 1000.0))
    region = audio[start_sample:end_sample]
    
    # Compute rolling energy across windows
    num_windows = len(region) // window_size
    if num_windows <= 1:
        return (start_sample + end_sample) // 2

    energies = []
    for i in range(num_windows):
        win = region[i * window_size : (i + 1) * window_size]
        energy = np.sum(win**2)
        energies.append(energy)

    # Find window with minimal acoustic energy (silence / pause)
    min_idx = int(np.argmin(energies))
    split_sample = start_sample + (min_idx * window_size) + (window_size // 2)
    return split_sample


def slice_audio_for_transcription(
    audio: np.ndarray,
    sample_rate: int = 16000,
    max_chunk_sec: float = 24.0,
    min_search_sec: float = 16.0,
) -> List[np.ndarray]:
    """
    Slices audio longer than max_chunk_sec into logical segments at natural pause points.
    Guarantees that no audio is dropped and Whisper never exceeds its optimal context window.
    """
    total_sec = len(audio) / sample_rate
    if total_sec <= max_chunk_sec:
        return [audio]

    logger.info("Audio length %.2fs exceeds chunk limit %.2fs; performing intelligent pause slicing.", total_sec, max_chunk_sec)
    slices: List[np.ndarray] = []
    current_offset = 0
    total_samples = len(audio)

    while current_offset < total_samples:
        remaining_samples = total_samples - current_offset
        remaining_sec = remaining_samples / sample_rate

        if remaining_sec <= max_chunk_sec:
            slices.append(audio[current_offset:])
            break

        # Search for a natural pause between min_search_sec and max_chunk_sec
        split_sample = find_pause_split_point(
            audio=audio,
            sample_rate=sample_rate,
            search_start_sec=(current_offset / sample_rate) + min_search_sec,
            search_end_sec=(current_offset / sample_rate) + max_chunk_sec,
        )

        # Safety fallback: ensure forward progress
        if split_sample <= current_offset:
            split_sample = current_offset + int(max_chunk_sec * sample_rate)

        chunk = audio[current_offset:split_sample]
        slices.append(chunk)
        logger.debug("Sliced chunk: %.2fs to %.2fs (length %.2fs)", current_offset / sample_rate, split_sample / sample_rate, len(chunk) / sample_rate)
        current_offset = split_sample

    logger.info("Sliced %.2fs of audio into %d seamless chunks with all samples retained.", total_sec, len(slices))
    return slices
