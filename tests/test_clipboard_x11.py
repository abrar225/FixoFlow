"""Fake X11 protocol/owner tests; no DISPLAY or user's selection is touched."""
from types import SimpleNamespace

import pytest

from fixoflow.clipboard import ClipboardRestoration
from fixoflow.clipboard_x11 import X11ClipboardAdapter,X11SelectionServer,X11_MAX_BYTES


class FakeServer:
    def __init__(self,text,maximum):
        self.text=text;self.maximum=maximum;self.snapshot={'text/html':('text/html',b'<b>old</b>'),'image/png':('image/png',b'\x89PNG')}
        self.unavailable_reason='';self.owner=42;self.current={'UTF8_STRING':('UTF8_STRING',text.encode())};self.started=False
    def start(self):self.started=True
    def restore(self,snapshot):
        if self.owner!=42:return False,'Clipboard changed; newer clipboard content was preserved.'
        self.current=snapshot
        return True,'Previous clipboard restored.'


def test_x11_rich_snapshot_stays_pending_until_confirmed_and_is_released():
    instances=[]
    def factory(text,maximum):
        server=FakeServer(text,maximum);instances.append(server);return server
    memory=ClipboardRestoration()
    memory.write(X11ClipboardAdapter(factory),'dictated')
    server=instances[0]
    assert server.started and server.maximum==X11_MAX_BYTES
    assert server.snapshot is None  # no second hidden reference to previous data
    assert not memory.restore().restored
    assert server.current['UTF8_STRING'][1]==b'dictated'
    assert memory.restore(insertion_confirmed=True).restored
    assert server.current['image/png'][1]==b'\x89PNG'


def test_x11_new_owner_is_never_reacquired_to_restore():
    instances=[]
    def factory(*args):
        server=FakeServer(*args);instances.append(server);return server
    memory=ClipboardRestoration();memory.write(X11ClipboardAdapter(factory),'dictated')
    server=instances[0];server.owner=99;server.current={'UTF8_STRING':('UTF8_STRING',b'new clipboard')}
    assert not memory.restore(insertion_confirmed=True).restored
    assert server.owner==99 and server.current['UTF8_STRING'][1]==b'new clipboard'


def test_x11_adapter_cannot_claim_pending_if_snapshot_is_unsupported():
    def factory(*args):
        server=FakeServer(*args);server.snapshot=None;server.unavailable_reason='Unsupported target';return server
    memory=ClipboardRestoration();result=memory.write(X11ClipboardAdapter(factory),'dictated')
    assert result.copied and not memory.pending and result.unavailable_reason=='Unsupported target'


def test_large_dictation_declines_native_transfer_before_any_x_connection():
    server=X11SelectionServer('x'*(X11_MAX_BYTES+1),X11_MAX_BYTES)
    with pytest.raises(ValueError,match='transfer limit'):server.start()
    assert server._thread is None


def test_closed_selection_server_never_restores():
    server=X11SelectionServer('text',100)
    restored,message=server.restore({})
    assert not restored and 'newer' in message


def test_capture_rejects_unknown_targets_and_incr_without_materializing_bytes():
    server=X11SelectionServer('text',100)
    server._owner=lambda:42
    server.display=SimpleNamespace(get_atom_name=lambda atom:{1:'application/private-handle'}[atom])
    server._read_target=lambda *args:SimpleNamespace(format=32,value=[1])
    with pytest.raises(ValueError,match='representations'):server._capture()


def test_capture_bounds_total_bytes_across_supported_formats():
    server=X11SelectionServer('text',10)
    server._owner=lambda:42
    server.display=SimpleNamespace(get_atom_name=lambda atom:{1:'UTF8_STRING',2:'text/html'}[atom])
    def read(target,deadline):
        if target=='TARGETS':return SimpleNamespace(format=32,value=[1,2])
        return SimpleNamespace(format=8,property_type=1,value=b'123456')
    server._read_target=read
    with pytest.raises(ValueError,match='48 KiB'):server._capture()
