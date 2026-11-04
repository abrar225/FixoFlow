"""Safe setup recording, tray choices, and clipboard confirmation boundaries."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fixoflow.config import FixoflowConfig
from fixoflow.controls import DictationControls
from fixoflow.onboarding import candidate, snapshot
from fixoflow.tray import choice_config, entries, DesktopTray


class Executor:
    def __init__(self): self.work=[]
    def submit(self,fn,*args): self.work.append((fn,args))
    def drain(self):
        while self.work:
            fn,args=self.work.pop(0);fn(*args)


def interaction():
    coordinator=SimpleNamespace(state='IDLE',last_error='',maintenance_busy=False)
    def start(cancellation=None):coordinator.state='RECORDING'
    def stop(auto_paste):coordinator.state='IDLE';return 'Practice words'
    coordinator.start_recording=Mock(side_effect=start)
    coordinator.stop_and_process=Mock(side_effect=stop)
    coordinator.cancel_recording=Mock(side_effect=lambda:setattr(coordinator,'state','IDLE'))
    executor=Executor()
    return DictationControls(coordinator,FixoflowConfig(),executor),coordinator,executor


def test_practice_cannot_paste_even_if_stopped_by_global_toggle():
    controls,coordinator,executor=interaction();results=[]
    controls.toggle_preview(lambda text,error:results.append((text,error)));executor.drain()
    controls.toggle();executor.drain()
    coordinator.stop_and_process.assert_called_once_with(auto_paste=False)
    assert results==[('Practice words','')] and controls.state=='IDLE'
    controls.toggle();executor.drain();controls.toggle();executor.drain()
    assert coordinator.stop_and_process.call_args.kwargs['auto_paste'] is True


def test_dismissing_setup_cannot_cancel_unrelated_dictation():
    controls,coordinator,executor=interaction();controls.toggle();executor.drain()
    controls.cancel_preview();executor.drain()
    assert controls.state=='RECORDING';coordinator.cancel_recording.assert_not_called()
    with pytest.raises(RuntimeError,match='Finish'):controls.toggle_preview(Mock())


def test_failed_practice_start_reports_error_and_releases_ownership():
    controls,coordinator,executor=interaction();coordinator.start_recording=Mock(side_effect=RuntimeError('missing mic'))
    result=Mock();controls.toggle_preview(result);executor.drain()
    assert controls.state=='IDLE' and not controls._preview_active
    assert result.call_args.args[0]=='' and 'microphone' in result.call_args.args[1]


def test_setup_progress_is_separate_from_permission_grants():
    config=FixoflowConfig();advanced=candidate(config,3)
    assert snapshot(advanced)['step']==3 and not snapshot(advanced)['completed']
    assert not config.onboarding_step
    with pytest.raises(ValueError):candidate(config,True)
    with pytest.raises(ValueError):candidate(config,2,True)
    assert snapshot(candidate(config,5,True))['completed']


def test_model_tray_choice_adapts_language_to_capabilities():
    from fixoflow.models.catalog import runtime_backend
    config=FixoflowConfig()
    multilingual='catalog:base-multi-'+runtime_backend()
    spanish=choice_config(choice_config(config,'selectModel',multilingual),'selectLanguage','es')
    assert spanish.language=='es'
    english=choice_config(spanish,'selectModel','catalog:base-en-'+runtime_backend())
    assert english.language=='en'
    with pytest.raises(ValueError):choice_config(config,'selectLanguage','hi')


def test_tray_processing_prevents_new_recording_and_exposes_cancel():
    menu=entries(FixoflowConfig(),{'state':'PROCESSING'})
    assert not next(item for item in menu if item.action=='toggle').enabled
    assert next(item for item in menu if item.action=='cancel').enabled
    assert next(item for item in menu if item.action=='openRecovery').enabled
    assert not next(item for item in menu if item.action=='restoreClipboard').enabled
    assert next(item for item in menu if item.label.startswith('Microphone:')).children


def test_missing_tray_menu_never_allows_hiding_window():
    backend=SimpleNamespace(Icon=SimpleNamespace(HAS_MENU=False))
    tray=DesktopTray(lambda:(),Mock(),backend=backend)
    tray.start()
    assert not tray.can_hide and 'no menu' in tray.error


def test_clipboard_restore_requires_explicit_confirmation(monkeypatch):
    from fixoflow.ui.controller import HubController
    import fixoflow.platform as native
    restore=Mock(return_value={'pending':False,'restored':True,'message':'Restored'})
    monkeypatch.setattr(native,'restore_previous_clipboard',restore)
    monkeypatch.setattr(native,'clipboard_restore_status',lambda:{'pending':True,'message':'Confirm paste'})
    hub=HubController();hub._eval_js=Mock()
    hub.handle_action('restorePreviousClipboard',{'confirmed':'true'})
    restore.assert_not_called()
    hub.handle_action('restorePreviousClipboard',{'confirmed':True})
    restore.assert_called_once_with(insertion_confirmed=True)


def test_refused_desktop_restart_does_not_latch_exit_or_relaunch_intent():
    """A refused restart must leave ordinary close-to-tray behavior usable."""
    from fixoflow.desktop_app import DesktopApplication
    app=DesktopApplication.__new__(DesktopApplication)
    app.config=FixoflowConfig()
    app.controls=SimpleNamespace(state='IDLE')
    app.tray=SimpleNamespace(can_hide=True)
    app._quitting=False
    app.restarting=False
    window=SimpleNamespace(hide=Mock())
    app.hub=SimpleNamespace(window=window,close_model_packs=Mock(return_value=False),_eval_js=Mock())
    window.destroy=Mock(side_effect=app.closing)
    app.restart()
    assert not app.restarting and not app._quitting
    assert app.closing() is False
    window.hide.assert_called_once()


def test_diagnostic_desktop_close_exits_even_when_tray_is_ready(monkeypatch):
    """The installed --tray-check must finish instead of hiding its window."""
    import threading
    import fixoflow.platform as native
    from fixoflow.desktop_app import DesktopApplication
    discard=Mock()
    monkeypatch.setattr(native,'discard_previous_clipboard',discard)
    app=DesktopApplication.__new__(DesktopApplication)
    app.config=FixoflowConfig()
    app._self_check=True
    app._quitting=False
    app._closed=threading.Event()
    app.hub=SimpleNamespace(window=SimpleNamespace(hide=Mock()),close_model_packs=Mock(return_value=True))
    app.inputs=SimpleNamespace(stop=Mock())
    app.controls=SimpleNamespace(shutdown=Mock())
    app.updates=SimpleNamespace(close=Mock())
    app.tray=SimpleNamespace(can_hide=True,close=Mock())
    app.pill=SimpleNamespace(destroy=Mock())
    assert app.closing() is True and app._closed.is_set()
    app.hub.window.hide.assert_not_called()
    app.controls.shutdown.assert_called_once()
    app.tray.close.assert_called_once()
    discard.assert_called_once()
