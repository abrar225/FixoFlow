"""Record exactly which repository source files were frozen into a local build."""
import hashlib
import json
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
paths=[root/'pyproject.toml']
for folder in ('fixoflow','packaging','scripts'):
    paths.extend(p for p in (root/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.spec','.sh','.html','.css','.woff2','.png','.icns','.ico','.txt','.md'})
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
manifest={'schema_version':1,'git_commit':commit,'files':files}
destination=root/'build/source-manifest.json';destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(manifest,indent=2)+'\n')
print('Recorded frozen source manifest for '+commit)
