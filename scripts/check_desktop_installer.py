"""Install and inspect this CI-built Windows package in an isolated target folder."""
from pathlib import Path
import json
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
    empty=directory/'empty';empty.mkdir()
    subprocess.run([str(executable),'--self-check','--check-report',str(report)],cwd=empty,check=True,timeout=120)
    result=json.loads(report.read_text());assert result['ui']=='ok' and result['local_inference']=='executed' and result['version']==__version__,result
    print(json.dumps({'installed_package':'ok','version':__version__,'bundled_inference':'executed','empty_working_directory':True}))
    # Inno uninstall owns cleanup of its installed files; user data is not purged.
    subprocess.run([str(application/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],check=True,timeout=60)
