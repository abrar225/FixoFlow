# Build from scripts/build_app.sh; do not invoke against an unprepared model.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

root = Path(SPECPATH).parent
model = Path(os.environ["FIXOFLOW_BUILD_MODEL_DIR"])
a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root)],
    binaries=collect_dynamic_libs("mlx"),
    datas=[(str(root / "fixoflow" / "ui" / "hub.html"), "fixoflow/ui"),
           (str(root / "fixoflow" / "ui" / "overlay.html"), "fixoflow/ui"),
           (str(model), "models/whisper")]
          + collect_data_files("mlx_whisper") + collect_data_files("mlx"),
    hiddenimports=["AppKit", "Foundation", "WebKit", "ApplicationServices", "Quartz",
                   "AVFoundation", "UserNotifications",
                   "pynput.keyboard._darwin", "pynput.mouse._darwin"]
                  + collect_submodules("tiktoken_ext") + collect_submodules("mlx")
                  + collect_submodules("scipy._external.array_api_compat"),
    runtime_hooks=[str(root / "packaging" / "offline_hook.py")],
    excludes=["pytest", "tkinter", "matplotlib", "torch", "transformers"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Fixoflow", console=False,
          target_arch="arm64", codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Fixoflow")
app = BUNDLE(coll, name="Fixoflow.app", icon=str(root / "resources" / "AppIcon.icns"),
             bundle_identifier="com.fixoflow.app", version="0.2.0",
             info_plist={"CFBundleDisplayName": "Fixoflow", "LSMinimumSystemVersion": "14.0",
                         "NSHighResolutionCapable": True, "LSUIElement": False,
                         "NSMicrophoneUsageDescription": "Record speech locally for dictation.",
                         "NSAccessibilityUsageDescription": "Insert dictated text into the application you choose.",
                         "NSInputMonitoringUsageDescription": "Respond to your global dictation shortcut."})
