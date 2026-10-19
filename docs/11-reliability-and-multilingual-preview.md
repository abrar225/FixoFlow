# Fixo Flow 0.3.0 reliability and multilingual preview

Implementation and verification record, 19 October 2026. This is a development
preview, not a declaration that every platform, language or acoustic condition
is production ready. The original 33 findings remain available in
[the dated audit](10-product-audit-and-roadmap.md).

## Approved behavior

- English remains the default. US, UK and India use the shared English
  recognizer with no forced regional spelling. User approved removing spelling
  instructions after a diagnostic showed invented text.
- Offline dictation remains the default and only processing mode implemented.
  No microphone audio, transcripts, API keys or identifiers are uploaded.
- Base multilingual is a separate optional download, never a replacement for
  bundled English. The UI installs it only after an explicit click.
- Hindi, Mandarin Chinese, Japanese and 96 other Whisper language options,
  including English, are selectable. All multilingual recognition is marked
  experimental. Simplified Chinese and Devanagari are recognition prompt
  preferences, not deterministic script conversion. Cantonese's large-v3-only
  extra token is excluded from the Base catalog.
- User approved evaluating Small after Base's Hindi errors. Small remains
  evaluation-only; it is neither bundled, selected by default nor offered by
  the Base install button. User subsequently chose to keep multilingual
  experimental while testing more offline models.
- Spoken punctuation and coding commands are opt-in. Verbatim bypasses both
  dictionary replacements and formatting; it preserves recognizer text apart
  from outer whitespace.
- Explicit History deletion removes the transcript and linked owned audio.
  No existing recording is deleted merely by starting/updating the application.
- The unanswered focus-policy choice is not changed: existing best-effort focus
  restoration remains. Final target and cancellation guards have been added.

## Implemented fixes, by priority

**Text and input safety: D01,D02,D04–D08.** Down/up suppression is owned per
physical key across both release orders and router reconfiguration. Idle Escape
passes through; active Escape cancels. Synthetic keyboard events bypass global
shortcut routing so simulated paste does not trigger dictation. Literal prose
and bullet content are protected, Verbatim skips correction, dictionary changes
are literal and non-cascading, longest valid phrase wins, combining marks are
word boundaries, symbol phrases work, and matching reads the full dictionary.
Real native key delivery across supported editors still needs physical tests.

**Owned deletion and capture recovery: D03,D09.** Newly written WAV/sidecar
identities and roots are registered. Explicit deletion validates legacy generated
files conservatively, preserves unknown/replaced/symlinked paths and unrelated
files, retains failed deletion for retry, and rebuilds analytics after partial
clear. Shared linked audio is retained until its final History reference.
Recorder cleanup ownership survives failure and is retried before another
capture. Recording cancellation drains the writer without allocating/filtering
the entire WAV. Cancellation/incomplete recordings are retained; a usable
recovery inbox is still pending (G05).

**Insertion and platform status: D10–D13.** Native adapters accept the intended
target rather than recapturing it after a clipboard write. Mac rechecks target
after waiting for modifiers; all adapters check cancellation immediately before
dispatch. Once a paste commits, required key-up cleanup still runs. Mac identity
remains application-level, not original field/caret ownership (R02). Windows app
identity comes from the executable rather than document title. Desktop recording
and processing show the pill even when idle visibility is disabled. Permission
UI retains platform guidance and unknown microphone state rather than claiming
Mac permissions on Windows/Linux. Microphone diagnostics remain pending (G04).

**Resources and filtering: D14,D15,G03.** Unrelated settings preserve the warm
STT engine, recorder and its callbacks; only model/language/CPU changes stage a
new locally validated engine. Filter arguments are honored. The active session
pipeline reads bounded PCM windows of at most 24 seconds rather than loading a
whole recording. Truncated files fail with partial text instead of looping at
EOF. Exact-zero audio skips recognition. Window-local filtering/normalization
can affect long-session results: sample coverage is tested, but word-boundary
quality/overlap reconciliation is unresolved (R01).

**Cooperative cancellation: G07, partial.** Controls own a cancellation Event
from intent creation, so Escape/shutdown before a queued start cannot be reset
by that delayed start. Cancellation prevents pending processing/paste and is
checked between decodes and during paste waits. It cannot interrupt a currently
running native model call; shutdown may still wait for that call.

**Management and neutral defaults: G08,G16.** History and dictionary have
backend pagination/search and Load more controls. Search treats SQL wildcard
characters literally. New users no longer receive a developer/AI vocabulary
seed. Only approved dictionary terms condition recognition; generated app/style
  instructions have been removed. Existing dictionary entries are preserved; users may remove them normally.

