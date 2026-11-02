# Post-implementation assessment: Fixo Flow and SpeakType

2 November 2026. Fixo Flow: a31a097 plus current uncommitted implementation.
SpeakType: 1e17f218a48d73f733fac1f15629e0345968e1ba; remote HEAD rechecked and
unchanged. This is an engineering judgment, not a matched native product trial.

## Overall judgment

**Fixo Flow: 6/10. SpeakType: 7/10.** Same rounded ratings as before. Fixo Flow
has progressed inside the experimental tier; that is not enough to claim a new
tier of product readiness or to erase SpeakType's broader completed workflow.

These scores assess implemented design/scope and available verification, not
recognition accuracy. Score meanings: 5 = useful prototype with major gaps;
7 = coherent experimental product with meaningful breadth but incomplete native
acceptance; 9 = convincing daily-use reliability and measured quality on a clearly
defined support matrix. Intermediate values are reviewer judgment. A 10 would
not mean perfect speech recognition.

Use the same six equally weighted dimensions as the earlier assessment:

- Recognition flexibility: Fixo Flow 4, SpeakType 8.
- Everyday workflow completeness: Fixo Flow 6, SpeakType 8 (Fixo Flow was 5).
- Capture durability/recovery design: Fixo Flow 8, SpeakType 4.
- Explicit output preservation/developer formatting: Fixo Flow 8, SpeakType 5.
- Platform/distribution breadth: Fixo Flow 5, SpeakType 8.
- Verification/maintenance design: Fixo Flow 6, SpeakType 7.

Rounded means are still 6 and 7. Recovery and output scores assess particular
design strengths, not observed reliability percentages. Verification includes
source/CI structure; SpeakType's Rust tests were not executed here. Native-test
coverage is unequal, so these numbers must not be read as precise measurements.

## Released product versus development source

Fixo Flow's new code is still in the working tree. There is no rebuilt installed
package or verified upgrade containing this work. Its public-product rating
therefore receives no credit for users already having the new mic picker,
playback, session journal or correction memory. Development-source comparison
can credit those implementations, with their tested limits. SpeakType's reviewed
v2 is the release-oriented cross-platform code, not its legacy Swift app.

## What improved, and what did not

Implemented: stable session IDs and idempotent completed-session storage;
separate delivery states; microphone selection; owned WAV playback; explicit
propose/approve/Forget UI; exact-utterance scoped corrections; evaluation summaries.
The last implementation suite passed 257 tests with 3 skips. Native Cocoa/WebKit
checks passed including the new bridge controls. These were isolated checks,
without real microphone capture, speaker playback or representative speech.

Not implemented: automatic manual-edit observation; contextual generalization;
acoustic weight adaptation; reinforcement learning; role profiles; qualified
model download/catalog/warm-up experience; multilingual release; complete recovery
actions; mic calibration/hotplug; themes/tray/clipboard upgrades; broader trusted
distribution. Do not describe the plan as delivered functionality.

Most importantly, the recognition engine/default weights were not improved in
the last slice. A better evaluator measures quality; it does not improve it.
More passing tests protect behavior; their count does not establish lower WER.

## Concrete deficiencies in the new Fixo Flow work

1. **Correction scope is not a persistent app identity on Windows/Linux.**
   `storage/feedback.py` matches `app_identity` exactly. Windows supplies HWND,
   PID and creation time; Linux supplies window ID, PID and process start time.
   That is appropriate as a temporary paste target but not persistent app scope.
   A temporary-database probe using simulated old/new process identities produced
   the approved correction only for the old identity. This is an isolated logic
   reproduction, not native-device validation. Split stable `app_id` from
   ephemeral `delivery_target`; migrate existing scope conservatively. Do not
   weaken the existing delivery checks to solve personalization persistence.
2. **Learning is exact-utterance recall.** Approving “Y is the build failing?”
   will not generalize to “Y did the tests fail?” or fix the underlying acoustic
   confusion. Even punctuation differences can prevent a match. This is safe
   initial memory, not the user's requested behavior-learning system.
