"""Install and inspect this CI-built Windows package in an isolated target folder."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
from fixoflow.version import __version__
root=Path(__file__).resolve().parents[1]
if sys.platform!='win32':raise SystemExit('Windows installer check must run on Windows')
installer=root/f'dist/Fixoflow-{__version__}-windows-x64-setup.exe'
with tempfile.TemporaryDirectory(prefix='fixoflow-install-check-') as temporary:
    directory=Path(temporary);application=directory/'Fixo Flow';report=directory/'installed-check.json'
    subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',f'/DIR={application}'],check=True,timeout=120)
    executable=application/'Fixoflow.exe';assert executable.is_file()
    provenance=json.loads((application/'_internal/release/source-manifest.json').read_text())
    if os.environ.get('GITHUB_SHA'):
        assert provenance['git_commit']==os.environ['GITHUB_SHA'],provenance['git_commit']
    empty=directory/'empty';empty.mkdir()
    subprocess.run([str(executable),'--self-check','--tray-check','--check-report',str(report)],cwd=empty,check=True,timeout=120)
    result=json.loads(report.read_text());assert result['ui']=='ok' and result['local_inference']=='executed' and result['version']==__version__,result
    assert result['tray_backend']=='ready',result
    evidence={'installed_package':'ok','version':__version__,'ui':result['ui'],'tray_backend':result['tray_backend'],'bundled_inference':'executed','empty_working_directory':True,'source_commit':provenance['git_commit']}
    output=root/'build/installed-windows-check.json';output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence))
    # Inno uninstall owns cleanup of its installed files; user data is not purged.
    subprocess.run([str(application/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=60)
