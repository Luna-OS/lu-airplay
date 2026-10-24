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

# UxPlay kompiliert auf x86 standardmäßig mit -march=native, also für die CPU des Rechners,
# auf dem gebaut wird. Ein so gebautes Paket stürzt auf anderen CPUs mit "Illegal Instruction"
# (0xC000001D) ab, z. B. wenn der CI-Server AVX-512 hat und der PC des Nutzers nicht.
# Für Pakete deshalb immer portabel bauen; LU_NATIVE=1 baut nur für diesen Rechner.
PORTABLE=(-DNO_MARCH_NATIVE=ON)
if [ "${LU_NATIVE:-0}" = "1" ]; then
    PORTABLE=()
fi

cmake -S "$SRC" -B "$BUILD_DIR" "${GENERATOR[@]}" -DCMAKE_BUILD_TYPE=Release "${PORTABLE[@]}"
cmake --build "$BUILD_DIR" --parallel

echo
echo "Fertig: $(ls "$BUILD_DIR"/uxplay "$BUILD_DIR"/uxplay.exe 2>/dev/null | head -n1)"
