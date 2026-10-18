#!/usr/bin/env python3
"""Convert the approved Flow Fold source into the macOS app icon.

The same unmodified PNG is used in the hub and floating bar. This script only
creates the standard macOS icon resolutions; it never redraws the brand mark.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'fixoflow/ui/assets/flow-fold.png'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'resources/AppIcon.icns')
    args = parser.parse_args()
    if not SOURCE.is_file():
        parser.error(f'Approved logo is missing: {SOURCE}')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='fixoflow-icon-') as directory:
        iconset = Path(directory) / 'FlowFold.iconset'
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                suffix = '@2x' if scale == 2 else ''
                target = iconset / f'icon_{size}x{size}{suffix}.png'
                pixels = str(size * scale)
                subprocess.run(['sips', '-z', pixels, pixels, str(SOURCE), '--out', str(target)],
                               check=True, capture_output=True)
        subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(args.out.resolve())], check=True)
    print(f'Wrote {args.out} from approved Flow Fold: {SOURCE}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
