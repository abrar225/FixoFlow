"""Constrain the bundled application to the bundled, local model."""
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["FIXOFLOW_BUNDLED_MODEL"] = str(Path(sys._MEIPASS) / "models" / "whisper")
