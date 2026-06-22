#!/usr/bin/env bash
# Build a drag-to-Applications DMG for HSSK Tools (macOS).
# Requires: brew install create-dmg
# Usage: bash packaging/make_dmg.sh [version]
# Run from the repo root after `pyinstaller packaging/hssk_gui.spec`.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  VERSION="$("$REPO_ROOT/.venv/bin/python" -c 'import hssk; print(hssk.__version__)')"
fi

# Arch suffix so the Intel and Apple Silicon DMGs don't collide. PyInstaller builds
# for the host arch, so detect it from this machine (override with $2 if needed).
ARCH="${2:-}"
if [[ -z "$ARCH" ]]; then
  case "$(uname -m)" in
    arm64)  ARCH="apple-silicon" ;;
    x86_64) ARCH="intel" ;;
    *)      ARCH="$(uname -m)" ;;
  esac
fi

APP_NAME="HSSK Tools"
APP_PATH="$REPO_ROOT/dist/${APP_NAME}.app"
OUT_DIR="$REPO_ROOT/out"
DMG_PATH="$OUT_DIR/HSSK-Tools-${VERSION}-${ARCH}.dmg"

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: '$APP_PATH' not found — run pyinstaller packaging/hssk_gui.spec first." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# create-dmg exits non-zero when it can't set ancillary metadata (e.g. in a
# sandbox / headless CI environment). Treat the DMG file existing as success.
create-dmg \
  --volname "$APP_NAME" \
  --volicon "$SCRIPT_DIR/assets/icon.icns" \
  --window-size 540 380 \
  --icon-size 128 \
  --icon "${APP_NAME}.app" 140 190 \
  --app-drop-link 400 190 \
  "$DMG_PATH" \
  "$APP_PATH" \
  || true

if [[ ! -f "$DMG_PATH" ]]; then
  echo "ERROR: create-dmg failed to produce '$DMG_PATH'." >&2
  exit 1
fi

echo "DMG ready: $DMG_PATH"
