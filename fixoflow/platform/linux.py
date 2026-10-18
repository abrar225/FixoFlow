"""Linux X11 integration; Wayland is explicitly clipboard-only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from .contracts import InsertionOutcome


def _display():
    if os.environ.get('XDG_SESSION_TYPE')=='wayland':raise RuntimeError('Global shortcuts and automatic insertion require an X11 session.')
    from Xlib.display import Display
    return Display()


def _identity(display,window):
    prop=window.get_full_property(display.intern_atom('_NET_WM_PID'),0)
    if prop is None or not len(prop.value):return None
    pid=int(prop.value[0])
    # /proc start time prevents a reused window/PID from inheriting a transcript.
    fields=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    return [window.id,pid,fields[19]]


def get_frontmost_app_info():
    display=None
    try:
        display=_display(); root=display.screen().root
        prop=root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'),0)
        if prop is None or not len(prop.value) or not prop.value[0]:return 'Unknown',''
        window=display.create_resource_object('window',int(prop.value[0])); identity=_identity(display,window)
        name=window.get_wm_class() or (window.get_wm_name() or 'Application',)
        return str(name[-1]),json.dumps(identity) if identity else ''
    except Exception:return 'Unknown',''
    finally:
        if display:display.close()


def activate_application(identity,timeout_sec=0.8):
    display=None
    try:
        from Xlib import X,protocol
        xid,pid,born=json.loads(identity); display=_display(); window=display.create_resource_object('window',xid)
        if _identity(display,window)!=[xid,pid,born]:return False
        event=protocol.event.ClientMessage(window=window,client_type=display.intern_atom('_NET_ACTIVE_WINDOW'),data=(32,[2,X.CurrentTime,0,0,0]))
        display.screen().root.send_event(event,event_mask=X.SubstructureRedirectMask|X.SubstructureNotifyMask);display.flush()
        deadline=time.monotonic()+timeout_sec
        while time.monotonic()<deadline:
            if get_frontmost_app_info()[1]==identity:return True
            time.sleep(0.02)
    except Exception:return False
    finally:
        if display:display.close()
    return False


def copy_to_clipboard(text):
    command=['wl-copy'] if os.environ.get('XDG_SESSION_TYPE')=='wayland' else ['xclip','-selection','clipboard']
    if not shutil.which(command[0]):return False
    try:
        subprocess.run(command,input=text.encode(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3,check=True)
        return True
    except (OSError,subprocess.SubprocessError):return False


def insert_text_at_cursor(text,delay_sec=0.05):
    if not copy_to_clipboard(text):return InsertionOutcome(False,False,'clipboard-failed')
    if os.environ.get('XDG_SESSION_TYPE')=='wayland':return InsertionOutcome(False,True,'permission')
    try:
        from pynput.keyboard import Controller,Key
        target=get_frontmost_app_info()[1];time.sleep(delay_sec)
        if not target or get_frontmost_app_info()[1]!=target:return InsertionOutcome(False,True,'event-failed')
        keyboard=Controller()
        with keyboard.pressed(Key.ctrl):keyboard.press('v');keyboard.release('v')
        return InsertionOutcome(True,True,'inserted')
    except Exception:return InsertionOutcome(False,True,'event-failed')


def permission_snapshot():
    x11=os.environ.get('XDG_SESSION_TYPE')!='wayland' and bool(os.environ.get('DISPLAY'))
    return {'accessibility':x11,'input':x11,'microphone':'not determined'}
def request_all_permissions():return permission_snapshot()
def open_permission_settings(section):return None
def notify(title,body):
    if shutil.which('notify-send'):
        subprocess.Popen(['notify-send',title,body],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);return True
    return False
def play_sound(name):pass
