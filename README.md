<p align="center">
  <img src="launcher/luairplay/assets/icon.png" width="96" alt="Lu AirPlay">
</p>

<h1 align="center">Lu AirPlay Receiver</h1>

<p align="center">
  iPhone-, iPad- und Mac-Bildschirm per AirPlay auf den PC spiegeln, ähnlich wie LonelyScreen, aber
  kostenlos, ohne Werbung und Open Source.<br>
  Windows · Linux · macOS
</p>

---

## Funktionen

- **Bildschirmsynchronisierung** von iPhone, iPad und Mac, bis 4K (H.265) und 60 fps
- **AirPlay-Audio** (Musik, Podcasts …) mit Lautstärkeregelung am iPhone
- **Deutsche Oberfläche** mit Live-Status: *Bereit*, *Verbunden mit „Lucas iPhone“*, *Bildschirm wird gespiegelt*
- **Eigener Name** für den Empfänger, direkt im Fenster änderbar
- **Zugangscode (PIN)** auf Wunsch; bekannte Geräte müssen ihn nur einmal eingeben
- **Vollbild**, Drehung, Auflösung, Bildrate, „nur Audio“-Modus
- **Neues Gerät übernimmt**: ein zweites iPhone kann die laufende Spiegelung übernehmen
- **Windows-Installer** richtet die Firewall automatisch ein
- Kein Bonjour/iTunes nötig, mDNS ist eingebaut

## Installation

### Windows

1. Unter [**Releases**](../../releases) `LuAirPlay-Setup-x.y.z.exe` herunterladen und ausführen
   (oder die portable ZIP entpacken und `Lu AirPlay.exe` starten).
2. Im Installer die Firewall-Option angehakt lassen. Windows stuft viele Heim-WLANs als
   „Öffentlich“ ein, und ohne diese Freigabe findet das iPhone den Empfänger nicht.
3. **Lu AirPlay Receiver** aus dem Startmenü öffnen. Fertig.

> Fehlt ein Release, liegt der neueste Build unter **Actions → Build → Artifacts** (`LuAirPlay-Windows`).

### Linux

```bash
sudo apt install git cmake ninja-build pkg-config libssl-dev libplist-dev python3-tk \
  libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-x gstreamer1.0-gl
git clone --recursive https://github.com/Luna-OS/lu-airplay.git
cd lu-airplay
scripts/install-linux.sh        # installiert nach ~/.local, Startmenü-Eintrag inklusive
```

Danach im Startmenü **Lu AirPlay Receiver** wählen oder `lu-airplay` eingeben.
(Fedora/Arch: Pakete entsprechend `gstreamer1-*`/`gst-plugins-*` installieren.)

### macOS

```bash
brew install cmake ninja pkg-config libplist openssl@3 gstreamer python-tk@3.13
git clone --recursive https://github.com/Luna-OS/lu-airplay.git && cd lu-airplay
scripts/build-engine.sh && python3 launcher/lu-airplay.pyw
```

## Benutzung

1. iPhone/iPad/Mac mit **demselben WLAN** wie der Computer verbinden.
2. **Kontrollzentrum** öffnen und auf **Bildschirmsynchronisierung** tippen.
3. Den Empfänger (Standard: „Lu AirPlay (*Computername*)“) auswählen.

Das Bild erscheint in einem eigenen Fenster. Unter Windows wechselt **Alt+Enter** in den Vollbildmodus.
Für Musik im Player auf das AirPlay-Symbol tippen.

## Probleme?

| Problem | Lösung |
|---|---|
| Empfänger taucht am iPhone nicht auf | Gleiches WLAN? Unter Windows: *Einstellungen → Zugriff → Windows-Firewall freigeben*. Gast-WLANs und manche Router (AP-/Client-Isolation) blockieren AirPlay. |
| Verbindet, aber schwarzes Bild/Bildfehler | *Einstellungen → Bild → Software-Dekodierung* einschalten oder unter *Erweitert* eine andere Videoausgabe wählen (Windows: `d3d12videosink`). |
| Ruckeln | Auflösung auf 1080p oder 720p und Bildrate auf 30 senken. LAN-Kabel am PC hilft. |
| Kein Ton | Unter *Einstellungen → Ton* prüfen, ob Ton aktiviert ist; Lautstärke am iPhone erhöhen. |
| Etwas anderes | Auf **Protokoll** klicken, **Kopieren** und als Issue melden. |

Einstellungen, Schlüssel und bekannte Geräte liegen in `%APPDATA%\LuAirPlay` (Windows),
`~/.config/lu-airplay` (Linux) bzw. `~/Library/Application Support/LuAirPlay` (macOS).

## Aufbau

```
launcher/            Oberfläche (Python + Tkinter, keine Zusatzpakete)
  luairplay/app.py      Fenster, Einstellungen, Protokoll
  luairplay/engine.py   startet die Engine, wertet ihre Ausgabe als Status aus
  tests/                Unit-Tests  (python -m unittest discover -s launcher/tests)
engine/uxplay/       AirPlay-Engine: UxPlay (Git-Submodul, fest auf eine geprüfte Version)
engine/patches/      kleine Anpassungen an der Engine
scripts/             build-engine.sh, package-windows.sh, install-linux.sh, make-icons.py
packaging/           Windows-Installer (Inno Setup), Linux-Desktop-Eintrag
.github/workflows/   CI: Linux-Build + Tests, Windows-Installer + ZIP, Release bei Tag v*
```

Neue Version veröffentlichen: Version in `launcher/luairplay/__init__.py` anheben, dann
`git tag v1.0.1 && git push --tags`. Die CI baut Installer und ZIP und hängt beide an das Release.

## Lizenz und Danksagung

Die AirPlay-Protokollarbeit erledigt [**UxPlay**](https://github.com/FDH2/UxPlay) (GPL-3.0), das
auf RPiPlay und shairplay aufbaut. Danke an alle Beteiligten! Lu AirPlay steht deshalb ebenfalls
unter der **GPL-3.0** (siehe [LICENSE](LICENSE)).

AirPlay, iPhone, iPad und Mac sind Marken von Apple Inc. Dieses Projekt steht in keiner Verbindung zu
Apple oder LonelyScreen.
