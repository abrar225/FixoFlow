"""
Fixoflow Session Coordinator
Coordinates audio capture, intelligent slicing, Metal-accelerated transcription,
text polishing, and macOS cursor injection into a seamless pipeline.
"""
from __future__ import annotations

import logging
import threading
import time
import json
import os
from pathlib import Path
from typing import Optional

from fixoflow.audio.recorder import AudioRecorder
from fixoflow.brain.polisher import TextPolisher
from fixoflow.config import FixoflowConfig
from fixoflow.platform import (
    activate_application,
    copy_to_clipboard,
    get_frontmost_app_info,
    get_stable_app_identity,
    insert_text_at_cursor,
    notify,
    play_sound,
)
from fixoflow.stt.engine import create_stt_engine
from fixoflow.storage.db import FixoflowDB
from fixoflow.brain.learner import AdaptiveLearner

import sys
if sys.platform == "darwin":
    from fixoflow.ui.overlay import OverlayManager
else:
    OverlayManager = None

logger = logging.getLogger("fixoflow.core")


class FixoflowCoordinator:
    def __init__(self, config: Optional[FixoflowConfig] = None, enable_overlay: bool = True):
        self.config = config or FixoflowConfig.load()
        self.config.validate_product()
        self.recorder = AudioRecorder(self.config)
        self.stt = create_stt_engine(self.config)
        self.polisher = TextPolisher(self.config)
        self.db = FixoflowDB.get_instance()
        self.learner = AdaptiveLearner(self.db)
        
        self.overlay: Optional[OverlayManager] = None
        if enable_overlay and OverlayManager is not None:
            try:
                self.overlay = OverlayManager.get_instance()
            except Exception as e:
                logger.warning("Could not initialize overlay: %s", e)
        
        self._state = "IDLE"  # "IDLE", "RECORDING", "PROCESSING"
        self._lock = threading.Lock()
        self._target_app_name = ""
        self._target_bundle_id = ""
        self._target_app_id = ''
        self.last_error = ""
        self._cancel_requested = threading.Event()
        self.session_id = None
        self.delivery_status = 'not_attempted'
        from fixoflow.audio.checkup import MicrophoneCheckup
        from fixoflow.models.manager import ModelManager
        self.checkup = MicrophoneCheckup()
        self.model_manager = ModelManager()

    @property
    def maintenance_busy(self):
        return bool(self.checkup.active or self.checkup.needs_cleanup or self.model_manager.busy)

    def close_services(self):
        check_closed = self.checkup.close()
        model_closed = self.model_manager.close()
        return check_closed and model_closed

    def _journal(self, **changes):
        if self.session_id:
            try:
                self.db.update_session(self.session_id, **changes)
            except Exception:
                logger.exception('Session journal update failed; recording retained')

    def apply_config(self, candidate):
        """Stage changed resources before saving; keep warm inference otherwise."""
        candidate.validate_product()
        if self.state != 'IDLE':
            from fixoflow.settings import SettingsBusy
            raise SettingsBusy('Finish dictation before changing settings.')
        replacement = None
        if any(getattr(candidate, key) != getattr(self.config, key) for key in ('model_name', 'cpu_threads', 'language')):
            replacement = create_stt_engine(candidate)
            replacement.resolve_model_path()  # local-only validation, no inference/download
        candidate.save()
        self.config.__dict__.update(candidate.__dict__)
        if replacement is not None:
            self.stt = replacement
            self.stt.config = self.config
        self.polisher = TextPolisher(self.config)

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start_recording(self, cancellation=None) -> None:
        with self._lock:
            if self._state != "IDLE":
                return
            self._state = "RECORDING"
            app_name, bundle_id = get_frontmost_app_info()
            self._target_app_name = app_name
            self._target_bundle_id = bundle_id
            self._target_app_id = get_stable_app_identity(bundle_id)
            self.last_error = ""
            self._cancel_requested = cancellation if cancellation is not None else threading.Event()

        if self.config.sound_enabled:
            play_sound("Pop")
        if self.overlay:
            self.overlay.show_listening("Listening...")
            self.recorder.on_level_callback = self.overlay.update_audio_level

        try:
            self.session_id = None
            self.delivery_status = 'not_attempted'
            # Persist identity before opening hardware. A failed journal must not
            # start an untracked capture; later journal failures retain the audio.
            self.session_id = self.db.begin_session(
                app_name, bundle_id, self.config.model_name,
                self.config.language, self.config.mode, app_id=self._target_app_id)
            def created(path):
                self.db.update_session(self.session_id, audio_path=str(path))
                self.db.register_session_artifact(path, self.config.cache_dir)
            self.recorder.on_session_created = created
            if self.recorder.needs_cleanup:
                self.recorder.retry_cleanup()
            session_file = self.recorder.start()
            self._journal(status='recording', audio_path=str(session_file))
        except Exception as e:
            self._journal(status='capture_failed')
            with self._lock:
                self._state = "IDLE"
            self.last_error = str(e)
            if self.overlay:
                self.overlay.show_error("Microphone unavailable")
            logger.exception("Could not start recording")
            return
        try:self.db.register_session_artifact(session_file,self.config.cache_dir)
        except (OSError,ValueError):logger.exception('Could not register recording ownership')
        logger.info("Fixoflow recording started. Target app: %s (Session: %s)", self._target_app_name, session_file.name)

    def stop_and_process(self, auto_paste: bool = True) -> str:
        with self._lock:
            if self._state != "RECORDING":
                return ""
            self._state = "PROCESSING"
        return self._process_capture(auto_paste)

    def _process_capture(self, auto_paste, capture=None):
        target_app = self._target_app_name
        self._journal(status='processing')

        if self.config.sound_enabled:
            play_sound("Tink")
        if self.overlay:
            self.overlay.show_processing("Transcribing...")

        logger.info("Processing dictation for application: %s...", target_app)
        t0 = time.perf_counter()
        session_path = None

        try:
            # 1. Stop audio capture and obtain persisted wav buffer
            capture = capture or self.recorder.finalize_capture()
            session_path = capture.path
            if capture.frames == 0:
                self._journal(status='no_audio')
                self.last_error = "No audio recorded"
                logger.warning("Empty audio recorded; skipping transcription.")
                if self.overlay:
                    self.overlay.show_error("No audio recorded")
                return ""

            # 2. Transcribe with prompt conditioning and pause slicing
            prompt = self.learner.get_vocabulary_prompt()
            raw_text = self.stt.transcribe_file(session_path, initial_prompt=prompt, cancelled=self._cancel_requested.is_set)
            if not raw_text:
                self._journal(status='no_speech')
                self.last_error = "No speech detected"
                logger.info("No speech detected.")
                if self.overlay:
                    self.overlay.show_error("No speech detected")
                return ""

            self._persist_transcript(session_path, raw_text, "transcribed")

            # 3. Apply mode formatting, dictionary replacements and polishing
            fixes_vocab = fixes_polish = 0
            try:
                formatted_text, fixes_vocab = ((raw_text.strip(), 0) if self.config.output_style == "verbatim"
                    else self.learner.format_for_mode_counted(raw_text, mode=self.config.mode, app_name=target_app, spoken_commands=self.config.spoken_commands))
                effective_mode = self.learner.effective_mode(self.config.mode, target_app)
                final_text, fixes_polish = self.polisher.polish_counted(formatted_text, app_context=target_app, mode=effective_mode)
                if self.config.output_style != 'verbatim':
                    final_text, correction_id = self.db.apply_approved_correction(
                        final_text, self._target_app_id, self.config.language, self.config.mode)
                    fixes_vocab += int(correction_id is not None)
                if not final_text.strip():
                    final_text = raw_text
                    fixes_polish = fixes_vocab = 0
            except Exception:
                logger.exception("Formatting failed; retaining raw transcription")
                final_text = raw_text
                fixes_polish = fixes_vocab = 0

            latency_ms = (time.perf_counter() - t0) * 1000.0
            self._persist_transcript(session_path, final_text, "formatted", raw_text=raw_text)
            logger.info("Transcription complete (%d characters, %.1fms)", len(final_text), latency_ms)

            # 4. Record the session in SQLite
            try:
                duration_sec = capture.frames / capture.sample_rate
                self.db.record_session(
                    asr_text=raw_text,
                    final_text=final_text,
                    app_name=target_app,
                    duration_sec=duration_sec,
                    latency_ms=latency_ms,
                    mode=self.config.mode,
                    audio_path=str(session_path),
                    fixes_polish=fixes_polish,
                    fixes_vocab=fixes_vocab,
                    session_id=self.session_id,
                )
            except Exception as dbe:
                logger.error("Failed to record session in database: %s", dbe)
                copied=bool(auto_paste and copy_to_clipboard(final_text))
                self.delivery_status='clipboard_only' if copied else 'not_attempted'
                self._journal(status='history_failed',delivery_status=self.delivery_status)
                self.last_error=('Transcript could not be saved in History; recording retained in Recovery.'
                    + (' Text copied to clipboard.' if copied else ''))
                if self.overlay:self.overlay.show_error('History unavailable · open Recovery')
                return final_text

            # 5. Insert the text into the application that owns the cursor
            self.last_error = ""
            inserted = False
            notice = ""
            if self._cancel_requested.is_set():
                self.delivery_status = 'cancelled'
                self._journal(status='cancelled', delivery_status='cancelled')
                self.last_error="Transcription cancelled; recording retained for recovery."
                return ""
            if auto_paste and final_text:
                inserted, notice = self._deliver_text(final_text)
            self._journal(status='completed', delivery_status=self.delivery_status)

            if self.overlay:
                if auto_paste and not inserted:
                    self.overlay.show_error(notice)
                else:
                    self.overlay.show_success("Paste sent" if auto_paste else "Transcribed!")

            return final_text
        except Exception as e:
            self._journal(status='cancelled' if self._cancel_requested.is_set()
                          else 'transcription_failed')
            self.last_error = str(e)
            partial = getattr(e, "partial_text", "")
            recovery_path = session_path or getattr(e, "session_path", None)
            if partial and recovery_path:
                try:
                    self._persist_transcript(recovery_path, partial, "incomplete")
                except Exception:
                    logger.exception("Could not save partial transcript; original audio retained")
            logger.error("Error during session processing: %s", e)
            if self.overlay:
                self.overlay.show_error("Failed")
            return ""
        finally:
            with self._lock:
                self._state = "IDLE"

    def _deliver_text(self, text: str) -> tuple[bool, str]:
        """Paste into the application that started the session.

        Returns (inserted, short_notice). `last_error` receives the detailed
        reason for the hub when insertion could not be completed. The text is
        copied to the clipboard before any failure is reported so it is always
        recoverable without opening History.
        """
        target_bundle = self._target_bundle_id
        if self._cancel_requested.is_set():
            self.delivery_status = 'cancelled'
            copy_to_clipboard(text)
            self.last_error = 'Cancelled before paste; transcript saved in History.'
            return False, 'Cancelled · open History'
        if not target_bundle:
            copied = copy_to_clipboard(text)
            self.delivery_status = 'clipboard_only' if copied else 'failed'
            self.last_error = ("Target application was not identified; transcript copied to clipboard and saved in History" if copied else "Target application was not identified; transcript saved in History")
            notify("Fixoflow", self.last_error)
            return False, "Saved · open History"

        current_bundle = get_frontmost_app_info()[1]
        if current_bundle != target_bundle:
            # The user touched another window mid-dictation. Return focus to the
            # original application so the transcript still lands at its cursor.
            if activate_application(target_bundle):
                current_bundle = get_frontmost_app_info()[1]
        if self._cancel_requested.is_set():
            self.delivery_status = 'cancelled'
            copy_to_clipboard(text)
            self.last_error = 'Cancelled before paste; transcript saved in History.'
            return False, 'Cancelled · open History'
        if current_bundle != target_bundle:
            copied = copy_to_clipboard(text)
            self.delivery_status = 'clipboard_only' if copied else 'failed'
            self.last_error = ("Focus moved to another app; transcript is on the clipboard and in History"
                               if copied else "Focus moved to another app; transcript saved in History")
            notify("Fixoflow", self.last_error)
            return False, "Saved · open History"

        outcome = insert_text_at_cursor(text, expected_target=target_bundle, cancelled=self._cancel_requested.is_set)
        self.delivery_status = ('dispatch_sent' if outcome.inserted else 'cancelled'
            if outcome.reason == 'cancelled' else 'clipboard_only' if outcome.copied else 'failed')
        if outcome.inserted:
            return True, ""
        if outcome.reason == 'cancelled':
            self.last_error = 'Cancelled before paste; transcript saved in History.'
            return False, 'Cancelled · open History'
        if outcome.reason == "permission":
            self.last_error = "Copied to clipboard — enable Accessibility in Settings to paste automatically"
        elif outcome.reason == "event-failed":
            self.last_error = "Paste keystroke was rejected — transcript copied to clipboard"
        else:
            self.last_error = "Paste unavailable; transcript saved in History"
        notify("Fixoflow", self.last_error)
        return False, ("Copied · enable Accessibility" if outcome.reason == "permission"
                       else "Copied · paste manually" if outcome.reason == "event-failed"
                       else "Saved · open History")

    def recover_session(self, source_id, cancellation=None):
        """Retry into a new owned session/history entry, never into another app."""
        import datetime
        import wave
        from fixoflow.audio.recorder import Capture
        with self._lock:
            if self._state!='IDLE' or self.maintenance_busy:
                raise RuntimeError('Finish dictation and model/microphone operations before recovery.')
            self._state='PROCESSING'
        self.session_id=None
        try:
            source=self.db.recovery_source(source_id)
            self._target_app_name=source['app_name'];self._target_bundle_id=''
            self._target_app_id=source['app_id']
            self._cancel_requested=cancellation if cancellation is not None else threading.Event()
            if self._cancel_requested.is_set():return ''
            self.last_error='';self.delivery_status='not_attempted'
            self.session_id=self.db.begin_session(source['app_name'],'',self.config.model_name,
                self.config.language,self.config.mode,app_id=source['app_id'])
            root=Path(self.config.cache_dir);root.mkdir(parents=True,exist_ok=True)
            path=root/('session_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.wav')
            with self.db.open_owned_audio(source['audio_path']) as input_audio, path.open('xb') as output:
                self.db.register_session_artifact(path,root)
                self._journal(audio_path=str(path))
                before=os.fstat(input_audio.fileno());remaining=before.st_size
                while remaining:
                    if self._cancel_requested.is_set():raise InterruptedError('Recovery cancelled; original recording retained.')
                    block=input_audio.read(min(remaining,1024*1024))
                    if not block:raise ValueError('Recovery source was truncated while copying.')
                    output.write(block);remaining-=len(block)
                after=os.fstat(input_audio.fileno())
                if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                    raise ValueError('Recovery source changed while copying.')
                output.flush();os.fsync(output.fileno())
            with wave.open(str(path)) as audio:
                if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,16000):
                    raise ValueError('Recovery requires 16 kHz mono PCM audio.')
                capture=Capture(path,audio.getnframes(),audio.getframerate())
            result=self._process_capture(False,capture)
            saved=self.db.get_session(self.session_id)
            if result and saved and saved['status']=='completed':
                self.db.update_session(source_id,status='recovered')
            return result
        except Exception as error:
            self.last_error=str(error)
            self._journal(status='transcription_failed')
            return ''
        finally:
            with self._lock:self._state='IDLE'

    def _persist_transcript(self, session_path, text: str, status: str, raw_text: str = "") -> None:
        """Keep decoded words recoverable even when formatting/history/paste fails."""
        destination = Path(session_path).with_suffix(".transcript.json")
        temporary = destination.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as output:
            json.dump({"status": status, "text": text, "raw_text": raw_text or text}, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        try:self.db.register_session_artifact(destination,self.config.cache_dir)
        except (OSError,ValueError):logger.exception("Could not register transcript ownership")

    def request_cancel(self):
        self._cancel_requested.set()

    def cancel_recording(self) -> None:
        """Finish disk capture without transcribing or inserting; retain audio."""
        with self._lock:
            if self._state != "RECORDING":
                return
            self._state = "PROCESSING"
        try:
            self.recorder.stop(load_audio=False)
            self._journal(status='cancelled', delivery_status='cancelled')
            if self.overlay:
                self.overlay.show_success("Recording saved")
        except Exception as error:
            self._journal(status='capture_failed')
            self.last_error = str(error)
            if self.overlay:
                self.overlay.show_error("Capture needs attention")
        finally:
            with self._lock:
                self._state = "IDLE"

    def toggle(self, auto_paste: bool = True) -> Optional[str]:
        """Toggles between starting recording and stopping/transcribing."""
        if self.state == "IDLE":
            self.start_recording()
            return None
        elif self.state == "RECORDING":
            return self.stop_and_process(auto_paste=auto_paste)
        return None
