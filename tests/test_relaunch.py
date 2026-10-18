import sys

from fixoflow import app as app_module


def test_source_relaunch_uses_interpreter_module_invocation():
    command = app_module.relaunch_command()
    assert command[:2] == ['/bin/sh', '-c']
    assert sys.executable in command[2]
    assert '-m fixoflow.app' in command[2]
    assert 'sleep' in command[2]


def test_bundle_relaunch_opens_a_fresh_instance_of_the_bundle():
    command = app_module.relaunch_command(bundle_path='/Applications/Fixoflow.app')
    assert command[:2] == ['/bin/sh', '-c']
    assert '/usr/bin/open -n' in command[2]
    assert "/Applications/Fixoflow.app" in command[2]


def test_bundle_path_is_shell_quoted():
    command = app_module.relaunch_command(bundle_path="/Applications/My App.app")
    assert "'/Applications/My App.app'" in command[2]


def test_dock_termination_drains_owned_dictation_before_exit():
    from types import SimpleNamespace
    from unittest.mock import Mock
    delegate = app_module.MenuDelegate.alloc().init()
    stop = Mock()
    delegate.app_instance = SimpleNamespace(stop=stop)
    assert delegate.applicationShouldTerminate_(None) == app_module.AppKit.NSTerminateNow
    stop.assert_called_once()
    assert delegate.applicationShouldTerminateAfterLastWindowClosed_(None) is False


def test_rejected_shutdown_does_not_spawn_replacement(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    instance=SimpleNamespace(stop=Mock(return_value=False))
    spawn=Mock();exit_process=Mock()
    monkeypatch.setattr(app_module.subprocess,'Popen',spawn)
    monkeypatch.setattr(app_module.os,'_exit',exit_process)
    app_module.FixoflowApp.restart(instance)
    spawn.assert_not_called();exit_process.assert_not_called()


def test_restart_spawn_failure_preserves_completed_shutdown_and_reports(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    instance=SimpleNamespace(stop=Mock(return_value=True))
    notice=Mock();exit_process=Mock()
    monkeypatch.setattr(app_module.subprocess,'Popen',Mock(side_effect=OSError('launch failed')))
    monkeypatch.setattr(app_module.os,'_exit',exit_process)
    monkeypatch.setattr(app_module,'notify',notice)
    app_module.FixoflowApp.restart(instance)
    instance.stop.assert_called_once();notice.assert_called_once();exit_process.assert_not_called()
