#!/usr/bin/env python3
"""Local, explicit WAV-manifest diagnostic. Never fetches models or uploads audio.

Manifest: [{"id":"...","audio":"/absolute/clip.wav","language":"hi", "reference":"..."}]
Whitespace WER is suitable for space-delimited languages; it is not a Chinese or
Japanese accuracy metric. Run each model in a fresh process for useful RSS data.
"""
from __future__ import annotations
import argparse
import json
import hashlib
import subprocess
try:
    import resource
except ImportError:
    resource = None
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixoflow.config import FixoflowConfig
from fixoflow.stt.engine import create_stt_engine
from fixoflow.evaluation import score_transcript, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--repetitions',type=int,default=1)
    parser.add_argument('--warmup',type=int,default=0,help='Unscored warm-up decodes per clip; no cold-cache guarantee.')
    args = parser.parse_args()
    if args.repetitions<1 or args.warmup<0:
        parser.error('Repetitions must be positive and warmup nonnegative.')
    manifest_bytes = args.manifest.read_bytes()
    cases = json.loads(manifest_bytes)
    if not isinstance(cases, list) or not cases:
        parser.error('Manifest must be a nonempty list.')
    seen = set()
    for case in cases:
        if (not isinstance(case, dict) or not all(isinstance(case.get(k), str) for k in ('id','audio','language','reference'))
                or not case['id'] or case['id'] in seen):
            parser.error('Cases require unique nonempty id and string audio/language/reference fields.')
        seen.add(case['id'])
        audio = Path(case['audio']).expanduser()
        case['audio'] = str((args.manifest.resolve().parent/audio).resolve())
        if not Path(case['audio']).is_file():
            parser.error('Audio file does not exist for case '+case['id'])
        digest=hashlib.sha256()
        with Path(case['audio']).open('rb') as audio:
            while block:=audio.read(1024*1024):digest.update(block)
        if case.get('audio_sha256') and case['audio_sha256']!=digest.hexdigest():
            parser.error('Audio hash mismatch for case '+case['id'])
        case['audio_sha256']=digest.hexdigest()
        score_transcript(case['reference'],case['reference'],case.get('labels'))
    rows = []
    start = time.perf_counter()
    cpu_start = time.process_time()
    engine = None
    calls=0
    for case in cases:
        for repetition in range(1,args.repetitions+1):
            began = time.perf_counter()
            row={**case,'repetition':repetition,'actual':'','status':'failed'}
            try:
                config = FixoflowConfig(model_name=args.model, language=None if case['language']=='auto' else case['language'])
                config.validate()
                if engine is None or engine.language != config.language:
                    engine = create_stt_engine(config)
                    calls=0
                if repetition==1:
                    for _ in range(args.warmup):
                        engine.transcribe_file(case['audio']);calls+=1
                row['timing_phase']='first_decode' if calls==0 else 'warm_worker'
                began=time.perf_counter()
                row['actual']=engine.transcribe_file(case['audio'])
                calls+=1
                row['status']='ok'
            except Exception as error:
                row['error']=str(error)
            row['elapsed_seconds']=time.perf_counter()-began
            row.update(score_transcript(case['reference'],row['actual'],case.get('labels')))
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    languages = sorted({row['language'] for row in rows})
    report = {'schema_version':2, 'manifest_sha256':hashlib.sha256(manifest_bytes).hexdigest(),
              'model':args.model, 'rows':rows, 'summary':summarize(rows),
              'by_language':{language:summarize([row for row in rows if row['language']==language]) for language in languages},
              'runtime':{'python':sys.version,'platform':sys.platform}, 'elapsed_seconds':time.perf_counter()-start,
              'measurement':{'phase':'mixed_first_decode_and_warm_worker' if not args.warmup else 'warm_worker',
                             'units':'seconds','scope':'transcribe_file wall time, including read/filter/decode; first decode includes lazy initialization; excludes process startup'},
              'by_timing_phase':{phase:summarize([row for row in rows if row.get('timing_phase')==phase])
                                 for phase in sorted({row['timing_phase'] for row in rows if 'timing_phase' in row})},
              'cpu_seconds':time.process_time()-cpu_start,
              'peak_main_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024) if resource else None,
              'limitations':'Small fixed diagnostic set; not a representative quality or latency guarantee. Main process memory only; imports included in RSS, not elapsed/CPU. First decode includes lazy model initialization; filesystem cache uncontrolled.'}
    source=subprocess.run(['git','-C',str(Path(__file__).resolve().parents[1]),'rev-parse','HEAD'],capture_output=True,text=True)
    report['source_sha']=source.stdout.strip() if source.returncode==0 else None
    report['decoder_options']={'language_policy':'manifest','initial_prompt':'','condition_on_previous_text':False,
                               'repetitions':args.repetitions,'unscored_warmups_per_clip':args.warmup}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if any(row['status']!='ok' for row in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
