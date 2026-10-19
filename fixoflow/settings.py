"""Shared preference-application outcomes for both native hosts."""


class SettingsBusy(RuntimeError):
    """A valid change can be retried once dictation/captured input is idle."""
