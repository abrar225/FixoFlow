# Fixo Flow 0.2.0: installation, platform packages and release gates

This is the current release-preparation runbook. The earlier 0.1.0 plan remains
an historical implementation record, not the current platform status.

## Priority and ownership

The implementation role is desktop/platform engineer and release engineer;
performance and publication claims must match executed checks.

1. Inventory installed copies and generated installers; preserve user data.
2. Remove verified obsolete artifacts, verify the replacement and install Mac.
3. Separate shared dictation/UI contracts from native platform dependencies.
4. Implement Windows x64 and Linux X11 adapters, then build on those native OSes.
5. Verify frozen decoding, native UI and installer execution before staging files.
6. Reduce footprint without silently changing the speech model or recognition rules.
7. Stage one download per platform, publish accurate requirements and preview status.
8. Remove retired source/assets and run regression, website and packaging checks.
9. Complete signing and physical-device acceptance before a stable public launch.

## What is implemented

- Cocoa host for Apple Silicon/macOS 14+, regular Dock activation and Flow Fold.
- Windows host using the system WebView2 engine; per-user Inno Setup installer.
- Linux GTK/WebKit host and Ubuntu 24.04 amd64 Debian package, targeting X11.
- One HTML/CSS design and action controller, dictionary, history, formatting,
  recording/persistence pipeline and independent shortcut/session router.
- Windows low-level keyboard/mouse filtering with press/release ownership;
  X11 input monitoring; OS-specific application identities and clipboard/paste.
- Windows identity includes HWND, PID and process birth time. Linux identity
  includes XID, PID and `/proc` birth time; reused IDs do not inherit a transcript.
- Clipboard/history fallback when automatic insertion cannot be performed.
- Mac MLX inference and Windows/Linux local CTranslate2 inference using Base
  English. CPU decoding uses float32, two threads by default, one worker and no
  optional neural VAD. The configured 1–4 thread budget changes CPU parallelism,
  not the speech model, beam size or formatting behavior.
- Native Windows/Linux preview workflows, portable contracts on three OSes,
  frozen UI/model checks and installed-package checks. Inspect the Actions run
  and its logs for executed results; a workflow definition alone is not evidence.
- Native decoder dependencies are loaded lazily. CPU bundles omit ONNX Runtime,
  which is used only by the optional neural VAD that this app does not enable.
- One version in `fixoflow/version.py`, currently 0.2.0 / build 2000. Use 0.2.1
  for a subsequent patch and 0.3.0 for the next feature release. Never replace a
  published artifact under an existing tag/version.

## Straight answer about size and low-end computers

**Yes: lossless packaging, avoiding unused runtimes and lazy loading can reduce
footprint while retaining the app's features and speech model. No: identical
accuracy, speed and very low RAM on every low-end computer cannot be guaranteed.**

The previous Mac DMG was approximately 309 MiB; LZMA DMG compression reduced it to
approximately 228 MiB. This changes download size, not installed model size or
inference memory. The Base English model weights are byte-identical to the
previous build. The installed Mac app remains approximately 598 MiB.

A fresh-launch snapshot on this Mac measured the main app process at about
242 MiB RSS before lazy inference imports and 214 MiB afterward. These are
individual observations, not peak-memory or universal benchmarks. CPU time at
the snapshots was 1.90 s and 1.48 s respectively. WebKit processes managed by the
OS were not reliably attributable and are excluded. Cold/warm dictation latency,
process-family peak memory and low-end hardware performance remain unmeasured.

Keeping local speech recognition means storing/loading model weights and doing
CPU/GPU work. A smaller/quantized model may improve size or latency, but could
change the transcript. This release does not silently substitute a smaller
model. CPU backends use a different implementation from MLX; broad accuracy
parity requires a shared speech corpus, accents/noise/long-session testing and
word-error measurements. Executing synthetic inference does not establish this.

Two CPU threads leave more capacity for other programs but may increase
transcription latency. Audio persists during capture using a bounded pending
queue. Final processing currently loads the recorded audio into memory; very
long recordings can therefore use more RAM. There is no hard promise of a
sub-300-MiB total process footprint during transcription.

