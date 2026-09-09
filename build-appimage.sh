#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/pc-analyzer"
APPIMAGE_TOOL_PATH="${APPIMAGE_TOOL:-$CACHE_DIR/appimagetool}"

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "PyInstaller no está instalado en $PYTHON. Instálalo con:"
    echo "  $PYTHON -m pip install pyinstaller"
    exit 1
fi

if command -v appimagetool >/dev/null 2>&1 && [[ -z "${APPIMAGE_TOOL:-}" ]]; then
    APPIMAGE_TOOL_PATH="$(command -v appimagetool)"
fi

mkdir -p "$CACHE_DIR"

if [[ ! -x "$APPIMAGE_TOOL_PATH" ]]; then
    if ! command -v curl >/dev/null 2>&1; then
        echo "curl es necesario para descargar appimagetool."
        exit 1
    fi
    echo "Descargando appimagetool..."
    curl -L --fail --silent --show-error \
        -o "$APPIMAGE_TOOL_PATH" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGE_TOOL_PATH"
fi

# Build everything in a temporary directory so no build artifacts
# (build/, dist/, _internal/) remain in the project.
TMP_BUILD="$(mktemp -d)"
trap 'rm -rf "$TMP_BUILD"' EXIT

APPDIR="$TMP_BUILD/AppDir"
mkdir -p "$APPDIR/usr/bin"

echo "Construyendo el ejecutable Python..."
"$PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name pc-analyzer \
    --distpath "$TMP_BUILD/dist" \
    --workpath "$TMP_BUILD/work" \
    --specpath "$TMP_BUILD" \
    --add-data "$PROJECT_DIR/static:static" \
    --collect-all fastapi \
    --collect-all pydantic \
    --collect-all uvicorn \
    "$PROJECT_DIR/main.py"

cp -a "$TMP_BUILD/dist/pc-analyzer/." "$APPDIR/usr/bin/"
cp "$PROJECT_DIR/appimage/AppRun" "$APPDIR/AppRun"
cp "$PROJECT_DIR/appimage/pc-analyzer.desktop" "$APPDIR/pc-analyzer.desktop"
cp "$PROJECT_DIR/appimage/pc-analyzer.svg" "$APPDIR/pc-analyzer.svg"
chmod +x "$APPDIR/AppRun"

OUTPUT="$PROJECT_DIR/PC-Analyzer-Linux-x86_64.AppImage"
rm -f "$OUTPUT"
ARCH=x86_64 "$APPIMAGE_TOOL_PATH" "$APPDIR" "$OUTPUT"
echo "AppImage creada: $OUTPUT"