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
