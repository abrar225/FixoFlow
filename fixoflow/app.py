"""
Fixoflow Native macOS Application Entry Point
Integrates the macOS Status Bar menu item, the Hub GUI window,
the floating glassmorphic pill overlay, and the global hotkey daemon.
"""
from __future__ import annotations

import logging
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import argparse
import fcntl
import json
from pathlib import Path
from typing import Optional

import AppKit
from Foundation import NSObject, NSDistributedNotificationCenter, NSOperationQueue

from fixoflow.config import FixoflowConfig, OVERLAY_POSITIONS
from fixoflow.daemon import FixoflowDaemon
from fixoflow.platform.macos import (
    accessibility_trusted,
    input_monitoring_trusted,
    request_notification_authorization,
)
from fixoflow.ui.hub import HubManager
from fixoflow.controls import shortcut_label

logger = logging.getLogger("fixoflow.app")


def relaunch_command(bundle_path: Optional[str] = None) -> list:
    """Detached command that opens a fresh instance after this one exits.

    macOS applies permission grants (Input Monitoring always, Accessibility
    usually) only to a newly started process. The single-instance lock would
    otherwise route every reopen to the process that predates the grant.
    """
    if getattr(sys, "frozen", False) or bundle_path:
        path = bundle_path or AppKit.NSBundle.mainBundle().bundlePath()
        return ["/bin/sh", "-c", f"sleep 1.2; exec /usr/bin/open -n {shlex.quote(path)}"]
    return ["/bin/sh", "-c", f"sleep 1.2; exec {shlex.quote(sys.executable)} -m fixoflow.app"]


def check_floating_control(overlay):
    """Exercise actual local WebKit IPC without opening audio or pasting text."""
    import time
    from Foundation import NSDate, NSRunLoop
    from fixoflow.ui.overlay import zone_origin
    events, result = [], []
    reported = []
    original_callback = overlay.on_position_change
    overlay.on_toggle = lambda: events.append('toggle')
    overlay.on_cancel = lambda: events.append('cancel')
    overlay.on_open_hub = lambda: events.append('settings')
    # The drag exercise below must not persist a position into the user's config.
    overlay.on_position_change = reported.append
    initial_zone = overlay._zone
    assert not overlay._panel.canBecomeKeyWindow()
    assert not overlay._panel.ignoresMouseEvents()
    deadline = time.monotonic() + 12
    loop = NSRunLoop.currentRunLoop()
    while not overlay._ready and time.monotonic() < deadline:
        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
    assert overlay._ready, 'Floating control did not finish loading'
    script = """(() => {
        const bar = document.getElementById('bar');
        const overflow = () => bar.scrollWidth <= bar.clientWidth + 1;
        updateControl({state:'listening',message:'Listening',shortcut:'⌃ Space',elapsed:2});
        const listeningFits = overflow();
        document.getElementById('toggle').click();
        document.querySelector('[aria-label="Cancel recording"]').click();
        updateControl({state:'processing',message:'Transcribing',shortcut:'⌃ Space'});
        const disabled = document.getElementById('toggle').disabled;
        document.getElementById('toggle').click();
        updateControl({state:'error',message:'Enable Accessibility permission',shortcut:'⌃ Space'});
        const errorFits = overflow();
        updateControl({state:'idle',message:'Click to dictate',shortcut:'⌃ Space'});
        document.querySelector('[aria-label="Open Fixoflow settings"]').click();
        const idleFits = overflow();
        const drag = {};
        try {
          const dispatch = (target, type, id, x, y) => target.dispatchEvent(new PointerEvent(type, {bubbles:true, button:0, pointerId:id, screenX:x, screenY:y}));
          dispatch(bar, 'pointerdown', 7, 400, 400);
          dispatch(window, 'pointermove', 7, 400, -5000);
          dispatch(window, 'pointerup', 7, 400, -5000);
          dispatch(bar, 'pointerdown', 8, 400, 100);
          dispatch(window, 'pointermove', 8, 400, 20000);
          dispatch(window, 'pointerup', 8, 400, 20000);
          drag.ok = true;
        } catch (error) { drag.error = String(error); }
        return JSON.stringify({disabled, label:document.getElementById('toggle').getAttribute('aria-label'),
            width:bar.style.width, height:bar.style.height, idleFits, listeningFits, errorFits, drag});
    })()"""
    overlay._webview.evaluateJavaScript_completionHandler_(script, lambda value, error: result.append((value, error)))
    while (not result or len(events) < 3) and time.monotonic() < deadline:
        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
    assert result and result[0][1] is None, f'Floating control script failed: {result}'
    payload = json.loads(result[0][0])
    assert payload['disabled'] is True and payload['label'] == 'Start dictation', payload
    # The idle pill must stay small and unobtrusive; it may never approach the
    # old full-width bar.
    assert float(payload['width'].rstrip('px')) <= 200 and float(payload['height'].rstrip('px')) <= 44, payload
    # No state may overflow its flex row into the neighbouring controls.
    assert payload['idleFits'] and payload['listeningFits'] and payload['errorFits'], payload
    assert events == ['toggle', 'cancel', 'settings'], f'Unexpected floating control actions: {events}'
    # Synthetic pointer drag through WebKit: up snaps top-center, down returns
    # to the starting column's bottom zone; the position callback reports each
    # change and the frame lands on the zone origin.
    assert payload['drag'].get('ok'), payload
    expected = [] if initial_zone == 'top-center' else ['top-center']
    down_zone = 'bottom-center' if initial_zone == 'top-center' else initial_zone
    if not expected or expected[-1] != down_zone:
        expected.append(down_zone)
    while len(reported) < len(expected) and time.monotonic() < deadline:
        loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
    assert reported == expected, f'Expected drag snap {expected}, got {reported} (initial {initial_zone})'
    loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(1.0))
    frame = overlay._panel.frame()
    target_x, target_y = zone_origin(down_zone, (frame.size.width, frame.size.height), overlay._visible_frame())
    assert abs(frame.origin.x - target_x) <= 6 and abs(frame.origin.y - target_y) <= 6, \
        f'Pill did not land on {down_zone}: {(frame.origin.x, frame.origin.y)} vs {(target_x, target_y)}'
    # Leave the pill exactly where the user had it.
    overlay._zone = initial_zone
    overlay._reported_zone = initial_zone
    overlay._snap(animate=False)
    overlay.on_position_change = original_callback


