"""Linux X11 integration; Wayland is explicitly clipboard-only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from .contracts import InsertionOutcome


def _display():
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        raise RuntimeError('Global shortcuts and automatic insertion require an X11 session.')
    from Xlib.display import Display
    return Display()


def _identity(display,window):
    prop=window.get_full_property(display.intern_atom('_NET_WM_PID'),0)
    if prop is None or not len(prop.value):
        return None
    pid=int(prop.value[0])
    # /proc start time prevents a reused window/PID from inheriting a transcript.
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return [window.id,pid,fields[19]]


def get_frontmost_app_info():
    display=None
    try:
        display = _display()
        root = display.screen().root
        prop=root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'),0)
        if prop is None or not len(prop.value) or not prop.value[0]:
            return 'Unknown', ''
        window = display.create_resource_object('window', int(prop.value[0]))
        identity = _identity(display, window)
        name=window.get_wm_class() or (window.get_wm_name() or 'Application',)
        return str(name[-1]),json.dumps(identity) if identity else ''
    except Exception:
        return 'Unknown', ''
    finally:
        if display:
            display.close()


def activate_application(identity,timeout_sec=0.8):
    display=None
    try:
        from Xlib import X,protocol
        xid, pid, born = json.loads(identity)
        display = _display()
        window = display.create_resource_object('window', xid)
        if _identity(display, window) != [xid, pid, born]:
            return False
        event = protocol.event.ClientMessage(window=window, client_type=display.intern_atom(
            '_NET_ACTIVE_WINDOW'), data=(32, [2, X.CurrentTime, 0, 0, 0]))
        display.screen().root.send_event(event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        display.flush()
        deadline=time.monotonic()+timeout_sec
        while time.monotonic()<deadline:
            if get_frontmost_app_info()[1] == identity:
                return True
            time.sleep(0.02)
    except Exception:
        return False
    finally:
        if display:
            display.close()
    return False


def get_stable_app_identity(identity):
    from fixoflow.app_identity import executable_scope
    display=None
    try:
        xid,pid,born=json.loads(identity)
        display=_display();window=display.create_resource_object('window',xid)
        if _identity(display,window)!=[xid,pid,born]:return ''
        executable=os.readlink(Path('/proc')/str(pid)/'exe')
        if _identity(display,window)!=[xid,pid,born]:return ''
        return executable_scope(executable,'linux')
    except Exception:return ''
    finally:
        if display:display.close()


def copy_to_clipboard(text):
    command=['wl-copy'] if os.environ.get('XDG_SESSION_TYPE')=='wayland' else ['xclip','-selection','clipboard']
    if not shutil.which(command[0]):
        return False
    try:
        subprocess.run(command, input=text.encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=3, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def insert_text_at_cursor(text,delay_sec=0.05,expected_target=None,cancelled=None,restore_clipboard=False):
    from dataclasses import replace
    if restore_clipboard and os.environ.get('XDG_SESSION_TYPE')!='wayland':
        from fixoflow.clipboard_x11 import X11ClipboardAdapter
        return insert_with_restoration(_insert_text_at_cursor,copy_to_clipboard,_clipboard_restoration,
            X11ClipboardAdapter,text,delay_sec,expected_target,cancelled,True)
    _clipboard_restoration.discard()
    outcome=_insert_text_at_cursor(text,delay_sec,expected_target,cancelled)
    if restore_clipboard:
        return replace(outcome,clipboard_restore_unavailable='Previous clipboard restoration is unavailable with the current X11/Wayland clipboard tools. Dictated text is kept for manual paste.')
    return outcome


def _insert_text_at_cursor(text,delay_sec=0.05,expected_target=None,cancelled=None,_copy=None):
    if not (_copy or copy_to_clipboard)(text):
        return InsertionOutcome(False, False, 'clipboard-failed')
    if cancelled and cancelled():
        return InsertionOutcome(False, True, 'cancelled')
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        return InsertionOutcome(False, True, 'permission')
    try:
        from pynput.keyboard import Controller,Key
        target = expected_target if expected_target is not None else get_frontmost_app_info()[1]
        time.sleep(delay_sec)
        if not target or get_frontmost_app_info()[1] != target:
            return InsertionOutcome(False, True, 'event-failed')
        keyboard=Controller()
        if cancelled and cancelled():
            return InsertionOutcome(False, True, 'cancelled')
        with keyboard.pressed(Key.ctrl):
            keyboard.press('v')
            keyboard.release('v')
        return InsertionOutcome(True,True,'inserted')
    except Exception:
        return InsertionOutcome(False, True, 'event-failed')


from fixoflow.clipboard import ClipboardRestoration,insert_with_restoration,restore_status,copy_with_restoration

_clipboard_restoration=ClipboardRestoration()


def copy_to_clipboard_preserving(text):
    if os.environ.get('XDG_SESSION_TYPE')=='wayland':
        _clipboard_restoration.discard()
        return copy_to_clipboard(text)
    from fixoflow.clipboard_x11 import X11ClipboardAdapter
    return copy_with_restoration(copy_to_clipboard,_clipboard_restoration,X11ClipboardAdapter,text).copied


def clipboard_restore_status():
    if os.environ.get('XDG_SESSION_TYPE')=='wayland':
        return {'pending':False,'message':'Previous clipboard restoration is unavailable in Wayland sessions.'}
    return _clipboard_restoration.status()


def restore_previous_clipboard(insertion_confirmed=False):
    if os.environ.get('XDG_SESSION_TYPE')=='wayland':
        return {'restored':False,**clipboard_restore_status()}
    return restore_status(_clipboard_restoration,insertion_confirmed)


def discard_previous_clipboard():
    _clipboard_restoration.discard()


def permission_snapshot():
    x11=os.environ.get('XDG_SESSION_TYPE')!='wayland' and bool(os.environ.get('DISPLAY'))
    return {'platform':'Linux','accessibility':x11,'input':x11,'microphone':'unknown'}


def request_all_permissions():return permission_snapshot()
def open_permission_settings(section):return None


def notify(title,body):
    if shutil.which('notify-send'):
        subprocess.Popen(['notify-send', title, body], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    return False


def play_sound(name):pass
