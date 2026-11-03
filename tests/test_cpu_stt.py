from types import SimpleNamespace
import numpy as np
import pytest
from fixoflow.config import FixoflowConfig
from fixoflow.stt.cpu import CPUWhisperEngine
from fixoflow.stt.engine import TranscriptionError


def test_local_windows_decoder_contract_and_model_reuse(tmp_path):
    for name in ('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt'):
        (tmp_path/name).write_bytes(b'local fixture')
    builds = []
    requests = []

    def factory(path,**kwargs):
        builds.append((path,kwargs))

        def transcribe(audio,**options):
            requests.append(options)
            return iter([SimpleNamespace(text=' locally decoded ')]),None
        return SimpleNamespace(transcribe=transcribe)
    engine=CPUWhisperEngine(FixoflowConfig(model_name=str(tmp_path)),model_factory=factory)
    assert engine.transcribe(np.ones(30,dtype=np.float32))=='locally decoded'
    assert engine.transcribe(np.ones(30,dtype=np.float32))=='locally decoded'
    assert len(builds)==1 and builds[0][1]['local_files_only'] is True
    assert builds[0][1]['device']=='cpu' and builds[0][1]['compute_type']=='float32'
    assert requests[0]['condition_on_previous_text'] is False


def test_incomplete_windows_model_never_constructs_or_downloads(tmp_path):
    called=[]
    engine = CPUWhisperEngine(FixoflowConfig(model_name=str(tmp_path)),
                              model_factory=lambda *a, **k: called.append(True))
    with pytest.raises(TranscriptionError, match='No model was downloaded'):
        engine.transcribe(np.ones(30, dtype=np.float32))
    assert not called


def test_custom_english_only_model_cannot_be_used_for_other_languages(tmp_path):
    import json
    for name in ('model.bin', 'tokenizer.json', 'vocabulary.txt'):
        (tmp_path/name).write_bytes(b'fixture')
    (tmp_path/'config.json').write_text(json.dumps({'lang_ids':None}))
    engine=CPUWhisperEngine(FixoflowConfig(model_name=str(tmp_path),language='hi'))
    with pytest.raises(TranscriptionError, match='not compatible'):
        engine.resolve_model_path()
    (tmp_path/'config.json').write_text(json.dumps({'lang_ids':list(range(50259,50358))}))
    assert engine.resolve_model_path()==str(tmp_path)


def test_warmup_loads_local_weights_once_without_decoding(tmp_path):
    for name in ('model.bin','config.json','tokenizer.json','vocabulary.txt'):(tmp_path/name).write_bytes(b'local fixture')
    builds=[]
    def factory(path,**kwargs):
        builds.append(path)
        return SimpleNamespace(transcribe=lambda *a,**k:pytest.fail('warm-up must not transcribe'))
    engine=CPUWhisperEngine(FixoflowConfig(model_name=str(tmp_path)),model_factory=factory)
    assert engine.warm_up()==str(tmp_path)
    engine.warm_up()
    assert builds==[str(tmp_path)] and engine.capabilities.local_only


def test_cpu_turbo_vocabulary_json_is_supported(tmp_path):
    import json
    for name in ('model.bin','tokenizer.json','vocabulary.json'):(tmp_path/name).write_bytes(b'fixture')
    (tmp_path/'config.json').write_text(json.dumps({'lang_ids':list(range(50259,50359))}))
    engine=CPUWhisperEngine(FixoflowConfig(model_name=str(tmp_path),language='es'))
    assert engine.resolve_model_path()==str(tmp_path)
