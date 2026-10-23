#!/usr/bin/env bash
# Baut Lu AirPlay und installiert es für den aktuellen Benutzer nach ~/.local
# (Startmenü-Eintrag "Lu AirPlay Receiver", Befehl "lu-airplay").
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
SHARE="$PREFIX/share/lu-airplay"

"$ROOT/scripts/build-engine.sh"

python3 -c "import tkinter" 2>/dev/null || {
    echo "Python-Tkinter fehlt. Installieren z. B. mit:  sudo apt install python3-tk"
    exit 1
}

rm -rf "$SHARE"
mkdir -p "$SHARE/engine" "$PREFIX/bin" "$PREFIX/share/applications" "$PREFIX/share/icons/hicolor/256x256/apps"
cp -r "$ROOT/launcher/luairplay" "$ROOT/launcher/lu-airplay.pyw" "$SHARE/"
cp "$ROOT/build/engine/uxplay" "$SHARE/engine/"
cp "$ROOT/launcher/luairplay/assets/icon.png" "$PREFIX/share/icons/hicolor/256x256/apps/lu-airplay.png"
cp "$ROOT/packaging/linux/lu-airplay.desktop" "$PREFIX/share/applications/"

cat > "$PREFIX/bin/lu-airplay" <<EOS
#!/bin/sh
exec python3 "$SHARE/lu-airplay.pyw" "\$@"
EOS
chmod +x "$PREFIX/bin/lu-airplay"

command -v update-desktop-database >/dev/null && update-desktop-database "$PREFIX/share/applications" || true
echo
echo "Installiert! Starte \"Lu AirPlay Receiver\" aus dem Startmenü oder mit: lu-airplay"
