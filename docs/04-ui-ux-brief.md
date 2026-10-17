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
- Collapsed: a small glass pill with a microphone button and the shortcut label.
- Recording: red mic button, "Listening", live elapsed time; a cancel control appears.
- Processing: "Transcribing", start disabled so clicks cannot queue another session.
- Error: short label such as "Copied · enable Accessibility" or "Saved · open History".
- A settings button opens the hub.

### Hub window (Cocoa + WebKit)
- Sidebar: Overview, History, Dictionary, Settings; footer states "On your Mac — Local audio & transcription".
- Overview: runtime status dot (Ready / Listening / Transcribing), shortcut state, words dictated, time saved (estimated at 40 WPM), speaking pace, session count, and per-app breakdown.
- History: searchable list with Copy and Delete; Clear history rebuilds analytics so the dashboard can never disagree with what is visible.
- Dictionary: phrase → replacement entries with review and remove; Add word form with category.
- Settings: control toggles, shortcut field with presets, dictation mode cards, local model selector, permission panel with live status and a Request permissions button.

### CLI
- Plain sentences, no emoji. `record` ends with an explicit delivery line: pasted at cursor, clipboard untouched (`--no-paste`), or the exact failure reason.

### Menu bar
- Status item with Start/Stop (shows the shortcut), mode selection (Coding / Writing / Automatic), Open Hub, Quit. Title reflects processing state.

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
