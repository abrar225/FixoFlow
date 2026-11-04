"""Record the release identity and digest after a successful local DMG build."""
from pathlib import Path
import hashlib
import json
import plistlib
root=Path(__file__).resolve().parents[1]
app=root/'dist/Fixoflow.app'
info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
image=root/'dist/Fixoflow.dmg'
manifest={'version':info['CFBundleShortVersionString'],'filename':image.name,'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'bytes':image.stat().st_size}
source_manifest=app/'Contents/Resources/release/source-manifest.json'
if source_manifest.is_file():
    source=json.loads(source_manifest.read_text())
    manifest.update(source_commit=source['git_commit'],source_manifest_sha256=hashlib.sha256(source_manifest.read_bytes()).hexdigest())
(root/'dist/macos-artifact.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Recorded verified Mac artifact identity: '+manifest['version'])
