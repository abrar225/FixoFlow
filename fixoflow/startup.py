"""Per-user login registration. Development and diagnostic runs never register.

OS registration is authoritative after first setup; normal launches do not
repair a missing/disabled entry and override a user's system preference.
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import time


class MacLogin:
    def __init__(self):
        from ServiceManagement import SMAppService
        self.service = SMAppService.mainAppService()

    def status(self):
        # SMAppServiceStatus: not registered, enabled, requires approval, missing.
        value = int(self.service.status())
        return value == 1, value == 2

    def set(self, enabled):
        ok, error = (self.service.registerAndReturnError_(None) if enabled
                     else self.service.unregisterAndReturnError_(None))
        if not ok:
            raise RuntimeError(str(error or 'macOS could not change the login item.'))


class WindowsLogin:
    key = r'Software\Microsoft\Windows\CurrentVersion\Run'
    name = 'FixoFlow'

    def __init__(self, executable):
        import winreg
        self.registry = winreg
        self.command = subprocess.list2cmdline([str(executable), '--background'])
        if len(self.command) > 260:
            raise ValueError('Install Fixo Flow in a shorter path to enable startup.')

    def status(self):
        r = self.registry
        try:
            with r.OpenKey(r.HKEY_CURRENT_USER, self.key) as key:
                value, _ = r.QueryValueEx(key, self.name)
            return value == self.command, False
        except FileNotFoundError:
            return False, False

    def set(self, enabled):
        r = self.registry
        with r.CreateKey(r.HKEY_CURRENT_USER, self.key) as key:
            if enabled:
                try:
                    previous, _ = r.QueryValueEx(key, self.name)
                except FileNotFoundError:
                    previous = None
                if previous is not None and previous != self.command:
                    raise RuntimeError(
                        'A different Fixo Flow startup entry exists. Remove it in Windows Startup Apps first.')
                r.SetValueEx(key, self.name, 0, r.REG_SZ, self.command)
            else:
                try:
                    previous, _ = r.QueryValueEx(key, self.name)
                except FileNotFoundError:
                    return
                if previous != self.command:
                    raise RuntimeError('The startup entry belongs to another installation; it was preserved.')
                r.DeleteValue(key, self.name)


def desktop_exec(path):
    """Desktop Entry escaping (two passes), not shell quoting."""
    value = str(path)
    if any(char in value for char in '\n\r\0'):
        raise ValueError('Unsupported startup path.')
    value = value.replace('%', '%%')
    value = ''.join('\\' + char if char in '\\"`$' else char for char in value)
    return '"' + value.replace('\\', '\\\\') + '" --background'


class LinuxLogin:
    def __init__(self, executable, config_home=None):
        base = Path(config_home or os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
        if not base.is_absolute():
            base = Path.home()/'.config'
        self.path = base/'autostart/com.fixoflow.desktop'
        self.command = desktop_exec(executable)
        self.content = ('[Desktop Entry]\nType=Application\nName=Fixo Flow\n'
                        f'Exec={self.command}\nTryExec={str(executable).replace(chr(92), chr(92)*2)}\nTerminal=false\nX-FixoFlow-Owned=true\n')

    def _parse(self, text):
        parser = configparser.ConfigParser(interpolation=None, strict=True,
                                           delimiters=('=',), comment_prefixes=('#',), empty_lines_in_values=False)
        parser.optionxform = str
        parser.read_string(text)
        entry = parser['Desktop Entry']
        if entry.get('X-FixoFlow-Owned') != 'true' or entry.get('Exec') != self.command:
            raise RuntimeError('A different startup entry exists; it was preserved.')
        return entry

    def _open(self, flags):
        fd = os.open(self.path, flags | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            os.close(fd)
            raise RuntimeError('Startup entry is not a small regular file; it was preserved.')
        return fd

    def status(self):
        if self.path.is_symlink():
            raise RuntimeError('Startup entry is a symbolic link; it was preserved.')
        try:
            with os.fdopen(self._open(os.O_RDONLY), 'r', encoding='utf-8') as stream:
                entry = self._parse(stream.read(65537))
        except FileNotFoundError:
            return False, False
        return (entry.get('Hidden', 'false').lower() != 'true' and
                entry.get('X-GNOME-Autostart-enabled', 'true').lower() != 'false'), False

    def set(self, enabled):
        # Open the actual inode without following links; validate that inode
        # before writing. A concurrent pathname replacement is never overwritten
        # or unlinked. Off uses Hidden=true, the XDG disable mechanism.
        if self.path.is_symlink():
            raise RuntimeError('Startup entry is a symbolic link; it was preserved.')
        try:
            fd = self._open(os.O_RDWR)
        except FileNotFoundError:
            if not enabled:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix='.fixoflow-')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(self.content)
                    stream.flush()
                    os.fsync(stream.fileno())
                # Exclusive publication, unlike replace(): preserve any entry
                # that appeared since the initial open, including foreign data.
                os.link(temporary, self.path)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return
        with os.fdopen(fd, 'r+', encoding='utf-8') as stream:
            import fcntl
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError('Startup entry is busy. Please retry the change.') from error
            self._parse(stream.read(65537))
            identity = os.fstat(stream.fileno())
            current = self.path.stat(follow_symlinks=False)
            if (identity.st_dev, identity.st_ino) != (current.st_dev, current.st_ino):
                raise RuntimeError('Startup entry changed during setup; it was preserved.')
            stream.seek(0)
            stream.write(self.content + ('Hidden=false\n' if enabled else 'Hidden=true\n'))
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())


class StartupService:
    def __init__(self, backend=None):
        self.backend = backend
        self.error = ''
        self._pending = None
        self._pending_since = 0.0
        if backend is not None or not getattr(sys, 'frozen', False):
            return
        executable = Path(sys.executable).resolve()
        try:
            if sys.platform == 'darwin':
                from Foundation import NSBundle
                bundle = NSBundle.mainBundle()
                path = Path(bundle.bundlePath())
                if bundle.bundleIdentifier() != 'com.fixoflow.app' or path.parent not in {Path('/Applications'), Path.home()/'Applications'}:
                    raise RuntimeError('Move Fixo Flow to Applications to enable startup.')
                self.backend = MacLogin()
            elif sys.platform == 'win32':
                self.backend = WindowsLogin(executable)
            elif sys.platform.startswith('linux'):
                if executable != Path('/opt/fixoflow/Fixoflow'):
                    raise RuntimeError('Install the Linux package to enable startup.')
                self.backend = LinuxLogin(executable)
        except Exception as error:
            self.error = str(error)

    def snapshot(self):
        enabled = approval = False
        try:
            if self.backend:
                enabled, approval = self.backend.status()
            message = ('Allow Fixo Flow in System Settings → General → Login Items.' if approval else
                       'Starts quietly after you sign in.' if enabled else 'Automatic startup is off.')
            if sys.platform == 'win32' and self.backend:
                message = ('Registered for login. Windows Startup Apps can still disable this entry.' if enabled else message)
            pending = False
            if self._pending is not None:
                if bool(enabled or approval) == self._pending:
                    self._pending = None
                elif time.monotonic() - self._pending_since < 10:
                    pending = True
                    message = 'Waiting for the system to confirm the startup setting…'
                else:
                    self._pending = None
                    message = 'The system has not confirmed the change. Check your system startup settings.'
            return {'supported': self.backend is not None, 'enabled': enabled, 'approval': approval,
                    'pending': pending, 'requested': self._pending,
                    'manage': self.backend is not None and sys.platform in {'darwin', 'win32'},
                    'message': self.error or (message if self.backend else 'Startup is available in the installed application.')}
        except Exception as error:
            return {'supported': False, 'enabled': False, 'approval': False, 'message': str(error)}

    def open_settings(self):
        if self.backend is None:
            raise RuntimeError(self.snapshot()['message'])
        if sys.platform == 'darwin':
            from ServiceManagement import SMAppService
            SMAppService.openSystemSettingsLoginItems()
        elif sys.platform == 'win32':
            os.startfile('ms-settings:startupapps')

    def initialize(self, config):
        if self.backend is None or config.login_setup_done:
            return
        if config.start_at_login:
            enabled, approval = self.backend.status()
            if not enabled and not approval:
                self.backend.set(True)
        from dataclasses import replace
        candidate = replace(config, login_setup_done=True)
        candidate.save()
        config.login_setup_done = True
        if config.start_at_login:
            self._pending = True
            self._pending_since = time.monotonic()

    def commit(self, config, candidate, apply, explicit=False):
        """Compensate registration if preference persistence/application fails."""
        changed = candidate.start_at_login != config.start_at_login or explicit
        if not changed:
            return apply()
        if self.backend is None:
            raise RuntimeError(self.snapshot()['message'])
        enabled, approval = self.backend.status()
        self.backend.set(candidate.start_at_login)
        candidate.login_setup_done = True
        try:
            result = apply()
            self.error = ''
            self._pending = candidate.start_at_login
            self._pending_since = time.monotonic()
            return result
        except Exception as error:
            try:
                self.backend.set(enabled or approval)
            except Exception as rollback:
                raise RuntimeError(f'{error} Startup restoration also failed: {rollback}') from error
            raise


def launched_at_login(event=None):
    """Apple's login launch event; ordinary Dock opens keep opening the hub."""
    if event is None:
        from Foundation import NSAppleEventManager
        event = NSAppleEventManager.sharedAppleEventManager().currentAppleEvent()
    if event is None:
        return False

    def keyword(value): return int.from_bytes(value.encode('ascii'), 'big')
    if event.eventID() != keyword('oapp'):
        return False
    marker = event.paramDescriptorForKeyword_(keyword('prdt'))
    return bool((marker and marker.enumCodeValue() == keyword('lgit')) or
                event.attributeDescriptorForKeyword_(keyword('lgit')) or
                event.paramDescriptorForKeyword_(keyword('lgit')))
