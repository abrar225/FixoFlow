from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from fixoflow.config import FixoflowConfig
from fixoflow.stt.engine import TranscriptionError, create_stt_engine
from fixoflow.stt.parakeet import ParakeetEngine


def test_parakeet_reuses_local_model_without_hint_or_forced_language(monkeypatch,tmp_path):
    from fixoflow.models import manager
    monkeypatch.setattr(manager,'resolve_catalog_model',lambda name,expected_backend:str(tmp_path))
    requests=[]
    def recognize(audio,**kwargs):
        requests.append((audio,kwargs));return ' hello locally '
    factory=Mock(return_value=SimpleNamespace(recognize=recognize))
    engine=ParakeetEngine(FixoflowConfig(model_name='catalog:parakeet-v3-onnx',language=None),factory)
    assert engine.warm_up()==str(tmp_path)
    assert engine.transcribe(np.ones(30,np.float32),initial_prompt='must not become speech')=='hello locally'
    assert engine.transcribe(np.ones(30,np.float32))=='hello locally'
    factory.assert_called_once_with(str(tmp_path),offline=True,quantization='int8',cpu_threads=2)
    assert all(options=={'sample_rate':16000} for _,options in requests)
    assert not engine.capabilities.vocabulary_hints and engine.capabilities.local_only


def test_uninstalled_parakeet_never_loads_or_downloads(monkeypatch,tmp_path):
    from fixoflow.models import manager
    monkeypatch.setattr(manager,'model_root',lambda:tmp_path/'missing')
    factory=Mock()
    engine=ParakeetEngine(FixoflowConfig(model_name='catalog:parakeet-v3-onnx',language=None),factory)
    with pytest.raises(TranscriptionError,match='not installed'):engine.warm_up()
    factory.assert_not_called()


def test_parakeet_rejects_forced_language_before_loading(monkeypatch,tmp_path):
    factory=Mock()
    engine=ParakeetEngine(FixoflowConfig(model_name='catalog:parakeet-v3-onnx',language='hi'),factory)
    with pytest.raises(TranscriptionError,match='Automatic'):engine.resolve_model_path()
    factory.assert_not_called()


def test_parakeet_factory_is_selected_only_for_supported_host(monkeypatch):
    from fixoflow.models import catalog
    monkeypatch.setattr(catalog.sys,'platform','darwin')
    monkeypatch.setattr(catalog.platform,'machine',lambda:'arm64')
    cfg=FixoflowConfig(model_name='catalog:parakeet-v3-onnx',language=None)
    assert isinstance(create_stt_engine(cfg),ParakeetEngine)
    monkeypatch.setattr(catalog.platform,'machine',lambda:'x86_64')
    with pytest.raises(TranscriptionError,match='incompatible'):create_stt_engine(cfg)


def test_parakeet_failure_retains_partial_and_cancel_never_completes(monkeypatch,tmp_path):
    from fixoflow.models import manager
    import fixoflow.stt.engine as engine_module
    monkeypatch.setattr(manager,'resolve_catalog_model',lambda *args:str(tmp_path))
    monkeypatch.setattr(engine_module,'slice_audio_for_transcription',lambda *a,**k:[np.ones(30)]*2)
    calls=[]
    def recognize(*a,**k):
        calls.append(True)
        if len(calls)>1:raise RuntimeError('native failure')
        return 'first words'
    engine=ParakeetEngine(FixoflowConfig(model_name='catalog:parakeet-v3-onnx',language=None),
        lambda *a,**k:SimpleNamespace(recognize=recognize))
    with pytest.raises(TranscriptionError) as error:engine.transcribe(np.ones(60))
    assert error.value.partial_text=='first words'
    calls.clear()
    with pytest.raises(TranscriptionError,match='cancelled'):
        engine.transcribe(np.ones(60),cancelled=lambda:True)
    assert not calls