**Multilingual provisioning: G02, experimental foundation.** Local model
compatibility is validated before saving a language/model change. Downloads use
pinned repository revisions, expected Git blob/LFS digests and exact sizes,
private staging, cancellation, complete validation and atomic promotion. A
working pack is never overwritten by a failed install. Validation caches only
unchanged file identities/size/timestamps, not weights; changed files are hashed
again. Model-manager close blocks new downloads, retains failed staging cleanup
for retry and gates host quit/restart until its worker/cleanup finishes. Forced
process termination can still leave a private staging directory; there is no
automatic scavenger for previous-process leftovers.

## Executed verification

- Local full suite: **192 passed, 2 skipped** after the final source fixes. The two
  skips require native Windows/Linux execution. Tests include queued-start
  cancellation, paste-delay cancellation, truncated WAV partial recovery,
  bounded windows/tail coverage, pack corruption/cache invalidation, blocked
  download shutdown, cleanup retry, terminal close, conservative deletion,
  dictionary text integrity and warm-resource reuse.
- Actual Cocoa/WebKit UI check passed all 6 panels, local font/logo, minimum
  viewport, shortcut capture/settings bridge, 99 languages plus auto detection,
  commands default, real DB History/dictionary pagination and Windows permission
  visibility. It used a temporary database and mock pack availability, opened
  no microphone and changed no user settings.
- Native Mac app build, strict local signature and frozen imports/resources
  checks are run before packaging. Local signing is not Apple notarization.
- Native CI coverage is configured on macOS, Windows and Ubuntu. Build/test
  results must be recorded separately; workflow configuration alone does not
  establish executed platform or physical-device acceptance.
- Diagnostic self-check now uses a nonzero tone: exact silence is deliberately
  skipped by the engine and therefore cannot prove decoder execution.

## Long-session allocation and prompt checks

A controlled DSP/allocation diagnostic replayed equivalent 16 kHz mono PCM16
files through the former whole-file workflow and the new bounded-window
workflow. The generated 440 Hz tone and mocked decoder isolate preprocessing;
this does not measure speech quality or full application memory. Each case ran
in a fresh process, with filesystem cache uncontrolled. Peak includes imports
and file preparation; CPU/elapsed cover processing only.

- One minute: whole-file peak 132,448,256 bytes, elapsed 0.01637 s, CPU 0.01544 s;
  windows 113,688,576 bytes, elapsed 0.01433 s, CPU 0.01434 s.
- Ten minutes: whole-file peak 468,631,552 bytes (446.9 MiB), elapsed 0.16444 s,
  CPU 0.16406 s; windows 122,290,176 bytes (116.6 MiB), elapsed 0.13009 s,
  CPU 0.13007 s. Both delivered all 9,600,000 frames to the mocked decoder.
- Full ASR/UI/process-family CPU, GPU, token cost and peak memory were not
  measured by this allocation test. Single runs do not establish latency
  guarantees, and changed pause positions/window normalization still need
  representative speech testing.

A separate repeated-English diagnostic exposed invented repetitions and echoed
spelling instructions. Isolating/removing the generated locale instruction
restored all expected words in that run. User approved removing English locale
instructions for US/UK/India; no regional spelling is now forced. Generated
coding/app instructions were removed too; only approved dictionary terms
condition ASR. Regression tests inspect actual decoder requests, not only the
language-label helper.

A retained fresh-process follow-up used eight repetitions of one locally
synthesized sentence. The recreated old locale hint produced 1 normalized word
error in 80 reference words; corrected source produced 0/80. The earlier
hallucinated run was more severe, so severity is not deterministic. This narrow
probe establishes neither universal English accuracy nor a fix for all model
hallucinations. Raw follow-up audio/outputs and the allocation script/results
are retained in the local audit evidence bundle.

## Hindi model evaluation

