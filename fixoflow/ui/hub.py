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
from Foundation import NSObject, NSOperationQueue, NSPoint, NSRect, NSSize, NSURL
import WebKit

from fixoflow.config import FixoflowConfig
from fixoflow.platform.macos import permission_snapshot, request_all_permissions
from fixoflow.storage.db import FixoflowDB

logger = logging.getLogger("fixoflow.ui.hub")


class HubBridgeHandler(NSObject):
    hub_manager = None

    def userContentController_didReceiveScriptMessage_(self, userContentController, message):
        try:
            body = message.body()
            # body might be an NSDictionary or dict
            action = body.get("action") if hasattr(body, "get") else None
            if not action and hasattr(body, "valueForKey_"):
                action = body.valueForKey_("action")

            if self.hub_manager is not None and action:
                self.hub_manager.handle_action(str(action), body)
        except Exception as e:
            logger.error("Error processing JS message: %s", e)


class HubManager:
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
        self._init_window()

    @classmethod
    def get_instance(cls) -> HubManager:
        if cls._instance is None:
            cls._instance = HubManager()
        return cls._instance

    def _init_window(self):
        try:
            width = 880.0
            height = 600.0

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
            self._window.setTitle_("Fixoflow")
            self._window.setAppearance_(AppKit.NSAppearance.appearanceNamed_(AppKit.NSAppearanceNameAqua))
            # Keep the retained hub reusable after the red close button. The
            # menu/Dock and second-instance notification reopen this same window.
            self._window.setReleasedWhenClosed_(False)
            self._window.setTitlebarAppearsTransparent_(True)
            self._window.setBackgroundColor_(AppKit.NSColor.colorWithRed_green_blue_alpha_(0.96, 0.957, 0.941, 1.0))

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

    def _publish_permissions(self):
        self._eval_js(f"onPermissionData({json.dumps(permission_snapshot())});")

    def handle_action(self, action: str, payload):
        """Processes IPC messages coming from hub.html UI."""
        if action == "getPermissions":
            self._publish_permissions()
        elif action == "requestPermissions":
            self._eval_js(f"onPermissionData({json.dumps(request_all_permissions())});")
            self.handle_action("getControlStatus", {})
        elif action == "getControlStatus":
            if self.on_control_status:
                self._eval_js(f"onControlStatus({json.dumps(self.on_control_status())});")
        elif action == "showOverlay":
            if self.on_show_overlay:
                self.on_show_overlay()
        elif action == "enableShortcut":
            try:
                if self.on_enable_shortcut is None:
                    raise RuntimeError("Open the full Fixoflow application to enable dictation.")
                message = self.on_enable_shortcut()
                if message:
                    self._eval_js(f"onSettingsResult(false, {json.dumps(message)});")
                else:
                    self._eval_js("onSettingsResult(true, 'Shortcut enabled.');")
            except Exception as e:
                self._eval_js(f"onSettingsResult(false, {json.dumps(str(e))});")
            self._publish_permissions()
            self.handle_action("getControlStatus", {})
        elif action == "restartApp":
            if self.on_restart is None:
                self._eval_js("onSettingsResult(false, 'Open the full Fixoflow application to restart it.');")
            else:
                self._eval_js("onSettingsResult(true, 'Restarting Fixoflow…');")
                self.on_restart()
        elif action == "openPermissionSettings":
            section = payload.get("section", "")
            allowed = {"microphone": "Privacy_Microphone", "accessibility": "Privacy_Accessibility", "input": "Privacy_ListenEvent"}
            if section in allowed:
                AppKit.NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_("x-apple.systempreferences:com.apple.preference.security?" + allowed[section]))
        elif action == "copyText":
            from fixoflow.platform.macos import copy_to_clipboard
            if isinstance(payload.get("text"), str):
                copy_to_clipboard(payload["text"])
        elif action == "getDashboard":
            stats = self.db.get_total_stats()
            top_apps = self.db.get_app_breakdown()
            js = f"onDashboardData({json.dumps(stats)}, {json.dumps(top_apps)});"
            self._eval_js(js)

        elif action == "getHistory":
            search = payload.get("search", "") if hasattr(payload, "get") else ""
            items = self.db.get_history(limit=50, search=str(search or ""))
            js = f"onHistoryData({json.dumps(items)});"
            self._eval_js(js)

        elif action == "deleteHistory":
            sess_id = payload.get("id") if hasattr(payload, "get") else None
            if sess_id:
                self.db.delete_history_item(str(sess_id))
                self.handle_action("getHistory", {})
                self.handle_action("getDashboard", {})

        elif action == "clearHistory":
            self.db.clear_all_history()
            self.handle_action("getHistory", {})
            self.handle_action("getDashboard", {})

        elif action == "getDictionary":
            words = self.db.get_dictionary(limit=100)
            js = f"onDictionaryData({json.dumps(words)});"
            self._eval_js(js)

        elif action == "addWord":
            phrase = str(payload.get("phrase", "") if hasattr(payload, "get") else "")
            replacement = str(payload.get("replacement", "") if hasattr(payload, "get") else "")
            category = str(payload.get("category", "general") if hasattr(payload, "get") else "general")
            if phrase and replacement:
                self.db.upsert_word(phrase, replacement, category=category, auto_learned=0)
                self.handle_action("getDictionary", {})

        elif action == "deleteWord":
            phrase = str(payload.get("phrase", "") if hasattr(payload, "get") else "")
            if phrase:
                self.db.delete_word(phrase)
                self.handle_action("getDictionary", {})

        elif action == "getConfig":
            from dataclasses import asdict
            js = f"onConfigData({json.dumps(asdict(self.config))});"
            self._eval_js(js)
            self._publish_permissions()

        elif action == "saveConfig":
            cfg_dict = payload.get("config") if hasattr(payload, "get") else {}
            if cfg_dict:
                try:
                    from dataclasses import asdict
                    allowed = {"mode", "hotkey", "model_name", "always_show_overlay", "sound_enabled", "dual_mode_hotkey", "hold_to_talk"}
                    data = asdict(self.config)
                    data.update({k: v for k, v in cfg_dict.items() if k in allowed})
                    candidate = FixoflowConfig(**data)
                    candidate.validate()
                    if self.on_config_change is None:
                        raise RuntimeError("Open the full Fixoflow application to change dictation settings.")
                    self.on_config_change(candidate)
                    self._eval_js("onSettingsResult(true, 'Preferences applied.');")
                    self.handle_action("getConfig", {})
                except Exception as e:
                    self._eval_js(f"onSettingsResult(false, {json.dumps(str(e))});")

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
