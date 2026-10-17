"""Global shortcut adapter. DictationControls owns all gesture/session intent."""
from __future__ import annotations

import logging
import threading

import AppKit
from pynput import keyboard

from fixoflow.config import FixoflowConfig
from fixoflow.controls import DictationControls
from fixoflow.core import FixoflowCoordinator

logger = logging.getLogger(__name__)


class FixoflowDaemon:
    def __init__(self, config=None):
        self.config = config or FixoflowConfig.load()
        self._app = AppKit.NSApplication.sharedApplication()
        self._app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        self.coordinator = FixoflowCoordinator(self.config, enable_overlay=True)
        self.controls = DictationControls(self.coordinator, self.config)
        self._listener = None
        self._pressed_keys = {}
        self._is_hotkey_active = False
        self._lock = threading.RLock()
        self._target_keys = set(keyboard.HotKey.parse(self.config.hotkey))

    @staticmethod
    def _physical_key(key):
        value = getattr(key, 'value', key)
        return getattr(value, 'vk', None) if getattr(value, 'vk', None) is not None else key

    def _on_key_press(self, key):
        if self._listener is None:
            return
        canonical = self._listener.canonical(key)
        if key == keyboard.Key.esc:
            self.controls.cancel()
            return
        with self._lock:
            self._pressed_keys[self._physical_key(key)] = canonical
            activate = not self._is_hotkey_active and self._target_keys.issubset(set(self._pressed_keys.values()))
            if activate:
                self._is_hotkey_active = True
        if activate:
            self.controls.press()

    def _on_key_release(self, key):
        with self._lock:
            self._pressed_keys.pop(self._physical_key(key), None)
            release = self._is_hotkey_active and not self._target_keys.issubset(set(self._pressed_keys.values()))
            if release:
                self._is_hotkey_active = False
        if release:
            self.controls.release()

    def configure_hotkey(self):
        keys = set(keyboard.HotKey.parse(self.config.hotkey))
        with self._lock:
            self._target_keys = keys
            self._pressed_keys.clear()
            self._is_hotkey_active = False

    def start_listener(self):
        if self._listener is not None and self._listener.is_alive():
            return
        self._listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self._listener.start()

    def stop_listener(self):
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.stop()
        with self._lock:
            self._pressed_keys.clear()
            self._is_hotkey_active = False

    def stop(self):
        if getattr(self, '_stopped', False):
            return
        self._stopped = True
        self.stop_listener()
        self.controls.shutdown()
        if self.coordinator.overlay:
            self.coordinator.overlay.hide()
        self._app.stop_(None)
