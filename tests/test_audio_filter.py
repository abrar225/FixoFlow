import numpy as np
from fixoflow.audio.filter import apply_bandpass, normalize_peak, clean_audio_pipeline


def test_bandpass_attenuates_rumble():
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    # 30 Hz sub-bass rumble
    rumble = np.sin(2 * np.pi * 30 * t).astype(np.float32)
    filtered = apply_bandpass(rumble, sample_rate=sr)
    
    # 30 Hz should be significantly attenuated (>15 dB attenuation, power < 0.2)
    orig_energy = np.mean(rumble ** 2)
    filt_energy = np.mean(filtered ** 2)
    assert filt_energy < 0.1 * orig_energy


def test_bandpass_preserves_speech_frequencies():
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    # 1000 Hz vowel formant
    speech_tone = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
    filtered = apply_bandpass(speech_tone, sample_rate=sr)
    
    orig_energy = np.mean(speech_tone ** 2)
    filt_energy = np.mean(filtered ** 2)
    # Should retain > 90% energy
    assert filt_energy > 0.85 * orig_energy


def test_peak_normalization():
    # Quiet speech with peak 0.1
    quiet = (np.sin(np.linspace(0, 10, 1600)) * 0.1).astype(np.float32)
    normalized = normalize_peak(quiet, target_db=-1.0)
    
    peak = np.max(np.abs(normalized))
    # Target -1.0 dB is approx 0.891
    assert 0.88 <= peak <= 0.90


def test_clean_audio_pipeline_edge_cases():
    # Empty
    empty = np.array([], dtype=np.float32)
    res = clean_audio_pipeline(empty)
    assert len(res) == 0
    
    # Very short
    short = np.array([0.1, -0.2, 0.3], dtype=np.float32)
    res_short = clean_audio_pipeline(short)
    assert len(res_short) == 3
