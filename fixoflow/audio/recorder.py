"""Bounded microphone capture with continuously persisted, recoverable PCM WAVs."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
import logging
import os
import queue
import threading
import wave
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import scipy.io.wavfile as wav
import sounddevice as sd

from fixoflow.audio.filter import clean_audio_pipeline
from fixoflow.config import FixoflowConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Capture:
    path: Path
    frames: int
    sample_rate: int


class RecordingError(RuntimeError):
    """Capture was incomplete; session_path identifies the retained recovery file."""

    def __init__(self, message: str, session_path: Optional[Path] = None):
        super().__init__(message)
        self.session_path = session_path


class AudioRecorder:
    # Two seconds of pending PCM, independent of recording duration.
    MAX_PENDING_BLOCKS = 20

    def __init__(self, config: Optional[FixoflowConfig] = None):
        self.config = config or FixoflowConfig.load()
        self.sample_rate = self.config.sample_rate
        self.channels = self.config.channels
        self._is_recording = False
        self._lock = threading.Lock()
        self._stream = None
        self._current_session_path: Optional[Path] = None
        self._writer: Optional[threading.Thread] = None
        self._output = None
        self._session = None
        self._stop_requested = False
        self._pending: queue.Queue = queue.Queue(self.MAX_PENDING_BLOCKS)
        self._error: Optional[BaseException] = None
        self.on_level_callback: Optional[Callable[[float], None]] = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    @property
    def needs_cleanup(self):
        return self._stream is not None or self._writer is not None or self._output is not None

    def retry_cleanup(self):
        try:self.stop(load_audio=False)
        except RecordingError:
            if self.needs_cleanup:raise
        return not self.needs_cleanup

    def _fail(self, error: BaseException) -> None:
        with self._lock:
            if self._error is None:
                self._error = error

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        with self._lock:
            if not self._is_recording or self._error is not None:
                return
        if status:
            self._fail(RecordingError(f"Audio input reported incomplete capture: {status}"))
        try:
            pcm = (np.clip(indata, -1.0, 1.0) * 32767).astype('<i2').tobytes()
            self._pending.put_nowait(pcm)
        except queue.Full:
            self._fail(RecordingError("Audio persistence could not keep up; pending buffer is full"))
        except Exception as error:
            self._fail(error)
        if self.on_level_callback:
            try:
                rms = float(np.sqrt(np.mean(indata ** 2)))
                self.on_level_callback(min(rms * 10.0, 1.0))
            except Exception:
                logger.exception("Audio level display failed")

    def _persist(self, output, session) -> None:
        try:
            while True:
                block = self._pending.get()
                if block is None:
                    break
                try:
                    # writeframes updates the WAV length after every block, so a
                    # completed flush is readable even before normal shutdown.
                    session.writeframes(block)
                    output.flush()
                    os.fsync(output.fileno())
                except Exception as error:
                    self._fail(error)
                    # Drain already queued blocks without growing memory or
                    # deadlocking stop; incomplete capture is never success.
        finally:
            self._close_output()

    def _close_output(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception as error:
                self._fail(error)
                return
            self._session = None
        if self._output is not None:
            try:
                self._output.flush()
                os.fsync(self._output.fileno())
            except Exception as error:
                self._fail(error)
            try:
                self._output.close()
            except Exception as error:
                self._fail(error)
                return
            self._output = None

    def start(self) -> Path:
        """Open the recovery file before accepting any microphone samples."""
        with self._lock:
            if self._is_recording:
                assert self._current_session_path is not None
                return self._current_session_path
            if self._stream is not None or self._writer is not None or self._output is not None:
                raise RecordingError("Previous capture still needs cleanup", self._current_session_path)
        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        path = cache_dir / f'session_{timestamp}.wav'
        self._current_session_path = path
        self._error = None
        self._pending = queue.Queue(self.MAX_PENDING_BLOCKS)
        self._stop_requested = False
        output = path.open('xb')
        try:
            session = wave.open(output, 'wb')
            session.setnchannels(self.channels)
            session.setsampwidth(2)
            session.setframerate(self.sample_rate)
            session.writeframes(b'')
            output.flush()
            os.fsync(output.fileno())
        except Exception:
            output.close()
            raise
        self._output = output
        self._session = session
        self._writer = threading.Thread(target=self._persist, args=(output, session), daemon=True)
        try:
            self._writer.start()
        except Exception:
            self._writer = None
            self._close_output()
            raise
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate, channels=self.channels, dtype='float32',
                callback=self._audio_callback, blocksize=int(self.sample_rate * 0.1),
            )
            with self._lock:
                self._is_recording = True
            self._stream.start()
        except Exception as error:
            self._fail(error)
            try:
                self.stop()
            except RecordingError:
                pass
            raise RecordingError(f"Could not start microphone: {error}", path) from error
        return path

    def finalize_capture(self):
        _, path = self.stop(load_audio=False)
        with wave.open(str(path)) as capture:
            return Capture(path, capture.getnframes(), capture.getframerate())

    def stop(self, load_audio=True) -> tuple[np.ndarray, Path]:
        """Drain persisted capture; return full audio only after successful cleanup.

        Capture uses bounded buffering, but this compatibility API still loads
        the whole recording for filtering and inference.
        """
        with self._lock:
            self._is_recording = False
        path = self._current_session_path or Path()
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception as error:
                self._fail(error)
            try:
                self._stream.close()
            except Exception as error:
                self._fail(error)
                # Keep ownership so a later stop can retry failed cleanup.
            else:
                self._stream = None
        if self._writer is not None:
            if not self._stop_requested:
                try:
                    self._pending.put(None, timeout=2.0)
                except queue.Full as error:
                    self._fail(RecordingError("Audio writer is stalled; cleanup needs retry"))
                    raise RecordingError(str(self._error), path) from error
                self._stop_requested = True
            self._writer.join(timeout=5.0)
            if self._writer.is_alive():
                self._fail(RecordingError("Audio writer has not finished; cleanup needs retry"))
                raise RecordingError(str(self._error), path)
            self._writer = None
        self._close_output()
        if self._error is not None:
            raise RecordingError(f"Recording incomplete: {self._error}", path) from self._error
        if self._current_session_path is None:
            return np.array([], dtype=np.float32), path
        if not load_audio:return np.array([], dtype=np.float32), path
        _, audio = wav.read(str(path))
        audio = audio.astype(np.float32) / 32767.0
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return clean_audio_pipeline(audio, self.sample_rate), path
