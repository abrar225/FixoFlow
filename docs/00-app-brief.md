# App Brief

App name: Fixoflow

One-line idea: A local-only voice dictation app for Apple Silicon Macs that captures speech at 16 kHz, transcribes it with Whisper on the Metal GPU, formats it with an offline dictionary and rule engine, and inserts it into the app you were already using.

Problem it solves:
- Cloud dictation tools send voice audio to third-party servers and require paid subscriptions.
- Heavy Electron-based dictation tools consume hundreds of megabytes of idle RAM.
- Long dictations can be truncated by fixed context windows or network timeouts.
- Most tools give no honest recovery path when insertion into the target app fails.

Who it is for:
- Developers and writers on Apple Silicon who dictate long thoughts into editors, terminals, coding agents, mail, and chat, and want their recordings to stay on the machine.

The main action a user should complete:
- Press the global shortcut (default `Ctrl+Space`, configurable), speak, and stop (tap again or release the held key). The transcript is pasted at the cursor of the app that was frontmost when dictation started, and is always stored in local History.

Must-have features (implemented):
- Global shortcut with tap-to-toggle and hold-to-talk gestures, plus a click-to-toggle floating control.
- 16 kHz mono capture; audio blocks are written, flushed, and fsynced to a recovery WAV during recording.
- Butterworth bandpass filtering (80 Hz–7.5 kHz), peak normalization, and energy-valley slicing above 24 s.
- Local Whisper (`mlx-community/whisper-base.en-mlx`) via mlx-whisper with prompt conditioning from approved vocabulary.
- Offline formatting: personal dictionary replacements (literal text), spoken-code transforms in coding mode, rule-based writing cleanup.
- Clipboard-first insertion: text is copied before any keystroke; failed insertion is reported and never presented as a successful paste.
- Native hub (Cocoa + WebKit HTML) with Overview, History, Dictionary, and Settings tabs; menu-bar item; floating control with shortcut label and elapsed time.
- Local SQLite storage with derived daily analytics, per-app breakdown, and explicit deletes that rebuild aggregates.

Nice-to-have features (implemented or partial):
- Menu bar status icon with start/stop control and mode selection.
- Desktop notifications for insertion failures (UserNotifications, legacy fallback).
- Live permission panel (Accessibility, Input Monitoring, Microphone) with a one-click request button and a Restart Fixoflow action (macOS applies grants only to a freshly started app; the shortcut then activates by itself).
- `fixoflow transcribe` for existing audio files (resamples to 16 kHz, applies formatting and polish).

Platform:
- macOS 14+ on Apple Silicon (M1/M2/M3/M4).

Business model:
- 100% free and open source. No accounts, no recurring fees.

Important constraints:
- 100% offline at runtime: no cloud transcription, no cloud polishing, no telemetry.
- Legacy cloud settings must load as inert values without breaking startup.
- The recorder must never claim success for audio that was not persisted.
- Insertion failure must leave the text recoverable without opening the app.

References or existing products:
- Wispr Flow (cloud, subscription; reference for workflow, not for architecture).
- WisprType (local WhisperKit baseline).
- Neither has been runtime-compared for accuracy on this user's speech; see the [assessment](2026-10-17-assessment.md).
