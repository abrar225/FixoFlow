import pytest
from fixoflow.evaluation import edit_distance, words, summarize


def test_weighted_wer_and_silence_separate_from_speech():
    rows = [
        dict(reference_words=1, word_errors=1, actual='wrong', elapsed_seconds=1),
        dict(reference_words=9, word_errors=0, actual='correct', elapsed_seconds=3),
        dict(reference_words=0, word_errors=2, actual='invented words', elapsed_seconds=2),
    ]
    result = summarize(rows)
    assert result['normalized_micro_wer'] == .1  # not mean per-clip WER (.5)
    assert result['empty_reference_with_output'] == 1
    assert result['stop_to_text_seconds_p50'] == 2
    assert result['stop_to_text_seconds_p95'] == pytest.approx(2.9)
    assert summarize([])['normalized_micro_wer'] is None


def test_normalization_and_insertions_are_measured():
    assert words('CAFÉ, hello!') == ['café', 'hello']
    assert edit_distance(['one'], ['two','three']) == 2  # WER may exceed 100%.
    assert edit_distance([], ['invented']) == 1
