"""
Fixoflow Local Database
SQLite storage for dictation history, personal vocabulary, app metadata and
daily usage analytics. Analytics is a derived aggregate over `history` and is
rebuilt whenever history changes, so the dashboard can never drift from the
sessions it summarizes.
100% offline and local on disk (~/.fixoflow/fixoflow.sqlite).
"""
from __future__ import annotations

import contextlib
import datetime
import logging
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger("fixoflow.storage.db")


class FixoflowDB:
    _instance: Optional[FixoflowDB] = None

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            base_dir = Path.home() / ".fixoflow"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = base_dir / "fixoflow.sqlite"
        else:
            self.db_path = db_path
        self._init_tables()
        self.rebuild_analytics()

    @classmethod
    def get_instance(cls) -> FixoflowDB:
        if cls._instance is None:
            cls._instance = FixoflowDB()
        return cls._instance

    @contextlib.contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME NOT NULL,
                    app_name TEXT,
                    asr_text TEXT NOT NULL,
                    final_text TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    word_count INTEGER NOT NULL,
                    latency_ms REAL NOT NULL,
                    mode TEXT NOT NULL,
                    audio_path TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON history (timestamp DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_app ON history (app_name)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dictionary (
                    phrase TEXT PRIMARY KEY,
                    replacement TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    frequency INTEGER NOT NULL DEFAULT 1,
                    auto_learned INTEGER NOT NULL DEFAULT 0,
                    last_used DATETIME NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dictionary_freq ON dictionary (frequency DESC)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytics_daily (
                    date TEXT PRIMARY KEY,
                    total_words INTEGER NOT NULL DEFAULT 0,
                    total_seconds REAL NOT NULL DEFAULT 0.0,
                    sessions_count INTEGER NOT NULL DEFAULT 0,
                    avg_wpm REAL NOT NULL DEFAULT 0.0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

    # ------------------------------------------------------------------
    # App metadata
    # ------------------------------------------------------------------

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # ------------------------------------------------------------------
    # History and analytics
    # ------------------------------------------------------------------

    def record_session(
        self,
        asr_text: str,
        final_text: str,
        app_name: str,
        duration_sec: float,
        latency_ms: float,
        mode: str = "auto",
        audio_path: str = "",
    ) -> str:
        """Record a completed dictation session and update derived analytics."""
        session_id = str(uuid.uuid4())
        now = datetime.datetime.now()
        word_count = len(final_text.split())

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history (id, timestamp, app_name, asr_text, final_text, duration_sec, word_count, latency_ms, mode, audio_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, now.isoformat(), app_name, asr_text, final_text, duration_sec, word_count, latency_ms, mode, audio_path),
            )
            date_str = now.strftime("%Y-%m-%d")
            conn.execute(
                """
                INSERT INTO analytics_daily (date, total_words, total_seconds, sessions_count, avg_wpm)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_words = total_words + excluded.total_words,
                    total_seconds = total_seconds + excluded.total_seconds,
                    sessions_count = sessions_count + 1,
                    avg_wpm = CASE WHEN (total_seconds + excluded.total_seconds) > 0
                        THEN ROUND((total_words + excluded.total_words) / ((total_seconds + excluded.total_seconds) / 60.0), 1)
                        ELSE 0.0 END
                """,
                (date_str, word_count, duration_sec,
                 round(word_count / (duration_sec / 60.0), 1) if duration_sec > 0 else 0.0),
            )
        return session_id

    def rebuild_analytics(self) -> None:
        """Recompute daily analytics from history so it cannot drift."""
        with self._connect() as conn:
            conn.execute("DELETE FROM analytics_daily")
            conn.execute(
                """
                INSERT INTO analytics_daily (date, total_words, total_seconds, sessions_count, avg_wpm)
                SELECT substr(timestamp, 1, 10) AS day,
                       SUM(word_count), SUM(duration_sec), COUNT(*),
                       CASE WHEN SUM(duration_sec) > 0
                            THEN ROUND(SUM(word_count) / (SUM(duration_sec) / 60.0), 1)
                            ELSE 0.0 END
                FROM history
                GROUP BY day
                """
            )

    def get_history(self, limit: int = 50, search: str = "", app: str = "") -> List[Dict[str, Any]]:
        """Fetch recent history with optional text search and app filtering."""
        query = "SELECT * FROM history WHERE 1=1"
        params: list = []

        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query += " AND (final_text LIKE ? ESCAPE '\\' OR asr_text LIKE ? ESCAPE '\\')"
            params.extend([f"%{escaped}%", f"%{escaped}%"])
        if app:
            query += " AND app_name = ?"
            params.append(app)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def delete_history_item(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM history WHERE id = ?", (session_id,))
        self.rebuild_analytics()

    def clear_all_history(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM history")
        self.rebuild_analytics()

    # ------------------------------------------------------------------
    # Dictionary / vocabulary
    # ------------------------------------------------------------------

    def upsert_word(
        self,
        phrase: str,
        replacement: str,
        category: str = "general",
        auto_learned: int = 0
    ) -> None:
        phrase_clean = phrase.strip()
        repl_clean = replacement.strip()
        if not phrase_clean:
            return

        now = datetime.datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dictionary (phrase, replacement, category, frequency, auto_learned, last_used)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(phrase) DO UPDATE SET
                    replacement = excluded.replacement,
                    frequency = frequency + 1,
                    last_used = excluded.last_used
                """,
                (phrase_clean, repl_clean, category, auto_learned, now),
            )

    def seed_word(self, phrase: str, replacement: str, category: str = "general") -> None:
        """Insert a built-in entry only when the phrase is not present.

        User deletions of built-in terms stay deleted.
        """
        phrase_clean = phrase.strip()
        if not phrase_clean:
            return
        now = datetime.datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dictionary (phrase, replacement, category, frequency, auto_learned, last_used)
                VALUES (?, ?, ?, 1, 0, ?)
                ON CONFLICT(phrase) DO NOTHING
                """,
                (phrase_clean, replacement.strip(), category, now),
            )

    def increment_word_usage(self, phrase: str) -> None:
        now = datetime.datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE dictionary SET frequency = frequency + 1, last_used = ? WHERE phrase = ?",
                (now, phrase.strip()),
            )

    def get_dictionary(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM dictionary ORDER BY frequency DESC, last_used DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_word(self, phrase: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM dictionary WHERE phrase = ?", (phrase.strip(),))

    def get_vocabulary_prompt_terms(self, limit: int = 40) -> List[str]:
        """Most frequent and recently used terms used to condition the decoder."""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT replacement FROM dictionary ORDER BY frequency DESC, last_used DESC LIMIT ?",
                (limit,),
            )
            return [row["replacement"] for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Analytics reads
    # ------------------------------------------------------------------

    def get_daily_analytics(self, days: int = 14) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM analytics_daily ORDER BY date DESC LIMIT ?", (days,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_total_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT SUM(total_words) as words, SUM(total_seconds) as seconds, SUM(sessions_count) as sessions FROM analytics_daily"
            ).fetchone()
            words = row["words"] or 0
            seconds = row["seconds"] or 0.0
            sessions = row["sessions"] or 0

            # Estimate time saved against 40 WPM typing.
            typing_time_min = words / 40.0
            speaking_time_min = seconds / 60.0
            time_saved_min = max(0.0, typing_time_min - speaking_time_min)

            return {
                "total_words": words,
                "total_seconds": round(seconds, 1),
                "total_sessions": sessions,
                "time_saved_minutes": round(time_saved_min, 1),
                "avg_wpm": round((words / (seconds / 60.0)), 1) if seconds > 0 else 0.0
            }

    def get_app_breakdown(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT app_name, COUNT(*) as count, SUM(word_count) as total_words
                FROM history
                WHERE app_name != ''
                GROUP BY app_name
                ORDER BY total_words DESC
                LIMIT 10
                """
            )
            return [dict(row) for row in cursor.fetchall()]
