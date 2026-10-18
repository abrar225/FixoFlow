"""Frozen Windows/Linux entry point with noninteractive diagnostic output."""
import multiprocessing
import sys
from pathlib import Path
import traceback
multiprocessing.freeze_support()
if __name__=='__main__':
    report=None
    if '--check-report' in sys.argv:
        report=Path(sys.argv[sys.argv.index('--check-report')+1])
        report.parent.mkdir(parents=True,exist_ok=True)
        trace=report.with_suffix('.trace.log').open('w',buffering=1)
        sys.stdout=sys.stderr=trace
        print('Fixo Flow frozen entry started',flush=True)
    try:
        from fixoflow.desktop import main
        main()
    except BaseException as error:
        if isinstance(error,SystemExit) and error.code in (None,0):raise
        traceback.print_exc()
        raise SystemExit(1)
