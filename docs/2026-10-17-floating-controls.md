# Floating controls and UI update

Implemented on 17 October 2026 for the user's request to match Wispr Flow's control workflow and improve Control–Space reliability.

## Observed gaps

The old overlay started hidden, ignored mouse events, and hid its contents after completion. It offered no persistent input button. Shortcut gesture decisions sampled recorder state even when recorder startup was still queued; a second fast tap could be interpreted as another start. Mouse/menu actions bypassed the hotkey's gesture owner. Toggle/hold configuration fields were not implemented by that owner. Status was disconnected from listener availability. Hub and CLI entry points owned different event loops and configuration instances.

Live reference inspection showed Wispr Flow's “Show Flow Bar at all times” setting, grouped light settings rows, black switches, neutral sidebar, and serif headings. No reference application preferences were changed. No reference dictation or cloud inference was invoked for this UI task.

## Changes

- Local WebKit bar in a nonactivating NSPanel, visible at idle by default, across Spaces and fullscreen contexts. The native panel can receive a first mouse click and cannot become the key/main window.
- Start/stop toggle, five-bar recording level, elapsed time, processing feedback, recording cancel, and settings shortcut. Completion/error feedback returns to the idle bar. The settings button works with the hub closed.
- DictationControls owns mouse, menu and keyboard intent synchronously while capture/decode commands execute in order. Processing input is ignored; stale held-key releases cannot stop a newer mouse session. Physical-key tracking handles modifier-first release and both Control keys. Auto-repeat does not spawn repeated sessions.
- Tap/hold, toggle-only and hold-only shortcut preferences. Escape preserves captured audio without transcription/insertion. Sound and persistent-bar preferences are backed by validated configuration.
- Light hub, monochrome iconography, accessible mode/switch controls, clear permission status, editable shortcut with alternate preset, and settings feedback driven by the native bridge. Returning from System Settings refreshes permissions without replacing unsaved preference edits.
- CLI start/hub route through the same single-instance application. Interactive terminal recording uses no disconnected overlay.

## Verification

67 source tests passed; scenarios include pending microphone startup, rapid taps, exact hold threshold, repeats, mixed keyboard/mouse input, cancellation, processing lockout, physical-key release with changed modifiers, preferences blocked during capture, invalid toggle values, permission refresh, and preservation of unexposed settings.

Native self-check executes the actual local WebKit page and IPC with substituted callbacks, verifying start/cancel/settings action delivery and disabled clicks during processing without recording or pasting. It also checks nonactivating panel flags and hub close/reopen. This does not establish real microphone or global shortcut behavior.

Live installed-app CUA verification: new hub renders, Settings opens, bar remains after closing the hub, bar exposes accessible Start dictation/Settings controls, actual bar Settings click restores the hub, and saved always-show preference produces zero visible idle bars when off and one when on (confirmed with OS window metadata). Preference is restored to on.

Accessibility and Input Monitoring remained ungranted on this device. Live microphone capture, global keyboard delivery, and insertion have not been certified under the final bundle; the app tells the user which OS permissions to grant. No OS permissions were granted by the agent.

The transcription model is unchanged. This update makes no new accuracy, RAM, battery, or complete-task performance claim. Idle UI is static; the recording timer runs only while recording. Existing memory limitations remain as described in the earlier assessment.

Final installed native build opens with matching Aqua titlebar. With the hub closed, a fresh CUA binding exposes Start dictation and Open Fixoflow settings, and a native screenshot confirms the persistent bar. Final DMG: 321,480,585 bytes; SHA-256 `2695f59a3021d6cfbe7c779cb28fe75eb9fb975cb3d4f7b94739ae941863ef8d`. Signature, isolated native bridge/self-check and image checksum validation passed. The bar is left visible with the persistent setting enabled.
