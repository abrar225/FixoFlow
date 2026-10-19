"""Login lifecycle using isolated entries; never register the developer machine."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import sys
import pytest
from fixoflow.config import FixoflowConfig
from fixoflow.startup import StartupService, LinuxLogin, WindowsLogin, desktop_exec, launched_at_login


def config(tmp_path, monkeypatch, **kwargs):
    monkeypatch.setattr(FixoflowConfig, 'get_config_path', classmethod(lambda cls:tmp_path/'config.json'))
    return FixoflowConfig(cache_dir=str(tmp_path/'audio'), **kwargs)


def test_default_first_login_setup_and_external_disable_are_not_repeated(tmp_path, monkeypatch):
    cfg=config(tmp_path,monkeypatch)
    backend=Mock();backend.status.return_value=(False,False)
    service=StartupService(backend)
    assert cfg.start_at_login
    service.initialize(cfg)
    assert cfg.login_setup_done and FixoflowConfig.load().start_at_login
    backend.set.assert_called_once_with(True)
    service.initialize(cfg)  # OS removal after setup stays removed.
    backend.set.assert_called_once()


def test_opt_out_survives_config_reload_without_registering(tmp_path, monkeypatch):
    cfg=config(tmp_path,monkeypatch,start_at_login=False)
    backend=Mock();service=StartupService(backend)
    service.initialize(cfg)
    backend.set.assert_not_called()
    assert not FixoflowConfig.load().start_at_login


def test_startup_failure_and_compensation_preserve_saved_preferences(tmp_path,monkeypatch):
    cfg=config(tmp_path,monkeypatch,start_at_login=False);cfg.save()
    backend=Mock();backend.status.return_value=(False,False)
    service=StartupService(backend)
    candidate=replace(cfg,start_at_login=True)
    with pytest.raises(OSError,match='disk full'):
        service.commit(cfg,candidate,lambda:(_ for _ in ()).throw(OSError('disk full')))
    assert [call.args for call in backend.set.call_args_list]==[(True,),(False,)]
    assert not FixoflowConfig.load().start_at_login
    backend.set.side_effect=PermissionError('denied')
    apply=Mock()
    with pytest.raises(PermissionError):service.commit(cfg,candidate,apply)
    apply.assert_not_called()


def test_unrelated_save_does_not_reenable_removed_login_item(tmp_path,monkeypatch):
    cfg=config(tmp_path,monkeypatch,login_setup_done=True)
    backend=Mock();backend.status.return_value=(False,False)
    service=StartupService(backend);apply=Mock()
    service.commit(cfg,replace(cfg,sound_enabled=False),apply)
    backend.set.assert_not_called();apply.assert_called_once()
    # Explicitly turning it back on is a fresh user request, even if old JSON is true.
    service.commit(cfg,replace(cfg),apply,explicit=True)
    backend.set.assert_called_once_with(True)


def test_source_run_has_no_registration(tmp_path,monkeypatch):
    monkeypatch.setattr(sys,'frozen',False,raising=False)
    service=StartupService();cfg=config(tmp_path,monkeypatch)
    service.initialize(cfg)
    assert not service.snapshot()['supported'] and not cfg.login_setup_done


@pytest.mark.skipif(sys.platform=='win32',reason='POSIX desktop entry')
def test_linux_real_entry_enable_disable_and_desktop_override(tmp_path):
    backend=LinuxLogin('/opt/fixoflow/Fixoflow',tmp_path)
    assert backend.status()==(False,False)
    backend.set(True);backend.set(True)
    assert backend.status()==(True,False)
    assert 'TryExec=/opt/fixoflow/Fixoflow' in backend.path.read_text()
    backend.path.write_text(backend.path.read_text().replace('Hidden=false','Hidden=true'))
    assert backend.status()==(False,False)
    backend.set(False)
    assert backend.path.exists() and backend.status()==(False,False)


@pytest.mark.skipif(sys.platform=='win32',reason='POSIX desktop entry')
def test_linux_preserves_foreign_and_symlink_entries(tmp_path):
    backend=LinuxLogin('/opt/fixoflow/Fixoflow',tmp_path)
    backend.path.parent.mkdir(parents=True)
    foreign='[Desktop Entry]\nType=Application\nExec=other\n'
    backend.path.write_text(foreign)
    for value in (True,False):
        with pytest.raises(RuntimeError,match='preserved'):backend.set(value)
        assert backend.path.read_text()==foreign
    backend.path.unlink();target=tmp_path/'target';target.write_text('untouched');backend.path.symlink_to(target)
    with pytest.raises(RuntimeError,match='symbolic'):backend.set(True)
    assert target.read_text()=='untouched'


def test_desktop_exec_uses_desktop_escaping_and_rejects_newlines():
    assert desktop_exec('/opt/a b/50%$"x')=='"/opt/a b/50%%\\\\$\\\\"x" --background'
    with pytest.raises(ValueError):desktop_exec('/bad\npath')


def test_apple_login_event_and_manual_open():
    code=lambda value:int.from_bytes(value.encode(),'big')
    event=Mock();event.eventID.return_value=code('oapp')
    event.paramDescriptorForKeyword_.side_effect=lambda key:SimpleNamespace(enumCodeValue=lambda:code('lgit')) if key==code('prdt') else None
    assert launched_at_login(event)
    event.paramDescriptorForKeyword_.side_effect=lambda key:None
    event.attributeDescriptorForKeyword_.return_value=None
    assert not launched_at_login(event)
    event.eventID.return_value=code('odoc')
    assert not launched_at_login(event)


@pytest.mark.skipif(sys.platform!='win32',reason='Real Windows registry only')
def test_windows_registration_in_isolated_registry_key(tmp_path):
    import winreg, uuid
    backend=WindowsLogin(Path(sys.executable))
    backend.key=rf'Software\FixoFlowTest\{uuid.uuid4()}'
    try:
        assert backend.status()==(False,False)
        backend.set(True);assert backend.status()==(True,False)
        backend.set(False);assert backend.status()==(False,False)
    finally:
        try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,backend.key)
        except FileNotFoundError:pass


@pytest.mark.skipif(sys.platform=='win32',reason='POSIX entry ownership')
def test_linux_concurrent_publication_never_overwrites_foreign_entry(tmp_path,monkeypatch):
    import os
    backend=LinuxLogin('/opt/fixoflow/Fixoflow',tmp_path)
    link=os.link
    def replaced(source,destination):
        backend.path.write_text('foreign entry')
        return link(source,destination)
    monkeypatch.setattr(os,'link',replaced)
    with pytest.raises(FileExistsError):backend.set(True)
    assert backend.path.read_text()=='foreign entry'


@pytest.mark.skipif(sys.platform=='win32',reason='POSIX entry ownership')
def test_linux_open_inode_cannot_write_a_replacement_path(tmp_path,monkeypatch):
    import os
    backend=LinuxLogin('/opt/fixoflow/Fixoflow',tmp_path);backend.set(True)
    original_open=os.open
    def replace_after_open(path,flags,*args,**kwargs):
        descriptor=original_open(path,flags,*args,**kwargs)
        if Path(path)==backend.path:
            backend.path.unlink();backend.path.write_text('foreign replacement')
        return descriptor
    monkeypatch.setattr(os,'open',replace_after_open)
    with pytest.raises(RuntimeError,match='preserved'):backend.set(False)
    assert backend.path.read_text()=='foreign replacement'


@pytest.mark.skipif(sys.platform=='win32',reason='POSIX lock')
def test_linux_external_lock_fails_promptly_instead_of_hanging(tmp_path):
    import fcntl
    backend=LinuxLogin('/opt/fixoflow/Fixoflow',tmp_path);backend.set(True)
    before=backend.path.read_text()
    with backend.path.open('r+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(RuntimeError,match='busy'):backend.set(False)
    assert backend.path.read_text()==before
