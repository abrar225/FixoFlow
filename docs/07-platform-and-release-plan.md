> Historical 0.1.0 record. Current implementation, commands and platform status: [0.2.0 runbook](08-multiplatform-release.md).

# Shortcuts, Windows 11 x64, and product releases

This is the implementation and launch checklist for the product, not the landing
page. The selected first Windows target is **Windows 11 x64**.

## Task ownership and current scope

- **Product/input engineer:** two independent shortcuts, input capture, conflict
  handling, legacy preference migration, cancellation, and listener lifecycle.
- **macOS application engineer:** Dock activation and icon ownership, ordinary
  application/edit menus, and a reusable nonactivating floating control.
- **Product UX engineer:** preserve the approved visual system, show recent
  dictations on Overview, and explain each shortcut's behavior in Settings.
- **Release/security engineer:** one version source, startup release discovery,
  opt-out checks, a signed-updater adapter, and an explicit release runbook.
- **Windows platform engineer:** isolate portable contracts, prepare local CPU
  inference, define Windows adapters and packaging, and add portable CI.
- **Verification engineer:** regression tests, native WebKit integration,
  packaging diagnostics, and clearly identified unverified platform behavior.

The first four have Mac implementation in this checkout. Signed automatic
installation is conditional on supplying a real Sparkle framework, public key,
and hosted appcast. Windows shared-code preparation is implemented; a Windows
application binary has not been built or hardware-validated here. Publishing a
release, obtaining signing identities, and completing Windows acceptance are
external release steps, not facts established by the local checks.

## What was learned from Wispr Flow

Read-only UI observation of the installed version **1.6.1174** established:
separate Push to talk and Hands-free rows; modifier-only and middle-mouse
bindings; an explicit Change dialog; recent transcript activity on its main
Dictation page; and version/update status in Settings. No shortcuts, account
settings, histories, or recordings in Wispr were changed. Its private transcript
contents are not copied into this repository.

