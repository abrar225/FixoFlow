"""
Unit tests for Fixoflow Text Polisher.
Verifies filler removal, spoken punctuation conversion, output styles,
fix counting, and zero-loss guarantees.
"""
from fixoflow.brain.polisher import TextPolisher, clean_with_rules, clean_with_rules_counted
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


def test_concise_style_trims_hedges_natural_keeps_them():
    natural = clean_with_rules_counted("basically this is fine", style="natural")
    assert natural[0] == "Basically this is fine"
    concise = clean_with_rules_counted("basically this is fine", style="concise")
    assert concise[0] == "This is fine" and concise[1] >= 1


def test_professional_style_expands_contractions():
    result, fixes = clean_with_rules_counted("I don't think we can't ship it", style="professional")
    assert result == "I do not think we cannot ship it"
    assert fixes >= 2


def test_verbatim_style_only_trims():
    result, fixes = clean_with_rules_counted("  um hello   world  ", style="verbatim")
    assert result == "um hello   world" and fixes == 0


def test_polish_counted_reports_fixes_for_the_session_record():
    polisher = TextPolisher(FixoflowConfig(mode="writing"))
    text, fixes = polisher.polish_counted("um hello world period")
    assert text == "Hello world." and fixes >= 2
    assert polisher.polish("um hello world period") == text
