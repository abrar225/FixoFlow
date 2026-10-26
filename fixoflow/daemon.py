"""macOS input adapter. The app alone owns Dock/activation policy.

Pynput owns event-tap lifetimes; raw Darwin intercepts add Fn and numbered
mouse buttons without copying its listener implementation.
"""
from __future__ import annotations
import logging
import threading
import Quartz
from pynput import keyboard, mouse
from fixoflow.config import FixoflowConfig
from fixoflow.controls import DictationControls
from fixoflow.core import FixoflowCoordinator
from fixoflow.shortcuts import ShortcutRouter, key_label

logger = logging.getLogger(__name__)


class FixoflowDaemon:
    def __init__(self, config=None):
        self.config = config or FixoflowConfig.load()
        self.coordinator = FixoflowCoordinator(self.config, enable_overlay=True)
        self.controls = DictationControls(self.coordinator, self.config)
        self._listener = None
        self._mouse_listener = None
        self._lock = threading.RLock()
        self._keyboard_consumed = False
        self._hub_focused = False
        self._generation = 0
        self._retired_listeners = []
        self.router = ShortcutRouter(self.config.hold_shortcut, self.config.hands_free_shortcut, self.controls)

    @staticmethod
    def _physical_key(key):
        value = getattr(key, 'value', key)
        vk = getattr(value, 'vk', None)
        return ('keyboard', vk if vk is not None else str(key))

    @staticmethod
    def _key_token(key):
        if isinstance(key, keyboard.Key):
            return key.name + '_l' if key.name in {'ctrl', 'alt', 'cmd', 'shift'} else key.name
        if key is None:
            return None
        char = getattr(key, 'char', None)
        if char and len(char) == 1 and char.isprintable():
            return char.lower()
        vk = getattr(key, 'vk', None)
        return f'vk:{vk}' if vk is not None else None

    def _feed_key(self, key, down, generation, injected=False):
        token = self._key_token(key)
        with self._lock:
            if generation != self._generation:
                return
            self._keyboard_consumed = False
            # Synthetic paste events must reach the editor without activating
            # or being swallowed by a shortcut that happens to use Cmd+V.
            if injected:
                return
            if token is not None:
                self._keyboard_consumed = self.router.input(self._physical_key(key), token, down)

    def _keyboard_event(self, event_type, event, generation):
        if generation != self._generation:
            return event
        if Quartz.CGEventGetIntegerValueField(event, Quartz.kCGEventSourceUnixProcessID):
            return event
        # The Fn/Globe hardware key has no pynput Key member on macOS.
        if event_type == Quartz.kCGEventFlagsChanged and Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode) == 63:
            down = bool(Quartz.CGEventGetFlags(event) & Quartz.kCGEventFlagMaskSecondaryFn)
            with self._lock:
                self._keyboard_consumed = self.router.input(('keyboard', 63), 'fn', down)
        return None if self._keyboard_consumed else event

    def _mouse_event(self, event_type, event, generation):
        if generation != self._generation:
            return event
        presses = {Quartz.kCGEventLeftMouseDown, Quartz.kCGEventRightMouseDown, Quartz.kCGEventOtherMouseDown}
        releases = {Quartz.kCGEventLeftMouseUp, Quartz.kCGEventRightMouseUp, Quartz.kCGEventOtherMouseUp}
        if event_type not in presses | releases:
            return event
        number = int(Quartz.CGEventGetIntegerValueField(event, Quartz.kCGMouseEventButtonNumber))
        if number in (0, 1) and self._hub_focused and event_type in presses and not self.router.capture:
            return event
        with self._lock:
            consumed = self.router.input(('mouse', number), f'mouse:{number}', event_type in presses)
        return None if consumed else event

    def configure_shortcuts(self):
        with self._lock:
            self.router.reset()
            decisions = self.router._decisions
            self.router = ShortcutRouter(self.config.hold_shortcut, self.config.hands_free_shortcut, self.controls)
            self.router._decisions = decisions

    def begin_capture(self, callback):
        with self._lock:
            self.router.begin_capture(callback)

    def expire_capture(self):
        with self._lock:
            self.router.expire_capture()

    def cancel_capture(self):
        with self._lock:
            self.router.cancel_capture()

    def capture_primary_mouse(self, number):
        if type(number) is not int or number not in (0, 1):
            raise ValueError('Choose a supported mouse button.')
        with self._lock:
            modifiers = [value for value in self.router.pressed.values() if value[0] in {
                'ctrl', 'ctrl_l', 'ctrl_r', 'alt', 'alt_l', 'alt_r', 'shift', 'shift_l', 'shift_r', 'cmd', 'cmd_l', 'cmd_r', 'fn'}]
            keys = [token for token, _ in modifiers] + [f'mouse:{number}']
            label = ' + '.join([label or key_label(token) for token, label in modifiers]+[key_label(f'mouse:{number}')])
            self.router.commit_capture(keys, label)

    def start_listener(self):
        if self._listener is not None and self._listener.is_alive() and self._mouse_listener is not None and self._mouse_listener.is_alive():
            return
        self.stop_listener()
        if self._retired_listeners:
            raise RuntimeError('The previous input listener is still stopping. Retry in a moment.')
        generation = self._generation
        self._listener = keyboard.Listener(on_press=lambda key, injected=False: self._feed_key(key, True, generation, injected), on_release=lambda key, injected=False: self._feed_key(
            key, False, generation, injected), darwin_intercept=lambda kind, event: self._keyboard_event(kind, event, generation))
        self._mouse_listener = mouse.Listener(darwin_intercept=lambda kind,
                                              event: self._mouse_event(kind, event, generation))
        try:
            self._listener.start()
            self._mouse_listener.start()
        except Exception:
            self.stop_listener()
            raise

    def stop_listener(self):
        with self._lock:
            self._generation += 1
            listeners = [item for item in (self._listener, self._mouse_listener, *
                                           self._retired_listeners) if item is not None]
            self._listener = self._mouse_listener = None
            self._retired_listeners = listeners
        for listener in listeners:
            listener.stop()
            if listener is not threading.current_thread() and listener.ident is not None:
                listener.join(timeout=2)
        with self._lock:
            self._retired_listeners = [listener for listener in listeners if listener.is_alive()]
            self.router.reset()
        if self._retired_listeners:
            logger.warning('Input listener cleanup pending; ownership retained for retry.')

    def stop(self):
        if getattr(self, '_stopped', False):
            return
        self._stopped = True
        self.stop_listener()
        self.controls.shutdown()
        if self.coordinator.overlay:
            self.coordinator.overlay.hide()
