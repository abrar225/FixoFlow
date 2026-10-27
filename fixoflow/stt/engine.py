"""Local-only Whisper inference with explicit incomplete-transcription failures."""
from __future__ import annotations
from fixoflow.audio.slicer import slice_audio_for_transcription
from fixoflow.config import FixoflowConfig

import logging
import json
import wave
from pathlib import Path
import sys
from typing import Optional

import numpy as np
# Load native inference only when the first decode is requested. The dashboard,
# shortcut recorder and history do not need the MLX/Numba runtime in memory.
mlx_whisper = None


def snapshot_download(*args, **kwargs):
    from huggingface_hub import snapshot_download as resolve
    return resolve(*args, **kwargs)


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

    def _validate_model_path(self, model_path: Path) -> str:
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
        if self.language != 'en':
            from fixoflow.model_packs import validate_model_language
            try:
                validate_model_language(json.loads(config.read_text()), 'mlx')
            except (ValueError, OSError) as error:
                raise TranscriptionError(
                    'Selected local model is not compatible with multilingual recognition.') from error
        return str(model_path.resolve())

    def resolve_model_path(self) -> str:
        # Explicit caller-selected folders always take precedence over defaults.
        if self.model_name == 'multilingual-base':
            from fixoflow.model_packs import pack_path, validate_pack
            try:
                return str(validate_pack(pack_path('mlx'), 'mlx').resolve())
            except (ValueError, OSError) as error:
                raise TranscriptionError('Install the Base multilingual pack in Settings first.') from error
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

    def transcribe(self, audio: np.ndarray, initial_prompt: Optional[str] = None, cancelled=None) -> str:
        if len(audio) == 0:
            return ''
        model_path = self.resolve_model_path()
        chunks = slice_audio_for_transcription(
            audio, sample_rate=self.sample_rate,
            max_chunk_sec=self.config.max_continuous_segment_sec,
        )
        return self._transcribe_chunks(chunks, model_path, initial_prompt, cancelled)

    def transcribe_file(self, path, initial_prompt=None, cancelled=None):
        """Process PCM recovery files using bounded windows, never a full WAV array."""
        from fixoflow.audio.filter import clean_audio_pipeline
        from fixoflow.audio.slicer import find_pause_split_point
        model_path = self.resolve_model_path()

        def chunks():
            with wave.open(str(path)) as capture:
                if (capture.getframerate(), capture.getnchannels(), capture.getsampwidth()) != (self.sample_rate, 1, 2):
                    raise TranscriptionError('Recovery audio must be 16 kHz mono PCM16.')
                maximum = int(self.config.max_continuous_segment_sec*self.sample_rate)
                while capture.tell() < capture.getnframes():
                    if cancelled and cancelled():
                        raise TranscriptionError('Transcription cancelled')
                    start = capture.tell()
                    expected = min(maximum, capture.getnframes()-start)
                    data = capture.readframes(expected)
                    if len(data) != expected*2:
                        raise TranscriptionError('Recording is truncated; audio is incomplete.')
                    audio = np.frombuffer(data, dtype='<i2').astype(np.float32)/32767.0
                    if len(audio) == maximum and capture.tell() < capture.getnframes():
                        split = find_pause_split_point(audio, self.sample_rate, min(
                            16, self.config.max_continuous_segment_sec), self.config.max_continuous_segment_sec)
                        split = max(1, min(split, len(audio)))
                        capture.setpos(start+split)
                        audio = audio[:split]
                    yield clean_audio_pipeline(audio, self.sample_rate)
        return self._transcribe_chunks(chunks(), model_path, initial_prompt, cancelled)

    def _transcribe_chunks(self, chunks, model_path, initial_prompt, cancelled):
        transcriptions: list[str] = []
        from fixoflow.languages import language_prompt
        base_prompt = ' '.join(p for p in (language_prompt(self.language, self.config.english_variant),
                               self.config.initial_prompt if initial_prompt is None else initial_prompt) if p)
        prompt = base_prompt
        iterator = iter(chunks)
        index = -1
        while True:
            index += 1
            try:
                chunk = next(iterator)
            except StopIteration:
                break
            except Exception as error:
                raise TranscriptionError(
                    f'Could not read chunk {index+1}: {error}', partial_text=' '.join(transcriptions), failed_chunk_index=index) from error
            if cancelled and cancelled():
                raise TranscriptionError('Transcription cancelled', partial_text=' '.join(transcriptions))
            if not np.any(chunk):
                continue
            if len(chunk) == 0:
                continue
            try:
                text = self._decode(chunk, model_path, prompt).strip()
                if cancelled and cancelled():
                    raise TranscriptionError('Transcription cancelled')
                if text:
                    transcriptions.append(text)
                    prompt = ' '.join(part for part in (base_prompt, ' '.join(text.split()[-30:])) if part)
            except Exception as error:
                raise TranscriptionError(
                    f"Transcription failed at chunk {index + 1}: {error}",
                    partial_text=' '.join(transcriptions), failed_chunk_index=index,
                ) from error
        return ' '.join(transcriptions).strip()

    def _decode(self, chunk, model_path, prompt):
        global mlx_whisper
        if mlx_whisper is None:
            if sys.platform != 'darwin':
                raise TranscriptionError('The MLX speech backend requires macOS.')
            import mlx_whisper as backend
            mlx_whisper = backend
        options = {}
        if self.language:
            options['language'] = self.language
        if prompt:
            options['initial_prompt'] = prompt
        return mlx_whisper.transcribe(chunk, path_or_hf_repo=model_path,
                                      condition_on_previous_text=False, **options)['text']


def create_stt_engine(config):
    if sys.platform == 'darwin':
        return STTEngine(config)
    if sys.platform == 'win32' or sys.platform.startswith('linux'):
        from fixoflow.stt.cpu import CPUWhisperEngine
        return CPUWhisperEngine(config)
    raise RuntimeError('Unsupported desktop platform.')
