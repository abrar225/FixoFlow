"""Build-policy tests independent of native inference/GUI dependencies."""
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
import sys
import wave

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('/', '_'), ROOT / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload(tmp_path):
    target = tmp_path / 'payload'
    target.mkdir()
    executable = target / 'Fixoflow'
    executable.write_bytes(b'\x7fELFtest')
    executable.chmod(0o755)
    (target / 'link').symlink_to('Fixoflow')
    source = target / '_internal/release/source-manifest.json'
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({'git_commit': 'a' * 40}))
    return target


def test_cpu_model_rejects_corruption_and_checks_git_identity(tmp_path):
    module = load('scripts/prepare_cpu_model.py')
    file = tmp_path / 'config.json'
    file.write_bytes(b'hello')
    expected = (5, 'git-sha1', hashlib.sha1(b'blob 5\0hello').hexdigest())
    module.verify(file, expected)
    file.write_bytes(b'jello')
    with pytest.raises(ValueError, match='identity mismatch'):
        module.verify(file, expected)
    file.write_bytes(b'hello!')
    with pytest.raises(ValueError, match='Wrong size'):
        module.verify(file, expected)


def test_cpu_offline_reuses_only_verified_files_and_preserves_previous_on_failure(tmp_path, monkeypatch):
    module = load('scripts/prepare_cpu_model.py')
    output = tmp_path / 'model'
    output.mkdir()
    (output / 'a').write_bytes(b'valid')
    expected = (5, 'sha256', hashlib.sha256(b'valid').hexdigest())
    monkeypatch.setattr(module, 'FILES', {'a': expected})
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('offline attempted download'))
    assert module.stage(output, offline=True)['verified'] is True
    (output / 'a').write_bytes(b'wrong')
    with pytest.raises(RuntimeError, match='Missing verified offline'):
        module.stage(output, offline=True)
    assert (output / 'a').read_bytes() == b'wrong'


def test_native_arch_policy_rejects_unknown():
    module = load('packaging/build_support.py')
    assert module.mac_architecture('arm64') == 'arm64'
    assert module.mac_architecture('x86_64') == 'x86_64'
    with pytest.raises(RuntimeError, match='Unsupported native'):
        module.mac_architecture('i386')


@pytest.mark.parametrize('architecture', ['arm64', 'x86_64'])
def test_mac_spec_selects_only_compatible_backend(architecture, monkeypatch, tmp_path):
    import platform
    from importlib import metadata
    hooks = pytest.importorskip('PyInstaller.utils.hooks')

    monkeypatch.setattr(platform, 'machine', lambda: architecture)
    monkeypatch.setenv('FIXOFLOW_BUILD_ARCH', architecture)
    monkeypatch.setenv('FIXOFLOW_BUILD_MODEL_DIR', str(tmp_path / 'model'))
    license_file = tmp_path / 'LICENSE'
    license_file.write_text('test fixture license')
    monkeypatch.setattr(metadata, 'distribution', lambda name: SimpleNamespace(files=[Path('LICENSE')], locate_file=lambda _: license_file))
    for method in ('collect_data_files', 'collect_dynamic_libs', 'copy_metadata'):
        monkeypatch.setattr(hooks, method, lambda name, **kwargs: [(name, name)])
    monkeypatch.setattr(hooks, 'collect_submodules', lambda name: [name])
    captured = {}
    def analysis(*args, **kwargs):
        captured['analysis'] = kwargs
        return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])
    def executable(*args, **kwargs):
        captured['executable'] = kwargs
        return object()
    runpy.run_path(str(ROOT / 'packaging/Fixoflow.spec'), init_globals={
        'SPECPATH': str(ROOT / 'packaging'), 'Analysis': analysis,
        'PYZ': lambda *a, **k: object(), 'EXE': executable,
        'COLLECT': lambda *a, **k: object(), 'BUNDLE': lambda *a, **k: object(),
    })
    assert captured['executable']['target_arch'] == architecture
    imports = captured['analysis']['hiddenimports']
    excludes = captured['analysis']['excludes']
    if architecture == 'arm64':
        assert 'mlx' in imports and 'onnxruntime' in imports
    else:
        assert 'ctranslate2' in imports and 'mlx' not in imports
        assert 'mlx' in excludes and 'onnxruntime' in excludes
    assert 'pystray' in excludes


