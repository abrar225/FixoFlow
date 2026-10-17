"""Local-only Whisper inference with explicit incomplete-transcription failures."""
from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import mlx_whisper
from huggingface_hub import snapshot_download

from fixoflow.audio.slicer import slice_audio_for_transcription
from fixoflow.config import FixoflowConfig

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    """A failed decode retains partial text for recovery, never for auto-paste."""

    def __init__(self, message: str, partial_text: str = '', failed_chunk_index: Optional[int] = None):
        super().__init__(message)
        self.partial_text = partial_text
        self.failed_chunk_index = failed_chunk_index


class STTEngine:
    def __init__(self, config: Optional[FixoflowConfig] = None):
        self.config = config or FixoflowConfig.load()
        self.model_name = self.config.model_name
        self.language = self.config.language
        self.sample_rate = self.config.sample_rate

    @staticmethod
    def _validate_model_path(model_path: Path) -> str:
        config = model_path / 'config.json'
        weight_paths = [model_path / name for name in ('weights.safetensors', 'weights.npz')]
        if not config.is_file() or config.stat().st_size == 0:
            raise TranscriptionError(
                f"Local Whisper model is incomplete at '{model_path}': missing config.json. "
                "Provision the complete model folder before dictating."
            )
        if not any(path.is_file() and path.stat().st_size > 0 for path in weight_paths):
            raise TranscriptionError(
                f"Local Whisper model is incomplete at '{model_path}': missing weights.npz "
                "or weights.safetensors. Provision the complete model folder before dictating."
            )
        return str(model_path.resolve())

    def resolve_model_path(self) -> str:
        # Explicit caller-selected folders always take precedence over defaults.
        local_path = Path(self.model_name).expanduser()
        if local_path.is_dir():
            return self._validate_model_path(local_path)
        bundle_root = getattr(sys, '_MEIPASS', None)
        bundled = Path(bundle_root) / 'models' / 'whisper' if bundle_root else None
        if (self.model_name == 'mlx-community/whisper-base.en-mlx'
                and bundled is not None and bundled.is_dir()):
            return self._validate_model_path(bundled)
        try:
            # Resolve an existing cache snapshot only. Passing the repository ID
            # directly to mlx-whisper would permit an implicit network fetch.
            cached = snapshot_download(self.model_name, local_files_only=True)
        except Exception as error:
            raise TranscriptionError(
                f"Whisper model '{self.model_name}' is unavailable locally. "
                "Install an app containing the model or provision a local model folder."
            ) from error
        return self._validate_model_path(Path(cached))

    def transcribe(self, audio: np.ndarray, initial_prompt: Optional[str] = None) -> str:
        if len(audio) == 0:
            return ''
        model_path = self.resolve_model_path()
        chunks = slice_audio_for_transcription(
            audio, sample_rate=self.sample_rate,
            max_chunk_sec=self.config.max_continuous_segment_sec,
        )
        transcriptions: list[str] = []
        base_prompt = self.config.initial_prompt if initial_prompt is None else initial_prompt
        prompt = base_prompt
        for index, chunk in enumerate(chunks):
            if len(chunk) == 0:
                continue
            options = {}
            if self.language:
                options['language'] = self.language
            if prompt:
                options['initial_prompt'] = prompt
            try:
                result = mlx_whisper.transcribe(
                    chunk, path_or_hf_repo=model_path,
                    condition_on_previous_text=False, **options,
                )
                text = result['text'].strip()
                if text:
                    transcriptions.append(text)
                    prompt = ' '.join(part for part in (base_prompt, ' '.join(text.split()[-30:])) if part)
            except Exception as error:
                raise TranscriptionError(
                    f"Transcription failed at chunk {index + 1} of {len(chunks)}: {error}",
                    partial_text=' '.join(transcriptions), failed_chunk_index=index,
                ) from error
        return ' '.join(transcriptions).strip()
