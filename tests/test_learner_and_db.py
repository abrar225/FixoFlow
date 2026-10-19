import datetime
import tempfile
from pathlib import Path
from fixoflow.storage.db import FixoflowDB
from fixoflow.brain.learner import AdaptiveLearner


def test_db_history_and_analytics():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite"
        db = FixoflowDB(db_path)

        # Record a session
        sess_id = db.record_session(
            asr_text="hello world testing voice dictation",
            final_text="Hello world, testing voice dictation.",
            app_name="Visual Studio Code",
            duration_sec=3.0,
            latency_ms=450.0,
            mode="coding"
        )
        assert sess_id is not None

        history = db.get_history()
        assert len(history) == 1
        assert history[0]["app_name"] == "Visual Studio Code"
        assert history[0]["word_count"] == 5

        stats = db.get_total_stats()
        assert stats["total_words"] == 5
        assert stats["total_sessions"] == 1


def test_adaptive_learner_code_mode_formatting():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite"
        db = FixoflowDB(db_path)
        learner = AdaptiveLearner(db)

        # Test camelCase spoken transform
        text1 = "create function camel case get user profile"
        res1 = learner.format_for_mode(text1, mode="coding", app_name="VS Code")
        assert "getUserProfile" in res1

        # Test snake_case spoken transform
        text2 = "run command snake case parse config file"
        res2 = learner.format_for_mode(text2, mode="coding", app_name="Terminal")
        assert "parse_config_file" in res2

        # Test CLI flags
        text3 = "pytest dash dash verbose single dash s"
        res3 = learner.format_for_mode(text3, mode="coding", app_name="Terminal")
        assert "--verbose" in res3
        assert "-s" in res3

        db.upsert_word("claude code", "Claude Code")
        db.upsert_word("antigravity", "Antigravity")
        # Test AI agent naming
        text4 = "ask claude code and antigravity to optimize this"
        res4 = learner.format_for_mode(text4, mode="coding", app_name="Cursor")
        assert "Claude Code" in res4
        assert "Antigravity" in res4


def test_dynamic_prompt_conditioning():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite"
        db = FixoflowDB(db_path)
        learner = AdaptiveLearner(db)

        # Add custom technical vocabulary
        db.upsert_word("superfast api", "SuperFastAPI", category="code")
        prompt = learner.get_vocabulary_prompt()
        assert "SuperFastAPI" in prompt


def test_dictionary_replacement_is_literal_not_a_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FixoflowDB(Path(tmpdir) / "test.sqlite")
        learner = AdaptiveLearner(db)
        db.upsert_word("log path", r"C:\1\logs")
        assert learner.format_for_mode("check log path now", mode="writing", app_name="") == r"check C:\1\logs now"


def test_deleting_history_rebuilds_analytics():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FixoflowDB(Path(tmpdir) / "test.sqlite")
        first = db.record_session("a", "one two three", "Terminal", 2.0, 100.0)
        db.record_session("b", "four five", "Mail", 1.0, 100.0)
        assert db.get_total_stats()["total_sessions"] == 2

        db.delete_history_item(first)
        stats = db.get_total_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_words"] == 2

        db.clear_all_history()
        stats = db.get_total_stats()
        assert stats == {"total_words": 0, "total_seconds": 0, "total_sessions": 0,
                         "time_saved_minutes": 0.0, "avg_wpm": 0.0}


def test_learner_has_no_implicit_developer_dictionary_and_keeps_existing_terms(tmp_path):
    db = FixoflowDB(tmp_path / "test.sqlite")
    AdaptiveLearner(db)
    assert db.get_dictionary() == []
    db.upsert_word("github", "GitHub")
    AdaptiveLearner(db)
    assert db.get_dictionary()[0]["replacement"] == "GitHub"
    db.delete_word("github")
    AdaptiveLearner(db)
    assert db.get_dictionary() == []


def test_counted_learner_reports_dictionary_and_code_fixes():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FixoflowDB(Path(tmpdir) / "test.sqlite")
        learner = AdaptiveLearner(db)
        db.upsert_word("claude code", "Claude Code")
        text, fixes = learner.format_for_mode_counted("ask claude code now", mode="writing", app_name="")
        assert "Claude Code" in text and fixes >= 1
        text, fixes = learner.format_for_mode_counted("pytest dash dash verbose", mode="coding", app_name="Terminal")
        assert "--verbose" in text and fixes >= 1


