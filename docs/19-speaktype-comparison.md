# Fixo Flow versus SpeakType

Reviewed 2 November 2026. Fixo Flow 0.3.4 at `a31a09795023b30feb851937ecf361d6c9b4b9c9`;
SpeakType 2.0.0 main at `1e17f218a48d73f733fac1f15629e0345968e1ba`.
SpeakType was cloned into `/tmp/fixoflow-speaktype-review` for read-only source
inspection and isolated frontend checks. No microphone, personal data, installed
app, speech model or production installation was exercised.

## Verdict

SpeakType is ahead as a broadly featured general-purpose dictation product.
Fixo Flow has stronger source-level protections for long capture, partial
recovery, original text retention and app-targeted delivery. Neither has won a
controlled recognition-quality comparison in this review. Model availability
is an advantage; advertised model scores are not accuracy measurements.

My provisional engineering/product-readiness ratings are **Fixo Flow 6/10** and
**SpeakType 7/10**. These are subjective judgments about inspected design and
implemented scope, not measured user satisfaction, accuracy or production
reliability. One-point differences should not be interpreted as precise science.

Using equal weight across six dimensions, my component judgments are:

- Recognition flexibility: Fixo Flow 4, SpeakType 8.
- Everyday workflow completeness: Fixo Flow 5, SpeakType 8.
- Capture durability and recoverability: Fixo Flow 8, SpeakType 4.
- Explicit text preservation and developer formatting: Fixo Flow 8, SpeakType 5.
- Platform/distribution breadth: Fixo Flow 5, SpeakType 8.
- Verification/maintenance design: Fixo Flow 6, SpeakType 7.

Rounded equal-weight means yield 6 and 7 respectively. Both remain below a
production-ready 9: native device acceptance and representative speech evidence
are incomplete. The verification score includes source test/CI design, not a
claim that SpeakType's native suite was run here. The recovery score does not
mean Fixo Flow already has a usable recovery inbox.

## SpeakType's system explained

### Two generations, one repository

The root `speaktype/` Swift project is SpeakType 1, using SwiftUI and earlier
WhisperKit/FluidAudio integrations. The current cross-platform implementation is
`desktop/`: React 19/TypeScript/Vite/Tailwind UI, Tauri 2 host, Rust backend.
Do not combine v1's automatic updater or engine behavior with v2's capabilities.
The v2 roadmap explicitly says updates currently open the release page.

The React UI has Dashboard, History, Dictionary, Statistics, AI Models and
Settings. Separate main, floating-pill and tray-panel entry points share state
through Tauri commands/events. Onboarding handles permissions/model setup. The
Rust backend owns privileged work; JavaScript is the interface, not the decoder.

### Input and capture

`dictation.rs` routes events through a controller thread with one session owner.
Pure decision logic maps hold/toggle, key release, interruption and Escape into
actions. Tauri's global shortcut plugin handles combinations; platform adapters
handle single modifier keys where supported. Mac defaults to Fn, other systems
to Ctrl+Shift+Space. The user chooses hold or toggle for one binding; Fixo Flow
offers separate simultaneous bindings for both, including mouse combinations.

`audio.rs` uses CPAL and supports a selected microphone, falling back to the
system default if it disappears. It accepts the device's sample format/rate,
averages channels to mono, buffers f32 samples in a growing vector and resamples
to 16 kHz at stop using windowed-sinc interpolation. An atomic level value keeps
UI work off the audio callback. The level meter's noise gate is visual feedback,
not audio denoising or speech detection. Stream errors are printed to logs.

Important tradeoff: capture is in memory. `pipeline.rs` writes a WAV only after
recognition and nonempty postprocessing. A crash during capture or failed
recognition therefore lacks Fixo Flow's continuously persisted recovery WAV.
This is evidence of a recovery risk, not an observed crash test.

### Models and recognition

`models.rs` provides eight catalog options: Parakeet v3, Parakeet v2 English,
Whisper Large v3 Turbo, compressed Turbo, Small English, Base English, Base and
Tiny. The catalog sizes
exclude some optional accelerators; compare total downloaded size, not just the
main model file. Downloads use progress/cancel, temporary paths and completion
checks; Whisper URLs reference `resolve/main`, so they are not immutable model
revisions. No cryptographic expected model digest was found in this downloader.