Model sources are pinned [MLX Base](https://huggingface.co/mlx-community/whisper-base-mlx/tree/1e3e249fb8d01c655324bd6841b1deadffd6d04c),
[MLX Small](https://huggingface.co/mlx-community/whisper-small-mlx/tree/45f3915923c7a79a5a5b5a7d909d39aeb0e5630e)
and [CPU Base](https://huggingface.co/Systran/faster-whisper-base/tree/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66).
Verified MLX download totals are 143,724,807 bytes for Base and 481,308,201 bytes for
Small. CPU Base was also downloaded and validated against its pinned digests: 147,884,932 bytes. This checks provisioning, not native Windows/Linux recognition quality. These are separate disk costs, not total installed application size.

One local synthetic sentence per language: both Base and Small recognized the
English, Chinese and Japanese sentences exactly; both made substantial Hindi
errors. Four sentences are not a multilingual accuracy benchmark.

The second diagnostic used the **first 12 rows** of the public
[Google FLEURS](https://huggingface.co/datasets/google/fleurs) `hi_in/test` Parquet
split, revision `168de341b3db6859a9bac1c50a2ef5e3b47647e0`, CC-BY 4.0. Hindi speech
and reference text are from Google FLEURS contributors; added noise and PCM16
conversion are evaluation modifications. No user recordings were used. These
12 clips were each tested clean, with +20 dB and +5 dB deterministic Gaussian noise
(seed 225; SNR based on full-clip RMS including pauses), 36 decodes per model.

- Base normalized whitespace word error: **93.7% clean, 97.2% at +20 dB, 124.8% at +5 dB**.
  WER can exceed 100% when insertions exceed the reference length.
- Small: **57.4% clean, 66.5% at +20 dB, 88.4% at +5 dB**.
- Base elapsed 61.615 s, CPU 34.149 s, peak main-process RSS 491,618,304 bytes
  (468.8 MiB). Small elapsed 55.898 s, CPU 21.638 s, peak main-process RSS 877,182,976 bytes
  (836.5 MiB). These are completed 36-case runs in separate processes.
- First decode includes lazy model initialization; filesystem caches were not
  controlled. Later cases reuse the model. CPU and elapsed values cover the
  evaluation loop; peak RSS also includes imports. GPU, process-family memory,
  GUI/WebKit, live microphone, low-end CPU, battery and native Windows/Linux
  speech quality were not measured. This small fixed sample is not
  representative of all Hindi speakers, conversational/noisy environments or
  other languages. Gaussian noise is not café/babble/interfering speech.

Small improves this diagnostic substantially but is **not launch-ready Hindi**.
It also costs substantially more memory/disk. No automatic upgrade is justified
by these results. Replay explicit PCM16 WAV cases using
`scripts/evaluate_speech.py --model LOCAL_MODEL --manifest CASES.json --report RESULTS.json`.
The script never downloads models or uploads audio. WER removes Unicode
punctuation/symbols and case, preserving letters/marks; whitespace WER is not a
suitable Chinese/Japanese quality metric. Raw outputs/provenance are retained in
the local audit evidence bundle, outside Git.

## Remaining work and gates

- **G01,G15:** representative public/lawfully supplied conversational, accented,
  café/babble and microphone recordings; measure clean/noisy accuracy, semantic
  formatting errors, empty/noise false positives, latency and process-family
  CPU/RAM/GPU/battery. No denoiser/VAD is added on an untested quality claim.
- **R01,R02:** speech-aware chunk boundaries and validated original editable
  window/field/caret ownership. Focus movement policy still needs the pending
  user decision; no claim of safe insertion into every editor.
- **G04–G06:** microphone selection/checkup/hotplug recovery, usable recovery
  inbox/retry, private sessions and explicit retention/quota policy. Existing
  retained recordings are not silently migrated or deleted.
- **G09,G10:** full desktop tray/reopen/background parity, visible transient
  outcomes and multi-monitor/work-area placement; X11 is the Linux integration
  target, Wayland remains manual/clipboard only.
- **G11,G12:** verified Windows publisher signing/reputation, Apple Developer ID
  and notarization, signed release/update feeds and installed update acceptance.
  Publisher accounts/certificates are absent. Code cannot manufacture trust or
  guarantee SmartScreen never warns. Existing OS protections stay enabled.
- **G13:** guided malformed-config startup recovery while preserving original
  file and user-selected settings.
- **G14:** native installer checks and physical Windows 11 x64/Windows 10/Ubuntu X11
  capture, global inputs, editor paste, updates and device matrix. Mac Intel,
  Windows 32-bit/ARM and arbitrary Linux distributions are not validated targets.
- Chinese script conversion, code-switching and regional spelling require
  further explicit acceptance testing. All99listed language tokens are model
  capabilities, not99verified product languages.
- Optional cloud, snippets, app profiles and hands-free editing remain proposed
  features. Cloud processing has not been enabled or selected.

Public website/download manifests continue to describe 0.2.0 installers. The
0.3.0 preview must not replace those links until its actual platform artifacts
and release gates are ready. Existing website/signing preparation is preserved.
