# Product Requirements Document (PRD)

## 1. Product Overview
- **Product name:** Fixoflow
- **One-sentence description:** A 100% local voice dictation app for macOS Apple Silicon that captures, transcribes, formats, and inserts text into any application while keeping audio and transcripts on disk.
- **Problem being solved:**
  1. Cloud dictation tools (Wispr Flow and similar) require subscriptions and send voice data to third-party servers.
  2. Electron-based tools idle at hundreds of megabytes of RAM.
  3. Long monologues risk truncation when a pipeline assumes short recordings.
  4. Insertion failures usually lose text or report success without evidence.
- **Why this product should exist:** To give macOS users a private, zero-cost dictation workflow that is honest about what it delivered: every session is stored locally, and insertion failures are reported with a recovery path.

---

## 2. Target Users
- **Primary user:** Developers, technical writers, and professionals on Apple Silicon who dictate long, technical thoughts into editors, terminals, coding agents, email, and chat.
- **Their current problem:** Cloud tools violate privacy and cost money; existing local tools are unreliable on long recordings or lose text when insertion fails.
- **Their desired outcome:** Speak naturally for any duration, stop, and have formatted text placed at the cursor — or, if that is impossible, know immediately and find the text on the clipboard or in History.
- **Secondary users:** Privacy-conscious users and air-gapped researchers who cannot send audio anywhere.

---

## 3. Core User Outcome
A user speaks a continuous thought of any length in any macOS application. On stop, the entire recording is transcribed locally, formatted according to the active mode, inserted at the cursor of the app that started the session when possible, and always recorded in local History. If insertion cannot complete, the transcript is already on the clipboard and a notification explains why.

---

## 4. Core Features

### Feature 1: Global Shortcut with Two Gestures
- **User need:** Low-friction activation for both short insertions and long paragraphs.
- **What it does:** A quick tap latches recording on/off. Holding past 0.45 s is push-to-talk and stops on release. The floating control and menu bar offer the same toggle by click.
- **Inputs:** `pynput` global key listener (requires Input Monitoring); clicks on the floating control.
- **Expected output:** Recording starts immediately with a `Tink` cue; stop plays `Basso`; state is visible in the floating control, menu bar, and hub.
- **Acceptance criteria:** Key-up in hold mode stops recording; Escape cancels and retains the audio file; repeated start clicks while processing do not queue a second recording.
- **Error states:** If the listener cannot run, the menu extra and hub explain which permission is missing; the floating control always remains usable.

### Feature 2: Acoustic Pre-Filtering & Normalization
- **User need:** Reduce mic rumble and hiss before recognition to avoid phonetic errors.
- **What it does:** Applies an 8th-order Butterworth bandpass (80 Hz–7.5 kHz) and peak normalization to −1 dB FS.
- **Inputs:** 16 kHz mono float32 PCM.
- **Acceptance criteria:** 40 Hz hum attenuated by >24 dB while speech-band tones pass at unity gain; no NaN/Inf on silence or clipping.
- **Error states:** Filtering failure retains the raw buffer; the recording is never discarded.

### Feature 3: Pause Slicing (No Truncation)
- **User need:** Multi-minute dictations must not be cut off.
- **What it does:** Audio longer than 24 s is sliced at low-energy breathing pauses; hard cut at 24 s with a cross-fade when no silence exists.
- **Acceptance criteria:** `sum(len(slices)) == len(original)` — every sample reaches the recognizer.
- **Error states:** A failed chunk is reported as an incomplete session with the partial text saved next to the audio; partial results are never pasted as complete.

### Feature 4: Local Metal Whisper Engine
- **User need:** Fast, accurate recognition with no cloud dependency.
- **What it does:** Runs `mlx-community/whisper-base.en-mlx` through mlx-whisper on the Apple Silicon GPU, conditioned with an initial prompt built from approved vocabulary.
- **Acceptance criteria:** Recognized text is returned for every nonempty chunk; missing models produce an actionable error instead of a download.
- **Error states:** Inference failure surfaces `TranscriptionError` with partial text and the failed chunk index.

### Feature 5: Offline Formatting & Personal Dictionary
- **User need:** Correct names, jargon, and coding identifiers without a cloud LLM.
- **What it does:** Applies dictionary replacements (literal strings, never regex templates), spoken-code transforms in coding mode (`camel case`, `snake case`, `dash dash`, punctuation words), and conservative writing cleanup that preserves line breaks and never erases all text.
- **Acceptance criteria:** Dictionary entries condition the recognizer and rewrite final text; user deletions of seeded terms stay deleted; unknown/legacy config keys never break startup.
- **Error states:** Any formatting failure falls back to the raw transcript.

