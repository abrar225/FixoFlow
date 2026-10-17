"""
Fixoflow Configuration System
Persists settings, handles model selection, hotkeys, and zero-loss guarantees.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Legacy keys from earlier releases that map onto a current field.
LEGACY_FIELD_MAP = {
    "dual_mode_threshold_sec": "hold_threshold_sec",
}


@dataclass
class FixoflowConfig:
    # Model configuration
    model_name: str = "mlx-community/whisper-base.en-mlx"
    language: Optional[str] = "en"  # "en" for English, or None for auto-detect
    initial_prompt: str = "Clean, punctuated English speech."

    # Dictation mode: "auto" (app-detected), "coding" (agents/IDE), "writing", "raw"
    mode: str = "auto"

    # Audio settings
    sample_rate: int = 16000
    channels: int = 1
    max_continuous_segment_sec: float = 24.0

    # Session audio recovery directory (persistence is always on)
    cache_dir: str = str(Path.home() / ".fixoflow" / "audio_cache")

    # Local-only polishing. Cloud behavior was removed; legacy keys are ignored.
    polishing_engine: str = "rules"

    # Hotkey (pynput format): tap toggles, holding past the threshold talks.
    hotkey: str = "<ctrl>+<space>"
    dual_mode_hotkey: bool = True
    hold_threshold_sec: float = 0.45
    hold_to_talk: bool = False
    always_show_overlay: bool = True
    sound_enabled: bool = True

    # Logging
    log_level: str = "INFO"

    @classmethod
    def get_config_path(cls) -> Path:
        base_dir = Path.home() / ".fixoflow"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "config.json"

    @classmethod
    def load(cls) -> FixoflowConfig:
        config_path = cls.get_config_path()
        if config_path.exists():
            with config_path.open(encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(f"Configuration at '{config_path}' must be a JSON object")
            config = cls(**cls._normalize_fields(data))
            config.validate()
            return config
        config = cls()
        config.save()
        return config

    @classmethod
    def _normalize_fields(cls, data: dict) -> dict:
        """Map legacy names onto current fields and drop unknown ones.

        Unknown keys are ignored with a warning instead of failing startup, so
        configurations written by older releases keep working.
        """
        known = {field.name for field in dataclasses.fields(cls)}
        normalized: dict = {}
        unknown: list = []
        for key, value in data.items():
            target = LEGACY_FIELD_MAP.get(key, key)
            if target in known:
                normalized[target] = value
            else:
                unknown.append(key)
        if unknown:
            logger.warning("Ignoring unknown configuration keys: %s", ", ".join(sorted(unknown)))
        if normalized.get("polishing_engine") == "gemini":
            normalized["polishing_engine"] = "rules"
        return normalized

    def validate(self) -> None:
        for name in ("always_show_overlay", "sound_enabled", "dual_mode_hotkey", "hold_to_talk"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if self.mode not in {"auto", "coding", "writing", "raw"}:
            raise ValueError("Unsupported dictation mode")
        if self.polishing_engine not in {"rules", "none"}:
            raise ValueError("Only offline polishing engines are supported")
        if self.sample_rate != 16000 or self.channels != 1:
            raise ValueError("Fixoflow requires 16 kHz mono audio")
        if not 1 <= self.max_continuous_segment_sec <= 24:
            raise ValueError("Audio chunks must be between 1 and 24 seconds")
        if not 0.1 <= self.hold_threshold_sec <= 2:
            raise ValueError("Hold threshold must be between 0.1 and 2 seconds")
        if not self.hotkey.strip() or not self.model_name.strip():
            raise ValueError("Shortcut and model must not be empty")
        if not self.cache_dir.strip():
            raise ValueError("Audio cache directory must not be empty")

    def save(self) -> None:
        self.validate()
        config_path = self.get_config_path()
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        if config_path.exists():
            shutil.copy2(config_path, config_path.with_suffix(".json.bak"))
        fd, temporary = tempfile.mkstemp(prefix="config-", dir=config_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, config_path)
        finally:
            Path(temporary).unlink(missing_ok=True)
