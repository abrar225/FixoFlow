"""macOS platform integration.

Owns everything that touches the operating system: permission state and
requests, frontmost-application identity, focus restoration, clipboard,
synthetic paste, notifications, and system sounds.

Insertion contract: dictated text is always copied to the clipboard before any
synthetic keystroke is attempted, so text is never lost when Accessibility is
missing or event posting fails. Callers distinguish the failure reason through
`InsertionOutcome`.
"""
from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import AppKit
import ApplicationServices
import AVFoundation
import Quartz

try:
    from Foundation import NSUserNotification, NSUserNotificationCenter
except Exception:  # pragma: no cover - older frameworks only
    NSUserNotification = None
    NSUserNotificationCenter = None

try:
    import UserNotifications
except Exception:  # pragma: no cover - source runs without the framework
    UserNotifications = None

logger = logging.getLogger("fixoflow.platform.macos")

# macOS virtual key code for 'v'
KEY_CODE_V = 0x09

_MICROPHONE_STATES = {
    0: "not determined",
    1: "restricted",
    2: "denied",
    3: "authorized",
}


@dataclass(frozen=True)
class InsertionOutcome:
    """Result of one insertion attempt.

    ``inserted`` means a Cmd+V keystroke was posted. ``copied`` means the text
    reached the system clipboard. ``reason`` is one of ``inserted``,
    ``permission``, ``event-failed`` or ``clipboard-failed``.
    """

    inserted: bool
    copied: bool
    reason: str


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def accessibility_trusted(prompt: bool = False) -> bool:
    """Accessibility trust state; optionally raises the system prompt.

    The prompt is what adds Fixoflow to System Settings → Privacy & Security →
    Accessibility. Without this permission no synthetic keystroke can be
    delivered, so insertion cannot work.
    """
    try:
        if prompt:
            options = {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
            return bool(ApplicationServices.AXIsProcessTrustedWithOptions(options))
        return bool(ApplicationServices.AXIsProcessTrusted())
    except Exception as error:
        logger.error("Accessibility trust check failed: %s", error)
        return False


def input_monitoring_trusted(prompt: bool = False) -> bool:
    """Input Monitoring state; optionally raises the system prompt.

    Required for the global shortcut listener to receive key events.
    """
    try:
        if prompt and hasattr(Quartz, "CGRequestListenEventAccess"):
            return bool(Quartz.CGRequestListenEventAccess())
        if hasattr(Quartz, "CGPreflightListenEventAccess"):
            return bool(Quartz.CGPreflightListenEventAccess())
        return accessibility_trusted(prompt=prompt)
    except Exception as error:
        logger.error("Input Monitoring trust check failed: %s", error)
        return False


def microphone_status() -> str:
    """Human-readable microphone authorization state."""
    try:
        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        return _MICROPHONE_STATES.get(int(status), "unknown")
    except Exception as error:
        logger.error("Microphone status check failed: %s", error)
        return "unknown"


def request_microphone_access() -> None:
    """Trigger the macOS microphone prompt when access has not been decided."""
    try:
        AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVFoundation.AVMediaTypeAudio, lambda granted: None
        )
    except Exception as error:
        logger.error("Microphone access request failed: %s", error)


def permission_snapshot() -> dict:
    """One dictionary shared with the hub permission panel."""
    return {
        "accessibility": accessibility_trusted(),
        "input": input_monitoring_trusted(),
        "microphone": microphone_status(),
    }


def request_all_permissions() -> dict:
    """Raise the system prompts for every permission Fixoflow needs."""
    accessibility_trusted(prompt=True)
    input_monitoring_trusted(prompt=True)
    request_microphone_access()
    return permission_snapshot()


# ---------------------------------------------------------------------------
# Application identity and focus
# ---------------------------------------------------------------------------

def get_frontmost_app_info() -> Tuple[str, str]:
    """Return (localized name, bundle identifier) of the frontmost application."""
    try:
        app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if app:
            return app.localizedName() or "Unknown", app.bundleIdentifier() or ""
    except Exception as error:
        logger.error("Failed to query frontmost application: %s", error)
    return "Unknown", ""


def frontmost_bundle_id() -> str:
    return get_frontmost_app_info()[1]


