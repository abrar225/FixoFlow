"""Shared appearance preference validation; native hosts render their own chrome."""

THEMES = ('light', 'dark', 'system')


def validate_theme(value):
    if value not in THEMES:
        raise ValueError('Appearance must be Light, Dark or System.')
    return value
