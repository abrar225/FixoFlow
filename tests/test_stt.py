from unittest.mock import Mock
import numpy as np
import pytest
from types import SimpleNamespace
from fixoflow.config import FixoflowConfig
from fixoflow.stt import engine as module


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'mlx_whisper', SimpleNamespace(transcribe=lambda *a, **k: {}))
    model = tmp_path / 'local-model'
    model.mkdir()
    (model / 'config.json').write_text('{}')
    (model / 'weights.npz').write_bytes(b'test weights')
    monkeypatch.delattr(module.sys, '_MEIPASS', raising=False)
    return module.STTEngine(FixoflowConfig(model_name=str(model)))


def test_tiny_tail_is_decoded(engine, monkeypatch):
    seen = []

    def decode(audio, **options):
        seen.append(len(audio))
        assert options['path_or_hf_repo'] == engine.model_name
        return {'text': 'Codex'}
    monkeypatch.setattr(module.mlx_whisper, 'transcribe', decode)
    assert engine.transcribe(np.ones(30, np.float32)) == 'Codex'
    assert seen == [30]


def test_chunk_failure_retains_partial_text_and_stops(engine, monkeypatch):
    monkeypatch.setattr(module, 'slice_audio_for_transcription', lambda *a, **k: [np.ones(2)] * 3)
    calls = []

    def decode(audio, **options):
        calls.append(options)
        if len(calls) == 2:
            raise RuntimeError('Metal allocation failed')
        return {'text': 'first words'}
    monkeypatch.setattr(module.mlx_whisper, 'transcribe', decode)
    with pytest.raises(module.TranscriptionError) as caught:
        engine.transcribe(np.ones(6), initial_prompt='Use Fixoflow terminology')
    assert caught.value.partial_text == 'first words'
    assert caught.value.failed_chunk_index == 1
    assert len(calls) == 2
    assert 'Use Fixoflow terminology' in calls[1]['initial_prompt']


def test_missing_model_never_requests_download(engine, monkeypatch):
    engine.model_name = 'missing/model'
    calls = []

    def resolve(repo_id, **options):
        calls.append(options)
        raise FileNotFoundError('no cache')
    monkeypatch.setattr(module, 'snapshot_download', resolve)
    with pytest.raises(module.TranscriptionError, match='unavailable locally'):
        engine.transcribe(np.ones(10))
    assert calls == [{'local_files_only': True}]


def test_frozen_bundle_model_is_used(engine, tmp_path, monkeypatch):
    bundled = tmp_path / 'models' / 'whisper'
    bundled.mkdir(parents=True)
    (bundled / 'config.json').write_text('{}')
    (bundled / 'weights.npz').write_bytes(b'test weights')
    monkeypatch.setattr(module.sys, '_MEIPASS', str(tmp_path), raising=False)
    engine.model_name = 'mlx-community/whisper-base.en-mlx'
    assert engine.resolve_model_path() == str(bundled)


def test_invalid_decode_result_fails_closed(engine, monkeypatch):
    monkeypatch.setattr(module.mlx_whisper, 'transcribe', lambda *a, **k: {})
    with pytest.raises(module.TranscriptionError):
        engine.transcribe(np.ones(10))


def test_explicit_local_model_takes_priority_over_bundle(engine, tmp_path, monkeypatch):
    bundled = tmp_path / 'models' / 'whisper'
    bundled.mkdir(parents=True)
    monkeypatch.setattr(module.sys, '_MEIPASS', str(tmp_path), raising=False)
    assert engine.resolve_model_path() == engine.model_name


def test_nondefault_repository_does_not_use_bundle(engine, tmp_path, monkeypatch):
    bundled = tmp_path / 'models' / 'whisper'
    bundled.mkdir(parents=True)
    monkeypatch.setattr(module.sys, '_MEIPASS', str(tmp_path), raising=False)
    selected = engine.model_name
    engine.model_name = 'mlx-community/whisper-tiny'
    calls = []

    def resolve(repo_id, **options):
        calls.append(repo_id)
        return selected
    monkeypatch.setattr(module, 'snapshot_download', resolve)
    assert engine.resolve_model_path() == selected
    assert calls == ['mlx-community/whisper-tiny']


def test_incomplete_cached_model_fails_before_decode(engine, tmp_path, monkeypatch):
    incomplete = tmp_path / 'incomplete-cache'
    incomplete.mkdir()
    (incomplete / 'config.json').write_text('{}')
    engine.model_name = 'missing/model'
    monkeypatch.setattr(module, 'snapshot_download', lambda *a, **k: str(incomplete))

    def unexpected_decode(*args, **kwargs):
        pytest.fail('Incomplete model must not reach decoder')
    monkeypatch.setattr(module.mlx_whisper, 'transcribe', unexpected_decode)
    with pytest.raises(module.TranscriptionError, match='missing weights'):
        engine.transcribe(np.ones(10))


def write_capture(path, frames):
    import wave
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(np.full(frames, 1000, dtype='<i2').tobytes())


def test_file_decode_is_bounded_and_keeps_final_samples(engine, tmp_path, monkeypatch):
    engine.config.max_continuous_segment_sec = 2
    path = tmp_path/'capture.wav'
    write_capture(path, 16000*7+31)
    sizes = []
    def decode(audio, model, prompt):
        sizes.append(len(audio))
        return 'words'
    monkeypatch.setattr(engine, '_decode', decode)
    assert engine.transcribe_file(path)
    assert max(sizes) <= 32000 and sum(sizes) == 16000*7+31


def test_truncated_file_fails_once_and_retains_decoded_prefix(engine, tmp_path, monkeypatch):
    engine.config.max_continuous_segment_sec = 2
    path = tmp_path/'truncated.wav'
    write_capture(path, 16000*5)
    with path.open('r+b') as output:
        output.truncate(44+32000*2+20)
    calls = []
    monkeypatch.setattr(engine, '_decode', lambda *args: calls.append(True) or 'first words')
    with pytest.raises(module.TranscriptionError, match='truncated') as caught:
        engine.transcribe_file(path)
    assert calls == [True] and caught.value.partial_text == 'first words'


def test_exact_silence_does_not_call_recognizer(engine, monkeypatch):
    decode = Mock()
    monkeypatch.setattr(engine, '_decode', decode)
    assert engine.transcribe(np.zeros(16000, np.float32)) == ''
    decode.assert_not_called()


def test_custom_english_only_model_is_rejected_for_non_english(engine):
    engine.language = 'hi'
    with pytest.raises(module.TranscriptionError, match='not compatible'):
        engine.resolve_model_path()


@pytest.mark.parametrize('region', ['en-US', 'en-GB', 'en-IN'])
def test_english_decode_request_never_contains_locale_instructions(engine, monkeypatch, region):
    engine.config.english_variant = region
    requests = []

    def decode(audio, **options):
        requests.append(options)
        return {'text': 'Recognized speech.'}
    monkeypatch.setattr(module.mlx_whisper, 'transcribe', decode)
    assert engine.transcribe(np.ones(16000, np.float32)) == 'Recognized speech.'
    assert 'initial_prompt' not in requests[0]
