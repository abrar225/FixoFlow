import json
import pytest
from fixoflow.config import FixoflowConfig


def test_legacy_cloud_config_loads_offline_without_overwriting(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    original = {'polishing_engine':'gemini', 'gemini_api_key':'legacy-value', 'gemini_model':'old', 'groq_api_key':'unknown-value'}
    path.write_text(json.dumps(original))
    monkeypatch.setattr(FixoflowConfig, 'get_config_path', classmethod(lambda cls: path))
    cfg = FixoflowConfig.load()
    assert cfg.polishing_engine == 'rules'
    assert not hasattr(cfg, 'gemini_api_key')
    assert not hasattr(cfg, 'groq_api_key')
    assert json.loads(path.read_text()) == original


def test_unknown_keys_never_break_startup(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps({'groq_api_key':'secret', 'mode':'coding'}))
    monkeypatch.setattr(FixoflowConfig, 'get_config_path', classmethod(lambda cls: path))
    cfg = FixoflowConfig.load()
    assert cfg.mode == 'coding'


def test_legacy_shortcuts_migrate_without_rewriting(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    original = {'hotkey':'<cmd>+<shift>+d','dual_mode_hotkey':True,'dual_mode_threshold_sec':0.9}
    path.write_text(json.dumps(original))
    monkeypatch.setattr(FixoflowConfig,'get_config_path',classmethod(lambda cls:path))
    cfg = FixoflowConfig.load()
    assert cfg.hold_shortcut['keys'] == ['cmd','shift','d']
    assert cfg.hands_free_shortcut['keys'] != cfg.hold_shortcut['keys']
    assert json.loads(path.read_text()) == original


def test_legacy_toggle_keeps_existing_shortcut_for_hands_free(tmp_path, monkeypatch):
    path=tmp_path/'config.json';path.write_text(json.dumps({'hotkey':'<ctrl>+<space>','dual_mode_hotkey':False,'hold_to_talk':False}))
    monkeypatch.setattr(FixoflowConfig,'get_config_path',classmethod(lambda cls:path))
    assert FixoflowConfig.load().hands_free_shortcut['keys']==['ctrl','space']


def test_invalid_config_is_not_silently_reset(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    path.write_text('{broken')
    monkeypatch.setattr(FixoflowConfig, 'get_config_path', classmethod(lambda cls: path))
    with pytest.raises(json.JSONDecodeError):
        FixoflowConfig.load()
    assert path.read_text() == '{broken'


def test_atomic_config_save_keeps_previous_backup(tmp_path, monkeypatch):
    path = tmp_path / 'config.json'
    monkeypatch.setattr(FixoflowConfig, 'get_config_path', classmethod(lambda cls: path))
    cfg = FixoflowConfig(cache_dir=str(tmp_path / 'audio'))
    cfg.save()
    previous = path.read_text()
    cfg.mode = 'coding'
    cfg.save()
    assert path.with_suffix('.json.bak').read_text() == previous
    assert json.loads(path.read_text())['mode'] == 'coding'
    assert not list(tmp_path.glob('config-*'))


def test_cloud_engine_is_rejected():
    with pytest.raises(ValueError, match='offline'):
        FixoflowConfig(polishing_engine='gemini').validate()


def test_overlay_position_defaults_to_bottom_center_and_rejects_unknown_zones():
    from fixoflow.config import OVERLAY_POSITIONS
    assert FixoflowConfig().overlay_position == 'bottom-center'
    assert 'bottom-left' in OVERLAY_POSITIONS
    for zone in OVERLAY_POSITIONS:
        FixoflowConfig(overlay_position=zone).validate()
    with pytest.raises(ValueError, match='Floating pill position'):
        FixoflowConfig(overlay_position='middle-left').validate()


def test_output_style_defaults_to_natural_and_rejects_unknown_styles():
    from fixoflow.config import OUTPUT_STYLES
    assert FixoflowConfig().output_style == 'natural'
    for style in OUTPUT_STYLES:
        FixoflowConfig(output_style=style).validate()
    with pytest.raises(ValueError, match='Output style'):
        FixoflowConfig(output_style='shakespearean').validate()