def test_fix_totals_aggregate_from_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FixoflowDB(Path(tmpdir) / "test.sqlite")
        db.record_session("a", "one two", "Mail", 1.0, 50.0, fixes_polish=3, fixes_vocab=2)
        db.record_session("b", "three", "Mail", 1.0, 50.0, fixes_polish=1, fixes_vocab=0)
        db.upsert_word("fizz buzz", "FizzBuzz")
        stats = db.get_fix_stats()
        assert stats["polish_fixes"] == 4 and stats["vocab_fixes"] == 2
        assert stats["dictionary_total"] == 1 and stats["dictionary_uses"] == 1


def _insert_days_ago(db, days_ago, words):
    stamp = (datetime.datetime.now() - datetime.timedelta(days=days_ago)).isoformat()
    with db._connect() as conn:
        conn.execute(
            "INSERT INTO history (id, timestamp, app_name, asr_text, final_text, duration_sec, word_count, latency_ms, mode, audio_path)"
            " VALUES (?, ?, '', 'a', ?, 2.0, ?, 10.0, 'auto', '')",
            (f"row-{days_ago}-{words}", stamp, " ".join(["word"] * words), words),
        )


def test_streak_counts_consecutive_days_and_survives_gaps():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FixoflowDB(Path(tmpdir) / "test.sqlite")
        assert db.get_streak() == {"current": 0, "best": 0, "last_date": None, "active_days": 0}
        for days_ago in (0, 1, 2, 4, 5):
            _insert_days_ago(db, days_ago, 10)
        db.rebuild_analytics()
        streak = db.get_streak()
        assert streak["current"] == 3 and streak["best"] == 3
        assert streak["active_days"] == 5


def test_today_and_week_activity_fill_missing_days():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FixoflowDB(Path(tmpdir) / "test.sqlite")
        _insert_days_ago(db, 0, 12)
        _insert_days_ago(db, 2, 8)
        db.rebuild_analytics()
        today = db.get_today_stats()
        assert today["total_words"] == 12 and today["sessions_count"] == 1
        week = db.get_week_activity(7)
        assert len(week) == 7 and week[-1]["is_today"] and week[-1]["active"]
        assert [day["active"] for day in week] == [False, False, False, False, True, False, True]
        assert week[-1]["words"] == 12 and week[-3]["words"] == 8

def test_dictionary_is_one_pass_symbol_aware_and_has_complete_coverage(tmp_path):
    db=FixoflowDB(tmp_path/'dictionary.sqlite');learner=AdaptiveLearner(db)
    db.upsert_word('alpha','beta');db.upsert_word('beta','gamma');db.upsert_word('C++','CPP')
    for i in range(250):db.upsert_word(f'word{i}',f'replacement{i}')
    for _ in range(2):
        assert learner.format_for_mode('alpha C++ word249 word0', 'writing','Mail')=='beta CPP replacement249 replacement0'
    db.increment_word_usage('beta')
    assert learner.format_for_mode('alpha', 'writing','Mail')=='beta'


def test_longest_valid_dictionary_match_does_not_hide_shorter_term(tmp_path):
    db=FixoflowDB(tmp_path/'dictionary.sqlite');learner=AdaptiveLearner(db)
    db.upsert_word('new york','NY');db.upsert_word('new','fresh');db.upsert_word('yorker','Yorker')
    assert learner.format_for_mode('new yorker and new york', 'writing','Mail')=='fresh Yorker and NY'
    db.upsert_word('नाम','पहचान')
    assert learner.format_for_mode('नामों नाम','writing','Mail')=='नामों पहचान'


def test_vocabulary_prompt_does_not_invent_app_or_format_instructions(tmp_path):
    db=FixoflowDB(tmp_path/'dictionary.sqlite');learner=AdaptiveLearner(db)
    assert learner.get_vocabulary_prompt()==''
    db.upsert_word('maya desai','Maya Desai')
    assert learner.get_vocabulary_prompt()=='Maya Desai'
