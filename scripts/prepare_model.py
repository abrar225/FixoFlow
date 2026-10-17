"""Stage a revision-pinned local model. Never downloads files."""
from pathlib import Path
import hashlib
import json
import os
import shutil

from huggingface_hub import snapshot_download

repo = "mlx-community/whisper-base.en-mlx"
revision = "aa0678c3466ed62c5c6114ec600a0e1f96820089"
source = Path(os.environ["FIXOFLOW_MODEL_DIR"]) if os.environ.get("FIXOFLOW_MODEL_DIR") else Path(
    snapshot_download(repo_id=repo, revision=revision, local_files_only=True)
)
stage = Path(os.environ["FIXOFLOW_BUILD_MODEL_DIR"])
stage.mkdir(parents=True, exist_ok=True)
weights = next((source / name for name in ("weights.safetensors", "weights.npz", "model.safetensors")
                if (source / name).is_file()), None)
if not weights or not (source / "config.json").is_file():
    raise SystemExit(f"Incomplete local Whisper model: {source}; config.json and weights required")
# mlx-whisper 0.4.3 expects weights.safetensors, even for repos using model.safetensors.
name = "weights.safetensors" if weights.suffix == ".safetensors" else "weights.npz"
for candidate in stage.iterdir():
    if candidate.is_file():
        candidate.unlink()
for filename in ("config.json", "README.md", "LICENSE", "LICENSE.txt"):
    if (source / filename).is_file():
        shutil.copy2(source / filename, stage / filename)
shutil.copy2(weights, stage / name)
manifest = {
    "source": repo if not os.environ.get("FIXOFLOW_MODEL_DIR") else str(source),
    "revision": revision if not os.environ.get("FIXOFLOW_MODEL_DIR") else "caller-supplied-local-model",
    "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.iterdir()) if p.is_file()},
}
(stage / "bundle-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Staged local model: {stage} ({weights.stat().st_size:,} weight bytes)")
