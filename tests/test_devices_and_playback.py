import json
import wave
from types import SimpleNamespace

import pytest

from fixoflow.audio.devices import input_devices, resolve_input_device
from fixoflow.config import FixoflowConfig
from fixoflow.storage.db import FixoflowDB


def backend(devices):
    return SimpleNamespace(query_hostapis=lambda:[{'name':'Test Audio'}], query_devices=lambda:devices)


def test_saved_mic_is_resolved_after_device_indices_change():
    mic = {'name':'USB Mic', 'hostapi':0, 'max_input_channels':1}
    speaker = {'name':'Speaker', 'hostapi':0, 'max_input_channels':0}
    saved = input_devices(backend([mic,speaker]))[0]['id']
    assert resolve_input_device(saved, backend([speaker,mic])) == 1
    assert resolve_input_device('', backend([])) is None
    with pytest.raises(ValueError,match='unavailable or ambiguous'):
        resolve_input_device(saved, backend([speaker]))
    with pytest.raises(ValueError,match='unavailable or ambiguous'):
        resolve_input_device(saved, backend([mic,mic]))


@pytest.mark.parametrize('value',[1, 'not-json', '{}', '[1,2]', '["only-one"]'])
def test_invalid_mic_preferences_are_rejected(value):
    with pytest.raises(ValueError,match='microphone'):
        FixoflowConfig(input_device=value).validate()


def owned_audio(tmp_path):
    path = tmp_path/'session_20261102_120000_123456.wav'
    with wave.open(str(path),'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\0\0'*160)
    db = FixoflowDB(tmp_path/'db.sqlite')
    sid = db.record_session('raw','final','Test',.01,1,audio_path=str(path))
    db.register_session_artifact(path,tmp_path)
    return db,sid,path


def test_playback_reads_owned_valid_audio_and_rejects_missing_or_replaced(tmp_path):
    db,sid,path = owned_audio(tmp_path)
    assert db.read_history_audio(sid) == path.read_bytes()
    with pytest.raises(ValueError,match='limit'):
        db.read_history_audio(sid,max_bytes=50)
    original = path.with_suffix('.backup')
    path.rename(original); path.write_bytes(b'foreign')
    with pytest.raises(ValueError,match='replaced'):
        db.read_history_audio(sid)
    path.unlink(); path.symlink_to(original)
    with pytest.raises(ValueError,match='symbolic'):
        db.read_history_audio(sid)


def test_playback_rejects_invalid_owned_audio_and_unregistered_paths(tmp_path):
    db,sid,path = owned_audio(tmp_path)
    path.write_bytes(b'invalid WAV')
    with pytest.raises(ValueError,match='valid WAV'):
        db.read_history_audio(sid)
    other = db.record_session('raw','final','Test',1,1,audio_path=str(tmp_path/'private.wav'))
    with pytest.raises(ValueError,match='ownership'):
        db.read_history_audio(other)
