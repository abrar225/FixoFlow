"""Additive session journal. States describe dispatch, never verified insertion."""
import datetime
import uuid


class SessionStore:
    def init_session_tables(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, started_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                app_name TEXT NOT NULL, app_identity TEXT NOT NULL,
                model_name TEXT NOT NULL, language TEXT NOT NULL, mode TEXT NOT NULL,
                status TEXT NOT NULL, audio_path TEXT NOT NULL DEFAULT '',
                delivery_status TEXT NOT NULL DEFAULT 'not_attempted')''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC)')
            columns = {row[1] for row in conn.execute('PRAGMA table_info(sessions)')}
            if 'app_id' not in columns:
                from fixoflow.app_identity import app_scope
                conn.execute("ALTER TABLE sessions ADD COLUMN app_id TEXT NOT NULL DEFAULT ''")
                for row in conn.execute('SELECT id,app_identity FROM sessions').fetchall():
                    conn.execute('UPDATE sessions SET app_id=? WHERE id=?', (app_scope(row['app_identity']),row['id']))
            if 'owner_pid' not in columns:
                conn.execute('ALTER TABLE sessions ADD COLUMN owner_pid INTEGER NOT NULL DEFAULT 0')

    def begin_session(self, app_name, app_identity, model_name, language, mode, app_id=None):
        import os
        from fixoflow.app_identity import app_scope
        app_id = app_scope(app_identity if app_id is None else app_id)
        sid = str(uuid.uuid4())
        now = datetime.datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute('''INSERT INTO sessions
                (id,started_at,updated_at,app_name,app_identity,model_name,language,mode,status,app_id,owner_pid)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (sid, now, now, app_name, app_identity, model_name, language or 'auto', mode, 'starting',app_id,os.getpid()))
        return sid

    def update_session(self, sid, *, status=None, audio_path=None, delivery_status=None):
        statuses = {'starting', 'recording', 'processing', 'completed', 'cancelled',
                    'capture_failed', 'transcription_failed', 'history_failed', 'no_audio', 'no_speech', 'recovered'}
        deliveries = {'not_attempted', 'cancelled', 'dispatch_sent', 'clipboard_only', 'failed'}
        if status is not None and status not in statuses:
            raise ValueError('Unknown session status')
        if delivery_status is not None and delivery_status not in deliveries:
            raise ValueError('Unknown delivery status')
        fields = {'updated_at': datetime.datetime.now().isoformat()}
        fields.update({k: v for k, v in dict(status=status, audio_path=audio_path,
                      delivery_status=delivery_status).items() if v is not None})
        with self._connect() as conn:
            conn.execute('UPDATE sessions SET ' + ','.join(k+'=?' for k in fields) + ' WHERE id=?',
                         (*fields.values(), sid))

    def get_session(self, sid):
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
        return dict(row) if row else None

    def get_session_journal(self, limit=50):
        """No startup mutation: another CLI instance may own an active recording."""
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?', (limit,))]

    def get_recovery_items(self, limit=50):
        with self._connect() as conn:
            return [dict(row) for row in conn.execute('''SELECT * FROM sessions WHERE audio_path!=''
                AND (status!='completed' OR delivery_status IN ('clipboard_only','failed','cancelled'))
                ORDER BY started_at DESC LIMIT ?''',(limit,))]

    def recovery_source(self, sid):
        from fixoflow.app_identity import process_alive
        row=self.get_session(sid)
        if not row or not row['audio_path']:raise ValueError('Recovery recording not found.')
        if row['status'] in {'starting','recording','processing'}:
            if row['owner_pid']<=0:
                raise ValueError('This legacy recording has no verifiable owner. Use Show recording folder to inspect or copy it manually; automatic retry/delete is unavailable.')
            # A live process or unknown legacy owner must not have its WAV copied
            # while headers/samples may still be changing. PID reuse blocks safely.
            alive = process_alive(row['owner_pid'])
            if alive:raise ValueError('This recording may still be active. Close the owning app before recovery.')
        return row

    def open_owned_audio(self, audio_path):
        import json
        import os
        import stat
        from pathlib import Path
        from fixoflow.storage.artifacts import session_files
        with self._connect() as conn:
            row=conn.execute('SELECT * FROM session_artifacts WHERE path=?',(str(Path(audio_path).absolute()),)).fetchone()
        if not row:raise ValueError('Recording ownership is unknown; recovery stopped.')
        session_files(audio_path,row['root'])
        fd=os.open(audio_path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        source=os.fdopen(fd,'rb')
        info=os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or [info.st_dev,info.st_ino]!=json.loads(row['identity']):
            source.close();raise ValueError('Recording was replaced; recovery stopped.')
        return source

    def delete_recovery_item(self, sid):
        self.recovery_source(sid)
        self.delete_history_item(sid)

    def reveal_recovery_audio(self, sid):
        """Explicit user action; reveals only an owned recording, never a UI path."""
        import os
        import sys
        import subprocess
        from pathlib import Path
        row=self.get_session(sid)
        if not row:raise ValueError('Recovery recording not found.')
        with self.open_owned_audio(row['audio_path']):pass
        path=Path(row['audio_path']).absolute()
        if sys.platform=='darwin':subprocess.Popen(['/usr/bin/open','-R',str(path)])
        elif sys.platform=='win32':os.startfile(str(path.parent))
        else:subprocess.Popen(['xdg-open',str(path.parent)])

    def read_history_audio(self, sid, max_bytes=20_000_000):
        """Read registered PCM audio with matching file identity; UI supplies no paths.

        Bounded bridge playback for new owned recordings. Older/unregistered
        recordings require a future explicit import rather than guessed ownership.
        """
        import io
        import json
        import os
        import stat
        import wave
        from pathlib import Path
        from fixoflow.storage.artifacts import session_files
        with self._connect() as conn:
            row = conn.execute('''SELECT h.audio_path,a.root,a.identity FROM history h
                JOIN session_artifacts a ON a.path=h.audio_path WHERE h.id=?''', (sid,)).fetchone()
        if not row:
            raise ValueError('This recording is missing or has no verified ownership record.')
        path = Path(row['audio_path'])
        session_files(path, row['root'])
        fd = os.open(path, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as audio:
            info = os.fstat(audio.fileno())
            if not stat.S_ISREG(info.st_mode) or [info.st_dev,info.st_ino] != json.loads(row['identity']):
                raise ValueError('Recording was replaced; playback stopped.')
            if info.st_size > max_bytes:
                raise ValueError('Recording exceeds the 20 MB in-app playback limit.')
            data = audio.read(max_bytes+1)
        if len(data) > max_bytes:
            raise ValueError('Recording exceeds the in-app playback limit.')
        try:
            with wave.open(io.BytesIO(data)) as capture:
                if (capture.getnchannels(),capture.getsampwidth(),capture.getframerate()) != (1,2,16000):
                    raise ValueError('Recording is not supported PCM audio.')
                if len(capture.readframes(capture.getnframes())) != capture.getnframes()*2:
                    raise ValueError('Recording is truncated.')
        except (wave.Error, EOFError) as error:
            raise ValueError('Recording is not valid WAV audio.') from error
        return data
