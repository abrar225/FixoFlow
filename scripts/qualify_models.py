#!/usr/bin/env python3
"""Explicit local model diagnostic using a supplied, lawfully available corpus.

No microphone capture or audio upload. --download explicitly provisions pinned
model assets. A diagnostic report is not a release qualification or accuracy claim.
Manifest: [{"id":"...","audio":"clip.wav","reference":"...","language":"en"}]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fixoflow.config import FixoflowConfig
from fixoflow.evaluation import edit_distance, words
from fixoflow.models.catalog import CATALOG, runtime_backend
from fixoflow.models.manager import ModelManager, model_root, verify_model
from fixoflow.stt.engine import create_stt_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-id', choices=sorted(CATALOG), required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--models-dir', type=Path, default=model_root())
    parser.add_argument('--model-path', type=Path, help='Verify an existing local folder against this exact catalog spec instead of installing a second copy.')
    parser.add_argument('--download', action='store_true', help='Explicitly download the immutable catalog assets if absent.')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20:
        parser.error('repeats must be between 1 and 20')
    if args.model_path and args.download:
        parser.error('Choose either an existing model path or an explicit download.')
    spec = CATALOG[args.model_id]
    if spec.backend != runtime_backend():
        parser.error('Model is not compatible with this computer/backend.')
    manifest = json.loads(args.manifest.read_text())
    cases = manifest.get('cases') if isinstance(manifest,dict) else manifest
    if not isinstance(cases,list) or not cases:
        parser.error('Manifest must contain at least one case.')
    seen = set()
    for case in cases:
        if (not isinstance(case,dict) or not all(isinstance(case.get(k),str) for k in ('id','audio','reference'))
                or not case['id'] or case['id'] in seen or case.get('language','en') != 'en'):
            parser.error('Each English case needs unique id, audio path and reference text.')
        seen.add(case['id'])
        path = (args.manifest.resolve().parent / Path(case['audio']).expanduser()).resolve()
        if not path.is_file():
            parser.error('Missing audio for '+case['id'])
        case['audio'] = str(path)
        digest = hashlib.sha256()
        with path.open('rb') as audio:
            while block := audio.read(1024*1024):
                digest.update(block)
        actual_hash = digest.hexdigest()
        if case.get('audio_sha256') and case['audio_sha256'] != actual_hash:
            parser.error('Audio SHA-256 mismatch for '+case['id'])
        case['audio_sha256'] = actual_hash
    manager = ModelManager(root=args.models_dir)
    path = args.model_path or args.models_dir/spec.id
    if args.download:
        path = manager.install(spec.id)
    path = verify_model(path,spec)
    config = FixoflowConfig(model_name=str(path),language='en')
    engine = create_stt_engine(config)
    began = time.perf_counter()
    if args.model_path:
        engine.warm_up()
    else:
        manager.warm_up(spec.id,engine)
    warming_seconds = time.perf_counter()-began
    rows = []
    for repetition in range(args.repeats):
        for case in cases:
            began = time.perf_counter()
            try:
                actual = engine.transcribe_file(case['audio'])
                expected = words(case['reference'])
                rows.append({**case, 'repetition':repetition, 'actual':actual,
                    'reference_words':len(expected), 'word_errors':edit_distance(expected,words(actual)),
                    'elapsed_seconds':time.perf_counter()-began, 'status':'ok'})
            except Exception as error:
                rows.append({**case, 'repetition':repetition, 'status':'failed', 'error':str(error),
                    'elapsed_seconds':time.perf_counter()-began})
    successful = [row for row in rows if row['status']=='ok']
    errors = sum(row['word_errors'] for row in successful)
    total = sum(row['reference_words'] for row in successful)
    times = [row['elapsed_seconds'] for row in successful]
    versions = {}
    for package in ('mlx','mlx-whisper','faster-whisper','ctranslate2','numpy','scipy'):
        try:versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:versions[package] = None
    report = {'schema_version':1,'model':spec.public(),
        'corpus':manifest.get('corpus') if isinstance(manifest,dict) else None,
        'manifest_sha256':hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        'hardware':{'system':platform.system(),'machine':platform.machine(),'python':platform.python_version()},
        'runtime_versions':versions,
        'decoder':{'engine':type(engine).__name__,'language':'en','prompt':'','cpu_threads':config.cpu_threads},
        'warm_up_seconds':warming_seconds,'repeats':args.repeats,'rows':rows,
        'summary':{'completed':len(successful),'failed':len(rows)-len(successful),
            'normalized_micro_wer':errors/total if total else None,
            'decode_seconds_median':statistics.median(times) if times else None},
        'limitations':'Supplied corpus only; repeated clips are not independent speakers. Warm-up separates model load but native kernels may still initialize during first decode. No matched competing-app runtime, cold-process series, battery or process-family memory measurement. Candidate purpose labels are not quality/performance guarantees.'}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'model':spec.id,'warm_up_seconds':warming_seconds,'summary':report['summary'],'report':str(args.report)}))
    if len(successful) != len(rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