[Official shortcut documentation](https://docs.wisprflow.ai/articles/2612050838-supported-unsupported-keyboard-hotkey-shortcuts)
adds documented restrictions, release-to-save capture, conflicts, and mouse
support. This does **not** mean Wispr accepts every physical input or that all
of its published behavior was reproduced on this machine. Fixo Flow implements
its own interaction and retains its own offline dictation architecture.

REA manifest-only static inspection: Evidence
`ev_1a76b7192234bce8454a82cd8f8b778e19d061ab59cf0eb90e630cd0a11deee1`,
ASAR SHA-256 `dc56b610fb46d34dabf7871a270f307c665371de3f28b492c687eca2af09faf4`.
Only `package.json` was selected; 182 other inventoried files were outside source
analysis scope. Declared integrity contradicted observed companion native bytes;
`record-and-continue` retained these as untrusted. No native companion was
executed or decompiled. Internal implementation claims remain unknown. UI
observations and public documentation, not that manifest, establish the patterns
above. Proprietary code and assets are not redistributed.

## Shortcut behavior

`fixoflow/shortcuts.py` owns binding identity, conflict checks, capture, timeout,
and edge routing. `DictationControls` owns session ordering. The macOS adapter
owns keyboard/mouse event taps; the hub only displays selections and saves
preferences through the bridge. Nested Objective-C collections are converted to
ordinary JSON types once at the WebKit bridge entry.

- Hold-to-talk starts on press and finishes on release, including a very short
  press. There is no duration guess and no tap-to-toggle on this binding.
- Hands-free toggles on the press edge. Repeated keydown events and the release
  do not toggle again. The floating bar remains an independent toggle control.
- Defaults: Control + Space for hold, Option + Space for hands-free. Both can be
  changed to standalone letters, modifiers, combinations, Fn/Globe, or mouse
  buttons exposed by macOS. Right and left modifiers retain their identity.
- Capturing a binding never records audio. Keyboard choices commit on release;
  non-primary mouse choices commit on press. Escape, Cancel, losing focus, or a
  20-second timeout ends capture without changing the prior saved preference.
- Left/right mouse buttons can be selected by clicking their shortcut field
  while it is recording. They do not hijack ordinary clicks inside the hub.
  Outside the hub, a chosen primary button can replace its normal action, so
  prefer a side or middle button for everyday use.
- The two bindings cannot be identical or contain one another. Changing both
  fields is allowed before Save; the backend validates the final pair together.
- Reserved OS/hardware events and Secure Keyboard Entry can prevent delivery.
  Fixo Flow cannot override events macOS does not expose. Caps Lock is supported
  for hands-free; the Mac event stream does not expose an ordinary held Caps
  Lock release, so it is rejected for hold-to-talk rather than silently behaving
  as a tap. Escape alone cancels capture and is not recordable through the UI.
- Releasing an old held shortcut cannot finish a newer hands-free session.
  Stale listener generations cannot control a new configuration. Listener
  cleanup that has not completed retains ownership and is retried.

Old `hotkey` preferences migrate at load. A legacy toggle-only binding stays
hands-free; other legacy bindings become hold-to-talk, with a separate,
non-overlapping hands-free choice. The file is not rewritten until Save. Save
uses the existing atomic replacement and `.json.bak` backup. Old timing fields
are retired. CLI `--hotkey` remains an alias for `--hold-shortcut`.

## Dock and overview

The application alone sets `NSApplicationActivationPolicyRegular`; the daemon
no longer overrides it to Accessory. The approved Flow Fold asset is also set
explicitly as the application icon. The app has a main menu with Open, Settings,
Check for Updates, and Quit, plus standard Edit actions. The floating panel stays
nonactivating. A live main app therefore belongs in the Dock/app switcher even
when the floating panel is the visible control.

Overview shows the five most recent completed transcripts with date groups,
time, app, and Copy, plus a link to full searchable history. Both surfaces share
one renderer and use literal text, including HTML-like transcript content.

## Version policy

`fixoflow/version.py` is the single release identity. Python package metadata,
macOS bundle metadata, Settings, and release comparisons consume it.

The first public version is **0.1.0**, tag **v0.1.0**, numeric build **1000**.
The old 0.2.0 value was local prototype metadata; GitHub had no published
releases when inspected on 2026-10-18. There is no remote downgrade migration
being advertised.

- Bug fix: `0.1.1`, build 1001, tag `v0.1.1`.
- New compatible functionality: `0.2.0`, build 2000.
- A breaking public contract uses an appropriate major-version decision and
  migration notes; do not reuse a version for different binaries.
- Keep source in Git and tag the exact reviewed commit. Keep DMGs, EXEs, models,
  signing certificates, and private update keys out of Git.
- Record behavior changes, migration, verification, and known limits in release
  notes. Human review and public-release approval are separate from passing CI.

## Update behavior available now

At launch, when enabled, the app requests public release metadata from the exact
FixoFlow GitHub repository. This is a narrow network exception to local dictation:
no audio, transcript, account information, or configuration is sent. Checks run
in a bounded background worker with a timeout; repeat requests are coalesced.
A newer stable SemVer release produces an in-app banner and repository release
link. Missing releases, offline errors, and an already-current version have
separate messages. Users can disable startup checking and check manually.

This fallback does **not** execute a downloaded binary or replace a running app.
It links to the verified repository release page. There are currently no public
releases to deliver. Devices with update checks disabled or without a network
connection cannot be notified until they check again.

Automatic downloads/installation use [Sparkle 2](https://sparkle-project.github.io/documentation/),
which verifies update signatures and owns the install/relaunch lifecycle. The
Settings option stays disabled with a concrete explanation in the current local
build. A custom unsigned updater is not substituted. A real appcast and
signing setup must exist before calling this production automatic updating.

### Enable signed Mac updates

1. Obtain the official current Sparkle 2 binary distribution, review its license,
   and provision its `Sparkle.framework` and command-line tools outside the repo.
   Pin the chosen release and keep its checksum in the release environment.
2. Follow Sparkle's `generate_keys` instructions. Keep the Ed25519 private key
   in the release operator's Keychain or CI secrets. Put only its public key
   in build configuration. Keep the existing key for every subsequent release.
3. For public distribution, use an Apple Developer ID Application identity,
   hardened-runtime configuration and notarization. The existing local signing
   identity is for local builds; it does not establish public Gatekeeper trust.
4. Set these build inputs (values below are placeholders):

   ```sh
   export FIXOFLOW_SPARKLE_FRAMEWORK=/absolute/path/Sparkle.framework
   export FIXOFLOW_UPDATE_FEED_URL=https://github.com/abrar225/FixoFlow/releases/latest/download/appcast.xml
   export FIXOFLOW_UPDATE_PUBLIC_KEY=YOUR_BASE64_ED25519_PUBLIC_KEY
   export FIXOFLOW_SIGN_IDENTITY='Developer ID Application: YOUR NAME (TEAMID)'
   bash scripts/build_app.sh
   bash scripts/build_dmg.sh
   ```

   `configure_updater.py` requires the complete configuration, validates the
   HTTPS URL and public-key shape, verifies the supplied framework signature,
   copies it into the staging bundle, and sets the public Info.plist keys.
   The normal app signing step follows embedding. It downloads nothing.
5. Sign/notarize/staple and verify the final application and distribution using
   Apple's documented release process. Verify Sparkle's nested XPC services and
   helpers as part of that process. These distribution steps are not completed
   by the local self-signed build script.
6. Name immutable artifacts by version and architecture, e.g.
   `Fixoflow-0.1.1-macos-arm64.dmg`. Run Sparkle's `generate_appcast` over the
   release archive directory; use the tool's signing options for your key
   storage. Point generated enclosure URLs to immutable GitHub tag assets.
7. Create a **draft** GitHub release for the reviewed tag. Attach the final DMG,
   generated `appcast.xml`, and release notes. Check that the appcast signature,
   enclosure length, build number, and actual binary agree. Publish only after
   the human release owner approves it.
8. Install the previous public version in a clean test account and exercise a
   real signed upgrade. Test manual and automatic checks, auto-download on/off,
   relaunch, a tampered archive, an invalid signature, interrupted download,
   network failure, active dictation, rollback, and preference/data preservation.
   A framework import or a settings toggle alone does not verify this workflow.

Changing the binary version in Git does not notify clients. Clients discover a
new release only after the hosted metadata/feed is published and accessible.

## Windows 11 x64 implementation path

The `.dmg`, Cocoa/PyObjC UI, MLX model format, and Metal libraries cannot become a
Windows EXE by changing a packaging flag. Keep the shared product and create
separate platform adapters.

Preparation present in this checkout:

- Portable binding/capture/session and version/update contracts have no Cocoa
  imports. Platform dependencies are marked in `pyproject.toml`.
- `WindowsSTTEngine` implements the local CTranslate2/faster-whisper contract,
  sharing chunking, rolling prompts, and partial-text failure recovery. It uses
  a CPU/int8 baseline, one worker, at most four CPU threads, and explicit local
  files only. Its model object is reused within the engine instance.
- The Windows extra declares faster-whisper and pywebview. A Mac MLX weight file
  is rejected for this backend; use a separately provisioned complete CTranslate2
  model with `model.bin`, `config.json`, `tokenizer.json`, and
  `preprocessor_config.json`, with its license.
- The portable-core workflow targets macOS and Windows runners. Adding a workflow
  does not establish that a Windows job has executed or passed remotely.

On a Windows development machine, use Python 3.12 x64 in a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[windows,dev,packaging]"
.\.venv\Scripts\python -m pytest tests/test_config.py tests/test_controls.py tests/test_updates.py tests/test_windows_stt.py tests/test_learner_and_db.py tests/test_polisher.py tests/test_audio_filter.py tests/test_audio_slicer.py -q
```

These commands install and test the portable core; they do **not** launch the
current Mac-only `fixoflow.app` entry point. Complete these Windows work items:

1. **Application host:** a Windows-specific entry point; use pywebview's Edge
   Chromium/WebView2 backend for the existing local HTML and a JSON bridge.
   Allow only the app's local content to call native actions. Keep the Cocoa
   host on Mac. Add Windows single-instance/reopen, shutdown, tray and taskbar
   identity, a Flow Fold `.ico`, and app data/log/cache paths under LocalAppData.
2. **Input adapter:** Windows low-level keyboard/mouse events feed the same
   `ShortcutRouter`. Preserve left/right modifiers and XBUTTON1/2, ignore repeat,
   quarantine capture releases, respect reserved Windows keys, and keep listener
   cleanup retryable. Do not import the Darwin daemon from this entry point.
3. **Foreground and insertion:** identify the original HWND/process at start;
   copy Unicode text before attempting Ctrl+V via `SendInput`; recheck foreground
   identity and preserve the clipboard/history fallback on failure. Respect
   Windows UIPI/integrity boundaries; do not promise pasting into elevated apps
   from a standard-user process or require administrator privileges.
4. **Audio and floating bar:** use the existing PortAudio capture path after
   testing device changes, sleep/resume, mute and unplug. Implement a native
   `WS_EX_NOACTIVATE` floating window with explicit DPI/multi-monitor geometry,
   drag/snap, and accessible controls. A generic always-on-top web window alone
   does not preserve the active text cursor.
5. **Speech:** provision the Windows model and required VC++ runtime during the
   controlled build/install. First validate CPU/int8 on supported x64 hardware;
   treat NVIDIA/CUDA acceleration as a separate optional build and test matrix.
6. **Packaging:** build on Windows with a Windows-specific PyInstaller spec;
   bundle model, PortAudio, CTranslate2 native dependencies, UI/font/licenses,
   and WebView2 runtime requirements. Test on a clean VM without Python or the
   source checkout. Use one stable publisher/app identity and Authenticode.
7. **Updates:** prefer a signed MSIX distributed through Microsoft Store or
   `.appinstaller` with HTTPS update metadata. Map SemVer to four-part package
   versions, e.g. `0.1.1.0`, preserving a stable publisher. OS-managed updates
   are independent of Sparkle. If direct EXE distribution is necessary, choose
   and integrate a maintained signed Windows updater rather than reusing DMG
   replacement code. Configure per-app update preferences through the supported
   Windows package/update APIs, not merely a JSON checkbox.
8. **Acceptance:** two independent shortcuts, raw input edge cases, Fn/media
   limitations, mouse drivers, target-app insertion, multi-monitor DPI,
   keyboard layouts/IME, microphone privacy, canceled/failed capture, retention,
   restart, clean install/uninstall, signed upgrade, corrupted updates, and
   preference migration. Verify the taskbar icon and keyboard navigation.

[pywebview](https://github.com/r0x0r/pywebview),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), and Microsoft's
[App Installer update documentation](https://learn.microsoft.com/en-us/windows/msix/app-installer/auto-update-and-repair--overview)
are the primary references. Windows model/decoder unit tests use a simulated
model factory; they establish the adapter contract, not real Windows inference,
GUI behavior, packaging, or a launch-ready Windows product.

## Verification record — 18 October 2026

- Local regression suite: **138 passed**. Coverage includes independent hold and
  toggle session ownership, shortcut capture and migration, native Darwin event
  translation, listener cleanup, update parsing/lifecycle, and the simulated
  Windows decoder contract.
- Native Cocoa/WKWebView integration check passed with an isolated temporary
  configuration/database: six views, nested shortcut capture/save through the
  native bridge, recent/full history rendering and escaping, local font/logo,
  update controls, and minimum window layout.
- Final frozen app self-check passed: regular Dock activation policy, application
  icon and native menu, WebKit UI, and local model resolution. It did not open the
  microphone or start global shortcut listeners.
- A separate copy outside the source checkout passed packaging imports/resource
  checks and UI/model self-check from an empty working directory with a minimal
  environment. Bundled MLX inference executed on synthetic silence; its output
  was `You`, so this is an execution check, **not** a recognition-quality result.
- Final DMG checksum, deep/strict app code signature, version `0.1.0` / build
  `1000`, Flow Fold icon, and packaged UI/font assets were verified. The image was
  mounted read-only and ejected after inspection. Signing uses the existing local
  certificate; this build is not Developer ID signed or notarized.
- The final live app restarted through its own control, preserved the user's two
  shortcut choices, and visibly cancelled recording with Escape. Public release
  status remains “No public releases yet.” No user bindings or history were
  replaced during this final check.
- All **83** landing-page source/asset hashes captured before this task remain
  unchanged. `git diff --check` passed.
- Not verified here: real Windows recording/input/insertion, Windows installer or
  runner execution, signed Sparkle feed/upgrade, or Developer ID notarization.
  Hardware-specific Fn/media keys and third-party mouse drivers still require
  testing on the supported devices; synthetic event tests do not establish every
  device's behavior.