`engine/mod.rs` keeps at most one model loaded and frees it before a replacement.
Whisper runs via whisper-rs/whisper.cpp, with Metal and optional CoreML encoder
on Mac. Parakeet uses transcribe-rs and ONNX Runtime with int8 exports; it is not
available on Intel Mac. Native CUDA/Vulkan features are build options, not proof
that every distributed package accelerates on every GPU.

The Whisper adapter uses greedy decoding, up to eight CPU threads, no prior
context, language selection/auto detection and pads very short recordings.
It does not feed the personal dictionary into recognition as Fixo Flow does.
Parakeet detects language through its backend; v3's catalog covers English plus
24 European languages, not Hindi. Whisper offers much wider language choices.
Availability does not establish usable Hindi-English code-switch accuracy.

Warm-up starts in the background for downloaded models, including at capture
start, and model load is serialized by an engine mutex. The UI distinguishes
warming from processing. Fixo Flow lazily imports inference and has no equivalent
user-facing model manager/warm-up experience.

### Cleanup and dictionary

`text.rs` removes recognized placeholder/noise labels, normalizes whitespace,
optionally removes fillers, applies enabled dictionary rules, then optionally
removes a trailing period from short non-prose tokens, URLs, email or numbers.
Dictionary rules allow enable/disable and whole-word settings.

Its rules deliberately chain: A→B and B→C can turn A into C. That is tested
behavior, but risky for accidental correction cascades. All whitespace is
collapsed, even with Auto Edit off; line/paragraph structure is not preserved.
The history item stores the resulting transcript, not a separate raw/final pair.
Fixo Flow's strict Verbatim, Raw, writing styles and opt-in code transformations
provide stronger explicit output controls. Neither currently has a local
generative writing assistant, semantic rewrite engine or correction-trained ASR.

### Persistence and delivery

`history.rs` maintains JSON history and separate JSON usage statistics, written
via temporary-file persistence. Deleting history intentionally retains statistics.
The full history list is returned by the API. This is simple, but full-list
serialization and rewriting deserve scale tests. Fixo Flow instead uses indexed
SQLite history, paged queries, raw/final pairs and rebuildable history-derived
aggregates. These products have different deletion/analytics semantics.

SpeakType has recording playback and reveal-in-folder commands, an advantage
over Fixo Flow's current history interface. Media decoding code and a developer
WAV example exist; the inspected v2 routes do not expose a general file
transcription screen. Do not count a code comment about such a screen as a feature.

`paste.rs` runs a persistent clipboard worker. It saves previous text/image,
sets the transcript, waits 250 ms, sends paste, waits another 350 ms and restores
the clipboard if it still contains the dictated text. It respects a newly copied
text value and leaves dictated text on the clipboard when paste dispatch fails.
Rich clipboard formats are not preserved by this text/image snapshot.

This is convenient but does not verify that the recipient consumed the clipboard
before restoration. The job contains no original-app identity; delivery targets
the focused app at paste time. The dictation controller receives no paste result,
and failures are logged. Fixo Flow remembers the initial target, attempts focus
restoration and reports recovery outcomes. Neither owns the original text field
or verifies that text actually appeared there. Fixo Flow's focus restoration can
also surprise a user who deliberately switched applications.

### Cancel, updates and platform boundaries

Escape during recording in SpeakType still transcribes/saves but suppresses paste.
Escape during processing dismisses the active flow; the worker continues and can
save history. It is not immediate native inference cancellation. Fixo Flow checks
cancellation between bounded chunks and after decode; native decode itself is
still not interruptible through that mechanism.

SpeakType v2 checks GitHub release metadata and opens the release page. Its
release workflow supplies Apple Developer ID/notarization secrets, and the
README claims a signed Mac release. This is stronger distribution preparation
than Fixo Flow's local Mac signing, but no actual DMG signature/notarization was
independently verified here. Windows signing remains roadmap work for SpeakType.

SpeakType builds Mac Intel/Apple Silicon, Windows and Linux .deb/.rpm/AppImage.
Wayland has wtype/ydotool paste fallbacks and an XWayland-dependent shortcut;
full portal support is unfinished. Its roadmap acknowledges little Windows/Linux
testing outside CI. Fixo Flow explicitly limits Linux to X11. Neither deserves
a universal compatibility claim.

## Where each project leads

