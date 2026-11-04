"""Persistent-session and correction policies, with no microphone or UI access."""
import sqlite3

import pytest

from fixoflow.storage.db import FixoflowDB


def completed(db, text='Y is the build failing?', app='test.editor', language='en', mode='writing'):
    sid = db.begin_session('Editor', app, 'test-model', language, mode)
    db.record_session(text, text, 'Editor', 1, 10, mode=mode, session_id=sid)
    db.update_session(sid, status='completed')
    return sid


def test_existing_database_gets_additive_tables_without_changing_history(tmp_path):
    path = tmp_path/'old.sqlite'
    db = FixoflowDB(path)
    sid = db.record_session('old raw', 'old text', 'Old App', 2, 3)
    reopened = FixoflowDB(path)
    assert reopened.get_history()[0]['id'] == sid
    assert reopened.get_session_journal() == []
    with pytest.raises(ValueError, match='session context'):
        reopened.propose_correction(sid, 'new text')


def test_duplicate_history_save_does_not_duplicate_analytics(tmp_path):
    db = FixoflowDB(tmp_path/'test.sqlite')
    sid = completed(db, 'hello there')
    db.record_session('hello there', 'hello there', 'Editor', 1, 10, mode='writing', session_id=sid)
    assert len(db.get_history()) == 1
    assert db.get_total_stats()['total_words'] == 2
    with pytest.raises(ValueError, match='different transcript'):
        db.record_session('different', 'different', 'Editor', 1, 10, session_id=sid)


def test_unfinished_session_survives_reopen_without_being_marked_complete(tmp_path):
    path = tmp_path/'test.sqlite'
    db = FixoflowDB(path)
    sid = db.begin_session('Editor', 'test.editor', 'test-model', 'en', 'writing')
    db.update_session(sid, status='recording', audio_path='/test/audio.wav')
    row = FixoflowDB(path).get_session(sid)
    assert row['status'] == 'recording' and row['delivery_status'] == 'not_attempted'
    assert row['audio_path'] == '/test/audio.wav'


def test_pending_approval_forget_and_scope(tmp_path):
    db = FixoflowDB(tmp_path/'test.sqlite')
    original, corrected = 'Y is the build failing?', 'Why is the build failing?'
    sid = completed(db, original)
    cid = db.propose_correction(sid, corrected)
    assert db.propose_correction(sid, corrected) == cid
    assert db.apply_approved_correction(original, 'test.editor', 'en', 'writing') == (original, None)
    db.approve_correction(cid)
    assert db.apply_approved_correction(original, 'test.editor', 'en', 'writing') == (corrected, cid)
    for text, app, language, mode in [
        (original, 'test.other', 'en', 'writing'),
        (original, 'test.editor', 'hi', 'writing'),
        (original, 'test.editor', 'en', 'coding'),
        (original, 'test.editor', 'en', 'raw'),
        ('Y is the vertical coordinate', 'test.editor', 'en', 'writing'),
        ('the letter Y', 'test.editor', 'en', 'writing'),
    ]:
        assert db.apply_approved_correction(text, app, language, mode) == (text, None)
    db.forget_correction(cid)
    assert db.apply_approved_correction(original, 'test.editor', 'en', 'writing') == (original, None)


def test_homophones_are_not_global_replacements_and_rules_do_not_cascade(tmp_path):
    db = FixoflowDB(tmp_path/'test.sqlite')
    sid = completed(db, 'The child began to ball.')
    cid = db.propose_correction(sid, 'The child began to bawl.')
    db.approve_correction(cid)
    assert db.apply_approved_correction('Throw the ball.', 'test.editor', 'en', 'writing') == ('Throw the ball.', None)
    second = completed(db, 'The child began to bawl.')
    db.approve_correction(db.propose_correction(second, 'A rewritten thought.'))
    assert db.apply_approved_correction('The child began to ball.', 'test.editor', 'en', 'writing')[0] == 'The child began to bawl.'


def test_conflicts_require_forgetting_prior_rule(tmp_path):
    db = FixoflowDB(tmp_path/'test.sqlite')
    sid = completed(db)
    first = db.propose_correction(sid, 'Why is the build failing?')
    second = db.propose_correction(sid, 'Why did the build fail?')
    db.approve_correction(first)
    with pytest.raises(ValueError, match='conflicting'):
        db.approve_correction(second)
    db.forget_correction(first)
    db.approve_correction(second)


def test_delete_source_removes_memory_and_journal(tmp_path):
    db = FixoflowDB(tmp_path/'test.sqlite')
    sid = completed(db)
    db.approve_correction(db.propose_correction(sid, 'Why is the build failing?'))
    db.delete_history_item(sid)
    assert db.get_corrections() == [] and db.get_session(sid) is None


def test_contextual_proposals_never_apply_or_generalize_without_approval(tmp_path):
    db=FixoflowDB(tmp_path/'test.sqlite')
    source=completed(db,'Y is the build failing?')
    cid=db.propose_correction(source,'Why is the build failing?');db.approve_correction(cid)
    target=completed(db,'Y is the deployment failing?')
    suggestions=db.contextual_suggestions(target)
    assert suggestions[0]['text']=='Why is the deployment failing?'
    assert db.get_history()[0]['final_text']=='Y is the deployment failing?'
    assert db.apply_approved_correction('Y is the deployment failing?','test.editor','en','writing')[1] is None
    assert db.contextual_suggestions(completed(db,'Y is the vertical coordinate'))==[]
    # Context matching remains conservative and is ALWAYS a proposal.
    assert db.apply_approved_correction('Y is the vertical coordinate','test.editor','en','writing')[0]=='Y is the vertical coordinate'
    assert db.contextual_suggestions(completed(db,'the letter Y'))==[]
    assert db.contextual_suggestions(completed(db,'Y is the deployment failing?',app='other.app'))==[]
    db.undo_correction_approval(cid)
    assert db.contextual_suggestions(target)==[]
    assert db.apply_approved_correction('Y is the build failing?','test.editor','en','writing')[1] is None


@pytest.mark.parametrize('text', ['', '  ', None, [], 'x'*20001])
def test_invalid_feedback_never_creates_candidates(tmp_path, text):
    db = FixoflowDB(tmp_path/'test.sqlite')
    sid = completed(db)
    with pytest.raises(ValueError):
        db.propose_correction(sid, text)
    assert db.get_corrections() == []
