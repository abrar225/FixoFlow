# Contributing to Fixo Flow

Fixo Flow is a free, MIT-licensed community dictation project. Contributions to
reliability, accessibility, packaging, documentation and measured speech quality
are welcome. Start with a small issue or pull request and describe the actual
behavior you observed.

## Report a problem

Use [GitHub Issues](https://github.com/abrar225/FixoFlow/issues). Include:

- Fixo Flow version and where you downloaded it.
- OS version, CPU architecture and desktop session (X11/Wayland on Linux).
- Reproduction steps, expected behavior and the exact error text.
- A redacted log or screenshot, if useful. Never include personal dictation,
  recordings, access tokens or private documents without informed consent.

An installer download failure, an operating-system security block and a speech
recognition error are different problems. Please identify which stage failed.

## Development and review

Use Python 3.12. Create a virtual environment and install the relevant platform
extra plus `dev`; see the README for commands. Run `pytest tests/ -q` and the
checks relevant to your change. Native microphone, shortcuts, focus/paste and
OS trust claims need real platform evidence; unit tests alone do not prove them.

Keep changes focused. Explain the problem, behavior change, checks run and known
limitations in your pull request. Screenshots should show the actual interface
and contain no personal history. Changes to language availability need a
representative consented evaluation; do not advertise unsupported accuracy.

Speech stays offline by default. Do not introduce telemetry, cloud processing,
unprompted model downloads or security-protection bypasses as incidental fixes.
Keep dependency/model notices intact. Contributions are submitted under the
project's [MIT License](LICENSE).
