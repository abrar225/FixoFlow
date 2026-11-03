"""Verify an installed/extracted preview in a disposable profile and empty cwd.

macOS checks a copy extracted from the actual DMG. Linux checks the installed
executable or AppImage runtime (with extraction mode when FUSE is unavailable).
These checks do not request microphone access, install hotkeys, or insert text.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import runpy
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = runpy.run_path(str(ROOT / 'fixoflow/version.py'))['__version__']


def json_lines(text):
    result = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def run_check(executable, report, environment, empty):
    subprocess.run([str(executable), '--self-check', '--tray-check', '--check-report', str(report)], env=environment, cwd=empty, check=True, timeout=180)
    value = json.loads(report.read_text())
    assert value['ui'] == 'ok' and value['local_inference'] == 'executed' and value['version'] == VERSION, value
    assert value['tray_backend'] == 'ready', value
    return value


def check_mac(image, directory, environment, expected_commit):
    mount = directory / 'mounted'
    mount.mkdir()
    subprocess.run(['hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', str(mount), str(image)], check=True, timeout=90)
    try:
        app = directory / 'Applications/Fixoflow.app'
        app.parent.mkdir()
        subprocess.run(['ditto', str(mount / 'Fixoflow.app'), str(app)], check=True)
    finally:
        subprocess.run(['hdiutil', 'detach', str(mount)], check=True, timeout=90)
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    assert info['CFBundleShortVersionString'] == VERSION, info
    executable = app / 'Contents/MacOS/Fixoflow'
    architectures = subprocess.check_output(['lipo', '-archs', str(executable)], text=True).split()
    assert architectures == [platform.machine()], architectures
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    provenance = json.loads((app / 'Contents/Resources/release/source-manifest.json').read_text())
    if expected_commit:
        assert provenance['git_commit'] == expected_commit, provenance['git_commit']
    output = subprocess.check_output([str(executable), '--packaging-check', '--inference'], cwd=directory, env=environment, text=True, timeout=180)
    print(output)
    results = json_lines(output)
    assert any(item.get('shared_engine_inference') == 'executed' for item in results), results
    assert any(item.get('status') == 'ok' and item.get('architecture') == platform.machine() for item in results), results
    output = subprocess.check_output([str(executable), '--self-check'], cwd=directory, env=environment, text=True, timeout=180)
    print(output)
    assert any(item.get('ui') == 'ok' for item in json_lines(output)), output
    return {'ui': 'ok', 'local_inference': 'executed', 'architecture': platform.machine(), 'source_commit': provenance['git_commit'], 'installed_from_dmg': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dmg', type=Path)
    parser.add_argument('--executable', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--expected-commit', default=os.environ.get('GITHUB_SHA'))
    args = parser.parse_args()
    args.report = args.report.resolve()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fixoflow-native-preview-') as temporary:
        directory = Path(temporary)
        home = directory / 'home'
        home.mkdir()
        environment = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'), XDG_CACHE_HOME=str(home / '.cache'), XDG_DATA_HOME=str(home / '.local/share'))
        environment.pop('FIXOFLOW_MODEL_DIR', None)
        if args.dmg:
            if platform.system() != 'Darwin':
                parser.error('DMG checks require native macOS')
            result = check_mac(args.dmg.resolve(), directory, environment, args.expected_commit)
        else:
            if not args.executable:
                parser.error('--dmg or --executable is required')
            executable = args.executable.resolve()
            if executable.suffix == '.AppImage':
                extraction_environment = dict(environment)
                extraction_environment.pop('APPIMAGE_EXTRACT_AND_RUN', None)
                subprocess.run([str(executable), '--appimage-extract'], cwd=directory, env=extraction_environment, check=True, timeout=120, stdout=subprocess.DEVNULL)
                source = directory / 'squashfs-root/usr/lib/fixoflow/_internal/release/source-manifest.json'
                provenance = json.loads(source.read_text())
                if args.expected_commit:
                    assert provenance['git_commit'] == args.expected_commit, provenance['git_commit']
            temporary_report = directory / 'result.json'
            result = run_check(executable, temporary_report, environment, directory)
            if executable.suffix == '.AppImage':
                result['source_commit'] = provenance['git_commit']
                result['appimage_runtime'] = 'executed'
            # Normal installed payloads have an adjacent provenance manifest. The
            # AppImage report must carry its embedded identity (checked by app).
            source = executable.parent / '_internal/release/source-manifest.json'
            if source.is_file():
                commit = json.loads(source.read_text())['git_commit']
                if args.expected_commit:
                    assert commit == args.expected_commit, commit
                result['source_commit'] = commit
            shutil.copy2(temporary_report, args.report.with_suffix('.raw.json'))
        result.update(version=VERSION, disposable_profile=True, empty_working_directory=True, preview=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))


if __name__ == '__main__':
    main()
