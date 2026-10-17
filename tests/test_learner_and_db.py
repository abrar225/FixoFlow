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
        prompt = learner.get_dynamic_prompt_conditioning("Terminal", mode="coding")
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


def test_seed_vocabulary_runs_once_and_respects_deletions():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FixoflowDB(Path(tmpdir) / "test.sqlite")
        AdaptiveLearner(db)
        assert any(entry["phrase"] == "github" for entry in db.get_dictionary())
        db.delete_word("github")
        AdaptiveLearner(db)
        assert not any(entry["phrase"] == "github" for entry in db.get_dictionary())