For Windows/Linux acceptance, start with a dual-core x64 CPU and 8 GB system RAM
as a test target, no dedicated GPU. Validate 4 GB machines separately before
advertising a minimum. This is a proposed test target, not a measured hardware
requirement or a guarantee of real-time operation.

## Supported scope and known differences

- **Mac:** Apple Silicon, macOS 14+. Locally signed and not notarized here.
- **Windows:** x64 preview for Windows 11. Windows 10 22H2 is a compatibility
  target; its OS support lifecycle is separate from this app. WebView2 and the
  Microsoft Visual C++ runtime must be available. Windows Server CI is not a
  substitute for testing Windows 11/10 desktop machines. No administrator
  privileges are required by the app; Windows UIPI can block insertion into an
  elevated application. In that case use the copied transcript/history.
- **Linux:** Ubuntu 24.04 x64 X11 preview. System GTK/WebKit/PortAudio/X11/clipboard
  dependencies are declared by the Debian package. Other distributions and ARM
  are unverified. X11 monitoring does not suppress every shortcut key; prefer
  modifier combinations to standalone typing keys. The first overlay uses the
  primary screen; multi-monitor/DPI acceptance is pending.
- **Wayland:** automatic paste and unrestricted global shortcut recording are
  not supported by the current adapter. Manual controls can retain output in
  history/clipboard when `wl-copy` is installed. Full support needs compositor
  portal integration, not root privileges or a claim that XWayland is equivalent.
- Fn/media keys depend on firmware, OS and drivers. The Windows OS may never
  expose a laptop Fn key. Test mice/keyboard layouts and reserved shortcuts.
- The Windows/Linux floating bar shares state animations and live audio levels,
  but Mac-specific backdrop blur and multi-monitor geometry are not duplicated.
- Mac has the optional Sparkle adapter; signed automatic update feeds remain
  unconfigured. Windows/Linux currently check public release metadata and link
  to releases; they do not implement unattended signed installation. Never
  enable an automatic-update checkbox without a working signed update path.

## Reproducible build and download staging

Use Python 3.12 x64 and clean build environments. Models are fetched only during
controlled build provisioning, not during runtime transcription. The CPU model
is pinned to `Systran/faster-whisper-base.en` revision
`3d3d5dee26484f91867d81cb899cfcf72b96be6c`; its build manifest records file digests.
The checked-in script downloads only the explicit model files and README.

Mac (from the project root):

```sh
bash scripts/build_app.sh
bash scripts/build_dmg.sh
```