def activate_application(bundle_id: str, timeout_sec: float = 0.8) -> bool:
    """Best-effort return of focus to the application that owns the cursor.

    Used when the user interacts with Fixoflow itself between starting and
    stopping a dictation, so the transcript still lands in the original field.
    """
    if not bundle_id:
        return False
    try:
        matches = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
        if not matches:
            return False
        app = matches[0]
        if not app.isActive():
            app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    except Exception as error:
        logger.error("Could not activate %s: %s", bundle_id, error)
        return False
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if frontmost_bundle_id() == bundle_id:
            return True
        time.sleep(0.05)
    return frontmost_bundle_id() == bundle_id


# ---------------------------------------------------------------------------
# Clipboard, insertion and feedback
# ---------------------------------------------------------------------------

def copy_to_clipboard(text: str) -> bool:
    """Replace the pasteboard string contents."""
    try:
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        return bool(pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString))
    except Exception as error:
        logger.error("Failed to copy to clipboard: %s", error)
        return False


def insert_text_at_cursor(text: str, delay_sec: float = 0.05) -> InsertionOutcome:
    """Copy text and post Cmd+V into the frontmost application.

    The clipboard write always happens first: even if Accessibility is not
    granted or event posting fails, the user can paste manually with Cmd+V.
    System prompts are never raised here; the hub raises them only when the
    user explicitly asks.
    """
    if not copy_to_clipboard(text):
        return InsertionOutcome(False, False, "clipboard-failed")

    if not accessibility_trusted():
        # Never raise the system prompt from an insertion attempt. Prompting is
        # an explicit user action (hub "Request permissions"); repeated dialogs
        # on every paste are what make the app feel like it is asking forever.
        logger.warning("Accessibility permission is required to paste automatically")
        return InsertionOutcome(False, True, "permission")

    time.sleep(delay_sec)
    try:
        event_down = Quartz.CGEventCreateKeyboardEvent(None, KEY_CODE_V, True)
        Quartz.CGEventSetFlags(event_down, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_down)

        event_up = Quartz.CGEventCreateKeyboardEvent(None, KEY_CODE_V, False)
        Quartz.CGEventSetFlags(event_up, 0)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event_up)
        logger.info("Pasted text (%d characters) at cursor", len(text))
        return InsertionOutcome(True, True, "inserted")
    except Exception as error:
        logger.error("Failed to post paste keystroke: %s", error)
        return InsertionOutcome(False, True, "event-failed")


def request_notification_authorization() -> None:
    """Ask for notification permission once, without blocking startup."""
    if UserNotifications is None:
        return
    try:
        center = UserNotifications.UNUserNotificationCenter.currentNotificationCenter()
        options = (UserNotifications.UNAuthorizationOptionAlert
                   | UserNotifications.UNAuthorizationOptionSound)
        center.requestAuthorizationWithOptions_completionHandler_(options, lambda granted, error: None)
    except Exception as error:
        logger.info("Notification authorization unavailable: %s", error)


def notify(title: str, body: str) -> bool:
    """Best-effort desktop notification for outcomes the user must notice."""
    if UserNotifications is not None:
        try:
            content = UserNotifications.UNMutableNotificationContent.alloc().init()
            content.setTitle_(title)
            content.setBody_(body)
            request = UserNotifications.UNNotificationRequest.requestWithIdentifier_content_trigger_(
                f"fixoflow-{time.monotonic_ns()}", content, None
            )
            UserNotifications.UNUserNotificationCenter.currentNotificationCenter() \
                .addNotificationRequest_withCompletionHandler_(request, lambda error: None)
            return True
        except Exception as error:
            logger.info("UserNotifications delivery failed: %s", error)
    if NSUserNotification is not None and NSUserNotificationCenter is not None:
        try:
            notification = NSUserNotification.alloc().init()
            notification.setTitle_(title)
            notification.setInformativeText_(body)
            NSUserNotificationCenter.defaultUserNotificationCenter().deliverNotification_(notification)
            return True
        except Exception as error:
            logger.info("Legacy notification delivery failed: %s", error)
    return False


def play_sound(sound_name: str = "Tink") -> None:
    """Play a macOS system sound asynchronously for state feedback."""
    try:
        sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
        subprocess.Popen(["afplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
