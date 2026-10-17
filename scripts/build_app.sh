#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
PYTHON_EXEC="${FIXOFLOW_BUILD_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo "Build requires Apple Silicon macOS." >&2; exit 1; }
"$PYTHON_EXEC" -c 'import PyInstaller' || { echo 'Install the packaging extra in the build venv first (see docs/packaging.md).' >&2; exit 1; }
# No runtime or build-time downloads. A complete revision-pinned model must already be cached.
export FIXOFLOW_BUILD_MODEL_DIR="$PROJECT_DIR/build/bundled-model"
"$PYTHON_EXEC" "$SCRIPT_DIR/prepare_model.py"
mkdir -p "$PROJECT_DIR/dist"
BUILD_OUTPUT="$(mktemp -d "$PROJECT_DIR/build/app-stage.XXXXXX")"
trap 'rm -rf "$BUILD_OUTPUT"' EXIT
"$PYTHON_EXEC" -m PyInstaller --noconfirm --clean --distpath "$BUILD_OUTPUT" --workpath "$PROJECT_DIR/build/pyinstaller" "$PROJECT_DIR/packaging/Fixoflow.spec"
CANDIDATE="$BUILD_OUTPUT/Fixoflow.app"
# Prefer the stable local identity (scripts/create_signing_cert.sh) so TCC
# grants survive rebuilds. Ad-hoc signing pins grants to the binary hash and
# silently resets permissions on every update.
SIGN_IDENTITY="${FIXOFLOW_SIGN_IDENTITY:-}"
if [[ -z "$SIGN_IDENTITY" ]] && /usr/bin/security find-identity -p codesigning 2>/dev/null | /usr/bin/grep -q "Fixoflow Local Signing"; then
    SIGN_IDENTITY="Fixoflow Local Signing"
fi
if [[ -n "$SIGN_IDENTITY" ]]; then
    /usr/bin/codesign --force --deep --sign "$SIGN_IDENTITY" "$CANDIDATE"
    SIGN_MODE="signed with '$SIGN_IDENTITY'"
else
    /usr/bin/codesign --force --deep --sign - "$CANDIDATE"
    SIGN_MODE="ad-hoc (run scripts/create_signing_cert.sh for permission-stable builds)"
fi
/usr/bin/codesign --verify --deep --strict "$CANDIDATE"
# This imports the real frozen dependencies and validates required resources,
# without requesting audio, creating a hotkey listener or inserting text.
"$CANDIDATE/Contents/MacOS/Fixoflow" --packaging-check
# Only replace the previous output after verification. Preserve user builds in a
# hidden folder with a non-app extension to avoid more launchable app copies.
if [[ -e "$PROJECT_DIR/dist/Fixoflow.app" ]]; then
    mkdir -p "$PROJECT_DIR/dist/.previous-builds"
    mv "$PROJECT_DIR/dist/Fixoflow.app" "$PROJECT_DIR/dist/.previous-builds/Fixoflow-$(date +%Y%m%d-%H%M%S).app.backup"
fi
mv "$CANDIDATE" "$PROJECT_DIR/dist/Fixoflow.app"
echo "Built self-contained local app: $PROJECT_DIR/dist/Fixoflow.app ($SIGN_MODE; not notarized)"
