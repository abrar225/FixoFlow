"""Build an amd64 Debian package on Ubuntu 24.04 (X11)."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
from fixoflow.version import __version__
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='fixoflow-deb-') as temporary:
    stage=Path(temporary);application=stage/'opt/fixoflow'
    shutil.copytree(root/'dist/Fixoflow',application,symlinks=True)
    control=stage/'DEBIAN';control.mkdir()
    size=sum(p.stat().st_size for p in application.rglob('*') if p.is_file())//1024
    (control/'control').write_text(f'''Package: fixoflow
Version: {__version__}
Architecture: amd64
Maintainer: Fixo Flow <noreply@fixoflow.local>
Section: sound
Priority: optional
Installed-Size: {size}
Depends: libwebkit2gtk-4.1-0, gir1.2-webkit2-4.1, libgtk-3-0, libportaudio2, xclip, libnotify-bin, libx11-6, libxtst6
Description: Local voice dictation for the Linux X11 desktop
 English speech recognition, personal dictionary and local history.
 Global shortcuts and automatic insertion require X11. No GPU required.
''')
    entry=stage/'usr/share/applications/fixoflow.desktop';entry.parent.mkdir(parents=True)
    entry.write_text('''[Desktop Entry]
Name=Fixo Flow
Comment=Local voice dictation
Exec=/opt/fixoflow/Fixoflow
Icon=fixoflow
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Accessibility;
StartupWMClass=Fixo Flow
''')
    icon=stage/'usr/share/icons/hicolor/256x256/apps/fixoflow.png';icon.parent.mkdir(parents=True)
    shutil.copy2(root/'fixoflow/ui/assets/flow-fold.png',icon)
    subprocess.run(['dpkg-deb','--root-owner-group','-Zxz','--build',str(stage),str(root/f'dist/Fixoflow-{__version__}-linux-x64.deb')],check=True)
