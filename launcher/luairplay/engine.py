"""Startet die AirPlay-Engine (UxPlay) und übersetzt ihre Ausgabe in Status-Events."""

from __future__ import annotations

import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .settings import Settings, config_dir

IS_WINDOWS = sys.platform.startswith("win")
ENGINE_NAME = "uxplay.exe" if IS_WINDOWS else "uxplay"


# --------------------------------------------------------------------------- #
# Engine finden
# --------------------------------------------------------------------------- #

def app_dir() -> Path:
    """Ordner der laufenden App (bei PyInstaller der Ordner der .exe)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_engine() -> Optional[Path]:
    candidates = []
    env = os.environ.get("LU_AIRPLAY_ENGINE")
    if env:
        candidates.append(Path(env))
    here = app_dir()
    candidates += [
        here / "engine" / "bin" / ENGINE_NAME,                  # Windows-Paket
        here.parent / "engine" / ENGINE_NAME,                   # Linux-Installation
        here.parent.parent / "build" / "engine" / ENGINE_NAME,  # Repo-Build
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    found = shutil.which("uxplay")
    return Path(found) if found else None


def engine_environment(engine: Path) -> dict:
    """Umgebung für die Engine; im Windows-Paket zeigt GStreamer auf die mitgelieferten Plugins."""
    env = dict(os.environ)
    bundle = engine.parent.parent  # .../engine
    plugins = bundle / "lib" / "gstreamer-1.0"
    if plugins.is_dir():
        env["GST_PLUGIN_PATH"] = str(plugins)
        env["GST_PLUGIN_SYSTEM_PATH"] = str(plugins)
        scanner = bundle / "libexec" / "gstreamer-1.0" / ("gst-plugin-scanner.exe" if IS_WINDOWS else "gst-plugin-scanner")
        if scanner.is_file():
            env["GST_PLUGIN_SCANNER"] = str(scanner)
        env["GST_REGISTRY"] = str(config_dir() / "gst-registry.bin")
        env["PATH"] = str(engine.parent) + os.pathsep + env.get("PATH", "")
    return env


def local_ipv4_addresses() -> List[str]:
    """IPv4-Adressen dieses Rechners (für die Auswahl in den Einstellungen)."""
    import socket
    found: List[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in found:
                found.append(ip)
    except OSError:
        pass
    return found


# --------------------------------------------------------------------------- #
# Kommandozeile
# --------------------------------------------------------------------------- #

RESOLUTIONS = {
    "720p": "1280x720",
    "1080p": "1920x1080",
    "1440p": "2560x1440",
    "4K": "3840x2160",
}


def build_args(s: Settings, engine: Path) -> List[str]:
    cfg = config_dir()
    rc_file = cfg / "engine.rc"
    if not rc_file.exists():
        rc_file.write_text("# Wird von Lu AirPlay verwaltet – Einstellungen bitte in der App ändern.\n",
                           encoding="utf-8")

    args = [str(engine),
            "-rc", str(rc_file),            # ~/.uxplayrc nicht mit einlesen
            "-n", s.name.strip() or "Lu AirPlay", "-nh",
            "-key", str(cfg / "server-key.pem")]  # stabile Identität: Geräte erkennen den Empfänger wieder

    size = RESOLUTIONS.get(s.resolution, RESOLUTIONS["1080p"])
    args += ["-s", f"{size}@{s.fps}", "-fps", str(s.fps)]
    if s.resolution == "4K":
        args.append("-h265")

    if not s.video:
        args += ["-vs", "0"]
    else:
        if IS_WINDOWS:
            args += ["-vs", s.videosink or "d3d11videosink"]
        elif s.videosink:
            args += ["-vs", s.videosink]
        if s.fullscreen:
            args.append("-fs")
        if s.software_decoding:
            args.append("-avdec")
        if s.keep_window:
            args.append("-nc")
        if s.rotation in ("R", "L"):
            args += ["-r", s.rotation]
        if s.flip in ("H", "V", "I"):
            args += ["-f", s.flip]

    if not s.audio:
        args += ["-as", "0"]
    else:
        args += ["-vol", f"{max(0.0, min(1.0, s.volume / 100.0)):.2f}"]

    if s.pin_enabled and s.pin:
        args += ["-pin", s.pin, "-reg", str(cfg / "clients.register")]

    if s.takeover:
        args.append("-nohold")

    if s.port:
        args += ["-p", str(s.port)]

    args += s.extra_args.split() if s.extra_args.strip() else []
    return args


# --------------------------------------------------------------------------- #
# Ausgabe auswerten
# --------------------------------------------------------------------------- #

@dataclass
class Event:
    kind: str  # ready | client | mirroring | audio | disconnected | lost | pin | warning | error | log | exited
    text: str = ""
    detail: str = ""


_RE_ACCEPTED = re.compile(r"Accepted \S+ client on socket (\d+)")
_RE_REMOVED = re.compile(r"Removing connection for socket (\d+)")
_RE_CLIENT = re.compile(r"connection request from (.*) \((.*?)\) with deviceID")
_RE_PIN = re.compile(r'CLIENT MUST NOW ENTER PIN = "(\d+)"')
_RE_MDNS = re.compile(r"mDNS: announcing on IPv4 (\S+) \((.*)\)")


class OutputParser:
    """Wandelt Engine-Zeilen in Events um. Zustandsbehaftet (zählt offene Verbindungen)."""

    def __init__(self) -> None:
        self.sockets: set = set()
        self.client: str = ""

    def feed(self, line: str) -> List[Event]:
        events = [Event("log", line)]
        if "Initialized server socket" in line:
            events.append(Event("ready"))
        elif m := _RE_ACCEPTED.search(line):
            self.sockets.add(m.group(1))
        elif m := _RE_REMOVED.search(line):
            self.sockets.discard(m.group(1))
            if not self.sockets and self.client:
                events.append(Event("disconnected", self.client))
                self.client = ""
        elif m := _RE_CLIENT.search(line):
            self.client = m.group(1).strip()
            events.append(Event("client", self.client, m.group(2)))
        elif m := _RE_MDNS.search(line):
            ip, how = m.group(1), m.group(2)
            events.append(Event("network", ip, how.split(": ", 1)[1] if ": " in how else ""))
            if ip == "0.0.0.0":
                events.append(Event("warning", "Kein passender Netzwerkadapter gefunden – unter "
                                               "Einstellungen → Erweitert die Netzwerk-IP wählen."))
        elif "starting mirroring" in line:
            events.append(Event("mirroring", self.client))
        elif "raop_rtp starting audio" in line:
            events.append(Event("audio", self.client))
        elif _RE_PIN.search(line):
            events.append(Event("pin", _RE_PIN.search(line).group(1)))
        elif "lost connection with client" in line:
            events.append(Event("lost", self.client))
        elif "DENIED" in line:
            events.append(Event("error", "Verbindung abgelehnt (Gerät blockiert)."))
        elif "failed to create video pipeline" in line:
            events.append(Event("warning", "Videoausgabe konnte nicht erstellt werden – "
                                           "unter Einstellungen → Erweitert eine andere Ausgabe wählen."))
        elif "gst_parse_launch error (audio" in line:
            events.append(Event("error", "Tonausgabe konnte nicht erstellt werden – Ton in den "
                                         "Einstellungen abschalten oder Audiogerät prüfen."))
        elif line.startswith("*** ERROR") and ("dnssd" in line or "socket" in line.lower()):
            events.append(Event("error", line.replace("*** ERROR:", "").strip()))
        return events


# --------------------------------------------------------------------------- #
# Prozess
# --------------------------------------------------------------------------- #

class Engine:
    """Verwaltet den Engine-Prozess. Events landen in `self.events` (thread-sicher)."""

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None
        self.events: "queue.Queue[Event]" = queue.Queue()
        self.path: Optional[Path] = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, settings: Settings) -> None:
        self.stop()
        self.path = find_engine()
        if not self.path:
            raise FileNotFoundError("Die AirPlay-Engine (uxplay) wurde nicht gefunden.")
        args = build_args(settings, self.path)
        kwargs = {}
        if IS_WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        else:
            kwargs["start_new_session"] = True
        self.events.put(Event("log", "> " + subprocess.list2cmdline(args)))
        env = engine_environment(self.path)
        if settings.network_ip.strip():
            env["LU_AIRPLAY_MDNS_IPV4"] = settings.network_ip.strip()
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, env=env,
                                cwd=str(config_dir()), **kwargs)
        self.proc = proc
        threading.Thread(target=self._read, args=(proc,), daemon=True).start()

    def _read(self, proc: subprocess.Popen) -> None:
        parser = OutputParser()
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                for ev in parser.feed(line):
                    self.events.put(ev)
        code = proc.wait()
        if proc is self.proc:
            self.events.put(Event("exited", str(code)))

    def stop(self) -> None:
        proc, self.proc = self.proc, None
        if not proc or proc.poll() is not None:
            return
        try:
            if IS_WINDOWS:
                proc.terminate()
            else:
                os.killpg(proc.pid, signal.SIGINT)  # sauber beenden: mDNS-Abmeldung
            proc.wait(timeout=4)
        except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
            proc.kill()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
