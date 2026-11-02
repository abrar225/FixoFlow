"""Pipeline behavior at the capture/decode/insertion boundaries, without a microphone."""
import json
from unittest.mock import Mock
import numpy as np
import pytest
from fixoflow.config import FixoflowConfig
from fixoflow.platform.contracts import InsertionOutcome
from fixoflow.storage.db import FixoflowDB
from fixoflow.stt.engine import TranscriptionError
import fixoflow.core as core


@pytest.fixture
def coordinator(tmp_path, monkeypatch):
    db = FixoflowDB(tmp_path / 'history.sqlite')
    monkeypatch.setattr(core.FixoflowDB, 'get_instance', lambda: db)
    monkeypatch.setattr(core, 'play_sound', lambda *_: None)
    monkeypatch.setattr(core, 'notify', lambda *_: None)
    monkeypatch.setattr(core, 'copy_to_clipboard', Mock(return_value=True))
    monkeypatch.setattr(core, 'activate_application', lambda bundle_id, timeout_sec=0.8: False)
    monkeypatch.setattr(core, 'get_frontmost_app_info', lambda: ('Antigravity', 'test.antigravity'))
    # This fixture simulates a Mac-style target on every OS. Resolve its scope
    # at the same fake native boundary instead of querying real Windows/X11.
    from fixoflow.app_identity import app_scope
    monkeypatch.setattr(core, 'get_stable_app_identity', app_scope)
    config = FixoflowConfig(cache_dir=str(tmp_path), mode='auto', spoken_commands=True)
    instance = core.FixoflowCoordinator(config, enable_overlay=False)
    instance.recorder = Mock()
    instance.recorder.needs_cleanup = False
    instance.recorder.start.return_value = tmp_path / 'session_20261018_120000_123456.wav'
    instance.recorder.stop.return_value = (np.ones(16000, dtype=np.float32),
                                           tmp_path / 'session_20261018_120000_123456.wav')
    from fixoflow.audio.recorder import Capture
    instance.recorder.finalize_capture.return_value=Capture(instance.recorder.start.return_value,16000,16000)
    instance.stt = Mock()
    instance.stt.transcribe_file.return_value = 'camel case parse config'
    instance.overlay = Mock()
    return instance


def test_coordinator_lifecycle(coordinator):
    coordinator.start_recording()
    assert coordinator.state == 'RECORDING'
    text = coordinator.stop_and_process(auto_paste=False)
    assert coordinator.state == 'IDLE'
    assert text == 'parseConfig'
    assert coordinator.last_error == ''
    assert coordinator.stt.transcribe_file.call_args.kwargs['initial_prompt'] == ''
    assert coordinator.db.get_history()[0]['final_text'] == 'parseConfig'
    assert coordinator.db.get_history()[0]['id'] == coordinator.session_id
    assert coordinator.db.get_session(coordinator.session_id)['delivery_status'] == 'not_attempted'


def test_session_records_measured_fix_counts(coordinator):
    coordinator.start_recording()
    coordinator.stop_and_process(auto_paste=False)
    row = coordinator.db.get_history()[0]
    assert row['fixes_vocab'] == 1   # spoken-code "camel case" transformation
    assert row['fixes_polish'] == 0  # coding mode leaves prose polishing off


def test_start_failure_rolls_back_state(coordinator):
    coordinator.recorder.start.side_effect = RuntimeError('microphone denied')
    coordinator.start_recording()
    assert coordinator.state == 'IDLE'
    assert 'microphone denied' in coordinator.last_error
    assert coordinator.db.get_session(coordinator.session_id)['status'] == 'capture_failed'


def test_focus_changed_does_not_inject(coordinator, monkeypatch):
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    coordinator.start_recording()
    monkeypatch.setattr(core, 'get_frontmost_app_info', lambda: ('Mail', 'com.apple.mail'))
    coordinator.stop_and_process()
    insert.assert_not_called()
    assert 'Focus moved' in coordinator.last_error
    coordinator.overlay.show_error.assert_called_with('Saved · open History')


def test_focus_restore_returns_text_to_original_app(coordinator, monkeypatch):
    insert = Mock(return_value=InsertionOutcome(True, True, 'inserted'))
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    monkeypatch.setattr(core, 'activate_application', lambda bundle_id, timeout_sec=0.8: True)
    coordinator.start_recording()
    # The user focused Fixoflow, then the original app came back before pasting.
    responses = iter([
        ('Antigravity', 'test.antigravity'),
        ('Fixoflow', 'com.fixoflow.app'),
        ('Antigravity', 'test.antigravity'),
    ])
    monkeypatch.setattr(core, 'get_frontmost_app_info', lambda: next(responses))
    assert coordinator.stop_and_process() == 'parseConfig'
    insert.assert_called_once_with('parseConfig', expected_target='test.antigravity',
                                   cancelled=coordinator._cancel_requested.is_set)
    coordinator.overlay.show_success.assert_called_with('Paste sent')


