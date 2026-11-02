#!/usr/bin/env python3
"""Explicitly prepare a bounded, pinned, CC-BY-4.0 public speech diagnostic.

Downloads 20 LibriSpeech clips across clean/other test strata using predeclared
offsets, at most 5 MB compressed per clip. No model runs or audio uploads.
This corpus is read English, not representative everyday/Hinglish dictation.
"""
import argparse
from pathlib import Path

from compare_recognizers import fetch_librispeech_subset


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    print(fetch_librispeech_subset(args.output_dir))


if __name__=='__main__':
    main()
