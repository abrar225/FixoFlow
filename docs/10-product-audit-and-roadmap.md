# Fixo Flow: product audit and decision backlog

**Historical audit snapshot.** The findings below describe the pre-implementation product. Current fixes, user decisions and remaining gates are tracked in [the 0.3.0 implementation report](11-reliability-and-multilingual-preview.md).

Date: 18 October 2026. Role: Desktop reliability engineer and speech-product architect.

## Recommendation

Fix reliability and text integrity before expanding the feature surface. The product has useful foundations: offline local inference, recoverable capture, separate hold/hands-free controls, shared UI/coordinator, and raw/processed transcript persistence. The largest value is making those foundations predictable across supported systems, then adding selected languages and optional cloud assistance.

This pass records **33 findings**: 15 defects demonstrated by isolated reproduction or confirmed in source, plus 18 capability/design/release/validation findings and risks. These are not 33 native runtime bugs. No finite audit proves every possible issue has been found.

Read-only product audit. Existing uncommitted signing/site work preserved. No app/config/model changes or user recordings/history accessed. Offline by default; optional cloud evaluation. No provider, model, retention default or new feature selected.

P1 means resolve or explicitly gate before widening public release. P2 means next product/reliability work. P3 means lower-priority cleanup. Ordering is a recommendation, not approval to implement product defaults. All items are open.

## What was actually checked

- Current desktop source across capture, filtering, slicing, both inference backends, formatting, learning, config, session/input controllers, platform adapters, persistence, UI and updates; applicable tests and packaging/release documentation. Source baseline is commit `19c8bf8` plus the existing uncommitted signing/site preparation. See source inventory for hashes of inspected product inputs.
- Local suite: **147 passed, 2 skipped, 1.44 seconds**. Passing tests do not negate the isolated regressions below; most inference/input tests use mocks.
- Isolated input/temporary-database/text examples reproduced defects without microphone, clipboard, real keystrokes, other-app focus or user history.
- Native Mac speech diagnostic used the installed Base English model on one locally generated 7.123875-second English sentence. Words were exact when clean, at +20 dB and +5 dB additive Gaussian noise (levels computed using full-clip RMS, including pauses), and in a warm repeat. One second of silence and one second of noise returned empty text. This probe did **not** reproduce a silence hallucination; an earlier dated probe did. Behavior is not uniform and must be measured.
- Diagnostic decode/preprocessing times were 0.832/0.100/0.094/0.050/0.049/0.098 seconds in that order. Main-process peak RSS was 459.4 MiB; elapsed decode-loop time 1.226 s, user CPU 0.788 s, system CPU 0.218 s. TTS generation and pre-loop imports are excluded from that elapsed loop; first decode includes lazy backend initialization. CPU counters are cumulative process values, including imports. The first call is not a controlled cold-filesystem run. No GUI/WebKit family, Windows/Linux, live microphone, learner vocabulary, formatting, delivery, battery, accent or café/babble benchmark was measured. This is a diagnostic, not a latency SLA or head-to-head product score.
- Separate filtering-only synthetic probes (single runs) showed peak main-process RSS rising from 96.8 MiB baseline to 118.7 MiB for one minute and 353.1 MiB for ten minutes. Model/UI memory excluded. These measure processing allocation scaling, not production memory or real-speech accuracy.
- Installed Wispr Flow 1.6.1174 artifact identity and narrow static comparison, plus current official workflow documentation. Details/limits appear below. No private reference history, live dictation, screen context or network traffic was inspected.

## Fixes and gaps, with acceptance criteria

### D01 · P1 · Shortcut suppression can leave unmatched modifier events

**Reproduced defect · macOS, Windows · Open**

Evidence: Real router with Ctrl+Space, modifier released first: Ctrl-down passed, Space-down suppressed, Ctrl-up suppressed, Space-up passed. Native stuck-key effect not reproduced.

User impact: Another application can observe an unbalanced key sequence; potential stuck modifier or stray input.

Proposed fix: Own suppression per physical down/up pair, separately from session transitions; handle repeat, capture, reset and listener replacement.

Acceptance: Both release orders, left/right modifiers, capture cancellation and focus changes pass raw-edge tests and native editor tests with balanced events.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/shortcuts.py:129](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/shortcuts.py:129>), [fixoflow/input_listener.py:64](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/input_listener.py:64>), [fixoflow/daemon.py:58](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/daemon.py:58>).

### D02 · P1 · Escape is intercepted while idle

**Reproduced defect · macOS, Windows · Open**

Evidence: Idle router consumes Escape-down and calls cancel; Escape-up is passed.

User impact: Escape can stop working in unrelated dialogs/apps.

Proposed fix: Consume Escape only for an owned active cancellation/capture and pair its edges.

Acceptance: Idle Escape behaves normally; active cancellation happens once and releases remain balanced.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/shortcuts.py:170](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/shortcuts.py:170>).

### D03 · P1 · Delete History leaves audio and transcript files

**Reproduced defect · macOS, Windows, Linux · Open**

Evidence: Temporary DB: deleting a row or clearing History leaves its WAV and .transcript.json on disk.