3. **Recovery remains mainly storage infrastructure.** Journal rows are visible,
   but safe retry/export/delete and interrupted-session reconciliation are not
   complete. Keeping audio on disk is valuable only if users can recover it.
4. **Mic/playback parity is incomplete.** Device selection uses host/name and
   rejects duplicates; no live calibration, native-rate fallback or tested device
   removal. Playback is a bounded base64 bridge transfer, limited to registered
   PCM files up to 20 MB; legacy unregistered recordings are rejected. It is not
   a scalable long-audio player or a native compatibility guarantee.
5. **Release validation trails source progress.** New schema/UI behavior has not
   been accepted on physical Windows/Linux systems, real existing user datasets
   or fresh installed upgrades. Mic selection was not exercised on hardware.

Code references: `storage/feedback.py:68`, `platform/windows.py:29`,
`platform/linux.py:17`, `audio/devices.py:19`, `storage/sessions.py:53`.

## SpeakType deserves scrutiny too

Its advantages remain model/engine choice, language selection, onboarding,
warm-up, microphone UX, playback/clipboard convenience, broader packaging and
Mac signing/notarization preparation. Its greater breadth makes it the stronger
candidate for a general-user trial today; this is a source-based recommendation,
not an observed usability-study result.

Its capture grows an in-memory buffer; successful recognition precedes saving
the WAV. That creates a crash/recognition-failure recovery exposure. The paste
worker targets the focused app, uses a fixed clipboard-restore delay and logs
errors without returning a delivery result to the controller. Dictionary rules
chain, whitespace normalization removes line structure, and history does not
store a distinct raw/final pair. These are material engineering tradeoffs.

Its own roadmap admits young Windows/Linux acceptance, incomplete Wayland
shortcuts, model-loading/device-change problems, missing audio-retention choice
and manual v2 updates. Automatic learning is also roadmap work. No 9/10 rating
is justified from this evidence. Its hardcoded model speed/accuracy bars are not
benchmarks against Fixo Flow. Rust/Tauri alone proves neither speed nor reliability.

## What cannot honestly be rated numerically

Actual speech accuracy, proper-name/number retention, Hindi/Hinglish quality,
end-to-end latency, battery cost, whole-app memory and real-world paste success
remain **unranked**. No common corpus, hardware-matched runs or installed acceptance
campaign was executed. More model choices make SpeakType more adaptable; they
do not prove every model is more accurate than Fixo Flow on the user's speech.

## Next work ranked by value

1. Fix persistent app identity in correction scope and cover restart/multiple-
   window behavior. Then verify explicit correction memory in installed apps.
2. Build a representative consented paired corpus and score current recognizers
   before changing defaults. Include names, numbers, identifiers, accents, noise,
   silence and long speech; separate raw accuracy from formatting.
3. Qualify one speed and one quality model candidate with visible lifecycle and
   warm-up. Preserve working offline inference and language gates until measured.
4. Complete mic test/device handling and the recovery inbox. Give durable capture
   a usable user-facing recovery path.
5. Build scoped contextual correction proposals, with protected homophone/letter/
   code negatives and undo. Add optional edit observation only for verified field
   ranges. Genuine RL is not the next dependency.
6. Build/install/test the result and publish the support matrix. Themes and extra
   package formats should not outrank recognition, recovery and installed trust.

Fixo Flow's immediate objective should be a demonstrably better complete
dictation task for a defined audience. “More accurate than every platform” is
not a claim the available evidence can support.

## Primary reference links

- [SpeakType current desktop source](https://github.com/karansinghgit/speaktype/tree/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop)
- [Capture](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/audio.rs)
- [Pipeline](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/pipeline.rs)
- [Paste](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/paste.rs)
- [Text rules](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/desktop/src-tauri/src/text.rs)
- [Roadmap/admitted gaps](https://github.com/karansinghgit/speaktype/blob/1e17f218a48d73f733fac1f15629e0345968e1ba/ROADMAP.md)

This reassessment changed no application code. Prior verification results are
reported as prior results; the only new executable diagnostic was the isolated
scope-identity probe. Current public installer trust was not independently tested.
