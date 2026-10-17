"""
Unit tests for Fixoflow Text Polisher.
Verifies filler removal, spoken punctuation conversion, and zero-loss guarantees.
"""
from fixoflow.brain.polisher import TextPolisher, clean_with_rules
from fixoflow.config import FixoflowConfig


def test_clean_with_rules_fillers_and_punctuation():
    raw = "Um hello world period this is uh like you know a test comma right question mark"
    expected = "Hello world. This is a test, right?"
    result = clean_with_rules(raw)
    assert result == expected


def test_clean_with_rules_bullet_points():
    raw = "Here are the steps colon bullet one install fixoflow period bullet two speak naturally period"
    result = clean_with_rules(raw)
    assert "•" in result
    assert "Install fixoflow." in result


def test_polisher_zero_loss_guarantee():
    polisher = TextPolisher(FixoflowConfig(polishing_engine="rules"))
    assert polisher.polish("um") == "um"


def test_writing_preserves_paragraphs():
    result = TextPolisher(FixoflowConfig(mode="writing")).polish("hello new paragraph world")
    assert result == "Hello\n\nWorld"


def test_coding_identifiers_are_verbatim():
    raw = "parseConfig API_KEY --verbose /tmp/config.py"
    assert TextPolisher(FixoflowConfig(mode="coding")).polish(raw) == raw


def test_polisher_never_calls_network(monkeypatch):
    import urllib.request
    def forbidden(*args, **kwargs):
        raise AssertionError("network access")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    polisher = TextPolisher(FixoflowConfig(mode="writing"))
    assert polisher.polish("hello period") == "Hello."
