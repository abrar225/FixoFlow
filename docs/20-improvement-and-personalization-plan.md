# Fixo Flow improvement and personalization plan

2 November 2026. Planning baseline: Fixo Flow 0.3.4, `a31a097`.
Reference: SpeakType v2 at `1e17f21`; see `19-speaktype-comparison.md`.
Status: proposed architecture and implementation sequence, not shipped behavior.

Planning policy: deep; dependency-level reconnaissance; impact-based verification;
no delegation. Deliverable scope: this plan and an interactive roadmap. Existing
application and user-data behavior is unchanged. The user's request establishes
the direction for correction learning; the in-product observation controls below
are part of the design, not a request to monitor this computer now.

## 1. Product outcome

Make local dictation easier to start, more accurate for the user's language and
vocabulary, recoverable when it fails and increasingly useful with explicit
personalization. Preserve offline speech processing, raw transcripts, durable
recordings, noncascading corrections, separate shortcuts and honest delivery.

Take inspiration from model management, onboarding, mic choice, playback,
clipboard convenience, themes and tray access. Do not port SpeakType wholesale
or copy its in-memory capture and dictionary cascades. Retain the current Python
core/native shells unless measured limits justify replacing a specific module.

This plan covers all requested product areas. It cannot promise perfect accuracy,
universal application compatibility or that an ambiguity never recurs. Rank
progress by correction effort and successful completed dictations, not model count.

## 2. Learning: the correct technical interpretation

An edit is useful feedback, not necessarily a recognition error or a reward.
The user may rewrite an idea, change tone, quote somebody, correct another app's
autocomplete, undo an expansion or edit text unrelated to Fixo Flow. No edit is
also not evidence of satisfaction. Do not reward a recognizer merely because its
output was pasted or left unchanged.

Ship three distinct layers:

1. **Correction memory:** explicit accepted examples, scoped personal vocabulary,
   recognition hints, deterministic transformations and reversible suggestions.
2. **Contextual personalization:** a calibrated candidate ranker uses language,
   limited sentence context, selected profile and correction history to choose
   between retaining raw output, suggesting an alternative and applying an
   approved correction. The safe action is often to abstain.
3. **Optional research:** contextual-bandit policy selection or supervised acoustic
   adaptation, only after trustworthy labels, held-out evaluation and rollback.
   Updating a dictionary is not reinforcement learning. A contextual bandit can
   learn which assistance to offer; it does not automatically train ASR weights.

Do not implement an autonomous desktop agent that explores actions while the user
works. No live experimentation with destructive changes or terminal commands.

### Example: Y versus why

Recognized: `Y is the build failing?` User corrects: `Why is the build failing?`.
Associate the correction only with that delivered session/range. Store a candidate
confusion and context, not an unconditional Y→why dictionary rule. Offer “Remember
this correction for English writing?” The user can approve it as a scoped
suggestion. Later, `Y is the vertical coordinate` in Coding must remain unchanged.
`the letter Y`, quoted text, an isolated ambiguous `Y` and identifiers also need
negative controls. A global rule would make accuracy worse.

### Example: ball versus bawl

For many speakers these are homophones; audio alone does not uniquely identify
the intended spelling. Use the sentence and accepted personal evidence:
`The child began to bawl` versus `Throw the ball`. Prefer the untouched result
or a suggestion when context is weak. Never replace all instances of ball with
bawl after one edit. A correction memory can reduce repeated mistakes, not
guarantee that both valid words are always resolved correctly.

## 3. Target architecture and boundaries

`Input → session record → durable capture → compatible local recognizer → raw
result → profile/vocabulary context → conservative formatting/personalization →
delivery attempt → optional bounded correction observation → candidate review`.

Keep UI callbacks out of audio threads. A single session coordinator owns input
and delivery state. Add separate model and observation lifecycles; do not overload
the current IDLE/RECORDING/PROCESSING values with every download/UI state.

Proposed additions, with existing ownership:

- `sessions/`: stable session ID created before capture, journal/status transitions,
  recovery reconciliation. Integrates `core.py`, `controls.py`, `storage/db.py`.
- `stt/contracts.py`: request/result/capability contracts; adapt current MLX and
  CPU classes rather than allowing native backend details into the hub.
