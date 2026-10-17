"""One ordered interaction owner for the floating button and keyboard shortcut."""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class DictationControls:
    def __init__(self, coordinator, config, executor=None, on_change=None, clock=time.monotonic):
        self.coordinator = coordinator
        self.config = config
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix='Fixoflow-session')
        self.on_change = on_change or (lambda: None)
        self.clock = clock
        self._lock = threading.RLock()
        self._intent = 'IDLE'
        self._down_at = None
        self._gesture = None
        self._session_id = 0
        self._gesture_session = None
        self._closed = False

    @property
    def state(self):
        with self._lock:
            return self._intent

    def _start(self):
        try:
            self.coordinator.start_recording()
        except Exception:
            logger.exception('Could not start dictation')
        finally:
            with self._lock:
                # A release may already have queued stop while the microphone
                # was opening. Do not overwrite that newer processing intent.
                if self._intent == 'RECORDING' and self.coordinator.state != 'RECORDING':
                    self._intent = 'IDLE'
            self.on_change()

    def _finish(self, cancel=False):
        try:
            if cancel:
                self.coordinator.cancel_recording()
            else:
                self.coordinator.stop_and_process(auto_paste=True)
        except Exception:
            logger.exception('Could not finish dictation')
        finally:
            with self._lock:
                self._intent = 'IDLE'
            self.on_change()

    def _begin_locked(self):
        self._session_id += 1
        self._intent = 'RECORDING'
        self.executor.submit(self._start)

    def _end_locked(self, cancel=False):
        if self._intent == 'RECORDING':
            self._intent = 'PROCESSING'
            self.executor.submit(self._finish, cancel)

    def toggle(self):
        with self._lock:
            if self._closed:
                return
            if self._intent == 'IDLE':
                self._begin_locked()
            elif self._intent == 'RECORDING':
                self._end_locked()
            # Ignore clicks during processing; never queue a surprise recording.
        self.on_change()

    def press(self):
        with self._lock:
            if self._closed or self._down_at is not None:
                return
            self._down_at = self.clock()
            if self._intent == 'IDLE':
                self._gesture = 'start'
                self._begin_locked()
            elif self._intent == 'RECORDING':
                self._gesture = 'stop'
            else:
                self._gesture = 'ignore'
            self._gesture_session = self._session_id
        self.on_change()

    def release(self):
        with self._lock:
            if self._down_at is None:
                return
            held = self.clock() - self._down_at
            gesture = self._gesture
            gesture_session = self._gesture_session
            self._down_at = None
            self._gesture = None
            if self._closed or gesture == 'ignore' or gesture_session != self._session_id:
                return
            held_to_talk = (self.config.dual_mode_hotkey and held >= self.config.hold_threshold_sec) or (
                not self.config.dual_mode_hotkey and self.config.hold_to_talk
            )
            if gesture == 'stop' or (gesture == 'start' and held_to_talk):
                self._end_locked()
        self.on_change()

    def cancel(self):
        with self._lock:
            if self._closed:
                return
            self._gesture = 'ignore'
            self._end_locked(cancel=True)
        self.on_change()

    def configure(self, update):
        """Exclude new gestures while applying settings to an idle session."""
        with self._lock:
            if self._intent != 'IDLE' or self._closed:
                raise RuntimeError('Finish the current dictation before changing settings.')
            update()
            self._down_at = None
            self._gesture = None

    def shutdown(self):
        with self._lock:
            self._closed = True
            self._down_at = None
        # Drain an in-flight start before closing capture. Queued finish keeps
        # ownership of its audio; shutdown must not abandon it midway.
        self.executor.shutdown(wait=True)
        if self.coordinator.recorder.is_recording:
            self.coordinator.cancel_recording()


def shortcut_label(shortcut):
    symbols = {'ctrl': '⌃', 'cmd': '⌘', 'shift': '⇧', 'alt': '⌥', 'space': 'Space'}
    return ' '.join(symbols.get(part.strip('<>').lower(), part.strip('<>').upper())
                    for part in shortcut.split('+'))
