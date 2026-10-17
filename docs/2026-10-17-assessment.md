# Fixoflow assessment — 17 October 2026

## Scope and decision

The immediate user-reported problem is failure to open and duplicate app icons, not just recognition quality. Inspection found `/Applications/Fixoflow.app` and `fixoflow/dist/Fixoflow.app`, both initially shell launchers pointing to the same development virtual environment. Importing source and creating the Cocoa/WebKit window succeeded, but CUA opening the old installed launcher timed out. That establishes a packaging/launch problem; it does not identify every possible startup fault.

Planning policy: deep planning, dependency-level context, impact verification, delegated independent reference-app inspection, packaging, and capture/STT changes. Authority: user's requested Fixoflow implementation and local app installation; no REA capability integration, other-app mutation, dictation upload, permission grants, or access to reference-app private histories.

## What was already built

Source inspection confirms 16 kHz capture, Butterworth filtering and normalization, pause-based segmentation, MLX Whisper transcription, a Cocoa/WebKit floating indicator and hub, global hotkey handling, personal dictionary, SQLite completed-session history, app usage aggregation, and a DMG generation script. These are useful prototype components. The UI was custom HTML loaded in WebKit, not an entire native reconstruction of Wispr Flow.

The original selected 10 non-device tests passed. The original coordinator test opened the real microphone and asserted only the state and text type; the original cloud fallback test performed a network request. They did not establish claimed recognition accuracy, zero loss, peak memory, or installed application launch behavior.

## Structural defects addressed

- App packaging depended on an absolute project path and external Python. Replacement packaging bundles the interpreter, dependencies, model and assets, uses atomic promotion with backups, verifies its native signature and imports, and produces a genuine disk image. Local ad-hoc signing is not Developer ID signing or notarization.
- Audio was retained entirely in a growing list until stop. Capture now writes recoverable PCM WAV blocks through a bounded queue, updating headers, flushing and fsyncing during capture. Overflow and failed persistence become explicit failures. Shutdown retains resources whose cleanup failed for retry.
- Transcription swallowed failed chunks and skipped short tails. It now decodes all nonempty tails and exposes an incomplete error with partial text; the coordinator preserves available text in an audio-adjacent JSON file and does not auto-paste partial results as complete.
- Model resolution could fetch dependencies at runtime. It now accepts validated explicit local folders, the bundled default model, or offline-only cached snapshots. Selecting another model does not silently reuse the bundled default.
- The cloud polisher conflicted with the offline requirement. Runtime network polishing is removed, legacy config is read as offline rules, and ambient API keys are not captured. Config saves are atomic and keep a previous-file backup; malformed configs are not silently overwritten.
- The learner generated a vocabulary prompt that was never sent to STT. The coordinator now supplies it, retaining AI tool names and personal terms.
- General text cleanup altered code capitalization and collapsed paragraphs. Coding/raw modes preserve formatted identifiers and symbols; writing cleanup preserves line/paragraph breaks and retains input if rules would erase all text.
- The hub edited a separate config instance. Changes now validate and update the live coordinator, model, formatter, recorder and shortcut while idle. Saved-success feedback comes from the native bridge, rather than an immediate unconditional JavaScript alert.
- Paste return status was ignored and foreground identity was not rechecked. Focus changes now prevent paste; failed insertion reports recovery through History. Keystroke dispatch still cannot prove that the recipient accepted text or retained the same text field.
- User transcript/dictionary text was interpolated into HTML and inline JavaScript handlers. It is now rendered with DOM text nodes and closures.
- Model-generated identifiers were automatically trusted as learned vocabulary. That self-reinforcement is disabled in normal dictation; user dictionary entries remain explicit.

## Reference app evidence

Observed installed artifacts: Wispr Flow 1.6.1174, Electron; WisprType 1.1.1, Apple Silicon native application with Tauri/Rust indicators and a WhisperKit inference helper.

Wispr Flow bundled main JavaScript (`wispr_extracted/.webpack/main/index.js`, minified line 8, SHA-256 `b2295c53e0029194248d2c12e84e3f26241c758cb0690dc1ed8a35f1f8fa824b`) has source-derived evidence of cloud endpoints, local SQLite models for Dictionary/History/UserContext/UserVoicePreferences, correction-driven dictionary additions gated by `shouldAutoLearnWords`, application/textbox context, and backup machinery. User edits and app context are inputs to learning around byte 3,881,866. This is not evidence of on-device reinforcement learning or per-user model weight training. Source inspection is not runtime validation of those paths.

WisprType bundled helper strings include chunkingStrategy, totalDecodingWindows, WhisperKit.EnergyVAD and chunk-transcription error messages. Fixed CoreML windows do not establish a universal app-wide 30-second truncation limit. Its strings/manifest suggest local-default transcription, optional cloud routing, raw/cleaned transcript persistence, and rewrite-failure fallback; these have not been runtime reproduced here.

REA ASAR analysis failed closed on an unpacked sqlite native module integrity mismatch. A narrow extracted-tree manifest analysis succeeded with Evidence `ev_45e0bdd088d940db055d6d4ce04fd9e2aa01bafd8d7239f053bbb5c2e61eef0f`; its scope excluded 182 files. The direct main-code observations above are ordinary static inspection, not conclusions supplied by that narrow REA result. No complete decompilation, full UI lifecycle capture, reference-app history access, or network interception was performed.

