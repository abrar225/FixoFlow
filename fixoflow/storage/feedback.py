"""Explicit correction memory: pending until approved, scoped exact utterances.

This is not acoustic training or observation of other applications. User edits
are never promoted to a global word replacement or to recognizer training data.
"""
import datetime
import uuid


class FeedbackStore:
    def init_feedback_tables(self):
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS correction_memory (
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
                original_text TEXT NOT NULL, corrected_text TEXT NOT NULL,
                app_identity TEXT NOT NULL, language TEXT NOT NULL, mode TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('proposed','approved')),
                created_at TEXT NOT NULL,
                UNIQUE(session_id, original_text, corrected_text))''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_correction_scope ON correction_memory(app_identity,language,mode,state)')
            columns = {row[1] for row in conn.execute('PRAGMA table_info(correction_memory)')}
            if 'app_id' not in columns:
                conn.execute("ALTER TABLE correction_memory ADD COLUMN app_id TEXT NOT NULL DEFAULT ''")
                conn.execute("""UPDATE correction_memory SET app_id=COALESCE(
                    (SELECT app_id FROM sessions WHERE sessions.id=correction_memory.session_id),'')""")
            conn.execute('CREATE INDEX IF NOT EXISTS idx_correction_app_id ON correction_memory(app_id,language,mode,state)')

    def propose_correction(self, session_id, corrected_text):
        if not isinstance(corrected_text, str) or not corrected_text.strip() or len(corrected_text) > 20000:
            raise ValueError('Enter a correction between 1 and 20,000 characters.')
        corrected_text = corrected_text.strip()
        with self._connect() as conn:
            row = conn.execute('''SELECT h.final_text,s.app_identity,s.app_id,s.language,s.mode
                FROM history h JOIN sessions s ON s.id=h.id WHERE h.id=?''', (session_id,)).fetchone()
            if not row:
                raise ValueError('This transcript has no session context. Corrections are available for new recordings.')
            if not row['app_id']:
                raise ValueError('The original app was not identified; a scoped correction cannot be saved.')
            if row['mode'] == 'raw':
                raise ValueError('Raw mode does not use learned corrections.')
            if corrected_text == row['final_text'].strip():
                raise ValueError('Change the transcript before proposing a correction.')
            cid = str(uuid.uuid4())
            conn.execute('''INSERT OR IGNORE INTO correction_memory
                (id,session_id,original_text,corrected_text,app_identity,language,mode,state,created_at,app_id)
                VALUES (?,?,?,?,?,?,?,'proposed',?,?)''',
                (cid, session_id, row['final_text'], corrected_text, row['app_identity'],
                 row['language'], row['mode'], datetime.datetime.now().isoformat(),row['app_id']))
            return conn.execute('''SELECT id FROM correction_memory WHERE session_id=?
                AND original_text=? AND corrected_text=?''', (session_id, row['final_text'], corrected_text)).fetchone()[0]

    def get_corrections(self, limit=100):
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                'SELECT * FROM correction_memory ORDER BY created_at DESC LIMIT ?', (limit,))]

    def approve_correction(self, correction_id):
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM correction_memory WHERE id=?', (correction_id,)).fetchone()
            if not row:
                raise ValueError('Correction no longer exists.')
            if not row['app_id']:
                raise ValueError('This older correction has no persistent app scope. Recreate it from a new recording.')
            # Conflicting targets are not silently ranked by frequency/recency.
            conflict = conn.execute('''SELECT id FROM correction_memory WHERE state='approved'
                AND app_id=? AND language=? AND mode=? AND original_text=?
                AND corrected_text!=?''', (row['app_id'], row['language'], row['mode'],
                    row['original_text'], row['corrected_text'])).fetchone()
            if conflict:
                raise ValueError('Forget the conflicting approved correction before approving this one.')
            conn.execute("UPDATE correction_memory SET state='approved' WHERE id=?", (correction_id,))

    def forget_correction(self, correction_id):
        with self._connect() as conn:
            conn.execute('DELETE FROM correction_memory WHERE id=?', (correction_id,))

    def undo_correction_approval(self, correction_id):
        """Disable future reuse. Never rewrite already delivered text/history."""
        with self._connect() as conn:
            conn.execute("UPDATE correction_memory SET state='proposed' WHERE id=?", (correction_id,))

    def contextual_suggestions(self, session_id):
        """Bounded, explainable proposals from approved edits. Never auto-apply.

        One small replacement must match its original neighbouring words. This
        is conservative context matching, not semantic reasoning or ASR training.
        """
        import difflib
        import re
        with self._connect() as conn:
            target = conn.execute('''SELECT h.final_text,s.app_id,s.language,s.mode
                FROM history h JOIN sessions s ON h.id=s.id WHERE h.id=?''', (session_id,)).fetchone()
            if not target or not target['app_id'] or target['mode']=='raw':
                return []
            rules=conn.execute('''SELECT * FROM correction_memory WHERE app_id=? AND language=?
                AND mode=? AND state='approved' ORDER BY created_at DESC LIMIT 100''',
                (target['app_id'],target['language'],target['mode'])).fetchall()
        text=target['final_text']; spans=list(re.finditer(r'\S+',text))
        words=[m[0] for m in spans]
        if len(words)>256 or any(c in text for c in ('`','"','“','”')):return []
        results=[];seen=set()
        for rule in rules:
            if rule['original_text'].rstrip().endswith('?') and not text.rstrip().endswith('?'):continue
            before=rule['original_text'].split();after=rule['corrected_text'].split()
            if max(len(before),len(after))>256:continue
            edits=[op for op in difflib.SequenceMatcher(None,before,after,autojunk=False).get_opcodes() if op[0]!='equal']
            if len(edits)!=1:continue
            kind,i,j,a,b=edits[0]
            if kind!='replace' or max(j-i,b-a)>5:continue
            start=max(0,i-2);end=min(len(before),j+2)
            # Context on at least one side, and at least two unchanged tokens,
            # is required. No naked global Y/ball replacement proposals.
            if (i-start)+(end-j)<2:continue
            pattern=before[start:end]
            for index in range(len(words)-len(pattern)+1):
                if words[index:index+len(pattern)]!=pattern:continue
                left=index+i-start;right=left+j-i
                candidate=text[:spans[left].start()]+' '.join(after[a:b])+text[spans[right-1].end():]
                if candidate==text or candidate in seen:continue
                seen.add(candidate)
                results.append({'source_correction_id':rule['id'],'text':candidate,
                    'explanation':'Matches an approved edit and neighbouring words in this app, language and mode. Review before use.'})
                if len(results)>=5:return results
        return results

    def apply_approved_correction(self, text, app_identity, language, mode):
        from fixoflow.app_identity import app_scope
        app_identity = app_scope(app_identity)
        if mode == 'raw' or not app_identity:
            return text, None
        with self._connect() as conn:
            rows = conn.execute('''SELECT id,corrected_text FROM correction_memory
                WHERE state='approved' AND original_text=? AND app_id=? AND language=? AND mode=?''',
                (text, app_identity, language or 'auto', mode)).fetchall()
        targets = {row['corrected_text'] for row in rows}
        if len(targets) != 1:
            return text, None
        # Single original-input lookup: generated corrections cannot cascade.
        return rows[0]['corrected_text'], rows[0]['id']
