# Pinned model lifecycle and candidate qualification

2 November 2026. This work adds compatible English model choices and actual
local diagnostic evidence. It does not establish representative accuracy or
prove that a default recognizer should change.

## Implemented

`fixoflow/models/catalog.py` contains immutable Tiny, Base and Small English
model variants for MLX and CTranslate2. Every required asset, including config,
tokenizer/vocabulary and conversion README as applicable, has an expected byte
count and SHA-256. Repository revisions were retrieved from the public Hugging
Face APIs, and the small files were fetched at those revisions and hashed.
Weights' SHA-256 values come from the pinned Git LFS metadata and are verified
again against actual downloaded bytes during provisioning.

Candidate sizes, including the catalog's required metadata assets:

- Tiny English MLX: 74,418,371 bytes; revision `5f4dafbb28e62a53c1b10426ff7eed36ca733bf7`.
- Base English MLX: 143,723,699 bytes; revision `aa0678c3466ed62c5c6114ec600a0e1f96820089`.
- Small English MLX: 481,306,773 bytes; revision `52a88bf6e98b114a210c21bb83e22d6e1505cb73`.
- Tiny English CPU: 78,091,917 bytes; revision `0d3d19a32d3338f10357c0889762bd8d64bbdeba`.
- Base English CPU: 147,770,833 bytes; revision `3d3d5dee26484f91867d81cb899cfcf72b96be6c`.
- Small English CPU: 486,100,128 bytes; revision `d1d751a5f8271d482d14ca55d9e2deeebbae577f`.

Tiny is a speed candidate and Small a quality candidate to evaluate; those names
are not measured quality ratings. The catalog publishes no invented score bars.
Whisper's upstream weights/code use MIT; conversion repositories and their
README attribution remain linked/included. Catalog entries expose license and
repository data for UI/packaging notices.

`ModelManager` provides explicit installation, progress snapshots, disk-space
preflight, size/hash validation, safe staging, cancellation and verified
warm-up states. Existing installations are never overwritten, including damaged
ones that need a user-visible repair path. One worker owns the operation; busy
state and initial operation state are available synchronously to prevent UI
start races. Closing retains ownership while a worker is still stopping.

The manager does not change app preferences or select a model by itself. Parent
coordinator integration must exclude dictation while warming/switching and must
keep network provisioning explicit. Cancellation cannot interrupt a native
weight-load call midway; it is acknowledged after that call returns.

Inference recognizes `catalog:<id>`, validates compatible installed files and
does not download missing models. Verification is cached only while file inode,
size and nanosecond modification/change times remain unchanged. Local direct
model paths and existing bundled Base behavior remain supported.

Warm-up loads the actual local weights into the same inference holder without
decoding fake speech. CPU warm-up constructs the local-only CTranslate2 model;
MLX warm-up uses mlx-whisper's current ModelHolder and releases its old model
reference before switching. Runtime capability metadata explicitly states that
native decode is not interruptible and confidence is not calibrated.

Intel Darwin routing now chooses CPU rather than MLX. That is a source contract,
not Intel packaging qualification: faster-whisper must be included on Intel,
MLX dependency markers changed, a separate compatible native package produced,
and actual Intel hardware acceptance run. No Intel installer was built here.

## Executed checks

`pytest tests/test_models_lifecycle.py tests/test_stt.py tests/test_cpu_stt.py -q`:
**32 passed**. Covers immutable downloads, corrupted/truncated/oversized data,
preserving a damaged existing model, integrity-cache invalidation, cancellation
and cleanup, busy/close ownership, matching-engine warm-up, incompatible models,
offline catalog inference, CPU warm-up without decoding, and Intel routing.

`scripts/qualify_models.py --help` passed. The script accepts a list manifest or
the versioned benchmark manifest, verifies supplied audio hashes, supports
explicit `--download`, records artifact/runtime versions, separates weight-load
time and repeated decode timings, and records failed clips without calling them
successful. It does not open a microphone or upload recordings.

## Public diagnostic corpus

The actual diagnostic uses the same Homebrew whisper.cpp public JFK sample as
the benchmark workstream: `/opt/homebrew/share/whisper.cpp/jfk.wav`, approximately
11 seconds, SHA-256
`59dfb9a4acb36fe2a2affc14bacbee2920ff435cb13cc314a08c13f66ba7860e`.
Reference is the familiar inaugural-speech passage beginning “And so my fellow
Americans”. It is one easy historical clip, not a representative multi-speaker,
noise, accented, name/number, developer-vocabulary or Hindi/Hinglish corpus.

Tiny and Small English MLX were explicitly downloaded and fully SHA-256 verified
on this Apple Silicon host. The installed Base model at
`/Applications/Fixoflow.app/Contents/Resources/models/whisper` also matched the
pinned Base English asset checks, avoiding a duplicate baseline installation.

After initial diagnostic runs, the three models were run **sequentially** with
five repeated local decodes each. Every decode completed and each had zero
normalized word errors on this one clip. Final reports:

- `/tmp/fixoflow-tiny-model-qualification-sequential.json`: one weight warm-up
  0.6131 s; median decode 0.05931 s; five completed, zero failures.
- `/tmp/fixoflow-base-model-qualification-sequential.json`: warm-up 0.6307 s;
  median decode 0.09884 s; five completed, zero failures.
- `/tmp/fixoflow-small-model-qualification-sequential.json`: warm-up 0.6670 s;
  median decode 0.29275 s; five completed, zero failures.

Tiny was faster than Base in this bounded warm diagnostic. Small loads and
decodes successfully but has **not** demonstrated higher accuracy: all models
were perfect on this easy clip. Small remains the quality candidate requiring a
harder held-out corpus. These findings do not justify changing the default.

Filesystem/OS/GPU caches and host load were uncontrolled. These warm decode
figures are not comparable to the other workstream's fresh-process timings,
which include startup. Single weight warm-up timings are not cold/warm percentile
estimates. Repeated copies of one recording are not independent speech samples.

No CPU model inference, Windows/Linux qualification, battery measurement or
whole-process-family memory study was performed in this model workstream.

## Remaining qualification gates

- A held-out representative corpus is still required before recommending a
  quality winner or changing defaults. Zero errors on JFK does not prove equal
  accuracy between Tiny, Base and Small.
- Multilingual and Hinglish release gates stay intact. These six catalog entries
  are English only. Parakeet requires a separately qualified runtime/conversion
  and does not automatically solve Hindi/Hinglish support.
- Model removal/repair/offline-import UI and memory/battery budgets need further
  implementation/acceptance. Installed presence shown by snapshots is not an
  integrity assertion; validation happens before use.
- Current MLX warm-up uses the installed mlx-whisper ModelHolder API; future
  upstream runtime changes require contract validation and packaging checks.

Primary sources: [MLX Tiny conversion](https://huggingface.co/mlx-community/whisper-tiny.en-mlx),
[MLX Small conversion](https://huggingface.co/mlx-community/whisper-small.en-mlx),
[CTranslate2 faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[Whisper upstream](https://github.com/openai/whisper).
