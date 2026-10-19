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
    result = TextPolisher(FixoflowConfig(mode="writing", spoken_commands=True)).polish("hello new paragraph world")
    assert result == "Hello\n\nWorld"


def test_coding_identifiers_are_verbatim():
    raw = "parseConfig API_KEY --verbose /tmp/config.py"
    assert TextPolisher(FixoflowConfig(mode="coding")).polish(raw) == raw


def test_polisher_never_calls_network(monkeypatch):
    import urllib.request
    def forbidden(*args, **kwargs):
        raise AssertionError("network access")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    polisher = TextPolisher(FixoflowConfig(mode="writing", spoken_commands=True))
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
    polisher = TextPolisher(FixoflowConfig(mode="writing", spoken_commands=True))
    text, fixes = polisher.polish_counted("um hello world period")
    assert text == "Hello world." and fixes >= 2
    assert polisher.polish("um hello world period") == text

def test_literal_punctuation_words_survive_without_commands():
    p=TextPolisher(FixoflowConfig(mode='writing'))
    assert p.polish('The colon is part of the body')=='The colon is part of the body'
    assert p.polish('This period was difficult')=='This period was difficult'
    assert 'buy' in clean_with_rules_counted('bullet buy milk',spoken_commands=True)[0].lower()
    assert 'apples' in clean_with_rules_counted('bullet point apples and bananas',spoken_commands=True)[0].lower()


def test_reported_ordinal_sequence_becomes_three_numbered_lines():
    raw='Firstly, we have to focus on this. Second, we have to focus on that. Third, we have to focus on both.'
    expected='1. We have to focus on this.\n2. We have to focus on that.\n3. We have to focus on both.'
    for style in ('natural','concise','professional'):
        assert TextPolisher(FixoflowConfig(mode='writing',output_style=style)).polish(raw)==expected
    for config in (FixoflowConfig(mode='raw'),FixoflowConfig(mode='coding'),FixoflowConfig(output_style='verbatim')):
        assert TextPolisher(config).polish(raw)==raw


def test_explicit_lists_preserve_intro_and_all_item_words():
    raw='My tasks: Firstly, keep API_KEY. Secondly, do not send the file. Thirdly, keep 3.14 and /tmp/config.py.'
    expected='My tasks:\n1. Keep API_KEY.\n2. Do not send the file.\n3. Keep 3.14 and /tmp/config.py.'
    assert clean_with_rules_counted(raw)[0]==expected
    assert clean_with_rules_counted(expected)[0]==expected


def test_ambiguous_or_nonconsecutive_prose_is_not_reformatted_as_a_list():
    cases=['First day was busy. Second day was quiet.',
           'First, keep this. Third, keep that.',
           'Second, keep this. Third, keep that.',
           'I came first, then second, then third.',
           'She said "Firstly, do this. Second, do that."',
           '`Firstly, do this. Second, do that.`',
           'First, do this. Second,']
    for raw in cases:
        assert clean_with_rules_counted(raw)[0]==raw


def test_actual_decoder_comma_separated_sequence_and_existing_numbering():
    raw='Firstly, we have to focus on this, second, we have to focus on that, third, we have to focus on both.'
    assert clean_with_rules_counted(raw)[0]=='1. We have to focus on this.\n2. We have to focus on that.\n3. We have to focus on both.'
    for raw in ['1. First, do this. 2. Second, do that.',
                'We discussed, firstly, this issue, secondly, that issue.']:
        assert clean_with_rules_counted(raw)[0]==raw


def test_list_item_identifiers_keep_their_case():
    raw='First, parseConfig is the function. Second, api_key is required.'
    assert clean_with_rules_counted(raw)[0]=='1. parseConfig is the function.\n2. api_key is required.'


def test_quoted_comma_ordinals_are_not_list_boundaries():
    for raw in ['First, the exact phrase is "wait, second, I disagree".',
                "First, the exact phrase is 'wait, second, I disagree'.",
                'First, the phrase is \u201cwait, second, I disagree\u201d.']:
        assert clean_with_rules_counted(raw)[0]==raw
