"""Pipeline behavior at the capture/decode/insertion boundaries, without a microphone."""
import json
from unittest.mock import Mock
import numpy as np
import pytest
from fixoflow.config import FixoflowConfig
from fixoflow.platform.macos import InsertionOutcome
from fixoflow.storage.db import FixoflowDB
from fixoflow.stt.engine import TranscriptionError
import fixoflow.core as core


@pytest.fixture
def coordinator(tmp_path, monkeypatch):
    db = FixoflowDB(tmp_path / 'history.sqlite')
    monkeypatch.setattr(core.FixoflowDB, 'get_instance', lambda: db)
    monkeypatch.setattr(core, 'play_sound', lambda *_: None)
    monkeypatch.setattr(core, 'notify', lambda *_: None)
    monkeypatch.setattr(core, 'activate_application', lambda bundle_id, timeout_sec=0.8: False)
    monkeypatch.setattr(core, 'get_frontmost_app_info', lambda: ('Antigravity', 'test.antigravity'))
    config = FixoflowConfig(cache_dir=str(tmp_path), mode='auto')
    instance = core.FixoflowCoordinator(config, enable_overlay=False)
    instance.recorder = Mock()
    instance.recorder.start.return_value = tmp_path / 'session.wav'
    instance.recorder.stop.return_value = (np.ones(16000, dtype=np.float32), tmp_path / 'session.wav')
    instance.stt = Mock()
    instance.stt.transcribe.return_value = 'camel case parse config'
    instance.overlay = Mock()
    return instance


def test_coordinator_lifecycle(coordinator):
    coordinator.start_recording()
    assert coordinator.state == 'RECORDING'
    text = coordinator.stop_and_process(auto_paste=False)
    assert coordinator.state == 'IDLE'
    assert text == 'parseConfig'
    assert coordinator.last_error == ''
    assert 'Antigravity' in coordinator.stt.transcribe.call_args.kwargs['initial_prompt']
    assert coordinator.db.get_history()[0]['final_text'] == 'parseConfig'


def test_start_failure_rolls_back_state(coordinator):
    coordinator.recorder.start.side_effect = RuntimeError('microphone denied')
    coordinator.start_recording()
    assert coordinator.state == 'IDLE'
    assert 'microphone denied' in coordinator.last_error


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
    insert.assert_called_once_with('parseConfig')
    coordinator.overlay.show_success.assert_called_with('Paste sent')


def test_paste_failure_is_copied_and_not_reported_as_success(coordinator, monkeypatch):
    monkeypatch.setattr(core, 'insert_text_at_cursor', lambda *_: InsertionOutcome(False, True, 'permission'))
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
    coordinator.stop_and_process()
    insert.assert_not_called()
    assert 'not identified' in coordinator.last_error


def test_decode_failure_saves_partial_and_never_pastes(coordinator, monkeypatch):
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    coordinator.stt.transcribe.side_effect = TranscriptionError('second chunk failed', partial_text='first words', failed_chunk_index=1)
    coordinator.start_recording()
    assert coordinator.stop_and_process() == ''
    insert.assert_not_called()
    assert coordinator.db.get_history() == []
    path = coordinator.recorder.start.return_value.with_suffix('.transcript.json')
    assert json.loads(path.read_text()) == {'status':'incomplete', 'text':'first words', 'raw_text':'first words'}


def test_formatter_failure_retains_raw(coordinator):
    coordinator.learner.format_for_mode = Mock(side_effect=RuntimeError('format error'))
    coordinator.start_recording()
    assert coordinator.stop_and_process(auto_paste=False) == 'camel case parse config'


def test_cancel_keeps_audio_without_asr_or_paste(coordinator, monkeypatch):
    insert = Mock()
    monkeypatch.setattr(core, 'insert_text_at_cursor', insert)
    coordinator.start_recording()
    coordinator.cancel_recording()
    assert coordinator.state == 'IDLE'
    coordinator.recorder.stop.assert_called_once()
    coordinator.stt.transcribe.assert_not_called()
    insert.assert_not_called()
    assert coordinator.db.get_history() == []
