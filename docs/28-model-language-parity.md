# Model and language parity implementation

3 November 2026. This supersedes the English-only availability description for
the new development source. Existing distributed 0.3.4 binaries do not acquire
these capabilities without a rebuilt release. Metadata support is distinct from
measured language accuracy.

## Delivered source

The pinned catalog now contains 16 backend-specific variants:

- Tiny, Base and Small English for MLX and CPU/CTranslate2 (six entries).
- Tiny, Base, Small and Large v3 Turbo multilingual for MLX and CPU/CTranslate2
  (eight entries). On the normal platform backend this is four multilingual
  choices, not eight different acoustic families.
- Parakeet TDT v2 English and v3 multilingual, both int8 ONNX (two entries).

All model files retain immutable repository revisions, expected byte lengths and
SHA-256 values in `fixoflow/models/catalog.py`. Config/tokenizer/vocabulary and
conversion README files are included in verification, not just weights. The
existing downloader remains explicit, bounded, cancellable and staged; inference
never downloads a missing model. Wrong backend/language combinations are rejected.
Turbo CPU models use vocabulary.json; the CPU validator now supports either
vocabulary.txt or vocabulary.json. The MLX Turbo entry is the compatible
weights.safetensors conversion, not an unrelated model.safetensors layout.

Runtime factories remain lazy. `create_stt_engine(config)` examines a known
catalog entry before selecting the host-default Whisper backend. Parakeet runs
through `onnx-asr[cpu]==0.12.0`, tested with ONNX Runtime 1.31.1. It is loaded using
`onnx_asr.loader.Manager.create_asr(..., quantization='int8', offline=True)` from
the SHA-verified local folder. This explicitly disables hub fallback even if a
file is missing. CPUExecutionProvider and the configured CPU-thread budget are
used for predictable baseline behavior. No implicit GPU/provider download occurs.

Parakeet shares the existing bounded WAV-file pipeline, partial-transcript
recovery and cancellation checks between native decodes. Native inference itself
is not interruptible. Its capability record reports no vocabulary-prompt support;
the application can still apply its approved text corrections after recognition.

The Parakeet int8 v3 assets were actually downloaded and verified (about 670 MB).
An initial CDN read timed out at the default 30-second socket timeout; the
explicit diagnostic retry used 120 seconds and succeeded. Existing installations
were preserved. The production downloader still exposes a failure/retry path
rather than silently retrying or replacing an installation.

## Model-aware language API

`fixoflow.languages` now exposes:

- `available_languages(model_name, backend=None)` → tuple of selectable codes;
  None denotes automatic detection.
- `validate_language_selection(language, model_name, backend=None)` → validates
  both computer/backend compatibility and supported selection.
- `options(model_name='bundled-base.en', backend=None)` → UI value/label records.
- `require_released_language` remains as a model-aware compatibility wrapper for
  current configuration callers.

English models offer English only. Multilingual Whisper entries offer Automatic
plus the conservative 99-language Whisper catalog, including Hindi, Chinese,
Japanese, Spanish and others. Translation and Roman transliteration are not
implied by selecting a spoken language. A token in a model vocabulary is not an
accuracy guarantee for a language, accent or code-switched conversation.

Parakeet v3 supports 25 European languages, automatically detected; it does not
accept a forced language. Therefore its selectable option is **Automatic only**,
while the catalog exposes all 25 supported language codes. Hindi is not included.
Parakeet v2 offers English. Intel Mac Parakeet is withheld pending native runtime
acceptance; Intel Whisper is routed through the CPU backend. This does not claim
a completed Intel package or universal OS/device support.

Explicit local Whisper folders can expose language support through compatible
model configuration. Unknown repository strings are not assumed multilingual.
The legacy Base model-pack backend now follows architecture-aware routing rather
than selecting MLX merely because the OS is Darwin.

Root configuration integration was reviewed: only incompatible old English-model
non-English/auto preferences are deferred. Valid catalog multilingual selections
must survive restart. A new isolated save/load test verifies Spanish plus a
multilingual catalog model and Automatic plus Parakeet v3 remain intact.

## Actual public non-English inference

