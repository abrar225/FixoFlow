"""Design-token contrast and explicit preference contract, not screenshot QA."""
import re
from pathlib import Path

import pytest

from fixoflow.appearance import THEMES,validate_theme


def luminance(color):
    channels=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in channels]
    return sum(x*w for x,w in zip(linear,[.2126,.7152,.0722]))


def contrast(a,b):
    bright,dark=sorted([luminance(a),luminance(b)],reverse=True)
    return (bright+.05)/(dark+.05)


def test_theme_preferences_are_explicit():
    assert THEMES==('light','dark','system')
    for theme in THEMES:assert validate_theme(theme)==theme
    for invalid in ('',None,'blue'):
        with pytest.raises(ValueError):validate_theme(invalid)


def test_dark_body_and_supporting_tokens_have_readable_contrast():
    css=(Path(__file__).parents[1]/'fixoflow/ui/hub.css').read_text()
    body=re.search(r':root\[data-theme="dark"\]\{([^}]+)\}',css)[1]
    tokens=dict(re.findall(r'--([a-z-]+):(#[0-9a-fA-F]{6})(?:;|$)',body))
    for foreground in ('text','muted'):
        for background in ('canvas','surface','row'):
            assert contrast(tokens[foreground],tokens[background])>=4.5,(foreground,background)
    for foreground,background in [('green-deep','mint'),('green-deep','green-soft'),('plum','canvas')]:
        assert contrast(tokens[foreground],tokens[background])>=4.5,(foreground,background)
    assert '@media(prefers-color-scheme:dark)' in css
    assert ':root[data-theme="system"]' in css
