# Build from scripts/build_app.sh; do not invoke against an unprepared model.
import os
import runpy
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
support = runpy.run_path(str(root / "packaging/build_support.py"))
arch = support["mac_architecture"]()
if os.environ.get("FIXOFLOW_BUILD_ARCH", arch) != arch:
    raise RuntimeError("Use a native Python interpreter matching the requested Mac architecture")
mlx_backend = arch == "arm64"
backend_binaries = collect_dynamic_libs("mlx") if mlx_backend else collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("av")
backend_data = collect_data_files("mlx_whisper") + collect_data_files("mlx") if mlx_backend else collect_data_files("faster_whisper")
backend_imports = collect_submodules("mlx") if mlx_backend else ["faster_whisper", "ctranslate2", "av"]
if mlx_backend:
    backend_binaries += collect_dynamic_libs("onnxruntime")
    backend_data += collect_data_files("onnx_asr") + copy_metadata("onnx-asr")
    backend_imports += ["onnxruntime", "onnx_asr"]
model = Path(os.environ["FIXOFLOW_BUILD_MODEL_DIR"])
release = runpy.run_path(str(root / "fixoflow/version.py"))
a = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root)],
    binaries=backend_binaries,
    datas=[(str(root / "LICENSE"), "licenses/fixoflow"),
           (str(root / "build/source-manifest.json"), "release"),
           (str(root / "fixoflow" / "ui" / "hub.html"), "fixoflow/ui"),
           (str(root / "fixoflow" / "ui" / "hub.css"), "fixoflow/ui"),
           (str(root / "fixoflow" / "ui" / "overlay.html"), "fixoflow/ui"),
           (str(root / "fixoflow" / "ui" / "assets"), "fixoflow/ui/assets"),
           (str(model), "models/whisper")]
          + backend_data + support["license_datas"](["mlx-whisper", "mlx", "onnx-asr", "onnxruntime"] if mlx_backend else ["faster-whisper", "ctranslate2", "av"]),
    hiddenimports=["AppKit", "Foundation", "WebKit", "ApplicationServices", "Quartz",
                   "AVFoundation", "UserNotifications", "ServiceManagement",
                   "pynput.keyboard._darwin", "pynput.mouse._darwin"]
                  + (collect_submodules("tiktoken_ext") if mlx_backend else []) + backend_imports
                  + collect_submodules("scipy._external.array_api_compat"),
    runtime_hooks=[str(root / "packaging" / "offline_hook.py")],
    excludes=["pytest", "tkinter", "matplotlib", "torch", "transformers", "pystray"] + ([] if mlx_backend else ["mlx", "mlx_whisper", "onnxruntime", "onnx_asr"]),
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Fixoflow", console=False,
          target_arch=arch, codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, name="Fixoflow")
app = BUNDLE(coll, name="Fixoflow.app", icon=str(root / "resources" / "AppIcon.icns"),
             bundle_identifier="com.fixoflow.app", version=release["__version__"],
             info_plist={"CFBundleDisplayName": "Fixo Flow", "CFBundleName": "Fixo Flow", "CFBundleVersion": str(release["BUILD_NUMBER"]), "LSMinimumSystemVersion": "14.0",
                         "NSHighResolutionCapable": True, "LSUIElement": False,
                         "NSMicrophoneUsageDescription": "Record speech locally for dictation.",
                         "NSAccessibilityUsageDescription": "Insert dictated text into the application you choose.",
                         "NSInputMonitoringUsageDescription": "Respond to your global dictation shortcut."})
