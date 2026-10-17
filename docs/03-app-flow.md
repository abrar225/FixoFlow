# App Flow: Fixoflow

## 1. Entry Points
- **Installed app:** `Fixoflow.app` (menu-bar application; the hub opens on first launch).
- **CLI:** `fixoflow start` (floating control only), `fixoflow hub`, `fixoflow record`, `fixoflow transcribe file.wav`.
- **Reopen:** launching again signals the running instance via `com.fixoflow.showHub` instead of starting a second copy.

---

## 2. Authentication Flow
- **Local application:** no accounts, passwords, or cloud logins.
- **macOS permission gates (one-time, user-granted):**
  1. *Microphone* — required for capture. Status shown in the hub; request button available.
  2. *Accessibility* — required for synthetic ⌘V insertion. Without it, transcripts still copy to the clipboard and a notification explains the fix.
  3. *Input Monitoring* — required for the global shortcut listener; restart after changing. Without it, the floating control still works.

---

## 3. Screen & State Inventory

| State | Mode | Purpose | Entry | Primary action | Failure | Success |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| **IDLE** | Background | Menu bar + floating control wait | Launched, permissions checked | Shortcut or click | Shortcut listener blocked → explicit detail in hub/menu | → RECORDING |
| **RECORDING** | Capture | 16 kHz blocks persisted to WAV | Shortcut tap/hold, floating control | Speak; Escape cancels | Mic unplugged → `RecordingError`, state rolls back | → PROCESSING |
| **PROCESSING** | Inference | Filter, slice, transcribe, format | Stop gesture | Wait (new starts disabled) | Chunk failure → partial `.transcript.json`, never a fake success | → insertion |
| **DELIVERY** | Insertion | Clipboard write, focus restore, ⌘V | Transcript ready | Automatic | `permission` / `event-failed` / `clipboard-failed` → notification + hub detail | → IDLE |

---

## 4. Mermaid Flowchart

```mermaid
flowchart TD
    Idle["IDLE: menu bar + floating control"] -->|Tap| RecToggle["RECORDING: latched"]
    Idle -->|Hold 0.45s| RecHold["RECORDING: push-to-talk"]
    RecToggle -->|Tap / click stop| Stop["Stop capture: WAV flushed and closed"]
    RecHold -->|Release| Stop
    RecToggle -->|Escape| Cancel["Cancel: audio retained, no ASR"]
    Stop --> Filter["Bandpass 80Hz-7.5kHz + normalize"]
    Filter --> Slice{"Longer than 24s?"}
    Slice -->|Yes| Chunks["Energy-valley slices"]
    Slice -->|No| One["Single chunk"]
    Chunks --> ASR["mlx-whisper on Metal GPU"]
    One --> ASR
    ASR -->|chunk fails| Partial["Partial text saved as .transcript.json"]
    ASR --> Format["Dictionary + mode formatting + polish"]
    Format --> Clipboard["Copy to clipboard first"]
    Clipboard --> Focus{"Target app frontmost?"}
    Focus -->|No| Restore["Activate target app"]
    Focus -->|Yes| Paste["Post Cmd+V"]
    Restore --> Paste
    Paste -->|permission missing or rejected| Notice["Notification + hub detail; clipboard holds the text"]
    Paste --> Done["History row + analytics update"]
    Notice --> Done
    Done --> Idle
```

---

## 5. Primary User Journey (Happy Path)

1. **User focus:** cursor is in an editor, terminal, mail, or chat.
2. **Activation:** user taps the shortcut (or holds it). `Tink` plays; the floating control shows "Listening" with elapsed time.
3. **Speech:** user speaks for 45 seconds, including natural pauses.
4. **Deactivation:** tap again or release the held key. `Basso` plays.
5. **Processing:** the WAV is already on disk; filtering and slicing run; each slice is transcribed locally; dictionary and mode rules format the transcript.
6. **Delivery:** the transcript is copied to the clipboard, focus returns to the original app if needed, and ⌘V is posted. History records app, duration, word count, and processing time.
7. **Failure path:** if paste cannot be posted, the notification says exactly why, the text is on the clipboard, and the session is in History.

---

## 6. Secondary Journeys

### Terminal dictation
- `fixoflow record` prompts for Enter to start and stop, prints the result, and reports the delivery outcome (pasted, clipboard untouched with `--no-paste`, or the failure reason).

### File transcription
- `fixoflow transcribe audio.wav` resamples to 16 kHz when needed, applies the configured mode formatting and polish, and prints raw and polished text.

### Permission setup
- Settings shows Accessibility / Input Monitoring / Microphone status. **Request permissions** raises all system prompts; per-permission buttons deep-link into System Settings.

### Configuration changes
- Saving settings validates the hotkey, persists atomically with a backup, rebuilds the recorder/STT/polisher on the live app, and restarts the shortcut listener when permitted.

---

## 7. Decision Points

| User action | Condition | Result | Destination |
| :-- | :-- | :-- | :-- |
| Press shortcut | IDLE | Recording starts; `Tink` | RECORDING |
| Release before threshold | Recording (hold gesture) | Latch stays recording | RECORDING |
| Release after threshold | Recording (hold gesture) | Stop and process | PROCESSING |
| Press shortcut / click stop | Recording (latched) | Stop and process | PROCESSING |
| Escape | Recording | Cancel; audio file retained | IDLE |
| Start while PROCESSING | — | Ignored; control disabled | PROCESSING |

---

## 8. Edge Cases and Recovery

1. **Empty audio / no speech:** pipeline aborts with a clear overlay message; nothing is pasted, History stays clean.
2. **Microphone failure or disconnect:** `RecordingError` surfaces; state returns to IDLE; already-flushed audio remains on disk.
3. **Accessibility missing:** clipboard-first insertion reports `permission`, raises the prompt, and notifies; the user pastes manually.
4. **Paste keystroke rejected:** `event-failed`; clipboard keeps the text; notification says to paste manually.
5. **No silence for slicing:** hard cut at 24 s with a cross-fade; sample count is preserved.
6. **Chunk decode failure:** partial text saved beside the audio as `.transcript.json`; the session is marked incomplete and never pasted as complete.
7. **Focus changed mid-dictation:** Fixoflow tries to reactivate the original app; if that fails, the transcript stays on the clipboard instead of being typed into the wrong window.
