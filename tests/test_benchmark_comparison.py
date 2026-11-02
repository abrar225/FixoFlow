import importlib.util
import io
import json
from pathlib import Path
import wave

import pytest

from fixoflow.evaluation import paired_summary, score_transcript, summarize

spec=importlib.util.spec_from_file_location('compare_recognizers',Path(__file__).resolve().parents[1]/'scripts/compare_recognizers.py')
benchmark=importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def row(text='hello', **extra):
    return {'id':'sample','audio_sha256':'a'*64,'reference':'hello','actual':text,
            'elapsed_seconds':1,'status':'ok',**score_transcript('hello',text),**extra}


def test_pairing_rejects_audio_reference_case_and_timing_mismatch():
    for bad in [row(audio_sha256='b'*64),row(reference='different'),row(id='other'),row(timing_phase='warm')]:
        with pytest.raises(ValueError):paired_summary([row()],[bad])
    with pytest.raises(ValueError,match='Duplicate'):paired_summary([row(),row()],[row()])


def test_failures_remain_visible_and_are_not_scored_as_silence():
    result=paired_summary([row()],[row(status='failed',actual='',error='decode failed')])
    assert result['both_successful']==0
    assert result['right']['failed_cases']==1
    assert result['right']['normalized_micro_wer'] is None
    assert result['pairs'][0]['right_minus_left_seconds'] is None


def test_bootstrap_clusters_repetitions_by_speaker_and_does_not_invent_sample_size():
    left=[row(id='one',speaker_id='s1'),row(id='two',speaker_id='s2')]
    right=[row('wrong',id='one',speaker_id='s1'),row('wrong',id='two',speaker_id='s2')]
    result=paired_summary(left,right)['speaker_cluster_bootstrap']
    assert result['clusters']==2 and result['interval_95']==[1.,1.]
    assert paired_summary([row()],[row()])['speaker_cluster_bootstrap']['interval_95'] is None


def test_exact_labels_preserve_case_numbers_and_identifier_boundaries():
    reference='Maya will call parseConfig with 12 and 12.'
    scores=score_transcript(reference,'maya will call parseConfigExtra with 312 and 12.',
                            {'names':['Maya'],'identifiers':['parseConfig'],'numbers':['12']})
    assert all(group['retained']==0 for group in scores['exact_labels'].values())
    clean=score_transcript(reference,reference,{'names':['Maya'],'identifiers':['parseConfig'],'numbers':['12']})
    assert all(group['retained']==1 for group in clean['exact_labels'].values())
    with pytest.raises(ValueError):score_transcript(reference,reference,{'names':['invented']})


def test_manifest_requires_provenance_and_checks_prepared_audio_hash(tmp_path):
    wav=tmp_path/'sample.wav'
    with wave.open(str(wav),'wb') as audio:
        audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(16000);audio.writeframes(b'\0\0'*160)
    path=tmp_path/'manifest.json'
    data={'schema_version':1,'corpus':{'source':'synthetic test fixture','license':'test-generated','scope':'unit test only'},
          'cases':[{'id':'sample','audio':'sample.wav','reference':'','language':'en'}]}
    path.write_text(json.dumps(data))
    loaded=benchmark.manifest(path)
    assert loaded['cases'][0]['audio_sha256']==benchmark.sha256(wav)
    assert loaded['cases'][0]['duration_seconds']==.01
    data['cases'][0]['audio_sha256']='0'*64;path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='hash mismatch'):benchmark.manifest(path)
    del data['corpus'];path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='provenance'):benchmark.manifest(path)


@pytest.mark.parametrize('ident,host',[('../outside','datasets-server.huggingface.co'),('1-2-3','untrusted.example')])
def test_public_fixture_fetch_rejects_untrusted_paths_and_hosts(tmp_path,monkeypatch,ident,host):
    monkeypatch.setattr(benchmark.shutil,'which',lambda name:'/test/ffmpeg')
    payload={'rows':[{'row':{'id':ident,'audio':[{'src':'https://'+host+'/audio.flac'}]}}]}
    def response(url,**kwargs):
        if isinstance(url,str) and '/api/datasets/' in url:
            return io.BytesIO(json.dumps({'sha':benchmark.LIBRISPEECH_REVISION}).encode())
        return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(benchmark.urllib.request,'urlopen',response)
    with pytest.raises(ValueError,match='Unexpected'):
        benchmark.fetch_librispeech_subset(tmp_path)
    assert not list(tmp_path.glob('*.flac'))


