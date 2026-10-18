#!/usr/bin/env python3
"""Exercise the real Cocoa/WebKit hub against an isolated local database.

No microphone, global shortcut, clipboard writes, permission prompts, or user
preference writes. --preview leaves the isolated empty-state window open.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
from types import SimpleNamespace
from fixoflow.shortcuts import ShortcutRouter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import AppKit
from Foundation import NSDate, NSRunLoop, NSObject
from fixoflow.config import FixoflowConfig
from fixoflow.storage.db import FixoflowDB
from fixoflow.ui.hub import HubManager


def pump(seconds=.12):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(seconds))


def evaluate(view, script):
    results = []
    view.evaluateJavaScript_completionHandler_(
        script, lambda result, error: results.append((result, error)))
    deadline = time.monotonic() + 8
    while not results and time.monotonic() < deadline:
        pump(.02)
    assert results and results[0][1] is None, results
    return results[0][0]


def check(hub):
    view = hub._webview
    deadline = time.monotonic() + 10
    while view.isLoading() and time.monotonic() < deadline:
        pump(.05)
    pump(.3)
    resources = json.loads(evaluate(view, """JSON.stringify({
      brand:[...document.images].every(i => i.complete && i.naturalWidth > 0),
      font:document.fonts.check('14px Geist'),
      fontCount:document.fonts.size,
      palette:getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim(),
      panels:document.querySelectorAll('.view-panel').length
    })"""))
    assert resources == {'brand': True, 'font': True, 'fontCount': 1,
                         'palette': '#eee9fb', 'panels': 6}, resources
    for tab in ('dashboard', 'insights', 'style', 'history', 'dictionary', 'settings'):
        evaluate(view, f"switchTab('{tab}')")
        pump()
        result = json.loads(evaluate(view, """JSON.stringify({
          visible:document.querySelectorAll('.view-panel:not(.hidden)').length,
          selected:document.querySelector('.nav-btn.active').textContent.trim(),
          overflow:document.querySelector('.content-area').scrollWidth > document.querySelector('.content-area').clientWidth
        })"""))
        assert result['visible'] == 1 and not result['overflow'], (tab, result)
    evaluate(view, "switchTab('dictionary'); toggleAddWordModal(); document.getElementById('newPhrase').value='maya desai'; document.getElementById('newReplacement').value='Maya Desai'; saveNewWord();")
    pump()
    assert hub.db.get_dictionary()[0]['replacement'] == 'Maya Desai'
    assert 'Maya Desai' in evaluate(view, "document.getElementById('dictionaryList').textContent")
    # Render real database text as text, including HTML-like strings.
    hub.db.record_session('ui-check', '<b>Literal words</b>', 'Mail', 2.0, 40.0)
    evaluate(view, "switchTab('history')")
    pump()
    assert '<b>Literal words</b>' in evaluate(view, "document.getElementById('historyList').textContent")
    assert evaluate(view, "document.querySelector('#historyList b') === null")
    evaluate(view, "document.getElementById('historySearch').value='no-such-transcript'; filterHistory();")
    pump()
    assert 'No matching' in evaluate(view, "document.getElementById('historyList').textContent")
    evaluate(view, "switchTab('style'); document.querySelector('#styleGrid [aria-checked=true]').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));")
    assert evaluate(view, "document.querySelector('#styleGrid [aria-checked=true] .style-name').textContent") == 'Concise'
    assert evaluate(view, "document.getElementById('stylePreview').textContent") == "I can't wait to share the idea."
    evaluate(view, "selectOutputStyle('professional'); saveStyle();")
    pump()
    assert hub.config.output_style == 'professional'
    assert 'Preferences applied' in evaluate(view, "document.getElementById('styleResult').textContent")
    evaluate(view, "switchTab('settings'); selectPillPosition('top-center'); startShortcutRecording('hold_shortcut');")
    pump()
    hub._check_router.input(('keyboard',62),'ctrl_r',True)
    hub._check_router.input(('keyboard',62),'ctrl_r',False)
    pump()
    assert 'Right' in evaluate(view, "document.getElementById('holdShortcutLabel').textContent")
    evaluate(view, "startShortcutRecording('hands_free_shortcut');")
    pump()
    hub._check_router.input(('mouse',4),'mouse:4',True)
    hub._check_router.input(('mouse',4),'mouse:4',False)
    pump()
    evaluate(view, "saveSettings();")
    pump()
    assert hub.config.overlay_position == 'top-center', evaluate(view, "document.getElementById('settingsResult').textContent")
    assert hub.config.hold_shortcut['keys'] == ['ctrl_r']
    assert hub.config.hands_free_shortcut['keys'] == ['mouse:4']
    assert evaluate(view, "document.getElementById('cfgAutoInstall').disabled")
    evaluate(view, "switchTab('dashboard');")
    pump()
    assert '<b>Literal words</b>' in evaluate(view, "document.getElementById('recentHistory').textContent")
    assert evaluate(view, "document.querySelector('#recentHistory b') === null")
    assert evaluate(view, "document.getElementById('permissionAccessibility').textContent") == 'Needed'
    assert evaluate(view, "document.getElementById('permissionMicrophone').textContent") == 'Not requested'
    # Check the actual content viewport at the minimum supported window size.
    hub._window.setContentSize_(AppKit.NSMakeSize(820, 600))
    pump()
    for tab in ('dashboard', 'insights', 'style', 'history', 'dictionary', 'settings'):
        evaluate(view, f"switchTab('{tab}')")
        pump(.05)
        assert evaluate(view, "document.querySelector('.content-area').scrollWidth <= document.querySelector('.content-area').clientWidth"), tab
    print(json.dumps({'native_webkit': 'ok', 'panels': 6, 'local_font_and_logo': 'ok',
                      'dictionary': 'ok', 'history_search_and_escaping': 'ok',
                      'style_and_settings_bridge': 'ok', 'minimum_window': 'ok',
                      'microphone_opened': False, 'user_data_modified': False}))
    print('VERDICT: PASS', flush=True)


class PreviewWindowDelegate(NSObject):
    def windowWillClose_(self, notification):
        AppKit.NSApp.stop_(None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    logo = Path(__file__).resolve().parents[1] / 'fixoflow/ui/assets/flow-fold.png'
    app.setApplicationIconImage_(AppKit.NSImage.alloc().initWithContentsOfFile_(str(logo)))
    with tempfile.TemporaryDirectory(prefix='fixoflow-ui-check-') as directory:
        FixoflowDB._instance = FixoflowDB(Path(directory) / 'check.sqlite')
        with patch.object(FixoflowConfig, 'load', return_value=FixoflowConfig()), \
             patch('fixoflow.ui.hub.permission_snapshot', return_value={'accessibility':False,'input':False,'microphone':'not determined'}):
            hub = HubManager()
            assert hub._window is not None and hub._webview is not None
            def apply(candidate):
                hub.config = candidate
            hub.on_config_change = apply
            controls = SimpleNamespace(state='IDLE')
            hub._check_router = ShortcutRouter(hub.config.hold_shortcut,hub.config.hands_free_shortcut,controls)
            def capture(field):
                hub._check_router.begin_capture(lambda binding,message:hub._eval_js('onShortcutCaptured('+json.dumps({'field':field,'binding':binding,'message':message})+');'))
            hub.on_shortcut_capture = capture
            hub.on_cancel_capture = hub._check_router.cancel_capture
            hub.on_update_status = lambda: {'version':'0.1.0','state':'idle','message':'Check for updates.','auto_install_available':False}
            hub.on_control_status = lambda: {'state':'IDLE','shortcut':'⌃ Space','shortcut_active':False,
                'detail':'Use the floating bar, or check permissions in Settings to enable your shortcut.'}
            if args.preview:
                preview_delegate = PreviewWindowDelegate.alloc().init()
                hub._window.setDelegate_(preview_delegate)
                hub.show()
                print('Isolated native preview: no recording or user settings writes.', flush=True)
                app.run()
            else:
                check(hub)
                hub._window.orderOut_(None)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
