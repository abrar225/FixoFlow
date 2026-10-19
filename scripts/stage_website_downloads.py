"""Stage only existing, format-checked installers; missing platforms stay unavailable."""
from pathlib import Path
import argparse
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fixoflow.version import __version__
from verify_public_artifact import digest as file_digest, require_report
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--artifacts',type=Path,default=root/'dist')
parser.add_argument('--require-public-trust',action='store_true',help='Require native Windows/Mac trust reports before any staging writes; does not certify device compatibility')
parser.add_argument('--trust-reports',type=Path,default=root/'dist/trust')
parser.add_argument('--github-release-downloads', action='store_true', help='Link website buttons to versioned GitHub release assets; still verify and stage local installer bytes')
args=parser.parse_args()
public=root/'Landing_Page/public/downloads'
platforms=[
    ('macos','macOS','Apple Silicon','macOS 14 or later','Fixoflow.dmg',f'Fixoflow-{__version__}-macos-arm64.dmg','local build','Locally signed; not Apple notarized. English model included.'),
    ('windows','Windows','x64','Windows 11; Windows 10 22H2 compatibility target',f'Fixoflow-{__version__}-windows-x64-setup.exe',f'Fixoflow-{__version__}-windows-x64-setup.exe','preview','Unsigned preview. WebView2 and Microsoft Visual C++ runtimes required. No GPU needed. Physical-device acceptance is pending.'),
    ('linux','Linux','x64','Ubuntu 24.04 · x64 · X11 desktop',f'Fixoflow-{__version__}-linux-x64.deb',f'Fixoflow-{__version__}-linux-x64.deb','preview','Preview for X11. Wayland global shortcuts and automatic paste are not supported yet. No GPU needed.'),
]
# Verify all public-trust prerequisites before copying or deleting any installer.
trust={}
if args.require_public_trust:
    for platform in platforms:
        key,_,_,_,source_name,*_=platform
        if key in {'windows','macos'}:
            source=args.artifacts/source_name
            if not source.is_file():raise ValueError(f'Missing {key} public installer')
            trust[key]=require_report(source,key,args.trust_reports)
public.mkdir(parents=True,exist_ok=True)
releases=[];keep=set()
for key,name,arch,requirements,source_name,filename,channel,notes in platforms:
    source=args.artifacts/source_name;available=source.is_file();digest=None;size=None
    if available:
        if key=='macos':
            record=json.loads((args.artifacts/'macos-artifact.json').read_text())
            assert record['version']==__version__ and record['sha256']==file_digest(source),'Stale Mac DMG: rebuild before staging'
        with source.open('rb') as file:
            head=file.read(8);file.seek(-512,2);tail=file.read(4)
        assert (tail==b'koly' if key=='macos' else head.startswith(b'MZ') if key=='windows' else head==b'!<arch>\n'),f'Invalid {key} installer: {source}'
        size=source.stat().st_size;digest=file_digest(source)
        destination=public/filename;shutil.copy2(source,destination);keep.add(filename)
        assert file_digest(destination)==digest
    if key in trust:
        channel='signed preview'
        notes=('Developer ID / Gatekeeper and stapled notarization checks passed. English model included.' if key=='macos' else 'Publisher signature and timestamp verified. New releases can still receive SmartScreen reputation warnings. Physical-device acceptance remains separate.')
    download_url = (f'https://github.com/abrar225/FixoFlow/releases/download/v{__version__}/{filename}' if args.github_release_downloads else f'/downloads/{filename}') if available else None
    releases.append(dict(id=key,name=name,architecture=arch,requirements=requirements,available=available,filename=filename if available else None,downloadUrl=download_url,bytes=size,sha256=digest,channel=channel,notes=notes,publicTrustVerified=key in trust))
# Only remove superseded product installers in this generated output directory.
for old in public.iterdir():
    if old.is_file() and old.name.startswith('Fixoflow') and old.suffix.lower() in {'.dmg','.exe','.deb'} and old.name not in keep:old.unlink()
manifest={'version':__version__,'platforms':releases}
(root/'Landing_Page/lib/releases.generated.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'version':__version__,'available':[p['id'] for p in releases if p['available']]},indent=2))