def test_repetitions_alternate_order_and_preserve_failed_pairs(monkeypatch):
    calls=[]
    def execute(adapter,executable,model,case,timeout):
        calls.append(adapter)
        return {'status':'ok','actual':'hello','elapsed_seconds':1}
    monkeypatch.setattr(benchmark,'execute',execute)
    result=benchmark.run_cases({'cases':[row(language='en')]},
        {'fixo':('fixo',None,None),'other':('other',None,None)},2,1)
    assert calls==['fixo','other','other','fixo']
    assert paired_summary(result['fixo'],result['other'])['both_successful']==2


def test_native_runner_failure_is_reported(tmp_path):
    case={'audio':'missing.wav','language':'en'}
    result=benchmark.execute('speaktype',tmp_path/'missing',('base',tmp_path),case,.1)
    assert result['status']=='failed'
    assert result['actual']==''


def test_native_runner_timeout_is_reported(tmp_path,monkeypatch):
    import subprocess
    def timeout(*args,**kwargs):raise subprocess.TimeoutExpired(args[0],.1)
    monkeypatch.setattr(benchmark.subprocess,'run',timeout)
    result=benchmark.execute('speaktype',tmp_path/'runner',('base',tmp_path),{'audio':'test.wav','language':'en'},.1)
    assert result['status']=='failed' and result['error']=='Recognizer timed out'


def test_import_comparison_persists_manifest_equivalent_pairs(tmp_path):
    measurement={'phase':'warm_worker','units':'seconds','scope':'decode_only'}
    identity={'name':'fixture-only','model':'fixture-model','source_identity':'fixture-source-hash','artifact_identity':'fixture-model-hash'}
    left=tmp_path/'left.json';right=tmp_path/'right.json';report=tmp_path/'report.json'
    left.write_text(json.dumps({'measurement':measurement,'recognizer':identity,'rows':[row()]}))
    right.write_text(json.dumps({'measurement':measurement,'recognizer':identity,'rows':[row(elapsed_seconds=2)]}))
    assert benchmark.main(['--import-left',str(left),'--import-right',str(right),'--report',str(report)])==0
    saved=json.loads(report.read_text())
    assert saved['comparison']['pairs'][0]['right_minus_left_seconds']==1
    assert saved['imports']['left_sha256']==benchmark.sha256(left)


def test_evaluator_preserves_failures_and_warm_repeat_metadata(tmp_path,monkeypatch):
    evaluator_spec=importlib.util.spec_from_file_location('evaluate_speech',Path(__file__).resolve().parents[1]/'scripts/evaluate_speech.py')
    evaluator=importlib.util.module_from_spec(evaluator_spec);evaluator_spec.loader.exec_module(evaluator)
    audio=tmp_path/'test.wav';audio.write_bytes(b'test-only-no-inference')
    manifest=tmp_path/'manifest.json';report=tmp_path/'report.json'
    manifest.write_text(json.dumps([{'id':'a','audio':'test.wav','reference':'hello','language':'en'}]))
    class Engine:
        language='en'
        calls=0
        def transcribe_file(self,path):
            self.calls+=1
            if self.calls==1:raise RuntimeError('simulated decode failure')
            return 'hello'
    monkeypatch.setattr(evaluator,'create_stt_engine',lambda config:Engine())
    monkeypatch.setattr(evaluator.sys,'argv',['evaluate_speech','--model','test-model','--manifest',str(manifest),
        '--report',str(report),'--repetitions','3'])
    assert evaluator.main()==2
    data=json.loads(report.read_text())
    assert data['summary']['failed_cases']==1 and data['summary']['successful_cases']==2
    assert data['rows'][0]['error']=='simulated decode failure'
    assert data['rows'][1]['timing_phase']=='first_decode'
    assert data['rows'][2]['timing_phase']=='warm_worker'
    assert data['rows'][0]['audio_sha256']==benchmark.sha256(audio)