class MenuDelegate(NSObject):
    app_instance = None

    def applicationShouldHandleReopen_hasVisibleWindows_(self, application, visible):
        self.openHub_(None)
        return True

    def reopen_(self, notification):
        self.openHub_(None)

    def tick_(self, timer):
        # Periodic Python entry also allows signal handlers to run while Cocoa
        # owns event dispatch. NSRunLoop alone never dispatches mouse/key events.
        if self.app_instance:
            self.app_instance.refresh_status()

    def openHub_(self, sender):
        if self.app_instance:
            self.app_instance.hub.show()

    def setModeCoding_(self, sender):
        if self.app_instance:
            self.app_instance.set_mode("coding")

    def setModeWriting_(self, sender):
        if self.app_instance:
            self.app_instance.set_mode("writing")

    def setModeAuto_(self, sender):
        if self.app_instance:
            self.app_instance.set_mode("auto")

    def toggleDictation_(self, sender):
        if self.app_instance:
            self.app_instance.daemon.controls.toggle()

    def restartApp_(self, sender):
        if self.app_instance:
            self.app_instance.restart()

    def quitApp_(self, sender):
        if self.app_instance:
            self.app_instance.stop()
        sys.exit(0)


class FixoflowApp:
    def __init__(self):
        self.config = FixoflowConfig.load()
        self.ns_app = AppKit.NSApplication.sharedApplication()
        # A regular app: Fixoflow keeps a Dock icon and joins the app switcher,
        # while the floating pill stays a nonactivating panel.
        self.ns_app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)

        self.daemon = FixoflowDaemon(self.config)
        self.hub = HubManager.get_instance()
        self.status_item: Optional[AppKit.NSStatusItem] = None
        self._delegate = MenuDelegate.alloc().init()
        self._delegate.app_instance = self
        self.ns_app.setDelegate_(self._delegate)
        NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self._delegate, "reopen:", "com.fixoflow.showHub", None
        )
        self.hub.config = self.config
        self.hub.on_config_change = self.apply_config
        self.hub.on_enable_shortcut = self.enable_shortcut
        self.hub.on_show_overlay = self.show_overlay
        self.hub.on_control_status = self.control_status
        self.hub.on_restart = self.restart
        self.daemon.controls.on_change = lambda: NSOperationQueue.mainQueue().addOperationWithBlock_(self.refresh_status)
        self._status_cache = None
        self._shortcut_error = "Shortcut needs Accessibility and Input Monitoring. Grant them, then restart Fixoflow if the status stays red."
        self._last_permission_probe = 0.0
        self._running = False
        request_notification_authorization()

        self._setup_menu_bar()
        self.daemon.coordinator.overlay.configure(self.config, on_toggle=self.daemon.controls.toggle,
            on_cancel=self.daemon.controls.cancel, on_open_hub=self.hub.show,
            on_position_change=self.set_overlay_position)

    def show_overlay(self):
        overlay = self.daemon.coordinator.overlay
        # Explicit Show works even when the persistent-bar preference is off.
        overlay.reveal()

    def control_status(self):
        listener = self.daemon._listener
        active = bool(listener is not None and listener.is_alive() and listener.running)
        state = self.daemon.controls.state
        detail = self.daemon.coordinator.last_error or ("Tap to toggle; hold to talk." if active else self._shortcut_error)
        return {"state": state, "shortcut": shortcut_label(self.config.hotkey), "shortcut_active": active, "detail": detail}

    def refresh_status(self):
        status = self.control_status()
        serialized = json.dumps(status)
        if serialized != self._status_cache:
            self._status_cache = serialized
            self.hub._eval_js(f"onControlStatus({serialized});")
            self._toggle_menu_item.setTitle_("Stop dictation" if status["state"] == "RECORDING" else
                "Transcribing…" if status["state"] == "PROCESSING" else f"Start dictation ({status['shortcut']})")
            self._toggle_menu_item.setEnabled_(status["state"] != "PROCESSING")
        self._activate_shortcut_when_permitted(status)

    def _activate_shortcut_when_permitted(self, status):
        """Start the listener as soon as macOS reports the grants are live.

        The permission check is cheap but not free; probe at most once a
        second while the shortcut is inactive with a known blocker.
        """
        if status["shortcut_active"] or not self._shortcut_error:
            return
        now = time.monotonic()
        if now - self._last_permission_probe < 1.0:
            return
        self._last_permission_probe = now
        if not accessibility_trusted(prompt=False) or not input_monitoring_trusted(prompt=False):
            return
        if self.enable_shortcut() is None:
            logger.info("Shortcut listener started after permissions became available")

    def enable_shortcut(self):
        """Start the global shortcut listener.

        Returns None on success or a user-facing reason when macOS permissions
        still block the listener.
        """
        if not accessibility_trusted(prompt=False):
            self._shortcut_error = "Enable Fixoflow in System Settings → Privacy & Security → Accessibility, then retry."
            return self._shortcut_error
        if not input_monitoring_trusted(prompt=False):
            self._shortcut_error = "Enable Fixoflow in System Settings → Privacy & Security → Input Monitoring, then restart Fixoflow."
            return self._shortcut_error
        self.daemon.start_listener()
        self._shortcut_error = ""
        self.refresh_status()
        return None

    def apply_config(self, candidate):
        from pynput import keyboard
        keyboard.HotKey.parse(candidate.hotkey)
        candidate.validate()
        from fixoflow.audio.recorder import AudioRecorder
        from fixoflow.stt.engine import STTEngine
        from fixoflow.brain.polisher import TextPolisher
        def update():
            candidate.save()
            self.daemon.stop_listener()
            self.config.__dict__.update(candidate.__dict__)
            self.daemon.coordinator.recorder = AudioRecorder(self.config)
            self.daemon.coordinator.stt = STTEngine(self.config)
            self.daemon.coordinator.polisher = TextPolisher(self.config)
            self.daemon.configure_hotkey()
        self.daemon.controls.configure(update)
        self.daemon.coordinator.overlay.configure(self.config)
        self._update_menu_mode_checks()
        message = self.enable_shortcut()
        if message:
            logger.info("Preferences saved; shortcut awaits macOS permissions")
        self.refresh_status()

    def _setup_menu_bar(self):
        status_bar = AppKit.NSStatusBar.systemStatusBar()
        self.status_item = status_bar.statusItemWithLength_(AppKit.NSVariableStatusItemLength)
        button = self.status_item.button()
        if button:
            symbol = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_("waveform", "Fixoflow")
            symbol.setTemplate_(True)
            button.setImage_(symbol)

        menu = AppKit.NSMenu.alloc().init()

        title_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Fixoflow (Active)", None, ""
        )
        title_item.setEnabled_(False)
        menu.addItem_(title_item)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        hub_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Open Hub Window...", "openHub:", ""
        )
        hub_item.setTarget_(self._delegate)
        menu.addItem_(hub_item)

        toggle_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Toggle Dictation ({self.config.hotkey})", "toggleDictation:", ""
        )
        toggle_item.setTarget_(self._delegate)
        self._toggle_menu_item = toggle_item
        menu.addItem_(toggle_item)

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        # Mode Selection
        self.mode_coding_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Coding & AI agents", "setModeCoding:", ""
        )
        self.mode_coding_item.setTarget_(self._delegate)
        menu.addItem_(self.mode_coding_item)

        self.mode_writing_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Writing & documents", "setModeWriting:", ""
        )
        self.mode_writing_item.setTarget_(self._delegate)
        menu.addItem_(self.mode_writing_item)

        self.mode_auto_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Automatic mode", "setModeAuto:", ""
        )
        self.mode_auto_item.setTarget_(self._delegate)
        menu.addItem_(self.mode_auto_item)

        self._update_menu_mode_checks()

        menu.addItem_(AppKit.NSMenuItem.separatorItem())

        restart_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Restart Fixoflow", "restartApp:", ""
        )
        restart_item.setTarget_(self._delegate)
        menu.addItem_(restart_item)

        quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit Fixoflow", "quitApp:", "q"
        )
        quit_item.setTarget_(self._delegate)
        menu.addItem_(quit_item)

        self.status_item.setMenu_(menu)

    def _update_menu_mode_checks(self):
        mode = self.config.mode
        self.mode_coding_item.setState_(1 if mode == "coding" else 0)
        self.mode_writing_item.setState_(1 if mode == "writing" else 0)
        self.mode_auto_item.setState_(1 if mode == "auto" else 0)

    def set_overlay_position(self, zone: str):
        """Persist a pill snap zone chosen by dragging (no engine rebuild)."""
        if zone not in OVERLAY_POSITIONS:
            logger.warning("Ignoring unknown floating pill position: %s", zone)
            return
        if zone == self.config.overlay_position:
            return
        self.config.overlay_position = zone
        self.config.save()
        self.hub.config = self.config
        self.hub.handle_action("getConfig", {})
        logger.info("Floating pill placed at: %s", zone)

    def set_mode(self, mode: str):
        from dataclasses import replace
        try:
            self.apply_config(replace(self.config, mode=mode))
        except Exception as error:
            self.daemon.coordinator.overlay.show_error("Settings rejected")
            logger.error("Mode switch failed: %s", error)
            return
        logger.info("Switched Fixoflow mode to: %s", mode)

    def run(self, show_hub_on_launch: bool = True):
        self._running = True
        self.ns_app.finishLaunching()
        logger.info("Launching Fixoflow Native macOS App...")

        def signal_handler(sig, frame):
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start keyboard listener in daemon
        message = self.enable_shortcut()
        if message:
            logger.warning("%s", message)

        self.daemon.coordinator.overlay.show_idle()

        if show_hub_on_launch:
            self.hub.show()

        from Foundation import NSTimer
        self._signal_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.2, self._delegate, "tick:", None, True
        )
        try:
            self.ns_app.run()
        except KeyboardInterrupt:
            self.stop()
        finally:
            self._signal_timer.invalidate()

    def stop(self):
        self._running = False
        self.ns_app.stop_(None)
        if self.daemon:
            self.daemon.stop()
        if self.hub:
            self.hub.hide()

    def restart(self):
        """Replace this process with a fresh instance.

        Required after permission changes: macOS applies grants only to newly
        started processes, and the single-instance lock routes plain reopens
        back to this (pre-grant) process.
        """
        command = relaunch_command()
        subprocess.Popen(command, start_new_session=True)
        logger.info("Restarting Fixoflow with a fresh process")
        self.stop()
        os._exit(0)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true", help="Check UI and local model without microphone or hotkey")
    parser.add_argument("--background", action="store_true", help="Start the floating controls without opening the hub")
    args = parser.parse_args(argv)
    log_dir = Path.home() / "Library/Logs/Fixoflow"
    log_dir.mkdir(parents=True, exist_ok=True)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(log_dir / "fixoflow.log", maxBytes=1000000, backupCount=2), logging.StreamHandler()], format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    if args.self_check:
        import tempfile
        from fixoflow.storage.db import FixoflowDB
        from fixoflow.stt.engine import STTEngine
        with tempfile.TemporaryDirectory() as directory:
            FixoflowDB._instance = FixoflowDB(Path(directory) / "check.sqlite")
            app = FixoflowApp()
            assert app.hub._window is not None and app.hub._webview is not None
            assert app.daemon.coordinator.overlay._panel is not None
            app.hub.handle_action("getConfig", {})
            check_floating_control(app.daemon.coordinator.overlay)
            window = app.hub._window
            window.makeKeyAndOrderFront_(None)
            window.close()
            assert not window.isVisible()
            window.makeKeyAndOrderFront_(None)
            assert window.isVisible() and window.alphaValue() == 1.0
            window.orderOut_(None)
            model = STTEngine(app.config).resolve_model_path()
            print(json.dumps({"ui": "ok", "model": str(model), "hotkey_started": False, "microphone_opened": False}))
            app.stop()
        return
    lock_path = Path.home() / ".fixoflow/app.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as instance_lock:
        try:
            fcntl.flock(instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_("com.fixoflow.showHub", None)
            return
        try:
            app = FixoflowApp()
            app.run(show_hub_on_launch=not args.background)
        except Exception:
            logger.exception("Fixoflow startup failed")
            alert = AppKit.NSAlert.alloc().init()
            alert.setMessageText_("Fixoflow could not start")
            alert.setInformativeText_(f"Details were saved to {log_dir / 'fixoflow.log'}. Your recordings have not been deleted.")
            alert.runModal()
            raise


if __name__ == "__main__":
    main()
