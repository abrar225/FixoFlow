"""Native event objects are inspected, never posted to another application."""
from types import SimpleNamespace
import threading
from unittest.mock import Mock
import Quartz
from pynput import keyboard
from fixoflow.config import FixoflowConfig
from fixoflow.daemon import FixoflowDaemon
from fixoflow.shortcuts import Shortcut, ShortcutRouter


def adapter(hold='<fn>',hands_free='<mouse:4>'):
    daemon=FixoflowDaemon.__new__(FixoflowDaemon)
    daemon._lock=threading.RLock();daemon._generation=1;daemon._keyboard_consumed=False;daemon._hub_focused=False
    controls=SimpleNamespace(state='IDLE',hold_press=Mock(),hold_release=Mock(),toggle=Mock(),cancel=Mock())
    daemon.router=ShortcutRouter(Shortcut.from_text(hold).as_dict(),Shortcut.from_text(hands_free).as_dict(),controls)
    return daemon,controls


def test_real_fn_flag_events_have_balanced_edges():
    d,c=adapter()
    event=Quartz.CGEventCreateKeyboardEvent(None,63,True)
    Quartz.CGEventSetType(event,Quartz.kCGEventFlagsChanged)
    Quartz.CGEventSetFlags(event,Quartz.kCGEventFlagMaskSecondaryFn)
    assert d._keyboard_event(Quartz.kCGEventFlagsChanged,event,1) is None
    Quartz.CGEventSetFlags(event,0)
    assert d._keyboard_event(Quartz.kCGEventFlagsChanged,event,1) is None
    c.hold_press.assert_called_once();c.hold_release.assert_called_once()


def test_raw_aux_mouse_number_is_not_collapsed_to_middle_click():
    d,c=adapter()
    event=Quartz.CGEventCreateMouseEvent(None,Quartz.kCGEventOtherMouseDown,(0,0),4)
    assert d._mouse_event(Quartz.kCGEventOtherMouseDown,event,1) is None
    assert d._mouse_event(Quartz.kCGEventOtherMouseDown,event,1) is None
    d._mouse_event(Quartz.kCGEventOtherMouseUp,event,1)
    c.toggle.assert_called_once()


def test_stale_listener_callbacks_cannot_control_a_new_session():
    d,c=adapter('a')
    d._feed_key(keyboard.KeyCode.from_vk(0,char='a'),True,0)
    assert not d.router.pressed;c.hold_press.assert_not_called()


def test_primary_clicks_inside_hub_do_not_activate_dictation():
    d,c=adapter('<mouse:0>');d._hub_focused=True
    event=Quartz.CGEventCreateMouseEvent(None,Quartz.kCGEventLeftMouseDown,(0,0),0)
    assert d._mouse_event(Quartz.kCGEventLeftMouseDown,event,1) is event
    c.hold_press.assert_not_called()


def test_physical_modifiers_keep_left_and_right_identity():
    assert FixoflowDaemon._key_token(keyboard.Key.ctrl)=='ctrl_l'
    assert FixoflowDaemon._key_token(keyboard.Key.ctrl_r)=='ctrl_r'
    assert FixoflowDaemon._physical_key(keyboard.Key.ctrl)!=FixoflowDaemon._physical_key(keyboard.Key.ctrl_r)


def test_pending_listener_cleanup_retains_ownership_for_retry():
    d,_=adapter();listener=Mock();listener.ident=1;listener.is_alive.side_effect=[True,False]
    d._listener=listener;d._mouse_listener=None;d._retired_listeners=[]
    d.stop_listener();assert d._retired_listeners==[listener]
    d.stop_listener();assert d._retired_listeners==[]
