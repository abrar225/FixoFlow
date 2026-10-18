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
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
# Remove stale staging leftovers: each dmg-stage copy is a full bundle with the
# same bundle identifier, and Launch Services registers them as duplicate
# Fixoflow apps (confusing permission rows and open-with resolution).
for stale in "$DIST_DIR"/dmg-stage.*; do
    [[ -d "$stale" ]] || continue
    "$LSREGISTER" -u "$stale/Fixoflow.app" >/dev/null 2>&1 || true
    rm -rf "$stale"
done
STAGE_DIR="$(mktemp -d "$DIST_DIR/dmg-stage.XXXXXX")"
trap '"$LSREGISTER" -u "$STAGE_DIR/Fixoflow.app" >/dev/null 2>&1 || true; rm -rf "$STAGE_DIR"' EXIT
/usr/bin/ditto "$APP_DIR" "$STAGE_DIR/Fixoflow.app"
ln -s /Applications "$STAGE_DIR/Applications"
if [[ -e "$DMG_PATH" ]]; then
    mkdir -p "$DIST_DIR/.previous-builds"
    mv "$DMG_PATH" "$DIST_DIR/.previous-builds/Fixoflow-$(date +%Y%m%d-%H%M%S).dmg"
fi
hdiutil create -volname Fixoflow -srcfolder "$STAGE_DIR" -format ULMO "$DMG_PATH"
hdiutil verify "$DMG_PATH"
echo "Built: $DMG_PATH (local build; not notarized)"
