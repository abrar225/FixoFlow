# English quality fixes and multilingual research

19 October 2026. Fixo Flow 0.3.2 development preview.

## Scope and decisions

The user approved implementation of English fixes and an English-only product
with **Multilingual coming soon**. New speech engines, cloud processing,
translation and Roman Hinglish remain research only. Existing model packs,
dictionary entries, transcripts and recordings are retained. The marketing
website is outside this update.

Transcription means writing the spoken language; translation means converting
it to another language. Roman Hinglish also needs a script policy. These are
separate capabilities and must be evaluated separately.

## English findings and implementation

1. **Auto mode bypassed writing formatting in conversational apps.** The old
   classifier treated ChatGPT and Claude as coding apps, and matched arbitrary
   app-name substrings. ChatGPT, Claude and Codex composers now use Writing
   behavior in Auto. Actual supported editors/terminals retain Coding behavior,
   including native Windows executable stems and Linux WM_CLASS aliases.
   Explicit Coding and Raw choices remain authoritative.
2. **Explicit ordinal sequences had no structural formatter.** Natural, Concise
   and Professional writing now turn consecutive sentence-start ordinals into
   numbered lines. Comma-separated boundaries emitted by the actual decoder are
   supported. This structures text without paraphrasing its content. Existing
   numeric lists, skipped/reordered markers, quoted sequences and ambiguous
   noun phrases are covered by negative controls. The rule is conservative,
   handles first through tenth, and does not infer every semantic list. Raw,
   Coding and strict Verbatim bypass it. Technical identifier case is retained.
3. **Proper nouns require spelling knowledge.** Existing personal dictionary
   entries condition recognition and replace exact misheard phrases. Prompt
   selection now deduplicates canonical spellings before applying its limit,
   so multiple aliases do not consume multiple vocabulary slots. Dictionary UI
   explains both recognition hints and exact corrections. The supplied
   `Visper Flow`, `VS Perflow`, and `wispr flow` spellings can explicitly map to
   `Wispr Flow`; these are personal choices, not a hardcoded product-wide brand
   substitution. No fuzzy global replacements were introduced.
4. **Ambiguous lost names cannot be recovered from text alone.** The supplied
   `VS Codex ... VS Codex` example represents two different intended names.
   Mapping that phrase globally would corrupt legitimate references to coding
   tools and cannot distinguish the two occurrences. Recovering these requires
   the original audio and better recognition/context, not guessed rewriting.

Reported example, with spoken punctuation commands still off:

> Firstly, we have to focus on this. Second, we have to focus on that. Third, we have to focus on both.

Produces:

1. We have to focus on this.
2. We have to focus on that.
3. We have to focus on both.

This is a deterministic formatting fix, not evidence that the acoustic model now
recognizes every English word correctly. The bundled English model is unchanged.

## English-only availability

The application offers English, with US/UK/India regional preferences using the
same recognizer. Other languages and auto-detection are not selectable, the
multilingual install action cannot initiate a download, and public preference
application rejects non-English requests. The Settings page states **Coming
soon** rather than offering an inaccurate experimental feature.

Loading an existing known non-English/auto preference defers it to the internal
`deferred_language` field and uses English. The prior experimental Base model
selection uses bundled English instead. Loading alone does not rewrite the
configuration; subsequent normal persistence retains the deferred choice and
backs up the previous file. Invalid unknown language values still fail validation
rather than being silently hidden. Packs are not deleted. Lower-level explicit
research scripts retain access to the language catalog and engine evaluations;
that is not a public delivery claim.

## Wispr Flow: observed client design versus unknown server behavior

Read-only inspection targeted installed Wispr Flow **1.6.1174**. No competitor
code was executed or copied into Fixo Flow, and no user account/history/credential
files were inspected.

