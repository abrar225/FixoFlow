# Matched recognizer benchmark tooling and executed evidence

2 November 2026. This implements the comparison infrastructure and runs a small
public backend diagnostic. It **does not complete a representative Fixo Flow
versus SpeakType application benchmark**. Neither product is declared more
accurate from this evidence.

## What is implemented

`scripts/compare_recognizers.py` accepts a versioned corpus manifest with source,
license/consent provenance and declared scope. It requires identical prepared
16 kHz mono PCM16 WAVs, checks supplied hashes/truncation, and fingerprints the
actual bytes. Repeated runs alternate recognizer execution order.

Built-in adapters:

- Fixo Flow: a fresh Python worker, explicit local model folder, manifest language,
  raw `transcribe_file` output. No hub, personal history, microphone or cloud use.
- SpeakType v2: its built `transcribe_wav` developer example, selected local catalog
  model and local models directory, one native run per fresh process. Requires a
  supplied native executable built from the recorded checkout.
- `whisper-cpp-proxy`: Homebrew/upstream `whisper-cli`, explicitly marked as a
  backend proxy. It is never labeled as an installed SpeakType result.

Reports record model-file hashes/sizes, executable hash, relevant source-file
fingerprints before/after runs (including uncommitted source), commit identities,
runtime/hardware descriptor, manifest identity, per-case output/error and timing.
Source-change flags expose concurrent source modification rather than pretending
a base commit identifies uncommitted code. A recorded source checkout does not
alone prove which checkout produced an independently supplied executable; retain
the build artifact manifest for release-grade runs.

Scoring includes normalized micro-WER/CER, separate empty-reference hallucination
counts, case-sensitive labeled name/number/identifier retention with token
boundaries, per-case paired deltas, matched-success-only summaries and visible
failure counts. Pairing rejects different audio hashes, reference text,
language/timing phase, missing cases and duplicate case/repetition identities.
Errors are retained as failed cases and never quietly converted to perfect silence.
The aggregate WER of successful cases must always be read with the failure count.

Fresh-process wall time includes process/interpreter startup, model load,
preparation, decode and teardown. It is **not** UI stop-to-paste latency and does
not imply a cold filesystem cache. The old `stop_to_text_seconds_p50/p95` summary
keys remain compatibility aliases; new callers should use `elapsed_seconds_p50/
p95` together with the report's explicit measurement scope.

The existing `scripts/evaluate_speech.py` also now supports repetitions and
unscored warm-up decodes, saves failed cases instead of losing the whole report,
records audio hashes/config/source metadata and separates first-decode/warm-worker
phase summaries. This runner's wall time measures `transcribe_file`, excluding
process startup. Never compare it directly with the fresh-process runner.

## Executed public smoke diagnostic

