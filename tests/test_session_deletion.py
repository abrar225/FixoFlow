import json
import wave
import pytest
from fixoflow.storage.db import FixoflowDB


def fixture_session(tmp_path):
    audio=tmp_path/'session_20261018_120000_123456.wav'
    with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*160)
    sidecar=audio.with_suffix('.transcript.json');sidecar.write_text(json.dumps({'raw_text':'raw','text':'Final'}))
    db=FixoflowDB(tmp_path/'history.sqlite');sid=db.record_session('raw','Final','Editor',.01,1,audio_path=str(audio))
    return db,sid,audio,sidecar


def test_delete_removes_owned_linked_files_only(tmp_path):
    db,sid,audio,sidecar=fixture_session(tmp_path)
    for file in [audio,sidecar]:db.register_session_artifact(file,tmp_path)
    unrelated=tmp_path/'keep.wav';unrelated.write_text('keep')
    db.delete_history_item(sid,cache_root=tmp_path)
    assert not audio.exists() and not sidecar.exists() and not db.get_history()
    assert unrelated.read_text()=='keep'


def test_explicit_legacy_delete_validates_generated_audio_and_matching_sidecar(tmp_path):
    db,sid,audio,sidecar=fixture_session(tmp_path)
    db.delete_history_item(sid,cache_root=tmp_path)
    assert not audio.exists() and not sidecar.exists()


def test_replaced_or_symlinked_files_are_not_deleted(tmp_path):
    db,sid,audio,sidecar=fixture_session(tmp_path)
    db.register_session_artifact(audio,tmp_path);db.register_session_artifact(sidecar,tmp_path)
    saved=audio.with_suffix('.backup');audio.rename(saved);audio.write_bytes(b'foreign')
    with pytest.raises(ValueError,match='replaced'):db.delete_history_item(sid,cache_root=tmp_path)
    assert audio.read_bytes()==b'foreign' and db.get_history()
    audio.unlink();audio.symlink_to(saved)
    with pytest.raises(ValueError):db.delete_history_item(sid,cache_root=tmp_path)
    assert saved.exists()


def test_failed_cleanup_retains_history_and_can_retry(tmp_path,monkeypatch):
    db,sid,audio,sidecar=fixture_session(tmp_path)
    for file in [audio,sidecar]:db.register_session_artifact(file,tmp_path)
    import fixoflow.storage.artifacts as artifacts
    real=artifacts.unlink_owned
    monkeypatch.setattr(artifacts,'unlink_owned',lambda *a:(_ for _ in ()).throw(PermissionError('busy')))
    with pytest.raises(PermissionError):db.delete_history_item(sid,cache_root=tmp_path)
    assert db.get_history()
    monkeypatch.setattr(artifacts,'unlink_owned',real)
    db.delete_history_item(sid,cache_root=tmp_path)
    assert not db.get_history()

@pytest.mark.parametrize('malformation',['wav','json-list','json-null'])
def test_malformed_legacy_data_is_reported_without_deletion(tmp_path,malformation):
    db,sid,audio,sidecar=fixture_session(tmp_path)
    if malformation=='wav':audio.write_bytes(b'broken')
    else:sidecar.write_text('[]' if malformation=='json-list' else 'null')
    with pytest.raises(ValueError):db.delete_history_item(sid,cache_root=tmp_path)
    assert audio.exists() and sidecar.exists() and db.get_history()


def test_registered_ownership_survives_config_cache_move(tmp_path):
    old=tmp_path/'old';old.mkdir()
    db,sid,audio,sidecar=fixture_session(old)
    for file in [audio,sidecar]:db.register_session_artifact(file,old)
    db.delete_history_item(sid,cache_root=tmp_path/'new')
    assert not audio.exists() and not sidecar.exists()