SpeakType: selectable speech engines/models, multilingual UI, microphone picker,
model download management, onboarding, audio playback, clipboard restoration,
themes, tray panel, more Mac hardware/package targets and broader native CI
checks. These are meaningful daily-use advantages, not just aesthetic differences.

Fixo Flow: continuously persisted capture, bounded file processing, partial
transcript recovery, raw/final provenance, noncascading dictionary, strict output
preservation, coding commands, independent hold/toggle shortcuts, login startup,
SQLite paging and initial-app identity checks with surfaced delivery errors.
Neither automatic privacy, free pricing nor local inference is unique to us.

Unsettled: actual speech accuracy, accent/Hinglish robustness, battery use,
whole-app memory, p95 latency, device reliability, accessible daily use and
installation trust. SpeakType's hardcoded speed/accuracy bars and README's
35-second/under-two-second and 15 MB claims are not comparative benchmarks.
Its small installer also requires separately downloaded models; Fixo Flow
installers bundle an English model. Comparing those sizes directly is unfair.

## Practical path to a stronger Fixo Flow

1. Build the comparison harness first. Use identical consented recordings for
   both applications: names, numbers, accents, code identifiers, quiet/noisy,
   silence/music, 5-second through multi-minute speech. Hold out speakers and
   sessions. Record raw WER, name/number/identifier exact match, missing clauses,
   formatting meaning changes, paste success, p50/p95 latency and total memory.
   Compare current Base English against suitable Parakeet/Turbo candidates;
   choose from measured hardware/quality tradeoffs rather than language fashion.
2. Close basic workflow gaps: mic choice and checkup, first-run successful test,
   model-ready status, playback and a recovery inbox with retry/export/delete.
   Define retention and private-session semantics before altering existing data.
3. Combine reliable delivery with optional clipboard preservation. Detect field
   changes where feasible, offer copy-only behavior and explicit recovery. Test
   slow recipients, focus switches, held modifiers and clipboard races. Never
   describe a dispatched keystroke as proven insertion.
4. Make developer and everyday experiences intentional: simple presets,
   per-app vocabulary/style, literal escape for commands, previewable code rules
   and correction feedback tied to a session. Proposed differentiation: turn a
   corrected name into an approved, scoped suggestion with undo; do not silently
   learn every edit or scrape private screen context.
5. Add creative usefulness after trust: user-approved voice snippets, structured
   issue/PR/message templates and optional review-before-paste. Keep expansions
   visibly distinct from literal dictation and never execute shell output.
6. Publish repeatable quality results and obtain trusted signing. Ship a small
   set of reliable language/model choices before adding a broad unmeasured menu.
   Meeting recording, mobile sync and agent-like editing are separate scope;
   copying every competitor roadmap item would dilute the core dictation job.

Success is fewer wrong names/numbers, fewer lost recordings, less correction
effort and predictable delivery. A different UI framework alone cannot produce
that. Retain Python unless measured deployment/performance constraints justify
a backend replacement; prototype a new recognizer behind the existing boundary.

## Checks and limits

SpeakType: `npm ci --ignore-scripts`, `npm test` (18 passed, three test files),
`npm run build` (TypeScript and Vite passed). Install audit reported four dev/full
tree vulnerabilities; `npm audit --omit=dev --json` reported zero production
vulnerabilities. This is not a Rust/native dependency security audit. Rust unit
tests and native installers were inspected in source/CI but not built/run here.
Fixo Flow's preceding session had 228 passing tests and three skips plus passing
website checks; the Python suite was also rerun during this comparison.

No fair runtime speed, memory or recognition ranking is possible from these
checks. Source supports the behavioral comparisons, not universal reliability.

## Pinned primary sources

- [SpeakType desktop architecture](https://github.com/karansinghgit/speaktype/tree/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop)
- [Capture](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/audio.rs)
- [Pipeline](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/pipeline.rs)
- [Models](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/models.rs)
- [Text processing](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/text.rs)
- [Paste](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/paste.rs)
- [History](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/history.rs)
- [Roadmap and admitted gaps](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/ROADMAP.md)
- [Native CI and release](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/.github/workflows/desktop.yml)
- Fixo Flow owners: `core.py`, `controls.py`, `audio/recorder.py`, `stt/engine.py`,
  `stt/cpu.py`, `brain/learner.py`, `brain/polisher.py`, `storage/db.py`, platform
  adapters, `startup.py`, and `docs/18-project-context.md` at the baseline above.
