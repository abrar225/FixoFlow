"""Bounded X11 CLIPBOARD owner. Imported only for opted-in Linux preservation.

No xclip subprocess is used for snapshots. A single daemon thread owns its X
connection/window and answers selection requests; manual restore only changes
what that same owner serves and never reacquires a selection lost to another app.
Large/INCR or unknown representations decline preservation without dropping text.
"""
import queue
import select
import threading
import time

from fixoflow.clipboard import ClipboardWrite

X11_MAX_BYTES = 48 * 1024
SUPPORTED_TARGETS = {'UTF8_STRING','STRING','TEXT','text/plain','text/plain;charset=utf-8',
                     'text/html','text/rtf','application/rtf','image/png','image/jpeg','image/bmp'}
PROTOCOL_TARGETS = {'TARGETS','MULTIPLE','TIMESTAMP','SAVE_TARGETS'}


class X11ClipboardAdapter:
    def __init__(self, server_factory=None):
        self.server_factory = server_factory or X11SelectionServer

    def capture_and_write(self, text, maximum, previous=None):
        server = self.server_factory(text,min(maximum,X11_MAX_BYTES))
        server.previous = previous
        server.start()
        snapshot=server.snapshot
        server.snapshot=None  # only the bounded restoration policy retains old data
        return ClipboardWrite(True,snapshot,server,server.unavailable_reason)

    def restore_if_owned(self, snapshot, token):
        return token.restore(snapshot)


