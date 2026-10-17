# Technical Requirements Document (TRD)

## 1. Technical Overview
- **Architecture summary:** Fixoflow is a Cocoa-run Python 3.12 application. A `pynput` listener adapts the global shortcut into recording gestures; the coordinator captures 16 kHz audio, persists it incrementally, filters and slices it, transcribes with `mlx-whisper` on the Metal GPU, formats with an offline rule engine, and delivers text clipboard-first via `NSPasteboard` + a synthetic ⌘V. A Cocoa/WebKit hub, floating control, and menu bar item are driven from the same process; a distributed-notification singleton guard keeps one instance alive.
- **Platforms:** macOS 14.0+ on Apple Silicon (ARM64).
- **Main technical constraints:**
  - 100% offline at runtime; no network calls, no model downloads.
  - Never report success for audio that was not persisted.
  - Never lose transcript text: clipboard-first insertion, History, and `.transcript.json` recovery files.

---

## 2. Technology Stack

| Layer | Chosen Technology | Reason | Rejected Alternatives |
| :--- | :--- | :--- | :--- |
| **Language runtime** | Python 3.12 | Fast iteration, first-class MLX and PyObjC bindings. | C++/Rust (build cost for a prototype). |
| **STT engine** | `mlx-whisper`, `mlx-community/whisper-base.en-mlx` | Native Metal GPU inference, no cloud, model snapshot pinned for packaging. | PyTorch Whisper (memory), cloud APIs (privacy). |
| **Audio I/O** | `sounddevice` (PortAudio) | Low-latency 16 kHz float32 capture via CoreAudio. | PyAudio (build friction). |
| **Acoustic filter** | `scipy.signal` Butterworth bandpass | 80 Hz–7.5 kHz filtering and peak normalization. | ML denoisers (model weight cost). |
| **Linguistic polisher** | Pure-Python rule engine (`brain/polisher.py`) + dictionary (`brain/learner.py`) | Zero extra RAM, instant, deterministic, fully offline. | Local LLMs (GBs of RAM), cloud polish (privacy). |
| **OS automation** | PyObjC (`AppKit`, `Quartz`, `ApplicationServices`, `AVFoundation`, `UserNotifications`) | `NSPasteboard`, `NSWorkspace` focus control, `CGEventPost`, permission APIs, notifications. | `pyautogui`/`pyperclip` (brittle wrappers). |
| **Global hotkey** | `pynput` keyboard listener | Key-down/up tracking for tap vs. hold gestures. | Deprecated Carbon APIs. |
| **GUI** | Cocoa window + WebKit HTML (`ui/hub.html`, `ui/overlay.html`) | Native window lifecycle with HTML/CSS rendering, no Electron. | Electron/Chromium (memory). |
| **Storage** | SQLite (`sqlite3`) | History, dictionary, app metadata, derived analytics. | JSON ledgers (concurrent-write fragility). |
| **Testing** | `pytest` | Fast, deterministic; boundaries simulated without hardware. | — |

---

## 3. System Architecture

```
Global shortcut (pynput) ─┐
Floating control (click)  ├─► DictationControls ─► FixoflowCoordinator.stop_and_process(
Menu bar (click)          ┘        (gesture/session state)          │
                                                                   ▼
  1. AudioRecorder     16 kHz mono; PCM blocks appended to WAV with flush+fsync; bounded queue
  2. filter.py         Butterworth bandpass 80 Hz–7.5 kHz, peak normalize (−1 dB FS)
  3. slicer.py         energy-valley slicing above 24 s; every sample preserved
  4. stt/engine.py     mlx-whisper on Metal GPU, vocabulary-conditioned initial prompt
  5. brain/learner.py  dictionary replacements (literal), spoken-code transforms per mode
     brain/polisher.py conservative writing cleanup, raw-text fallback on any failure
  6. platform/macos.py clipboard write → focus restore → CGEvent ⌘V → notification on failure
  7. storage/db.py     session row + daily analytics; deletes rebuild aggregates
```

### Component responsibilities
1. **AudioRecorder** — owns the stream, writer thread, and WAV header; overflow, disk failure, and close failure are explicit `RecordingError`s with retained ownership for cleanup retry.
2. **AudioSlicer / filter** — pure functions over arrays; never mutate input buffers.
3. **STTEngine** — resolves a validated local/bundled/cached model path; raises `TranscriptionError` with `partial_text` and `failed_chunk_index` on chunk failure.
4. **AdaptiveLearner** — owns dictionary seeding (once, via `app_meta`), prompt conditioning, and literal replacement.
5. **TextPolisher** — rule-based cleanup; preserves line breaks; returns input when rules would erase everything.
6. **macos platform module** — sole owner of permission state, focus, clipboard, insertion (`InsertionOutcome`), notifications, and sounds.
7. **FixoflowDB** — closing context-managed connections; analytics are derived and rebuilt on init and after deletes.

