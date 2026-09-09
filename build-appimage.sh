#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
APPDIR="$BUILD_DIR/AppDir"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    PYTHON="$(command -v python3)"
fi

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
    echo "PyInstaller no está instalado en $PYTHON. Instálalo con:"
    echo "  $PYTHON -m pip install pyinstaller"
    exit 1
fi

if [[ -n "${APPIMAGE_TOOL:-}" ]]; then
    APPIMAGE_TOOL_PATH="$APPIMAGE_TOOL"
else
    APPIMAGE_TOOL_PATH="$BUILD_DIR/appimagetool"
fi

mkdir -p "$BUILD_DIR"

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

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"

echo "Construyendo el ejecutable Python..."
"$PYTHON" -m PyInstaller \
    --noconfirm \
    --clean \
    --onedir \
    --name laptop-analyzer \
    --add-data "$PROJECT_DIR/static:static" \
    --collect-all fastapi \
    --collect-all pydantic \
    --collect-all uvicorn \
    "$PROJECT_DIR/main.py"

cp -a "$PROJECT_DIR/dist/laptop-analyzer/." "$APPDIR/usr/bin/"
cp "$PROJECT_DIR/appimage/AppRun" "$APPDIR/AppRun"
cp "$PROJECT_DIR/appimage/laptop-analyzer.desktop" "$APPDIR/laptop-analyzer.desktop"
cp "$PROJECT_DIR/appimage/laptop-analyzer.svg" "$APPDIR/laptop-analyzer.svg"
chmod +x "$APPDIR/AppRun"

OUTPUT="$PROJECT_DIR/laptop-analyzer-x86_64.AppImage"
ARCH=x86_64 "$APPIMAGE_TOOL_PATH" "$APPDIR" "$OUTPUT"
echo "AppImage creada: $OUTPUT"