"""
Unit tests for Fixoflow Audio Slicer.
Verifies zero data loss across chunk boundaries on long audio recordings.
"""
import numpy as np

from fixoflow.audio.slicer import slice_audio_for_transcription, find_pause_split_point


def test_short_audio_not_sliced():
    sample_rate = 16000
    # 5 seconds of audio
    audio = np.random.randn(sample_rate * 5).astype(np.float32) * 0.1
    slices = slice_audio_for_transcription(audio, sample_rate=sample_rate, max_chunk_sec=24.0)
    assert len(slices) == 1
    assert len(slices[0]) == len(audio)


def test_long_audio_sliced_with_zero_sample_loss():
    sample_rate = 16000
    # 60 seconds of audio (should be sliced into at least 3 chunks)
    total_seconds = 60
    audio = np.random.randn(sample_rate * total_seconds).astype(np.float32) * 0.1

    # Insert silence valleys every 18 seconds to simulate natural breathing pauses
    for pause_sec in [18, 36, 54]:
        idx = int(pause_sec * sample_rate)
        audio[idx: idx + sample_rate] = 0.0  # 1 second of silence

    slices = slice_audio_for_transcription(
        audio,
        sample_rate=sample_rate,
        max_chunk_sec=24.0,
        min_search_sec=15.0,
    )

    assert len(slices) >= 3
    # Check that total samples across all slices exactly equal the original audio
    total_sliced_samples = sum(len(s) for s in slices)
    assert total_sliced_samples == len(audio), f"Expected {len(audio)} samples, got {total_sliced_samples}"


def test_find_pause_split_point():
    sample_rate = 16000
    # 10 seconds of audio: active sound everywhere except at 6.0 - 7.0 seconds
    audio = np.ones(sample_rate * 10, dtype=np.float32) * 0.5
    silence_start = int(6.0 * sample_rate)
    silence_end = int(7.0 * sample_rate)
    audio[silence_start:silence_end] = 0.0

    split = find_pause_split_point(
        audio=audio,
        sample_rate=sample_rate,
        search_start_sec=5.0,
        search_end_sec=8.0,
    )
    # Split should fall inside the quiet region
    assert silence_start <= split <= silence_end