User impact: The deletion UI does not express the remaining sensitive files; disk use grows.

Proposed fix: Define explicit transcript-only versus entire-session deletion; track owned WAV/sidecars and cleanup failures. Do not erase existing recordings without approval.

Acceptance: Chosen deletion scope matches DB/files, failed deletion is retryable, unrelated paths cannot be deleted and in-flight sessions remain safe.

Decision: Choose deletion scope and existing-data migration before implementation.

Sources: [fixoflow/storage/db.py:212](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/storage/db.py:212>), [fixoflow/core.py:241](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:241>), [fixoflow/ui/controller.py:102](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/controller.py:102>).

### D04 · P1 · Punctuation cleanup changes ordinary prose

**Reproduced defect · macOS, Windows, Linux · Open**

Evidence: “This period was difficult” becomes “This. Was difficult”; “The colon is part of the body” becomes “The: is part of the body”.

User impact: Correct recognition can be changed into incorrect final text.

Proposed fix: Separate explicit spoken formatting commands from literal prose; retain raw text and reversible edits.

Acceptance: Literal-word and intentional-command corpus passes; semantic changes are scored separately from raw ASR errors.

Decision: Choose command opt-in/default and literal escape syntax.

Sources: [fixoflow/brain/polisher.py:61](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/polisher.py:61>), [fixoflow/brain/polisher.py:123](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/polisher.py:123>).

### D05 · P1 · Bullet formatting deletes the first content word

**Reproduced defect · macOS, Windows, Linux · Open**

Evidence: “bullet buy milk” becomes “• Milk”; “bullet point apples and bananas” becomes “• And bananas”.

User impact: User content is silently removed by formatting.

Proposed fix: Replace arbitrary-word consumption with a narrowly defined command grammar.

Acceptance: List content survives exactly; literal discussions of bullets remain literal when commands are disabled.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/brain/polisher.py:70](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/polisher.py:70>).

### D06 · P1 · Verbatim still applies dictionary substitutions

**Reproduced defect · macOS, Windows, Linux · Open**

Evidence: Writing + Verbatim transforms a custom dictionary term before the polisher bypass; UI promises recognizer output untouched.

User impact: The output mode fails its stated contract.

Proposed fix: Give the complete pipeline one output policy; strict verbatim bypasses all transformations, or rename the promise.

Acceptance: Coordinator tests compare recognizer/final text with dictionary, code patterns and every style.

Decision: Choose strict verbatim versus dictionary-assisted wording; recommend strict verbatim.

Sources: [fixoflow/core.py:136](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:136>), [fixoflow/brain/learner.py:138](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/learner.py:138>), [fixoflow/ui/hub.html:388](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/hub.html:388>).

### D07 · P1 · Dictionary correction cascades and symbol terms fail

**Reproduced defect · macOS, Windows, Linux · Open**

Evidence: alpha→beta plus beta→gamma can produce beta or gamma as usage order changes. A C++→CPP rule fails on “use C++ for this”.

User impact: Personal corrections become unpredictable, especially technical/product names.

Proposed fix: Use one deterministic longest-match pass over original text with Unicode/symbol-aware boundaries and literal replacements.

Acceptance: Results do not change with usage order; overlapping phrases, C++, C#, possessives and Unicode terms pass.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/brain/learner.py:151](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/learner.py:151>), [fixoflow/storage/db.py:279](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/storage/db.py:279>).

### D08 · P1 · Saved dictionary entries silently fall outside active coverage

**Source-confirmed defect · macOS, Windows, Linux · Open**

Evidence: Correction code requests only 200 entries; dictionary UI requests 100 without pagination. Prompt top-25 is a separate, legitimate context budget.

User impact: Valid saved terms can become inactive or invisible as vocabulary grows.

Proposed fix: Separate complete correction coverage from prompt budgeting; page/search/edit the full dictionary.

Acceptance: More than 200 entries remain correctable, discoverable and editable with bounded lookup cost.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/brain/learner.py:151](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/learner.py:151>), [fixoflow/ui/controller.py:114](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/controller.py:114>).

### D09 · P1 · Failed capture finalization has no user retry path

**Source-confirmed defect · macOS, Windows, Linux · Open**

Evidence: Recorder retains failed resources for retry, but coordinator returns IDLE; next start rejects previous cleanup. Low-level retry tests exist; end-to-end coordinator recovery is missing.

User impact: A recoverable writer/close problem can prevent subsequent dictation until restart.

Proposed fix: Model FINALIZING/RECOVERY_REQUIRED explicitly and expose retry through the owning coordinator.

Acceptance: Stalled writer/close fails, later recovers, and a new session works without restart; retained audio/error ownership is preserved.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/audio/recorder.py:125](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/recorder.py:125>), [fixoflow/audio/recorder.py:178](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/recorder.py:178>), [fixoflow/core.py:194](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:194>).

### D10 · P1 · Mac paste has no final target check

**Source-confirmed defect · macOS · Open**

Evidence: Coordinator checks identity, then Mac adapter writes clipboard, waits 50 ms and posts Cmd+V without rechecking focus. Mock observed zero adapter-side focus checks.

