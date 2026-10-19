# Fixo Flow 0.3.1: startup, autosave and Hinglish research

19 October 2026. Scope: the desktop product. Marketing site and public download
assets were not changed for this work. This document distinguishes implemented
behavior from proposed language experiments.

## User decisions

- Launch at login defaults on; start quietly with dictation controls available.
- Save after a short pause, with visible Saving/Saved status. Defer changes while
  dictation is recording/processing or captured input has not been released.
- Future Hinglish output should be Roman text: `kal meeting hai`. Existing Hindi
  remains a separate Devanagari preference. Hinglish is research, not ready support.
- English remains the default, offline processing remains the only implemented
  mode, and multilingual quality remains experimental. No extra models or cloud
  uploads were selected as part of this work.

## Implemented startup behavior

Settings now has **Start Fixo Flow when I sign in**, default on. Registration is
per user, on the first normal launch of an installed application. Developer runs,
packaging diagnostics and desktop self-checks do not register themselves.

- macOS 14+: native `SMAppService.mainAppService`. macOS may require approval in
  Login Items; the UI reports this rather than claiming approval. The installed
  bundle must have the Fixo Flow identifier and live in Applications. An Apple
  login launch event suppresses the main hub; ordinary Dock opens still open it.
- Windows: the current user's Run registration targets the frozen executable
  with `--background`; no administrator permission or RunOnce entry. The main
  window starts minimized, so its taskbar entry can reopen it. Windows Startup
  Apps can override the registration: the UI reports **registered**, not proof
  of effective OS enablement. The app does not modify undocumented
  `StartupApproved` registry data. Installer removal deletes only a Run command
  matching that installation.
- Linux desktop: a per-user XDG autostart entry starts the installed `/opt`
  application with `--background`. `TryExec` prevents launching a missing binary;
  off writes `Hidden=true`. Foreign files and symbolic links are preserved.
  Publication is exclusive; updates validate and write the opened owned inode
  rather than replacing a pathname that could have changed. Only supported
  graphical desktop sessions can run this GUI; startup does not add Wayland
  global-shortcut support.

First setup is recorded once. Ordinary subsequent launches and unrelated
preference saves do not recreate an item removed/disabled in system settings.
An explicit toggle is a new registration request. If saving preferences fails
after changing registration, the service attempts to restore its prior state
and reports any restoration failure. Linux's small owned entry updates use a
validated open file; forced termination during that write is not crash-atomic.
Startup registration failures remain visible and do not stop manual dictation.

