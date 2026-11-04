"""Fake-native clipboard tests. Never touch the user's pasteboard or keyboard."""
import ctypes
import threading
from types import SimpleNamespace

import pytest

from fixoflow.clipboard import (ClipboardRestoration, ClipboardWrite, MacClipboardAdapter,
    WindowsClipboardAdapter, insert_with_restoration, MAX_SNAPSHOT_BYTES)
from fixoflow.platform.contracts import InsertionOutcome


class FakeAdapter:
    def __init__(self):
        self.sequence=1
        self.formats={'rich':b'{\\rtf1 original}', 'image':b'\x89PNG\x00original'}
        self.restores=0

    def capture_and_write(self,text,maximum,previous=None):
        prior=previous[0] if previous is not None and previous[1]==self.sequence else dict(self.formats)
        self.formats={'text':text.encode()};self.sequence+=1
        return ClipboardWrite(True,prior,self.sequence)

    def restore_if_owned(self,snapshot,token):
        if token!=self.sequence:return False,'Clipboard changed; preserved newer content.'
        self.formats=snapshot;self.sequence+=1;self.restores+=1
        return True,'Restored.'


def test_requires_confirmation_never_restores_on_dispatch_or_elapsed_time():
    adapter=FakeAdapter();memory=ClipboardRestoration();before=dict(adapter.formats)
    memory.write(adapter,'dictated words')
    assert memory.pending
    assert not memory.restore().restored
    assert adapter.formats=={'text':b'dictated words'} and adapter.restores==0
    assert memory.restore(insertion_confirmed=True).restored
    assert adapter.formats==before and not memory.pending


def test_new_user_copy_including_same_text_is_not_overwritten():
    for replacement in ({'text':b'new text'}, {'text':b'dictated words'}):
        adapter=FakeAdapter();memory=ClipboardRestoration()
        memory.write(adapter,'dictated words')
        adapter.formats=replacement;adapter.sequence+=1
        assert not memory.restore(insertion_confirmed=True).restored
        assert adapter.formats==replacement and not memory.pending


def test_repeated_dictation_retains_original_and_shutdown_only_discards_memory():
    adapter=FakeAdapter();memory=ClipboardRestoration()
    original=dict(adapter.formats)
    memory.write(adapter,'first')
    memory.write(adapter,'second')
    assert memory.restore(insertion_confirmed=True).restored
    assert adapter.formats==original
    memory.write(adapter,'third');memory.discard()
    assert not memory.pending and adapter.formats=={'text':b'third'}


def test_new_user_copy_resets_baseline_for_next_dictation():
    adapter=FakeAdapter();memory=ClipboardRestoration()
    memory.write(adapter,'first')
    adapter.formats={'text':b'new user content'};adapter.sequence+=1
    memory.write(adapter,'second')
    assert memory.restore(insertion_confirmed=True).restored
    assert adapter.formats=={'text':b'new user content'}


def test_failed_delivery_keeps_fallback_until_user_confirms_manual_paste():
    adapter=FakeAdapter();memory=ClipboardRestoration()
    def denied(text,**options):
        assert options['_copy'](text)
        assert options['expected_target']=='verified.target'
        return InsertionOutcome(False,True,'permission')
    result=insert_with_restoration(denied,lambda _:pytest.fail('duplicate copy'),memory,
        lambda:adapter,'dictated',0,'verified.target',None,True)
    assert not result.inserted and result.clipboard_restore_pending
    assert adapter.formats=={'text':b'dictated'}


def test_disabled_preference_does_not_read_old_clipboard():
    memory=ClipboardRestoration()
    def ordinary(text,**options):
        assert '_copy' not in options
        return InsertionOutcome(True,True,'inserted')
    result=insert_with_restoration(ordinary,lambda _:True,memory,
        lambda:pytest.fail('must not snapshot without opt-in'),'text',0,None,None,False)
    assert not result.clipboard_restore_pending


def test_preference_defaults_off():
    from fixoflow.config import FixoflowConfig
    assert FixoflowConfig().restore_clipboard is False


class MacItem:
    def __init__(self,data=None):self.data=data or {}
    @classmethod
    def alloc(cls):return cls()
    def init(self):return self
    def types(self):return list(self.data)
    def dataForType_(self,kind):return self.data.get(kind)
    def setString_forType_(self,text,kind):self.data[kind]=text.encode();return True
    def setData_forType_(self,data,kind):self.data[kind]=bytes(data);return True