### Feature 6: Clipboard-First Insertion with Honest Reporting
- **User need:** Text should appear where the cursor is, and never be lost silently.
- **What it does:** Copies the transcript to the clipboard, then posts a synthetic ⌘V to the app that started the session (refocusing it first if the user focused another window mid-dictation).
- **Outcomes:** `inserted` · `permission` (clipboard kept, Accessibility prompt raised) · `event-failed` (clipboard kept) · `clipboard-failed` (History only). Failures raise a desktop notification and are shown in the hub and CLI.
- **Acceptance criteria:** No keystroke is posted before the clipboard write succeeds; an unidentified target app is never guessed at.
- **Error states:** Posting a keystroke does not prove the receiving app accepted it; History remains the recovery path.

---

## 5. Scope

### Included in Version One
- 100% offline runtime: zero network calls, no accounts.
- Global shortcut (default `Ctrl+Space`) with tap and hold gestures.
- Butterworth bandpass pre-filtering and pause slicing.
- Metal GPU Whisper (bundled base.en model in DMG builds).
- Rule-based offline formatting, personal dictionary, and spoken-code commands.
- Session WAV persistence during capture with `.transcript.json` partial recovery.
- Clipboard-first insertion with notification and hub reporting.
- Cocoa/WebKit hub (Overview, History, Dictionary, Settings), floating control, menu bar item.
- Local SQLite history, dictionary, derived analytics; live permission panel.
- CLI: `start`, `hub`, `record`, `transcribe`, `config`.

### Explicitly Excluded from Version One
- Cloud transcription, cloud polishing, or telemetry of any kind.
- Running local LLMs (Ollama or similar) for polishing.
- Multi-user or team features.

### Possible Later Additions
- Correction feedback with provenance, per-app profiles, and undo.
- Developer ID signing and notarization for distribution.
- Replacing the Python/MLX inference path to meet the 200 MB memory target.

---

## 6. User Stories
- **US1:** As a developer, I want to dictate a 2-minute architectural explanation into a PR description with zero words missing, so I can draft faster than typing.
- **US2:** As a privacy-conscious user, I want all audio and transcripts to stay on my Mac with zero network calls.
- **US3:** As an engineer, I want technical terms and identifiers spelled my way, with `getUserId` and `--verbose` produced from speech.
- **US4:** As a user whose paste occasionally fails, I want the text already on my clipboard with a clear explanation instead of silent loss.

---

## 7. Functional Requirements
- **FR1:** Capture at 16,000 Hz, mono, float32.
- **FR2:** Persist audio to a timestamped WAV during capture, flushing and fsyncing queued blocks; failed persistence is an explicit error.
- **FR3:** Segment audio above 24 s at silence points without dropping samples.
- **FR4:** Condition the Whisper decoder with approved vocabulary.
- **FR5:** Copy transcripts to the clipboard before posting any ⌘V event.
- **FR6:** Store every completed session in local SQLite; deleting history rebuilds daily analytics from remaining rows.
- **FR7:** Load legacy/unknown config keys without failing; never read ambient API keys.

---

## 8. Non-Functional Requirements
- **Performance:** Stop-to-text should feel sub-second for short dictations on M-series hardware; measured values are reported in the assessment, not assumed.
- **Reliability:** Failed chunks produce partial text files, never silent success.
- **Privacy:** Zero network packets during dictation.
- **Compatibility:** macOS 14+ on Apple Silicon.
- **Resource honesty:** The Python/MLX stack currently exceeds the original 200 MB peak memory target; this is documented as a known limitation rather than claimed away.

---

## 9. Success Criteria
1. Every nonempty recording yields either inserted text or an explicit, recoverable failure.
2. Daily analytics always match the sessions visible in History.
3. Legacy configurations from cloud-era releases load and run offline.
4. Two permission states degrade gracefully: no Accessibility → clipboard + notification; no shortcut permission → floating control still dictates.

---

## 10. Assumptions and Open Questions
- **Assumption:** The user grants Microphone, Accessibility, and Input Monitoring permissions to the packaged app (not to a terminal).
- **Open question:** Whether the MLX inference path can be replaced or reworked to satisfy the 200 MB memory ceiling.
- **Open question:** Accuracy vs. Wispr Flow / WisprType on this user's speech is unmeasured; no comparative claim is made.
