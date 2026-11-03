# Distribution parity implementation (preview)

The distribution pipeline now has native architecture-specific Mac builds and
three actual Linux package builders. These are preview artifacts; this change
does not publish a release, change the website, enable unsigned updates, or claim
Apple Developer ID/notarization approval.

## Native macOS

`packaging/Fixoflow.spec`, `packaging/entry.py` and `scripts/build_app.sh` select
MLX on arm64 and CTranslate2/faster-whisper CPU on x86_64. A mismatched requested
architecture/Python interpreter fails before freezing; no cross compilation or
Rosetta benchmark is represented as native Intel support. ONNX/Parakeet is
excluded on Intel because the model catalog does not support that backend there.
The existing AppKit UI and menu remain native on both architectures.

For Intel, first explicitly stage the pinned CPU model:

```sh
.venv/bin/python scripts/prepare_cpu_model.py --output build/bundled-model-x86_64
bash scripts/build_app.sh
bash scripts/build_dmg.sh
```

The build itself requires verified offline weights. The CPU preparation tool
validates every expected byte count plus SHA256 for the LFS weights and Git blob
identities for the repository text/tokenizer files, then records SHA256 for all
files. Existing model files are reused only after verification. Partial downloads
and validation failures do not promote a new staged model.

The workflow uses `macos-15-intel` and an x64 Python3.12 interpreter for Intel,
and `macos-15` with arm64 Python for Apple Silicon. These runner names and
architectures were checked against the [official GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
Each job builds the app and actual DMG, mounts it read-only, copies its app to a
temporary Applications directory, verifies Mach-O architecture, signature,
version and embedded source commit, then runs frozen dependency/import checks,
shared recognizer inference and AppKit self-check from an empty working directory
with disposable HOME/XDG paths. The inference input is a synthetic tone used only
to detect broken bundled execution; it measures no recognition quality.

For additional frozen backend checks, `--packaging-check --inference` accepts
diagnostic-only environment overrides: `FIXOFLOW_DIAGNOSTIC_MODEL=catalog:<id>`,
`FIXOFLOW_DIAGNOSTIC_LANGUAGE=es` (or `auto`) and
`FIXOFLOW_DIAGNOSTIC_WAV=/absolute/public-fixture.wav`. The WAV must be PCM16,
mono,16kHz and at most ten minutes. This constructs a fresh in-memory config,
uses an already provisioned offline catalog model, and returns the actual engine
class, model, language, transcript and fixture SHA256. It neither loads/saves
user preferences nor implicitly downloads a model. Stage diagnostic catalog
artifacts into a disposable HOME before execution, preserving the manager's
manifest/hash checks; normal application startup ignores these overrides.

## Linux package formats

`scripts/package_linux.py --format deb|rpm|appimage` requires a native x86_64
Linux frozen ELF payload with embedded source provenance. All outputs get
version, architecture, byte count, SHA256, source commit/source-manifest digest
and builder/tool evidence sidecars.

- **DEB:** native `dpkg-deb`, explicit Ubuntu24.04 X11 dependencies, application
  under `/opt/fixoflow`, desktop entry and icon. CI installs the resulting DEB
  through apt and checks its installed executable, UI and bundled inference.
- **RPM:** native `rpmbuild` inside a digest-pinned Fedora43 image. Explicit
  Fedora dependencies include WebKitGTK4.1, GTK3, Ayatana AppIndicator, PortAudio
  and X11 tools. RPM post-processing cannot rewrite PyInstaller's executable
  archive. CI installs through dnf, checks package integrity with `rpm -V`, and
  executes installed UI/inference as an unprivileged desktop user under Xvfb and
  a D-Bus session. This is a Fedora build, not an Ubuntu-built RPM with assumed
  compatibility.
- **AppImage:** a relocatable AppDir/AppRun, desktop file and icon, produced by
  appimagetool1.9.1. The tool and independently supplied type2 runtime both have
  fixed expected sizes and SHA256 hashes; the runtime uses immutable GitHub
  asset ID657374641, not a mutable continuous download URL. Both downloads were
  actually fetched and verified on this development host. CI validates the
  desktop entry, then executes the resulting AppImage runtime using
  `APPIMAGE_EXTRACT_AND_RUN=1`, so FUSE is not required. It independently extracts
  the image to check embedded source provenance. The runtime's upstream notice
  and exact source/build references are included in the AppDir.

This AppImage intentionally depends on host WebKitGTK4.1/GTK3/Ayatana/PortAudio
and targets the Ubuntu24.04 baseline. It is **not** a universal, dependency-free
Linux binary. Global shortcuts and insertion require X11. Wayland and desktop
tray visibility require separate desktop qualification; a packaged AppIndicator
backend alone does not prove a visible tray host.

## Windows and bundled dependencies

The existing Windows setup build/install checks remain. Desktop freezes now
include source provenance, ONNX preprocessing data/runtime and explicit native
pystray backends (`_win32`, `_appindicator`, `_gtk`) with Pillow. Mac builds use
AppKit and exclude pystray. Dependency license notices are copied without
importing GUI backends; required absent notices fail the build. Because the
mlx-whisper0.4.3 wheel lacks its upstream notice, a pinned upstream MIT notice is
retained under `packaging/licenses`.

Windows/Linux frozen and installed/extracted checks request `--tray-check` and
require a `tray_backend: ready` completion report. This initializes the native
backend and exercises menu construction/refresh/teardown; it does not establish
that a desktop shell visibly displays an indicator. Linux tray checks run in a
D-Bus session. Separate native clipboard tests run only under a newly created
Xvfb display with `FIXOFLOW_TEST_X11_ISOLATED=1`, never a user's existing display.

## Verification observed locally

- `tests/test_packaging_parity.py` and `tests/test_release_trust.py`:16 passed.
  The spec tests execute both architecture branches using controlled build-hook
  doubles; native execution is tested separately by CI, not inferred from them.
- Python compilation and both Mac shell scripts' syntax checks passed.
- Workflow YAML parsed with four jobs (Windows, Ubuntu, Mac architecture matrix,
  Fedora RPM).
- appimagetool:15,092,216bytes, SHA256
  `ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0`.
- type2 runtime:944,632bytes, SHA256
  `617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46`;
  source `fedfad51acc2860b2916a1eef32ba4a500ff31ef`.
- The CPU model's four text/tokenizer assets were fetched at the pinned revision
  and their expected identities/sizes verified. The full145MB CPU weight artifact
  has a pinned upstream LFS SHA256 and is verified when staged by native CI.

At this point these local checks establish the build policy and provenance
mechanisms, not native Intel/Fedora/Ubuntu runtime success. Record actual native
workflow runs and any resulting fixes below before calling those platforms
validated. Public signing, notarization, physical microphone/TCC interaction,
Wayland insertion and broad distro/desktop testing remain outside these smoke
checks.