class MacBoard:
    def __init__(self):self.items=[MacItem({'public.rtf':b'rtf\0bytes','public.png':b'\x89PNG\x00img'})];self.version=1
    def changeCount(self):return self.version
    def pasteboardItems(self):return self.items
    def clearContents(self):self.items=[];self.version+=1
    def writeObjects_(self,items):self.items=items;self.version+=1;return True
    def stringForType_(self,kind):
        value=self.items[0].data.get(kind) if self.items else None
        return value.decode() if value else None
    def setString_forType_(self,text,kind):self.items=[MacItem({kind:text.encode()})];self.version+=1;return True


def mac_adapter(board):
    kit=SimpleNamespace(NSPasteboard=SimpleNamespace(generalPasteboard=lambda:board),
        NSPasteboardItem=MacItem,NSPasteboardTypeString='public.utf8-plain-text')
    return MacClipboardAdapter(kit)


def test_mac_preserves_multiple_rich_image_formats_and_detects_new_owner(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules,'Foundation',SimpleNamespace(NSData=SimpleNamespace(dataWithBytes_length_=lambda data,size:data)))
    board=MacBoard();adapter=mac_adapter(board);memory=ClipboardRestoration()
    original=dict(board.items[0].data)
    memory.write(adapter,'hello')
    assert memory.restore(insertion_confirmed=True).restored
    assert board.items[0].data==original
    memory.write(adapter,'hello')
    board.setString_forType_('new copy','public.utf8-plain-text')
    assert not memory.restore(insertion_confirmed=True).restored
    assert board.stringForType_('public.utf8-plain-text')=='new copy'


def test_mac_snapshot_limit_does_not_disable_normal_copy():
    board=MacBoard();board.items=[MacItem({'public.png':b'x'*(MAX_SNAPSHOT_BYTES+1)})]
    memory=ClipboardRestoration()
    result=memory.write(mac_adapter(board),'hello')
    assert result.copied and not memory.pending and 'limit' in result.unavailable_reason
    assert 'limit' in memory.status()['message']
    assert board.stringForType_('public.utf8-plain-text')=='hello'


def test_mac_change_during_snapshot_discards_stale_restoration():
    board=MacBoard();item=board.items[0];read=item.dataForType_
    def concurrent_change(kind):
        board.version+=1
        return read(kind)
    item.dataForType_=concurrent_change
    memory=ClipboardRestoration();result=memory.write(mac_adapter(board),'dictation')
    assert result.copied and not memory.pending
    assert 'changed' in result.unavailable_reason.lower()


def test_mac_partial_restore_failure_keeps_dictation_available(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules,'Foundation',SimpleNamespace(NSData=SimpleNamespace(dataWithBytes_length_=lambda data,size:data)))
    board=MacBoard();memory=ClipboardRestoration();memory.write(mac_adapter(board),'dictation')
    board.writeObjects_=lambda _:False
    result=memory.restore(insertion_confirmed=True)
    assert not result.restored and not result.pending
    assert board.stringForType_('public.utf8-plain-text')=='dictation'


class WinNative:
    def __init__(self):self.memory={};self.clip={};self.sequence=1;self.next=10;self.freed=[];self.open=False;self.windows=0
    def CreateWindowExW(self,*args):self.windows+=1;return 900
    def DestroyWindow(self,window):assert window==900;self.windows-=1;return True
    def GlobalAlloc(self,flags,size):
        self.next+=1;self.memory[self.next]=ctypes.create_string_buffer(size);return self.next
    def GlobalLock(self,handle):return ctypes.addressof(self.memory[handle])
    def GlobalUnlock(self,handle):return True
    def GlobalSize(self,handle):return ctypes.sizeof(self.memory[handle])
    def GlobalFree(self,handle):self.freed.append(handle);self.memory.pop(handle,None)
    def OpenClipboard(self,hwnd):
        assert hwnd==900
        if self.open:return False
        self.open=True;return True
    def CloseClipboard(self):self.open=False
    def EmptyClipboard(self):self.clip={};self.sequence+=1;return True
    def SetClipboardData(self,kind,handle):self.clip[kind]=handle;self.sequence+=1;return handle
    def GetClipboardData(self,kind):return self.clip.get(kind)
    def EnumClipboardFormats(self,previous):
        keys=list(self.clip)
        if not previous:return keys[0] if keys else 0
        index=keys.index(previous)+1
        return keys[index] if index<len(keys) else 0
    def RegisterClipboardFormatW(self,name):return 0xC002
    def GetClipboardSequenceNumber(self):return self.sequence
    def set_bytes(self,kind,data):
        handle=self.GlobalAlloc(2,len(data));ctypes.memmove(self.GlobalLock(handle),data,len(data));self.SetClipboardData(kind,handle)
    def bytes(self,kind):
        handle=self.clip[kind];return ctypes.string_at(self.GlobalLock(handle),self.GlobalSize(handle))


