#!/usr/bin/env bash
# Stellt die Engine samt GStreamer für Windows zusammen (in einer MSYS2-UCRT64-Shell ausführen).
#
#   scripts/package-windows.sh [ZIELORDNER]      (Standard: dist/LuAirPlay)
#
# Ergebnis:
#   ZIEL/engine/bin/uxplay.exe + alle benötigten DLLs
#   ZIEL/engine/lib/gstreamer-1.0/*.dll                (GStreamer-Plugins)
#   ZIEL/engine/libexec/gstreamer-1.0/gst-plugin-scanner.exe
# Die Oberfläche (Lu AirPlay.exe) wird separat mit PyInstaller daneben gelegt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$ROOT/dist/LuAirPlay}"
ENGINE_EXE="${ENGINE_EXE:-$ROOT/build/engine/uxplay.exe}"
PREFIX="${MINGW_PREFIX:-/ucrt64}"
PKG_PREFIX="${MINGW_PACKAGE_PREFIX:-mingw-w64-ucrt-x86_64}"

[ -f "$ENGINE_EXE" ] || { echo "Engine fehlt: $ENGINE_EXE (zuerst scripts/build-engine.sh)"; exit 1; }

BIN="$DEST/engine/bin"
PLUGINS="$DEST/engine/lib/gstreamer-1.0"
LIBEXEC="$DEST/engine/libexec/gstreamer-1.0"
rm -rf "$DEST/engine"
mkdir -p "$BIN" "$PLUGINS" "$LIBEXEC"

cp "$ENGINE_EXE" "$BIN/"
cp "$PREFIX/libexec/gstreamer-1.0/gst-plugin-scanner.exe" "$LIBEXEC/"

# Nur die Plugins bündeln, die die Engine wirklich nutzt. Alle ~240 Plugins mitzuliefern
# macht den Start langsam und instabil: beim ersten Start scannt GStreamer jedes Plugin,
# und Hardware-Plugins (nvcodec, qsv, amfcodec, mediafoundation, ...) können dabei auf
# manchen Rechnern abstürzen.
PLUGIN_WHITELIST="
  coreelements app playback typefindfunctions pbtypes videoconvertscale videorate
  audioconvert audioresample volume opengl pango subparse rawparse
  autodetect level directsound videofilter jpeg png imagefreeze isomp4 audioparsers
  rtp udp adaptivedemux2 soup
  d3d11 d3d12 videoparsersbad wasapi wasapi2 debugutilsbad hls
  libav
"
for name in $PLUGIN_WHITELIST; do
    dll="$PREFIX/lib/gstreamer-1.0/libgst$name.dll"
    if [ -f "$dll" ]; then
        cp "$dll" "$PLUGINS/"
    else
        echo "Hinweis: Plugin nicht installiert: libgst$name.dll"
    fi
done

# DLL-Abhängigkeiten (rekursiv, nur aus dem MSYS2-Prefix) mit ntldd einsammeln
PREFIX_BIN_WIN="$(cygpath -m "$PREFIX/bin" | tr '[:upper:]' '[:lower:]')"
ntldd -R "$BIN/uxplay.exe" "$LIBEXEC/gst-plugin-scanner.exe" "$PLUGINS"/*.dll 2>/dev/null \
    | awk '/=>/ {print $3}' | tr '\\' '/' | sort -u | while read -r dll; do
        if [[ "$(echo "$dll" | tr '[:upper:]' '[:lower:]')" == "$PREFIX_BIN_WIN"/* ]]; then
            cp -n "$(cygpath -u "$dll")" "$BIN/"
        fi
    done

# Plugins entfernen, deren Abhängigkeiten nicht auflösbar sind (würden nur Warnungen erzeugen)
missing=0
for p in "$PLUGINS"/*.dll; do
    if PATH="$BIN:/c/Windows/System32" ntldd -R "$p" 2>/dev/null | grep "not found" \
            | grep -viqE '^\s*(api|ext)-ms-'; then
        echo "Entferne Plugin mit fehlenden Abhängigkeiten: $(basename "$p")"
        rm -f "$p"
        missing=$((missing + 1))
    fi
done

cp "$ROOT/LICENSE" "$DEST/LICENSE.txt"
cp "$ROOT/engine/uxplay/LICENSE" "$DEST/engine/LICENSE-UxPlay.txt"

echo
echo "Engine-Paket fertig: $DEST/engine"
echo "  $(ls "$BIN" | wc -l) Dateien in bin, $(ls "$PLUGINS" | wc -l) Plugins ($missing aussortiert)"
du -sh "$DEST/engine" | awk '{print "  Größe: " $1}'
