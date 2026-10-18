#!/usr/bin/env python3
"""Local, explicit WAV-manifest diagnostic. Never fetches models or uploads audio.

Manifest: [{"id":"...","audio":"/absolute/clip.wav","language":"hi", "reference":"..."}]
Whitespace WER is suitable for space-delimited languages; it is not a Chinese or
Japanese accuracy metric. Run each model in a fresh process for useful RSS data.
"""
from __future__ import annotations
import argparse
import json
try:
    import resource
except ImportError:
    resource = None
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fixoflow.config import FixoflowConfig
from fixoflow.stt.engine import create_stt_engine


def words(text):
    normalized = unicodedata.normalize('NFC', text).casefold()
    return ''.join(' ' if unicodedata.category(c)[0] in 'PS' else c for c in normalized).split()


def edit_distance(reference, actual):
    previous = list(range(len(actual) + 1))
    for i, token in enumerate(reference, 1):
        row = [i]
        for j, other in enumerate(actual, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (token != other)))
        previous = row
    return previous[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.manifest.read_text())
    rows = []
    start = time.perf_counter()
    cpu_start = time.process_time()
    engine = None
    for case in cases:
        config = FixoflowConfig(model_name=args.model, language=case['language'])
        config.validate()
        if engine is None or engine.language != config.language:
            engine = create_stt_engine(config)
        began = time.perf_counter()
        actual = engine.transcribe_file(case['audio'])
        expected_words = words(case['reference'])
        row = {**case, 'actual':actual, 'word_errors':edit_distance(expected_words, words(actual)),
               'reference_words':len(expected_words), 'elapsed_seconds':time.perf_counter()-began}
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = {'model':args.model, 'rows':rows, 'elapsed_seconds':time.perf_counter()-start,
              'cpu_seconds':time.process_time()-cpu_start,
              'peak_main_process_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024) if resource else None,
              'limitations':'Small fixed diagnostic set; not a representative quality or latency guarantee. Main process memory only; imports included in RSS, not elapsed/CPU. First decode includes lazy model initialization; filesystem cache uncontrolled.'}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