class X11SelectionServer:
    def __init__(self, text, maximum):
        self.text = text
        self.maximum = maximum
        self.snapshot = None
        self.previous = None
        self.unavailable_reason = ''
        self._ready = threading.Event()
        self._commands = queue.Queue(maxsize=1)
        self._thread = None
        self._error = None
        self._formats = {}
        self._closed = False

    def start(self):
        if len(self.text.encode('utf-8')) > self.maximum:
            raise ValueError('Dictation exceeds the bounded native X11 clipboard transfer limit.')
        self._thread = threading.Thread(target=self._run,name='FixoFlow-X11-clipboard',daemon=True)
        self._thread.start()
        if not self._ready.wait(4):
            self._closed = True
            raise RuntimeError('X11 clipboard did not become ready.')
        if self._error:
            raise RuntimeError(self._error)

    def restore(self, snapshot):
        if self._closed or self._thread is None or not self._thread.is_alive():
            return False,'Clipboard changed; newer clipboard content was preserved.'
        done = threading.Event()
        result = []
        self._commands.put((snapshot,done,result),timeout=.1)
        if not done.wait(2):
            raise RuntimeError('X11 clipboard restoration timed out.')
        return result[0]

    def _owner(self):
        owner = self.display.get_selection_owner(self.selection)
        return int(owner.id) if owner else 0

    def _read_target(self, target, deadline):
        from Xlib import X
        prop_atom = self.display.intern_atom('FixoFlowClipboardRead')
        self.window.delete_property(prop_atom)
        self.window.convert_selection(self.selection,self.display.intern_atom(target),prop_atom,X.CurrentTime)
        self.display.flush()
        while time.monotonic() < deadline:
            if not self.display.pending_events():
                select.select([self.display.fileno()],[],[],min(.05,max(0,deadline-time.monotonic())))
                continue
            event = self.display.next_event()
            if event.type != X.SelectionNotify:
                continue
            if not event.property:
                raise ValueError('A previous clipboard representation is unavailable.')
            prop = self.window.get_property(prop_atom,X.AnyPropertyType,0,(self.maximum+3)//4)
            if prop is None or prop.bytes_after or self.display.get_atom_name(prop.property_type)=='INCR':
                raise ValueError('Previous clipboard requires a large/INCR transfer, which is not preserved.')
            return prop
        raise ValueError('Previous clipboard owner did not respond within two seconds.')

    def _capture(self):
        old_owner = self._owner()
        if not old_owner:
            return {},old_owner
        deadline = time.monotonic()+2
        target_property = self._read_target('TARGETS',deadline)
        if target_property.format != 32 or len(target_property.value)>128:
            raise ValueError('Previous clipboard target list is unsupported.')
        names = [self.display.get_atom_name(int(atom)) for atom in target_property.value]
        unknown = set(names)-SUPPORTED_TARGETS-PROTOCOL_TARGETS
        if unknown:
            raise ValueError('Previous clipboard includes representations that cannot be restored safely.')
        saved = {}
        total = 0
        for name in names:
            if name in PROTOCOL_TARGETS:
                continue
            prop = self._read_target(name,deadline)
            if prop.format != 8:
                raise ValueError('Previous clipboard representation is not a supported byte format.')
            data = bytes(prop.value)
            total += len(data)
            if total > self.maximum:
                raise ValueError('Previous clipboard exceeds the 48 KiB native X11 preservation limit.')
            saved[name] = (self.display.get_atom_name(prop.property_type),data)
        if self._owner()!=old_owner:
            raise ValueError('Clipboard changed while reading its previous representations.')
        return saved,old_owner

    def _reply(self, event):
        from Xlib import X, Xatom, protocol
        target_name = self.display.get_atom_name(event.target)
        property_atom = event.property or event.target
        if target_name=='TARGETS':
            atoms=[self.display.intern_atom(name) for name in ['TARGETS',*self._formats]]
            event.requestor.change_property(property_atom,Xatom.ATOM,32,atoms)
        elif target_name in self._formats:
            kind,data=self._formats[target_name]
            event.requestor.change_property(property_atom,self.display.intern_atom(kind),8,data)
        else:
            property_atom=X.NONE
        notification=protocol.event.SelectionNotify(time=event.time,requestor=event.requestor,
            selection=event.selection,target=event.target,property=property_atom)
        event.requestor.send_event(notification,propagate=False)
        self.display.flush()

    def _run(self):
        display = None
        try:
            from Xlib import X
            from Xlib.display import Display
            display = self.display = Display()
            self.selection=display.intern_atom('CLIPBOARD')
            self.window=display.screen().root.create_window(0,0,1,1,0,X.CopyFromParent,
                                                           event_mask=X.PropertyChangeMask)
            old_owner=self._owner()
            try:
                if self.previous is not None and getattr(self.previous[1],'window',None) is not None and old_owner==self.previous[1].window.id:
                    self.snapshot=self.previous[0]
                else:
                    self.snapshot,old_owner=self._capture()
            except Exception as error:
                self.snapshot=None
                self.unavailable_reason=str(error)
            self.previous=None
            utf8=self.text.encode('utf-8')
            self._formats={'UTF8_STRING':('UTF8_STRING',utf8),'TEXT':('UTF8_STRING',utf8),
                           'text/plain;charset=utf-8':('UTF8_STRING',utf8),
                           'text/plain':('UTF8_STRING',utf8),'STRING':('STRING',self.text.encode('latin-1','replace'))}
            if self._closed:
                raise RuntimeError('X11 clipboard startup was cancelled.')
            # Hold the server only for the final owner comparison/acquisition,
            # never while asking the previous owner to render its data.
            display.grab_server()
            try:
                if self._closed:
                    raise RuntimeError('X11 clipboard startup was cancelled.')
                if self._owner()!=old_owner:
                    self.snapshot=None
                    self.unavailable_reason='Clipboard changed before insertion; older snapshot discarded.'
                self.window.set_selection_owner(self.selection,X.CurrentTime)
                display.sync()
                if self._owner()!=self.window.id:
                    raise RuntimeError('X11 clipboard ownership could not be acquired.')
            finally:
                display.ungrab_server();display.flush()
            self._ready.set()
            while not self._closed:
                try:
                    snapshot,done,result=self._commands.get_nowait()
                except queue.Empty:
                    pass
                else:
                    # Do not call set_selection_owner here. If another client
                    # wins after this check, only our unserved bytes change.
                    if self._owner()!=self.window.id:
                        result.append((False,'Clipboard changed; newer clipboard content was preserved.'))
                    else:
                        self._formats=snapshot
                        result.append((True,'Previous clipboard restored.'))
                    done.set()
                if not display.pending_events():
                    select.select([display.fileno()],[],[],.05)
                    continue
                event=display.next_event()
                if event.type==X.SelectionClear:
                    self._closed=True
                elif event.type==X.SelectionRequest:
                    try:self._reply(event)
                    except Exception:pass  # a disappearing requestor must not kill the owner
        except Exception:
            self._error='Native X11 clipboard is unavailable.'
        finally:
            self._closed=True
            self._ready.set()
            if display is not None:
                try:self.window.destroy();display.flush()
                except Exception:pass
                display.close()
