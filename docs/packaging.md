# Local Apple Silicon application builds

`Fixoflow.app` is a self-contained PyInstaller application, with a native Mach-O
launcher, embedded Python, native Cocoa/WebKit UI, PortAudio, MLX Metal libraries,
Whisper assets, and a local speech model. It does not invoke a project virtualenv
or depend on the checkout at runtime. A DMG is a drag-and-drop distribution image;
it is not an installer that grants microphone or Accessibility permission.

Build on Apple Silicon macOS using the project environment:

```sh
uv pip install --python .venv/bin/python -e '.[packaging]'
# Regenerate the macOS icon from the approved local Flow Fold PNG:
.venv/bin/python scripts/make_icon.py
bash scripts/build_app.sh
bash scripts/build_dmg.sh
```

No script installs or upgrades Python, Homebrew, or other system software. The
build scripts do not download models. By default they require the complete
`mlx-community/whisper-base.en-mlx` snapshot at revision
`aa0678c3466ed62c5c6114ec600a0e1f96820089` in the local Hugging Face cache. For a
separately obtained local compatible MLX Whisper model, set `FIXOFLOW_MODEL_DIR`
to its directory. Its config, weight file, source README/license if present, and a
SHA-256 manifest are copied into the bundle. A caller-supplied model's identity
is recorded as local rather than incorrectly attributed to the default snapshot.
Model and dependency licensing must be reviewed before public distribution.

The frozen runtime sets `HF_HUB_OFFLINE=1` and points the engine to its bundled
model; a missing model should produce an actionable error instead of a download.
The bundle contains local tokenizer and mel-filter assets. Array transcription
does not need an external ffmpeg executable; importing arbitrary compressed audio
files through mlx-whisper's own filename API would require ffmpeg and is not a
supported packaged workflow.

Build products are in `dist/`. Existing app/DMG products are retained in `dist/.previous-builds/` before
replacement; app backups use a non-app extension to avoid extra launchable copies. The scripts never overwrite `/Applications/Fixoflow.app`. DMG staging
copies are unregistered from Launch Services and removed after the image is
created, so only one bundle with `com.fixoflow.app` stays visible to the system.

Run `scripts/create_signing_cert.sh` once to install a self-signed **"Fixoflow
Local Signing"** code-signing identity in the login keychain; `build_app.sh`
then signs with it automatically (`FIXOFLOW_SIGN_IDENTITY` overrides). This
keeps the designated requirement certificate-anchored
(`certificate root = H"…"` instead of `cdhash H"…"`), so macOS permission
grants survive rebuilds. Without the identity, builds fall back to ad-hoc
signing and every update resets Accessibility / Input Monitoring / Microphone
grants. Builds are **not Developer ID signed or notarized**, and no claim of
Gatekeeper approval is made. Entitlements and a Developer ID/notarization
pipeline are future distribution work.

Validate the actual final bundle before copying it to Applications:

```sh
codesign --verify --deep --strict dist/Fixoflow.app
hdiutil verify dist/Fixoflow.dmg
# Run the app's diagnostic entry point without recording or inserting text:
dist/Fixoflow.app/Contents/MacOS/Fixoflow --packaging-check
dist/Fixoflow.app/Contents/MacOS/Fixoflow --self-check
# Optional real GPU inference using generated silence, without recording:
dist/Fixoflow.app/Contents/MacOS/Fixoflow --packaging-check --inference
```

Repeat diagnostics from a copied app in a temporary directory outside the source
checkout, with an empty working directory and sanitized environment. UI launch,
microphone, hotkey permissions, recording, insertion, recognition accuracy, and
peak memory are separate acceptance checks: a passing package diagnostic does
not establish those outcomes or the requested 200 MB memory ceiling.

## Product interface assets

The frozen app bundles `hub.html`, `hub.css`, `overlay.html`, and the complete
`fixoflow/ui/assets/` directory, including Flow Fold, Geist Sans, and font/icon
licenses. Setuptools includes these resources too. Neither build nor runtime
reads the landing-page directory. See [product interface](04-ui-ux-brief.md) for
the visual system and the recorded checks.

Run `.venv/bin/python scripts/check_product_ui.py` for an isolated native
Cocoa/WebKit integration check. `--preview` opens a temporary-database design
preview; it does not connect to the running dictation daemon or write user
preferences. The ordinary packaged application connects to the real engine.

## Versioned releases and optional updater

`fixoflow/version.py` supplies both the user-visible release and numeric build
number to the application bundle. `configure_updater.py` runs on the unsigned
staging app. With no updater inputs, only public GitHub release discovery is
enabled. With complete caller-provided Sparkle framework, HTTPS appcast, and
Ed25519 public-key inputs, it embeds the framework and public settings before
signing. It never generates or stores a private key or downloads a framework.
See [the release runbook](07-platform-and-release-plan.md) for public signing,
notarization, feed publication, real-upgrade acceptance, and Windows 11 x64.