One deterministic sample was retrieved from the public
[Meta Multilingual LibriSpeech dataset](https://huggingface.co/datasets/facebook/multilingual_librispeech),
Spanish test split row 0, dataset revision
`2e83e61823b4c47dcbcb1980bb88601274127609`. Dataset license is CC BY 4.0.
Attribution: Pratap et al., “MLS: A Large-Scale Multilingual Dataset for Speech
Research,” Interspeech 2020; source LibriVox read audiobooks. The sample is an
excerpt of Miguel de Unamuno poetry, original recording linked in the manifest.

The download was 68,704 bytes of viewer-served Opus; ffmpeg converted it to
16 kHz mono PCM16 WAV. The original, converted file, complete reference,
attribution and inference evidence are retained under
`build/parity-public-spanish/`. Converted WAV SHA-256:
`99ddaaf1436fe866a08dae0439964836bb91100dfc9bcc97b11da4657d9b4ee5`.
The manifest records the download hash, original recording interval, dataset
revision and transformation. No user audio was accessed or uploaded.

The source reference contains 31 words. Actual results on this one sample:

- Base multilingual MLX, forced Spanish: 4 normalized word errors, 0.306 s decode.
- Small multilingual MLX, forced Spanish: 1 normalized word error, 0.462 s decode.
- Parakeet v3 ONNX, automatic detection: 0 normalized word errors, 0.468 s decode.

All returned Spanish text, exercising actual non-English decoding and Parakeet
automatic language handling rather than only an English demo. Timings are single
warm diagnostic runs on this Mac, with uncontrolled host/cache conditions.
One poetry excerpt does not establish Spanish-wide accuracy, model superiority,
25/99-language quality, Hindi/Hinglish behavior or general end-to-end latency.

Additional English runtime diagnostics for verified Base/Small multilingual and
Parakeet v3 are preserved in `build/parity-model-evidence/`. They use the public
JFK excerpt and are also smoke checks, not representative benchmarks.

## Verification and integration requirements

Focused suite: **50 tests passed** across model lifecycle, Parakeet, MLX/CPU STT
and language tests. Coverage includes missing installed assets without network,
SHA/size corruption, incompatible backend/language, ONNX local-only loader
arguments, no forced language/hint claims, warm model reuse, chunk failures with
partial text, cancellation before decode, CPU Turbo vocabulary.json and persistent
multilingual selection. `git diff --check` passed during this workstream.

Root owns the following integration requirements:

- Include `onnx-asr[cpu]==0.12.0` and compatible ONNX Runtime in shipped packages.
  The isolated actual test installed them under `/tmp/fixoflow-onnx-runtime`;
  that temporary installation alone does not put them into a frozen application.
- PyInstaller must collect `onnx_asr` package data, notably bundled
  `preprocessors/data/*.onnx`, and ONNX Runtime native resources. These resources
  are used locally and must not be fetched at inference time.
- Query language options for the draft selected model; when switching to
  Parakeet v3 select Automatic. Preserve acknowledged autosave, no silent model
  downloading/switching and the existing model/mic maintenance lock.
- Retain Whisper MIT and Parakeet CC BY 4.0 notices/attribution. Catalog public
  metadata includes upstream links and attribution, and installed conversion
  README files remain present.

Read-only integration review found no model-operation/recording race in the
root flow: `controls.configure` excludes session start while launching work,
`maintenance_busy` remains true during worker execution, and settings use the
same idle guard. Warm-up uses the selected engine, not a second hidden model.
Direct internal coordinator callers must continue respecting those ownership
contracts; native Windows/Linux installed acceptance remains a separate gate.

Not yet executed here: inference with every catalog entry, Turbo loading,
Parakeet v2 loading, CPU multilingual inference, native Windows/Linux/Intel
runtime acceptance, memory/battery profiling or representative language studies.
These limits must remain visible in release language.

Primary runtime sources:
[onnx-asr usage](https://istupakov.github.io/onnx-asr/usage/),
[pinned v0.12.0 loader](https://github.com/istupakov/onnx-asr/blob/v0.12.0/src/onnx_asr/loader.py),
[NVIDIA Parakeet v3 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3),
[NVIDIA Parakeet v2 model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2).
