"""Frozen entry point and non-interactive packaging diagnostics."""
import json
import os
from pathlib import Path
import sys
import platform
import hashlib
import wave

# PyInstaller must dispatch multiprocessing helper processes before app argument
# parsing or heavy imports (MLX/Numba can start a resource tracker).
if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()

def diagnostic_inference(environment=None):
    """Explicit offline backend diagnostic; never loads/saves user preferences."""
    import numpy as np
    from fixoflow.stt.engine import create_stt_engine
    from fixoflow.config import FixoflowConfig

    environment = os.environ if environment is None else environment
    selected = environment.get('FIXOFLOW_DIAGNOSTIC_MODEL')
    language = environment.get('FIXOFLOW_DIAGNOSTIC_LANGUAGE')
    options = {}
    if selected:
        if not selected.startswith('catalog:'):
            raise ValueError('Diagnostic model override must be an installed catalog:<id>')
        options['model_name'] = selected
    if language is not None:
        options['language'] = None if language == 'auto' else language
    config = FixoflowConfig(**options)
    audio_path = environment.get('FIXOFLOW_DIAGNOSTIC_WAV')
    if audio_path:
        audio_path = Path(audio_path)
        if not audio_path.is_absolute():
            raise ValueError('Diagnostic WAV must be an explicit absolute path')
        with wave.open(str(audio_path), 'rb') as recording:
            if (recording.getnchannels(), recording.getsampwidth(), recording.getframerate(), recording.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise ValueError('Diagnostic WAV must be uncompressed mono PCM16 at 16000 Hz')
            if not 0 < recording.getnframes() <= 16000 * 600:
                raise ValueError('Diagnostic WAV must contain 0–600 seconds of audio')
            frames = recording.readframes(recording.getnframes())
            if len(frames) != recording.getnframes() * 2:
                raise ValueError('Diagnostic WAV is truncated')
        audio = np.frombuffer(frames, dtype='<i2').astype(np.float32) / 32768.0
        input_identity = {'kind': 'explicit_wav', 'filename': audio_path.name,
                          'sha256': hashlib.sha256(audio_path.read_bytes()).hexdigest()}
    else:
        audio = (.01 * np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)).astype(np.float32)
        input_identity = {'kind': 'synthetic_tone_execution_only'}
    engine = create_stt_engine(config)
    result = engine.transcribe(audio)
    return {'text': result, 'shared_engine_inference': 'executed', 'model_name': config.model_name,
            'language': config.language, 'backend': type(engine).__module__ + '.' + type(engine).__name__,
            'inference_input': input_identity}

if __name__ == "__main__":
    if "--packaging-check" in sys.argv:
        import AppKit
        import WebKit
        import ServiceManagement
        import sounddevice
        import fixoflow.ui.hub

        root = Path(sys._MEIPASS)
        required = [root / "fixoflow/ui/hub.html", root / "fixoflow/ui/overlay.html",
                    root / "fixoflow/ui/hub.css", root / "fixoflow/ui/assets/flow-fold.png",
                    root / "fixoflow/ui/assets/Geist-Variable.woff2",
                    root / "fixoflow/ui/assets/Geist-LICENSE.txt", root / "fixoflow/ui/assets/Lucide-LICENSE.txt",
                    root / "models/whisper/config.json", root / "models/whisper/bundle-manifest.json"]
        model = root / "models/whisper"
        provenance=json.loads((root/'release/source-manifest.json').read_text())
        architecture = platform.machine()
        if architecture == "arm64":
            import mlx.core
            import mlx_whisper
            required += [root / "mlx/lib/mlx.metallib", root / "mlx_whisper/assets/gpt2.tiktoken", root / "mlx_whisper/assets/mel_filters.npz"]
            assert any((model / n).is_file() for n in ("weights.npz", "weights.safetensors")), "Missing bundled model weights"
        elif architecture == "x86_64":
            import faster_whisper
            import ctranslate2
            import av
            required += [model / n for n in ("model.bin", "tokenizer.json", "vocabulary.txt")]
        else:
            raise RuntimeError(f"Unsupported Mac architecture: {architecture}")
        assert all(p.is_file() for p in required), f"Missing bundle resources: {[str(p) for p in required if not p.is_file()]}"
        assert os.environ.get("HF_HUB_OFFLINE") == "1"
        assert Path(os.environ["FIXOFLOW_BUNDLED_MODEL"]) == model
        if "--inference" in sys.argv:
            print(json.dumps(diagnostic_inference()))
        print(json.dumps({"status": "ok", "bundle": str(root), "model": str(model),
                          "source_commit":provenance['git_commit'],
                          "ui_resources": "present", "native_dependencies": "imported",
                          "architecture": architecture, "offline": True}))
    else:
        from fixoflow.app import main
        main()