def test_license_collection_fails_closed_if_notice_absent(monkeypatch, tmp_path):
    module = load('packaging/build_support.py')
    distribution = SimpleNamespace(files=[], locate_file=lambda file: tmp_path / file)
    monkeypatch.setattr(module.metadata, 'distribution', lambda name: distribution)
    with pytest.raises(RuntimeError, match='Missing upstream license'):
        module.license_datas(['pystray'])
    file = Path('pystray-0.19.5.dist-info/LICENSE.txt')
    (tmp_path / file).parent.mkdir()
    (tmp_path / file).write_text('LGPL-3.0')
    distribution.files = [file]
    result = module.license_datas(['pystray'])
    assert result[0][1].startswith('licenses/pystray/')


def test_linux_staging_preserves_symlinks_and_relocatable_apprun(tmp_path):
    module = load('scripts/package_linux.py')
    source = payload(tmp_path)
    system = tmp_path / 'system'
    module.stage_system(source, system)
    assert (system / 'opt/fixoflow/link').is_symlink()
    assert 'Exec=/opt/fixoflow/Fixoflow' in (system / 'usr/share/applications/fixoflow.desktop').read_text()
    appdir = tmp_path / 'appdir'
    module.stage_appdir(source, appdir)
    assert (appdir / '.DirIcon').is_symlink()
    script = (appdir / 'AppRun').read_text()
    assert 'exec "$APPDIR/usr/lib/fixoflow/Fixoflow" "$@"' in script
    assert str(ROOT) not in script
    if sys.platform != 'win32':
        assert (appdir / 'AppRun').stat().st_mode & 0o111
    assert 'Exec=Fixoflow' in (appdir / 'fixoflow.desktop').read_text()


def test_appimage_tool_cache_never_executes_unverified_bytes(tmp_path, monkeypatch):
    module = load('scripts/package_linux.py')
    (tmp_path / 'runtime').write_bytes(b'bad')
    monkeypatch.setattr(module.urllib.request, 'urlopen', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('network unavailable')))
    with pytest.raises(RuntimeError, match='network unavailable'):
        module.verified_tool('runtime', tmp_path)
    assert not (tmp_path / 'runtime.download').exists()
    content = b'valid tool'
    monkeypatch.setitem(module.APPIMAGE_TOOLS, 'runtime', ('https://example.invalid/tool', len(content), hashlib.sha256(content).hexdigest()))
    (tmp_path / 'runtime').write_bytes(content)
    assert module.verified_tool('runtime', tmp_path) == tmp_path / 'runtime'


def test_rpm_uses_native_builder_and_disables_binary_rewriting(tmp_path, monkeypatch):
    module = load('scripts/package_linux.py')
    source = payload(tmp_path)
    stage = tmp_path / 'rpm'
    stage.mkdir()
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        if command[0] == 'rpmbuild':
            file = stage / 'RPMS/x86_64/fixoflow.rpm'
            file.parent.mkdir()
            file.write_bytes(b'rpm')
    monkeypatch.setattr(module.subprocess, 'run', run)
    monkeypatch.setattr(module.subprocess, 'check_output', lambda *a, **k: 'RPM version test\n')
    output = tmp_path / 'output.rpm'
    module.build_rpm(source, output, stage)
    assert output.read_bytes() == b'rpm'
    assert '__os_install_post %{nil}' in calls[0]
    assert calls[-1][:3] == ['rpm', '-K', '--nosignature']
    spec = (stage / 'SPECS/fixoflow.spec').read_text()
    assert 'libayatana-appindicator-gtk3' in spec
    assert '/opt/fixoflow' in spec


