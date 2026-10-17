"""Frozen entry point and non-interactive packaging diagnostics."""
import json
import os
from pathlib import Path
import sys

# PyInstaller must dispatch multiprocessing helper processes before app argument
# parsing or heavy imports (MLX/Numba can start a resource tracker).
if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()

from fixoflow.app import main

if __name__ == "__main__":
    if "--packaging-check" in sys.argv:
        import AppKit
        import WebKit
        import sounddevice
        import mlx.core
        import mlx_whisper
        import fixoflow.ui.hub

        root = Path(sys._MEIPASS)
        required = [root / "fixoflow/ui/hub.html", root / "fixoflow/ui/overlay.html",
                    root / "models/whisper/config.json", root / "mlx/lib/mlx.metallib",
                    root / "mlx_whisper/assets/gpt2.tiktoken", root / "mlx_whisper/assets/mel_filters.npz"]
        model = root / "models/whisper"
        assert any((model / n).is_file() for n in ("weights.npz", "weights.safetensors")), "Missing bundled model weights"
        assert all(p.is_file() for p in required), f"Missing bundle resources: {[str(p) for p in required if not p.is_file()]}"
        assert os.environ.get("HF_HUB_OFFLINE") == "1"
        assert Path(os.environ["FIXOFLOW_BUNDLED_MODEL"]) == model
        if "--inference" in sys.argv:
            import numpy as np
            result = mlx_whisper.transcribe(np.zeros(16000, dtype=np.float32),
                                            path_or_hf_repo=str(model), language="en")
            print(json.dumps({"synthetic_silence_text": result.get("text", "")}))
        print(json.dumps({"status": "ok", "bundle": str(root), "model": str(model),
                          "ui_resources": "present", "native_dependencies": "imported",
                          "offline": True}))
    else:
        main()
