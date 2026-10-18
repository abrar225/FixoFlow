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
(root/'dist/macos-artifact.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Recorded verified Mac artifact identity: '+manifest['version'])