---

## 4. APIs and Integrations
- **CoreAudio (via PortAudio):** 16,000 Hz, mono, float32, 100 ms blocks. Failure → `RecordingError`, state rolls back to IDLE.
- **Quartz event services:** key code `0x09` (v) with `kCGEventFlagMaskCommand`. Requires Accessibility (`AXIsProcessTrusted`). Missing permission → clipboard-first fallback with prompt and notification.
- **AppKit NSWorkspace:** frontmost app name + bundle identifier captured at session start; `NSRunningApplication.activate` restores focus before insertion.
- **AVFoundation / UserNotifications:** microphone authorization status and requests; insertion-failure notifications with `NSUserNotification` fallback.
- **mlx-whisper:** array-based transcription (`transcribe(array)`), so no ffmpeg requirement in packaged builds.

---

## 5. Security and Privacy
- **Zero cloud transmission:** no runtime network code paths for dictation; `HF_HUB_OFFLINE=1` in frozen builds.
- **Private storage:** `~/.fixoflow/` for config, SQLite, and audio cache; logs under `~/Library/Logs/Fixoflow/`.
- **Input validation:** NaN/Inf/overflow checks before filtering; unknown config keys ignored; malformed JSON fails loudly rather than resetting user settings.
- **Secrets:** no API keys exist. Legacy `gemini_api_key`-style values are ignored, never read, and never re-saved.

---

## 6. Performance Requirements (targets, not claims)
- **Latency budget (5 s utterance):** flush < 15 ms · filter < 20 ms · GPU transcript < 450 ms · polish < 8 ms · paste < 35 ms → ~550 ms target. Actual end-to-end latency is unmeasured; see the [assessment](2026-10-17-assessment.md).
- **Memory:** original target was idle < 50 MB RSS and inference < 180–200 MB. Measured MLX inference exceeds this; the limitation is documented, not hidden.
- **CPU:** idle listening should remain a small single-digit percentage; not yet instrumented.

---

## 7. Testing and Quality
- **Boundary tests with simulations:** recorder (persistence before stop, overflow, disk failure, cleanup retry), coordinator (decode failure partials, focus change, focus restore, insertion failure outcomes), hub bridge (permission publishing, config preservation, request flow), macos insertion (clipboard-first ordering, flag correctness).
- **Data tests:** analytics rebuild after delete/clear, seed-once semantics, literal dictionary replacement.
- **Contract tests:** config legacy keys and malformed-file behavior.
- **Self-checks:** `--self-check` initializes real Cocoa/WebKit UI and model resolution without microphone or hotkey; the packaged app adds `--packaging-check [--inference]`.
- Tests never open the microphone or post real keystrokes; they do not establish recognition accuracy.

---

## 8. Development and Deployment
- **Environments:** `uv` virtualenv (`.venv`), Python pinned by `.python-version`/`nvm`-equivalent tooling.
- **Toolchain:** `setuptools`, `pytest`.
- **Packaging:** PyInstaller spec (`packaging/Fixoflow.spec`) produces a self-contained `Fixoflow.app` with `LSUIElement` (menu-bar app), bundled model, ad-hoc signature; DMG built by `scripts/build_dmg.sh`.
- **Run modes:** `fixoflow start` (background), `fixoflow hub`, or launching the app; single instance enforced by a lock file plus distributed notification that reopens the existing hub.

---

## 9. Technical Risks and Open Questions
- **Risk 1:** Synthetic ⌘V cannot be confirmed as accepted by the target app.
  - *Mitigation:* clipboard-first ordering, failure notification, History recovery.
- **Risk 2:** Long unbroken speech with no silence.
  - *Mitigation:* hard 24 s ceiling with cross-fade; every sample still reaches the recognizer.
- **Risk 3:** Memory ceiling of the Python/MLX stack.
  - *Mitigation:* documented; requires inference rework to meet the original target.
- **Risk 4:** App-context heuristics misclassify agents/websites.
  - *Mitigation:* explicit mode selection overrides auto mode.