User impact: A focus change or held modifier can misdirect the paste; actual wrong-target insertion not reproduced.

Proposed fix: Carry expected target identity into the adapter, revalidate immediately before dispatch and fall back to copy when unresolved.

Acceptance: Native cross-app, same-app window and held-modifier scenarios never insert into unintended targets.

Decision: Confirm whether focus restoration is desired; recommend no focus stealing.

Sources: [fixoflow/core.py:214](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:214>), [fixoflow/platform/macos.py:195](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/macos.py:195>).

### D11 · P2 · Document titles drive app identity and formatting

**Reproduced defect · Windows · Open**

Evidence: Windows returns window title as app name. “Invoice codes - Notepad” selects coding; “Shopping list - Notepad” selects writing.

User impact: Document text changes formatting and fragments app analytics; titles may reveal unnecessary context.

Proposed fix: Use stable executable/package identity and friendly app name; keep document title separate and optional.

Acceptance: Changing a document title does not change default mode or analytics grouping; titles are not retained by default.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/platform/windows.py:44](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/windows.py:44>), [fixoflow/brain/learner.py:118](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/learner.py:118>), [fixoflow/core.py:154](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:154>).

### D12 · P1 · Recording indicator stays hidden when idle visibility is off

**Source-confirmed defect · Windows, Linux · Open**

Evidence: Desktop only shows the pill for always-show/manual show; poll updates content but does not reveal active recording. Mac has state-based visibility.

User impact: Keyboard-triggered recording may have no visible recording/cancel indicator.

Proposed fix: Show pill for recording/processing/outcome; apply hide preference only to idle.

Acceptance: Preference off + hotkey start displays recording and cancel, then returns to hidden idle.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/desktop_app.py:60](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:60>), [fixoflow/desktop_app.py:149](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:149>), [fixoflow/desktop_app.py:175](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:175>).

### D13 · P2 · Permission UI reports unknown states as Mac setup

**Source-confirmed defect · Windows, Linux · Open**

Evidence: Desktop mic is always not determined; later refresh rewrites initial platform guidance to Mac text. Some Mac-only permission actions do nothing.

User impact: Users get misleading setup instructions and cannot distinguish denied, missing or busy input.

Proposed fix: Use a shared typed capability/permission/availability model and host-specific actionable instructions.

Acceptance: Refocus/repeated refresh preserves correct platform copy; denied, missing, busy and successful mic states are distinct.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/platform/windows.py:117](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/windows.py:117>), [fixoflow/platform/linux.py:80](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/linux.py:80>), [fixoflow/ui/hub.html:248](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/hub.html:248>), [fixoflow/ui/hub.html:561](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/hub.html:561>).

### D14 · P2 · Unrelated settings changes discard the warm CPU model

**Source-confirmed defect · Windows, Linux · Open**

Evidence: Every preferences save constructs a new STT engine; CPU engine starts with _model=None. Mac also recreates wrapper but library cache cost differs.

User impact: Changing sounds/overlay can cause another model load; actual latency penalty not measured.

Proposed fix: One config owner computes resource changes; only replace inference resources when affected.

Acceptance: Warm CPU model identity persists across unrelated changes; invalid model replacement keeps a working configuration.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/desktop_app.py:137](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:137>), [fixoflow/stt/cpu.py:14](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/stt/cpu.py:14>), [fixoflow/app.py:344](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/app.py:344>).

### D15 · P3 · Audio filter ignores custom cutoff arguments

**Reproduced defect · macOS, Windows, Linux · Open**

Evidence: Two disjoint requested cutoff ranges produce identical output because apply_bandpass always uses default filter. Default product path is not shown broken.

User impact: Internal API is misleading and future tuning would be ineffective.

Proposed fix: Honor cutoff parameters in filter design/cache or remove unsupported arguments.

Acceptance: A 1 kHz tone is preserved by its passband and rejected outside it; default behavior remains characterized.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/audio/filter.py:39](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/filter.py:39>), [fixoflow/audio/filter.py:56](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/filter.py:56>).

### G01 · P1 · No demonstrated real-world noise robustness

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Preprocessing is bandpass + normalization; CPU VAD is off; no application-level padded speech gate/quality indicator. A small local TTS/Gaussian-noise probe passed, not a representative benchmark.

User impact: Fan, babble, TV, typing, soft speech and clipping remain uncharacterized; quiet noise can be amplified up to 12×.

Proposed fix: Baseline real speech/noise first; evaluate padded VAD, capture quality warnings and optional local denoising against unchanged baseline.

Acceptance: Held-out clean/noisy speech at multiple levels measures WER/CER, names/numbers, silence false text, boundary loss, latency and CPU/RAM.

Decision: Choose denoiser/VAD only after paired quality/performance comparison; none selected.

Sources: [fixoflow/audio/filter.py:83](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/filter.py:83>), [fixoflow/stt/cpu.py:41](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/stt/cpu.py:41>), [fixoflow/stt/engine.py:78](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/stt/engine.py:78>).

### G02 · P1 · Multilingual dictation is not implemented end to end

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Bundled base.en, English prompts/rules, no language selector/update action and no model-language validation.

