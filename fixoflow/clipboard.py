"""Bounded, explicit previous-clipboard restoration with native ownership checks.

Synthetic paste has no consumption acknowledgement. A timer alone never restores
the clipboard: the user must confirm insertion (or a future verified recipient
integration may supply that signal). No clipboard data is persisted or logged.
"""
from dataclasses import dataclass
import threading


MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class ClipboardWrite:
    copied: bool
    snapshot: object = None
    token: object = None
    unavailable_reason: str = ''


@dataclass(frozen=True)
class ClipboardRestore:
    restored: bool
    reason: str
    pending: bool = False


class ClipboardRestoration:
    """One prior snapshot per process. All native access is injected for tests."""
    def __init__(self):
        self._lock = threading.RLock()
        self._pending = None
        self._message = 'No previous clipboard is waiting to be restored.'

    @property
    def pending(self):
        with self._lock:
            return self._pending is not None

    def write(self, adapter, text):
        with self._lock:
            prior = self._pending
            self._pending = None
            previous = (prior[1],prior[2]) if prior is not None and type(prior[0]) is type(adapter) else None
            result = adapter.capture_and_write(text, MAX_SNAPSHOT_BYTES, previous=previous)
            self._message = result.unavailable_reason or 'No previous clipboard is waiting to be restored.'
            if result.copied and result.snapshot is not None and result.token is not None:
                self._pending = (adapter, result.snapshot, result.token)
            return result

    def restore(self, *, insertion_confirmed=False):
        with self._lock:
            if self._pending is None:
                return ClipboardRestore(False, 'No previous clipboard is available.')
            if not insertion_confirmed:
                return ClipboardRestore(False, 'Confirm your words have been inserted before restoring the previous clipboard.', True)
            adapter, snapshot, token = self._pending
            try:
                restored, reason = adapter.restore_if_owned(snapshot, token)
            except Exception:
                return ClipboardRestore(False, 'Clipboard is unavailable. Retry without copying anything else.', True)
            # Changed ownership is terminal: never overwrite a newer clipboard.
            self._pending = None
            self._message = reason
            return ClipboardRestore(restored, reason)

    def discard(self):
        with self._lock:
            self._pending = None
            self._message = 'No previous clipboard is waiting to be restored.'

    def status(self):
        pending = self.pending
        return {'pending':pending, 'message':(
            'Previous clipboard is held only in memory. Confirm your words have been inserted before restoring it.'
            if pending else self._message)}


def restore_status(restoration, insertion_confirmed=False):
    result = restoration.restore(insertion_confirmed=insertion_confirmed)
    return {'restored':result.restored, 'pending':result.pending, 'message':result.reason}


def insert_with_restoration(operation, copier, restoration, adapter_factory,
                            text, delay_sec, expected_target, cancelled, enabled):
    """Keep existing target/cancel checks; replace only the clipboard-write step."""
    from dataclasses import replace
    if not enabled:
        restoration.discard()
        return operation(text,delay_sec=delay_sec,expected_target=expected_target,cancelled=cancelled)
    written = copy_with_restoration(copier,restoration,adapter_factory,text)
    outcome = operation(text,delay_sec=delay_sec,expected_target=expected_target,cancelled=cancelled,
                        _copy=lambda _:written.copied)
    return replace(outcome,clipboard_restore_pending=restoration.pending,
                   clipboard_restore_unavailable=written.unavailable_reason)


def copy_with_restoration(copier, restoration, adapter_factory, text):
    try:
        return restoration.write(adapter_factory(),text)
    except Exception:
        # If snapshot/native marker support fails, normal dictation still works.
        restoration.discard()
        return ClipboardWrite(copier(text),unavailable_reason='Previous clipboard could not be preserved safely.')


