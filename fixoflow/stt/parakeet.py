"""Pinned int8 Parakeet through ONNX Runtime, with explicit local-only loading.

The backend shares durable-file chunking/partial recovery/cancellation checks.
Parakeet does not accept a forced language or Whisper vocabulary prompt.
"""
from pathlib import Path

import numpy as np

from fixoflow.stt.contracts import RecognitionCapabilities
from fixoflow.stt.engine import STTEngine, TranscriptionError


class ParakeetEngine(STTEngine):
    def __init__(self, config, model_factory=None):
        super().__init__(config)
        self._factory = model_factory
        self._model = None
        self._loaded_path = None

    def resolve_model_path(self):
        from fixoflow.languages import validate_language_selection
        from fixoflow.models.manager import resolve_catalog_model
        try:
            validate_language_selection(self.language, self.model_name)
            path = resolve_catalog_model(self.model_name, 'onnx')
            if path is None:
                raise ValueError('Parakeet requires an explicitly installed pinned catalog model.')
            return path
        except (ValueError, OSError) as error:
            raise TranscriptionError(str(error)) from error

    @property
    def capabilities(self):
        return RecognitionCapabilities(backend='onnx', vocabulary_hints=False)

    def _load_model(self, path):
        if self._factory:
            return self._factory(path, offline=True, quantization='int8',
                                 cpu_threads=self.config.cpu_threads)
        try:
            import onnxruntime as ort
            from onnx_asr.loader import Manager
        except ImportError as error:
            raise TranscriptionError('Parakeet requires the packaged onnx-asr and ONNX Runtime dependencies.') from error
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.config.cpu_threads
        options.inter_op_num_threads = 1
        # Explicit offline=True prevents hub resolution even when local files
        # are missing. CPU provider keeps platform behavior predictable; the
        # pinned package's bundled preprocessing resources require no download.
        manager = Manager(sess_options=options, providers=['CPUExecutionProvider'],
                          preprocessor_config={'use_numpy_preprocessors':True,'max_concurrent_workers':1})
        return manager.create_asr('nemo-conformer-tdt', Path(path),
                                  quantization='int8', offline=True)

    def warm_up(self):
        path = self.resolve_model_path()
        if self._model is None or self._loaded_path != path:
            self._model = None
            self._loaded_path = None
            self._model = self._load_model(path)
            self._loaded_path = path
        return path

    def _decode(self, chunk, model_path, prompt):
        if self._model is None or self._loaded_path != model_path:
            self._model = None
            self._loaded_path = None
            self._model = self._load_model(model_path)
            self._loaded_path = model_path
        text = self._model.recognize(np.asarray(chunk, dtype=np.float32), sample_rate=16000)
        if not isinstance(text, str):
            raise TranscriptionError('Parakeet returned an unsupported transcription result.')
        return text.strip()
