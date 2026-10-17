from types import SimpleNamespace
from unittest.mock import Mock
import threading

import pytest
from pynput import keyboard
from fixoflow.controls import DictationControls, shortcut_label
from fixoflow.config import FixoflowConfig
from fixoflow.daemon import FixoflowDaemon


class DeferredExecutor:
    def __init__(self):
        self.pending = []
    def submit(self, fn, *args):
        self.pending.append((fn, args))
    def drain(self):
        while self.pending:
            fn, args = self.pending.pop(0)
            fn(*args)
    def shutdown(self, wait=True):
        self.drain()


@pytest.fixture
def interaction():
    coordinator = SimpleNamespace(state='IDLE', recorder=SimpleNamespace(is_recording=False), events=[])
    def start():
        coordinator.events.append('start')
        coordinator.state = 'RECORDING'
        coordinator.recorder.is_recording = True
    def finish(auto_paste):
        coordinator.events.append('stop')
        coordinator.state = 'IDLE'
        coordinator.recorder.is_recording = False
    def cancel():
        coordinator.events.append('cancel')
        coordinator.state = 'IDLE'
        coordinator.recorder.is_recording = False
    coordinator.start_recording = start
    coordinator.stop_and_process = finish
    coordinator.cancel_recording = cancel
    executor = DeferredExecutor()
    clock = [0.0]
    controls = DictationControls(coordinator, FixoflowConfig(), executor=executor, clock=lambda: clock[0])
    return controls, coordinator, executor, clock


def test_two_fast_taps_before_microphone_opens_stop_once(interaction):
    controls, backend, executor, clock = interaction
    controls.press(); clock[0] = .1; controls.release()
    assert controls.state == 'RECORDING'
    assert backend.events == []  # microphone start still pending
    clock[0] = .2; controls.press(); clock[0] = .3; controls.release()
    assert controls.state == 'PROCESSING'
    executor.drain()
    assert backend.events == ['start', 'stop']
    assert controls.state == 'IDLE'


def test_hold_records_until_release_even_when_start_is_slow(interaction):
    controls, backend, executor, clock = interaction
    controls.press(); clock[0] = .7; controls.release()
    executor.drain()
    assert backend.events == ['start', 'stop']


def test_autorepeat_does_not_start_multiple_sessions(interaction):
    controls, backend, executor, clock = interaction
    for _ in range(8): controls.press()
    clock[0] = .1; controls.release(); executor.drain()
    assert backend.events == ['start']


def test_mouse_and_keyboard_share_latched_session(interaction):
    controls, backend, executor, clock = interaction
    controls.toggle(); executor.drain()
    controls.press(); clock[0] = .1; controls.release(); executor.drain()
    assert backend.events == ['start', 'stop']


def test_processing_clicks_never_queue_an_extra_recording(interaction):
    controls, backend, executor, clock = interaction
    controls.toggle(); controls.toggle()
    controls.toggle(); controls.press(); clock[0] = 1; controls.release(); controls.toggle()
    executor.drain()
    assert backend.events == ['start', 'stop']
    assert controls.state == 'IDLE'


def test_cancel_queued_start_preserves_capture_without_transcription(interaction):
    controls, backend, executor, clock = interaction
    controls.press(); controls.cancel(); controls.release(); executor.drain()
    assert backend.events == ['start', 'cancel']
    assert controls.state == 'IDLE'


def test_start_failure_recovers_for_next_click(interaction):
    controls, backend, executor, _ = interaction
    original = backend.start_recording
    backend.start_recording = Mock(side_effect=RuntimeError('microphone unavailable'))
    controls.toggle(); executor.drain()
    assert controls.state == 'IDLE'
    backend.start_recording = original
    controls.toggle(); executor.drain()
    assert controls.state == 'RECORDING'


@pytest.mark.parametrize('hold_mode,expected', [(False, ['start']), (True, ['start','stop'])])
def test_explicit_shortcut_modes(interaction, hold_mode, expected):
    controls, backend, executor, clock = interaction
    controls.config.dual_mode_hotkey = False
    controls.config.hold_to_talk = hold_mode
    controls.press(); clock[0] = .1; controls.release(); executor.drain()
    assert backend.events == expected