User impact: Adding a dropdown alone will not produce reliable non-English/mixed-language dictation.

Proposed fix: Evaluate multilingual model packs for both MLX/CPU; language/script-aware prompts and formatting; explicit local or optional cloud selection.

Acceptance: Per-language WER/CER and code-switch tests; scripts/names/numbers survive; storage/RAM costs and model compatibility shown before selection.

Decision: First languages, script preferences and code-switch pairs await user choice.

Sources: [fixoflow/config.py:33](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/config.py:33>), [fixoflow/brain/learner.py:168](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/learner.py:168>), [fixoflow/ui/controller.py:149](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/controller.py:149>).

### G03 · P1 · Long sessions still load and filter the whole recording

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Capture queue is bounded, but stop reads full WAV and uses whole-buffer filter intermediates. Cancel also invokes this work.

User impact: RAM/disk cost grows with recording length; especially relevant to long hands-free sessions and low-end PCs.

Proposed fix: Separate capture finalization from file-backed bounded chunk processing; make cancel preserve the file without full filtering.

Acceptance: 1/10/60-minute sessions have measured bounded working memory, responsive cancel and retained recovery with no lost boundary words.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/audio/recorder.py:214](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/recorder.py:214>), [fixoflow/audio/filter.py:57](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/filter.py:57>), [fixoflow/core.py:252](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:252>).

### R01 · P1 · Chunk boundaries can cut speech; sample retention is not word accuracy

**Unverified risk · macOS, Windows, Linux · Open**

Evidence: Minimum-energy split need not be a true pause. Chunks do not overlap despite docstring; output concatenation has no timestamp reconciliation.

User impact: No proof of missing/repeated words on continuous/noisy speech; zero audio-sample loss is not zero transcript loss.

Proposed fix: Evaluate VAD-aligned chunks, bounded overlap and timestamp reconciliation against recorded boundary cases.

Acceptance: Continuous speech crossing every boundary has no added omissions/repetitions beyond the measured baseline.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/audio/slicer.py:16](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/slicer.py:16>), [fixoflow/audio/slicer.py:92](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/slicer.py:92>), [fixoflow/stt/engine.py:95](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/stt/engine.py:95>).

### G04 · P1 · No microphone choice, calibration or device recovery UI

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Recorder opens default device at 16 kHz mono; no stable selected-device identity, capability negotiation or hotplug recovery.

User impact: Users cannot deliberately select/test headsets or diagnose poor/absent input. Not all devices are proven incompatible.

Proposed fix: Add device selector, explicit test, level/clipping/noise guidance, one sample-rate negotiation/resampling owner and reconnect recovery.

Acceptance: Laptop/USB/Bluetooth, mute/deny/busy/unplug/suspend and non-16k native devices pass per-OS physical tests.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/audio/recorder.py:159](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/audio/recorder.py:159>).

### G05 · P1 · Recovery files have no usable recovery inbox

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Failed/cancelled/no-speech recordings can exist only on disk; no History row/retry browser. Cancel tooltip incorrectly says audio stays in History.

User impact: Recovery exists technically but is hard to discover or use.

Proposed fix: Owned session ledger with status, raw/final text, retry/copy/export/delete and clear audio retention.

Acceptance: Interrupted/failed/cancelled sessions are discoverable, retryable and deletable without exposing unrelated files.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/core.py:182](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:182>), [fixoflow/core.py:252](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:252>), [fixoflow/ui/overlay.html:97](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/overlay.html:97>).

### G06 · P1 · No retention/private-session controls

**Capability gap · macOS, Windows, Linux · Open**

Evidence: WAV, plaintext sidecars and SQLite persist; no retention duration, quota, private session or user-facing storage summary.

User impact: Offline processing does not itself mean encrypted storage or deleted data.

Proposed fix: Offer explicit retention/private mode, owner-only storage permissions, storage meter and export; assess OS-backed encryption against a chosen threat model.

Acceptance: Retention follows the chosen policy across success/failure/recovery, storage bounds are visible and deletion failures remain owned.

Decision: Choose retention default and migration; never silently remove existing recordings.

Sources: [fixoflow/config.py:46](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/config.py:46>), [fixoflow/storage/db.py:19](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/storage/db.py:19>), [fixoflow/core.py:241](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:241>).

### R02 · P1 · Original editable field is not owned across processing

**Unverified risk · macOS, Windows, Linux · Open**

Evidence: Mac tracks app bundle only; Windows/Linux track window/process identity, not original control/caret. Coordinator may restore app focus.

User impact: Switching document/field within an app may place output somewhere unintended. Secure/password/elevated fields need explicit handling.

Proposed fix: Verify target control/window when available; safe clipboard-only fallback, user-controlled focus restoration and sensitive-field policy.

Acceptance: Test same-app documents, tabs, caret moves, password/secure fields, elevated apps and focus changes during decode.

Decision: Choose focus restoration, clipboard preservation and sensitive-field behavior.

Sources: [fixoflow/core.py:205](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/core.py:205>), [fixoflow/platform/macos.py:131](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/macos.py:131>), [fixoflow/platform/windows.py:26](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/windows.py:26>), [fixoflow/platform/linux.py:17](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/linux.py:17>).

