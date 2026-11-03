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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixoflow.shortcuts import ShortcutRouter
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
    assert not evaluate(view,"document.getElementById('onboardingBackdrop').classList.contains('hidden')")
    assert evaluate(view,"document.querySelectorAll('[data-setup-step]').length")==6
    evaluate(view,'advanceOnboarding(1);');pump()
    assert hub.config.onboarding_step==1
    evaluate(view,'closeOnboarding();openOnboarding();');pump()
    assert 'Step 2 of 6' in evaluate(view,"document.getElementById('onboardingProgress').textContent")
    for _ in range(4):evaluate(view,'advanceOnboarding(1);');pump()
    assert hub.config.onboarding_step==5
    evaluate(view,'advanceOnboarding(1);');pump()
    assert hub.config.onboarding_version==1
    assert evaluate(view,"document.getElementById('onboardingBackdrop').classList.contains('hidden')")
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
    evaluate(view, "selectOutputStyle('professional');")
    pump()
    pump(1.1)
    assert hub.config.output_style == 'professional'
    assert 'Saved automatically' in evaluate(view, "document.getElementById('styleResult').textContent")
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
    pump(1.1)
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
    evaluate(view, "switchTab('settings')")
    pump()
    assert evaluate(view, "document.getElementById('cfgLanguage').options.length") == 1
    assert evaluate(view, "document.getElementById('cfgLanguage').value") == 'en'
    assert evaluate(view, "document.getElementById('cfgLanguage').disabled")
    assert 'compatible multilingual model' in evaluate(view, "document.getElementById('languageAvailability').textContent")
    assert not evaluate(view, "document.querySelector('[onclick*=installModelPack]') !== null")
    assert not evaluate(view, "document.getElementById('cfgSpokenCommands').checked")
    evaluate(view, "post('autosaveConfig',{request_id:9999,config:{language:'hi',model_name:'mlx-community/whisper-base.en-mlx'}})")
    pump(.2)
    assert hub.config.language == 'en'
    # Model changes and their language capabilities save as one valid choice.
    for model in ['catalog:base-multi-mlx','catalog:parakeet-v3-onnx']:
        evaluate(view,"{let option=element('option','',"+json.dumps(model)+");option.value="+json.dumps(model)+";document.getElementById('cfgModel').append(option);chooseModel(option.value);}")
        pump(.2)
        if 'base-multi' in model:
            assert evaluate(view,"document.getElementById('cfgLanguage').options.length")==100
            evaluate(view,"document.getElementById('cfgLanguage').value='es';document.getElementById('cfgLanguage').dispatchEvent(new Event('change'));")
        else:
            assert evaluate(view,"document.getElementById('cfgLanguage').value")=='auto'
            assert evaluate(view,"document.getElementById('cfgLanguage').disabled")
        pump(1.1)
        assert hub.config.model_name==model
        assert hub.config.language==('es' if 'base-multi' in model else None)
    evaluate(view,"chooseModel('mlx-community/whisper-base.en-mlx');");pump(1.2)
    assert hub.config.language=='en'
    evaluate(view,"onLanguageData({model_name:'catalog:base-multi-mlx',languages:[{value:'es',label:'Spanish'}],message:'Stale reply'});")
    assert evaluate(view,"document.getElementById('cfgLanguage').value")=='en'
    evaluate(view,"onClipboardStatus({pending:true,message:'Test snapshot'});confirmClipboardRestore();")
    assert not evaluate(view,"document.getElementById('clipboardConfirmation').classList.contains('hidden')")
    evaluate(view,"document.getElementById('clipboardConfirmation').classList.add('hidden');")
    # A late acknowledgement cannot replace a newer style selection.
    evaluate(view, "window.realPreferenceResult=onPreferencesResult; window.delayedPreferenceResult=null; onPreferencesResult=result=>{window.delayedPreferenceResult=result}; selectOutputStyle('natural');")
    pump(1.1)
    assert hub.config.output_style == 'natural'
    evaluate(view, "selectOutputStyle('concise'); onPreferencesResult=window.realPreferenceResult; onPreferencesResult(window.delayedPreferenceResult);")
    assert evaluate(view, "styleSelection") == 'concise'
    pump(1.1)
    assert hub.config.output_style == 'concise'
    # Coalesced changes wait for active dictation; no manual save is involved.
    evaluate(view, "onControlStatus({state:'RECORDING',shortcut_active:false}); document.getElementById('cfgSounds').checked=false; document.getElementById('cfgSounds').dispatchEvent(new Event('change'));")
    pump(1.1)
    assert hub.config.sound_enabled
    assert 'Waiting' in evaluate(view, "document.getElementById('settingsResult').textContent")
    evaluate(view, "onControlStatus({state:'IDLE',shortcut_active:false});")
    pump(.8)
    assert not hub.config.sound_enabled
    assert not hub.preferences_pending
    evaluate(view, "document.getElementById('cfgStartAtLogin').checked=false; document.getElementById('cfgStartAtLogin').dispatchEvent(new Event('change'));")
    pump(1.1)
    assert not hub.config.start_at_login
    assert evaluate(view, "document.querySelectorAll('.save-button').length") == 0
    # A failed apply is visible, retains the choice and supports explicit retry.
    apply_preferences=hub.on_config_change
    hub.on_config_change=lambda candidate: (_ for _ in ()).throw(OSError('Test disk unavailable'))
    evaluate(view, "selectOutputStyle('professional');")
    pump(1.1)
    assert hub.config.output_style == 'concise'
    assert 'Not saved' in evaluate(view, "document.getElementById('styleResult').textContent")
    assert not evaluate(view, "document.querySelector('[data-settings-retry]').hidden")
    hub.on_config_change=apply_preferences
    evaluate(view, "retryPreferences();")
    pump(.2)
    assert hub.config.output_style == 'professional' and not hub.preferences_pending
    # OS status may briefly lag a just-applied startup request.
    evaluate(view, "onStartupData({supported:true,enabled:true,approval:false,pending:true,requested:false,message:'Waiting for system confirmation'});")
    assert not evaluate(view, "document.getElementById('cfgStartAtLogin').checked")
    pump(.7)
    assert not evaluate(view, "document.getElementById('cfgStartAtLogin').checked")
    # Page through the real database, then search beyond the first page.
    for i in range(55):hub.db.record_session('raw', f'Page item {i}', 'Editor', 1, 1)
    evaluate(view, "document.getElementById('historySearch').value=''; switchTab('history')")
    pump()
    assert evaluate(view, "historyItems.length") == 50
    assert not evaluate(view, "document.getElementById('historyMore').hidden")
    evaluate(view, "document.getElementById('historyMore').click()")
    pump()
    assert evaluate(view, "historyItems.length") == 56
    assert evaluate(view, "document.getElementById('historyMore').hidden")
    for i in range(105):hub.db.upsert_word(f'page word {i}', f'Replacement {i}')
    evaluate(view, "switchTab('dictionary')")
    pump()
    assert evaluate(view, "document.querySelectorAll('#dictionaryList .list-item').length") == 100
    evaluate(view, "document.getElementById('dictionaryMore').click()")
    pump()
    assert evaluate(view, "document.querySelectorAll('#dictionaryList .list-item').length") == 106
    # Exercise correction proposal/approval/forget through the real WebKit bridge.
    sid = hub.db.begin_session('Editor','test.editor','test-model','en','writing')
    hub.db.record_session('Y is this failing?', 'Y is this failing?', 'Editor',1,1,
                          mode='writing', session_id=sid)
    hub.db.update_session(sid,status='completed',delivery_status='dispatch_sent')
    item = next(row for row in hub.db.get_history() if row['id'] == sid)
    evaluate(view, 'switchTab("history"); openCorrectionEditor('+json.dumps(item)+');')
    evaluate(view, "document.getElementById('correctedTranscript').value='<b>Why is this failing?</b>'; proposeCorrection();")
    pump()
    assert hub.db.get_corrections()[0]['state'] == 'proposed'
    assert hub.db.apply_approved_correction('Y is this failing?','test.editor','en','writing')[0] == 'Y is this failing?'
    assert evaluate(view, "document.querySelector('#correctionMemory b') === null")
    assert 'dispatch_sent' in evaluate(view, "document.getElementById('sessionJournal').textContent")
    evaluate(view, "document.querySelector('#correctionMemory button').click()")
    pump()
    assert hub.db.get_corrections()[0]['state'] == 'approved'
    assert hub.db.apply_approved_correction('Y is this failing?','test.editor','en','writing')[0] == '<b>Why is this failing?</b>'
    evaluate(view, "document.querySelector('#correctionMemory .delete').click(); closeCorrectionEditor();")
    pump()
    assert not hub.db.get_corrections()
    # Playback reads only an owned synthetic fixture; never opens audio output.
    import wave
    audio = hub.db.db_path.parent/'session_20261102_120000_123456.wav'
    with wave.open(str(audio),'wb') as capture:
        capture.setnchannels(1);capture.setsampwidth(2);capture.setframerate(16000)
        capture.writeframes(b'\0\0'*160)
    playback_id = hub.db.record_session('test','test','Editor',.01,1,audio_path=str(audio))
    hub.db.register_session_artifact(audio,audio.parent)
    evaluate(view, 'loadHistoryAudio('+json.dumps(playback_id)+');')
    pump()
    assert evaluate(view,"document.getElementById('historyAudio').src.startsWith('data:audio/wav;base64,')")
    evaluate(view, 'stopHistoryAudio();')
    assert evaluate(view,"document.getElementById('historyAudio').getAttribute('src') === null")
    # Device-list rendering must preserve a saved selection if hardware is gone.
    selection = json.dumps(['Test Audio','USB Mic'])
    evaluate(view, 'onInputDeviceData([], "", '+json.dumps(selection)+');')
    assert evaluate(view,"document.getElementById('cfgInputDevice').value") == selection
    evaluate(view,'onInputDeviceData([], "", "");')
    # Theme controls alter real WebKit tokens and are saved through normal autosave.
    evaluate(view,"switchTab('settings'); document.getElementById('cfgTheme').value='dark'; document.getElementById('cfgTheme').dispatchEvent(new Event('change'));")
    pump(1.1)
    assert hub.config.theme=='dark'
    assert evaluate(view,"getComputedStyle(document.documentElement).getPropertyValue('--canvas').trim()")!='#eee9fb'
    evaluate(view,"document.getElementById('cfgTheme').value='light'; document.getElementById('cfgTheme').dispatchEvent(new Event('change'));")
    pump(1.1)
    assert hub.config.theme=='light'
    evaluate(view,"onServiceData({microphone:{state:'idle',level:0,message:'No check running'},busy:false,models:[{compatible:true,id:'test-model',name:'Test English',download_bytes:1000000,purpose:'Diagnostic candidate',state:'absent',message:'Explicit download',installed:false,model_name:'catalog:test-model'}]});")
    assert 'Test English' in evaluate(view,"document.getElementById('catalogModels').textContent")
    assert evaluate(view,"document.querySelector('#catalogModels button').textContent")=='Download model'
    evaluate(view,"onRecoveryData([{id:'test-recovery',app_name:'Editor',status:'cancelled',started_at:'2026-11-02T12:00:00'}]);")
    assert 'Retry into History' in evaluate(view,"document.getElementById('recoveryInbox').textContent")
    evaluate(view, "onPermissionData({platform:'Windows',microphone:'unknown',accessibility:null,input:null})")
    assert evaluate(view, "getComputedStyle(document.getElementById('permissionAccessibility').closest('.permission-card')).display") == 'none'
    assert 'Windows' in evaluate(view, "document.getElementById('permissionStatus').textContent")
    # Check the actual content viewport at the minimum supported window size.
    hub._window.setContentSize_(AppKit.NSMakeSize(820, 600))
    pump()
    for tab in ('dashboard', 'insights', 'style', 'history', 'dictionary', 'settings'):
        evaluate(view, f"switchTab('{tab}')")
        pump(.05)
        assert evaluate(view, "document.querySelector('.content-area').scrollWidth <= document.querySelector('.content-area').clientWidth"), tab
    print(json.dumps({'native_webkit': 'ok', 'panels': 6, 'local_font_and_logo': 'ok',
                      'dictionary': 'ok', 'history_search_and_escaping': 'ok',
                      'debounced_autosave_busy_retry_and_late_ack': 'ok', 'startup_toggle_isolated': 'ok', 'minimum_window': 'ok',
                      'language_and_commands': 'ok', 'history_and_dictionary_paging':'ok', 'desktop_permission_visibility':'ok',
                      'correction_approval_forget_and_literal_rendering':'ok', 'session_journal':'ok',
                      'owned_audio_playback_without_output':'ok', 'microphone_selection_rendering':'ok',
                      'guided_setup_resume_and_finish':'ok', 'model_aware_spanish_and_parakeet_auto_selection':'ok', 'stale_language_reply_protection':'ok', 'clipboard_confirmation_rendering':'ok', 'microphone_opened': False, 'user_data_modified': False}))
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
             patch('fixoflow.ui.controller.permission_snapshot', return_value={'accessibility':False,'input':False,'microphone':'not determined'}), \
             patch('fixoflow.model_packs.ModelPackManager', return_value=SimpleNamespace(snapshot=lambda: {'state':'ready','message':'Installed test pack'},close=lambda **kwargs:True)):
            hub = HubManager()
            assert hub._window is not None and hub._webview is not None
            def apply(candidate, **kwargs):
                candidate.validate_product()
                hub.config = candidate
            hub.on_config_change = apply
            hub.on_startup_status = lambda: {'supported':True,'enabled':hub.config.start_at_login,'approval':False,'message':'Isolated startup preview'}
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
