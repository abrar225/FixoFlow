"""Stage only existing, format-checked installers; missing platforms stay unavailable."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fixoflow.version import __version__
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--artifacts',type=Path,default=root/'dist');args=parser.parse_args()
public=root/'Landing_Page/public/downloads';public.mkdir(parents=True,exist_ok=True)
platforms=[
    ('macos','macOS','Apple Silicon','macOS 14 or later','Fixoflow.dmg',f'Fixoflow-{__version__}-macos-arm64.dmg','local build','Locally signed; not Apple notarized. English model included.'),
    ('windows','Windows','x64','Windows 11; Windows 10 22H2 compatibility target',f'Fixoflow-{__version__}-windows-x64-setup.exe',f'Fixoflow-{__version__}-windows-x64-setup.exe','preview','Unsigned preview. WebView2 runtime required. No GPU needed. Physical-device acceptance is pending.'),
    ('linux','Linux','x64','Ubuntu 24.04 / compatible Debian desktop · X11',f'Fixoflow-{__version__}-linux-x64.deb',f'Fixoflow-{__version__}-linux-x64.deb','preview','Preview for X11. Wayland global shortcuts and automatic paste are not supported yet. No GPU needed.'),
]
releases=[];keep=set()
for key,name,arch,requirements,source_name,filename,channel,notes in platforms:
    source=args.artifacts/source_name;available=source.is_file();digest=None;size=None
    if available:
        if key=='macos':
            record=json.loads((args.artifacts/'macos-artifact.json').read_text())
            assert record['version']==__version__ and record['sha256']==hashlib.sha256(source.read_bytes()).hexdigest(),'Stale Mac DMG: rebuild before staging'
        with source.open('rb') as file:
            head=file.read(8);file.seek(-512,2);tail=file.read(4)
        assert (tail==b'koly' if key=='macos' else head.startswith(b'MZ') if key=='windows' else head==b'!<arch>\n'),f'Invalid {key} installer: {source}'
        size=source.stat().st_size;digest=hashlib.sha256(source.read_bytes()).hexdigest()
        destination=public/filename;shutil.copy2(source,destination);keep.add(filename)
        assert hashlib.sha256(destination.read_bytes()).hexdigest()==digest
    releases.append(dict(id=key,name=name,architecture=arch,requirements=requirements,available=available,filename=filename if available else None,bytes=size,sha256=digest,channel=channel,notes=notes))
# Only remove superseded product installers in this generated output directory.
for old in public.iterdir():
    if old.is_file() and old.name.startswith('Fixoflow') and old.suffix.lower() in {'.dmg','.exe','.deb'} and old.name not in keep:old.unlink()
manifest={'version':__version__,'platforms':releases}
(root/'Landing_Page/lib/releases.generated.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'version':__version__,'available':[p['id'] for p in releases if p['available']]},indent=2))
