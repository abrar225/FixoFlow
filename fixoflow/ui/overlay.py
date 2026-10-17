"""A persistent, nonactivating dictation control backed by local WebKit.

The control is a compact glass pill that snaps into one of four placement
zones (top center, bottom left, bottom center, bottom right). The user drags
it anywhere — pressing any part of the pill, buttons included — and it drops
into the nearest zone; a snap guide shows the zones while dragging. Placement
geometry is plain tuple math (``zone_origin``, ``dragged_origin``,
``clamp_origin``, ``nearest_zone``) so it is unit tested without Cocoa. Every
resize re-derives the origin from the zone's canonical slot, so state changes
and snap animations can never drift the pill off its margin.

Glass look: the panel hosts an ``NSVisualEffectView`` (behind-window blend)
with a capsule mask; the HTML only draws a translucent tint, so the blur is
macOS's real backdrop blur, not a simulated one.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import AppKit
from Foundation import NSObject, NSOperationQueue, NSPoint, NSRect, NSSize, NSURL, NSTimer
import WebKit

from fixoflow.config import OVERLAY_POSITIONS
from fixoflow.controls import shortcut_label

logger = logging.getLogger(__name__)

ZONE_LABELS = {
    "top-center": "Top center",
    "bottom-left": "Bottom left",
    "bottom-center": "Bottom center",
    "bottom-right": "Bottom right",
}
ZONE_MARGIN = 10.0
IDLE_SIZE = (116.0, 30.0)
MIN_SIZE = (64.0, 26.0)
RESIZE_SECONDS = 0.18
SNAP_SECONDS = 0.26
IDLE_ALPHA = 0.82


# ---------------------------------------------------------------------------
# Placement geometry (pure math; coordinates are (x, y, width, height) tuples
# in AppKit's bottom-left origin space).
# ---------------------------------------------------------------------------

def zone_origin(zone, size, visible_frame, margin=ZONE_MARGIN):
    """Bottom-left origin that places a pill of ``size`` in ``zone``."""
    x, y, width, height = visible_frame
    pill_width, pill_height = size
    if zone == "top-center":
        return (x + (width - pill_width) / 2.0, y + height - pill_height - margin)
    if zone == "bottom-left":
        return (x + margin, y + margin)
    if zone == "bottom-right":
        return (x + width - pill_width - margin, y + margin)
    return (x + (width - pill_width) / 2.0, y + margin)


def clamp_origin(origin, size, visible_frame):
    """Keep the whole pill inside the visible frame."""
    x, y, width, height = visible_frame
    pill_width, pill_height = size
    return (
        min(max(origin[0], x), x + width - pill_width),
        min(max(origin[1], y), y + height - pill_height),
    )


def dragged_origin(start_origin, start_point, current_point, size, visible_frame):
    """AppKit origin after a drag.

    WebKit screen coordinates grow downward from the top of the primary
    screen; AppKit window origins grow upward, so the vertical delta flips
    sign. The result is clamped to the visible frame.
    """
    delta_x = current_point[0] - start_point[0]
    delta_y = current_point[1] - start_point[1]
    return clamp_origin((start_origin[0] + delta_x, start_origin[1] - delta_y), size, visible_frame)


def nearest_zone(center, size, visible_frame):
    """Zone whose snapped pill center is closest to ``center``."""
    best = OVERLAY_POSITIONS[0]
    best_distance = None
    for zone in OVERLAY_POSITIONS:
        origin = zone_origin(zone, size, visible_frame)
        zone_center = (origin[0] + size[0] / 2.0, origin[1] + size[1] / 2.0)
        distance = (zone_center[0] - center[0]) ** 2 + (zone_center[1] - center[1]) ** 2
        if best_distance is None or distance < best_distance:
            best, best_distance = zone, distance
    return best


# ---------------------------------------------------------------------------
# Cocoa views
# ---------------------------------------------------------------------------

class DictationPanel(AppKit.NSPanel):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False


class ControlWebView(WebKit.WKWebView):
    def acceptsFirstMouse_(self, event):
        return True


class SnapGuideView(AppKit.NSView):
    """Draws ghost pill outlines for the placement zones while dragging."""

    zones = None
    highlight = -1

    def drawRect_(self, rect):
        if not self.zones:
            return
        attributes = {
            AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(11),
            AppKit.NSForegroundColorAttributeName: AppKit.NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.72),
        }
        for index, (zone, zone_rect) in enumerate(self.zones):
            radius = zone_rect.size.height / 2.0
            path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(zone_rect, radius, radius)
            if index == self.highlight:
                AppKit.NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.20).setFill()
                path.fill()
                AppKit.NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.85).setStroke()
            else:
                AppKit.NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.07).setFill()
                path.fill()
                AppKit.NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.32).setStroke()
            path.setLineWidth_(1.0)
            path.setLineDash_count_phase_([4.0, 4.0], 2, 0.0)
            path.stroke()
            label = AppKit.NSString.stringWithString_(ZONE_LABELS.get(zone, zone))
            label_size = label.sizeWithAttributes_(attributes)
            label_x = zone_rect.origin.x + (zone_rect.size.width - label_size.width) / 2.0
            if zone == "top-center":
                label_y = zone_rect.origin.y - label_size.height - 6
            else:
                label_y = zone_rect.origin.y + zone_rect.size.height + 6
            label.drawAtPoint_withAttributes_((label_x, label_y), attributes)


class OverlayBridge(NSObject):
    manager = None

    def userContentController_didReceiveScriptMessage_(self, controller, message):
        body = message.body()
        if self.manager is not None and hasattr(body, 'get'):
            self.manager.handle_action(body.get('action'), body)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class OverlayManager:
    _instance = None

    def __init__(self):
        self._panel = None
        self._effect = None
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
        self._zone = 'bottom-center'
        self._reported_zone = 'bottom-center'
        self._hovered = False
        self._drag = None
        self._guide_panel = None
        self._guide_view = None
        self.on_toggle = None
        self.on_cancel = None
        self.on_open_hub = None
        self.on_position_change = None
        self._init_window()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # -- window construction -------------------------------------------------

    def _init_window(self):
        width, height = IDLE_SIZE
        x, y = zone_origin('bottom-center', IDLE_SIZE, self._visible_frame())
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
        self._panel.setHasShadow_(True)
        self._panel.setIgnoresMouseEvents_(False)
        self._panel.setAlphaValue_(IDLE_ALPHA)

        # Real macOS backdrop blur behind the translucent HTML tint.
        self._effect = AppKit.NSVisualEffectView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(width, height)))
        self._effect.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow)
        self._effect.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        self._effect.setState_(AppKit.NSVisualEffectStateActive)
        self._effect.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        self._effect.setWantsLayer_(True)
        self._effect.layer().setCornerRadius_(height / 2.0)
        self._effect.layer().setMasksToBounds_(True)
        self._effect.layer().setBorderWidth_(1.0)
        self._effect.layer().setBorderColor_(AppKit.NSColor.colorWithWhite_alpha_(1.0, 0.14).CGColor())

        config = WebKit.WKWebViewConfiguration.alloc().init()
        self._bridge = OverlayBridge.alloc().init()
        self._bridge.manager = self
        config.userContentController().addScriptMessageHandler_name_(self._bridge, 'fixoflow')
        self._webview = ControlWebView.alloc().initWithFrame_configuration_(
            NSRect(NSPoint(0, 0), NSSize(width, height)), config)
        self._webview.setValue_forKey_(False, 'drawsBackground')
        self._webview.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        url = NSURL.fileURLWithPath_(str(Path(__file__).with_name('overlay.html').resolve()))
        self._webview.loadFileURL_allowingReadAccessToURL_(url, url.URLByDeletingLastPathComponent())
        self._effect.addSubview_(self._webview)
        self._panel.setContentView_(self._effect)

    def _reduce_motion(self):
        return bool(AppKit.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion())

    def _screen(self):
        if self._panel is None:
            return AppKit.NSScreen.mainScreen()
        frame = self._panel.frame()
        center = NSPoint(frame.origin.x + frame.size.width / 2.0, frame.origin.y + frame.size.height / 2.0)
        for screen in AppKit.NSScreen.screens():
            if AppKit.NSPointInRect(center, screen.frame()):
                return screen
        return AppKit.NSScreen.mainScreen()

    def _visible_frame(self):
        screen = self._screen()
        if screen is None:
            return (0.0, 0.0, 1440.0, 900.0)
        rect = screen.visibleFrame()
        return (rect.origin.x, rect.origin.y, rect.size.width, rect.size.height)

    def _pill_center(self):
        frame = self._panel.frame()
        return (frame.origin.x + frame.size.width / 2.0, frame.origin.y + frame.size.height / 2.0)

    # -- frame animation -----------------------------------------------------

    def _animate_frame(self, rect, seconds):
        if self._reduce_motion():
            self._panel.setFrame_display_(rect, True)
            return
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(seconds)
        self._panel.animator().setFrame_display_(rect, True)
        AppKit.NSAnimationContext.endGrouping()

    def _apply_size(self, width, height, seconds=RESIZE_SECONDS):
        width = max(MIN_SIZE[0], float(width))
        height = max(MIN_SIZE[1], float(height))
        # Re-derive from the zone's canonical slot: idempotent, so a resize
        # racing a snap animation can never leave the pill off its margin.
        origin = zone_origin(self._zone, (width, height), self._visible_frame())
        self._effect.layer().setCornerRadius_(height / 2.0)
        self._animate_frame(NSRect(NSPoint(origin[0], origin[1]), NSSize(width, height)), seconds)

    def _snap(self, animate=True):
        frame = self._panel.frame()
        size = (frame.size.width, frame.size.height)
        x, y = zone_origin(self._zone, size, self._visible_frame())
        rect = NSRect(NSPoint(x, y), NSSize(size[0], size[1]))
        if animate and not self._reduce_motion():
            self._animate_frame(rect, SNAP_SECONDS)
        else:
            self._panel.setFrame_display_(rect, True)

    def _idle_alpha(self):
        return IDLE_ALPHA if (self._state == 'idle' and not self._hovered) else 1.0

    def _animate_alpha(self, value):
        if self._reduce_motion():
            self._panel.setAlphaValue_(value)
            return
        AppKit.NSAnimationContext.beginGrouping()
        AppKit.NSAnimationContext.currentContext().setDuration_(0.15)
        self._panel.animator().setAlphaValue_(value)
        AppKit.NSAnimationContext.endGrouping()

    # -- snap guide ----------------------------------------------------------

    def _ensure_guide(self):
        if self._guide_panel is not None:
            return
        screen = self._screen()
        frame = screen.frame() if screen is not None else NSRect(NSPoint(0, 0), NSSize(1440, 900))
        panel = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        panel.setIgnoresMouseEvents_(True)
        panel.setHasShadow_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setLevel_(AppKit.NSStatusWindowLevel - 1)
        panel.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                     AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        view = SnapGuideView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), frame.size))
        view.zones = []
        view.highlight = -1
        panel.setContentView_(view)
        self._guide_panel, self._guide_view = panel, view

    def _show_guide(self):
        self._ensure_guide()
        screen = self._screen()
        frame = screen.frame() if screen is not None else NSRect(NSPoint(0, 0), NSSize(1440, 900))
        if self._guide_panel.frame() != frame:
            self._guide_panel.setFrame_display_(frame, True)
            self._guide_view.setFrame_(NSRect(NSPoint(0, 0), frame.size))
        visible = self._visible_frame()
        pill = self._panel.frame()
        size = (pill.size.width, pill.size.height)
        view_origin = (frame.origin.x, frame.origin.y)
        entries = []
        for zone in OVERLAY_POSITIONS:
            gx, gy = zone_origin(zone, size, visible)
            entries.append((zone, NSRect(NSPoint(gx - view_origin[0], gy - view_origin[1]), NSSize(size[0], size[1]))))
        self._guide_view.zones = entries
        self._guide_view.highlight = self._nearest_zone_index()
        self._guide_view.setNeedsDisplay_(True)
        self._guide_panel.orderFrontRegardless()

    def _nearest_zone_index(self):
        frame = self._panel.frame()
        zone = nearest_zone(self._pill_center(), (frame.size.width, frame.size.height), self._visible_frame())
        return OVERLAY_POSITIONS.index(zone)

    def _hide_guide(self):
        if self._guide_panel is not None:
            self._guide_panel.orderOut_(None)

    # -- drag ----------------------------------------------------------------

    def _drag_start(self, x, y):
        frame = self._panel.frame()
        self._drag = {'start_point': (x, y), 'origin': (frame.origin.x, frame.origin.y)}
        self._show_guide()

    def _drag_move(self, x, y):
        if self._drag is None:
            return
        frame = self._panel.frame()
        size = (frame.size.width, frame.size.height)
        origin = dragged_origin(self._drag['origin'], self._drag['start_point'], (x, y), size, self._visible_frame())
        self._panel.setFrameOrigin_(NSPoint(origin[0], origin[1]))
        if self._guide_view is not None:
            self._guide_view.highlight = self._nearest_zone_index()
            self._guide_view.setNeedsDisplay_(True)

    def _drag_end(self, x, y):
        if self._drag is None:
            return
        self._drag = None
        self._hide_guide()
        frame = self._panel.frame()
        size = (frame.size.width, frame.size.height)
        self._zone = nearest_zone(self._pill_center(), size, self._visible_frame())
        self._snap(animate=True)
        if self.on_position_change is not None and self._zone != self._reported_zone:
            self._reported_zone = self._zone
            self.on_position_change(self._zone)

    # -- configuration and actions -------------------------------------------

    def _dispatch_main(self, action):
        NSOperationQueue.mainQueue().addOperationWithBlock_(action)

    def configure(self, config, on_toggle=None, on_cancel=None, on_open_hub=None, on_position_change=None):
        self._always_show = config.always_show_overlay
        self._explicit_reveal = False
        self._shortcut = shortcut_label(config.hotkey)
        if on_toggle is not None:
            self.on_toggle = on_toggle
        if on_cancel is not None:
            self.on_cancel = on_cancel
        if on_open_hub is not None:
            self.on_open_hub = on_open_hub
        if on_position_change is not None:
            self.on_position_change = on_position_change
        zone = config.overlay_position if config.overlay_position in OVERLAY_POSITIONS else 'bottom-center'
        zone_changed = zone != self._zone
        self._zone = zone
        self._reported_zone = zone

        def apply():
            if zone_changed:
                self._snap(animate=True)
            self._render()

        self._dispatch_main(apply)

    def handle_action(self, action, payload=None):
        payload = payload or {}
        if action == 'ready':
            self._ready = True
            self._render()
        elif action == 'toggle' and self.on_toggle:
            self.on_toggle()
        elif action == 'cancel' and self.on_cancel:
            self.on_cancel()
        elif action == 'openHub' and self.on_open_hub:
            self.on_open_hub()
        elif action == 'resize':
            if self._drag is None:
                self._apply_size(payload.get('width', IDLE_SIZE[0]), payload.get('height', IDLE_SIZE[1]))
        elif action == 'hover':
            self._hovered = bool(payload.get('hovered'))
            self._animate_alpha(self._idle_alpha())
        elif action == 'dragStart':
            self._drag_start(float(payload.get('x', 0)), float(payload.get('y', 0)))
        elif action == 'dragMove':
            self._drag_move(float(payload.get('x', 0)), float(payload.get('y', 0)))
        elif action == 'dragEnd':
            self._drag_end(float(payload.get('x', 0)), float(payload.get('y', 0)))

    # -- state rendering -----------------------------------------------------

    def _render(self):
        visible = self._always_show or self._explicit_reveal or self._state != 'idle'
        if visible:
            self._panel.orderFrontRegardless()
        else:
            self._panel.orderOut_(None)
        self._is_visible = visible
        self._animate_alpha(self._idle_alpha())
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