References: [Apple login items](https://developer.apple.com/documentation/servicemanagement/smappservice),
[Apple login launch marker](https://developer.apple.com/documentation/coreservices/keyaelaunchedasloginitem),
[Microsoft Run keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys),
[XDG autostart](https://specifications.freedesktop.org/autostart/latest/).

## Implemented autosave behavior

Manual Save style/Save preferences buttons are removed. Each completed selection
schedules a save after **800 ms**. Rapid changes coalesce into one patch. Only
changed exposed fields are submitted, preserving internal preferences. Changes
are serialized and acknowledged by request identity, so a late response cannot
replace a newer draft. Native refreshes preserve pending edits. Pill dragging
publishes its own position update; both desktop windows share one mutation lock.

The UI shows Changes pending, Saving, Saved automatically, Waiting, or Not saved.
Waiting changes retry after dictation/input capture finishes; validation/disk/OS
errors retain the draft with Retry saving. Invalid model/language changes keep
the working configuration. Model downloads remain explicit. Quit is deferred
while a valid autosave is pending; failed drafts do not trap users in the app.
Forced process termination can lose an unsaved draft.

Only shortcut changes restart listeners. Other preferences retain the input
listeners; the existing coordinator retains warm inference unless model,
language or CPU budget changes. Saving does not restart the application.
The explicit Restart action still exists for OS permission changes.

## Multilingual and Roman Hinglish R&D

### Findings

Whisper's language catalog has Hindi and English but no Hinglish token. A label
must be a product profile, not an invented backend language code. Existing Base
and Small Hindi tests in [the previous verification record](11-reliability-and-multilingual-preview.md)
were poor; neither is evidence of reliable Hinglish. Current script prompts are
hints, and adding a romanization instruction risks prompt echoes/translation.
Roman output needs recognition **and** separately evaluated transliteration;
romanization cannot recover words the recognizer missed.
[Whisper language tokens](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py).

### Offline candidates to compare, not selected replacements

1. **Existing Base/Small multilingual** with automatic versus forced-Hindi
   decoding, and no-prompt versus existing Hindi hint controls. These give a
   measured baseline using already approved local packs.
2. **Whisper large-v3-turbo**, an optional higher-resource experiment, using an
   equivalent CPU/Apple decoder and pinned converted weights. It keeps a familiar
   engine family but has more parameters than Base; low-end suitability needs
   measurement. [Whisper models](https://github.com/openai/whisper),
   [faster-whisper runtime](https://github.com/SYSTRAN/faster-whisper).
3. **Qwen3-ASR-0.6B**, a separate-backend experiment. Its publisher lists 30
   languages including Hindi, English, Chinese and Japanese and Apache-2.0
   licensing. This does not establish Fixo Flow CPU performance or Roman Hinglish
   quality. The standard runtime brings different dependencies; retain it as
   optional research until offline packaging and all three platforms are tested.
   [Publisher repository](https://github.com/QwenLM/Qwen3-ASR).
4. **Indic-specific comparison**: IndicConformer lists 22 Indian languages and
   MIT licensing, with gated access. Its publisher now points to
   **Indic-Transcribe-core**: native-script/code-mixed recognition, 25 languages,
   1.2B parameters and a 4.6 GB checkpoint, with gated custom terms. Those are
   publisher descriptions, not our results. It is not a lightweight default or
   an automatic redistribution choice. Review access/terms and actual CPU/macOS
   compatibility before any download/integration.
   [IndicConformer](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual),
   [Indic-Transcribe-core](https://huggingface.co/bodhan-ai/indic-transcribe-core).

### Proposed evaluation, before enabling a Hinglish option

- Use a pinned, licensed human Hindi-English test subset. MUCS provides a
  5.18-hour Hindi-English test set of technical lectures, listed CC BY-SA 4.0.
  It is useful but domain-specific; also collect consented everyday messages,
  names, numbers and meetings across accents, devices and background noise.
  Dataset downloads/decoding have **not** been executed in this phase.
  [MUCS dataset and licensing](https://navana-tech.github.io/MUCS2021/data.html).
- Keep speakers/sessions separate between tuning and evaluation. Fix model
  revision, decoding parameters and raw reference transcripts; compare models
  on identical clips and hardware. No instruction prompt may become transcript.
- Report raw mixed-script WER/CER and English/name/number retention. For Roman
  Hinglish, preserve English spans and compare a pinned local transliterator
  against independently reviewed Roman references. Report native and Roman
  scores separately, since transliteration can hide recognition errors.
- Include silence, music, fan/cafe noise, interruptions and long code-switched
  utterances. Synthetic Gaussian noise alone does not establish robustness.
- Measure cold/warm time, p50/p95 latency, real-time factor, CPU time, process-
  family peak memory and disk size on Apple Silicon and 8 GB Windows/Linux CPU
  machines with 1/2/4-thread budgets. Publisher GPU throughput is not a laptop
  benchmark. No new resource estimates are represented as measurements.
- Review results with the user before choosing a model, transliterator, quality
  threshold or pack size. Keep English lightweight and multilingual optional.
  Do not advertise all listed languages as equally accurate.

## Verification record

- Full local suite: **214 passed, 3 skipped** (native Windows/Linux-only checks).
- Native Cocoa/WebKit check: all six panels, actual bridge, rapid/debounced saves,
  late acknowledgements, dictation waiting, explicit retry, startup toggle,
  font/logo and minimum viewport passed with an isolated database and no user
  preference writes, microphone capture or OS registration.
- The ServiceManagement framework imported and its native status query ran in
  development mode; it correctly reported no main app service for the Python
  host. The frozen Mac build imported the real framework and passed resource,
  native dependency and offline-model packaging diagnostics.
- Independent read-only review found three issues (Linux publication ownership,
  cross-window mutation serialization and blocking file lock); all were fixed
  and covered by regression checks. Final review found no remaining blockers.
- Final Mac 0.3.1 source: `480854c`. The self-contained bundle is installed at
  `/Applications/Fixoflow.app`; signature/resource/offline-model checks passed.
  It uses the existing local signing identity and is not notarized. Settings,
  History, recordings and dictionary were preserved.
- Installed native acceptance: the app started, showed 0.3.1, registered with
  macOS, and its startup toggle saved off without restarting. The entry
  disappeared from System Settings → Open at Login. Turning it on saved and
  restored the system entry; it was left **on**. This establishes actual
  registration/unregistration, not a full logout/login cycle.
- The Mac DMG was rebuilt and `hdiutil verify` passed. Preview filename:
  `Fixoflow-0.3.1-macos-arm64.dmg`, 239,978,505 bytes. SHA-256:
  `978c2769ae35f0ca111994bd94c106eeb6f8267dd3c5f0bb3ec9f2624788a479`.
- Portable CI passed for `480854c` on macOS, Windows and Ubuntu:
  [run 39208171622](https://github.com/abrar225/FixoFlow/actions/runs/39208171622).
- Native package CI passed on the same source:
  [run 39208171717](https://github.com/abrar225/FixoFlow/actions/runs/39208171717).
  Windows: **177 passed, 6 platform-specific skips**; Linux: **181 passed,
  2 platform-specific skips**. Both passed frozen UI/bundled decode, installer
  generation, installation and installed-app checks. Windows registration was
  tested against an isolated real HKCU key; Linux entry tests used temporary
  directories. These are not interactive user-session reboot tests.
- Preview archives (GitHub sign-in may be required):
  [Windows x64 installer](https://github.com/abrar225/FixoFlow/actions/runs/39208171717/artifacts/12167095209),
  [Linux x64 Debian installer](https://github.com/abrar225/FixoFlow/actions/runs/39208171717/artifacts/12166068715).
  They are CI preview artifacts, not public releases or website updates. Signing
  and broader physical-device acceptance gates from the prior release record
  remain open.
- Temporary 0.3.1 rebuild bundles were removed after final installed verification;
  the previous 0.2.0 rollback bundle was retained.
- The first Linux frozen UI run exposed a lock held across a synchronous
  WebView callback. Mutation ownership was narrowed to the startup/configuration
  write; callbacks run outside it. A cross-thread regression verifies that
  content loading does not block bridge callbacks. The corrected frozen UI
  check passed on the final native Linux runner.
OS status may lag a successful registration change. The service keeps the requested checkbox while polling for up to 10 seconds, then reports any unconfirmed system state. This prevents a stale response immediately reverting a fresh toggle.

Actual logout/reboot behavior requires interactive OS-session acceptance;
simulated events and isolated registration tests cannot establish that coverage.