def test_paste_failure_is_copied_and_not_reported_as_success(coordinator, monkeypatch):
    monkeypatch.setattr(core, 'insert_text_at_cursor', lambda *_, **kwargs: InsertionOutcome(False, True, 'permission'))
    coordinator.start_recording()
    assert coordinator.stop_and_process() == 'parseConfig'
    coordinator.overlay.show_success.assert_not_called()
    assert 'Accessibility' in coordinator.last_error
    coordinator.overlay.show_error.assert_called_with('Copied · enable Accessibility')


def test_unidentified_target_copies_instead_of_guessing(coordinator, monkeypatch):
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    monkeypatch.setattr(core, 'get_frontmost_app_info', lambda: ('Unknown', ''))
    coordinator.start_recording()
    text = coordinator.stop_and_process()
    insert.assert_not_called()
    assert 'not identified' in coordinator.last_error
    core.copy_to_clipboard.assert_called_once_with(text)


def test_decode_failure_saves_partial_and_never_pastes(coordinator, monkeypatch):
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    coordinator.stt.transcribe_file.side_effect = TranscriptionError(
        'second chunk failed', partial_text='first words', failed_chunk_index=1)
    coordinator.start_recording()
    assert coordinator.stop_and_process() == ''
    insert.assert_not_called()
    assert coordinator.db.get_history() == []
    path = coordinator.recorder.start.return_value.with_suffix('.transcript.json')
    assert json.loads(path.read_text()) == {'status':'incomplete', 'text':'first words', 'raw_text':'first words'}


def test_formatter_failure_retains_raw(coordinator):
    coordinator.learner.format_for_mode_counted = Mock(side_effect=RuntimeError('format error'))
    coordinator.start_recording()
    assert coordinator.stop_and_process(auto_paste=False) == 'camel case parse config'


def test_cancel_keeps_audio_without_asr_or_paste(coordinator, monkeypatch):
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    coordinator.start_recording()
    coordinator.cancel_recording()
    assert coordinator.state == 'IDLE'
    coordinator.recorder.stop.assert_called_once()
    coordinator.stt.transcribe_file.assert_not_called()
    insert.assert_not_called()
    assert coordinator.db.get_history() == []
    assert coordinator.db.get_session(coordinator.session_id)['status'] == 'cancelled'


def test_session_identity_exists_before_microphone_open(coordinator):
    path = coordinator.recorder.start.return_value
    def open_microphone():
        assert coordinator.db.get_session(coordinator.session_id)['status'] == 'starting'
        return path
    coordinator.recorder.start.side_effect = open_microphone
    coordinator.start_recording()
    assert coordinator.state == 'RECORDING'


def test_journal_failure_does_not_open_microphone(coordinator):
    coordinator.db.begin_session = Mock(side_effect=OSError('disk full'))
    coordinator.start_recording()
    coordinator.recorder.start.assert_not_called()
    assert coordinator.state == 'IDLE'


@pytest.mark.parametrize('style,expected', [('natural','corrected words'),('verbatim','camel case parse config')])
def test_explicit_approved_memory_respects_verbatim(coordinator, style, expected):
    coordinator.start_recording()
    coordinator.stop_and_process(auto_paste=False)
    cid = coordinator.db.propose_correction(coordinator.session_id, 'corrected words')
    coordinator.db.approve_correction(cid)
    coordinator.config.output_style = style
    coordinator.start_recording()
    assert coordinator.stop_and_process(auto_paste=False) == expected


def test_dispatch_is_not_claimed_as_verified_delivery(coordinator, monkeypatch):
    monkeypatch.setattr(core, 'insert_text_at_cursor', lambda *a, **k: InsertionOutcome(True,True,'inserted'))
    coordinator.start_recording()
    coordinator.stop_and_process()
    assert coordinator.db.get_session(coordinator.session_id)['delivery_status'] == 'dispatch_sent'


