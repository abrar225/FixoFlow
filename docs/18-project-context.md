# Fixo Flow project context

Source review: 2 November 2026. Baseline commit: `a31a097`; application version
0.3.4. This is a working context map for subsequent product development, not a
claim that every runtime behavior or speech scenario has been verified.

## Product and scope

Fixo Flow is an MIT-licensed, local voice dictation desktop application with a
separate static marketing/download website. Its central job is to turn speech
into useful text in the application where the user began dictating. It has no
account service, hosted transcription backend, subscription system or telemetry
pipeline in the inspected implementation. SQLite is its application database.

The original brief targets developers on Apple Silicon. The current README and
website broaden this to everyday writing and three desktop platforms. These
audiences share capture and recognition, but need different formatting,
vocabulary, activation and recovery experiences.

Current public scope: English; macOS 14+ Apple Silicon; Windows x64 preview;
Ubuntu 24.04 x64 X11 preview. Windows 10 compatibility and physical-device
acceptance remain qualified. Wayland global shortcuts and paste are unsupported.
Hindi, Roman Hinglish and other languages are research, not released features.
US/UK/India preferences use the same English recognizer and do not force spelling.

## End-to-end architecture

1. `desktop.py` selects the native host. `app.py` owns Cocoa, Dock, menu bar,
   native permission handling and WebKit on macOS. `desktop_app.py` owns pywebview
   hub/pill windows on Windows and Linux.
2. `daemon.py` (Mac) and `input_listener.py` (Windows/X11) adapt keyboard/mouse
   input. `shortcuts.py` owns physical key identities, pair validation, recording
   shortcuts, quarantine after capture and input-edge routing.
3. `controls.py` serializes session actions on a single-worker executor. Its
   intent state handles fast press/release while microphone startup is pending.
   Core states are IDLE, RECORDING and PROCESSING. Settings wait for idle.
4. `core.py` owns capture, recognition, formatting, persistence and delivery.
   It remembers the target app at start, retains raw and final text, and exposes
   user-visible failure information.
5. `audio/recorder.py` captures 16 kHz mono audio into recoverable PCM16 WAVs.
   A queue of twenty 100 ms blocks bounds pending capture. A writer flushes and
   fsyncs audio. Failures retain cleanup ownership rather than reporting success.
6. `stt/engine.py` resolves local models, reads recovery WAVs in bounded windows,
   filters each window, decodes and carries recent transcript context forward.
   `audio/slicer.py` finds low-energy splits, normally between 16 and 24 seconds.
   `audio/filter.py` applies bandpass conditioning and capped peak normalization.
7. MLX Whisper handles Mac inference. `stt/cpu.py` uses faster-whisper/CTranslate2
   on Windows/Linux, float32 CPU, one worker and configurable bounded threads.
   That decoder currently has VAD disabled. Exact-zero chunks are skipped by the
   shared engine; this is not a general silence/noise detector.
8. `brain/learner.py` supplies up to 25 approved vocabulary terms and applies
   dictionary replacements plus opt-in spoken-code rules. `brain/polisher.py`
   applies deterministic writing cleanup. No model weights are personalized.
9. `storage/db.py` records completed sessions and derived analytics. Adjacent
   `.transcript.json` files preserve intermediate/final/partial transcripts.
10. `platform/` adapters copy text to the clipboard, restore app focus where
    possible, recheck target identity and dispatch platform paste keystrokes.
    A sent keystroke does not prove acceptance in the original editable field.

## User-facing behavior

The hub has six panels: Overview, Insights, Style, History, Dictionary and
Settings. `ui/hub.html` and `hub.css` are shared between native hosts;
`ui/controller.py` owns bridge actions and data. `hub.py` is the Mac window host.
`ui/overlay.py` is the Mac nonactivating panel; `overlay.html` is the shared pill.

There are two independently recorded shortcuts: hold-to-talk and hands-free
toggle, with keyboard and mouse support. Defaults are Control+Space and
Alt+Space. Escape can cancel capture/processing. Decoding cancellation is checked
between chunks and after decode, rather than interrupting native inference.

