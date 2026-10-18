"""
Fixoflow Acoustic Pre-Filtering Module.
Applies zero-phase Butterworth bandpass filtering (80 Hz - 7500 Hz)
and peak normalization (-1.0 dB FS) to attenuate out-of-band rumble
and condition levels before Mel spectrogram extraction.
"""

from typing import Optional
import numpy as np
import scipy.signal as signal


def create_bandpass_sos(
    sample_rate: int = 16000,
    low_cutoff: float = 80.0,
    high_cutoff: float = 7500.0,
    order: int = 4,
) -> np.ndarray:
    """Design a second-order sections (SOS) bandpass Butterworth filter."""
    nyquist = sample_rate / 2.0
    low = max(1.0, low_cutoff) / nyquist
    high = min(nyquist - 1.0, high_cutoff) / nyquist
    return signal.butter(order, [low, high], btype="bandpass", output="sos")


# Pre-compute standard 16kHz SOS filter for zero-latency execution
_SOS_16K: Optional[np.ndarray] = None


def get_default_sos(sample_rate: int = 16000) -> np.ndarray:
    global _SOS_16K
    if sample_rate == 16000:
        if _SOS_16K is None:
            _SOS_16K = create_bandpass_sos(16000, 80.0, 7500.0, 4)
        return _SOS_16K
    return create_bandpass_sos(sample_rate, 80.0, min(sample_rate / 2.0 - 100, 7500.0), 4)


def apply_bandpass(
    audio: np.ndarray,
    sample_rate: int = 16000,
    low_cutoff: float = 80.0,
    high_cutoff: float = 7500.0,
) -> np.ndarray:
    """
    Applies forward-backward zero-phase filtering to prevent phase distortion
    of speech transients.
    """
    if audio.ndim != 1 or len(audio) < 64:
        return audio

    # Ensure float32 format
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    sos = (get_default_sos(sample_rate) if (low_cutoff, high_cutoff) == (80.0, 7500.0)
           else create_bandpass_sos(sample_rate, low_cutoff, high_cutoff))
    filtered = signal.sosfiltfilt(sos, audio)
    return filtered.astype(np.float32)


def normalize_peak(audio: np.ndarray, target_db: float = -1.0) -> np.ndarray:
    """
    Normalizes audio peak amplitude to target_db FS (default -1.0 dB = ~0.891).
    Avoids clipping while boosting soft whispered speech.
    """
    if audio.size == 0:
        return audio

    peak = float(np.max(np.abs(audio)))
    if peak <= 1e-6:
        # Near silence, do not amplify noise floor
        return audio

    target_linear = 10.0 ** (target_db / 20.0)
    gain = target_linear / peak
    # Guard against extreme amplification of pure quiet background noise
    gain = min(gain, 12.0)

    normalized = audio * gain
    return np.clip(normalized, -1.0, 1.0).astype(np.float32)


def clean_audio_pipeline(
    audio: np.ndarray,
    sample_rate: int = 16000,
    target_db: float = -1.0,
) -> np.ndarray:
    """
    Complete acoustic conditioning pipeline:
    1. Zero-phase bandpass filter (80Hz - 7.5kHz)
    2. Peak normalization to -1.0 dB FS
    """
    filtered = apply_bandpass(audio, sample_rate=sample_rate)
    return normalize_peak(filtered, target_db=target_db)