Official product documentation independently says Flow uses cloud processing and learns dictionary additions from edits when enabled. References: https://docs.wisprflow.ai/articles/3467817258-security-and-compliance-faq ; https://docs.wisprflow.ai/articles/4052411709-Teach-Flow-your-words-with-the-dictionary . WisprType's product page advertises on-device Whisper models: https://wisprtype.com/ . Vendor claims do not establish head-to-head accuracy on this user's speech.

## Measurements and limitations

Single cold subprocess measurements on this Mac, using `/usr/bin/time -l`; no warm-run series or process-family aggregation:

- Source app import: elapsed 1.02 s, user CPU 0.83 s, max RSS 212,746,240 bytes, peak footprint 135,562,176 bytes.
- Current base.en model, actual inference on one second of synthetic silence: elapsed 1.19 s, user CPU 0.86 s, max RSS 471,580,672 bytes, peak footprint 863,470,792 bytes.
- Cached 4-bit base model, same synthetic silence: elapsed 1.38 s, user CPU 0.78 s, max RSS 259,948,544 bytes, peak footprint 565,838,928 bytes.
- Initial packaged import check: elapsed 3.70 s, user CPU 1.35 s, max RSS 218,611,712 bytes, peak footprint 142,771,184 bytes.

Both inference probes hallucinated the text “You” on synthetic silence. These probes measure resource cost and reveal a silence risk; they do not measure ordinary speech accuracy or comparative speed. System CPU times, process-family memory (including WebKit), warm-run performance, battery cost, and agent token costs were not measured. No equivalent before/after complete-task performance comparison is available. Bounded capture improves memory growth but does not meet the strict 200 MB inference ceiling; filtering/inference still loads full-session arrays. The Python/MLX inference implementation needs replacement or substantial rework before that requirement can pass.

Absolute zero loss is not achievable against all hardware/disk/power/recognizer failures. The bounded capture queue still has up to two seconds of unflushed audio, there is no automatic startup replay queue yet, and chunk boundaries can affect recognition despite preserving samples. Failed audio and partial text can be recovered from disk. The system does not currently monitor user edits in other applications, train pronunciations, infer language preferences, or learn tone. App detection uses name heuristics; browser sites and terminal agents are not reliably distinguished.

## Daily-use verdict and next work

There is no measured accuracy winner. Wispr Flow is a reference for a mature cloud-backed workflow but does not satisfy this user's air-gap requirement. WisprType is a relevant offline baseline; the alleged universal 30-second defect remains unverified. Fixoflow is currently an experimental local alternative, not a proven superior daily driver, and still fails the hard memory target.

Next enhancement for AI coding workflows: explicit correction feedback with provenance, per-app profiles and undo. Store session ID, raw text, final text, the user's accepted correction, app bundle ID and profile, then bias recognition using approved technical vocabulary. Do not turn the recognizer's own output into unquestioned training truth. Retain local-only opt-in controls, retention/export/delete semantics and user-visible failure recovery. Do not read unrelated screen text or sensitive fields as an implied part of learning.

Before a daily-use claim: verify signed installed launch/reopen, user-granted permissions, shortcut press/release races, microphone selection/disconnection, recovered interrupted sessions, delivery into a safe text editor and each requested agent, and shared reference recordings spanning 5/15/30/60/300 seconds. Score raw word error rate, coding-identifier exact match, omitted clauses, semantic preservation after cleanup, paste completion, p50/p95 stop-to-text latency and total app-family memory. Run with network unavailable using preloaded models. Do not upload the user's recordings to a cloud reference app without explicit authorization.

## Executed verification update

The revised suite passes **45 tests** using `.venv/bin/pytest tests/ -q` (latest source run 1.64 s). Source and isolated frozen self-checks initialize real Cocoa/WebKit UI and local model resolution. Frozen diagnostics also validate native MLX/PortAudio/tokenizer resources and run real bundled Metal inference on generated silence. The bundled app runs from a copied directory with an empty working directory, sanitized environment and separate HOME, without the project virtualenv or cache.

Actual installed-app CUA checks confirmed a window named Fixoflow under the Fixoflow application identity; clicking Settings changed the visible view; clicking Save Preferences produced the native-bridge result “Preferences applied.” This caught an Accessibility-framework export mistake and the original event-loop defect that noninteractive initialization tests missed. The event loop now uses NSApplication.run instead of only stepping NSRunLoop. Hub ownership now retains the window after close, and the self-check closes/reopens it and verifies visibility and alpha.

The installed application's permission panel reported Accessibility and Input Monitoring as needed. Neither permission was granted by the agent. Microphone capture, the live global hotkey, and text injection into a user application remain unverified under the packaged app. No spoken recordings or dictation data were sent to a reference product.

The original installed launcher and developer DMG were preserved; the native replacement was installed at `/Applications/Fixoflow.app`. Development/test Launch Services registrations are cleaned separately from user data; existing dictation history is retained. The DMG is a local ad-hoc signed build, not notarized.

Final installed-app reopen check: after closing the hub, a second invocation exited successfully, restored the original process's visible window, and OS window metadata reported alpha 1.0. A fresh CUA screenshot confirmed the actual dashboard, and Settings remained clickable. The app is left open on its permission setup screen. Final DMG SHA-256: `e5d42689b8632527e21d242f92071c329f1c71e2a57ef0c77c1402d9b92b2a19`; 321,465,516 bytes.