### G07 · P2 · Processing cannot be cancelled safely

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Controls cancel acts on recording, not active decode; shutdown waits for worker.

User impact: Long/hung transcription can hold attention or delay quit.

Proposed fix: Cooperative chunk cancellation/progress; consider owned worker isolation if hard cancellation is needed.

Acceptance: Cancel never causes later auto-paste, retains recoverable audio, and quit completes within a measured bound.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/controls.py:96](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/controls.py:96>), [fixoflow/controls.py:113](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/controls.py:113>).

### G08 · P2 · History/dictionary management stops at small lists

**Capability gap · macOS, Windows, Linux · Open**

Evidence: History latest 50 (search still capped); dictionary first 100; no paging/import/export/edit workflow for full vocabulary.

User impact: Growing use makes previous work and vocabulary hard to find/manage.

Proposed fix: Paged date-grouped history, full search and counts, raw/final comparison; dictionary edit/search/import/export.

Acceptance: Thousands of entries stay searchable and responsive; supported import validation and partial failures are understandable.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/ui/controller.py:96](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/controller.py:96>), [fixoflow/ui/controller.py:114](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/controller.py:114>), [fixoflow/ui/hub.html:198](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/ui/hub.html:198>).

### G09 · P2 · Background-app behavior lacks Mac parity

**Capability gap · Windows, Linux · Open**

Evidence: Closing desktop exits; no native tray/background preference; second launch does not reopen running hub.

User impact: Users may believe dictation still runs after closing, or cannot find an already running app.

Proposed fix: Tray, reopen IPC and explicit close/background/quit semantics; optional launch at login with no surprise recording.

Acceptance: Close/reopen/relaunch/quit and restart work predictably without duplicate instances or unintended mic activation.

Decision: Confirm desired close-to-background and launch-at-login defaults.

Sources: [fixoflow/desktop_app.py:111](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:111>), [fixoflow/desktop_app.py:201](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:201>).

### G10 · P2 · Overlay geometry is primary-screen oriented

**Capability gap · Windows, Linux · Open**

Evidence: Desktop positions fixed 600×96 rectangle using primary screen and implements only limited drag messages.

User impact: Multi-monitor, taskbar/work-area, scaling and hit-testing are unverified.

Proposed fix: Shared placement/resize/drag contract with DPI-aware work areas and monitor ownership.

Acceptance: Mixed DPI, screen attach/remove, taskbar changes, corners and compact click-through bounds pass native tests.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/desktop_app.py:156](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:156>), [fixoflow/desktop_app.py:164](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:164>).

### G11 · P1 · Trusted public distribution remains incomplete

**External release gate · macOS, Windows, Linux · Open**

Evidence: Windows unsigned; Mac locally signed/not notarized. Enrollment absent. Linux package repository trust not configured.

User impact: Installation warnings/policy blocks remain; this is not fixed by lowering OS security.

Proposed fix: Choose eligible publisher signing identity; Developer ID/hardened notarized Mac build; signed distro repository and clean download acceptance.

Acceptance: Final immutable artifacts pass native trust checks and clean browser install/upgrade/uninstall tests with protections enabled.

Decision: Publisher identity/accounts and Linux distribution scope require user action/choice.

Sources: [docs/09-public-distribution.md:1](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/docs/09-public-distribution.md:1>).

### G12 · P1 · Signed automatic updates are not operational across platforms

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Windows/Linux discover release metadata but do not install signed updates; Mac optional Sparkle path/feed still requires production configuration/verification.

User impact: An update toggle alone cannot deliver safe upgrades or rollback.

Proposed fix: Signed versioned channels/feed, authenticated artifact verification, staged rollouts, user-controlled download/install and recovery/migrations.

Acceptance: Tampered/old/wrong-platform update rejected; upgrade/uninstall preserves chosen user data; interrupted update and rollback tested.

Decision: Choose update channels/defaults after signing is available; keep automatic install disabled until verified.

Sources: [fixoflow/updates.py:117](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/updates.py:117>), [fixoflow/platform/macos_updates.py:1](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/macos_updates.py:1>), [fixoflow/desktop_app.py:134](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/desktop_app.py:134>).

### G13 · P2 · Broken configuration has no guided startup recovery

**Capability gap · macOS, Windows, Linux · Open**

Evidence: Malformed JSON or invalid supported values raise during load. Original is preserved, but no guided repair/safe-mode workflow exists.

User impact: Users can be blocked at startup instead of receiving an actionable recovery choice.

Proposed fix: Preserve invalid file; offer validated last-good settings/read-only diagnostics and explicit repair, not silent overwrite.

Acceptance: Corrupt, partial, old-version and invalid model/language configs recover without losing recordings or shortcut choices.

Decision: No behavior choice implemented; approve work first.

Sources: [fixoflow/config.py:75](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/config.py:75>), [fixoflow/config.py:130](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/config.py:130>).

### G14 · P1 · Platform support exceeds executed physical acceptance

**Validation gap · macOS, Windows, Linux · Open**

