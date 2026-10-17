# UI/UX Design Brief: Fixoflow

## 1. Experience Goal
- **Desired feeling:** Quiet, native, dependable. Fixoflow should read as a small macOS utility, not an application you manage.
- **Adjectives:** 1) *Frictionless* — activated by shortcut, floating control, or menu bar; 2) *Candid* — failures name the exact reason and the recovery path; 3) *Lightweight* — one menu-bar item, one small window, one floating pill.
- **Avoid:** persistent overlays that cover the cursor, setup wizards, decorative animation, and any success message that the pipeline cannot back up.

---

## 2. Users and Context
- **Primary user:** developers and writers who dictate into many apps across a workday.
- **Environment:** macOS on Apple Silicon, often with a coding agent or terminal focused, sometimes in noisy rooms.
- **Accessibility:** every state change has a sound cue and text label; tap-to-toggle exists for users who cannot hold a key; the hub is keyboard navigable.

---

## 3. Auditory Direction
- **Recording start:** `/System/Library/Sounds/Tink.aiff`.
- **Stop / processing:** `/System/Library/Sounds/Basso.aiff`.
- **Failure that needs action:** desktop notification with the reason (e.g. "Copied to clipboard — enable Accessibility in Settings to paste automatically").
- Sounds respect the "Recording sounds" setting.

---

## 4. Component Language

### Floating control (always-on pill, or summoned)
- Shape: 92 × 30 pt capsule at rest — glass over a real `NSVisualEffectView` backdrop blur, 82% opacity while idle, full opacity on hover; the panel window is exactly the pill, so it never steals clicks from surrounding content.
- Idle: microphone glyph plus a shortcut key chip; hovering expands the capsule (~192 pt) to reveal "Click to dictate" and the settings button, then contracts on exit.
- Recording: expands to ~208 × 36 pt with an audio-reactive five-bar waveform, "Listening…", live elapsed timer, a stop button, and a cancel control.
- Processing: "Transcribing…" with a spinner; start is disabled so clicks cannot queue another session.
- Success: green check pops in with "Pasted" / "Transcribed!" / "Recording saved" for 2.5 s.
- Error: warm warning glyph with the reason (e.g. "Copied · enable Accessibility"); clicking the pill opens the hub for the fix.
- Placement: drag anywhere and the pill falls into the nearest of three snap slots — top center, bottom center, bottom right — with ghost-outline guides shown during the drag; the slot is saved to preferences. Dragging is anchored from every non-button area of the pill.
- Motion: width/height/resize, snap, and opacity all animate on a shared 0.18–0.26 s ease curve; `prefers-reduced-motion` and the macOS reduce-motion setting disable animation.

### Hub window (Cocoa + WebKit)
- Sidebar: Overview, History, Dictionary, Settings; footer states "On your Mac — Local audio & transcription".
- Overview: runtime status dot (Ready / Listening / Transcribing), shortcut state, words dictated, time saved (estimated at 40 WPM), speaking pace, session count, and per-app breakdown.
- History: searchable list with Copy and Delete; Clear history rebuilds analytics so the dashboard can never disagree with what is visible.
- Dictionary: phrase → replacement entries with review and remove; Add word form with category.
- Settings: control toggles, shortcut recorder (click the button, press the combination; Escape cancels, Backspace clears, presets included), dictation mode cards, local model selector, permission panel with live status, a Request permissions button, and Restart Fixoflow after granting Input Monitoring.

### CLI
- Plain sentences, no emoji. `record` ends with an explicit delivery line: pasted at cursor, clipboard untouched (`--no-paste`), or the exact failure reason.

### Menu bar
- Status item with Start/Stop (shows the shortcut), mode selection (Coding / Writing / Automatic), Open Hub, Restart Fixoflow, Quit. Title reflects processing state.

---

## 5. Interaction States & Motion
- **Tap:** latches recording until the next tap.
- **Hold (>0.45 s):** push-to-talk; release stops and processes.
- **Escape / Cancel:** stops capture, keeps the audio file, never pastes.
- **Motion:** none decorative; the pill state changes are immediate. Insertion happens as soon as the transcript exists.
- **Focus restore:** if another app was focused mid-dictation, Fixoflow attempts to reactivate the session's original app before pasting; failure means clipboard-only, never a paste into the wrong window.

---

## 6. Honest Feedback Rules
- "Paste sent" means a ⌘V event was posted — not that the other app accepted it.
- Failure labels state the cause and the location of the text (clipboard or History).
- Partial transcriptions are labeled incomplete; they are never presented as the full result.

---

## 7. Consistency Rules

### Always
- Copy to the clipboard before posting any keystroke.
- Sound cue + text label for every state transition.
- Native `NSPasteboard` and `CGEvent` primitives for insertion.
- Non-blocking audio I/O; the UI thread never waits on inference.

### Never
- Electron/Chromium runtimes.
- Network calls for dictation.
- Silent failures: every failed insertion produces a notification and a hub detail message.
- Discarding text under any error condition.