class MacClipboardAdapter:
    """NSPasteboard item/type byte snapshots; only an injected pasteboard is used."""
    marker_type = 'com.fixoflow.clipboard-owner'

    def __init__(self, appkit):
        self.appkit = appkit

    def capture_and_write(self, text, maximum, previous=None):
        import uuid
        pasteboard = self.appkit.NSPasteboard.generalPasteboard()
        before = int(pasteboard.changeCount())
        snapshot = []
        size = 0
        reason = ''
        try:
            keep_previous = previous is not None and self._owns(pasteboard,previous[1])
            source_items = [] if keep_previous else list(pasteboard.pasteboardItems() or [])
            if keep_previous:
                snapshot = previous[0]
            if len(source_items) > 32:
                raise ValueError('Too many previous clipboard items to preserve safely.')
            format_count = 0
            for item in source_items:
                saved = []
                for kind in item.types():
                    format_count += 1
                    if format_count > 128:
                        raise ValueError('Too many previous clipboard formats to preserve safely.')
                    data = item.dataForType_(kind)
                    if data is None:
                        raise ValueError('A previous clipboard format could not be read.')
                    data_size = int(data.length()) if hasattr(data,'length') else len(data)
                    if size + data_size > maximum:
                        raise ValueError('Previous clipboard exceeds the 8 MB restoration limit.')
                    value = bytes(data)
                    size += len(value)
                    if size > maximum:
                        raise ValueError('Previous clipboard exceeds the 8 MB restoration limit.')
                    saved.append((str(kind), value))
                snapshot.append(saved)
            if int(pasteboard.changeCount()) != before:
                raise ValueError('Clipboard changed while taking its snapshot.')
        except Exception as error:
            snapshot = None
            reason = str(error)
        owner = uuid.uuid4().hex
        # NS item writes package text + owner marker as a single writeObjects call.
        item = self.appkit.NSPasteboardItem.alloc().init()
        if not item.setString_forType_(text, self.appkit.NSPasteboardTypeString):
            return ClipboardWrite(False,unavailable_reason='Clipboard text could not be prepared.')
        if not item.setString_forType_(owner, self.marker_type):
            snapshot = None
            reason = 'Clipboard ownership marker could not be prepared.'
        if int(pasteboard.changeCount()) != before:
            snapshot = None
            reason = 'Clipboard changed before insertion; the older snapshot was discarded.'
        pasteboard.clearContents()
        copied = bool(pasteboard.writeObjects_([item]))
        token = (int(pasteboard.changeCount()), owner, text) if copied else None
        return ClipboardWrite(copied, snapshot, token, reason)

    def _owns(self, pasteboard, token):
        version,owner,_ = token
        return int(pasteboard.changeCount()) == version and pasteboard.stringForType_(self.marker_type) == owner

    def restore_if_owned(self, snapshot, token):
        pasteboard = self.appkit.NSPasteboard.generalPasteboard()
        version, owner, text = token
        if not self._owns(pasteboard,token):
            return False, 'Clipboard changed; newer clipboard content was preserved.'
        items = []
        # Materialize all objects before clearing the live pasteboard.
        from Foundation import NSData
        for saved in snapshot:
            item = self.appkit.NSPasteboardItem.alloc().init()
            for kind, data in saved:
                if not item.setData_forType_(NSData.dataWithBytes_length_(data, len(data)), kind):
                    raise ValueError('Could not reconstruct a clipboard format.')
            items.append(item)
        if int(pasteboard.changeCount()) != version:
            return False, 'Clipboard changed; newer clipboard content was preserved.'
        pasteboard.clearContents()
        if items and not pasteboard.writeObjects_(items):
            # Preserve dictated-text recovery if the platform refuses restoration.
            pasteboard.setString_forType_(text, self.appkit.NSPasteboardTypeString)
            return False, 'Restoration failed; dictated text was kept on the clipboard where possible.'
        return True, 'Previous clipboard restored.'