Evidence: Mac Apple Silicon 14+; Windows 11 x64 preview, Win10 22H2 target unverified; Ubuntu24.04 X11 preview. Wayland controls, other distros/ARM/Intel Mac unsupported or unverified.

User impact: Passing CI UI/synthetic inference does not prove real mic/input/paste across user machines.

Proposed fix: Publish a support matrix; acceptance on Intel/AMD, low-end PCs, clean installs, layouts/IME, Fn/media keys, mouse buttons, reserved shortcuts, RDP/VM, sleep/hotplug and security boundaries. Some firmware Fn keys never reach the OS; X11 shortcut monitoring may also allow the trigger into the foreground app. Do not promise every physical key is capturable.

Acceptance: Each advertised OS/architecture has signed artifacts, real capture/input/delivery and clean upgrade evidence.

Decision: Choose Linux distributions/Wayland priority, Intel Mac/ARM scope and minimum hardware budget.

Sources: [docs/08-multiplatform-release.md:1](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/docs/08-multiplatform-release.md:1>), [fixoflow/input_listener.py:47](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/input_listener.py:47>), [fixoflow/platform/linux.py:11](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/platform/linux.py:11>).

### G15 · P1 · No representative accuracy/performance benchmark

**Validation gap · macOS, Windows, Linux · Open**

Evidence: Existing tests mostly contracts/mocks. Tiny real-model probe passed but no held-out accents/noise/languages corpus, p95 delivery latency or full process-family/battery measurements.

User impact: No defensible claim of universally accurate, low-memory or faster-than-reference dictation.

Proposed fix: Versioned consented/public corpus; separate raw ASR, formatting and delivery metrics; equivalent low-end/typical-machine tasks, cold and warm runs.

Acceptance: Report per-language/noise WER/CER, number/name/omitted-clause errors, false text, p50/p95 stop-to-paste, CPU, family peak RAM, energy and package sizes.

Decision: No behavior choice implemented; approve work first.

Sources: [tests/test_stt.py:1](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/tests/test_stt.py:1>), [tests/test_audio_filter.py:1](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/tests/test_audio_filter.py:1>), [docs/08-multiplatform-release.md:1](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/docs/08-multiplatform-release.md:1>).

### G16 · P2 · Universal dictation still receives developer-oriented vocabulary

**Source-confirmed design limitation · macOS, Windows, Linux · Open**

Evidence: Default vocabulary seeds developer terms and every prompt includes Claude Code, Antigravity, Codex and ChatGPT, even writing mode.

User impact: This is a source-confirmed bias in prompts; actual accuracy harm in ordinary prose remains unmeasured.

Proposed fix: Neutral general vocabulary by default; explicit domain packs and per-app profiles, only approved terms in learning.

Acceptance: General and technical corpora compared; user choices govern domain packs; no self-reinforcing learning from uncorrected model output.

Decision: Choose intended first audience/domain packs; audience question remains pending.

Sources: [fixoflow/brain/learner.py:109](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/learner.py:109>), [fixoflow/brain/learner.py:168](</Users/abrarakhunji/Desktop/reverse  Enginner/fixoflow/fixoflow/brain/learner.py:168>).

## Background-noise improvement plan

