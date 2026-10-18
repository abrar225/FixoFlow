"""
Fixoflow Configuration System
Persists settings, model selection, shortcuts and recovery preferences.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
from fixoflow.shortcuts import Shortcut, validate_pair

logger = logging.getLogger(__name__)

# Floating pill snap zones. Shared with the overlay geometry so the hub,
# validation, and positioning cannot drift apart.
OVERLAY_POSITIONS = ("top-center", "bottom-left", "bottom-center", "bottom-right")

# Output styles applied by the local polisher in writing mode. "verbatim"
# keeps the recognizer's wording untouched apart from trimming.
OUTPUT_STYLES = ("natural", "concise", "professional", "verbatim")


@dataclass
class FixoflowConfig:
    # Model configuration
    model_name: str = "mlx-community/whisper-base.en-mlx" if sys.platform == "darwin" else "bundled-base.en"
    cpu_threads: int = 2  # Windows/Linux CPU budget; recognition settings stay unchanged.
    language: Optional[str] = "en"  # "en" for English, or None for auto-detect
    initial_prompt: str = ""
    english_variant: str = "en-US"

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
    # Writing-mode output style: "natural", "concise", "professional", "verbatim".
    output_style: str = "natural"
    spoken_commands: bool = False

    # Separate device-local bindings; labels never determine key identity.
    hold_shortcut: dict = field(default_factory=lambda: Shortcut.from_text('<ctrl>+<space>').as_dict())
    hands_free_shortcut: dict = field(default_factory=lambda: Shortcut.from_text('<alt>+<space>').as_dict())
    check_updates_on_launch: bool = True
    auto_install_updates: bool = False
    always_show_overlay: bool = True
    # Floating pill snap zone: "top-center", "bottom-left", "bottom-center"
    # or "bottom-right".
    overlay_position: str = "bottom-center"
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
        data = dict(data)
        # Old timing-based settings migrate once at this owning boundary. The
        # user's existing shortcut becomes hold-to-talk; no file is rewritten
        # until the user saves, when the original is backed up atomically.
        legacy = data.pop('hotkey', None)
        dual = data.pop('dual_mode_hotkey', True)
        hold_only = data.pop('hold_to_talk', False)
        data.pop('hold_threshold_sec', None)
        data.pop('dual_mode_threshold_sec', None)
        if legacy and 'hold_shortcut' not in data and 'hands_free_shortcut' not in data:
            saved = Shortcut.from_text(legacy).as_dict()
            data['hold_shortcut'] = saved
            candidates = ['<alt>+<space>','<cmd>+<shift>+<f12>','<ctrl>+<alt>+<f11>']
            for candidate in candidates:
                alternate = Shortcut.from_text(candidate).as_dict()
                try:
                    validate_pair(saved, alternate)
                    data['hands_free_shortcut'] = alternate
                    break
                except ValueError:
                    continue
            if data.get('hands_free_shortcut') is None:
                raise ValueError('Choose two distinct shortcuts in Settings.')
            if not dual and not hold_only:
                data['hold_shortcut'], data['hands_free_shortcut'] = data['hands_free_shortcut'], saved
        known = {field.name for field in dataclasses.fields(cls)}
        normalized: dict = {}
        unknown: list = []
        for key, value in data.items():
            target = key
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
        from fixoflow.languages import LANGUAGES, ENGLISH_VARIANTS
        if self.language is not None and self.language not in LANGUAGES:
            raise ValueError('Choose a supported recognition language.')
        if self.english_variant not in ENGLISH_VARIANTS:
            raise ValueError('Choose a supported English regional preference.')
        if self.language != 'en' and self.model_name in {'bundled-base.en','mlx-community/whisper-base.en-mlx','mlx-community/whisper-small.en-mlx'}:
            raise ValueError('Install and choose the Base multilingual pack for this language or auto detection.')
        for name in ("always_show_overlay", "sound_enabled", "check_updates_on_launch", "auto_install_updates", "spoken_commands"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        if self.mode not in {"auto", "coding", "writing", "raw"}:
            raise ValueError("Unsupported dictation mode")
        if self.output_style not in OUTPUT_STYLES:
            raise ValueError("Output style must be one of: " + ", ".join(OUTPUT_STYLES))
        if self.overlay_position not in OVERLAY_POSITIONS:
            raise ValueError("Floating pill position must be one of: " + ", ".join(OVERLAY_POSITIONS))
        if self.polishing_engine not in {"rules", "none"}:
            raise ValueError("Only offline polishing engines are supported")
        if self.sample_rate != 16000 or self.channels != 1:
            raise ValueError("Fixoflow requires 16 kHz mono audio")
        if not 1 <= self.max_continuous_segment_sec <= 24:
            raise ValueError("Audio chunks must be between 1 and 24 seconds")
        if type(self.cpu_threads) is not int or not 1 <= self.cpu_threads <= 4:
            raise ValueError("CPU threads must be between 1 and 4")
        validate_pair(self.hold_shortcut, self.hands_free_shortcut)
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise ValueError("Model must not be empty")
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
