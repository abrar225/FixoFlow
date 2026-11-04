#!/usr/bin/env python3
"""Matched offline recognition runner. No audio upload or implicit model download.

The SpeakType adapter requires its built `transcribe_wav` developer executable.
`whisper-cpp-proxy` is explicitly a backend proxy, never a SpeakType app result.
All measured executions use fresh processes; OS/file caches are uncontrolled.
Use --import-left/--import-right for JSON reports from independently instrumented
warm workers. Paired identities, actual audio bytes and references must match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fixoflow.evaluation import paired_summary, score_transcript, summarize

LIBRISPEECH_REVISION='71cacbfb7e2354c4226d01e70d77d5fca3d04ba1'


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        while block:=file.read(1024*1024):digest.update(block)
    return digest.hexdigest()


def fetch_librispeech_subset(destination):
    """Explicit public CC-BY-4.0 diagnostic download; no recognition-based selection."""
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise ValueError('ffmpeg is required to prepare public FLAC fixtures.')
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    metadata_url='https://huggingface.co/api/datasets/openslr/librispeech_asr/revision/'+LIBRISPEECH_REVISION
    with urllib.request.urlopen(metadata_url,timeout=30) as response:metadata=json.load(response)
    if metadata.get('sha')!=LIBRISPEECH_REVISION:
        raise ValueError('Dataset metadata does not match the pinned revision.')
    (destination/'source-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    cases=[]
    for config,step in [('clean',250),('other',290)]:
        for offset in range(0,step*10,step):
            query=urllib.parse.urlencode({'dataset':'openslr/librispeech_asr','config':config,'split':'test','offset':offset,'length':1})
            request=urllib.request.Request('https://datasets-server.huggingface.co/rows?'+query,headers={'User-Agent':'FixoFlow-public-benchmark'})
            with urllib.request.urlopen(request,timeout=30) as response:data=json.load(response)
            row=data['rows'][0]['row'];src=row['audio'][0]['src']
            if not re.fullmatch(r'\d+-\d+-\d+',row['id']):raise ValueError('Unexpected public audio identifier.')
            if urllib.parse.urlparse(src).hostname!='datasets-server.huggingface.co':raise ValueError('Unexpected dataset audio host.')
            if '/--/'+LIBRISPEECH_REVISION+'/--/' not in urllib.parse.urlparse(src).path:
                raise ValueError('Dataset viewer returned audio from a different revision.')
            stem=config+'-'+row['id'];original=destination/(stem+'.flac');prepared=destination/(stem+'.wav')
            if original.is_symlink() or prepared.is_symlink():raise ValueError('Public fixture paths must not be symbolic links.')
            if not original.exists():
                with urllib.request.urlopen(src,timeout=30) as response:payload=response.read(5_000_001)
                if len(payload)>5_000_000:raise ValueError('Public audio exceeds the 5 MB per-clip limit.')
                with tempfile.NamedTemporaryFile(dir=destination,prefix='.fixture-',delete=False) as temporary:
                    temporary.write(payload)
                Path(temporary.name).replace(original)
            if not prepared.exists():
                subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(original),'-ac','1','-ar','16000','-c:a','pcm_s16le',str(prepared)],check=True,timeout=30)
            cases.append({'id':stem,'audio':str(prepared),'audio_sha256':sha256(prepared),'language':'en',
                'reference':row['text'],'speaker_id':str(row['speaker_id']),'chapter_id':str(row['chapter_id']),
                'stratum':config,'dataset_row':offset,'original_sha256':sha256(original),'source_asset':src.split('?',1)[0]})
    data={'schema_version':1,'corpus':{'source':'https://www.openslr.org/12 ; https://huggingface.co/datasets/openslr/librispeech_asr',
        'dataset_revision':LIBRISPEECH_REVISION,'source_metadata_sha256':sha256(destination/'source-metadata.json'),
        'license':'CC BY 4.0. LibriSpeech prepared by Vassil Panayotov with Daniel Povey; Panayotov, Chen, Povey and Khudanpur, ICASSP 2015. Derived from LibriVox read audiobooks.',
        'scope':'20 deterministic multi-speaker read-English test clips; 10 clean and 10 harder other. Other is not controlled additive noise. Not representative of everyday dictation, personal names, code, Indian English or Hinglish.',
        'selection':'Predeclared evenly spaced offsets: clean 0..2250 by 250; other 0..2610 by 290. No recognition-based filtering or tuning.'},'cases':cases}
    output=destination/'manifest.json';output.write_text(json.dumps(data,indent=2)+'\n')
    manifest(output)  # Validate prepared bytes before claiming corpus readiness.
    return output


def manifest(path):
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or data.get('schema_version')!=1 or not isinstance(data.get('cases'),list) or not data['cases']:
        raise ValueError('Expected schema_version 1 manifest with nonempty cases.')
    if not isinstance(data.get('corpus'),dict) or not all(data['corpus'].get(k) for k in ('source','license','scope')):
        raise ValueError('Corpus source, license/consent provenance and scope are required.')
    seen=set()
    for case in data['cases']:
        if not isinstance(case,dict) or any(not isinstance(case.get(k),str) for k in ('id','audio','reference','language')) or not case['id'] or case['id'] in seen:
            raise ValueError('Cases require unique id and string audio/reference/language.')
        seen.add(case['id'])
        audio=(path.resolve().parent/Path(case['audio']).expanduser()).resolve()
        if not audio.is_file():raise ValueError('Missing audio for '+case['id'])
        with wave.open(str(audio)) as wav:
            if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate())!=(1,2,16000):
                raise ValueError('Supply identical prepared 16 kHz mono PCM16 WAV files.')
            frames=wav.getnframes()
            if len(wav.readframes(frames))!=frames*2:raise ValueError('Truncated WAV')
            case['duration_seconds']=frames/16000
        case['audio']=str(audio)
        digest=sha256(audio)
        if case.get('audio_sha256') and case['audio_sha256']!=digest:raise ValueError('Audio hash mismatch for '+case['id'])
        case['audio_sha256']=digest
        score_transcript(case['reference'],case['reference'],case.get('labels'))
    return data


def source_sha(path):
    result=subprocess.run(['git','-C',str(path),'rev-parse','HEAD'],capture_output=True,text=True)
    return result.stdout.strip() if result.returncode==0 else None


def source_identity(path):
    """Include uncommitted source contents; a base commit alone is insufficient."""
    path=Path(path).resolve()
    listing=subprocess.run(['git','-C',str(path),'ls-files','--cached','--others','--exclude-standard','-z'],capture_output=True)
    fingerprints=[]
    for name in sorted(set(listing.stdout.decode().split('\0'))):
        file=path/name
        if name and file.is_file() and (name.startswith(('fixoflow/','scripts/','desktop/src-tauri/src/')) or name in {'pyproject.toml','desktop/src-tauri/Cargo.toml','desktop/src-tauri/Cargo.lock'}):
            fingerprints.append({'path':name,'sha256':sha256(file)})
    content=hashlib.sha256(json.dumps(fingerprints,sort_keys=True).encode()).hexdigest()
    dirty=subprocess.run(['git','-C',str(path),'status','--porcelain'],capture_output=True,text=True)
    return {'commit':source_sha(path),'working_tree_dirty':bool(dirty.stdout),
            'relevant_source_sha256':content,'relevant_files':fingerprints}


def artifact_identity(path):
    path=Path(path).expanduser().resolve()
    if not path.exists():raise ValueError('Missing local model artifact: '+str(path))
    files=[path] if path.is_file() else sorted(p for p in path.rglob('*') if p.is_file())
    return {'path':str(path),'files':[{'path':str(p.relative_to(path)) if path.is_dir() else path.name,
                                      'bytes':p.stat().st_size,'sha256':sha256(p)} for p in files]}


def fixo_worker(model, audio, language):
    from fixoflow.config import FixoflowConfig
    from fixoflow.stt.engine import create_stt_engine
    config=FixoflowConfig(model_name=model,language=None if language=='auto' else language)
    config.validate()  # Research runner can evaluate unreleased languages without enabling the app UI.
    engine=create_stt_engine(config)
    actual=engine.transcribe_file(audio)
    print(json.dumps({'actual':actual},ensure_ascii=False))


def command_for(adapter, executable, model, case, output):
    if adapter=='fixoflow':
        return [sys.executable,str(Path(__file__).resolve()),'--fixo-worker',str(model),case['audio'],case['language']]
    if adapter=='speaktype':
        return [str(executable),str(model[0]),str(model[1]),case['audio'],'1']
    # Match SpeakType Whisper adapter's no-context, greedy single-best defaults.
    return [str(executable),'-m',str(model),'-f',case['audio'],'-l',case['language'],
            '-t',str(min(os.cpu_count() or 4,8)),'-mc','0','-bo','1','-bs','1','-nt','-otxt','-of',str(output)]


def execute(adapter, executable, model, case, timeout):
    with tempfile.TemporaryDirectory(prefix='fixoflow-bench-output-') as root:
        output=Path(root)/'transcript'
        command=command_for(adapter,executable,model,case,output)
        started=time.perf_counter()
        try:
            result=subprocess.run(command,capture_output=True,text=True,timeout=timeout,check=False)
            elapsed=time.perf_counter()-started
            if result.returncode:
                # Avoid emitting captured model/audio output as a generic exception.
                return {'status':'failed','error':'Recognizer exited with code '+str(result.returncode),
                        'elapsed_seconds':elapsed,'actual':''}
            if adapter=='fixoflow':
                actual=json.loads(result.stdout.splitlines()[-1])['actual']
            elif adapter=='speaktype':
                marker='  text: '
                if marker not in result.stdout:raise ValueError('SpeakType runner did not emit a transcript marker.')
                actual=result.stdout.split(marker,1)[1].strip()
            else:
                actual=output.with_suffix('.txt').read_text().strip()
            if not isinstance(actual,str):raise ValueError('Adapter returned nontext transcript.')
            return {'status':'ok','actual':actual,'elapsed_seconds':elapsed}
        except subprocess.TimeoutExpired:
            return {'status':'failed','error':'Recognizer timed out','actual':'','elapsed_seconds':time.perf_counter()-started}
        except (OSError,ValueError,KeyError,IndexError) as error:
            return {'status':'failed','error':str(error),'actual':'','elapsed_seconds':time.perf_counter()-started}


def run_cases(data, adapters, repetitions, timeout):
    reports={name:[] for name in adapters}
    for repetition in range(1,repetitions+1):
        for case in data['cases']:
            # Alternate order to reduce a systematic filesystem/thermal-order advantage.
            order=list(adapters)
            if repetition%2==0:order.reverse()
            for name in order:
                adapter,executable,model=adapters[name]
                row={**case,'repetition':repetition,'timing_phase':'fresh_process',
                     'timing_scope':'parent wall time including interpreter/process startup, model load, audio preparation, decode and teardown'}
                row.update(execute(adapter,executable,model,case,timeout))
                row.update(score_transcript(case['reference'],row['actual'],case.get('labels')))
                reports[name].append(row)
    return reports


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--report',type=Path)
    parser.add_argument('--fetch-librispeech-subset',type=Path,metavar='DIR',help='Explicitly download/prepare a public CC-BY-4.0 20-clip diagnostic; no inference.')
    parser.add_argument('--fixo-model',type=Path)
    parser.add_argument('--comparison-backend',choices=['speaktype','whisper-cpp-proxy'],default='speaktype')
    parser.add_argument('--comparison-executable',type=Path)
    parser.add_argument('--comparison-model',required=False)
    parser.add_argument('--speaktype-models-dir',type=Path)
    parser.add_argument('--speaktype-source',type=Path)
    parser.add_argument('--repetitions',type=int,default=3)
    parser.add_argument('--timeout',type=float,default=180)
    parser.add_argument('--import-left',type=Path)
    parser.add_argument('--import-right',type=Path)
    args=parser.parse_args(argv)
    if args.fetch_librispeech_subset:
        print(str(fetch_librispeech_subset(args.fetch_librispeech_subset)))
        return 0
    if not args.report:parser.error('--report is required for comparison.')
    if args.import_left or args.import_right:
        if not (args.import_left and args.import_right):parser.error('Provide both reports.')
        left=json.loads(args.import_left.read_text());right=json.loads(args.import_right.read_text())
        if not left.get('measurement') or left.get('measurement')!=right.get('measurement'):
            parser.error('Imported reports require identical explicit measurement metadata (phase, units and timing scope).')
        if any(not isinstance(data.get('recognizer'),dict) or not all(data['recognizer'].get(key) for key in ('name','model','source_identity','artifact_identity')) for data in (left,right)):
            parser.error('Imported reports require recognizer name, model, source_identity and artifact_identity.')
        report={'schema_version':1,'measurement':left['measurement'],'comparison':paired_summary(left['rows'],right['rows']),
                'recognizers':{'left':left['recognizer'],'right':right['recognizer']},
                'imports':{'left_sha256':sha256(args.import_left),'right_sha256':sha256(args.import_right)}}
    else:
        if not all((args.manifest,args.fixo_model,args.comparison_executable,args.comparison_model)):
            parser.error('Supply manifest, local Fixo model, comparison executable and comparison model.')
        if args.repetitions<1 or args.timeout<=0:parser.error('Repetitions and timeout must be positive.')
        data=manifest(args.manifest)
        if not args.comparison_executable.is_file():parser.error('Comparison executable is missing; build it first.')
        if args.comparison_backend=='speaktype':
            if not args.speaktype_models_dir or not args.speaktype_source:parser.error('Supply SpeakType models directory and source checkout.')
            comparison_model=(args.comparison_model,args.speaktype_models_dir.resolve())
            comparison_artifacts=artifact_identity(args.speaktype_models_dir)
        else:
            comparison_model=Path(args.comparison_model).expanduser().resolve()
            comparison_artifacts=artifact_identity(comparison_model)
        fixo_source_before=source_identity(Path(__file__).resolve().parents[1])
        comparison_source_before=source_identity(args.speaktype_source) if args.speaktype_source else None
        fixo_artifact=artifact_identity(args.fixo_model)
        results=run_cases(data,{'fixoflow':('fixoflow',None,args.fixo_model.resolve()),
            args.comparison_backend:(args.comparison_backend,args.comparison_executable.resolve(),comparison_model)},args.repetitions,args.timeout)
        fixo_source_after=source_identity(Path(__file__).resolve().parents[1])
        comparison_source_after=source_identity(args.speaktype_source) if args.speaktype_source else None
        report={'schema_version':1,'manifest_sha256':sha256(args.manifest),'corpus':data['corpus'],
            'sample_counts':{'distinct_audio':len({row['audio_sha256'] for row in data['cases']}),
                'declared_speakers':len({str(row['speaker_id']) for row in data['cases'] if row.get('speaker_id')})},
            'measurement':{'phase':'fresh_process','units':'seconds','scope':'parent wall time; no filesystem-cache eviction; no warm-worker comparison'},
            'runtime':{'python':sys.version,'platform':platform.platform(),'machine':platform.machine()},
            'recognizers':{'fixoflow':{'source_before':fixo_source_before,'source_after':fixo_source_after,
                    'source_changed_during_run':fixo_source_before!=fixo_source_after,'artifact':fixo_artifact},
                args.comparison_backend:{'source_before':comparison_source_before,'source_after':comparison_source_after,
                    'source_changed_during_run':comparison_source_before!=comparison_source_after,
                    'executable_sha256':sha256(args.comparison_executable),'model':args.comparison_model,'artifact':comparison_artifacts}},
            'rows':results,'comparison':paired_summary(results['fixoflow'],results[args.comparison_backend]),
            'by_stratum':{stratum:paired_summary([row for row in results['fixoflow'] if row.get('stratum','unspecified')==stratum],
                [row for row in results[args.comparison_backend] if row.get('stratum','unspecified')==stratum])
                for stratum in sorted({row.get('stratum','unspecified') for row in data['cases']})},
            'limitations':['Public smoke fixtures do not establish representative accuracy.',
                'Raw recognition only: excludes UI, formatting, clipboard and paste. No process-family memory measurement.',
                'SpeakType native developer example forces auto language; Fixo/proxy use manifest language. Record this decoder-policy difference.',
                'A whisper.cpp proxy result is not a SpeakType application result.',
                'Fresh process does not imply cold filesystem cache. Warm native SpeakType repetition needs an instrumented worker exporting every transcript.']}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['comparison'],ensure_ascii=False,indent=2))
    if 'rows' in report and any(row['status']!='ok' for rows in report['rows'].values() for row in rows):return 2
    return 0


if __name__=='__main__':
    if len(sys.argv)==5 and sys.argv[1]=='--fixo-worker':
        fixo_worker(*sys.argv[2:])
    else:
        raise SystemExit(main())
