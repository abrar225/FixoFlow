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
        self.last_error = ""

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def start_recording(self) -> None:
        with self._lock:
            if self._state != "IDLE":
                return
            self._state = "RECORDING"
            app_name, bundle_id = get_frontmost_app_info()
            self._target_app_name = app_name
            self._target_bundle_id = bundle_id
            self.last_error = ""

        if self.config.sound_enabled:
            play_sound("Pop")
        if self.overlay:
            self.overlay.show_listening("Listening...")
            self.recorder.on_level_callback = self.overlay.update_audio_level

        try:
            session_file = self.recorder.start()
        except Exception as e:
            with self._lock:
                self._state = "IDLE"
            self.last_error = str(e)
            if self.overlay:
                self.overlay.show_error("Microphone unavailable")
            logger.exception("Could not start recording")
            return
        logger.info("Fixoflow recording started. Target app: %s (Session: %s)", self._target_app_name, session_file.name)

    def stop_and_process(self, auto_paste: bool = True) -> str:
        with self._lock:
            if self._state != "RECORDING":
                return ""
            self._state = "PROCESSING"
            target_app = self._target_app_name

        if self.config.sound_enabled:
            play_sound("Tink")
        if self.overlay:
            self.overlay.show_processing("Transcribing...")

        logger.info("Processing dictation for application: %s...", target_app)
        t0 = time.perf_counter()
        session_path = None

        try:
            # 1. Stop audio capture and obtain persisted wav buffer
            audio, session_path = self.recorder.stop()
            if len(audio) == 0:
                self.last_error = "No audio recorded"
                logger.warning("Empty audio recorded; skipping transcription.")
                if self.overlay:
                    self.overlay.show_error("No audio recorded")
                return ""

            # 2. Transcribe with prompt conditioning and pause slicing
            prompt = self.learner.get_dynamic_prompt_conditioning(target_app, self.config.mode)
            raw_text = self.stt.transcribe(audio, initial_prompt=prompt)
            if not raw_text:
                self.last_error = "No speech detected"
                logger.info("No speech detected.")
                if self.overlay:
                    self.overlay.show_error("No speech detected")
                return ""

            self._persist_transcript(session_path, raw_text, "transcribed")

            # 3. Apply mode formatting, dictionary replacements and polishing
            fixes_vocab = fixes_polish = 0
            try:
                formatted_text, fixes_vocab = self.learner.format_for_mode_counted(raw_text, mode=self.config.mode, app_name=target_app)
                effective_mode = self.learner.effective_mode(self.config.mode, target_app)
                final_text, fixes_polish = self.polisher.polish_counted(formatted_text, app_context=target_app, mode=effective_mode)
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
                duration_sec = len(audio) / self.config.sample_rate
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
                )
            except Exception as dbe:
                logger.error("Failed to record session in database: %s", dbe)

            # 5. Insert the text into the application that owns the cursor
            self.last_error = ""
            inserted = False
            notice = ""
            if auto_paste and final_text:
                inserted, notice = self._deliver_text(final_text)

            if self.overlay:
                if auto_paste and not inserted:
                    self.overlay.show_error(notice)
                else:
                    self.overlay.show_success("Paste sent" if auto_paste else "Transcribed!")

            return final_text
        except Exception as e:
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
        if not target_bundle:
            copied = copy_to_clipboard(text)
            self.last_error = ("Target application was not identified; transcript copied to clipboard and saved in History" if copied else "Target application was not identified; transcript saved in History")
            notify("Fixoflow", self.last_error)
            return False, "Saved · open History"

        current_bundle = get_frontmost_app_info()[1]
        if current_bundle != target_bundle:
            # The user touched another window mid-dictation. Return focus to the
            # original application so the transcript still lands at its cursor.
            if activate_application(target_bundle):
                current_bundle = get_frontmost_app_info()[1]
        if current_bundle != target_bundle:
            copied = copy_to_clipboard(text)
            self.last_error = ("Focus moved to another app; transcript is on the clipboard and in History"
                               if copied else "Focus moved to another app; transcript saved in History")
            notify("Fixoflow", self.last_error)
            return False, "Saved · open History"

        outcome = insert_text_at_cursor(text)
        if outcome.inserted:
            return True, ""
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

    @staticmethod
    def _persist_transcript(session_path, text: str, status: str, raw_text: str = "") -> None:
        """Keep decoded words recoverable even when formatting/history/paste fails."""
        destination = Path(session_path).with_suffix(".transcript.json")
        temporary = destination.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as output:
            json.dump({"status": status, "text": text, "raw_text": raw_text or text}, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)

    def cancel_recording(self) -> None:
        """Finish disk capture without transcribing or inserting; retain audio."""
        with self._lock:
            if self._state != "RECORDING":
                return
            self._state = "PROCESSING"
        try:
            self.recorder.stop()
            if self.overlay:
                self.overlay.show_success("Recording saved")
        except Exception as error:
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
