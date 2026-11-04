"""Build native x86_64 Linux preview packages from the same frozen payload.

AppImage deliberately uses host WebKitGTK/GTK/PortAudio; it is not a universal
Linux runtime. Build/test DEB and AppImage on Ubuntu 24.04, RPM on Fedora 43.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = runpy.run_path(str(ROOT / 'fixoflow/version.py'))['__version__']
APPIMAGE_TOOLS = {
    'appimagetool': ('https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage',
                    15092216, 'ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0'),
    # Immutable GitHub asset identity AND digest; never follow the mutable continuous tag.
    'runtime': ('https://api.github.com/repos/AppImage/type2-runtime/releases/assets/657374641',
                944632, '617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46'),
}
DEB_DEPENDS = 'libwebkit2gtk-4.1-0, gir1.2-webkit2-4.1, libgtk-3-0, gir1.2-ayatanaappindicator3-0.1, libportaudio2, xclip, libnotify-bin, libx11-6, libxtst6'
RPM_DEPENDS = 'webkit2gtk4.1, gtk3, libayatana-appindicator-gtk3, portaudio, xclip, libnotify, libX11, libXtst, libstdc++, glibc'


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            checksum.update(block)
    return checksum.hexdigest()


def desktop_text(executable):
    return f'''[Desktop Entry]
Name=Fixo Flow
Comment=Local voice dictation (X11 preview)
Exec={executable}
Icon=fixoflow
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Accessibility;
StartupWMClass=Fixo Flow
'''


def stage_system(payload, stage):
    application = stage / 'opt/fixoflow'
    shutil.copytree(payload, application, symlinks=True)
    entry = stage / 'usr/share/applications/fixoflow.desktop'
    entry.parent.mkdir(parents=True)
    entry.write_text(desktop_text('/opt/fixoflow/Fixoflow'))
    icon = stage / 'usr/share/icons/hicolor/256x256/apps/fixoflow.png'
    icon.parent.mkdir(parents=True)
    shutil.copy2(ROOT / 'fixoflow/ui/assets/flow-fold.png', icon)
    return application


def stage_appdir(payload, stage):
    application = stage / 'usr/lib/fixoflow'
    shutil.copytree(payload, application, symlinks=True)
    (stage / 'fixoflow.desktop').write_text(desktop_text('Fixoflow'))
    shutil.copy2(ROOT / 'fixoflow/ui/assets/flow-fold.png', stage / 'fixoflow.png')
    (stage / '.DirIcon').symlink_to('fixoflow.png')
    notices = application / '_internal/licenses/AppImage-runtime'
    notices.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'packaging/licenses/AppImage-runtime-LICENSE.txt', notices / 'LICENSE.txt')
    (notices / 'SOURCE.txt').write_text('https://github.com/AppImage/type2-runtime/tree/fedfad51acc2860b2916a1eef32ba4a500ff31ef\nhttps://github.com/AppImage/type2-runtime/actions/runs/39320578745\n')
    # No cd into the project, no install location assumption, preserve all arguments.
    runner = stage / 'AppRun'
    runner.write_text('#!/bin/sh\nset -eu\nAPPDIR="${APPDIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}"\nexec "$APPDIR/usr/lib/fixoflow/Fixoflow" "$@"\n')
    runner.chmod(0o755)


def verified_tool(name, directory):
    url, size, expected = APPIMAGE_TOOLS[name]
    path = directory / name
    if path.is_file() and path.stat().st_size == size and digest(path) == expected:
        return path
    directory.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.download')
    try:
        request = urllib.request.Request(url, headers={'Accept': 'application/octet-stream', 'User-Agent': 'Fixoflow-preview-packager'})
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as output:
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > size:
                    raise ValueError(f'Oversized {name} download')
                output.write(block)
        if temporary.stat().st_size != size or digest(temporary) != expected:
            raise ValueError(f'Pinned {name} digest/size mismatch')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    path.chmod(0o755)
    return path


def build_deb(payload, output, stage):
    application = stage_system(payload, stage)
    control = stage / 'DEBIAN'
    control.mkdir()
    size = sum(p.stat().st_size for p in application.rglob('*') if p.is_file()) // 1024
    (control / 'control').write_text(f'''Package: fixoflow
Version: {VERSION}
Architecture: amd64
Maintainer: Fixo Flow <noreply@fixoflow.local>
Section: sound
Priority: optional
Installed-Size: {size}
Depends: {DEB_DEPENDS}
Description: Local speech dictation for X11 desktops (preview)
 Bundled CPU English model; additional models are explicit downloads.
 Global shortcuts and insertion require X11. No GPU required.
''')
    subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(stage), str(output)], check=True)
    return {'builder': subprocess.check_output(['dpkg-deb', '--version'], text=True).splitlines()[0]}


def build_rpm(payload, output, stage):
    tree = stage / 'root'
    stage_system(payload, tree)
    for name in ('BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS'):
        (stage / name).mkdir(exist_ok=True)
    spec = stage / 'SPECS/fixoflow.spec'
    spec.write_text(f'''Name: fixoflow
Version: {VERSION}
Release: 1
Summary: Local speech dictation for X11 desktops (preview)
License: MIT AND LGPL-3.0-or-later
BuildArch: x86_64
AutoReqProv: no
Requires: {RPM_DEPENDS}
%description
Offline bundled CPU English speech recognition. Additional models require an
explicit download. X11 is required for shortcuts/insertion. Fedora 43 preview.
%install
mkdir -p %{{buildroot}}
cp -a {tree}/. %{{buildroot}}/
%files
/opt/fixoflow
/usr/share/applications/fixoflow.desktop
/usr/share/icons/hicolor/256x256/apps/fixoflow.png
''')
    # PyInstaller owns stripped binaries; RPM must not rewrite its executable archive.
    subprocess.run(['rpmbuild', '-bb', '--define', f'_topdir {stage}', '--define', '__os_install_post %{nil}', '--define', '_build_id_links none', str(spec)], check=True)
    candidates = list((stage / 'RPMS').rglob('*.rpm'))
    if len(candidates) != 1:
        raise RuntimeError(f'Expected exactly one native RPM, got {candidates}')
    shutil.copy2(candidates[0], output)
    subprocess.run(['rpm', '-K', '--nosignature', str(output)], check=True)
    return {'builder': subprocess.check_output(['rpmbuild', '--version'], text=True).strip()}


def build_appimage(payload, output, stage, tool_cache):
    stage_appdir(payload, stage)
    subprocess.run(['desktop-file-validate', str(stage / 'fixoflow.desktop')], check=True)
    tool, runtime = (verified_tool(name, tool_cache) for name in ('appimagetool', 'runtime'))
    environment = dict(os.environ, APPIMAGE_EXTRACT_AND_RUN='1', ARCH='x86_64')
    subprocess.run([str(tool), '--runtime-file', str(runtime), str(stage), str(output)], env=environment, check=True)
    output.chmod(0o755)
    with output.open('rb') as image:
        if image.read(4) != b'\x7fELF':
            raise RuntimeError('AppImage is not an ELF executable')
    return {'builder': 'appimagetool 1.9.1', 'tools': {name: {'url': value[0], 'sha256': value[2], 'bytes': value[1]} for name, value in APPIMAGE_TOOLS.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('deb', 'rpm', 'appimage'), default='deb')
    parser.add_argument('--payload', type=Path, default=ROOT / 'dist/Fixoflow')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    parser.add_argument('--tool-cache', type=Path, default=ROOT / 'build/appimage-tools')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        parser.error('Native x86_64 Linux required; cross-built payloads are not supported')
    payload = args.payload.resolve()
    executable = payload / 'Fixoflow'
    if not executable.is_file() or executable.read_bytes()[:4] != b'\x7fELF':
        parser.error('Payload must contain the native frozen ELF executable')
    source = payload / '_internal/release/source-manifest.json'
    if not source.is_file():
        parser.error('Frozen source provenance is required')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    extension = {'deb': 'deb', 'rpm': 'rpm', 'appimage': 'AppImage'}[args.format]
    output = (args.output_dir / f'Fixoflow-{VERSION}-linux-x64.{extension}').resolve()
    with tempfile.TemporaryDirectory(prefix=f'fixoflow-{args.format}-') as temporary:
        stage = Path(temporary)
        if args.format == 'appimage':
            tools = build_appimage(payload, output, stage, args.tool_cache.resolve())
        else:
            tools = {'deb': build_deb, 'rpm': build_rpm}[args.format](payload, output, stage)
    manifest = {'version': VERSION, 'filename': output.name, 'sha256': digest(output), 'bytes': output.stat().st_size,
                'architecture': 'x86_64', 'preview': True, 'source_commit': json.loads(source.read_text())['git_commit'],
                'source_manifest_sha256': digest(source), **tools}
    output.with_suffix(output.suffix + '.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
