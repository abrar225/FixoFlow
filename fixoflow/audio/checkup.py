"""Explicit short microphone checkup. Retains signal metrics, never PCM or text.

The caller must exclude dictation while running and request microphone permission
through its normal user flow. The service never starts on construction or reads
an existing recording. Signal/no-signal is a level check, not speech recognition.
"""
from __future__ import annotations

import math
import threading
import time

import numpy as np

from fixoflow.audio.devices import resolve_input_device


class MicrophoneCheckup:
    def __init__(self, backend=None, clock=time.monotonic):
        self._backend = backend
        self._clock = clock
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker = None
        self._stream = None
        self._state = {'state':'idle', 'level':0.0, 'peak':0.0, 'clipping':False,
                       'no_signal':None, 'elapsed_seconds':0.0,
                       'message':'Start a microphone check to inspect the signal. No audio is saved.'}

    @property
    def active(self):
        return self._worker is not None and self._worker.is_alive()

    @property
    def needs_cleanup(self):
        return self._stream is not None and not self.active

    def snapshot(self):
        with self._lock:
            return {**self._state, 'cleanup_required':self.needs_cleanup}

    def _publish(self, **values):
        with self._lock:
            self._state.update(values)

    def start(self, selection='', duration=5):
        if isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or not 1 <= duration <= 10:
            raise ValueError('Microphone check must last between 1 and 10 seconds.')
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                raise ValueError('A microphone check is already running.')
            if self._stream is not None:
                raise ValueError('The previous microphone check needs cleanup. Retry closing it first.')
            self._stop.clear()
            self._state.update(state='starting',level=0.0,peak=0.0,clipping=False,
                no_signal=None,elapsed_seconds=0.0,message='Opening the selected microphone…')
            self._worker = threading.Thread(target=self._run,args=(selection,float(duration)),daemon=True,
                                            name='FixoFlow-mic-check')
            self._worker.start()

    def cancel(self):
        self._stop.set()

    def close(self, timeout=2):
        self.cancel()
        worker = self._worker
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout)
        if self.active:
            return False
        self._cleanup()
        return self._stream is None

    def _cleanup(self):
        errors=[]
        stream=self._stream
        if stream is not None:
            try:stream.stop()
            except Exception as error:errors.append('Microphone stop failed: '+str(error))
            try:stream.close()
            except Exception as error:errors.append('Microphone cleanup failed: '+str(error))
            else:self._stream=None
        return errors

    def _run(self, selection, duration):
        stream = None
        peak = rms_max = 0.0
        frames_seen = 0
        failure = []
        began = self._clock()

        def callback(indata, frames, time_info, status):
            nonlocal peak, rms_max, frames_seen
            if status:
                if not failure:failure.append('The microphone stream reported an error. Reconnect it and try again.')
                self._stop.set()
                return
            if not np.isfinite(indata).all():
                if not failure:failure.append('The microphone returned invalid sample data.')
                self._stop.set()
                return
            if not indata.size:
                return
            # Only scalar metrics escape the callback; PCM is not copied/queued.
            current_peak = float(np.max(np.abs(indata)))
            rms = float(np.sqrt(np.mean(np.square(indata, dtype=np.float64))))
            peak = max(peak,current_peak)
            rms_max = max(rms_max,rms)
            frames_seen += frames
            level = max(0.0,min(1.0,(20*math.log10(max(rms,1e-6))+60)/60))
            self._publish(level=level,peak=peak,clipping=peak >= .99,
                          elapsed_seconds=min(duration,max(0.0,self._clock()-began)))

        try:
            backend = self._backend
            if backend is None:
                import sounddevice as backend
            device = resolve_input_device(selection,backend)
            info = backend.query_devices(device,'input')
            rate = float(info['default_samplerate'])
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError('The microphone has no valid default sample rate.')
            stream = backend.InputStream(device=device,samplerate=rate,channels=1,dtype='float32',
                                         blocksize=0,callback=callback)
            self._stream = stream
            if self._stop.is_set():
                return
            stream.start()
            began = self._clock()
            self._publish(state='running',message='Speak normally for a few seconds. No audio is saved.')
            while not self._stop.wait(.05):
                elapsed = max(0.0,self._clock()-began)
                self._publish(elapsed_seconds=min(duration,elapsed))
                if elapsed >= duration:
                    break
                if getattr(stream,'active',True) is False:
                    failure.append('The microphone stopped responding. Reconnect it and try again.')
                    break
        except Exception as error:
            # Hardware/runtime errors are useful; sample contents never appear.
            failure.append(str(error))
        finally:
            failure.extend(self._cleanup())
            if failure:
                self._publish(state='error',level=0.0,no_signal=None,message=failure[0])
            elif self._stop.is_set():
                self._publish(state='cancelled',level=0.0,no_signal=None,message='Microphone check cancelled. No audio was saved.')
            else:
                no_signal = frames_seen == 0 or rms_max < .003
                message = ('No clear signal detected. Check mute, device and input level.' if no_signal
                    else 'Signal is clipping. Reduce microphone input gain.' if peak >= .99
                    else 'Microphone signal detected. This does not measure transcription accuracy.')
                self._publish(state='complete',level=0.0,no_signal=no_signal,message=message)