Observed client contracts separate cloud transcription from optional formatting,
and raw text from formatted text. They carry dictionary vocabulary, correction
maps, language choices and bounded app/text context. An explicit Polish operation
is separate from ordinary transcription. Local edit-based dictionary learning is
preference-gated. These are static client observations, not captured requests or
proof of an active server model. Wispr's documentation independently confirms
cloud transcription and documents varying accuracy, mixed-language limitations,
dictionary corrections and structural list formatting.
[Accuracy and limitations](https://docs.wisprflow.ai/articles/4048537120-what-to-expect-from-flow-accuracy-and-known-limitations),
[dictionary](https://docs.wisprflow.ai/articles/4052411709-Teach-Flow-your-words-with-the-dictionary),
[formatting](https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-and-backtrack).

Current desktop cleanup documentation supersedes older switch instructions;
server weights, production prompts, routing and measured accuracy remain unknown.
A cloud product's output is not evidence that an offline 74M-parameter recognizer
can match its quality or resources.

Provenance:

- ASAR SHA-256: `dc56b610fb46d34dabf7871a270f307c665371de3f28b492c687eca2af09faf4`.
- REA inventory Evidence: `ev_69cdd231c550338d6cfef6abbdb5114c254920ff781016564efe57728d5f80bc`.
- Scoped Evidence: `ev_7ae192b42256ff847377a931ca7527f8091308fcc3a81b30cc17e6fb8f714001`.
- Coverage: 183 relevant inventory members; four selected semantic sources.
  The main bundle exceeded the analyzer's 1 GiB heap, so its findings use bounded
  inert source ranges with member hashes/byte spans. Three unpacked native
  companions disagreed with declared integrity metadata. Record-and-continue
  retained observed bytes; their cause was not established and they were not
  executed. This is not a complete semantic reconstruction or server audit.
- Full local report and byte provenance are retained in the task evidence folder
  `english-quality/wispr/report.md` and `findings.json`.

## Offline language-engine research

No engine below was downloaded, integrated or selected in this phase. Publisher
support lists and benchmark claims do not establish Fixo Flow quality or laptop
compatibility. Model revisions, runtime support, conversion provenance and terms
must be checked before an experiment or distribution decision.

1. **Whisper large-v3 / large-v3-turbo.** Familiar multilingual engine family and
   existing MLX/CTranslate2 paths make these relevant higher-resource candidates.
   The model card lists Base at 74M parameters and Turbo at 798M. It explicitly
   describes uneven language/accent performance and hallucination risk. Language
   tokens do not mean universal equal accuracy. Compare a larger optional pack
   on the same audio before choosing it; do not replace lightweight English by
   default. [Model card](https://github.com/openai/whisper/blob/main/model-card.md),
   [CPU runtime](https://github.com/SYSTRAN/faster-whisper).
2. **Qwen3-ASR-0.6B / 1.7B.** Publisher lists 30 languages including Hindi,
   English, Chinese and Japanese, plus Chinese dialects. It is a separate backend
   candidate, not a drop-in Whisper file. Published throughput does not establish
   single-user CPU or Apple Silicon latency, memory or mixed-language accuracy.
   Compare auto versus constrained language and verify native/Roman script output.
   [Publisher repository](https://github.com/QwenLM/Qwen3-ASR).
3. **Meta Omnilingual ASR.** Broad-coverage candidate with 1,600+ advertised
   languages and 300M/1B/3B/7B CTC/LLM families. Its own reported 7B result is CER
   below 10% for 78% of languages, not 99% accuracy for all languages. Language-
   script identifiers differ from Whisper's. CPU/macOS/Windows integration and
   lightweight packaging remain unverified here. Apache-2.0 is listed for code
   and models. [Publisher repository](https://github.com/facebookresearch/omnilingual-asr).
4. **Indic-specific engines.** IndicConformer is a 22-language comparison point;
   its publisher now recommends Indic-Transcribe-core. The latter advertises
   native-script recognition/code mixing for 25 languages, with 1.2B parameters
   and a 4.6 GB checkpoint. Gated custom terms and a different runtime require
   review. Native-script Hinglish claims do not prove Roman Hinglish quality or
   suitability for an 8 GB CPU laptop.
   [IndicConformer](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual),
   [Indic-Transcribe-core](https://huggingface.co/bodhan-ai/indic-transcribe-core).
5. **NVIDIA Parakeet TDT 0.6B v3.** Candidate for English and 25 European
   languages, with punctuation/capitalization support. Its listed languages do
   not include Hindi, Chinese or Japanese, so it cannot alone meet the global
   requirement. Test CPU/export support and accuracy against the same cases.
   [Publisher model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3).

## How to pursue maximum accuracy

These are proposed experiments, not implemented features or guaranteed results.

1. **Establish a representative baseline first.** Keep original audio, raw ASR,
   correction output and formatted output separately attributable. Include Indian,
   US and UK English; names, numbers, negation, lists, URLs, identifiers, silence,
   long speech and real fan/cafe noise. Use consented local recordings and licensed
   public test sets, not private audio sent to cloud services.
2. **Check capture before decoding.** Measure microphone selection, initial-word
   clipping, clipping peaks, sample rates and resampling. Compare unchanged audio
   against any VAD/denoising/normalization change; aggressive filtering can erase
   phonemes. Synthetic Gaussian noise alone does not prove robustness.
3. **Compare decoders on identical audio.** Pin weights, runtime and parameters;
   compare cold and warm runs. Current MLX versus CPU decoding settings differ.
   Evaluate beam search/fallback and segmentation/context carryover, including
   words crossing the current 24-second boundaries. Do not combine results from
   different hardware/audio into a single performance claim.
4. **Improve names through approved context.** Compare vocabulary hints, exact
   correction rules, pronunciation aliases and optional context biasing. Context
   reading/edit learning would require explicit scope and controls. No app text,
   clipboard or screen scraping was added. Never silently approve model guesses
   as dictionary facts.
5. **Treat language identification as a separate error source.** Compare a known
   selected language with automatic detection, including short clips and related
   languages. Test every advertised language on native references, multiple
   speakers, accents and noise. Use per-language capability and quality gates;
   do not enable 99 labels after only testing English.
6. **Evaluate code switching directly.** Hindi-English mixtures need mixed-language
   references, not monolingual Hindi scores. For the selected Roman Hinglish
   target, compare recognition plus a pinned local romanization step against
   human-reviewed Roman references, preserving English names/numbers. Report
   native-script recognition and Roman output scores separately. Translation
   must be an explicit task, not an accidental cleanup side effect.
7. **Separate structure from rewriting.** Test lists, paragraphs and punctuation
   independently from grammar/clarity rewrites. Preserve negation, numbers,
   named entities and technical identifiers; retain raw text/recovery. A fluent
   rewrite can conceal a recognition error. An optional local rewriting model
   needs its own memory, latency and fidelity evaluation before integration.
8. **Make hardware tradeoffs explicit.** Compare optional language packs and
   quantization against the same quality baseline on an 8 GB CPU Windows/Linux
   device and Apple Silicon. Record p50/p95 latency, real-time factor, CPU time,
   process-family peak memory and disk usage. Do not promise smaller models with
   unchanged accuracy, or use GPU batch benchmarks as low-end CPU estimates.
9. **Keep optional cloud separate.** If an offline configuration fails the agreed
   quality/resource target, present opt-in cloud candidates with concrete provider,
   cost, retention and consent choices. No cloud processing was added or benchmarked
   with user audio. It remains a future decision.

## What 99% would mean

There is no evidence for promising 99% across all languages, accents, noise,
names and low-end devices. Even Wispr documents varying quality. Define the
unit before making a claim: 1% WER, 1% CER, exact named-entity accuracy and
meaning-preserving formatting are different metrics. WER includes substitutions,
deletions and insertions and can exceed 100%; it is not a universal confidence
score. Chinese/Japanese cannot use naive whitespace-word scoring.

For promotion, propose independently reviewed, speaker-separated holdouts per
language/domain, documented normalization and tokenization, and confidence
intervals sampled by speaker/session. Also require explicit checks for name,
number and negation preservation, list-structure success, silence hallucinations
and acceptable CPU/RAM/latency. Agree thresholds with the user before calling a
language ready. Do not report a small synthetic test as population accuracy.

## Executed diagnostic and verification

Two offline synthetic Samantha clips at 160 words/minute used the existing
bundled Base English MLX model. No user audio was uploaded or inspected.

- Names without vocabulary: `In this case, whisper flow is much better than fixo flow.`
- Same audio with approved transcript-like terms `Wispr Flow, Fixo Flow`:
  `In this case, Wispr Flow is much better than Fixo Flow.`
- List raw ASR used commas between ordinal items. The initial formatter missed
  it; after the boundary fix, that same decoded text produces the three numbered
  lines shown above. Actual audio decoding, not only mocked transcript strings,
  informed this regression.
- Measured decode times were 1.51 s for the first names decode, 0.087 s for the
  hinted decode, and 0.110 s for the list decode; peak main-process RSS was
  474,415,104 bytes. Ordering includes cold/warm effects, so the time difference
  is not attributed to vocabulary and is not a product latency claim. Two clean
  generated clips are not representative of human voices, accents or noise.

Final verification for runtime commit `9561054bc3329301cef19bfae0eec72c4aabcb46`:

- Local regression suite: **226 passed, 3 skipped**; skipped native Windows/Linux
  cases were not represented as locally executed coverage.
- Real Cocoa/WebKit UI check passed across all six panels, including English-only
  availability, rejected non-English preference requests, dictionary behavior,
  autosave, isolated startup controls, history and bundled font/logo resources.
  This check does not open the microphone or register system shortcuts.
- [Portable CI](https://github.com/abrar225/FixoFlow/actions/runs/39211980249)
  passed on macOS, Windows and Linux.
- [Desktop preview CI](https://github.com/abrar225/FixoFlow/actions/runs/39211980222)
  passed both Windows and Linux jobs, including frozen UI/model checks and
  installation/smoke checks of the generated Windows setup and Debian package.
  Its `windows-preview` and `linux-preview` artifacts are development previews;
  runner smoke checks do not establish microphone/global-input/text-insertion
  behavior on every user's desktop, or compatibility with every Linux distro.
- The self-contained Mac 0.3.2 bundle passed signature and offline packaging
  checks and replaced the installed 0.3.1 app, with the previous bundle retained
  for rollback. The installed UI visibly reports 0.3.2, English-only recognition,
  and the multilingual Coming soon notice. Existing settings/history remain.
- After a protected local SQLite backup, the reported exact aliases and canonical
  `Wispr Flow` / `Fixo Flow` spellings were added through the installed app's
  personal dictionary UI. A check against those persisted entries verified both
  canonical terms appear in the recognition prompt, the reported aliases resolve,
  and the reported list becomes three numbered lines through Auto/ChatGPT writing
  formatting. No ambiguous `VS Codex` replacement was added. This check does not
  establish recognition accuracy on unseen human audio.
- The Mac DMG passed `hdiutil verify`; versioned local artifact:
  `dist/preview-0.3.2/9561054/Fixoflow-0.3.2-macos-arm64.dmg`
  (239,213,692 bytes; SHA-256
  `7943ee0ac2ecc0ada2440a6314d3e6b75556747a12c66aecf0185911813c1d99`).
  It is locally signed, **not Apple-notarized**. Windows remains unsigned.
  This work did not publish installers or modify/deploy the website.

**VERDICT: PASS** for the scoped English formatting, personal-dictionary and
English-only release criteria. General English recognition improvement, a 99%
multilingual claim and broad physical-device validation remain unverified.
