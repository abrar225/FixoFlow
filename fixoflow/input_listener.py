"""Windows/X11 input edges routed to the shared shortcut/session owner."""
from __future__ import annotations
import json
import os
import sys
import threading
from fixoflow.shortcuts import ShortcutRouter, key_label


class DesktopInput:
    def __init__(self, config, controls):
        self.config = config
        self.controls = controls
        self.router = ShortcutRouter(config.hold_shortcut, config.hands_free_shortcut, controls)
        self._lock = threading.RLock()
        self._listeners = []
        self._retired = []
        self._generation = 0

    @property
    def active(self):
        return len(self._listeners) == 2 and all(item.is_alive() for item in self._listeners)

    def _feed(self, physical, token, down, generation):
        with self._lock:
            if generation != self._generation:
                return False
            # A primary click in our settings must never start dictation.
            if token in {'mouse:0', 'mouse:1'} and down and not self.router.capture:
                from fixoflow.platform import get_frontmost_app_info
                try:
                    if json.loads(get_frontmost_app_info()[1])[1] == os.getpid():
                        return False
                except (ValueError, IndexError, TypeError):
                    pass
            return self.router.input(physical, token, down)

    def begin_capture(self, callback):
        with self._lock:
            self.router.begin_capture(callback)

    def cancel_capture(self):
        with self._lock:
            self.router.cancel_capture()

    def expire_capture(self):
        with self._lock:
            self.router.expire_capture()

    def capture_primary(self, number):
        if type(number) is not int or number not in (0, 1):
            raise ValueError('Unsupported mouse button')
        with self._lock:
            modifiers = [value for value in self.router.pressed.values() if value[0].split('_')[0] in {
                'ctrl', 'alt', 'shift', 'cmd', 'fn'}]
            self.router.commit_capture([token for token, _ in modifiers]+[f'mouse:{number}'], ' + '.join(
                [label or key_label(token) for token, label in modifiers]+[key_label(f'mouse:{number}')]))

    def start(self):
        if self.active:
            return
        self.stop()
        if self._retired:
            raise RuntimeError('Previous input listener is still stopping. Retry shortly.')
        if sys.platform.startswith('linux') and os.environ.get('XDG_SESSION_TYPE') == 'wayland':
            raise RuntimeError('Global shortcuts need an X11 session. Wayland portal support is not included yet.')
        from pynput import keyboard, mouse
        generation = self._generation
        if sys.platform == 'win32':
            import ctypes
            native = ctypes.WinDLL('user32')
            native.GetKeyboardLayout.restype = ctypes.c_void_p
            native.MapVirtualKeyExW.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
            specials = {0x08: 'backspace', 0x09: 'tab', 0x0D: 'enter', 0x14: 'caps_lock', 0x1B: 'esc', 0x20: 'space', 0x21: 'page_up', 0x22: 'page_down', 0x23: 'end', 0x24: 'home', 0x25: 'left', 0x26: 'up',
                        0x27: 'right', 0x28: 'down', 0x2D: 'insert', 0x2E: 'delete', 0x5B: 'cmd_l', 0x5C: 'cmd_r', 0xA0: 'shift_l', 0xA1: 'shift_r', 0xA2: 'ctrl_l', 0xA3: 'ctrl_r', 0xA4: 'alt_l', 0xA5: 'alt_r'}
            specials.update({0x70+i: f'f{i+1}' for i in range(24)})

            def keyboard_filter(message, data):
                if message not in (0x100, 0x101, 0x104, 0x105):
                    return True
                if data.flags & 0x10:
                    return True  # LLKHF_INJECTED: never trigger on simulated paste.
                vk = int(data.vkCode)
                token = specials.get(vk)
                if not token:
                    char = native.MapVirtualKeyExW(vk, 2, native.GetKeyboardLayout(0)) & 0x7FFFFFFF
                    token = chr(char).lower() if 0 < char <= 0x10ffff and chr(char).isprintable() else f'vk:{vk}'
                if self._feed(('key', int(data.scanCode), bool(data.flags & 1)), token, message in (0x100, 0x104), generation):
                    key_listener.suppress_event()
                return True

            def mouse_filter(message, data):
                edges = {0x201: (0, True), 0x202: (0, False), 0x204: (1, True),
                         0x205: (1, False), 0x207: (2, True), 0x208: (2, False)}
                edge = edges.get(message)
                if message in (0x20B, 0x20C):
                    edge = (2+(int(data.mouseData) >> 16), message == 0x20B)
                if edge and self._feed(('mouse', edge[0]), f'mouse:{edge[0]}', edge[1], generation):
                    mouse_listener.suppress_event()
                return True
            key_listener = keyboard.Listener(win32_event_filter=keyboard_filter)
            mouse_listener = mouse.Listener(win32_event_filter=mouse_filter)
        else:
            def key_event(key, down, injected=False):
                if injected:
                    return
                name = getattr(key, 'name', None)
                if name:
                    token = name+'_l' if name in {'ctrl', 'alt', 'shift', 'cmd'} else name
                else:
                    char = getattr(key, 'char', None)
                    vk = getattr(key, 'vk', None)
                    token = char.lower() if char and char.isprintable() and len(
                        char) == 1 else f'vk:{vk}' if vk is not None else None
                if token:
                    self._feed(('key', getattr(getattr(key, 'value', key), 'vk', str(key))), token, down, generation)

            def click(x, y, button, down):
                number = {'left': 0, 'right': 1, 'middle': 2, 'button8': 3, 'button9': 4}.get(button.name)
                if number is not None:
                    self._feed(('mouse', number), f'mouse:{number}', down, generation)
            key_listener = keyboard.Listener(on_press=lambda key, injected=False: key_event(
                key, True, injected), on_release=lambda key, injected=False: key_event(key, False, injected))
            mouse_listener = mouse.Listener(on_click=click)
        self._listeners = [key_listener, mouse_listener]
        try:
            for item in self._listeners:
                item.start()
                item.wait()
        except Exception:
            self.stop()
            raise

    def stop(self):
        with self._lock:
            self._generation += 1
            items = self._listeners+self._retired
            self._listeners = []
            self._retired = items
        for item in items:
            item.stop()
            if item.ident is not None and item is not threading.current_thread():
                item.join(timeout=2)
        with self._lock:
            self._retired = [item for item in items if item.is_alive()]
            self.router.reset()

    def reconfigure(self):
        with self._lock:
            decisions = self.router._decisions
            self.router = ShortcutRouter(self.config.hold_shortcut, self.config.hands_free_shortcut, self.controls)
            self.router._decisions = decisions
