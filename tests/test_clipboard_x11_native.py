"""Opt-in integration on a disposable Xvfb server only, never a user's DISPLAY.

Run: xvfb-run -a env FIXOFLOW_TEST_X11_ISOLATED=1 python -m pytest
tests/test_clipboard_x11_native.py -q
"""
import os
import sys

import pytest

if sys.platform!='linux' or os.environ.get('FIXOFLOW_TEST_X11_ISOLATED')!='1':
    pytest.skip('Requires an explicitly disposable Xvfb display.',allow_module_level=True)

from Xlib import X
from Xlib.display import Display
from fixoflow.clipboard import ClipboardRestoration
from fixoflow.clipboard_x11 import X11ClipboardAdapter,X11SelectionServer,X11_MAX_BYTES


def read_text():
    import time
    reader=X11SelectionServer('',X11_MAX_BYTES)
    reader.display=Display();reader.selection=reader.display.intern_atom('CLIPBOARD')
    reader.window=reader.display.screen().root.create_window(0,0,1,1,0,X.CopyFromParent)
    try:
        return bytes(reader._read_target('UTF8_STRING',time.monotonic()+2).value).decode()
    finally:
        reader.window.destroy();reader.display.close()


def test_native_x11_owner_serves_and_restores_without_reacquiring_new_selection():
    servers=[]
    def factory(text,maximum):
        server=X11SelectionServer(text,maximum);servers.append(server);return server
    try:
        old=X11SelectionServer('original text',X11_MAX_BYTES);servers.append(old);old.start()
        memory=ClipboardRestoration()
        memory.write(X11ClipboardAdapter(factory),'dictated words')
        assert read_text()=='dictated words'
        memory.write(X11ClipboardAdapter(factory),'second dictation')
        assert read_text()=='second dictation'
        assert not memory.restore().restored
        assert memory.restore(insertion_confirmed=True).restored
        assert read_text()=='original text'
        memory.write(X11ClipboardAdapter(factory),'next dictation')
        newer=X11SelectionServer('new user copy',X11_MAX_BYTES);servers.append(newer);newer.start()
        assert not memory.restore(insertion_confirmed=True).restored
        assert read_text()=='new user copy'
    finally:
        for server in servers:server._closed=True
        for server in servers:
            if server._thread:server._thread.join(2)
