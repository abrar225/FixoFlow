import sqlite3
import pytest
from fixoflow.app_identity import app_scope, executable_scope
from fixoflow.storage.db import FixoflowDB


@pytest.mark.parametrize('system,path,new_path',[
    ('windows',r'C:\Apps\Editor.exe',r'c:\apps\EDITOR.exe'),
    ('linux','/usr/bin/editor','/usr/bin/editor'),
])
def test_memory_survives_target_restart_and_multiple_windows(tmp_path,system,path,new_path):
    db=FixoflowDB(tmp_path/'test.sqlite')
    old_target='[101, 10, 100]';new_target='[202, 20, 200]'
    app_id=executable_scope(path,system)
    sid=db.begin_session('Editor',old_target,'model','en','writing',app_id=app_id)
    db.record_session('Y did it fail?','Y did it fail?','Editor',1,1,mode='writing',session_id=sid)
    cid=db.propose_correction(sid,'Why did it fail?');db.approve_correction(cid)
    new_sid=db.begin_session('Editor',new_target,'model','en','writing',app_id=executable_scope(new_path,system))
    assert db.get_session(new_sid)['app_identity']==new_target
    assert db.get_session(new_sid)['app_id']==app_id
    assert db.apply_approved_correction('Y did it fail?',executable_scope(new_path,system),'en','writing')==('Why did it fail?',cid)
    assert db.apply_approved_correction('Y did it fail?',executable_scope(path+'2',system),'en','writing')[1] is None


def test_legacy_window_targets_are_not_guessed_as_app_scope():
    assert app_scope('[101,10,100]')==''
    assert app_scope('Editor')==''
    assert app_scope('com.example.Editor')=='macos:bundle:com.example.Editor'


def test_additive_scope_migration_preserves_old_records_without_global_rules(tmp_path):
    path=tmp_path/'old.sqlite'
    with sqlite3.connect(path) as c:
        c.execute('''CREATE TABLE sessions(id TEXT PRIMARY KEY,started_at TEXT,updated_at TEXT,
            app_name TEXT,app_identity TEXT,model_name TEXT,language TEXT,mode TEXT,status TEXT,
            audio_path TEXT,delivery_status TEXT)''')
        c.execute('''CREATE TABLE correction_memory(id TEXT PRIMARY KEY,session_id TEXT,
            original_text TEXT,corrected_text TEXT,app_identity TEXT,language TEXT,mode TEXT,
            state TEXT,created_at TEXT,UNIQUE(session_id,original_text,corrected_text))''')
        for sid,identity in [('mac','com.example.Editor'),('win','[101,10,100]')]:
            c.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)',(sid,'now','now','Editor',identity,'m','en','writing','completed','','not_attempted'))
            c.execute('INSERT INTO correction_memory VALUES (?,?,?,?,?,?,?,?,?)',(sid,sid,'Y','why',identity,'en','writing','approved','now'))
    db=FixoflowDB(path)
    assert db.get_session('mac')['app_id']=='macos:bundle:com.example.Editor'
    assert db.get_session('win')['app_id']==''
    assert db.apply_approved_correction('Y','[101,10,100]','en','writing')==('Y',None)
    assert db.apply_approved_correction('Y','macos:bundle:com.example.Editor','en','writing')==('why','mac')
    assert len(db.get_corrections())==2
