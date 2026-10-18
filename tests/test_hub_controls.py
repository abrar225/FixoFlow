import json
from pathlib import Path
from unittest.mock import Mock

from fixoflow.config import FixoflowConfig
from fixoflow.ui import hub


def manager():
    ui = hub.HubManager.__new__(hub.HubManager)
    ui.config = FixoflowConfig(initial_prompt='Keep the selected prompt')
    ui._eval_js = Mock()
    ui.on_control_status = lambda: {'state':'IDLE','shortcut_active':False}
    ui.on_restart = None
    return ui


def test_restart_action_replaces_the_process():
    ui = manager()
    restarts = []
    ui.on_restart = lambda: restarts.append(True)
    ui.handle_action('restartApp', {})
    assert restarts == [True]
    assert 'Restarting' in ui._eval_js.call_args.args[0]


def test_restart_without_app_is_reported_not_silently_ignored():
    ui = manager()
    ui.handle_action('restartApp', {})
    assert 'onSettingsResult(false' in ui._eval_js.call_args.args[0]


def test_pill_position_passes_into_saved_preferences():
    ui = manager()
    changes = []
    ui.on_config_change = lambda candidate: changes.append(candidate)
    ui.handle_action('saveConfig', {'config': {'overlay_position': 'top-center'}})
    assert len(changes) == 1 and changes[0].overlay_position == 'top-center'


def test_output_style_passes_into_saved_preferences():
    ui = manager()
    changes = []
    ui.on_config_change = lambda candidate: changes.append(candidate)
    ui.handle_action('saveConfig', {'config': {'output_style': 'concise'}})
    assert len(changes) == 1 and changes[0].output_style == 'concise'
    assert changes[0].initial_prompt == 'Keep the selected prompt'


def test_invalid_output_style_is_rejected_without_applying():
    ui = manager()
    ui.on_config_change = Mock()
    ui.handle_action('saveConfig', {'config': {'output_style': 'shakespearean'}})
    ui.on_config_change.assert_not_called()
    assert 'onSettingsResult(false' in ui._eval_js.call_args.args[0]


def test_insights_publish_streak_today_fixes_and_apps():
    import tempfile
    from fixoflow.storage.db import FixoflowDB
    with tempfile.TemporaryDirectory() as tmpdir:
        ui = manager()
        ui.db = FixoflowDB(Path(tmpdir) / 'insights.sqlite')
        ui.db.record_session('a', 'one two three', 'Mail', 2.0, 40.0, fixes_polish=2, fixes_vocab=1)
        ui.handle_action('getInsights', {})
        [payload] = [call.args[0] for call in ui._eval_js.call_args_list
                     if call.args[0].startswith('onInsightsData(')]
        data = json.loads(payload[len('onInsightsData('):-2])
        assert data['total']['total_words'] == 3 and data['total']['total_sessions'] == 1
        assert data['streak']['current'] == 1 and data['streak']['active_days'] == 1
        assert data['today']['total_words'] == 3
        assert data['fixes']['polish_fixes'] == 2 and data['fixes']['vocab_fixes'] == 1
        assert data['apps'][0]['app_name'] == 'Mail'
        assert len(data['week']) == 7 and data['week'][-1]['is_today']
        assert isinstance(data['user'], str)


def test_invalid_pill_position_is_rejected_without_applying():
    ui = manager()
    ui.on_config_change = Mock()
    ui.handle_action('saveConfig', {'config': {'overlay_position': 'middle-left'}})
    ui.on_config_change.assert_not_called()
    assert 'onSettingsResult(false' in ui._eval_js.call_args.args[0]


def test_new_preferences_preserve_unexposed_settings():
    ui = manager()
    changes = []
    ui.on_config_change = lambda candidate: changes.append(candidate)
    ui.handle_action('saveConfig', {'config': {'always_show_overlay': False, 'sound_enabled':False,
         'check_updates_on_launch':False, 'initial_prompt':'unexpected replacement'}})
    assert len(changes) == 1
    cfg = changes[0]
    assert cfg.always_show_overlay is False
    assert cfg.sound_enabled is False
    assert cfg.check_updates_on_launch is False
    assert cfg.initial_prompt == 'Keep the selected prompt'


def test_invalid_toggle_value_is_rejected_without_applying():
    ui = manager()
    ui.on_config_change = Mock()
    ui.handle_action('saveConfig', {'config':{'always_show_overlay':'false'}})
    ui.on_config_change.assert_not_called()
    assert 'onSettingsResult(false' in ui._eval_js.call_args.args[0]


def test_retry_publishes_current_permissions_even_when_shortcut_fails(monkeypatch):
    ui = manager()
    ui.on_enable_shortcut = Mock(return_value='Input Monitoring needed')
    monkeypatch.setattr('fixoflow.ui.controller.permission_snapshot',
                        lambda: {'accessibility':True,'input':False,'microphone':'authorized'})
    ui.handle_action('enableShortcut', {})
    messages = [call.args[0] for call in ui._eval_js.call_args_list]
    assert any('onSettingsResult(false' in s and 'Input Monitoring needed' in s for s in messages)
    permissions = next(s for s in messages if s.startswith('onPermissionData('))
    assert json.loads(permissions[len('onPermissionData('):-2]) == {'accessibility':True,'input':False,'microphone':'authorized'}
    assert any(s.startswith('onControlStatus(') for s in messages)


def test_successful_enable_reports_success(monkeypatch):
    ui = manager()
    ui.on_enable_shortcut = Mock(return_value=None)
    monkeypatch.setattr('fixoflow.ui.controller.permission_snapshot',
                        lambda: {'accessibility':True,'input':True,'microphone':'authorized'})
    ui.handle_action('enableShortcut', {})
    messages = [call.args[0] for call in ui._eval_js.call_args_list]
    assert any('onSettingsResult(true' in s for s in messages)


def test_request_permissions_triggers_system_prompts(monkeypatch):
    ui = manager()
    requested = []
    monkeypatch.setattr('fixoflow.ui.controller.request_all_permissions',
                        lambda: requested.append(True) or {'accessibility':False,'input':False,'microphone':'not determined'})
    ui.handle_action('requestPermissions', {})
    assert requested == [True]
    messages = [call.args[0] for call in ui._eval_js.call_args_list]
    permissions = next(s for s in messages if s.startswith('onPermissionData('))
    assert json.loads(permissions[len('onPermissionData('):-2])['microphone'] == 'not determined'
    assert any(s.startswith('onControlStatus(') for s in messages)


def test_permission_refresh_does_not_reload_unsaved_preferences(monkeypatch):
    ui = manager()
    monkeypatch.setattr('fixoflow.ui.controller.permission_snapshot',
                        lambda: {'accessibility':False,'input':True,'microphone':'denied'})
    ui.handle_action('getPermissions', {})
    assert ui._eval_js.call_count == 1
    assert ui._eval_js.call_args.args[0].startswith('onPermissionData(')
