"""Windows desktop integration. Never requires administrator privileges."""
from __future__ import annotations
import ctypes as c
from ctypes import wintypes as w
import json
import os
import threading
import time
from .contracts import InsertionOutcome

u = c.WinDLL('user32', use_last_error=True)
k = c.WinDLL('kernel32', use_last_error=True)
u.GetForegroundWindow.restype = w.HWND
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.IsWindow.argtypes = [w.HWND]
u.SetForegroundWindow.argtypes = [w.HWND]
k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k.OpenProcess.restype = w.HANDLE
k.CloseHandle.argtypes = [w.HANDLE]
k.GetProcessTimes.argtypes = [w.HANDLE, *([c.POINTER(w.FILETIME)]*4)]
k.GlobalAlloc.argtypes = [w.UINT, c.c_size_t]
k.GlobalAlloc.restype = w.HGLOBAL
k.GlobalLock.argtypes = [w.HGLOBAL]
k.GlobalLock.restype = c.c_void_p
k.GlobalUnlock.argtypes = [w.HGLOBAL]
k.GlobalFree.argtypes = [w.HGLOBAL]
u.SetClipboardData.argtypes = [w.UINT, w.HANDLE]
u.SetClipboardData.restype = w.HANDLE
u.GetWindowTextLengthW.argtypes = [w.HWND]
u.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
clipboard_lock = threading.Lock()


def _identity(hwnd):
    pid = w.DWORD()
    u.GetWindowThreadProcessId(hwnd, c.byref(pid))
    handle = k.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return None
    try:
        times = [w.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle, *[c.byref(t) for t in times]):
            return None
        born = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        return [int(hwnd), pid.value, born]
    finally:
        k.CloseHandle(handle)


def get_frontmost_app_info():
    hwnd = u.GetForegroundWindow()
    identity = _identity(hwnd) if hwnd else None
    if not identity:
        return 'Unknown', ''
    process = k.OpenProcess(0x1000, False, identity[1])
    name = 'Application'
    if process:
        try:
            size = w.DWORD(32768)
            buffer = c.create_unicode_buffer(size.value)
            k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
            if k.QueryFullProcessImageNameW(process, 0, buffer, c.byref(size)):
                from pathlib import PureWindowsPath
                name = PureWindowsPath(buffer.value).stem
        finally:
            k.CloseHandle(process)
    return name, json.dumps(identity)


def activate_application(identity, timeout_sec=0.8):
    try:
        hwnd, pid, born = json.loads(identity)
        if not u.IsWindow(hwnd) or _identity(hwnd) != [hwnd, pid, born]:
            return False
        u.SetForegroundWindow(hwnd)
        deadline = time.monotonic()+timeout_sec
        while time.monotonic() < deadline:
            if get_frontmost_app_info()[1] == identity:
                return True
            time.sleep(0.02)
    except (ValueError, TypeError, OSError):
        pass
    return False


def copy_to_clipboard(text):
    # Clipboard handles transfer ownership only after SetClipboardData succeeds.
    data = (text+'\0').encode('utf-16-le')
    owned = None
    with clipboard_lock:
        for _ in range(10):
            if u.OpenClipboard(None):
                break
            time.sleep(0.01)
        else:
            return False
        try:
            owned = k.GlobalAlloc(0x0002, len(data))
            if not owned:
                return False
            ptr = k.GlobalLock(owned)
            if not ptr:
                return False
            c.memmove(ptr, data, len(data))
            k.GlobalUnlock(owned)
            if not u.EmptyClipboard() or not u.SetClipboardData(13, owned):
                return False
            owned = None
            return True
        finally:
            if owned:
                k.GlobalFree(owned)
            u.CloseClipboard()


class KEYBDINPUT(c.Structure):
    _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', c.c_size_t)]


class MOUSEINPUT(c.Structure):
    _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD),
                ('dwFlags', w.DWORD), ('time', w.DWORD), ('dwExtraInfo', c.c_size_t)]


class HARDWAREINPUT(c.Structure):
    _fields_ = [('uMsg', w.DWORD), ('wParamL', w.WORD), ('wParamH', w.WORD)]


class INPUTUNION(c.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]


class INPUT(c.Structure):
    _anonymous_ = ('value',)
    _fields_ = [('type', w.DWORD), ('value', INPUTUNION)]


u.SendInput.argtypes = [w.UINT, c.POINTER(INPUT), c.c_int]
u.SendInput.restype = w.UINT


def insert_text_at_cursor(text, delay_sec=0.05, expected_target=None, cancelled=None):
    if not copy_to_clipboard(text):
        return InsertionOutcome(False, False, 'clipboard-failed')
    if cancelled and cancelled():
        return InsertionOutcome(False, True, 'cancelled')
    target = expected_target if expected_target is not None else get_frontmost_app_info()[1]
    deadline = time.monotonic()+0.8
    # Do not paste while the user's shortcut modifiers are physically held.
    while any(u.GetAsyncKeyState(v) & 0x8000 for v in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
        if cancelled and cancelled():
            return InsertionOutcome(False, True, 'cancelled')
        if time.monotonic() > deadline:
            return InsertionOutcome(False, True, 'event-failed')
        time.sleep(0.01)
    time.sleep(delay_sec)
    if not target or get_frontmost_app_info()[1] != target:
        return InsertionOutcome(False, True, 'event-failed')
    events = (INPUT*4)(*[INPUT(type=1, ki=KEYBDINPUT(wVk=vk, dwFlags=flags))
                         for vk, flags in [(0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2)]])
    if cancelled and cancelled():
        return InsertionOutcome(False, True, 'cancelled')
    sent = u.SendInput(4, events, c.sizeof(INPUT))
    if sent != 4:
        # Best-effort key-up after a partially accepted sequence; UIPI may reject all.
        releases = (INPUT*2)(INPUT(type=1, ki=KEYBDINPUT(wVk=0x56, dwFlags=2)),
                             INPUT(type=1, ki=KEYBDINPUT(wVk=0x11, dwFlags=2)))
        u.SendInput(2, releases, c.sizeof(INPUT))
    return InsertionOutcome(sent == 4, True, 'inserted' if sent == 4 else 'event-failed')


def permission_snapshot():
    return {'platform': 'Windows', 'accessibility': None, 'input': None, 'microphone': 'unknown'}


def request_all_permissions():
    open_permission_settings('microphone')
    return permission_snapshot()


def open_permission_settings(section):
    if section == 'microphone':
        os.startfile('ms-settings:privacy-microphone')


def notify(title, body):
    # The app's visible status/history is the reliable fallback; no blocking dialogs.
    import logging
    logging.getLogger('fixoflow.platform').info('%s: %s', title, body)
    return False


def play_sound(name):
    import winsound
    winsound.MessageBeep(winsound.MB_OK)
