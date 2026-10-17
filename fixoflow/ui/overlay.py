"""A persistent, nonactivating dictation control backed by local WebKit."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import AppKit
from Foundation import NSObject, NSOperationQueue, NSPoint, NSRect, NSSize, NSURL, NSTimer
import WebKit

from fixoflow.controls import shortcut_label

logger = logging.getLogger(__name__)


class DictationPanel(AppKit.NSPanel):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


class ControlWebView(WebKit.WKWebView):
    def acceptsFirstMouse_(self, event):
        return True


class OverlayBridge(NSObject):
    manager = None

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        body = message.body()
        if self.manager is not None and hasattr(body, 'get'):
            self.manager.handle_action(body.get('action'))


class OverlayManager:
    _instance = None

    def __init__(self):
        self._panel = None
        self._webview = None
        self._is_visible = False
        self._ready = False
        self._state = 'idle'
        self._message = 'Click to dictate'
        self._shortcut = '⌃ Space'
        self._always_show = True
        self._explicit_reveal = False
        self._started_at = None
        self._reset_timer = None
        self.on_toggle = None
        self.on_cancel = None
        self.on_open_hub = None
        self._init_window()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_window(self):
        width, height = 320.0, 72.0
        screen = AppKit.NSScreen.mainScreen()
        frame = screen.visibleFrame() if screen else NSRect(NSPoint(0, 0), NSSize(1440, 900))
        x = frame.origin.x + (frame.size.width - width) / 2
        y = frame.origin.y + 12
        rect = NSRect(NSPoint(x, y), NSSize(width, height))
        self._panel = DictationPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False)
        self._panel.setTitle_('Fixoflow floating control')
        self._panel.setReleasedWhenClosed_(False)
        self._panel.setFloatingPanel_(True)
        self._panel.setBecomesKeyOnlyIfNeeded_(True)
        self._panel.setHidesOnDeactivate_(False)
        self._panel.setLevel_(AppKit.NSStatusWindowLevel)
        self._panel.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                           AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        self._panel.setOpaque_(False)
        self._panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        self._panel.setHasShadow_(False)
        self._panel.setIgnoresMouseEvents_(False)
        config = WebKit.WKWebViewConfiguration.alloc().init()
        self._bridge = OverlayBridge.alloc().init()
        self._bridge.manager = self
        config.userContentController().addScriptMessageHandler_name_(self._bridge, 'fixoflow')
        self._webview = ControlWebView.alloc().initWithFrame_configuration_(
            NSRect(NSPoint(0, 0), NSSize(width, height)), config)
        self._webview.setValue_forKey_(False, 'drawsBackground')
        url = NSURL.fileURLWithPath_(str(Path(__file__).with_name('overlay.html').resolve()))
        self._webview.loadFileURL_allowingReadAccessToURL_(url, url.URLByDeletingLastPathComponent())
        self._panel.setContentView_(self._webview)

    def _dispatch_main(self, action):
        NSOperationQueue.mainQueue().addOperationWithBlock_(action)

    def configure(self, config, on_toggle=None, on_cancel=None, on_open_hub=None):
        self._always_show = config.always_show_overlay
        self._explicit_reveal = False
        self._shortcut = shortcut_label(config.hotkey)
        if on_toggle is not None:
            self.on_toggle = on_toggle
        if on_cancel is not None:
            self.on_cancel = on_cancel
        if on_open_hub is not None:
            self.on_open_hub = on_open_hub
        self._dispatch_main(self._render)

    def handle_action(self, action):
        if action == 'ready':
            self._ready = True
            self._render()
        elif action == 'toggle' and self.on_toggle:
            self.on_toggle()
        elif action == 'cancel' and self.on_cancel:
            self.on_cancel()
        elif action == 'openHub' and self.on_open_hub:
            self.on_open_hub()

    def _render(self):
        visible = self._always_show or self._explicit_reveal or self._state != 'idle'
        if visible:
            self._panel.orderFrontRegardless()
        else:
            self._panel.orderOut_(None)
        self._is_visible = visible
        if self._ready:
            snapshot = {'state': self._state, 'message': self._message, 'shortcut': self._shortcut,
                        'elapsed': time.monotonic() - self._started_at if self._started_at else 0}
            self._webview.evaluateJavaScript_completionHandler_(f'updateControl({json.dumps(snapshot)});', None)

    def _set_state(self, state, message, reset_after=None):
        def apply():
            if self._reset_timer is not None:
                self._reset_timer.invalidate()
                self._reset_timer = None
            if state == 'listening' and self._state != 'listening':
                self._started_at = time.monotonic()
            self._state, self._message = state, message
            self._render()
            if reset_after:
                self._reset_timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
                    reset_after, False, lambda timer: self.show_idle())
        self._dispatch_main(apply)

    def show_idle(self, message='Click to dictate'):
        self._set_state('idle', message)

    def reveal(self):
        def apply():
            self._explicit_reveal = True
            self._render()
        self._dispatch_main(apply)

    def show_listening(self, message='Listening…'):
        self._set_state('listening', message)

    def show_processing(self, message='Transcribing…'):
        self._set_state('processing', message)

    def show_success(self, message='Saved'):
        self._set_state('success', message, reset_after=2.5)

    def show_error(self, message='Open Settings'):
        self._set_state('error', message, reset_after=5)

    def update_audio_level(self, level):
        def apply():
            if self._ready and self._state == 'listening':
                self._webview.evaluateJavaScript_completionHandler_(f'setAudioLevel({max(0.0, min(float(level), 1.0))});', None)
        self._dispatch_main(apply)

    def hide(self):
        def apply():
            self._explicit_reveal = False
            if self._reset_timer is not None:
                self._reset_timer.invalidate()
            self._panel.orderOut_(None)
            self._is_visible = False
        self._dispatch_main(apply)