def test_preferences_cannot_replace_a_pending_capture(interaction):
    controls, _, _, _ = interaction
    controls.toggle()
    update = Mock()
    with pytest.raises(RuntimeError, match='Finish'):
        controls.configure(update)
    update.assert_not_called()


def test_shutdown_drains_start_then_keeps_audio_and_rejects_new_events(interaction):
    controls, backend, _, _ = interaction
    controls.toggle(); controls.shutdown()
    controls.toggle(); controls.press(); controls.release(); controls.cancel()
    assert backend.events == ['start', 'cancel']


def daemon_adapter(controls):
    daemon = FixoflowDaemon.__new__(FixoflowDaemon)
    daemon.controls = controls
    daemon._listener = keyboard.Listener(on_press=lambda _: None)  # canonical only, not started
    daemon._lock = threading.RLock()
    daemon._pressed_keys = {}
    daemon._target_keys = set(keyboard.HotKey.parse('<ctrl>+<space>'))
    daemon._is_hotkey_active = False
    return daemon


def test_control_space_normalization_and_modifier_first_release(interaction):
    controls, backend, executor, clock = interaction
    daemon = daemon_adapter(controls)
    daemon._on_key_press(keyboard.Key.ctrl_r)
    daemon._on_key_press(keyboard.Key.space)
    daemon._on_key_press(keyboard.Key.space)  # OS autorepeat
    clock[0] = .8
    daemon._on_key_release(keyboard.Key.ctrl_r)  # combination breaks here
    daemon._on_key_release(keyboard.Key.space)
    executor.drain()
    assert backend.events == ['start', 'stop']


def test_both_control_keys_do_not_cancel_when_one_is_released(interaction):
    controls, backend, executor, clock = interaction
    daemon = daemon_adapter(controls)
    daemon._on_key_press(keyboard.Key.ctrl)
    daemon._on_key_press(keyboard.Key.ctrl_r)
    daemon._on_key_press(keyboard.Key.space)
    clock[0] = .6
    daemon._on_key_release(keyboard.Key.ctrl)
    assert controls.state == 'RECORDING'
    daemon._on_key_release(keyboard.Key.space)
    daemon._on_key_release(keyboard.Key.ctrl_r)
    executor.drain()
    assert backend.events == ['start', 'stop']


def test_shortcut_display_preserves_identity():
    config = FixoflowConfig(hotkey='<cmd>+<shift>+d')
    assert shortcut_label(config.hotkey) == '⌘ ⇧ D'
    assert config.hotkey == '<cmd>+<shift>+d'


def test_old_held_shortcut_cannot_stop_a_new_mouse_session(interaction):
    controls, backend, executor, clock = interaction
    controls.press(); executor.drain()
    controls.toggle(); executor.drain()  # finish first session with mouse, key still down
    controls.toggle(); executor.drain()  # new session belongs to a new click
    clock[0] = 3
    controls.release(); executor.drain()
    assert backend.events == ['start', 'stop', 'start']
    assert controls.state == 'RECORDING'


def test_exact_hold_threshold_finishes_recording(interaction):
    controls, backend, executor, clock = interaction
    controls.press(); clock[0] = controls.config.hold_threshold_sec; controls.release()
    executor.drain()
    assert backend.events == ['start', 'stop']


def test_letter_release_after_modifier_change_clears_physical_key(interaction):
    controls, backend, executor, clock = interaction
    daemon = daemon_adapter(controls)
    daemon._target_keys = set(keyboard.HotKey.parse('<cmd>+<shift>+d'))
    daemon._on_key_press(keyboard.Key.cmd)
    daemon._on_key_press(keyboard.Key.shift)
    daemon._on_key_press(keyboard.KeyCode.from_vk(2, char='D'))
    clock[0] = .8
    daemon._on_key_release(keyboard.Key.shift)
    daemon._on_key_release(keyboard.KeyCode.from_vk(2, char='d'))
    daemon._on_key_release(keyboard.Key.cmd)
    executor.drain()
    assert daemon._pressed_keys == {}
    assert backend.events == ['start', 'stop']
