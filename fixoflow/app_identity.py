"""Persistent personalization scope is separate from a short-lived paste target.

Legacy native Mac bundle identifiers can be migrated without guessing. Legacy
Windows/X11 window/PID arrays cannot: keep them as provenance, not active scope.
"""
import ntpath
import re
import os
import sys


def app_scope(value):
    if not isinstance(value, str):
        return ''
    if value.startswith(('macos:bundle:', 'windows:exe:', 'linux:exe:')):
        return value
    if re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+', value):
        return 'macos:bundle:' + value
    return ''


def executable_scope(path, system):
    if system == 'windows' and isinstance(path, str) and ntpath.isabs(path):
        return 'windows:exe:' + ntpath.normcase(ntpath.normpath(path))
    if system == 'linux' and isinstance(path, str) and path.startswith('/') and not path.endswith(' (deleted)'):
        return 'linux:exe:' + path
    return ''


def windows_process_alive(pid, kernel=None):
    """Query process state without console events: os.kill(pid,0) is unsafe on Windows."""
    import ctypes as c
    from ctypes import wintypes as w
    kernel=kernel if kernel is not None else c.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,c.POINTER(w.DWORD)];kernel.GetExitCodeProcess.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:
        # Invalid PID means absent; access denied/unknown errors fail closed.
        return c.get_last_error()!=87
    try:
        code=w.DWORD()
        return bool(not kernel.GetExitCodeProcess(handle,c.byref(code)) or code.value==259)
    finally:kernel.CloseHandle(handle)


def process_alive(pid):
    if pid<=0:return True
    if sys.platform=='win32':return windows_process_alive(pid)
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
    except (PermissionError,OSError):return True
