# Implementation status

Planning policy: deep; dependency-level context; impact verification; no delegation.
Baseline: a31a097 / 0.3.4. Existing docs 08/09 changes are preserved.

Authorized scope: implement docs/20 in reviewable dependency order. Current slice:
session traceability and journal, idempotent completed history, delivery states,
explicit suggest-first correction memory, portable hub controls and reproducible
evaluation summaries. Native observation remains off; no default model/language
or publisher/distribution change in this slice.

Acceptance: durable session identity before microphone open; failed/cancelled
sessions retained; repeated processing cannot duplicate analytics; journal remains
useful across database reopen; correction proposals never apply before approval;
approved corrections are exact-utterance scoped to app/language/mode, preserve
Raw/Verbatim and cannot cascade; Forget/delete removes linked learning; current
suite and meaningful new integration tests pass. No inference-accuracy claim from
these tests. Phase B/C/native platform work remains tracked in docs/20.

Decision: retain existing native/Python architecture and integrate at core/storage/
hub boundaries already inspected. Risk: schema migration and text changes; mitigate
with additive tables, explicit approval, narrow scope and isolated database tests.

## Implemented in this slice

- `storage/sessions.py`: additive durable journal, stable IDs before microphone
  opening, statuses for failure/cancel/completion and distinct delivery outcomes.
  Recorder binds its persisted WAV to ownership/journal before hardware opens.
  Repeated history writes with the same identity cannot double-count analytics.
- `storage/feedback.py`: explicit proposed/approved correction memory, exact
  utterance plus app/language/mode scope, conflict rejection and Forget. Generated
  replacements do not cascade; Raw/Verbatim bypass memory. Source deletion also
  deletes its learned memory. No other-app observer or training process is enabled.
- History hub: corrected-transcript editor, approval/Forget controls, raw output
  reference, journal and owned-recording playback. Playback is bounded to 20 MB
  and requires registered identity/valid mono PCM WAV. Legacy unregistered audio
  has an explicit error rather than a guessed file claim. Playback stops/clears
  when leaving History or deleting records.
- `audio/devices.py`: microphone selection by host/name resolved at each start,
  with missing/ambiguous devices rejected rather than silently falling back.
  Settings choice autosaves through the existing idle/config transaction. The
  empty choice follows the system default at start. PortAudio does not supply a
  universal immutable hardware ID through this interface; duplicate names are
  deliberately rejected. Native-rate conversion, hotplug handling and a live mic
  test are still pending.
- `evaluation.py` and speech diagnostic: normalized micro-WER, separate empty-
  reference hallucination counts, interpolated p50/p95 decode timing, per-language
  summaries, manifest SHA-256, validation and runtime metadata. Audio paths can
  be relative to the manifest. First decode includes initialization; this is not
  a cold/warm repeated benchmark, identifier scorer or representative dataset.
- Portable CI now includes memory, evaluation and device/playback boundary tests.
  Fixed native UI check's repository-path setup before importing local modules.

## Executed verification

2 November 2026:

- Baseline suite: 228 passed, 3 skipped in the preceding comparison; initial
  implementation checks also ran the existing suite before broadening coverage.
- Final `.venv/bin/python -m pytest tests/ -q`: **257 passed, 3 skipped** (2.98 s).
- `.venv/bin/python scripts/check_product_ui.py`: **VERDICT: PASS**. Real Cocoa /
  WebKit bridge exercised all six panels, pending/approved/forgotten corrections,
  literal HTML-like text rendering, session status, owned synthetic audio loading
  without playback output, microphone selection rendering, existing autosave/
  shortcuts/paging and minimum-window layout. Test DB/config were isolated.
- `git diff --check`: passed. Speech evaluator `--help`: passed.

No microphone opened, speaker playback performed, real speech benchmark run,
native Windows/Linux UI executed, personal-history migration exercised, package
built, release published or deployment changed. Source tests and native bridge
checks do not establish physical device behavior or improved speech accuracy.

## Remaining plan coverage

A is a delivered foundation, not the full benchmark/recovery program. B is
partial (selection/playback; no mic checkup, hotplug or recovery actions). D is
partial (explicit exact-utterance memory, not contextual vocabulary ranking or
role profiles). Model catalogs/downloads/warm-up and multilingual release gates
(C), optional external correction observation (E), themes/tray/clipboard updates
(F), Intel/Linux-format/public signing work (G), and learning research (H) remain
unimplemented. No full-plan completion claim is made.

Next dependency work: owned recovery inbox with safe retry/export/delete and
model capability/lifecycle contracts; keep manual correction memory available
while qualified recognition choices and observer feasibility are developed.

Microphone API reference checked against the official
[sounddevice 0.5.3 hardware](https://python-sounddevice.readthedocs.io/en/0.5.3/api/checking-hardware.html)
and [stream](https://python-sounddevice.readthedocs.io/en/0.5.3/api/streams.html)
documentation. No new runtime dependency was added.