Modes: Automatic, Coding, Writing, Raw. Automatic selects Coding from an explicit
set of editor/terminal app names and Writing otherwise. It does not understand
browser tabs, the current document, or the semantic purpose of a text field.
Conversational Codex/Claude/ChatGPT composers are not automatically Coding.

Styles: Natural, Concise, Professional, Verbatim. These are rule sets, not a
generative writing assistant. Professional expands selected contractions;
Concise removes additional hedges; writing modes can structure conservative
explicit ordinal lists. Spoken punctuation/code commands are opt-in. Strict
Verbatim bypasses dictionary and cleanup. Raw bypasses formatting as well.

Dictionary replacements are literal, longest-first and noncascading against the
original text. Unicode boundaries and symbol terms receive specific handling.
Vocabulary is explicit; recognizer output is not silently trusted as learning.
History and dictionary support search and pagination. History is not an inbox
for interrupted or failed sessions.

Preferences autosave after a pause with bridge acknowledgments, pending/error
states and retry. `config.py` validates settings, migrates legacy keys, writes
atomically and preserves a backup. Malformed JSON can still prevent startup;
there is no guided recovery flow. `startup.py` integrates SMAppService, the
per-user Windows Run key and Linux XDG autostart; installed identity and existing
OS settings matter. Source/diagnostic runs do not register login startup.

## Data, privacy and network boundaries

Default user state is under `~/.fixoflow/`: config and backup, SQLite database,
audio cache and transcript sidecars. Mac logs are under `~/Library/Logs/Fixoflow/`;
the other desktop host uses `.fixoflow/logs` with rotation. No personal history,
recordings or logs were opened for this review.

Database tables: history (raw/final text, duration, latency, mode, app, audio path,
fix counts); dictionary (phrase, replacement, category, frequency, last-used and
legacy learning flag); analytics_daily; app_meta; session_artifacts (path/root/
filesystem identity). Session deletion checks file ownership and linked artifacts
before unlinking. Clearing History does not sweep orphaned recordings that never
became completed History rows. Filesystem deletion and SQL rollback do not form
one atomic transaction.

Audio persists even on cancel/incomplete capture. Automatic retention, a private
session mode and an exposed recovery inbox are missing. Local storage does not
mean application-level encryption. The current clipboard is replaced for delivery.
App identity checks do not establish sensitive-field awareness or field ownership.

Recognition/polishing do not require network calls. Optional startup/manual update
checks request bounded metadata from the configured website feed, without audio
or transcripts. Local model resolution fails rather than silently downloading.
`model_packs.py` retains multilingual research/download machinery, but released
language validation and the hub prevent its public activation. Do not mistake
the language catalog for enabled language support.

## Website and distribution

`Landing_Page/` is Next.js 15 / React 19 / TypeScript, statically exported.
Routes: home, features, how-it-works, download and privacy, plus sitemap/robots.
GSAP and Framer Motion drive visual examples. `use-demo-availability.ts` pauses
automatic demonstrations offscreen/when hidden and respects reduced motion.
Website examples are illustrative; they do not record the visitor's microphone.

`lib/product.ts` owns brand/URL constants. `lib/releases.generated.json` owns
installer availability, version, filenames, byte counts, hashes and trust notes.
`public/releases/latest.json` is the manual updater feed. The website package
version 1.1.0 is separate from app version 0.3.4.

`packaging/Fixoflow.spec` bundles Python/native dependencies, UI and the English
MLX model for Mac. `Desktop.spec` bundles the CPU model and pywebview dependencies.
Windows uses Inno Setup; Linux produces a .deb. Build helpers prepare pinned
models, create/sign the Mac app and DMG, check native installers, verify artifact
metadata and stage website links. Model preparation and app inference have
different network policies: inspect the appropriate build helper before use.