def test_windows_retains_unicode_dib_and_registered_rtf_bytes():
    native=WinNative();native.set_bytes(13,'original\0'.encode('utf-16-le'))
    native.set_bytes(8,b'DIB\0pixeldata');native.set_bytes(0xC001,b'{\\rtf1 rich}')
    original={kind:native.bytes(kind) for kind in native.clip}
    adapter=WindowsClipboardAdapter(native,native,ctypes,threading.Lock());memory=ClipboardRestoration()
    memory.write(adapter,'dictated')
    assert memory.restore(insertion_confirmed=True).restored
    assert {kind:native.bytes(kind) for kind in native.clip}==original
    assert not native.open
    assert native.windows==0


def test_windows_sequence_prevents_restoring_over_new_clipboard():
    native=WinNative();native.set_bytes(13,'original\0'.encode('utf-16-le'))
    adapter=WindowsClipboardAdapter(native,native,ctypes,threading.Lock());memory=ClipboardRestoration()
    memory.write(adapter,'dictated')
    native.EmptyClipboard();native.set_bytes(13,'new copy\0'.encode('utf-16-le'))
    assert not memory.restore(insertion_confirmed=True).restored
    assert native.bytes(13)=='new copy\0'.encode('utf-16-le')


def test_windows_plain_copy_uses_nonnull_owner_and_releases_window():
    native=WinNative();adapter=WindowsClipboardAdapter(native,native,ctypes,threading.Lock())
    assert adapter.copy_text('plain')
    assert native.bytes(13)=='plain\0'.encode('utf-16-le')
    assert native.windows==0 and not native.open


def test_windows_unsupported_gdi_format_does_not_claim_preservation():
    native=WinNative();native.set_bytes(14,b'metafile-handle')
    memory=ClipboardRestoration()
    result=memory.write(WindowsClipboardAdapter(native,native,ctypes,threading.Lock()),'dictated')
    assert result.copied and not memory.pending and 'unsupported' in result.unavailable_reason
    assert native.bytes(13)=='dictated\0'.encode('utf-16-le')


def test_transient_restore_error_retains_snapshot_for_explicit_retry():
    adapter=FakeAdapter();memory=ClipboardRestoration();memory.write(adapter,'text')
    real=adapter.restore_if_owned
    adapter.restore_if_owned=lambda *_:(_ for _ in ()).throw(OSError('busy'))
    assert memory.restore(insertion_confirmed=True).pending
    adapter.restore_if_owned=real
    assert memory.restore(insertion_confirmed=True).restored


def test_snapshot_failure_uses_normal_clipboard_fallback_and_no_restore():
    memory=ClipboardRestoration();calls=[]
    def no_adapter():raise OSError('native snapshot unavailable')
    def copy(text):calls.append(text);return True
    def insert(text,**options):
        assert options['_copy'](text)
        return InsertionOutcome(False,True,'event-failed')
    outcome=insert_with_restoration(insert,copy,memory,no_adapter,'recoverable',0,None,None,True)
    assert outcome.copied and not outcome.clipboard_restore_pending and outcome.clipboard_restore_unavailable
    assert calls==['recoverable']


def test_linux_wayland_declines_restore_without_reading_old_clipboard(monkeypatch):
    from fixoflow.platform import linux
    copied=[]
    monkeypatch.setenv('XDG_SESSION_TYPE','wayland')
    monkeypatch.setattr(linux,'copy_to_clipboard',lambda text:copied.append(text) or True)
    outcome=linux.insert_text_at_cursor('manual recovery',restore_clipboard=True)
    assert outcome.copied and not outcome.inserted and not outcome.clipboard_restore_pending
    assert outcome.clipboard_restore_unavailable and copied==['manual recovery']
    assert not linux.restore_previous_clipboard(insertion_confirmed=True)['restored']
