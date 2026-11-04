"""Shared tray menu model and optional Windows/Linux native status icon.

All callbacks are dispatched to the host mutation queue. A missing tray backend
is an ordinary capability limitation; it must never hide the only app window.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import logging
from pathlib import Path
import threading
import sys
import time

logger = logging.getLogger(__name__)


def choice_config(config, action, value):
    from dataclasses import replace
    from fixoflow.languages import options
    if action == 'selectModel':
        choices = {item['value'] for item in options(value)}
        language = config.language or 'auto'
        if language not in choices:
            language = 'en' if 'en' in choices else 'auto'
        return replace(config, model_name=value, language=None if language == 'auto' else language)
    if action == 'selectLanguage':
        if value not in {item['value'] for item in options(config.model_name)}:
            raise ValueError('This model does not support that language choice.')
        return replace(config, language=None if value == 'auto' else value)
    if action == 'selectMicrophone': return replace(config, input_device=value)
    if action == 'selectMode': return replace(config, mode=value)
    raise ValueError('Unknown tray preference.')


@dataclass(frozen=True)
class TrayEntry:
    label: str
    action: str = ''
    value: str = ''
    enabled: bool = True
    checked: bool | None = None
    children: tuple = field(default_factory=tuple)


def entries(config, status, models=(), devices=(), clipboard_pending=False):
    state = status.get('state', 'IDLE')
    idle = state == 'IDLE' and not status.get('busy', False)
    selected = next((m for m in models if m['model_name'] == config.model_name), None)
    name = selected['name'] if selected else 'Base English · bundled' if config.model_name in {
        'bundled-base.en','mlx-community/whisper-base.en-mlx'} else Path(config.model_name).name
    model_choices = tuple(TrayEntry(m['name'], 'selectModel', m['model_name'], idle,
                         m['model_name'] == config.model_name) for m in models if m.get('compatible') and m.get('installed'))
    mic_choices = (TrayEntry('System default', 'selectMicrophone', '', idle, not config.input_device),) + tuple(
        TrayEntry(d['name'], 'selectMicrophone', d['id'], idle, d['id'] == config.input_device)
        for d in devices)
    mic = next((d['name'] for d in devices if d['id'] == config.input_device), 'Saved microphone') if config.input_device else 'System default'
    from fixoflow.languages import options
    languages = tuple(TrayEntry(item['label'], 'selectLanguage', item['value'], idle,
                      item['value'] == (config.language or 'auto')) for item in options(config.model_name))
    result = [TrayEntry('Fixo Flow · ' + {'IDLE':'Ready','RECORDING':'Listening','PROCESSING':'Transcribing'}.get(state,state), enabled=False),
        TrayEntry('Open Fixo Flow', 'openHub'),
        TrayEntry('Stop dictation' if state == 'RECORDING' else 'Transcribing…' if state == 'PROCESSING' else 'Start hands-free dictation',
                  'toggle', enabled=(state == 'RECORDING' or idle)),
        TrayEntry('Cancel dictation', 'cancel', enabled=state in {'RECORDING','PROCESSING'}),
        TrayEntry('Model: ' + name, enabled=False)]
    if selected:
        result.append(TrayEntry('Model status: ' + selected.get('state','installed'), enabled=False))
    if model_choices: result.append(TrayEntry('Choose installed model', children=model_choices))
    result.extend([TrayEntry('Language: ' + (config.language or 'Auto detect'), children=languages),
        TrayEntry('Microphone: ' + mic, children=mic_choices),
        TrayEntry('Mode', children=tuple(TrayEntry(label,'selectMode',mode,idle,config.mode == mode) for mode,label in
            [('auto','Automatic'),('coding','Coding & AI'),('writing','Writing'),('raw','Raw transcript')])),
        TrayEntry('Model downloads and settings…', 'openSettings'),
        TrayEntry('Guided setup…', 'openSetup'),
        TrayEntry('Recovery inbox…', 'openRecovery'),
        TrayEntry('Restore previous clipboard after paste', 'restoreClipboard', enabled=clipboard_pending),
        TrayEntry('Quit Fixo Flow', 'quit')])
    return tuple(result)


class DesktopTray:
    def __init__(self, menu, dispatch, backend=None, image_loader=None):
        self._menu = menu
        self._dispatch = dispatch
        self._backend = backend
        self._image_loader = image_loader
        self._icon = None
        self._ready = threading.Event()
        self.error = ''
        self._host_checked = 0.0
        self._host_present = False

    @property
    def can_hide(self):
        if not (self._ready.is_set() and self._icon is not None and bool(self._icon.HAS_MENU)):
            return False
        if not sys.platform.startswith('linux'):
            return True
        # AppIndicator can accept an icon even when GNOME has no tray host.
        # Never hide the only window merely because the backend imported.
        if time.monotonic()-self._host_checked>5:
            self._host_checked=time.monotonic()
            self._host_present=False
            try:
                from gi.repository import Gio, GLib
                bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
                result=bus.call_sync('org.kde.StatusNotifierWatcher','/StatusNotifierWatcher',
                    'org.freedesktop.DBus.Properties','Get',
                    GLib.Variant('(ss)',('org.kde.StatusNotifierWatcher','IsStatusNotifierHostRegistered')),
                    GLib.VariantType('(v)'),Gio.DBusCallFlags.NONE,300,None)
                self._host_present=bool(result.unpack()[0])
            except Exception:
                status_icon=getattr(self._icon,'_status_icon',None)
                try:self._host_present=bool(status_icon and status_icon.is_embedded())
                except Exception:pass
        return self._host_present

    def snapshot(self):
        return {'available': self.can_hide, 'ready': self._ready.is_set(),
                'message': self.error or ('Available in the system tray.' if self.can_hide else 'A usable tray host was not detected; closing the window exits instead of hiding it.')}

    def _native_menu(self):
        backend = self._backend
        def item(entry):
            action = backend.Menu(*(item(child) for child in entry.children)) if entry.children else (
                lambda icon, menu_item: self._dispatch(entry.action, entry.value))
            checked = (lambda menu_item: entry.checked) if entry.checked is not None else None
            return backend.MenuItem(entry.label, action, enabled=entry.enabled and bool(entry.action or entry.children),
                                    checked=checked, default=entry.action == 'openHub')
        return backend.Menu(*(item(entry) for entry in self._menu()))

    def start(self):
        if self._icon is not None:
            return
        try:
            if self._backend is None:
                import pystray
                self._backend = pystray
            if not self._backend.Icon.HAS_MENU:
                raise RuntimeError('This desktop tray backend has no menu; use the app window.')
            if self._image_loader is None:
                from PIL import Image
                self._image_loader = Image.open
            with self._image_loader(Path(__file__).parent/'ui/assets/flow-fold.png') as image:
                self._icon = self._backend.Icon('FixoFlow', image.copy(), 'Fixo Flow', menu=self._native_menu())
            def setup(icon):
                icon.visible = True
                self._ready.set()
            # GTK/AppIndicator share the host GTK main loop. Win32 owns its own
            # message thread. macOS uses the native AppKit menu instead.
            self._icon.run_detached(setup=setup)
        except Exception as error:
            self.error = 'System tray unavailable: ' + str(error)
            logger.warning('%s', self.error)
            self._ready.clear()
            if self._icon:
                try: self._icon.stop()
                except Exception: pass
            self._icon = None

    def refresh(self):
        if self._ready.is_set() and self._icon:
            try:
                self._icon.menu = self._native_menu()
                self._icon.update_menu()
            except Exception as error:
                self.error = 'Tray refresh failed: ' + str(error)
                self._ready.clear()
                logger.warning('%s', self.error)

    def close(self):
        self._ready.clear()
        if self._icon:
            self._icon.stop()
            self._icon = None
