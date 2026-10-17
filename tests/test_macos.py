from unittest.mock import Mock
from fixoflow.platform import macos


def test_missing_accessibility_still_copies_and_reports_permission(monkeypatch):
    # Actual PyObjC framework export must exist; Quartz does not own this API.
    assert callable(macos.ApplicationServices.AXIsProcessTrusted)
    prompts = []
    monkeypatch.setattr(macos, 'accessibility_trusted',
                        lambda prompt=False: prompts.append(prompt) or False)
    clipboard = Mock(return_value=True)
    monkeypatch.setattr(macos, 'copy_to_clipboard', clipboard)
    event = Mock()
    monkeypatch.setattr(macos.Quartz, 'CGEventCreateKeyboardEvent', event)
    outcome = macos.insert_text_at_cursor('keep this text')
    clipboard.assert_called_once_with('keep this text')
    event.assert_not_called()
    assert outcome == macos.InsertionOutcome(False, True, 'permission')
    assert prompts == [False, True]


def test_failed_clipboard_prevents_event_injection(monkeypatch):
    monkeypatch.setattr(macos, 'accessibility_trusted', lambda prompt=False: True)
    monkeypatch.setattr(macos, 'copy_to_clipboard', lambda _: False)
    event = Mock()
    monkeypatch.setattr(macos.Quartz, 'CGEventCreateKeyboardEvent', event)
    outcome = macos.insert_text_at_cursor('keep this text')
    event.assert_not_called()
    assert outcome == macos.InsertionOutcome(False, False, 'clipboard-failed')


def test_successful_insertion_posts_command_v(monkeypatch):
    monkeypatch.setattr(macos, 'accessibility_trusted', lambda prompt=False: True)
    monkeypatch.setattr(macos, 'copy_to_clipboard', lambda _: True)
    monkeypatch.setattr(macos.time, 'sleep', lambda _: None)
    keys = []
    monkeypatch.setattr(macos.Quartz, 'CGEventCreateKeyboardEvent',
                        lambda system, keycode, down: keys.append((keycode, down)) or Mock())
    flags = []
    monkeypatch.setattr(macos.Quartz, 'CGEventSetFlags', lambda event, value: flags.append(value))
    posted = []
    monkeypatch.setattr(macos.Quartz, 'CGEventPost', lambda tap, event: posted.append(event))
    outcome = macos.insert_text_at_cursor('hello')
    assert outcome == macos.InsertionOutcome(True, True, 'inserted')
    assert keys == [(macos.KEY_CODE_V, True), (macos.KEY_CODE_V, False)]
    assert flags == [macos.Quartz.kCGEventFlagMaskCommand, 0]
    assert len(posted) == 2
