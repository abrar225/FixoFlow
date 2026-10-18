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

            cursor.execute("CREATE TABLE IF NOT EXISTS session_artifacts (path TEXT PRIMARY KEY, root TEXT NOT NULL, identity TEXT NOT NULL)")
            # Additive migration for databases created before fix tracking.
            history_columns = {row[1] for row in cursor.execute("PRAGMA table_info(history)")}
            if "fixes_polish" not in history_columns:
                cursor.execute("ALTER TABLE history ADD COLUMN fixes_polish INTEGER NOT NULL DEFAULT 0")
            if "fixes_vocab" not in history_columns:
                cursor.execute("ALTER TABLE history ADD COLUMN fixes_vocab INTEGER NOT NULL DEFAULT 0")

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
        fixes_polish: int = 0,
        fixes_vocab: int = 0,
    ) -> str:
        """Record a completed dictation session and update derived analytics."""
        session_id = str(uuid.uuid4())
        now = datetime.datetime.now()
        word_count = len(final_text.split())

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history (id, timestamp, app_name, asr_text, final_text, duration_sec, word_count, latency_ms, mode, audio_path, fixes_polish, fixes_vocab)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, now.isoformat(), app_name, asr_text, final_text, duration_sec, word_count, latency_ms, mode, audio_path,
                 max(0, int(fixes_polish)), max(0, int(fixes_vocab))),
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

    def get_history(self, limit: int = 50, search: str = "", app: str = "", offset: int = 0) -> List[Dict[str, Any]]:
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

        query += " ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?"
        params.extend((limit,offset))

        with self._connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def register_session_artifact(self, path, root):
        import json
        from .artifacts import identity, session_files
        path=Path(path)
        audio=path if path.suffix=='.wav' else path.with_suffix('').with_suffix('.wav')
        if path not in session_files(audio,root):raise ValueError('Unknown recording artifact')
        with self._connect() as conn:
            conn.execute('INSERT OR REPLACE INTO session_artifacts VALUES (?,?,?)',(str(path.absolute()),str(Path(root).resolve()),json.dumps(identity(path))))

    def delete_history_item(self, session_id: str, cache_root=None, rebuild=True) -> None:
        import json
        from .artifacts import session_files, validate_legacy, identity, unlink_owned
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM history WHERE id=?',(session_id,)).fetchone()
            if row and row['audio_path']:
                audio=Path(row['audio_path']).absolute()
                shared=conn.execute('SELECT count(*) FROM history WHERE audio_path=? AND id!=?',(row['audio_path'],session_id)).fetchone()[0]
                if not shared:
                    records={r['path']:dict(r) for r in conn.execute('SELECT * FROM session_artifacts WHERE path IN (?,?)',(str(audio),str(audio.with_suffix('.transcript.json'))))}
                    roots={record['root'] for record in records.values()}
                    if len(roots)>1:raise ValueError('Recording ownership roots disagree; deletion stopped.')
                    root=next(iter(roots)) if roots else cache_root
                    if root is None:raise ValueError('Recording ownership needs verification; History was preserved.')
                    files=session_files(audio,root)
                    if any(f.exists() and str(f) not in records for f in files):
                        files=validate_legacy(audio,root,row['asr_text'])
                        for file in files:
                            if file.exists():records.setdefault(str(file),{'identity':json.dumps(identity(file))})
                    for file in files:
                        if str(file) in records:unlink_owned(file,json.loads(records[str(file)]['identity']))
                    conn.execute('DELETE FROM session_artifacts WHERE path IN (?,?)',(str(files[0]),str(files[1])))
            conn.execute("DELETE FROM history WHERE id = ?", (session_id,))
        if rebuild:self.rebuild_analytics()

    def clear_all_history(self, cache_root=None) -> None:
        with self._connect() as conn:
            ids=[row[0] for row in conn.execute('SELECT id FROM history')]
        failures=[]
        for session_id in ids:
            try:self.delete_history_item(session_id,cache_root,rebuild=False)
            except (OSError,ValueError) as error:failures.append(str(error))
        self.rebuild_analytics()
        if failures:raise ValueError(f'{len(failures)} sessions could not be fully deleted. Retry after resolving the file issue. '+failures[0])

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

    def increment_word_usage(self, phrase: str) -> None:
        now = datetime.datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE dictionary SET frequency = frequency + 1, last_used = ? WHERE phrase = ?",
                (now, phrase.strip()),
            )

    def get_dictionary(self, limit: Optional[int] = 100, offset: int = 0, search: str = "") -> List[Dict[str, Any]]:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM dictionary WHERE phrase LIKE ? ESCAPE '\\' OR replacement LIKE ? ESCAPE '\\' ORDER BY frequency DESC, last_used DESC, phrase" + (" LIMIT ? OFFSET ?" if limit is not None else ""),
                (f'%{escaped}%',f'%{escaped}%') + (() if limit is None else (limit,offset))
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

    # ------------------------------------------------------------------
    # Insights (streaks, today, weekly rhythm, learning fixes)
    # ------------------------------------------------------------------

    def _active_days(self, conn: sqlite3.Connection) -> List[datetime.date]:
        rows = conn.execute(
            "SELECT DISTINCT substr(timestamp, 1, 10) AS day FROM history ORDER BY day"
        ).fetchall()
        days = []
        for row in rows:
            try:
                days.append(datetime.date.fromisoformat(row["day"]))
            except (TypeError, ValueError):
                continue
        return days

    def get_streak(self) -> Dict[str, Any]:
        """Current and best consecutive-day dictation streaks."""
        with self._connect() as conn:
            days = self._active_days(conn)

        if not days:
            return {"current": 0, "best": 0, "last_date": None, "active_days": 0}

        best = current_run = 1
        for previous, day in zip(days, days[1:]):
            current_run = current_run + 1 if (day - previous).days == 1 else 1
            best = max(best, current_run)

        today = datetime.date.today()
        last = days[-1]
        current = 0
        if last in (today, today - datetime.timedelta(days=1)):
            current = 1
            for previous, day in zip(reversed(days[:-1]), reversed(days)):
                if (day - previous).days == 1:
                    current += 1
                else:
                    break
        return {
            "current": current,
            "best": best,
            "last_date": last.isoformat(),
            "active_days": len(days),
        }

    def get_today_stats(self) -> Dict[str, Any]:
        today = datetime.date.today().strftime("%Y-%m-%d")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT total_words, total_seconds, sessions_count, avg_wpm FROM analytics_daily WHERE date = ?",
                (today,),
            ).fetchone()
        if row is None:
            return {"date": today, "total_words": 0, "total_seconds": 0.0,
                    "sessions_count": 0, "avg_wpm": 0.0}
        return {"date": today, "total_words": row["total_words"], "total_seconds": row["total_seconds"],
                "sessions_count": row["sessions_count"], "avg_wpm": row["avg_wpm"]}

    def get_week_activity(self, days: int = 7) -> List[Dict[str, Any]]:
        """Per-day activity for the trailing window, oldest first, gaps filled."""
        today = datetime.date.today()
        start = today - datetime.timedelta(days=days - 1)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT date, total_words, sessions_count, avg_wpm FROM analytics_daily WHERE date >= ?",
                (start.isoformat(),),
            ).fetchall()
        by_date = {row["date"]: row for row in rows}
        week = []
        for offset in range(days):
            day = start + datetime.timedelta(days=offset)
            key = day.isoformat()
            row = by_date.get(key)
            week.append({
                "date": key,
                "label": day.strftime("%a")[0],
                "words": row["total_words"] if row else 0,
                "sessions": row["sessions_count"] if row else 0,
                "avg_wpm": row["avg_wpm"] if row else 0.0,
                "active": bool(row and row["sessions_count"] > 0),
                "is_today": day == today,
            })
        return week

    def get_fix_stats(self) -> Dict[str, Any]:
        """Learning totals: polish fixes, vocabulary fixes, and dictionary size."""
        with self._connect() as conn:
            history_row = conn.execute(
                "SELECT COALESCE(SUM(fixes_polish), 0) AS polish, COALESCE(SUM(fixes_vocab), 0) AS vocab FROM history"
            ).fetchone()
            dictionary_row = conn.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(frequency), 0) AS uses FROM dictionary"
            ).fetchone()
        return {
            "polish_fixes": history_row["polish"],
            "vocab_fixes": history_row["vocab"],
            "dictionary_total": dictionary_row["total"],
            "dictionary_uses": dictionary_row["uses"],
        }