- `models/`: catalog, lifecycle and provisioning. Refactor `model_packs.py` into
  this boundary while preserving existing installed models and validation.
- `audio/devices.py`: enumerate/select/test/reconnect; recorder keeps persistence.
- `personalization/`: feedback evidence, diff attribution, memory, policy,
  suggestion ranking, explanations and rollback. `brain/learner.py` remains the
  compatibility entry point until callers migrate.
- `platform/text_observer.py` plus native adapters: capability-probed, optional
  focused-field observation. Delivery and observation are distinct permissions.
- `profiles/`: effective role/app/language settings; manual override wins.
- shared hub actions and UI: onboarding, models, playback, recovery, learning,
  themes and controls. No separate business logic in each host.

### Session and inference contracts

Create the ID before microphone startup and carry it into audio, history,
sidecars, decode chunks, delivery and feedback. Capture timestamps, frame counts,
model ID/revision, decoder options, language/script, effective profile, raw and
final output, transformation provenance and delivery status. Monotonic time
measures latency; wall time orders history.

Separate status values for capture, recognition, delivery and feedback prevent
“transcribed” from meaning “pasted successfully.” A pipeline error retains audio,
completed chunks and raw/final text independently of analytics.

`TranscriptionRequest`: session/audio reference, language policy, vocabulary hints,
cancel token, options. `TranscriptionResult`: text, optional segments/timestamps,
detected language, backend/model identity, warnings, completeness and timings.
Backend confidence is optional and uncalibrated until evaluated; never compare
Whisper log probabilities directly with a Parakeet score as one probability.

Capabilities declare supported hardware/languages, timestamps, prompting,
streaming and cancellation. Unsupported hints must be surfaced rather than
silently claimed as applied. Same recovery/cancellation contract across engines.

## 4. Recognition choices and language release policy

Support the following candidate families through catalog metadata rather than
hardcoding “eight” into product architecture: Whisper Tiny, Base English, Base
multilingual, Small English, multilingual Small, Turbo, quantized Turbo;
Parakeet English v2 and multilingual v3. Exact entries depend on verified
conversion artifacts, runtime support, licenses and hardware evidence. These
are candidates to qualify, not approved download URLs or a default model change.

Start with existing Base English plus one quality and one speed candidate.
Test MLX/CTranslate2 Whisper variants first behind the common contract; prototype
an isolated Parakeet ONNX worker. Choose its runtime from integration evidence
instead of automatically adding a heavyweight training framework to installers.
If native isolation is needed, use a bounded request protocol and restartable
worker; account for total process memory and cancellation/cleanup behavior.

Catalog records: stable ID, upstream identity and immutable revision, format,
runtime version, artifact SHA-256/bytes, license/notices, language/script claims,
hardware/OS support, total download/storage estimates including accelerators,
measured quality/latency/memory and provenance. Missing evidence is “not measured,”
never an invented score bar. Validate third-party conversions independently.

Lifecycle: absent → downloading → verifying → installed → warming → ready;
separate cancelled, failed and incompatible states. Deduplicate warm-ups, queue
only one heavy load, unload the previous model before exceeding memory budget,
allow retry and preserve a working selection on failure. Do not switch mid-session.
Use explicit downloads, disk-space preflight, bounded size/network timeouts,
staged verification, atomic promotion and cleanup. Check extraction paths and
symlinks; resume only with validated server identity/ranges, otherwise restart.
Provide remove/offline-import actions and protect models in use.

Language selection is model-capability based; selection, auto detection,
transcription, translation and transliteration are separate controls. Preserve
original script by default. Hindi and Roman Hinglish require independent code-
switch and script evaluations. Parakeet v3 covers 25 European languages, not
Hindi; it cannot be the universal multilingual answer. Do not remove the current
English gate until specific model/language pairs pass release acceptance.

Regional English spelling is a separate optional transformation policy. A
language flag or vocabulary prompt does not guarantee regional spelling.

## 5. Setup and everyday convenience

### Onboarding and microphone

Flow: choose language and optional role → explain/request only needed permissions
→ choose/test mic → compatible recommended model/download or bundled default →
warm-up → record shortcut → dictate in a safe test field → show recovery controls.
Allow skipping optional personalization, tray and theme choices. Keep diagnostics
different from real dictation and avoid adding test speech to personal learning.

