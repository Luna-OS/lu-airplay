#!/usr/bin/env bash
# Baut die AirPlay-Engine (UxPlay) mit den Lu-AirPlay-Patches.
# Läuft unter Linux, macOS und in einer MSYS2-UCRT64-Shell unter Windows.
#
#   scripts/build-engine.sh            -> build/engine/uxplay[.exe]
#   BUILD_DIR=/tmp/x scripts/build-engine.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/engine/uxplay"
BUILD_DIR="${BUILD_DIR:-$ROOT/build/engine}"

if [ ! -f "$SRC/CMakeLists.txt" ]; then
    echo "Engine-Quellcode fehlt – lade Submodul ..."
    git -C "$ROOT" submodule update --init --recursive
fi

# Patches anwenden (idempotent: bereits angewendete werden übersprungen)
for patch in "$ROOT"/engine/patches/*.patch; do
    [ -e "$patch" ] || continue
    if git -C "$SRC" apply --reverse --check "$patch" 2>/dev/null; then
        echo "Patch bereits angewendet: $(basename "$patch")"
    else
        echo "Wende Patch an: $(basename "$patch")"
        git -C "$SRC" apply "$patch"
    fi
done

GENERATOR=()
if command -v ninja >/dev/null 2>&1; then
    GENERATOR=(-G Ninja)
fi

cmake -S "$SRC" -B "$BUILD_DIR" "${GENERATOR[@]}" -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" --parallel

echo
echo "Fertig: $(ls "$BUILD_DIR"/uxplay "$BUILD_DIR"/uxplay.exe 2>/dev/null | head -n1)"