Audio: the 11-second JFK excerpt distributed with Homebrew whisper.cpp 1.9.5,
`/opt/homebrew/share/whisper.cpp/jfk.wav`. Upstream source is the public sample
in the [whisper.cpp repository](https://github.com/ggml-org/whisper.cpp/tree/master/samples),
whose repository has an MIT notice. Provenance and the limited historical-speech
scope are retained in the manifest. No user's recordings were accessed/uploaded.

Audio SHA-256:
`59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e`.

Reference, ignoring punctuation/case for normalized WER:

> And so my fellow Americans ask not what your country can do for you ask what you can do for your country.

Fixo model: the existing installed Base English MLX pack at
`/Applications/Fixoflow.app/Contents/Resources/models/whisper`.
Weight SHA-256:
`b6c8ee500656e04e8e57c2949a5253f0dda002ba36cd1561846574dbcf01132e`.

Proxy model: valid `ggml-tiny.en.bin` downloaded explicitly from ggerganov's
Whisper.cpp model repository at immutable revision
`5359861c739e955e79d9a303bcbc70fb988958b1` (77,704,715 bytes).
Expected/observed SHA-256:
`921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f`.
The much smaller bundled `for-tests-ggml-tiny.bin` was not used as a valid speech
model. CLI version: whisper.cpp 1.9.5. Machine: macOS 27.2 arm64.

Three repeated fresh-process executions per backend completed successfully:

- Fixo Base MLX: zero normalized word/character errors on this clip; process-wall
  p50 0.946 s, interpolated p95 1.321 s.
- Tiny English whisper.cpp proxy: zero normalized word/character errors on this
  clip; process-wall p50 0.175 s, interpolated p95 0.230 s.
- All three audio/reference pairs matched. Source-before/after fingerprints were
  unchanged during that run. Each repetition has 22 reference words; 66 aggregate
  words do not mean three independent speakers or samples.

A separate Fixo-only one-warm-up/three-measured-run diagnostic completed with
zero normalized errors; warm `transcribe_file` p50 0.102 s and p95 0.102 s.
This timing scope differs from process-wall time and cannot establish a backend
speed winner. Filesystem caches were uncontrolled, and other development work
was running on the machine. With only three observations, p95 is descriptive,
not a reliable production tail-latency estimate.

Full temporary reports and manifest are under
`/tmp/fixoflow-public-benchmark/` (`proxy-report.json`, `fixo-warm-report.json`,
`manifest.json`). The temporary directory also contains the verified downloaded
GGML model; no model was added to the repository or silently selected in the app.
This document retains the important results if temporary artifacts are cleaned.

## Actual SpeakType comparison: concrete missing prerequisite

The temporary SpeakType checkout is at `1e17f21`. Its current Rust example is at
`desktop/src-tauri/examples/transcribe_wav.rs`, using `devtools::benchmark`.
At the initial diagnostic pass there was no built v2 example executable in that
checkout and no Rust toolchain on PATH. The subsequent user-authorized native
build effort is recorded below. The installed whisper.cpp CLI is never a
substitute for claiming SpeakType app behavior.

Build the example using SpeakType's supported native toolchain, provision a
verified local model, then run:

```sh
.venv/bin/python scripts/compare_recognizers.py \
  --manifest /absolute/corpus/manifest.json \
  --fixo-model /absolute/fixo-model \
  --comparison-backend speaktype \
  --comparison-executable /absolute/speaktype/desktop/src-tauri/target/release/examples/transcribe_wav \
  --comparison-model base-en \
  --speaktype-models-dir /absolute/speaktype-models \
  --speaktype-source /absolute/speaktype \
  --repetitions 3 --report /absolute/evidence/comparison.json
```

The existing SpeakType example forces auto language and only prints the final
transcript in repeated runs. The adapter therefore requests one run per process;
it does not fabricate transcripts for prior iterations. Native warm-worker
comparisons require instrumentation exporting every actual run's transcript and
timing. Import two flat reports using `--import-left`, `--import-right` and
`--report`; both must contain identical explicit `measurement` metadata, a
`recognizer` object with `name`, `model`, `source_identity`, `artifact_identity`,
and paired `rows` (id, repetition, audio_sha256, reference, actual, language,
timing_phase, status, elapsed_seconds and score fields).

## Manifest format and representative acceptance still required

```json
{
  "schema_version": 1,
  "corpus": {
    "source": "public dataset URL or consented local collection",
    "license": "actual license/consent provenance",
    "scope": "speaker/session/language coverage and known exclusions"
  },
  "cases": [{
    "id": "speaker-session-clip",
    "audio": "relative/prepared.wav",
    "audio_sha256": "actual SHA-256",
    "language": "en",
    "reference": "Call Maya with parseConfig and 12 items.",
    "labels": {"names": ["Maya"], "identifiers": ["parseConfig"], "numbers": ["12"]}
  }]
}
```

The example above is a format illustration, not a supplied recording or result.
The benchmark does not fetch audio or infer consent/license from a filename.
Before product superiority/default-model decisions, collect a licensed/consented
held-out speaker/session set spanning accents, personal names, numbers, developer
identifiers, conversational speech, noise, silence, long dictation and separately
Hindi/Hinglish. Pin the prepared audio and references, reserve tuning data, record
decoder-policy differences and repeat on named target hardware. Raw recognition,
formatting changes and actual app delivery need separate acceptance reports.

## Verification

`python -m pytest tests/test_evaluation.py tests/test_benchmark_comparison.py -q`
passes the comparison/aggregation suite, including failed-run handling, strict
pairing, case-sensitive labels, timeout reporting, provenance/hash validation,
alternating order, import metadata and evaluator warm/failure persistence.
Actual Base MLX and whisper.cpp proxy inference ran as described above.

VERDICT: PASS for the executed harness tests and public backend diagnostic.
Representative product quality and actual SpeakType v2 acceptance remain open.

## Follow-up: reproducible broader public diagnostic

`scripts/prepare_public_benchmark.py --output-dir /absolute/output` now prepares a
bounded 20-clip public LibriSpeech subset. Its shared implementation is also
available as `compare_recognizers.py --fetch-librispeech-subset DIR`. This is an
explicit network operation, not part of running dictation or offline benchmarks.

Dataset: [OpenSLR SLR12](https://www.openslr.org/12), hosted as
[openslr/librispeech_asr](https://huggingface.co/datasets/openslr/librispeech_asr),
CC BY 4.0. Attribution: Vassil Panayotov, Guoguo Chen, Daniel Povey and Sanjeev
Khudanpur, “LibriSpeech: an ASR corpus based on public domain audio books,”
ICASSP 2015; prepared from LibriVox read audiobooks. Dataset revision is pinned
to `71cacbfb7e2354c4226d01e70d77d5fca3d04ba1`. The tool checks both the source
metadata SHA and the revision embedded in the dataset-viewer audio asset URL;
an unexpected revision fails rather than silently changing the corpus.

Selection was fixed before recognition: clean test offsets 0,250,...2250 and
other test offsets 0,290,...2610. The resulting set has 20 clips from 20 declared
speakers, ten per stratum, 130.805 s total and 340 normalized reference words.
Original FLAC and prepared 16 kHz mono PCM16 WAV hashes, row IDs, source assets,
speaker/chapter IDs and the dataset metadata are retained. No outcomes were used
to select or remove clips. Downloads are capped at 5 MB per compressed clip;
ffmpeg preparation is explicit and transcript references are not sent anywhere.

The clean/other distinction is corpus difficulty, not a controlled noise-SNR
experiment. This remains a small read-English diagnostic. It does not cover
Indian English conversational dictation, personal terminology, coding names,
Hinglish, interruptions or long-session app behavior. No exact-match entity labels
were fabricated for this corpus; that metric remains unmeasured here.

Broader same-family **backend proxy** result, one fresh-process decode per clip:

- Fixo Base English MLX: 20/20 successful; 29/340 word errors = **8.53%** normalized
  WER. Clean 5.26%, other 12.67%. Parent wall-time p50 0.971 s, p95 1.062 s.
- Base English whisper.cpp CLI proxy: 20/20 successful; 24/340 errors = **7.06%**
  normalized WER. Clean 4.74%, other 10.00%. Parent wall-time p50 0.230 s,
  p95 0.364 s.
- Paired descriptive speaker-cluster bootstrap (1,000 draws, seed 0), proxy-minus-
  Fixo normalized WER 95% interval: **−3.95 to +0.31 percentage points**. It crosses
  zero. No statistical or general product superiority claim follows.

The proxy's pinned Base English GGML weights are 147,964,211 bytes, SHA-256
`a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002`, from
the same immutable ggerganov repository revision recorded above. This compares
Base English model families with different model conversion, audio preprocessing
and decoder implementations; it is not an assertion of bit-identical weights or
identical decode settings. Source fingerprints were unchanged during this run.

Evidence: `/tmp/fixoflow-public-benchmark/librispeech-base-proxy-report.json`.
Its original manifest is preserved as `librispeech-subset/manifest-before-pinning.json`;
the current `manifest.json` adds verified pinned-source metadata without changing
the prepared audio/references. Future native comparisons use the current pinned
manifest. New paired reports include per-stratum metrics, distinct-audio/speaker
counts and a speaker-cluster bootstrap that does not treat repetitions as new
speakers. Missing speaker identities produce no confidence interval.

The explicit native build attempt uses Homebrew Rust/cargo 1.99.1 and
`cargo build --locked --release --example transcribe_wav` in the unchanged
temporary SpeakType checkout. Its log is retained at
`/tmp/fixoflow-public-benchmark/speaktype-native-build.log`. Final native build/run
outcome is recorded in the subsequent implementation evidence when available;
the proxy results above are not renamed as SpeakType results.