class WindowsClipboardAdapter:
    """Snapshot HGLOBAL-backed text, DIB images and registered rich formats.

    Unsupported private/GDI/metafile formats disable restoration rather than
    replacing the previous object with a partial text-only representation.
    """
    def __init__(self, user32, kernel32, ctypes, lock):
        self.u, self.k, self.c, self.lock = user32, kernel32, ctypes, lock

    def _open(self):
        import time
        # EmptyClipboard with a NULL owner makes SetClipboardData fail on Win32.
        # A short-lived message-only STATIC window owns fully materialized data.
        window = self.u.CreateWindowExW(0,'STATIC','FixoFlow clipboard',0,0,0,0,0,-3,None,None,None)
        if not window:
            raise RuntimeError('Clipboard owner window could not be created.')
        for _ in range(10):
            if self.u.OpenClipboard(window):
                return window
            time.sleep(.01)
        self.u.DestroyWindow(window)
        raise RuntimeError('Clipboard is busy.')

    def _close(self, window):
        try:
            self.u.CloseClipboard()
        finally:
            self.u.DestroyWindow(window)

    def _bytes(self, kind):
        handle = self.u.GetClipboardData(kind)
        if not handle:
            raise ValueError('A previous clipboard format could not be read.')
        size = self.k.GlobalSize(handle)
        if not size or size > MAX_SNAPSHOT_BYTES:
            raise ValueError('Previous clipboard format is unsupported or exceeds the 8 MB limit.')
        pointer = self.k.GlobalLock(handle)
        if not pointer:
            raise ValueError('A previous clipboard format could not be locked.')
        try:
            return self.c.string_at(pointer, size)
        finally:
            self.k.GlobalUnlock(handle)

    def _allocate(self, data):
        handle = self.k.GlobalAlloc(0x0002, len(data))
        if not handle:
            raise MemoryError('Clipboard allocation failed.')
        pointer = self.k.GlobalLock(handle)
        if not pointer:
            self.k.GlobalFree(handle)
            raise MemoryError('Clipboard allocation failed.')
        try:
            self.c.memmove(pointer, data, len(data))
        finally:
            self.k.GlobalUnlock(handle)
        return handle

    def _set(self, kind, data):
        handle = self._allocate(data)
        if not self.u.SetClipboardData(kind, handle):
            self.k.GlobalFree(handle)
            raise RuntimeError('Clipboard write failed.')

    def capture_and_write(self, text, maximum, previous=None):
        import uuid
        with self.lock:
            window = self._open()
            try:
                snapshot = []
                reason = ''
                try:
                    keep_previous=previous is not None and self._owns_open(previous[1])
                    if keep_previous:
                        snapshot=previous[0]
                    formats = []
                    kind = 0
                    while not keep_previous:
                        if hasattr(self.c,'set_last_error'):
                            self.c.set_last_error(0)
                        kind = self.u.EnumClipboardFormats(kind)
                        if not kind:
                            if hasattr(self.c,'get_last_error') and self.c.get_last_error():
                                raise ValueError('Previous clipboard formats could not be enumerated.')
                            break
                        formats.append(kind)
                        if len(formats) > 128:
                            raise ValueError('Too many previous clipboard formats to preserve safely.')
                    size = 0
                    for kind in formats:
                        # Windows synthesizes CF_BITMAP/PALETTE from DIB bytes.
                        if kind in (2,9) and (8 in formats or 17 in formats):
                            continue
                        if kind not in (1,7,8,13,15,16,17) and kind < 0xC000:
                            raise ValueError('A previous clipboard format is unsupported for restoration.')
                        data = self._bytes(kind)
                        size += len(data)
                        if size > maximum:
                            raise ValueError('Previous clipboard exceeds the 8 MB restoration limit.')
                        snapshot.append((kind,data))
                except Exception as error:
                    snapshot = None
                    reason = str(error)
                marker = self.u.RegisterClipboardFormatW('FixoFlowClipboardOwner')
                owner = uuid.uuid4().hex.encode('ascii') + b'\0'
                if not self.u.EmptyClipboard():
                    return ClipboardWrite(False, unavailable_reason='Clipboard could not be opened for writing.')
                self._set(13,(text+'\0').encode('utf-16-le'))
                if not marker:
                    return ClipboardWrite(True, unavailable_reason='Clipboard ownership marker is unavailable.')
                self._set(marker,owner)
                sequence = int(self.u.GetClipboardSequenceNumber())
                if sequence == 0:
                    return ClipboardWrite(True, unavailable_reason='Clipboard sequence is unavailable.')
                return ClipboardWrite(True,snapshot,(sequence,marker,owner,text),reason)
            finally:
                self._close(window)

    def _owns_open(self, token):
        sequence,marker,owner,_=token
        return int(self.u.GetClipboardSequenceNumber())==sequence and self._bytes(marker).rstrip(b'\0')==owner.rstrip(b'\0')

    def copy_text(self, text):
        with self.lock:
            window = self._open()
            handle = None
            try:
                handle = self._allocate((text+'\0').encode('utf-16-le'))
                if not self.u.EmptyClipboard() or not self.u.SetClipboardData(13,handle):
                    return False
                handle = None
                return True
            finally:
                if handle:self.k.GlobalFree(handle)
                self._close(window)

    def restore_if_owned(self, snapshot, token):
        sequence, marker, owner, text = token
        with self.lock:
            window = self._open()
            allocated=[]
            try:
                if not self._owns_open(token):
                    return False,'Clipboard changed; newer clipboard content was preserved.'
                # Allocate every object before EmptyClipboard so allocation
                # failures leave the dictated fallback intact.
                for kind,data in snapshot:
                    allocated.append([kind,self._allocate(data)])
                if not self.u.EmptyClipboard():
                    raise RuntimeError('Clipboard is busy.')
                try:
                    for item in allocated:
                        if not self.u.SetClipboardData(item[0],item[1]):
                            raise RuntimeError('Clipboard restoration failed.')
                        item[1]=None  # ownership transferred to Windows
                except Exception:
                    self.u.EmptyClipboard()
                    self._set(13,(text+'\0').encode('utf-16-le'))
                    return False,'Restoration failed; dictated text was kept on the clipboard where possible.'
                return True,'Previous clipboard restored.'
            finally:
                for _,handle in allocated:
                    if handle:self.k.GlobalFree(handle)
                self._close(window)
