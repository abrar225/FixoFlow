import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files,collect_dynamic_libs,collect_submodules
root=Path(SPECPATH).parent
model=Path(os.environ['FIXOFLOW_BUILD_MODEL_DIR'])
windows=sys.platform=='win32'
a=Analysis([str(root/'packaging/desktop_entry.py')],pathex=[str(root)],
    datas=[(str(root/'LICENSE'),'licenses/fixoflow'),(str(model),'models/whisper')]+collect_data_files('fixoflow.ui',includes=['*.html','*.css','assets/*'])+collect_data_files('webview')+collect_data_files('faster_whisper'),
    binaries=collect_dynamic_libs('ctranslate2')+collect_dynamic_libs('av'),
    hiddenimports=collect_submodules('scipy._external.array_api_compat')+(['webview.platforms.edgechromium','webview.platforms.winforms','pynput.keyboard._win32','pynput.mouse._win32'] if windows else ['webview.platforms.gtk','pynput.keyboard._xorg','pynput.mouse._xorg','gi.repository.WebKit2','gi.repository.Gtk','gi.repository.Soup']),
    excludes=['onnxruntime','mlx','mlx_whisper','torch','transformers','pytest','tkinter','matplotlib','PyQt5','PyQt6','PySide2','PySide6','webview.platforms.cef','webview.platforms.qt','webview.platforms.cocoa'],
    runtime_hooks=[str(root/'packaging/offline_hook.py')])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Fixoflow',console=False,
        icon=str(root/'fixoflow/ui/assets/flow-fold.ico') if windows else None)
coll=COLLECT(exe,a.binaries,a.datas,name='Fixoflow')
