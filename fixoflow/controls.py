"""One ordered session owner for hold-to-talk, hands-free, and the floating bar."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class DictationControls:
    def __init__(self, coordinator, config, executor=None, on_change=None):
        self.coordinator = coordinator
        self.config = config
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix='Fixoflow-session')
        self.on_change = on_change or (lambda: None)
        self._lock = threading.RLock()
        self._intent = 'IDLE'
        self._hold_down = False
        self._session_id = 0
        self._hold_session = None
        self._closed = False
        self._cancel_requested = threading.Event()

    @property
    def state(self):
        with self._lock:
            return self._intent

    def _start(self, cancellation):
        try:
            self.coordinator.start_recording(cancellation=cancellation)
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
            if cancel or self._cancel_requested.is_set():
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
        self._cancel_requested = threading.Event()
        self._intent = 'RECORDING'
        self.executor.submit(self._start, self._cancel_requested)

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

    def hold_press(self):
        with self._lock:
            if self._closed or self._hold_down:
                return
            self._hold_down = True
            self._hold_session = None
            if self._intent == 'IDLE':
                self._begin_locked()
                self._hold_session = self._session_id
        self.on_change()

    def hold_release(self):
        with self._lock:
            session = self._hold_session
            self._hold_down = False
            self._hold_session = None
            if not self._closed and session is not None and session == self._session_id:
                self._end_locked()
        self.on_change()

    def cancel(self):
        with self._lock:
            if self._closed:
                return
            self._hold_session = None
            self._cancel_requested.set()
            if self._intent == 'PROCESSING' and hasattr(self.coordinator, 'request_cancel'):
                self.coordinator.request_cancel()
            self._end_locked(cancel=True)
        self.on_change()

    def configure(self, update):
        """Exclude new gestures while applying settings to an idle session."""
        with self._lock:
            if self._intent != 'IDLE' or self._closed:
                from fixoflow.settings import SettingsBusy
                raise SettingsBusy('Finish the current dictation before changing settings.')
            update()
            self._hold_down = False
            self._hold_session = None

    def shutdown(self):
        with self._lock:
            self._closed = True
            self._hold_down = False
            self._cancel_requested.set()
        # Drain an in-flight start before closing capture. Queued finish keeps
        # ownership of its audio; shutdown must not abandon it midway.
        if hasattr(self.coordinator, 'request_cancel'):
            self.coordinator.request_cancel()
        self.executor.shutdown(wait=True)
        if self.coordinator.recorder.is_recording:
            self.coordinator.cancel_recording()


def shortcut_label(shortcut):
    from fixoflow.shortcuts import Shortcut
    return Shortcut.read(shortcut).display()