Windows, on a native x64 build machine:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[windows,packaging,dev]"
.\.venv\Scripts\python scripts/prepare_cpu_model.py --output build/model
$env:FIXOFLOW_BUILD_MODEL_DIR = (Resolve-Path build/model).Path
.\.venv\Scripts\python -m PyInstaller --noconfirm --clean packaging/Desktop.spec
$version = .\.venv\Scripts\python -c "from fixoflow.version import __version__; print(__version__)"
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" "/DAppVersion=$version" packaging/windows.iss
.\.venv\Scripts\python scripts/check_desktop_installer.py
```

Linux: follow the Ubuntu dependency and virtual-environment commands in
`.github/workflows/desktop-preview.yml`. Build with `Desktop.spec`, then run
`python scripts/package_linux.py`. Native GUI smoke checks require a desktop or
Xvfb plus a window manager. A self-check never opens the microphone or activates
global input listeners; it resolves the bundled model, executes local synthetic
inference and checks the shared UI.

After downloading the successful native artifacts into `dist/`, stage the site:

```sh
python3 scripts/stage_website_downloads.py
cd Landing_Page
npm ci
npm run lint
npm run build
npm run audit:copy
```

Files are named `Fixoflow-0.2.0-macos-arm64.dmg`,
`Fixoflow-0.2.0-windows-x64-setup.exe` and `Fixoflow-0.2.0-linux-x64.deb` in the
website's generated downloads directory. Missing artifacts produce unavailable
choices, never broken/fabricated download links. The Mac manifest binds version
to the exact DMG digest; staging verifies all file formats and copied digests.
The website build includes the generated release manifest and must be deployed
with the complete `out/` directory and installer files. Installers/build outputs
are excluded from Git. Do not deploy a website bundle whose manifest references
an installer that was not uploaded.

## Before a stable public launch

1. Test real microphone capture, speech quality, input layouts/IME, Fn/media and
   mouse buttons, standby/device changes, foreground insertion and clipboard
   fallback on Windows 11, the declared Windows 10 target and Ubuntu X11.
2. Test quiet/low-resource machines, cold/warm latency and process-family peak
   RAM/CPU. Publish measured requirements rather than aspirational minimums.
3. Verify clean installs without Python/build tools and with missing runtime
   prerequisites. Test uninstall, upgrading a prior version, user-data retention,
   corrupt/tampered packages and interrupted updates.
4. Apply Developer ID/notarization on Mac and Authenticode on Windows. Configure
   signed Sparkle updates; choose and implement a signed Windows/Linux updater.
5. Review the release diff and validation record. Publish immutable GitHub
   release assets/tags, update feeds and the complete website export together.
   This task's preparation branch and Actions artifacts are not a public release
   or a production deployment.

Primary references: [pywebview](https://pywebview.flowrl.com/api/),
[pynput limitations](https://pynput.readthedocs.io/en/latest/limitations.html),
[CTranslate2 precision](https://opennmt.net/CTranslate2/quantization.html),
[Windows 10 lifecycle](https://learn.microsoft.com/en-us/windows/release-health/status-windows-10-22h2),
[Sparkle](https://sparkle-project.github.io/documentation/).

## Executed verification and cleanup record — 18 October 2026

- Local regression suite: **144 passed, 2 skipped** (Windows/Linux-only checks).
- Native Windows runner: **98 passed, 1 skipped**; native Ubuntu runner:
  **98 passed, 1 skipped**. Both frozen UI/bundled-model checks and installed
  package checks passed, including local synthetic inference. The Windows
  installer was installed to an isolated directory and launched from an empty
  working directory; Ubuntu installed the Debian package through its package
  manager. No real microphone or global input was activated by self-checks.
- Native package evidence: [successful Actions run](https://github.com/abrar225/FixoFlow/actions/runs/39129542514),
  source commit `be1bb7d57a8a765485853d454e694ee2388774d8`. Later website/docs
  and Mac diagnostic changes do not alter those Windows/Linux runtime sources.
- Final Mac build: shared-engine inference, UI/model self-check and isolated
  Cocoa/WKWebView integration passed. Read-only DMG inspection verified the
  version/build, strict code signature, Flow Fold icon, UI/font assets, unchanged
  model weights and equality with the installed executable. Image checksum passed.
- Fixo Flow 0.2.0 / build 2000 was installed in `/Applications/Fixoflow.app`,
  launched through the native application surface, and showed Ready to dictate
  with the user's existing two shortcuts and all three Mac permissions allowed.
  Config/history digests were preserved during replacement.
- Website typecheck, static export and copy/link audit passed: **19 required
  files and 102 exported links**. All three exported installers matched their
  manifest digests and returned HTTP 200 with exact Content-Length values.
  Mac/Windows/Linux selection and their distinct guidance/download URLs were
  verified in the browser. The site was prepared locally, not deployed publicly.
- Final installer sizes: macOS 228.85 MiB, Windows 199.53 MiB, Linux 253.3 MiB.
- Removed 27 obsolete build artifacts/backup links, approximately 11.27 GiB of file content, plus reproducible build caches. This is not a measurement of APFS physical space reclaimed.
- Removed retired static HTML/Astro implementations, alternate-logo comparison
  code/assets and 48 unused logo CSS rules; kept Flow Fold and required config
  migrations. Retired website sources were archived outside the project before
  removal. Superseded CI artifacts generated by this task were also removed; the
  final packages and workflow logs are retained. No releases were published.
- Inventory used accessible user/Application locations and Spotlight bundle/name
  queries. 543 protected locations could not be read; this is not a forensic
  assertion that every other user's/protected location is free of old copies.
  The similarly named WebKit directory is user data/cache, not an app bundle,
  and was retained. Only current build and installed app copies remain in the
  verified inventory.
- Still unverified: Windows 11/10 physical-device audio/input/insertion, low-end
  requirements, broad recognition parity, clean machines lacking prerequisites,
  complete Wayland controls, production signing and signed automatic upgrades.

VERDICT: PASS for the executed preparation checks; production launch gates remain.