Enumerate stable device IDs with a default-device option. Show live level,
clipping/no-signal hints and record/playback test. Measure recommended conversion
from native sample rates; retain persisted 16 kHz mono contract. On disappearance,
stop safely and retain the recording; notify before changing to another physical
microphone. Do not silently transcribe mixed-device audio as a complete capture.
OS default-following behavior must be explicit and tested.

### Playback and recovery

History playback uses owned artifact paths, never arbitrary paths from UI input.
Provide play/pause/seek/speed, reveal/export and raw/final comparison. Missing or
deleted audio is a normal state. Playback never creates microphone input loops.
Keep the audio decoder asynchronous and reject malformed/oversized files.

A recovery inbox reconciles the session journal and owned files at startup;
statuses include interrupted capture, incomplete decode, delivery failure and
cleanup-needed. Offer inspect/retry/export/delete. Retry must never auto-paste
old text or duplicate history. App crash, disk full and shutdown are first-class
scenarios. Private sessions need encrypted ephemeral recovery or an explicitly
disclosed reduced-recovery mode, not a hidden plaintext audio exception.

### Clipboard, appearance and tray

Optional clipboard preservation uses ownership/change markers and supported
format snapshots. Restore only while Fixo still owns the clipboard and the
recipient policy allows; capability failure leaves a visible manual recovery
path. A fixed timer is not proof of consumption. Test slow apps, clipboard
managers, image/rich text, user copying during paste and modifier release.

Themes use shared tokens for System/Light/Dark, contrast and reduced-motion
support; native titlebar and pill remain legible. Tray panel gives start/stop,
current model/language, warm-up status, mic/profile and recent recovery shortcut.
No accidental focus theft. Keep close/minimize/quit/reopen consistent and make
menu/tray actions accessible by keyboard and screen reader.

## 6. Personalization from daily corrections

### Feedback modes

Implement: Off; explicit “Remember correction”; Suggest from observed corrections;
and later opt-in automatic use of trusted patterns. Confirmed default is suggest-
first, as selected by the user. Never silently turn observing on because
Accessibility was already granted for paste. Provide per-app allowlist, pause,
private-session exclusion, inspect/export/delete learned memory and one-click
undo/disable for each application. Explain what was learned and where it applies.

User decision, 2 November 2026: suggest learned corrections for approval first;
optionally automate trusted patterns later. This is the confirmed default.

### Observation and attribution

First deliver a portable in-app raw/final/corrected editor and “Correct last
dictation” shortcut. This works without reading another application's contents.
Then add optional Mac Accessibility and Windows UI Automation observers, followed
by Linux AT-SPI experiments. Native availability must be probed per control;
these are proposed adapters, not guaranteed support in Electron, browsers,
terminals, editors, games or every Wayland session.

Only attach after a verifiable insertion range is located in the original
eligible control. Observe a bounded session/range with minimal nearby context.
Default proposal: at most 60 seconds after delivery, with an in-app fallback for
later edits. End on focus/field change, send/submit, timeout, lock, new session,
private mode or user pause. Proposed context bound: 256 characters either side;
do not read an entire document to find a match. If a control exposes only broad
unbounded text, report unsupported and fall back to explicit feedback.

Exclude password/protected fields and unsupported/unknown-sensitive controls.
No screenshot/OCR fallback, global keylogging, clipboard polling or background
document scraping. Do not use filenames, contacts, source repositories or browsing
history as implicit vocabulary. This design needs native spikes before promises.

Debounce events, map original delivered range through edits and require unique
anchors/version identity. Same-app identity alone is insufficient. Ignore remote
collaborator, IME composition, app autocorrect and assistant-generated changes
unless confirmed; many controls cannot distinguish authors, so uncertain events
remain suggestions. Whole-paragraph rewrites, undo/redo, multi-cursor changes,
ambiguous offsets and overlapping sessions invalidate automatic attribution.

Separate evidence labels: explicit correction; verified-range observed edit;
unverified candidate; rejection; undo. If the final edit reverses a previous
correction, update the candidate rather than learning both as positive examples.
If editing happens after observation ends, use explicit feedback instead of
claiming continuous surveillance.

### Memory and safe application

