"""Real shared boundaries; OS-specific checks run on their own native runner."""
import ctypes
import json
import os
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fixoflow.instance import InstanceLock
from fixoflow.desktop_app import Bridge,DesktopHub
from fixoflow.config import FixoflowConfig
from fixoflow.input_listener import DesktopInput


def test_single_instance_ownership_and_reacquire(tmp_path):
    path=tmp_path/'app.lock';first=InstanceLock(path);second=InstanceLock(path)
    try:
        assert first.acquire()
        assert not second.acquire()
        first.close()
        assert second.acquire()
    finally:first.close();second.close()


def test_native_bridge_serializes_actions_and_rejects_non_messages():
    active=[];seen=[]
    def callback(action,payload):
        assert not active
        active.append(action);time.sleep(0.01);seen.append(payload['number']);active.clear()
    bridge=Bridge(callback)
    assert not bridge.post(None) and not bridge.post({'action':12})
    threads=[threading.Thread(target=bridge.post,args=({'action':'test','number':n},)) for n in range(3)]
    for worker in threads:worker.start()
    for worker in threads:worker.join()
    assert sorted(seen)==[0,1,2]


def test_input_generation_quarantines_stale_callbacks():
    controls=SimpleNamespace(hold_press=Mock(),hold_release=Mock(),toggle=Mock())
    inputs=DesktopInput(FixoflowConfig(),controls)
    generation=inputs._generation
    inputs.stop()
    assert not inputs._feed(('keyboard',1),'ctrl_l',True,generation)
    assert not inputs.router.pressed
    inputs._feed(('keyboard',1),'ctrl_l',True,inputs._generation)
    inputs._feed(('keyboard',2),'space',True,inputs._generation)
    controls.hold_press.assert_called_once()
    inputs.stop()
    controls.hold_release.assert_called_once()


def test_cleanup_retains_live_listener_until_retry():
    inputs=DesktopInput(FixoflowConfig(),SimpleNamespace(hold_release=Mock()))
    listener=Mock();listener.ident=None;listener.is_alive.side_effect=[True,False]
    inputs._listeners=[listener];inputs.stop()
    assert inputs._retired==[listener]
    inputs.stop();assert not inputs._retired
    assert listener.stop.call_count==2


def test_primary_capture_validation():
    inputs=DesktopInput(FixoflowConfig(),SimpleNamespace(hold_release=Mock()))
    for invalid in (True,-1,2,'0',None):
        with pytest.raises(ValueError):inputs.capture_primary(invalid)


@pytest.mark.skipif(sys.platform!='win32',reason='Real Windows ABI only')
def test_windows_input_abi_and_native_identity():
    from fixoflow.platform import windows
    assert ctypes.sizeof(windows.INPUT)==40
    # Real Win32 query, no synthetic input or clipboard mutation.
    hwnd=windows.u.GetForegroundWindow()
    if hwnd:
        identity=windows._identity(hwnd)
        if identity:assert identity[0]==hwnd and identity[1]>0 and identity[2]>0


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Real Linux /proc identity')
def test_linux_window_identity_includes_process_birth():
    from fixoflow.platform import linux
    display=SimpleNamespace(intern_atom=lambda name:1)
    window=SimpleNamespace(id=42,get_full_property=lambda *args:SimpleNamespace(value=[os.getpid()]))
    identity=linux._identity(display,window)
    assert identity[:2]==[42,os.getpid()] and int(identity[2])>0


def test_capture_callback_does_not_wait_for_native_ui():
    import queue
    from fixoflow.desktop_app import DesktopApplication
    application=DesktopApplication.__new__(DesktopApplication)
    application.controls=SimpleNamespace(state='IDLE')
    application.inputs=Mock();application.hub=Mock();application._captures=queue.SimpleQueue()
    application.enable_shortcut=lambda:None
    application.capture('hold_shortcut')
    callback=application.inputs.begin_capture.call_args.args[0]
    callback({'keys':['space']},'selected')
    application.hub._eval_js.assert_not_called()
    assert application._captures.get_nowait()['field']=='hold_shortcut'


def test_hub_and_pill_bridges_share_one_mutation_owner():
    lock=threading.RLock();active=[];seen=[]
    def callback(action,payload):
        assert not active
        active.append(action);time.sleep(.01);seen.append(action);active.clear()
    hub=Bridge(callback,lock);pill=Bridge(callback,lock)
    workers=[threading.Thread(target=bridge.post,args=({'action':name},)) for bridge,name in ((hub,'settings'),(pill,'position'))]
    for worker in workers:worker.start()
    for worker in workers:worker.join()
    assert sorted(seen)==['position','settings']


def test_unrelated_preferences_keep_desktop_input_running():
    from dataclasses import replace
    from fixoflow.desktop_app import DesktopApplication
    application=DesktopApplication.__new__(DesktopApplication)
    application.config=FixoflowConfig()
    application.controls=Mock(state='IDLE')
    application.controls.configure.side_effect=lambda update:update()
    application.inputs=Mock();application.inputs.router.quarantined=False
    application.startup=Mock();application.startup.commit.side_effect=lambda config,candidate,apply,**kw:apply()
    application.coordinator=Mock();application.hub=Mock();application.pill=Mock()
    application.position_pill=Mock();application.enable_shortcut=Mock()
    application.apply_config(replace(application.config,sound_enabled=False))
    application.inputs.stop.assert_not_called();application.inputs.reconfigure.assert_not_called()
    application.enable_shortcut.assert_not_called()
    application.coordinator.apply_config.assert_called_once()


def test_content_loading_does_not_hold_bridge_mutation_lock():
    from fixoflow.desktop_app import DesktopApplication
    application=DesktopApplication.__new__(DesktopApplication)
    application._self_check=True;application._actions=threading.RLock()
    observed=[]
    def content():
        completed=threading.Event()
        def bridge_callback():
            with application._actions:completed.set()
        worker=threading.Thread(target=bridge_callback)
        worker.start()
        observed.append(completed.wait(.5))
        worker.join(timeout=.5)
    application._load_content=content
    application.loaded()
    assert observed==[True]
