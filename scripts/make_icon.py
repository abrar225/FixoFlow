#!/usr/bin/env python3
"""
Designs the Fixoflow app icon and writes resources/AppIcon.icns.

The mark: an ink squircle holding a flowing three-bar waveform — speech
turning into text — with a green node where the flow lands. The green node
echoes the Insights streak accent, and the bars match the hub brand mark.

Renders the 1024px master with CoreGraphics (no external dependencies beyond
the PyObjC that the app itself uses), then downsamples with sips/iconutil.

Usage: .venv/bin/python scripts/make_icon.py [--out resources/AppIcon.icns]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import Quartz
from Foundation import NSURL

ROOT = Path(__file__).resolve().parent.parent
CANVAS = 1024.0
CONTENT = (100.0, 100.0, 824.0, 824.0)  # macOS icon grid content rect
CORNER_RADIUS = 185.0

INK_TOP = (0.102, 0.102, 0.125)
INK_BOTTOM = (0.180, 0.180, 0.219)
BAR_BRIGHT = (1.0, 1.0, 1.0)
BAR_WARM = (0.949, 0.937, 0.902)
BAR_DIM = (0.851, 0.835, 0.784)
NODE_GREEN = (0.408, 0.706, 0.502)


def _squircle_path():
    x, y, width, height = CONTENT
    return Quartz.CGPathCreateWithRoundedRect(
        Quartz.CGRectMake(x, y, width, height), CORNER_RADIUS, CORNER_RADIUS, None
    )


def _fill_gradient(context, colors, start, end):
    space = Quartz.CGColorSpaceCreateDeviceRGB()
    components = []
    for color in colors:
        components.extend(list(color) if len(color) == 4 else list(color) + [1.0])
    locations = [0.0, 1.0]
    gradient = Quartz.CGGradientCreateWithColorComponents(space, components, locations, len(colors))
    Quartz.CGContextDrawLinearGradient(context, gradient, start, end, 0)


def _color(components):
    return Quartz.CGColorCreateGenericRGB(components[0], components[1], components[2],
                                          components[3] if len(components) == 4 else 1.0)


def _stroke_flow(context, start, controls, end, width, color):
    path = Quartz.CGPathCreateMutable()
    Quartz.CGPathMoveToPoint(path, None, start[0], start[1])
    Quartz.CGPathAddCurveToPoint(path, None, controls[0][0], controls[0][1], controls[1][0], controls[1][1], end[0], end[1])
    Quartz.CGContextSetStrokeColorWithColor(context, _color(color))
    Quartz.CGContextSetLineWidth(context, width)
    Quartz.CGContextSetLineCap(context, Quartz.kCGLineCapRound)
    Quartz.CGContextAddPath(context, path)
    Quartz.CGContextStrokePath(context)


def render_master() -> Quartz.CGImageRef:
    space = Quartz.CGColorSpaceCreateDeviceRGB()
    context = Quartz.CGBitmapContextCreate(None, int(CANVAS), int(CANVAS), 8, 0, space,
                                            Quartz.kCGImageAlphaPremultipliedLast)
    Quartz.CGContextClearRect(context, Quartz.CGRectMake(0, 0, CANVAS, CANVAS))

    # Ink squircle with a soft vertical gradient and a top sheen.
    Quartz.CGContextSaveGState(context)
    Quartz.CGContextAddPath(context, _squircle_path())
    Quartz.CGContextClip(context)
    _fill_gradient(context, (INK_TOP, INK_BOTTOM),
                   Quartz.CGPointMake(0, CONTENT[1] + CONTENT[3]),
                   Quartz.CGPointMake(0, CONTENT[1]))
    Quartz.CGContextSaveGState(context)
    Quartz.CGContextAddPath(context, _squircle_path())
    Quartz.CGContextClip(context)
    _fill_gradient(context, ((1.0, 1.0, 1.0, 0.06), (1.0, 1.0, 1.0, 0.0)),
                   Quartz.CGPointMake(0, 924), Quartz.CGPointMake(0, 610))
    Quartz.CGContextRestoreGState(context)
    Quartz.CGContextRestoreGState(context)

    Quartz.CGContextSaveGState(context)
    Quartz.CGContextAddPath(context, _squircle_path())
    Quartz.CGContextSetStrokeColorWithColor(context, _color((1.0, 1.0, 1.0, 0.06)))
    Quartz.CGContextSetLineWidth(context, 3.5)
    Quartz.CGContextStrokePath(context)
    Quartz.CGContextRestoreGState(context)

    # The flow: three bars drifting right, ending in a green node.
    _stroke_flow(context, (306, 612), ((396, 642), (498, 582)), (592, 606), 72, BAR_WARM)
    _stroke_flow(context, (338, 412), ((432, 382), (514, 442)), (616, 412), 72, BAR_DIM)
    _stroke_flow(context, (296, 512), ((420, 558), (562, 460)), (694, 506), 84, BAR_BRIGHT)
    Quartz.CGContextSetFillColorWithColor(context, _color((*NODE_GREEN, 1.0)))
    Quartz.CGContextFillEllipseInRect(context, Quartz.CGRectMake(660, 462, 92, 92))

    return Quartz.CGBitmapContextCreateImage(context)


def write_png(image, path: Path) -> None:
    url = NSURL.fileURLWithPath_(str(path))
    destination = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
    if destination is None:
        raise RuntimeError(f"Could not create PNG destination at {path}")
    Quartz.CGImageDestinationAddImage(destination, image, None)
    if not Quartz.CGImageDestinationFinalize(destination):
        raise RuntimeError(f"Could not write {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Fixoflow app icon")
    parser.add_argument("--out", default=str(ROOT / "resources" / "AppIcon.icns"))
    args = parser.parse_args()

    build_dir = ROOT / "build" / "icon.iconset"
    build_dir.mkdir(parents=True, exist_ok=True)
    master_png = ROOT / "build" / "icon-master-1024.png"
    write_png(render_master(), master_png)

    variants = [
        (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
    ]
    for size, name in variants:
        subprocess.run(
            ["sips", "-z", str(size), str(size), str(master_png), "--out", str(build_dir / name)],
            check=True, capture_output=True,
        )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["iconutil", "-c", "icns", str(build_dir), "-o", str(out_path)], check=True)
    print(f"Wrote {out_path} from {master_png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