Do not overload existing global dictionary frequency. Store correction candidates
with session provenance, before/after span, bounded local context, language/script,
profile/app scope, evidence source, distinct-session support, explicit approvals,
rejections, undo count, creation/last-use time and policy version.

States: observed → proposed → approved → active; rejected/disabled/expired.
Manual exact entries remain authoritative unless the user disables them.
Ambiguous homophones, single letters, numbers and code identifiers never become
global replacements based only on repetition. Offer narrower phrase/context rules.
Default automatic policy: disabled; optional trusted deterministic expansion can
activate only under the user's chosen scope and an evaluated precision gate.

Recognition personalization: retrieve a token-budgeted set of approved relevant
terms, not the whole dictionary; pass hints only to capable backends. Evaluate
prompt hallucination and generic vocabulary regression. Rank alternatives only
when real decoder alternatives/redecode support exists; do not invent n-best
lists from a single transcript. Run targeted redecoding only when retained audio
and latency policy allow it. An optional local language model may propose a
correction, but may not silently change facts, names, numbers or code.

Corrections can also personalize nonsemantic preferences: preferred manually
selected mic/model/style/profile. Recommend changes first. Frequency of use is
not permission to switch language, save private audio or alter commands.

### Genuine RL/adaptation research, after the foundation

Contextual-bandit actions may choose keep/suggest or an explicitly enabled
low-risk personalization policy. Use explicit accept/reject/undo as feedback;
lack of editing is missing feedback. Store policy version and action propensity
if doing offline policy evaluation. No sensitive content needs to leave the
device. Use logged-feedback replay/shadow evaluation before opt-in experiments;
avoid overclaiming causality from biased historical selections.

Suggested utility combines explicit usefulness/correction savings with strong
penalties for undo, incorrect semantic changes and latency. Weights and confidence
thresholds must be chosen on validation data, not invented as reliable constants.
Retain a frozen baseline and rollback if the guardrail set regresses.

Weight adaptation is a separate supervised research project: consented aligned
audio/corrected transcripts, label validation, sufficient varied data, speaker/
session holdouts, compatible training/export runtime and measured battery/storage
cost. One homophone edit is not enough for robust acoustic learning. Do not train
on the recognizer's own output or ship unvalidated online fine-tuning. Keep base
weights immutable; any adapter is versioned, removable and independently tested.

## 7. Roles without fragmentation

Offer optional presets, all editable and usable without choosing a role:

- Everyday: conservative prose, names/places, messages and simple lists.
- Developer: literal identifiers, paths/flags, project vocabulary explicitly
  imported by the user, opt-in coding commands and copy-only terminal option.
- Writer/student/researcher: paragraph preservation, quotations, terminology,
  structured notes and explicit citation/name corrections without invented facts.
- Business/support: approved snippets, jargon and optional tone/templates with
  preview; avoid automatically rewriting factual details.
- Accessibility/hands-free: configurable activation, large controls, audible state,
  keyboard/screen-reader operation and optional review-before-insert.

Precedence: explicit session override → app/profile/language override → user
default. Context never weakens strict Raw/Verbatim or private mode. Browser tab
or site profiles require user-configured integrations, not inferred page reading.
One person can have several roles. Do not infer profession from their documents.

## 8. Storage, migrations and privacy controls

Add a migration version and transactional additive schema evolution. New entities:
sessions/journal; delivery_attempts; feedback_events; correction_candidates;
personalization_rules; rule_applications; profiles; model_installations. Index by
session/time/scope and bound retained event volume. Keep raw, formatted and
user-corrected text distinguishable. Do not rewrite historical asr_text as feedback.

Use minimal persisted diffs, not entire observed documents. Never log transcript
content by default. Separate audio, transcript and learning-memory retention;
proposed defaults require visible choices in onboarding/settings. Deleting a
session must offer deletion of linked learning evidence; deleting learned memory
must remove derived active rules/embeddings/adapters as applicable. Aggregated
counts must not make deleted evidence capable of reactivating a rule. Explain
that OS backups and exported copies are outside immediate app deletion.

Retain the owned-artifact checks. Add a resumable deletion journal because SQL
rollback cannot restore already deleted files. Protect database/backups with
appropriate file permissions; app-managed encryption requires OS key storage
and an explicit recovery story before claiming encrypted local privacy.

