# Daily convenience implementation

2 November 2026. Owned workstream: appearance tokens and explicit mic checkup.
This document records source behavior and integration requirements. It does not
claim that all SpeakType convenience features, native appearance or publisher
acceptance are complete.

## Appearance

`fixoflow/appearance.py` exports `THEMES = ('light','dark','system')` and
`validate_theme(value)` (raises ValueError on another value).

`ui/hub.css` now supports `document.documentElement.dataset.theme` values:

- `light`: existing purple/cream appearance, unchanged token values.
- `dark`: dark surfaces, light text, readable green/purple supporting states.
- `system`: CSS media query follows `prefers-color-scheme: dark` automatically.
- Missing attribute: Light, preserving existing installations until a preference
  is chosen rather than unexpectedly changing their appearance.

Hardcoded supporting colors were converted to semantic tokens (error, input
disabled, graph idle, hover, recording and calendar surfaces). Textarea uses the
same tokens. `overlay.html` accepts `theme` in `updateControl(data)` and follows
the same Light/Dark/System policy; key colors, spinner, focus, glyph fills and
labels use theme variables. The cancel tooltip now says audio is retained for
recovery rather than implying all cancelled audio is already a History row.

Native host window/titlebar appearance still requires native integration and
acceptance; CSS cannot theme system chrome. The overlay receives its preference
through its existing update protocol; it does not independently read config.

Parent integration:

1. Add validated `config.theme` default `light`; allow through settings updates.
2. Add a Settings select and in `onConfigData` set root `data-theme` to the value;
   include the choice in acknowledged autosave values.
3. Include `theme: config.theme` in every overlay state render, including idle.
4. Native UI check should switch Light/Dark/System and verify computed palette,
   control values, persistence and minimum-window layout. Confirm visually on
   actual supported OSs before claiming complete contrast/accessibility.

## Explicit microphone checkup service

`fixoflow/audio/checkup.py` exports `MicrophoneCheckup(backend=None, clock=...)`.
Construction opens no hardware. No files, PCM queues, recordings or transcripts
are retained. It analyzes only peak, maximum RMS and current level scalars from
the live callback. Native-rate capture avoids rejecting a microphone merely
because it does not expose 16 kHz in this check; that does **not** add conversion
to normal dictation, whose existing capture contract remains 16 kHz mono.

Usage:

```python
checkup = MicrophoneCheckup()
checkup.start(selection=config.input_device, duration=5)  # explicit user action
data = checkup.snapshot()
checkup.cancel()
finished = checkup.close(timeout=2)
```

`start` allows 1–10 seconds and refuses another active check. Device resolution
uses existing explicit host/name selection; missing/ambiguous saved microphones
fail without falling back. The worker opens native default sample rate, mono
float32, `blocksize=0`. The callback does no UI dispatch or disk write.

Snapshot fields: `state` (`idle`, `starting`, `running`, `complete`, `cancelled`,
`error`); `level` 0–1; maximum `peak`; `clipping` when peak >= .99; `no_signal`
(None until successful completion); elapsed seconds; user-visible message;
`cleanup_required`. Signal threshold is a diagnostic heuristic (.003 maximum
RMS), not voice activity detection, speech recognition or a background-noise
quality score. Silence, clipping, invalid samples, callback errors, unresponsive
streams, cancellation and cleanup failures have distinct outcomes.

If close fails, the stream reference remains owned. New starts are refused and
`close()` retries cleanup. The parent must block dictation when `active` **or**
`needs_cleanup` is true, as well as block checkup during recording/processing.
Use a shared app/coordinator lock to prevent a checkup and dictation start racing;
service-level exclusion alone only prevents two checkups. Do not permit settings
device changes halfway through an active check. Quit/restart should call `close`
and stay open if it returns false. A snapshot must be polled/dispatched by the
native host; audio callbacks must never call WebKit directly.

Parent hub actions: `startMicrophoneCheckup` (explicit button),
`getMicrophoneCheckup`, `cancelMicrophoneCheckup`. Display status, level meter,
clipping/no-signal message and Cancel; label it “Signal check — no recording is
saved,” not an accuracy test. Existing OS permission flow remains authoritative.
The service does not request permissions silently or trigger checkup on launch.
Do not add diagnostic metrics/audio to History or correction learning.

## Verification

Owned tests use only fake hardware and generated numeric arrays. No real
microphone was opened, no speaker output played, no user audio read or uploaded.

- `tests/test_checkup.py`: constructor/invalid inputs do not open hardware;
  bounded duration; normal/no-signal/clipping scalars; error/invalid data;
  cancellation; single-owner exclusion; cleanup retry without lost ownership.
- `tests/test_appearance.py`: preference validation and dark text/supporting
  foreground/background token contrast >= 4.5:1 for selected combinations.
  This is deterministic token coverage, not a complete screenshot/accessibility
  audit of every component.
- Existing overlay geometry tests run as neighborhood regression coverage.

Official API documentation consulted:
[sounddevice 0.5.3 stream API](https://python-sounddevice.readthedocs.io/en/0.5.3/api/streams.html).
No additional runtime dependency is introduced.

Clipboard preservation and native tray panel remain separate work; this
workstream did not fabricate platform clipboard ownership/consumption guarantees.
