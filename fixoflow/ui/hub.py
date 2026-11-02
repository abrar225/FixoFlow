"""
Fixoflow Hub Application Window
Standard macOS application window providing the Dashboard, History explorer,
Adaptive Dictionary management, and Mode settings.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import AppKit
from Foundation import NSObject, NSOperationQueue, NSPoint, NSRect, NSSize, NSURL, NSJSONSerialization
import WebKit

from fixoflow.ui.controller import HubController
from fixoflow.config import FixoflowConfig
from fixoflow.storage.db import FixoflowDB

logger = logging.getLogger("fixoflow.ui.hub")


class HubBridgeHandler(NSObject):
    hub_manager = None

    def userContentController_didReceiveScriptMessage_(self, userContentController, message):
        try:
            raw = message.body()
            # WKWebView returns nested NSDictionary/NSArray values, not Python
            # dict/list instances. Normalize the JSON protocol once at entry.
            if not NSJSONSerialization.isValidJSONObject_(raw):
                return
            data, error = NSJSONSerialization.dataWithJSONObject_options_error_(raw, 0, None)
            if error is not None or data is None:
                return
            body = json.loads(bytes(data).decode('utf-8'))
            action = body.get('action') if isinstance(body, dict) else None
            if self.hub_manager is not None and isinstance(action, str):
                self.hub_manager.handle_action(action, body)
        except Exception as e:
            logger.error("Error processing JS message: %s", e)


class HubManager(HubController):
    _instance: Optional[HubManager] = None

    def __init__(self):
        self._window: Optional[AppKit.NSWindow] = None
        self._webview: Optional[WebKit.WKWebView] = None
        self.db = FixoflowDB.get_instance()
        self.config = FixoflowConfig.load()
        self.on_config_change = None
        self.on_enable_shortcut = None
        self.on_show_overlay = None
        self.on_control_status = None
        self.on_restart = None
        self.on_shortcut_capture = None
        self.on_cancel_capture = None
        self.on_primary_mouse_capture = None
        self.on_update_check = None
        self.on_update_status = None
        self.on_open_release = None
        self._init_window()

    @classmethod
    def get_instance(cls) -> HubManager:
        if cls._instance is None:
            cls._instance = HubManager()
        return cls._instance

    def _init_window(self):
        try:
            width = 1040.0
            height = 740.0

            screen = AppKit.NSScreen.mainScreen()
            if screen is not None:
                screen_frame = screen.visibleFrame()
                x = screen_frame.origin.x + (screen_frame.size.width - width) / 2.0
                y = screen_frame.origin.y + (screen_frame.size.height - height) / 2.0
            else:
                x, y = 200.0, 200.0

            frame = NSRect(NSPoint(x, y), NSSize(width, height))
            style_mask = (
                AppKit.NSWindowStyleMaskTitled
                | AppKit.NSWindowStyleMaskClosable
                | AppKit.NSWindowStyleMaskMiniaturizable
                | AppKit.NSWindowStyleMaskResizable
            )

            self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                frame,
                style_mask,
                AppKit.NSBackingStoreBuffered,
                False,
            )
            self._window.setTitle_("Fixo Flow")
            self._window.setMinSize_(NSSize(820.0, 620.0))
            self._window.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameAqua))
            # Keep the retained hub reusable after the red close button. The
            # menu/Dock and second-instance notification reopen this same window.
            self._window.setReleasedWhenClosed_(False)
            self._window.setTitlebarAppearsTransparent_(True)
            self._window.setBackgroundColor_(AppKit.NSColor.colorWithRed_green_blue_alpha_(0.933, 0.914, 0.984, 1.0))

            # Configure WebKit View
            config = WebKit.WKWebViewConfiguration.alloc().init()
            bridge = HubBridgeHandler.alloc().init()
            bridge.hub_manager = self
            config.userContentController().addScriptMessageHandler_name_(bridge, "fixoflow")

            self._webview = WebKit.WKWebView.alloc().initWithFrame_configuration_(
                NSRect(NSPoint(0, 0), NSSize(width, height)),
                config,
            )
            self._webview.setValue_forKey_(False, "drawsBackground")

            # Load local hub.html
            html_path = Path(__file__).parent / "hub.html"
            file_url = NSURL.fileURLWithPath_(str(html_path.resolve()))
            self._webview.loadFileURL_allowingReadAccessToURL_(file_url, file_url.URLByDeletingLastPathComponent())

            self._window.setContentView_(self._webview)
            logger.info("Fixoflow Hub window initialized.")
        except Exception as e:
            logger.error("Failed to initialize Hub window: %s", e)

    def _eval_js(self, script: str):
        if self._webview is not None:
            self._webview.evaluateJavaScript_completionHandler_(script, None)

    def show(self):
        def _action():
            if self._window is not None:
                self._window.makeKeyAndOrderFront_(None)
                AppKit.NSApp.activateIgnoringOtherApps_(True)
        NSOperationQueue.mainQueue().addOperationWithBlock_(_action)

    def hide(self):
        def _action():
            if self._window is not None:
                self._window.orderOut_(None)
        NSOperationQueue.mainQueue().addOperationWithBlock_(_action)

    def toggle(self):
        def _action():
            if self._window is not None:
                if self._window.isVisible():
                    self._window.orderOut_(None)
                else:
                    self._window.makeKeyAndOrderFront_(None)
                    AppKit.NSApp.activateIgnoringOtherApps_(True)
        NSOperationQueue.mainQueue().addOperationWithBlock_(_action)