No migration should delete existing recordings or enable observation. Save a
rollback-compatible backup and test old installations with malformed configs,
interrupted migration, full disk, existing dictionary and missing audio.

## 9. Distribution and trust

Intel Mac is a real backend change: current Darwin routing always picks MLX and
packaging targets arm64. Detect architecture/capabilities, use a qualified CPU
Whisper backend on Intel, adjust dependencies/specs, and test on actual Intel
hardware. Separate arm64/x64 bundles may be simpler initially than a universal
binary with incompatible native resources. Decide macOS 13 versus 14 only after
checking API/runtime requirements; do not lower the minimum for parity alone.

Windows x64: installed WebView2/VC runtime handling, microphone/hotkey/paste/device
tests and sign/timestamp packages when publisher credentials are available.
Linux: qualify .deb first, then .rpm and AppImage with native runtime smoke tests;
do not claim distro support from changing archive format. Keep X11 explicit and
develop Wayland portal/integration support separately with capability messaging.

Mac releases require Developer ID, hardened-runtime/entitlement review, nested
native signing, notarization, stapling and clean-machine Gatekeeper checks.
Signing accounts/certificates and native hardware are external prerequisites, not
things code can manufacture. Keep credentials in CI secrets/keychain, never repo.

Each artifact needs exact source SHA, version, dependency/model notices, checksums,
installed UI/model smoke report and native acceptance record. Separate installer
publisher trust from model integrity. Preserve manual updates until authenticated
signed updater/rollback paths have independent acceptance. Host-appropriate
catalogs and website metadata must not advertise unqualified binaries/languages.

## 10. Delivery sequence: small independently reviewable changes

### A. Baseline and traceability
Changes: extend `evaluate_speech.py`, session ID/journal, structured delivery
status and bounded timings. Fixtures use synthetic/nonprivate inputs.
Exit: existing 228-test baseline retained; crash/retry/double-delivery contract
tests; versioned evaluation manifest and reproducible report for current engine.
Dependency: none. No default model or user-language change.

### B. Microphone, playback, recovery
Changes: device selection/test, hotplug handling, owned-audio playback, recovery
inbox and resumable cleanup/delete semantics. Build onboarding test flow.
Exit: real mic unplug/default switch; interrupted capture/decode recovery; no
auto-paste on retry; missing/malformed audio handled; screen-reader controls.
Dependency: A; device platform test access.

### C. Model lifecycle and qualified choices
Changes: inference contract, catalog, downloader, warm-up and selection UI;
existing Base adapter first, quality Whisper candidate second, Parakeet spike.
Exit: hash mismatch, interrupted download, full disk, incompatible model/language,
cancel/warm-up/switch races and offline startup preserve working model/session.
Run paired accuracy/resource tests; no unmeasured recommendations.
Dependency: A; backend artifact qualification. Basic onboarding uses B/C.

### D. Explicit correction learning and profiles
Changes: corrected-transcript editor, Remember/Forget, feedback schema, scoped
vocabulary retrieval, rule preview/undo, user-selected presets/app overrides.
Exit: repeat corrections improve targeted cases without changing Y/ball negative
controls; Raw/Verbatim preserved; deletion purges derived learning; zero automatic
collection by default. Test no-feedback and malicious/untrusted text inputs.
Dependency: A and stable inference contract from C.

### E. Optional observation and contextual learning
Changes: Mac native spike, Windows UIA spike, Linux feasibility; range attribution,
suggestion inbox and calibrated contextual policy in shadow mode.
Exit: explicit allowlist/activation; unsupported controls fail closed; no unrelated
text captured; undo/rewrite/IME/app-generated edits excluded; precision and
false-change guardrails pass on held-out sessions before any automatic use.
Dependency: D; native acceptance. Manual D remains useful if E coverage is narrow.

### F. Convenience and role workflows
Changes: System/Light/Dark tokens, accessible tray panels, clipboard policy,
optional approved snippets/templates and optional local rewrite experiments.
Exit: focus/clipboard races, slow recipients, modifiers, multiple monitors,
theme/contrast and permission-denial tests; transformations are explainable and
reversible. Template content never acts as agent instructions or shell execution.
Dependency: B/D; appearance work can proceed independently after contracts settle.