def recovery_fixture(coordinator, status='cancelled'):
    import wave
    path=coordinator.recorder.start.return_value
    with wave.open(str(path),'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000)
        audio.writeframes(b'\0\0'*160)
    sid=coordinator.db.begin_session('Antigravity','test.antigravity','model','en','auto')
    coordinator.db.register_session_artifact(path,path.parent)
    coordinator.db.update_session(sid,status=status,audio_path=str(path))
    return sid,path


def test_recovery_uses_new_owned_copy_and_never_pastes(coordinator,monkeypatch):
    sid,path=recovery_fixture(coordinator)
    insert=Mock();monkeypatch.setattr(core,'insert_text_at_cursor',insert)
    assert coordinator.recover_session(sid)=='parseConfig'
    assert coordinator.session_id!=sid
    row=coordinator.db.get_history()[0]
    assert row['id']==coordinator.session_id and row['audio_path']!=str(path)
    assert path.exists() and coordinator.db.get_session(sid)['status']=='recovered'
    assert coordinator.db.get_recovery_items()[0]['status']=='recovered'
    insert.assert_not_called();coordinator.recorder.start.assert_not_called()


def test_active_recovery_is_refused_and_source_remains_unchanged(coordinator):
    sid,path=recovery_fixture(coordinator,status='recording')
    assert coordinator.recover_session(sid)==''
    assert 'active' in coordinator.last_error
    assert coordinator.db.get_session(sid)['status']=='recording'
    assert coordinator.db.get_history()==[] and path.exists()


def test_recovery_delete_removes_owned_audio_without_completed_history(coordinator):
    sid,path=recovery_fixture(coordinator)
    coordinator.db.delete_recovery_item(sid)
    assert not path.exists() and coordinator.db.get_session(sid) is None


def test_history_failure_stays_recoverable_and_never_reports_history_saved(coordinator,monkeypatch):
    coordinator.db.record_session=Mock(side_effect=OSError('disk full'))
    insert=Mock();monkeypatch.setattr(core,'insert_text_at_cursor',insert)
    coordinator.start_recording()
    assert coordinator.stop_and_process()=='parseConfig'
    assert coordinator.db.get_session(coordinator.session_id)['status']=='history_failed'
    assert coordinator.db.get_recovery_items() and not coordinator.db.get_history()
    assert 'could not be saved' in coordinator.last_error
    insert.assert_not_called()


def test_failed_recovery_history_write_does_not_retire_original(coordinator):
    sid,path=recovery_fixture(coordinator)
    coordinator.db.record_session=Mock(side_effect=OSError('disk full'))
    coordinator.recover_session(sid)
    assert coordinator.db.get_session(sid)['status']=='cancelled'
    assert len(coordinator.db.get_recovery_items())==2 and path.exists()


def test_unrelated_preferences_preserve_warm_engine_and_recorder(coordinator,monkeypatch):
    import dataclasses
    candidate=dataclasses.replace(coordinator.config,sound_enabled=False)
    monkeypatch.setattr(candidate,'save',Mock())
    engine,recorder=coordinator.stt,coordinator.recorder
    coordinator.apply_config(candidate)
    assert coordinator.stt is engine and coordinator.recorder is recorder
    engine.resolve_model_path.assert_not_called()
    assert coordinator.config.sound_enabled is False


def test_verbatim_bypasses_dictionary_and_code_commands(coordinator):
    coordinator.config.output_style='verbatim'
    coordinator.db.upsert_word('camel','changed')
    coordinator.start_recording()
    assert coordinator.stop_and_process(auto_paste=False)=='camel case parse config'


def test_spoken_code_commands_require_opt_in(coordinator):
    coordinator.config.spoken_commands=False
    coordinator.start_recording()
    assert coordinator.stop_and_process(auto_paste=False)=='camel case parse config'


def test_cancellation_during_focus_restore_prevents_insertion(coordinator,monkeypatch):
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    coordinator.start_recording()
    monkeypatch.setattr(core,'get_frontmost_app_info',lambda:('Other','other'))
    def activate(*args):
        coordinator.request_cancel()
        return False
    monkeypatch.setattr(core,'activate_application',activate)
    coordinator.stop_and_process()
    insert.assert_not_called()
    assert 'Cancelled' in coordinator.last_error


@pytest.mark.parametrize('shutdown',[False,True])
def test_cancel_before_queued_start_is_not_reset(coordinator,monkeypatch,shutdown):
    from fixoflow.controls import DictationControls

    class Deferred:
        def __init__(self):self.queue=[]
        def submit(self,fn,*args):self.queue.append((fn,args))

        def drain(self):
            while self.queue:
                fn, args = self.queue.pop(0)
                fn(*args)

        def shutdown(self,wait=True):self.drain()
    executor = Deferred()
    controls = DictationControls(coordinator, coordinator.config, executor=executor)
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    controls.hold_press()
    controls.hold_release()
    if shutdown:
        controls.shutdown()
    else:
        controls.cancel()
        executor.drain()
    coordinator.stt.transcribe_file.assert_not_called()
    insert.assert_not_called()
    assert coordinator._cancel_requested.is_set() and controls.state=='IDLE'
