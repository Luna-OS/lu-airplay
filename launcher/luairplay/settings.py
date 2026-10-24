"""Einstellungen von Lu AirPlay (JSON im Benutzer-Konfigurationsordner)."""

from __future__ import annotations

import json
import os
import random
import socket
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        path = base / "LuAirPlay"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "LuAirPlay"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        path = base / "lu-airplay"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_name() -> str:
    host = socket.gethostname().split(".")[0]
    return f"Lu AirPlay ({host})" if host else "Lu AirPlay"


def random_pin() -> str:
    return f"{random.randint(1000, 9999)}"


@dataclass
class Settings:
    name: str = ""
    autostart: bool = True          # Empfänger beim Öffnen der App direkt starten
    resolution: str = "1080p"       # 720p | 1080p | 1440p | 4K
    fps: int = 60
    fullscreen: bool = False
    video: bool = True
    audio: bool = True
    volume: int = 100               # Startlautstärke in %
    pin_enabled: bool = False
    pin: str = ""
    takeover: bool = True           # neues Gerät übernimmt die laufende Verbindung
    keep_window: bool = False       # Videofenster nach dem Trennen offen lassen
    always_on_top: bool = False     # Videofenster immer im Vordergrund (Windows)
    window_size: int = 70           # Startgröße des Videofensters in % des Bildschirms (Windows)
    video_window: list = field(default_factory=list)  # zuletzt gewählte Position [l, t, r, b]
    software_decoding: bool = False
    rotation: str = ""              # "" | R | L
    flip: str = ""                  # "" | H | V | I
    videosink: str = ""             # leer = automatisch
    port: int = 0                   # 0 = automatisch
    network_ip: str = ""            # IPv4, unter der sich der Empfänger ankündigt ("" = automatisch)
    extra_args: str = ""            # zusätzliche Engine-Optionen für Profis

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        try:
            data = json.loads((config_dir() / "settings.json").read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            for key, value in data.items():
                if key in known and type(value) is type(getattr(s, key)):
                    setattr(s, key, value)
        except (OSError, ValueError):
            pass
        if not s.name.strip():
            s.name = default_name()
        if not (s.pin.isdigit() and len(s.pin) == 4 and s.pin != "0000"):
            s.pin = random_pin()
        return s

    def save(self) -> None:
        path = config_dir() / "settings.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
