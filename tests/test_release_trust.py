"""Release checks reject missing/stale evidence without touching staged downloads."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_artifact', ROOT / 'scripts/verify_public_artifact.py')
trust = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trust)


def test_report_must_match_exact_bytes_and_complete_checks(tmp_path):
    artifact = tmp_path / 'installer.exe'
    artifact.write_bytes(b'first release')
    report = {'platform': 'windows', 'sha256': trust.digest(artifact),
              'verified_at': datetime.now(timezone.utc).isoformat(),
              'checks': {'authenticode': True, 'timestamp': True}}
    evidence = tmp_path / 'windows-trust.json'
    evidence.write_text(json.dumps(report))
    assert trust.require_report(artifact, 'windows', tmp_path) == report
    artifact.write_bytes(b'modified release')
    with pytest.raises(ValueError, match='mismatched'):
        trust.require_report(artifact, 'windows', tmp_path)
    report['sha256'] = trust.digest(artifact)
    report['checks']['timestamp'] = False
    evidence.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='Missing'):
        trust.require_report(artifact, 'windows', tmp_path)
    report['checks']['timestamp'] = True
    report['verified_at'] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    evidence.write_text(json.dumps(report))
    with pytest.raises(ValueError, match='Expired'):
        trust.require_report(artifact, 'windows', tmp_path)


def test_unsigned_staging_gate_fails_before_site_mutation(tmp_path):
    # Native reports are deliberately absent. This must fail before staging.
    (tmp_path / 'Fixoflow.dmg').write_bytes(b'not signed')
    manifest = ROOT / 'Landing_Page/lib/releases.generated.json'
    before = manifest.read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/stage_website_downloads.py'),
                             '--artifacts', str(tmp_path), '--require-public-trust',
                             '--trust-reports', str(tmp_path / 'missing-reports')],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'macos-trust.json' in result.stderr
    assert manifest.read_bytes() == before


def test_authenticode_needs_native_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(trust.sys, 'platform', 'darwin')
    with pytest.raises(ValueError, match='must run on Windows'):
        trust.verify_windows(tmp_path / 'installer.exe', '0' * 40)
