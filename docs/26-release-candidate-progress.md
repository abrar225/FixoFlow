# 0.4.0 candidate: implementation and launch gates

2 November 2026. This document supersedes the partial implementation inventory
in docs/21. Public website/download metadata remains at 0.3.4. Version 0.4.0 is a
development candidate until native and publisher-trust gates pass.

Policy: deep implementation; broad feature/dependency context; parallel bounded
benchmark/model/convenience work under gravitas, followed by integration checks
and an independent recovery review. Existing user changes to docs/08 and the
untracked docs/09 are excluded from implementation commits.

## Implemented

- Persistent learning identity is distinct from the temporary paste target:
  Mac bundle ID; Windows normalized executable path; Linux executable path.
  Window/PID/start-time checks remain on delivery. Additive migration preserves
  old records; legacy Windows/Linux window arrays cannot become global rules.
- Approved exact-utterance memory survives stable app scope across restart.
  Context matching can propose a small edit with neighbouring words, always for
  review; it never silently generalizes a homophone/letter rule. Quoted/code-like
  text and question-to-statement mismatches are excluded conservatively. Undo
  approval disables future reuse; Forget and source deletion remove memory.
- Recovery inbox retries a verified owned WAV into a new owned recording and
  History entry, with current model/settings and no automatic paste. Copying is
  bounded, cancellable and detects changing/truncated sources. Originals remain
  visible and deletable even after recovery. Active/unknown owners are protected;
  legacy unknown-owner recordings have a validated Show recording folder action
  rather than an impossible promise to verify inactivity.
- History-save failure now remains a recovery-needed state and never retires an
  original retry source as recovered before a new History entry is durable.
- Microphone selection, explicit five-second level/clipping/no-signal check,
  retained cleanup ownership, and capture failure detection via finished callback
  and control-thread polling. Dictation/settings cannot race mic/model operations.
  No checkup audio is stored or used as learning evidence.
- Six pinned English catalog entries: Tiny/Base/Small in MLX and CPU formats.
  Explicit download, size/SHA-256 verification, staged promotion, disk preflight,
  cancel/error states, verified local warm-up, and offline inference. Catalog
  labels identify candidates rather than inventing quality scores.
- Intel Mac source routing uses CPU instead of MLX, with conditional dependencies.
  This is not an Intel installer or hardware acceptance claim.
- Light/Dark/System themes, shared pill theme payloads, and editable role starting
  presets for everyday writing, developers, writers, business and hands-free use.
  Presets set existing mode/style/control preferences; they do not infer roles,
  add a semantic writing model or personalize acoustic weights.
- Matched benchmark and pinned public-corpus preparation tools; failure-aware
  WER/CER, explicitly labeled entity metrics, raw artifact/source hashes,
  timing-phase separation and uncertainty reporting. See docs/23 and docs/24.
- Local self-contained Mac 0.4.0 app, installed diagnostic checks and DMG build.
  Source-manifest provenance is included in final builds. Public publication
  remains gated; the website is not changed to advertise unqualified binaries.

## Measured recognition evidence

The original one-clip public JFK diagnostic was insufficient to rank accuracy.
A deterministic 20-clip OpenSLR LibriSpeech subset was subsequently prepared:
20 speakers, ten clean/test and ten other/test clips; 130.805 seconds and 340
reference words. Source dataset revision and prepared audio hashes are pinned.

- Fixo Base English MLX: 29 normalized word errors / 340 = **8.53% WER**.
- Base English whisper.cpp reference backend: 24 / 340 = **7.06% WER**.
- Fixo Small English MLX: 16 / 340 = **4.71% WER**.
- Fixo Tiny English MLX: 37 / 340 = **10.88% WER**.

All four paths completed these clips. Small/Tiny qualification used the same
manifest but different execution/timing procedures from the paired backend run;
do not compare their timing columns as equivalent end-to-end measurements.
Tiny's median local decode was about 0.055 s; Small about 0.246 s, under
uncontrolled host/cache conditions. Existing JFK sequential tests also support
Tiny as a speed candidate. Small's lower observed WER on this subset supports
continuing its quality qualification, not claiming universal accuracy superiority.

The paired Base backend speaker-bootstrap interval for right-minus-left WER
crossed zero. These data do not establish a product winner. The whisper.cpp
reference is initially a proxy, not SpeakType's complete application. Native
SpeakType runner work and any later results are recorded in docs/23.

Read speech from 20 clips does not cover everyday phrasing, personal names,
developer identifiers, Hindi/Hinglish, device changes or long dictation. No
personal audio was accessed or uploaded. Default model remains Base English.

## Reference feature checklist

SpeakType reference is the temporary checkout `/tmp/fixoflow-speaktype-review`,
refreshed at 1e17f21. Product/workflow inspiration, not a source transplant.

- Local/free/no required account: retained.
- Separate hold/toggle and developer controls: Fixo strengths retained.
- Microphone selection/check: implemented; physical acceptance remains.
- Download/warm-up UI: implemented for qualified English candidate formats.
- Playback: implemented for owned PCM audio up to 20 MB; scalable streaming and
  legacy audio import remain open.
- Themes: implemented; native titlebar/tray appearance parity remains open.
- Model/engine breadth: English Whisper catalog implemented; Parakeet runtime,
  Turbo variants and multilingual release are not implemented/qualified here.
- Clipboard restoration: still open; no timed restore added that could silently
  remove the only manually recoverable clipboard transcript.
- Tray panel: existing Mac menu remains; dedicated cross-platform tray panel is
  still open. Startup registration and floating controls remain available.
- Distribution breadth: Windows/Linux native preview workflow expanded to new
  contracts; Intel installer, .rpm/AppImage and full Wayland portal support remain
  open. A new archive format alone would not establish supported distro behavior.
- Publisher trust: local Mac signing available; public Developer ID/notarization
  and Windows signing acceptance remain external gates. Manual updates retained.
- Retention/private sessions and complete migration/export controls: still open.
- Local generative rewriting, auto-learning from other apps, live transcription,
  meeting notes/mobile syncing: roadmap items, not competitor features to claim
  copied or completed. No reinforcement learning/acoustic adaptation is claimed.

## Verification and remaining launch gates

Local source suite most recently passed **310 tests, 3 skipped**. Native isolated
Cocoa/WebKit checks passed six panels plus correction approval/Forget, journal,
owned audio loading, mic selection, themes and service/recovery rendering. No
physical microphone/speaker or global input/paste was exercised by these checks.

The self-contained and installed 0.4.0 Mac bundle passed offline native dependency,
bundled synthetic inference and Cocoa/WebKit window/overlay checks, with temporary
HOME/DB and no microphone or shortcut start. Original installed app was backed up
under `dist/.previous-builds/`. The local DMG passed `hdiutil verify`.

Final source-commit/provenance build and Windows/Linux CI status are appended
after completion. Required before broad public launch: meaningful native-device
acceptance, validated installed upgrade/data migration, publisher trust where
promised, broader representative speech evaluation, and completion or explicit
scope reduction of the remaining feature checklist above. This is a substantial
candidate improvement, not a final/perfect-product or superiority claim.