1. Establish capture quality first: selectable input, stable device identity, input-format negotiation, clipping/low-level indicators, unplug/sleep handling and a bounded recovery path. Bandpass filtering is useful for rumble; it does not remove competing speech or restore clipped information.
2. Create held-out recordings across quiet rooms, fans, keyboards, traffic, café babble, TV/music, soft speech, accents and near/far microphones. Measure clean and noisy versions of the same utterances at defined levels, including no-speech and very short phrases. Use public/consented recordings; do not upload user recordings implicitly.
3. Evaluate padded voice-activity detection (VAD) with pre-roll/hangover so short words/whispers are not cut. VAD detects speech presence; it is not a denoiser or speaker-identity system. [Silero VAD](https://github.com/snakers4/silero-vad) is one candidate, not a selected dependency. The previous packaging omitted its runtime for size, so adding it has a measurable size/RAM cost.
4. Compare unchanged audio against optional local enhancement candidates such as [RNNoise](https://github.com/xiph/rnnoise) or [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet). Check native sample-rate requirements, CPU budget, license/model distribution and ASR accuracy. Cleaner-sounding audio can still worsen recognition, and denoisers can remove soft speech. No denoiser was installed in this audit.
5. Evaluate model/decoding tiers and the approved optional-cloud direction only after a baseline. Preserve language/script and user meaning; never silently upload a failed local recording or substitute a lower-quality model. Background speakers are still speech: treating VAD as a way to ignore them would be incorrect.
6. Release only measured gains: raw WER/CER, proper names/numbers/negations, omitted clauses, no-speech false text, formatting semantic preservation, boundary continuity, p50/p95 stop-to-paste, CPU and full process-family peak RAM. Report clean-speech regressions too. Whisper’s [model card](https://github.com/openai/whisper/blob/main/model-card.md) explicitly describes hallucination and language/accent variation; no “perfect in any noise” claim is justified.

## Features worth considering

These are proposals ranked for user value and dependency order, not selected implementations. “First” means a candidate accompanying reliability work, not that every item must ship together.

### F01 · Speak in your language · Next

Value: Selected languages, scripts and mixed-language dictation with local model packs.

Tradeoff: Larger models/downloads and per-language CPU/accuracy testing; first languages pending.

Success: Language/script preserved; code-switch corpus and model compatibility pass.

### F02 · Microphone checkup · First

Value: Choose a microphone, see live levels and practical low-volume/noise/clipping guidance.

Tradeoff: Explicit mic test consent; native device/hotplug work.

Success: Works with laptop, USB and Bluetooth on each supported OS.

### F03 · Your words, reversible · First

Value: Compare recognizer output with formatted text; restore original and correct safely.

Tradeoff: History retention/user privacy choice; avoid blind undo in another app.

Success: Every transformation is recoverable without overwriting unrelated edits.

### F04 · Recovery inbox · First

Value: Find interrupted recordings, retry transcription, copy/export or erase them.

Tradeoff: Owned file lifecycle and clear retention; local audio remains sensitive.

Success: Failed/cancelled sessions recover without filesystem hunting.

### F05 · My vocabulary · First

Value: Explicit corrections, names and terminology, searchable/editable with import/export.

Tradeoff: Approved learning only; deterministic Unicode/symbol handling.

Success: Correction provenance visible; large dictionaries behave predictably.

### F06 · Voice snippets · Next

Value: Speak a distinctive trigger to insert a signature, address or reusable reply.

Tradeoff: Collision/literal handling and confirmation for sensitive snippets; no arbitrary actions.

Success: Whole phrase and formatting survive supported destinations; duplicates handled.

### F07 · App profiles · Next

Value: Email, chat, plain writing and code styles chosen per app.

Tradeoff: Stable app identity; optional context access must be explicit.

Success: Profile selection remains consistent across documents and respects manual override.

### F08 · Private session · First

Value: One clear mode governing history/audio retention and cloud use.

Tradeoff: Retention/deletion policy and existing-data migration require approval.

Success: UI promise matches all files, logs and any optional network processing.

### F09 · Choose speed or detail · Next

Value: Measured low-resource/balanced/accuracy profiles and clear model size.

Tradeoff: Quantization/model/beam changes may change words; never silently downgrade quality.

Success: Paired quality and CPU/RAM/latency results before selecting defaults.

### F10 · Optional cloud assist · Next

Value: Explicitly choose online recognition or rewriting when local output is insufficient.

Tradeoff: User approved evaluation, not a provider or upload; consent, cost/retention/region controls required.

Success: Offline remains default; no silent fallback, upload or training; visible per-session processing location.

### F11 · Hands-free editing · Later

Value: Opt-in commands for paragraph, list, correction and cancel with a literal escape.

Tradeoff: Command ambiguity, accessibility and cross-app undo safety; no auto-send actions.

Success: Ordinary prose never triggers destructive actions; cancellation cannot paste later.

### F12 · Accessible everywhere · First

Value: Screen-reader and keyboard flows, localization/RTL, consistent tray/pill and clear progress.

Tradeoff: Native assistive-tech and DPI testing; reduced-motion support already exists.

Success: Core dictation, recovery/settings work without a mouse and with assistive tech.

### F13 · Local audio-file transcription · Later

Value: Transcribe an explicitly selected recording into editable/exportable text.

Tradeoff: Long-file memory/cancellation, rights/consent and model language support; separate from meeting capture.

Success: Large files process with bounded memory and visible progress; no unsolicited recording.

## What to learn from Wispr Flow

Learn its workflows rather than copy its implementation or assume its accuracy. Official documentation describes a Home page with date-grouped searchable dictations, quick copying and stats; a selected-microphone test; manageable dictionary/snippets; and explicit data controls. For Fixo Flow, the corresponding priorities are a recovery-first history, clear capture setup, deterministic vocabulary, explicit optional processing and usable privacy controls. [Desktop navigation](https://docs.wisprflow.ai/articles/5096240724-navigating-the-wispr-flow-app-desktop-ios-and-android), [microphone setup](https://docs.wisprflow.ai/articles/9192039587-using-wispr-flow-discreetly-microphone-guide).

Wispr documents correction-based vocabulary learning when enabled and reusable spoken-trigger snippets. Fixo Flow should make accepted corrections explicit, preserve provenance, expose editing/import/export and avoid learning from its own uncorrected output. [Dictionary](https://docs.wisprflow.ai/articles/4052411709-Teach-Flow-your-words-with-the-dictionary), [snippets](https://docs.wisprflow.ai/articles/5784437944-create-and-use-snippets).

Its current language documentation separates language selection from script variants and calls out special mixed-language behavior. Fixo Flow should validate selected languages/scripts and code-switch pairs independently; a language count is not a quality score. The vendor documents cloud transcription, so these workflows do not prove comparable offline model performance. [Languages](https://docs.wisprflow.ai/articles/3191899797), [processing/privacy](https://docs.wisprflow.ai/articles/3467817258-security-and-compliance-faq).

Installed artifact: version 1.6.1174, ASAR digest `dc56b610fb46d34dabf7871a270f307c665371de3f28b492c687eca2af09faf4`. REA Evidence `ev_abc704b547ef456513716446dda63122aba962d42a37839514143e16ac9e4839`. Selected package.json/main only; 181 files unselected; main semantic analysis exhausted worker heap. Three unpacked native integrity contradictions recorded; this is not a malware diagnosis. No full reverse engineering, network interception, reference dictation execution or private history access. Installed main bytes match previous extracted main SHA b2295c53e0029194248d2c12e84e3f26241c758cb0690dc1ed8a35f1f8fa824b. Bounded ordinary static snippets show auto-learning preference, cloud voice-preference upload and local UserContext declarations; not runtime behavior. Current vendor docs may describe newer capabilities than the installed build. No full UI/runtime reconstruction or measured comparison with Wispr was completed; no claims of Fixo superiority or Wispr defects follow from this pass.

## Proposed implementation order

Signing enrollment and supported-platform test hardware can be arranged alongside Phase A. No calendar or exact effort promise is made before choices and a baseline.

### Phase A: Reliability and text safety

D01, D02, D03, D04, D05, D06, D07, D08, D09, D10, D12, G05, G06, R02.

Exit gate: Native input/target tests, exact text-preservation regressions, owned recovery/deletion lifecycle. Defaults requiring product choices remain pending.

### Phase B: Measurement and microphone quality

G01, G03, R01, G04, G07, G15.

Exit gate: Baseline corpus and clean/noisy device matrix, then paired VAD/denoiser/model candidates; no guessed accuracy claims.

### Phase C: Multilingual and useful personalization

G02, G08, G16, D11, D14.

Exit gate: User-selected languages/audience, deterministic vocabulary, script-preserving output and measured model-pack tradeoffs.

### Phase D: Platform and release readiness

D13, G09, G10, G11, G12, G13, G14, D15.

Exit gate: Native supported-OS acceptance, publisher enrollment/signing, safe upgrades and a published truthful support matrix.

## Decisions before implementation

- **Answered:** offline by default, optional cloud evaluation. This authorizes evaluating a direction, not choosing a provider, collecting credentials, buying a plan, uploading recordings or turning on fallback.
- **Pending:** first languages, mixed-language pairs and script/transliteration preferences. Initial question remains open.
- **Pending:** primary audience (everyday writing, professional work or accessibility). Initial question remains open.
- **Choose before changing storage:** transcript/audio retention defaults, private mode semantics, deletion wording and migration of existing recordings. No existing data was deleted.
- **Choose before changing output:** strict Verbatim, spoken-command opt-in/literal escape, app-focus restoration, clipboard preservation and sensitive-field behavior.
- **Choose before optimizing quality:** minimum hardware/performance budget, model-pack sizes and optional cloud provider/cost/region/retention policy. Compare candidates before selecting.
- **Choose before expanding platforms:** Linux distributions/Wayland priority, Intel Mac or ARM scope, update channels and signed release enrollment. Current scope is Apple Silicon macOS14+, Windows11 x64 preview (Win10 compatibility unverified), Ubuntu24.04 x64 X11 preview.

## Evidence and review artifacts

- [Interactive audit board](</Users/abrarakhunji/.cursor/projects/empty-window/canvases/fixoflow-product-audit.canvas.tsx>) — filter by platform, evidence type and priority.
- [Structured finding ledger](</Users/abrarakhunji/.codex/visualizations/2026/10/18/01a14dd2-e898-74a2-8c4d-f0eb74d89a04/fixoflow-product-audit/audit-data.json>).
- [Speech audit evidence](</Users/abrarakhunji/.codex/visualizations/2026/10/18/01a14dd2-e898-74a2-8c4d-f0eb74d89a04/fixoflow-product-audit/speech-evidence.md>) and [platform audit evidence](</Users/abrarakhunji/.codex/visualizations/2026/10/18/01a14dd2-e898-74a2-8c4d-f0eb74d89a04/fixoflow-product-audit/platform-evidence.md>).
- [Acoustic diagnostic results](</Users/abrarakhunji/.codex/visualizations/2026/10/18/01a14dd2-e898-74a2-8c4d-f0eb74d89a04/fixoflow-product-audit/acoustic-probe.json>) and [reproducer](</Users/abrarakhunji/.codex/visualizations/2026/10/18/01a14dd2-e898-74a2-8c4d-f0eb74d89a04/fixoflow-product-audit/acoustic-probe.py>).
- [REA summary](</Users/abrarakhunji/.codex/visualizations/2026/10/18/01a14dd2-e898-74a2-8c4d-f0eb74d89a04/fixoflow-product-audit/wispr-REA-summary.json>) and [complete retained REA Evidence](</Users/abrarakhunji/.codex/visualizations/2026/10/18/01a14dd2-e898-74a2-8c4d-f0eb74d89a04/fixoflow-product-audit/wispr-REA-evidence.json>).

No implementation fixes, releases, deployments, account changes, security bypasses or app installations were performed in this audit. Verification result: PASS for the executed source suite/isolated probes and report consistency; physical device, representative accuracy, production signing and reference runtime coverage remain open. Agent token cost, repeated cold/warm statistical estimates and complete process-family/battery cost were not measured.