def test_native_report_parser_ignores_non_json_logs():
    module = load('scripts/check_native_preview.py')
    assert module.json_lines('log\n{"ui":"ok"}\n[]\nnot json') == [{'ui': 'ok'}]


def test_installed_check_requires_real_tray_completion(tmp_path, monkeypatch):
    module = load('scripts/check_native_preview.py')
    report = tmp_path / 'report.json'
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        report.write_text(json.dumps({'ui': 'ok', 'local_inference': 'executed', 'version': module.VERSION, 'tray_backend': 'ready'}))
    monkeypatch.setattr(module.subprocess, 'run', run)
    module.run_check(tmp_path / 'Fixoflow', report, {}, tmp_path)
    assert '--tray-check' in calls[0]
    def failed_tray(command, **kwargs):
        report.write_text(json.dumps({'ui': 'ok', 'local_inference': 'executed', 'version': module.VERSION, 'tray_backend': 'unavailable'}))
    monkeypatch.setattr(module.subprocess, 'run', failed_tray)
    with pytest.raises(AssertionError):
        module.run_check(tmp_path / 'Fixoflow', report, {}, tmp_path)


def test_frozen_backend_diagnostic_uses_explicit_wav_and_no_saved_config(tmp_path, monkeypatch):
    from fixoflow.config import FixoflowConfig
    import fixoflow.stt.engine as stt
    module = load('packaging/entry.py')
    audio = tmp_path / 'public-fixture.wav'
    with wave.open(str(audio), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        output.writeframes(b'\0\0' * 160)
    monkeypatch.setattr(FixoflowConfig, 'load', lambda: pytest.fail('Read saved preferences'))
    configs = []
    class DiagnosticEngine:
        def transcribe(self, samples):
            assert len(samples) == 160
            return 'habla pública'
    def create(config):
        configs.append(config)
        return DiagnosticEngine()
    monkeypatch.setattr(stt, 'create_stt_engine', create)
    report = module.diagnostic_inference({'FIXOFLOW_DIAGNOSTIC_MODEL': 'catalog:parakeet-v3-onnx',
        'FIXOFLOW_DIAGNOSTIC_LANGUAGE': 'auto', 'FIXOFLOW_DIAGNOSTIC_WAV': str(audio)})
    assert configs[0].model_name == 'catalog:parakeet-v3-onnx' and configs[0].language is None
    assert report['text'] == 'habla pública' and report['backend'].endswith('.DiagnosticEngine')
    assert report['inference_input']['sha256'] == hashlib.sha256(audio.read_bytes()).hexdigest()
    assert report['inference_input']['kind'] == 'explicit_wav'
    with pytest.raises(ValueError, match='absolute path'):
        module.diagnostic_inference({'FIXOFLOW_DIAGNOSTIC_WAV': 'relative.wav'})
    with pytest.raises(ValueError, match='installed catalog'):
        module.diagnostic_inference({'FIXOFLOW_DIAGNOSTIC_MODEL': '/arbitrary/model'})


def test_workflow_requires_native_installed_checks_and_no_public_release():
    text = (ROOT / '.github/workflows/desktop-preview.yml').read_text()
    assert 'macos-15-intel' in text and 'arch: x86_64' in text
    assert '--dmg dist/Fixoflow.dmg' in text
    assert '--executable /opt/fixoflow/Fixoflow' in text
    assert '--format rpm' in text and '--format appimage' in text
    assert 'APPIMAGE_EXTRACT_AND_RUN' in text
    assert 'runuser -u preview' in text
    assert 'WEBKIT_DISABLE_SANDBOX' not in text
    assert 'gh release' not in text
    assert 'gir1.2-ayatanaappindicator3-0.1' in text
    assert 'image: registry.fedoraproject.org/fedora@sha256:' in text
