"""Windows/Linux x64: local CTranslate2 inference, CPU baseline.

This backend reuses shared chunking, dictionary prompts and partial recovery.
It is not a Windows desktop shell or a claim of Windows hardware validation.
"""
from __future__ import annotations
import os
import json
import sys
from pathlib import Path
from fixoflow.stt.engine import STTEngine, TranscriptionError


class CPUWhisperEngine(STTEngine):
    def __init__(self, config, model_factory=None):
        super().__init__(config)
        self._factory = model_factory
        self._model = None
        self._loaded_path = None

    def resolve_model_path(self):
        path = Path(self.model_name).expanduser()
        if self.model_name == 'multilingual-base':
            from fixoflow.model_packs import pack_path, validate_pack
            try:
                return str(validate_pack(pack_path('cpu'), 'cpu').resolve())
            except (ValueError, OSError) as error:
                raise TranscriptionError('Install the Base multilingual pack in Settings first.') from error
        if self.model_name == 'bundled-base.en':
            path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))/'models'/'whisper'
        required = ('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt')
        if not path.is_dir() or any(not (path/name).is_file() or (path/name).stat().st_size == 0 for name in required):
            raise TranscriptionError('Choose a complete local CTranslate2 Whisper model directory containing ' +
                                     ', '.join(required)+'. Mac MLX weights cannot be used directly. No model was downloaded.')
        if self.language != 'en':
            from fixoflow.model_packs import validate_model_language
            try:
                validate_model_language(json.loads((path/'config.json').read_text()), 'cpu')
            except (ValueError, OSError) as error:
                raise TranscriptionError(
                    'Selected local model is not compatible with multilingual recognition.') from error
        return str(path.resolve())

    def _decode(self, chunk, model_path, prompt):
        if self._model is None or self._loaded_path != model_path:
            factory = self._factory
            if factory is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as error:
                    raise TranscriptionError('Install the desktop speech extra before using this backend.') from error
                factory = WhisperModel
            self._model = factory(model_path, device='cpu', compute_type='float32',
                                  cpu_threads=max(1, min(self.config.cpu_threads, os.cpu_count() or 1)), num_workers=1, local_files_only=True)
            self._loaded_path = model_path
        segments, _ = self._model.transcribe(chunk, language=self.language, initial_prompt=prompt or None,
                                             condition_on_previous_text=False, vad_filter=False, beam_size=5)
        return ' '.join(segment.text.strip() for segment in segments).strip()
