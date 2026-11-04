# Optional clipboard preservation

3 November 2026. Source implementation and fake-native verification; public
publisher trust and physical-device clipboard acceptance are separate checks.

## Implemented behavior

The existing `insert_text_at_cursor` on all providers accepts optional
`restore_clipboard=False`. Disabled by default, it keeps the original clipboard-
first delivery checks and does not inspect the previous clipboard. When enabled
on a capable provider, one previous snapshot is held in process memory only.
No clipboard data is written to disk, logs, history or telemetry. Repeated
dictations retain the original pre-Fixo snapshot while the prior Fixo owner/token
still owns the clipboard. If a user copies new content, the next dictation takes
that content as its new baseline. Native capture checks ownership inside its
clipboard operation rather than relying on a separate stale preflight. Shutdown
can discard the pending RAM explicitly.

The provider's `InsertionOutcome` adds `clipboard_restore_pending` and
`clipboard_restore_unavailable`. Existing three-field callers remain compatible.
These are separate from `inserted`, which continues to mean dispatched input,
not verified consumption by the recipient.

Exports from `fixoflow.platform`:

- `clipboard_restore_status()` → `{pending, message}`.
- `restore_previous_clipboard(insertion_confirmed=False)` →
  `{restored, pending, message}`. A caller must supply explicit user confirmation
  that text has been inserted before restore can run.
- `discard_previous_clipboard()` drops pending RAM without touching the clipboard.
- `copy_to_clipboard_preserving(text)` → bool uses the same optional preservation
  policy for clipboard-only recovery/focus-failure/cancellation branches. It does
  not dispatch keyboard input; root calls it only when the preference is enabled.

Root UI integration uses `restore_clipboard` and a **Restore previous clipboard**
button with confirmation. No timer, synthetic keystroke or elapsed delay is
treated as proof that another app consumed the dictated text. Slow recipients
therefore keep the text until a user chooses restoration. This is a deliberately
manual fallback rather than claiming automatic consumption-aware restoration.

If paste dispatch fails, text remains on the clipboard for manual paste and the
snapshot may still be restored after the user confirms doing so. If the user or
another application copied anything in the meantime, restoration is refused and
the newer clipboard is preserved—even if the copied text is identical.

## Platform capability and limits

**macOS:** NS pasteboard item/type data is copied as bytes, retaining multiple
items and rich/image representations where all types can be materialized. The
aggregate cap is 8 MB, with at most 32 items/128 formats. Unsupported/lazy data
or a concurrent change disables preservation but does not disable normal
dictation. An insertion marker plus native `changeCount` protect restoration.
All restoration objects are constructed before clearing the current pasteboard.
macOS does not expose an atomic cross-process compare-and-swap through this API;
the final ownership check minimizes the remaining check/write race, but this
must not be described as a universal race-free or recipient-acknowledged operation.

**Windows:** The clipboard is opened with a non-NULL message-only STATIC window
owner. This also fixes the older plain-copy path, which called `OpenClipboard`
with NULL before `EmptyClipboard`/`SetClipboardData`, a combination Microsoft
documents as invalid. All bytes are materialized (no delayed rendering worker).
The hidden owner window is destroyed after closing the operation; memory ownership
passes to Windows after successful `SetClipboardData`.

Supported snapshots include HGLOBAL-backed text/Unicode, DIB/DIBV5 images, HDROP,
locale and registered rich formats such as RTF/HTML, within the same 8 MB/128-
format limits. Unsupported private/GDI/metafile data disables preservation rather
than silently restoring a text-only approximation. Common image formats can use
Windows' DIB representations; arbitrary native handles are not cloned. Snapshot
restore checks the native sequence and marker while holding the clipboard open,
so external modification cannot interleave with that operation. Objects are
allocated before clearing; partial restore failures attempt to preserve dictated
text. A transient clipboard-open/allocation failure retains memory for explicit
retry while the pending token is still valid.

**Linux X11:** An opted-in native selection-owner thread owns a dedicated window
and serves CLIPBOARD requests. Supported text, HTML, RTF and small PNG/JPEG/BMP
representations are captured through bounded native selection conversion. The
aggregate native-transfer cap is **48 KiB** to remain below ordinary X11 property
request limits without claiming INCR transfer support. Unknown/application-
private targets, INCR, large data and unresponsive owners decline preservation
while normal dictation fallback remains. Snapshots are discarded if selection
ownership changes during capture; native acquisition performs a short server-
grab owner comparison, never holding that grab while asking the prior owner to
render data.

Manual restore checks that our exact owner window still owns CLIPBOARD and changes
only the formats that window serves. It never reacquires a selection lost to
another app, so a concurrent newer copy is not overwritten. This also serves
clipboard data through a persistent thread rather than relying on a short-lived
xclip process. All old snapshot data is owned by the bounded restoration policy;
the server releases its capture reference after handing it off. SelectionClear
ends an obsolete owner loop. X11 clipboard content remains process-served, so
exiting the app can remove its served data if no clipboard manager has saved it;
History remains the recovery path.

**Linux Wayland:** Preservation is explicitly unavailable. The normal wl-copy
path remains; no unsupported snapshot is read and no unconditional wipe/restore
is attempted. Native portal/Wayland preservation remains future work.

Clipboard snapshots represent native data formats, not arbitrary live object
identities or applications' delayed-render behavior. Native acceptance is still
required for document editors, image sources and clipboard managers.

## Verification

`tests/test_clipboard_restore.py` uses only fake pasteboards, fake Win32 functions
and allocated test buffers. It covers rich/image bytes, user copying different
or identical text, pending-snapshot supersession, explicit confirmation, disabled
default, permission/dispatch failures with preserved fallback, oversized or
unsupported formats, transient restore retry and non-NULL Win32 ownership.
Existing Mac delivery tests continue exercising focus/cancel/modifier behavior
with clipboard/keyboard operations mocked. No user's clipboard was read or
modified and no real application received synthetic input during these tests.

`tests/test_clipboard_x11.py` uses fake owner/protocol objects. An additional
`tests/test_clipboard_x11_native.py` only runs when
`FIXOFLOW_TEST_X11_ISOLATED=1` is explicitly supplied on Linux and must be invoked
under a disposable Xvfb server, not a user's desktop display. It verifies served
text, explicit restoration and a newer owner surviving a refused restore. It
was not run on this Mac, where Xvfb/python-xlib are unavailable. This is a native
acceptance gap, not evidence that an X11 test passed.

References:

- [Microsoft OpenClipboard](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-openclipboard)
- [Microsoft clipboard sequence numbers](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getclipboardsequencenumber)
- [Microsoft clipboard formats](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats)
- [Apple changeCount](https://developer.apple.com/documentation/appkit/nspasteboard/changecount)
- [Python Xlib Window API](https://python-xlib.github.io/python-xlib_20.html)

These APIs document ownership/change information, not proof that a target app
accepted dictated text. That distinction is preserved in the implementation.
