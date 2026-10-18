"""Windows and Linux native-webview host for the shared Fixo Flow product UI."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import logging
import queue
from pathlib import Path
import sys
import threading
import time
import webbrowser

from fixoflow.config import FixoflowConfig
from fixoflow.controls import DictationControls,shortcut_label
from fixoflow.core import FixoflowCoordinator
from fixoflow.input_listener import DesktopInput
from fixoflow.instance import InstanceLock
from fixoflow.storage.db import FixoflowDB
from fixoflow.ui.controller import HubController
from fixoflow.updates import UpdateService
from fixoflow.version import __version__


class DesktopHub(HubController):
    def __init__(self,config):
        self.config=config;self.db=FixoflowDB.get_instance();self.window=None
        for name in ('config_change','enable_shortcut','show_overlay','control_status','restart','shortcut_capture','cancel_capture','primary_mouse_capture','update_check','update_status','open_release'):
            setattr(self,'on_'+name,None)
    def _eval_js(self,script):
        if self.window:
            try:self.window.evaluate_js(script)
            except Exception:logging.getLogger(__name__).debug('UI not ready',exc_info=True)
    def show(self):self.window.show();self.window.restore()


class Bridge:
    def __init__(self,callback):self._callback=callback;self._lock=threading.RLock()
    def post(self,body):
        if not isinstance(body,dict) or not isinstance(body.get('action'),str):return False
        # One mutation at a time, just as Cocoa dispatches the bridge serially.
        with self._lock:
            self._callback(body['action'],body)
        return True


class DesktopApplication:
    def __init__(self,config,background=False,self_check=False,report=None):
        import webview
        self._audio_level=0.0
        self._captures=queue.SimpleQueue()
        self.config=config;self.hub=DesktopHub(config);self._closed=threading.Event();self._loaded=threading.Event();self._error='';self._self_check=self_check;self.check_passed=False;self.report=report;self.restarting=False
        self.coordinator=FixoflowCoordinator(config,enable_overlay=False)
        self.coordinator.recorder.on_level_callback=self.audio_level
        self.controls=DictationControls(self.coordinator,config)
        self.inputs=DesktopInput(config,self.controls)
        self.updates=UpdateService(on_change=lambda status:self.hub._eval_js('onUpdateData('+json.dumps(status)+');'))
        ui=Path(__file__).parent/'ui'
        self.hub.window=webview.create_window('Fixo Flow',str(ui/'hub.html'),js_api=Bridge(self.hub.handle_action),width=1040,height=740,min_size=(820,620),hidden=False,minimized=background)
        self.pill=webview.create_window('Fixo Flow dictation',str(ui/'overlay.html'),js_api=Bridge(self.pill_action),width=600,height=96,hidden=True,frameless=True,focus=False,on_top=True,resizable=False,background_color='#eee9fb',easy_drag=False)
        self.pill.events.loaded+=self.position_pill
        self.hub.window.events.loaded+=self.loaded
        self.hub.window.events.closing+=self.closing
        self.hub.on_config_change=self.apply_config
        self.hub.on_enable_shortcut=self.enable_shortcut
        self.hub.on_show_overlay=self.pill.show
        self.hub.on_control_status=self.status
        self.hub.on_shortcut_capture=self.capture
        self.hub.on_cancel_capture=self.inputs.cancel_capture
        self.hub.on_primary_mouse_capture=self.inputs.capture_primary
        self.hub.on_update_check=self.updates.check
        self.hub.on_update_status=self.updates.snapshot
        self.hub.on_open_release=lambda:webbrowser.open(self.updates.release_url()) if self.updates.release_url() else None
        self.hub.on_restart=self.restart

    def loaded(self):
        try:self._load_content()
        except Exception:
            logging.getLogger(__name__).exception('Desktop content initialization failed')
            if self._self_check:self.hub.window.destroy()

    def _load_content(self):
        if sys.stdout:print('Hub content loaded',flush=True)
        self._loaded.set()
        self.hub._eval_js("document.getElementById('appVersion').textContent="+json.dumps('Fixo Flow '+__version__)+';')
        self.hub.handle_action('getConfig',{});self.hub.handle_action('getDashboard',{});self.hub.handle_action('getUpdateStatus',{})
        self.hub._eval_js('onDesktopPlatform('+json.dumps('Windows' if sys.platform=='win32' else 'Linux')+');')
        if self._self_check:
            result=self.hub.window.evaluate_js("({views:document.querySelectorAll('.view-panel').length,logo:!!document.querySelector('img'),bridge:typeof window.pywebview.api.post})")
            # UI/model resolution check never activates input, audio or network.
            self.coordinator.stt.resolve_model_path()
            import numpy as np
            # Nonzero diagnostic tone reaches the actual decoder; exact silence
            # is deliberately short-circuited by the shared inference owner.
            self.coordinator.stt.transcribe((.01*np.sin(2*np.pi*440*np.arange(16000)/16000)).astype(np.float32))
            assert result['bridge']=='function' and result['views']==6,result
            self.check_passed=True
            evidence={'ui':'ok','platform':sys.platform,'version':__version__,'microphone_opened':False,'input_started':False,'local_inference':'executed'}
            if self.report:self.report.write_text(json.dumps(evidence))
            if sys.stdout:print(json.dumps(evidence),flush=True)
            self.hub.window.destroy()
        else:
            self.enable_shortcut()
            if self.config.always_show_overlay:self.pill.show()
            if self.config.check_updates_on_launch:self.updates.check()

    def restart(self):
        if self.controls.state!='IDLE':
            self.hub._eval_js("onSettingsResult(false,'Finish dictation before restarting.');")
            return
        self.restarting=True;self.hub.window.destroy()

    def closing(self):
        if not self.hub.close_model_packs():return False
        self._closed.set()
        # Shutdown is allowed to drain processing; never abandon audio on exit.
        self.inputs.stop();self.controls.shutdown();self.updates.close()
        try:self.pill.destroy()
        except Exception:pass
        return True

    def status(self):
        return {'state':self.controls.state,'shortcut':shortcut_label(self.config.hold_shortcut),'hands_free_shortcut':shortcut_label(self.config.hands_free_shortcut),'shortcut_active':self.inputs.active,'detail':self.coordinator.last_error or self._error}

    def enable_shortcut(self):
        try:self.inputs.start();self._error='';return None
        except Exception as error:self._error=str(error);return self._error

    def capture(self,field):
        if self.controls.state!='IDLE':raise RuntimeError('Finish dictation first.')
        error=self.enable_shortcut()
        if error:raise RuntimeError(error)
        self.inputs.begin_capture(lambda binding,message:self._captures.put({'field':field,'binding':binding,'message':message}))

    def apply_config(self,candidate):
        candidate.validate()
        if candidate.auto_install_updates:raise ValueError('Signed automatic installation is not configured for this preview.')
        if self.controls.state!='IDLE':raise RuntimeError('Finish dictation before saving settings.')
        if self.inputs.router.quarantined and self.inputs.router.pressed:raise RuntimeError('Release captured input before saving.')
        self.inputs.stop()
        def update():
            self.coordinator.apply_config(candidate)
            self.inputs.reconfigure();self.hub.config=self.config
        try:self.controls.configure(update)
        finally:self.enable_shortcut()
        self.position_pill()
        if candidate.always_show_overlay:self.pill.show()
        elif self.controls.state == 'IDLE':self.pill.hide()

    def audio_level(self,level):
        # Audio callback never waits for WebView or paints the screen.
        self._audio_level=float(level)

    def position_pill(self):
        import webview
        screen=webview.screens[0];width,height=screen.width,screen.height
        zone=self.config.overlay_position
        x=18 if zone=='bottom-left' else width-618 if zone=='bottom-right' else (width-600)//2
        y=18 if zone=='top-center' else height-132
        self.pill.move(max(0,int(x)),max(0,int(y)))

    def pill_action(self,action,payload):
        if action=='toggle':self.controls.toggle()
        elif action=='cancel':self.controls.cancel()
        elif action=='openHub':self.hub.show()
        elif action=='dragEnd':
            import webview
            screen=webview.screens[0];x=payload.get('x',screen.width/2);y=payload.get('y',screen.height)
            self.config.overlay_position='top-center' if y<screen.height/2 else 'bottom-left' if x<screen.width/3 else 'bottom-right' if x>2*screen.width/3 else 'bottom-center'
            self.config.save();self.position_pill()
        elif action=='ready':self.position_pill()

    def poll(self):
        previous=None
        while not self._closed.wait(0.2):
            if not self._loaded.is_set():continue
            self.inputs.expire_capture();status=self.status()
            while True:
                try:captured=self._captures.get_nowait()
                except queue.Empty:break
                self.hub._eval_js('onShortcutCaptured('+json.dumps(captured)+');')
            if status['state']=='RECORDING':
                try:self.pill.evaluate_js('setAudioLevel('+json.dumps(self._audio_level)+');')
                except Exception:pass
            serialized=json.dumps(status)
            if serialized!=previous:
                if status['state'] in {'RECORDING','PROCESSING'} or self.config.always_show_overlay:self.pill.show()
                elif status['state']=='IDLE':self.pill.hide()
                previous=serialized;self.hub._eval_js('onControlStatus('+serialized+');')
                try:self.pill.evaluate_js('updateControl('+json.dumps({'state':{'IDLE':'idle','RECORDING':'listening','PROCESSING':'processing'}[status['state']],'message':status['detail'] or ('Listening…' if status['state']=='RECORDING' else 'Transcribing…' if status['state']=='PROCESSING' else 'Ready to dictate')})+');')
                except Exception:pass


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--background',action='store_true');parser.add_argument('--self-check',action='store_true');parser.add_argument('--check-report',type=Path);args=parser.parse_args(argv)
    from logging.handlers import RotatingFileHandler
    log_dir=FixoflowConfig.get_config_path().parent/'logs';log_dir.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(log_dir/'fixoflow.log',maxBytes=2_000_000,backupCount=2,encoding='utf-8')])
    if sys.stdout:print('Importing native webview',flush=True)
    import webview
    lock=InstanceLock(FixoflowConfig.get_config_path().parent/'desktop.lock')
    if not args.self_check and not lock.acquire():
        raise SystemExit('Fixo Flow is already running. Open its taskbar window.')
    try:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('FixoFlow.Desktop')
        if sys.stdout:print('Creating desktop windows',flush=True)
        app=DesktopApplication(FixoflowConfig.load(),args.background,args.self_check,args.check_report)
        worker=threading.Thread(target=app.poll,name='FixoFlow-status',daemon=True);worker.start()
        icon=Path(__file__).parent/'ui/assets'/('flow-fold.ico' if sys.platform=='win32' else 'flow-fold.png')
        if sys.stdout:print('Starting native event loop',flush=True)
        webview.start(gui='edgechromium' if sys.platform=='win32' else 'gtk',icon=str(icon),private_mode=True,debug=False)
        app._closed.set();worker.join(timeout=2)
        if args.self_check and not app.check_passed:raise SystemExit('Desktop self-check did not complete')
    finally:lock.close()
    if app.restarting:
        import subprocess
        command=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,'-m','fixoflow.desktop']
        subprocess.Popen(command,start_new_session=True)

if __name__=='__main__':main()
