#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
DIST_DIR="$PROJECT_DIR/dist"
APP_DIR="$DIST_DIR/Fixoflow.app"
DMG_PATH="$DIST_DIR/Fixoflow.dmg"
[[ -d "$APP_DIR" ]] || bash "$SCRIPT_DIR/build_app.sh"
# Refuse to ship the old project-bound shell launcher.
/usr/bin/file "$APP_DIR/Contents/MacOS/Fixoflow" | /usr/bin/grep -q 'Mach-O' || { echo 'Build a self-contained app first.' >&2; exit 1; }
/usr/bin/codesign --verify --deep --strict "$APP_DIR"
STAGE_DIR="$(mktemp -d "$DIST_DIR/dmg-stage.XXXXXX")"
trap 'rm -rf "$STAGE_DIR"' EXIT
/usr/bin/ditto "$APP_DIR" "$STAGE_DIR/Fixoflow.app"
ln -s /Applications "$STAGE_DIR/Applications"
if [[ -e "$DMG_PATH" ]]; then
    mkdir -p "$DIST_DIR/.previous-builds"
    mv "$DMG_PATH" "$DIST_DIR/.previous-builds/Fixoflow-$(date +%Y%m%d-%H%M%S).dmg"
fi
hdiutil create -volname Fixoflow -srcfolder "$STAGE_DIR" -format UDZO "$DMG_PATH"
hdiutil verify "$DMG_PATH"
echo "Built: $DMG_PATH (local ad-hoc build; not notarized)"