### G. Broader distribution and measured release
Changes: Intel backend/package, Linux formats, publisher signing CI and clean
install/upgrade reports; language/profile quality pages and accurate website.
Exit: native supported-OS matrix, offline inference, installed recovery/paste,
upgrade/downgrade data safety, public trust checks and release manifest agreement.
Dependency: C and external signing/hardware. Packaging preparation can start
earlier; advertise only after exit gates.

### H. Research beyond correction memory
Changes: opt-in bandit-assisted suggestions or supervised adapter prototype,
only if D/E supply reliable labels and demonstrable benefit.
Exit: held-out improvement, false-change/latency guardrails, shadow replay,
rollback/delete/export controls and no general-set regression.
Dependency: D/E and evaluation evidence; not a blocker for the useful product.

These are dependency order, not promised calendar dates. Native coverage and
model qualification determine effort; do not call the full program one feature
or one PR. First implementation slice should be A followed by B and explicit D,
while C validates recognition candidates. Avoid waiting for automatic observation
or a universal model catalog before delivering useful improvements.

## 11. Acceptance and measurement

Create separate baseline, development and held-out speaker/session sets. Include
English accents; domain names/numbers; quiet/fan/cafe; silence/music; long speech;
dictation into messaging, documents, supported IDEs and terminals; device/focus
changes; and selected multilingual/code-switch samples. Licensed/consented only.

Report raw WER/CER as language-appropriate; name/number/identifier exact match;
omissions; semantic changes after cleanup; correction effort; false automatic
changes; suggestion precision/coverage; accepted/rejected/undone rules; recovery
success; delivery verified versus dispatch-only; p50/p95 cold/warm stop-to-text;
main/worker/WebKit memory, CPU and battery where measurable. Aggregate word errors
by total reference words; report per-speaker strata and uncertainty, not just a
mean hiding bad subgroups. Repeat runs and pin decode/artifact versions.

Proposed initial release gates (targets, not existing measurements): zero
unrelated/sensitive text captured in observer acceptance fixtures; zero changes
to strict Raw/Verbatim; all simulated interrupted-session files recoverable or
explicitly reported; no unexpected paste during cancel/retry. Any automatic
correction cohort should meet a high precision target (initial target 99% with
adequate sample size and a reported confidence bound) plus zero critical changes
on protected-name/number/code cases; otherwise keep suggestion-only. Compare
general-corpus regressions using a preregistered paired tolerance/uncertainty
rule before tuning, and publish p95 device budgets once baseline hardware runs
exist. Never imply 99% speech accuracy from a correction-policy precision target.

A replay harness must explicitly test Y/why, ball/bawl, valid capitals, identifiers,
quoted corrections, reversed edits, intentional rewriting, repeated same-session
edits, cross-language collisions, prompt echo, unsupported observers and deletes.
Do not count ten edits of one session as ten independent supporting examples.

## 12. Decisions and external prerequisites

Fixed direction: local-first; existing durability preserved; explicit scoped
learning; no perfect-recognition claim; role presets optional; measure before
default model changes. Confirmed learning default is proposals requiring approval;
the user confirmed this preference on 2 November 2026. Later automatic use of
trusted patterns remains a separate opt-in, not implied by enabling suggestions.

Before respective releases, choose: supported-app pilot list; language/script
priorities (English first, Hindi/Roman Hinglish evaluated separately); retention
defaults; target hardware/resource budgets; permitted automatic corrections;
publisher accounts/certificates and real-device test access. None is necessary
to finish this plan or start the session/evaluation foundation.

## Sources and evidence limits

Local owners inspected: core, recorder, current inference backends, model packs,
learner, storage, platform delivery contract and packaging; baseline context and
comparison are in docs 18/19. This turn produces planning artifacts, not trained
models, live observation or a new verified application build.

- [Pinned SpeakType desktop](https://github.com/karansinghgit/speaktype/tree/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop): inspiration and contrasts; not transplanted source.
- [NVIDIA Parakeet v3 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3): 25 European languages; model license and deployment details. A converted runtime still needs independent qualification.
- [Microsoft text event documentation](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-handlingtextrelatedevents): text/selection notifications; event availability alone does not establish edit authorship or successful range attribution.
- Apple and Linux observation APIs require native feasibility/documentation validation in phase E; their full documentation was not successfully retrieved during this planning pass.
