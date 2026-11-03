# 0.5.0 preview: broader dictation workflow

3 November 2026. Implements the requested model/language, onboarding, clipboard,
tray, Intel Mac and Linux package improvements. This supersedes docs/26 for
development-source scope. Public downloads remain0.3.4; the0.4 draft is preserved.

## Recognition choices and language

Sixteen pinned format variants provide English Tiny/Base/Small, multilingual
Tiny/Base/Small/Turbo in MLX and CPU formats, plus Parakeet v2/v3 ONNX. Compatible
choices depend on hardware; ONNX is currently excluded on Intel Mac. Every asset
has immutable revision, byte count and SHA256 validation. Downloads are explicit.
Whisper multilingual exposes99 languages plus Auto. Parakeet v3 automatically
detects its25 supported languages; the UI does not pretend it can force one.
English defaults remain unchanged. Language/model choices survive restart.

English formatting/vocabulary rules are skipped for other languages and Auto,
because the text-only recognition contract cannot reliably identify the language
after Auto decoding. This protects valid words such as German "um". Explicit
approved correction memory remains scoped and protected by Raw/Verbatim policy.

Actual local source inference ran English JFK and a public Spanish MLS test
recording. Spanish output was preserved without translation; one31-word sample
is runtime/script evidence, not representative language accuracy. See
[model/runtime evidence](28-model-language-parity.md).

## Guided setup

Six resumable pages: introduction/preset, permissions, microphone, model/language,
practice, completion. Requests for permissions and microphone use require an
explicit action. Setup records metadata through the shared settings boundary;
pending preferences, recording, checkup and model work cannot be overwritten.
Practice uses the existing ordered session owner with auto-paste disabled. Closing
setup cancels only its practice recording/checkup, never an unrelated dictation.
Practice transcripts/recordings remain in local History; no microphone check PCM
is stored. Completing setup does not grant missing native permissions.

## Clipboard and tray

Clipboard preservation is optional and off by default. Mac/Windows preserve
supported rich/image/text formats in bounded memory; native X11 has a bounded
selection-owner implementation. Ownership changes protect newer clipboard data.
Consecutive Fixo dictations retain the original baseline only while ownership
still matches. Failed insertion keeps a recoverable transcript. Disabling the
preference or quitting discards the snapshot without overwriting the clipboard.

Restoration requires confirming that paste appeared, through an inline Hub action
or the tray. This deliberately differs from SpeakType's fixed-delay automatic
restore: dispatching a synthetic key is not recipient-consumption proof. Wayland,
unsupported formats and large X11 INCR snapshots report capability limitations.
Details and bounds: [clipboard evidence](28-clipboard-parity.md).

Mac menu-bar and Windows/Linux tray menus expose start/stop/cancel, selected
model/warm-up status, installed model switching, model-aware language selection,
microphone selection, mode, settings, guided setup, recovery and clipboard
restoration. Windows/Linux close-to-tray only hides the window when a usable
tray exists. On Linux a missing StatusNotifier host leaves the window accessible
instead of hiding it. Quit drains operations; diagnostic checks cannot hide and
hang behind the tray. Failed restart/quit does not retain stale restart intent.

## Distribution

Native arm64 and x86_64 Mac spec/build/diagnostic paths; CPU on Intel. Linux DEB,
native Fedora RPM and actual AppImage runtime packaging, with immutable verified
AppImage tool/runtime artifacts. Windows setup retained. Dependency notices and
source manifests travel with installers. See [distribution evidence](28-distribution-parity.md).
All remain previews: public Mac notarization and Windows publisher signing were
explicitly deferred by the user. Package-format availability does not establish
support for every distro, desktop, microphone or paste target.

## Verification ledger

Record final source commit and actual native runs below after integration.
No physical microphone, synthetic global keyboard or user's clipboard may be
used by automated checks. Native X11 tests require their own Xvfb display.
Existing user edits in docs/08 and docs/09 are excluded from commits.

- Model, download integrity, compatibility and local engine tests passed in the
  model workstream; actual public non-English runtime reports are retained.
- Native WebKit integration passed guided setup resume, compatible Spanish
  selection, forced-auto Parakeet, stale-capability-reply protection, existing
  panels, history and correction UI. Final completion checks are being recorded.
- Independent review caught and fixed stale idle-pill theme, nonterminal service
  draining, refused-restart flags, and diagnostic close-to-tray behavior. Regression
  tests cover the critical lifecycle boundaries.
- Native Intel, Ubuntu/Fedora and Windows execution must be recorded from the
  final integration workflow; source/fixture tests are not substitutes.