GitHub workflows run portable contracts on three OSs, build Windows/Linux
installers and smoke-test installed UI/model execution. The attachment workflow
checks exact build SHA, successful run, matching draft, hashes and reports before
adding assets. Mac packaging is local. Source metadata describes locally signed,
unnotarized Mac packages and unsigned Windows previews. Signed automatic
installation is not operational by default. Checksums establish file identity,
not public publisher trust. Historical deployment claims were not rechecked live.

## What changed since the original audit

Do not treat `docs/10-product-audit-and-roadmap.md` as a list of still-open bugs.
Source and tests now cover separate shortcuts, bounded WAV-file processing,
partial recovery, cancellation checks, strict Verbatim, noncascading dictionary
corrections, dictionary/history paging, preserving the warm CPU model for
unrelated preference changes, final app identity checks before paste, English-only
release gates, login startup and acknowledged preference autosave.

Older briefs also describe a single timing-based shortcut, Mac-only support,
four panels, cross-faded slicing and absolute zero network/zero loss. Those are
not reliable descriptions of current behavior. Current slicing is adjacent
low-energy segmentation, not cross-fading. Optional updates use the network.
Recovery reduces loss risk but does not guarantee complete recognition.

Use current code/tests plus README and docs 13/17 for shipped behavior. Use docs
00–06 for original intent; 07–09 and packaging for platform/release evolution;
10 for the historical finding ledger; 11–13 for subsequent fixes and language
research; 14–17 for release/domain/distribution history. Existing local edits to
docs 08 and 09 were preserved.

## Improvement direction

First, establish recognition evidence. `scripts/evaluate_speech.py` already
accepts a local WAV/reference manifest and records normalized word errors,
elapsed/CPU time and main-process peak RSS. Extend a consented corpus across
accents, names, numbers, noise, silence, technical terms and long sessions. Track
raw WER, identifier/name/number exact match, omitted clauses, formatting meaning
changes, p50/p95 stop-to-text latency and whole-app memory. Compare models and
preprocessing on identical held-out audio. Existing synthetic language probes
in docs are historical diagnostics, not representative human accuracy scores.

Second, make failures understandable: microphone choice and level test, device
disconnect recovery, a recovery inbox with retry/export/delete, explicit delivery
status and recovery from bad configuration. Add retention/private-session choices
with clear semantics before changing stored user data.

Third, make everyday writing and developer workflows distinct but compatible:
simple optional presets; per-app mode/style/vocabulary overrides; correction
feedback with raw/final/user-corrected provenance; reversible text changes;
opt-in snippets; preview of commands before enabling them. These are proposals,
not implemented features. Avoid automatic rewriting or executing terminal text.

Fourth, improve quality through measured acoustic/model changes: speech-aware
segmentation, silence/hallucination suppression, overlap/deduplication and a
small number of benchmarked model choices. Bandpass filtering is not general
background-noise removal. Larger models alone do not establish better daily use.

Finally, validate native device workflows and accessible interaction across
platforms, multi-monitor behavior, trustworthy signing and upgrade paths. Keep
multilingual/Hinglish gated until script policy and speech evidence support it.
The original sub-200 MB ambition is not proven; bounded input processing does
not bound all inference or WebKit memory.

## Verification performed in this review

- `.venv/bin/python -m pytest tests/ -q`: **228 passed, 3 skipped**, 3.05 s.
- Website `npm run lint`: passed (this script is TypeScript checking).
- Website `npm run build`: passed; static export completed.
- Website `npm run audit:copy`: passed five product routes, 19 required files and
  101 exported local links, plus release metadata/copy checks.

No application behavior was modified. This review did not run microphone
capture, real speech accuracy evaluation, native installed UI checks, OS input
or paste acceptance, fresh installer builds, signing/notarization, production
downloads or deployment. Local tests and static export cannot establish those.
Graph relationships described here come from source inspection; no complete
Graphify semantic graph or exhaustive runtime trace was generated.

VERDICT: PASS for the executed source suite and website checks; runtime and
representative recognition-quality acceptance remain unverified.
