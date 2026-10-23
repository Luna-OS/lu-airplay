"""Hauptfenster von Lu AirPlay Receiver (Tkinter, keine Zusatzpakete nötig)."""

from __future__ import annotations

import collections
import queue
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

from . import __version__
from .engine import IS_WINDOWS, RESOLUTIONS, Engine, find_engine, local_ipv4_addresses
from .settings import Settings, config_dir, random_pin

APP_TITLE = "Lu AirPlay Receiver"
ASSETS = Path(__file__).resolve().parent / "assets"

# Farben
BG = "#14151f"
CARD = "#1f2130"
CARD_HI = "#2a2d40"
FG = "#f2f3f7"
MUTED = "#9aa0b5"
ACCENT = "#7c5cff"
ACCENT_HI = "#9479ff"
GREEN = "#3ddc84"
YELLOW = "#ffc04d"
RED = "#ff5c6c"
BLUE = "#4da3ff"


def pick_font(*families: str) -> str:
    available = set(tkfont.families())
    for f in families:
        if f in available:
            return f
    return tkfont.nametofont("TkDefaultFont").actual("family")


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.settings = Settings.load()
        self.engine = Engine()
        self.log_lines: "collections.deque[str]" = collections.deque(maxlen=3000)
        self.log_window: "LogWindow | None" = None
        self.state = "stopped"
        self.client = ""
        self.stopping = False

        family = pick_font("Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue",
                           "Cantarell", "Inter", "Noto Sans", "DejaVu Sans")
        self.f_title = tkfont.Font(family=family, size=17, weight="bold")
        self.f_status = tkfont.Font(family=family, size=15, weight="bold")
        self.f_text = tkfont.Font(family=family, size=10)
        self.f_small = tkfont.Font(family=family, size=9)
        self.f_pin = tkfont.Font(family=family, size=26, weight="bold")
        self.f_btn = tkfont.Font(family=family, size=10, weight="bold")

        root.title(APP_TITLE)
        root.configure(bg=BG)
        root.minsize(440, 560)
        root.geometry("460x600")
        self._set_icon()
        self._style()
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.quit)

        self.root.after(100, self._poll)
        if self.settings.autostart:
            self.root.after(300, self.start)
        else:
            self._render()

    # ------------------------------------------------------------------ UI --
    def _set_icon(self) -> None:
        try:
            self._icon = tk.PhotoImage(file=str(ASSETS / "icon.png"))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        if IS_WINDOWS and (ASSETS / "icon.ico").exists():
            try:
                self.root.iconbitmap(default=str(ASSETS / "icon.ico"))
            except tk.TclError:
                pass

    def _style(self) -> None:
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, font=self.f_text, fieldbackground=CARD_HI,
                     bordercolor=CARD_HI, lightcolor=CARD_HI, darkcolor=CARD_HI, insertcolor=FG)
        st.configure("Card.TFrame", background=CARD)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Card.TLabel", background=CARD, foreground=FG)
        st.configure("Muted.TLabel", background=BG, foreground=MUTED, font=self.f_small)
        st.configure("TEntry", fieldbackground=CARD_HI, foreground=FG, padding=6)
        st.configure("TCheckbutton", background=BG, foreground=FG)
        st.map("TCheckbutton", background=[("active", BG)], indicatorcolor=[("selected", ACCENT)])
        st.configure("TCombobox", fieldbackground=CARD_HI, foreground=FG, background=CARD_HI,
                     arrowcolor=FG, padding=4)
        st.map("TCombobox", fieldbackground=[("readonly", CARD_HI)], foreground=[("readonly", FG)])
        self.root.option_add("*TCombobox*Listbox.background", CARD_HI)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        st.configure("Horizontal.TScale", background=BG, troughcolor=CARD_HI)
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=CARD, foreground=MUTED, padding=(14, 6))
        st.map("TNotebook.Tab", background=[("selected", CARD_HI)], foreground=[("selected", FG)])
        st.configure("Vertical.TScrollbar", background=CARD_HI, troughcolor=CARD, arrowcolor=FG)

    def _button(self, parent, text, command, primary=False) -> tk.Button:
        bg, hi = (ACCENT, ACCENT_HI) if primary else (CARD_HI, "#363a52")
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=FG, activebackground=hi,
                      activeforeground=FG, relief="flat", bd=0, padx=16, pady=9, cursor="hand2",
                      font=self.f_btn, highlightthickness=0)
        b.bind("<Enter>", lambda e: b.configure(bg=hi))
        b.bind("<Leave>", lambda e: b.configure(bg=b._base_bg))  # type: ignore[attr-defined]
        b._base_bg = bg  # type: ignore[attr-defined]
        return b

    def _build(self) -> None:
        pad = 18
        # Kopfzeile
        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=pad, pady=(pad, 8))
        try:
            self._logo = tk.PhotoImage(file=str(ASSETS / "logo.png"))
            tk.Label(head, image=self._logo, bg=BG).pack(side="left")
        except tk.TclError:
            pass
        titles = tk.Frame(head, bg=BG)
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="Lu AirPlay", font=self.f_title, bg=BG, fg=FG).pack(anchor="w")
        tk.Label(titles, text="Receiver für iPhone, iPad & Mac", font=self.f_small, bg=BG,
                 fg=MUTED).pack(anchor="w")

        # Status-Karte
        card = tk.Frame(self.root, bg=CARD)
        card.pack(fill="x", padx=pad, pady=8)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=18, pady=16)
        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x")
        self.dot = tk.Canvas(row, width=14, height=14, bg=CARD, highlightthickness=0)
        self.dot_id = self.dot.create_oval(2, 2, 12, 12, fill=MUTED, outline="")
        self.dot.pack(side="left", pady=(4, 0))
        self.status_lbl = tk.Label(row, text="", font=self.f_status, bg=CARD, fg=FG)
        self.status_lbl.pack(side="left", padx=8)
        self.sub_lbl = tk.Label(inner, text="", font=self.f_text, bg=CARD, fg=MUTED, justify="left",
                                anchor="w", wraplength=380)
        self.sub_lbl.pack(fill="x", pady=(6, 0))
        self.warn_lbl = tk.Label(inner, text="", font=self.f_small, bg=CARD, fg=YELLOW, justify="left",
                                 anchor="w", wraplength=380)

        # PIN
        self.pin_frame = tk.Frame(inner, bg=CARD)
        tk.Label(self.pin_frame, text="AirPlay-Code", font=self.f_small, bg=CARD, fg=MUTED).pack(anchor="w")
        self.pin_lbl = tk.Label(self.pin_frame, text="", font=self.f_pin, bg=CARD, fg=FG)
        self.pin_lbl.pack(anchor="w")

        # Anleitung
        self.steps = tk.Frame(self.root, bg=BG)
        self.steps.pack(fill="x", padx=pad, pady=(8, 4))
        self.step_lbls = []
        for i in range(3):
            r = tk.Frame(self.steps, bg=BG)
            r.pack(fill="x", pady=3)
            num = tk.Canvas(r, width=24, height=24, bg=BG, highlightthickness=0)
            num.create_oval(1, 1, 23, 23, fill=CARD_HI, outline="")
            num.create_text(12, 12, text=str(i + 1), fill=FG, font=self.f_small)
            num.pack(side="left", anchor="n")
            lbl = tk.Label(r, text="", font=self.f_text, bg=BG, fg=FG, justify="left", anchor="w",
                           wraplength=360)
            lbl.pack(side="left", padx=10, fill="x")
            self.step_lbls.append(lbl)

        # Name
        name_box = tk.Frame(self.root, bg=BG)
        name_box.pack(fill="x", padx=pad, pady=(14, 4))
        tk.Label(name_box, text="Name des Empfängers", font=self.f_small, bg=BG, fg=MUTED).pack(anchor="w")
        name_row = tk.Frame(name_box, bg=BG)
        name_row.pack(fill="x", pady=(4, 0))
        self.name_var = tk.StringVar(value=self.settings.name)
        entry = ttk.Entry(name_row, textvariable=self.name_var, font=self.f_text)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.apply_name())
        self._button(name_row, "Übernehmen", self.apply_name).pack(side="left", padx=(8, 0))

        # Buttons
        btns = tk.Frame(self.root, bg=BG)
        btns.pack(fill="x", padx=pad, pady=(14, 4))
        self.toggle_btn = self._button(btns, "Starten", self.toggle, primary=True)
        self.toggle_btn.pack(side="left", fill="x", expand=True)
        self._button(btns, "Einstellungen", self.open_settings).pack(side="left", padx=8)
        self._button(btns, "Protokoll", self.open_log).pack(side="left")

        # Fußzeile
        self.footer = tk.Label(self.root, text="", font=self.f_small, bg=BG, fg=MUTED, anchor="w")
        self.footer.pack(side="bottom", fill="x", padx=pad, pady=(4, 12))

    # --------------------------------------------------------------- Status --
    def _render(self) -> None:
        name = self.settings.name
        s = self.state
        colors = {"ready": GREEN, "starting": YELLOW, "connected": BLUE, "mirroring": BLUE,
                  "audio": BLUE, "error": RED, "stopped": MUTED}
        self.dot.itemconfigure(self.dot_id, fill=colors.get(s, MUTED))
        title, sub = {
            "stopped": ("Gestoppt", "Der Empfänger ist aus. Klicke auf „Starten“."),
            "starting": ("Wird gestartet …", "Einen Moment, der Empfänger meldet sich im Netzwerk an. "
                         "Der allererste Start kann bis zu einer Minute dauern."),
            "ready": ("Bereit für AirPlay", f"Wähle auf deinem Gerät „{name}“."),
            "connected": ("Verbunden", f"{self.client or 'Ein Gerät'} hat sich verbunden."),
            "mirroring": ("Bildschirm wird gespiegelt", f"{self.client or 'Ein Gerät'} spiegelt gerade."),
            "audio": ("Audio wird abgespielt", f"{self.client or 'Ein Gerät'} streamt Audio."),
            "error": ("Fehler", self.error_text),
        }.get(s, ("", ""))
        self.status_lbl.configure(text=title)
        self.sub_lbl.configure(text=sub)
        if self.warning and s not in ("stopped", "error"):
            self.warn_lbl.configure(text="⚠ " + self.warning)
            before = self.pin_frame if self.pin_frame.winfo_manager() else None
            self.warn_lbl.pack(fill="x", pady=(8, 0), before=before)
        else:
            self.warn_lbl.pack_forget()

        show_pin = self.settings.pin_enabled and s in ("ready", "connected")
        if show_pin:
            self.pin_lbl.configure(text=" ".join(self.settings.pin))
            self.pin_frame.pack(anchor="w", pady=(12, 0))
        else:
            self.pin_frame.pack_forget()

        steps = [
            "iPhone, iPad oder Mac mit demselben WLAN wie dieser Computer verbinden.",
            "Kontrollzentrum öffnen und auf „Bildschirmsynchronisierung“ tippen "
            "(für Musik: AirPlay-Symbol im Player).",
            f"„{name}“ auswählen" + (" und den angezeigten Code eingeben." if self.settings.pin_enabled else "."),
        ]
        for lbl, text in zip(self.step_lbls, steps):
            lbl.configure(text=text)

        running = s not in ("stopped", "error")
        self.toggle_btn.configure(text="Stoppen" if running else "Starten")
        engine = self.engine.path or find_engine()
        parts = [f"Lu AirPlay {__version__}"]
        if self.settings.video:
            parts.append(self.settings.resolution + f" · {self.settings.fps} fps")
        else:
            parts.append("nur Audio")
        if not engine:
            parts.append("Engine fehlt!")
        if self.network and running:
            parts.append("Netz: " + self.network)
        self.footer.configure(text="   ·   ".join(parts))

    error_text = ""
    warning = ""
    network = ""

    def _set_state(self, state: str, error: str = "") -> None:
        self.state = state
        if error:
            self.error_text = error
        self._render()

    def _poll(self) -> None:
        try:
            while True:
                ev = self.engine.events.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _handle(self, ev) -> None:
        if ev.kind == "log":
            self.log_lines.append(ev.text)
            if self.log_window:
                self.log_window.append(ev.text)
            return
        if ev.kind == "ready":
            self.client = ""
            self._set_state("ready")
        elif ev.kind == "client":
            self.client = ev.text
            self._set_state("connected")
        elif ev.kind == "mirroring":
            self._set_state("mirroring")
        elif ev.kind == "audio":
            if self.state != "mirroring":
                self._set_state("audio")
        elif ev.kind in ("disconnected", "lost"):
            self.client = ""
            if self.engine.running:
                self._set_state("ready")
        elif ev.kind == "network":
            self.network = ev.text + (f" ({ev.detail})" if ev.detail else "")
            self._render()
        elif ev.kind == "pin":
            self.settings.pin = ev.text
            self._render()
        elif ev.kind == "warning":
            self.warning = ev.text
            self._render()
        elif ev.kind == "error":
            self.error_text = ev.text
            self.log_lines.append("! " + ev.text)
        elif ev.kind == "exited":
            if self.stopping:
                return
            self.log_lines.append(f"! Engine beendet (Code {ev.text})")
            if self.log_window:
                self.log_window.append(f"! Engine beendet (Code {ev.text})")
            hint = self.error_text or f"Die Engine wurde unerwartet beendet (Code {ev.text})."
            self._set_state("error", hint + "  (Details unter „Protokoll“)")

    # ------------------------------------------------------------- Aktionen --
    def start(self) -> None:
        self.network = ""
        self.stopping = False
        self.error_text = ""
        self.warning = ""
        self._set_state("starting")
        try:
            self.engine.start(self.settings)
        except FileNotFoundError as e:
            self._set_state("error", f"{e} Bitte das komplette Paket neu entpacken.")
        except OSError as e:
            self._set_state("error", f"Engine konnte nicht gestartet werden: {e}")

    def stop(self) -> None:
        self.stopping = True
        self.engine.stop()
        self.client = ""
        self._set_state("stopped")

    def toggle(self) -> None:
        if self.state in ("stopped", "error"):
            self.start()
        else:
            self.stop()

    def restart_if_running(self) -> None:
        if self.state not in ("stopped", "error"):
            self.stop()
            self.root.after(200, self.start)
        else:
            self._render()

    def apply_name(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            self.name_var.set(self.settings.name)
            return
        if name != self.settings.name:
            self.settings.name = name
            self.settings.save()
            self.restart_if_running()

    def open_settings(self) -> None:
        SettingsDialog(self)

    def open_log(self) -> None:
        if self.log_window and self.log_window.top.winfo_exists():
            self.log_window.top.lift()
            return
        self.log_window = LogWindow(self)

    def quit(self) -> None:
        self.stopping = True
        self.engine.stop()
        self.root.destroy()


# ----------------------------------------------------------------------- #
class SettingsDialog:
    def __init__(self, app: App) -> None:
        self.app = app
        s = app.settings
        top = self.top = tk.Toplevel(app.root, bg=BG)
        top.title("Einstellungen – " + APP_TITLE)
        top.transient(app.root)
        top.resizable(False, False)

        nb = ttk.Notebook(top)
        nb.pack(fill="both", expand=True, padx=14, pady=(14, 0))
        video = tk.Frame(nb, bg=BG, padx=14, pady=12)
        audio = tk.Frame(nb, bg=BG, padx=14, pady=12)
        access = tk.Frame(nb, bg=BG, padx=14, pady=12)
        expert = tk.Frame(nb, bg=BG, padx=14, pady=12)
        nb.add(video, text="Bild")
        nb.add(audio, text="Ton")
        nb.add(access, text="Zugriff")
        nb.add(expert, text="Erweitert")

        self.v = {
            "video": tk.BooleanVar(value=s.video),
            "resolution": tk.StringVar(value=s.resolution),
            "fps": tk.StringVar(value=str(s.fps)),
            "fullscreen": tk.BooleanVar(value=s.fullscreen),
            "keep_window": tk.BooleanVar(value=s.keep_window),
            "software_decoding": tk.BooleanVar(value=s.software_decoding),
            "rotation": tk.StringVar(value={"": "Keine", "R": "90° rechts", "L": "90° links"}[s.rotation or ""]),
            "audio": tk.BooleanVar(value=s.audio),
            "volume": tk.IntVar(value=s.volume),
            "pin_enabled": tk.BooleanVar(value=s.pin_enabled),
            "takeover": tk.BooleanVar(value=s.takeover),
            "autostart": tk.BooleanVar(value=s.autostart),
            "videosink": tk.StringVar(value=s.videosink),
            "port": tk.StringVar(value=str(s.port or "")),
            "extra_args": tk.StringVar(value=s.extra_args),
            "network_ip": tk.StringVar(value=s.network_ip),
        }

        def check(parent, key, text):
            ttk.Checkbutton(parent, text=text, variable=self.v[key]).pack(anchor="w", pady=3)

        def labeled(parent, text):
            tk.Label(parent, text=text, bg=BG, fg=MUTED, font=app.f_small).pack(anchor="w", pady=(10, 2))

        # Bild
        check(video, "video", "Bildschirm spiegeln (aus = nur Audio)")
        labeled(video, "Auflösung")
        ttk.Combobox(video, textvariable=self.v["resolution"], values=list(RESOLUTIONS),
                     state="readonly", width=12).pack(anchor="w")
        tk.Label(video, text="4K nutzt H.265 und braucht einen schnellen Rechner.", bg=BG, fg=MUTED,
                 font=app.f_small).pack(anchor="w")
        labeled(video, "Bildrate")
        ttk.Combobox(video, textvariable=self.v["fps"], values=["30", "60"], state="readonly",
                     width=12).pack(anchor="w")
        labeled(video, "Drehung")
        ttk.Combobox(video, textvariable=self.v["rotation"], values=["Keine", "90° rechts", "90° links"],
                     state="readonly", width=12).pack(anchor="w")
        tk.Frame(video, bg=BG, height=8).pack()
        check(video, "fullscreen", "Im Vollbild starten (Alt+Enter wechselt)" if IS_WINDOWS
              else "Im Vollbild starten")
        check(video, "keep_window", "Videofenster nach dem Trennen offen lassen")
        check(video, "software_decoding", "Software-Dekodierung (bei Bildfehlern)")

        # Ton
        check(audio, "audio", "Ton abspielen")
        labeled(audio, "Startlautstärke")
        vol_row = tk.Frame(audio, bg=BG)
        vol_row.pack(fill="x")
        vol_lbl = tk.Label(vol_row, text=f"{s.volume} %", bg=BG, fg=FG, width=6)
        ttk.Scale(vol_row, from_=0, to=100, variable=self.v["volume"], length=220,
                  command=lambda val: vol_lbl.configure(text=f"{int(float(val))} %")).pack(side="left")
        vol_lbl.pack(side="left", padx=8)
        tk.Label(audio, text="Die Lautstärke lässt sich danach am iPhone regeln.", bg=BG, fg=MUTED,
                 font=app.f_small).pack(anchor="w", pady=(8, 0))

        # Zugriff
        check(access, "pin_enabled", "Code beim Verbinden verlangen")
        pin_row = tk.Frame(access, bg=BG)
        pin_row.pack(anchor="w", pady=(2, 8))
        self.pin_lbl = tk.Label(pin_row, text=f"Aktueller Code: {s.pin}", bg=BG, fg=FG)
        self.pin_lbl.pack(side="left")
        self.new_pin = s.pin
        app._button(pin_row, "Neuer Code", self._regen_pin).pack(side="left", padx=10)
        tk.Label(access, text="Bekannte Geräte müssen den Code nur einmal eingeben.", bg=BG, fg=MUTED,
                 font=app.f_small).pack(anchor="w")
        tk.Frame(access, bg=BG, height=8).pack()
        check(access, "takeover", "Neues Gerät darf laufende Verbindung übernehmen")
        check(access, "autostart", "Empfänger beim Öffnen der App automatisch starten")
        if IS_WINDOWS:
            tk.Frame(access, bg=BG, height=8).pack()
            app._button(access, "Windows-Firewall freigeben", self._firewall).pack(anchor="w")
            tk.Label(access, text="Nötig, wenn der Empfänger auf dem iPhone nicht erscheint.", bg=BG,
                     fg=MUTED, font=app.f_small).pack(anchor="w", pady=(4, 0))

        # Erweitert
        labeled(expert, "GStreamer-Videoausgabe (leer = automatisch)")
        ttk.Combobox(expert, textvariable=self.v["videosink"], width=28,
                     values=(["", "d3d11videosink", "d3d12videosink", "glimagesink"] if IS_WINDOWS else
                             ["", "autovideosink", "xvimagesink", "glimagesink", "waylandsink",
                              "osxvideosink"])).pack(anchor="w")
        labeled(expert, "Netzwerk (IP-Adresse im WLAN des iPhones; leer = automatisch)")
        ttk.Combobox(expert, textvariable=self.v["network_ip"], width=28,
                     values=[""] + local_ipv4_addresses()).pack(anchor="w")
        labeled(expert, "Netzwerk-Port (leer = automatisch, sonst z. B. 7100)")
        ttk.Entry(expert, textvariable=self.v["port"], width=12).pack(anchor="w")
        labeled(expert, "Zusätzliche Engine-Optionen (UxPlay-Syntax)")
        ttk.Entry(expert, textvariable=self.v["extra_args"], width=40).pack(anchor="w")
        tk.Frame(expert, bg=BG, height=10).pack()
        app._button(expert, "Konfigurationsordner öffnen", self._open_config).pack(anchor="w")

        # Unten
        bottom = tk.Frame(top, bg=BG)
        bottom.pack(fill="x", padx=14, pady=14)
        app._button(bottom, "Speichern", self.save, primary=True).pack(side="right")
        app._button(bottom, "Abbrechen", top.destroy).pack(side="right", padx=8)

        top.grab_set()
        top.focus_set()

    def _regen_pin(self) -> None:
        self.new_pin = random_pin()
        self.pin_lbl.configure(text=f"Aktueller Code: {self.new_pin}")

    def _firewall(self) -> None:
        engine = find_engine()
        if not engine:
            messagebox.showerror(APP_TITLE, "Engine nicht gefunden.", parent=self.top)
            return
        import ctypes
        # Alle Profile: Windows stuft Heim-WLANs oft als "Öffentlich" ein
        params = (f'advfirewall firewall add rule name="Lu AirPlay (App)" dir=in action=allow '
                  f'program="{engine}" enable=yes profile=any')
        rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", params, None, 0)
        if rc <= 32:
            messagebox.showerror(APP_TITLE, "Firewall-Regel konnte nicht angelegt werden.", parent=self.top)
        else:
            messagebox.showinfo(APP_TITLE, "Firewall-Regel für Lu AirPlay wurde angelegt.", parent=self.top)

    def _open_config(self) -> None:
        import subprocess
        path = str(config_dir())
        if IS_WINDOWS:
            subprocess.Popen(["explorer", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def save(self) -> None:
        s, v = self.app.settings, self.v
        port_txt = v["port"].get().strip()
        if port_txt and not (port_txt.isdigit() and 1024 <= int(port_txt) <= 65533):
            messagebox.showerror(APP_TITLE, "Der Port muss zwischen 1024 und 65533 liegen.", parent=self.top)
            return
        s.video = v["video"].get()
        s.resolution = v["resolution"].get()
        s.fps = int(v["fps"].get())
        s.fullscreen = v["fullscreen"].get()
        s.keep_window = v["keep_window"].get()
        s.software_decoding = v["software_decoding"].get()
        s.rotation = {"Keine": "", "90° rechts": "R", "90° links": "L"}[v["rotation"].get()]
        s.audio = v["audio"].get()
        s.volume = int(v["volume"].get())
        s.pin_enabled = v["pin_enabled"].get()
        s.pin = self.new_pin
        s.takeover = v["takeover"].get()
        s.autostart = v["autostart"].get()
        s.videosink = v["videosink"].get().strip()
        s.port = int(port_txt) if port_txt else 0
        s.extra_args = v["extra_args"].get().strip()
        s.network_ip = v["network_ip"].get().strip()
        s.save()
        self.top.destroy()
        self.app.restart_if_running()


# ----------------------------------------------------------------------- #
class LogWindow:
    def __init__(self, app: App) -> None:
        self.app = app
        top = self.top = tk.Toplevel(app.root, bg=BG)
        top.title("Protokoll – " + APP_TITLE)
        top.geometry("760x420")
        bottom = tk.Frame(top, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        app._button(bottom, "Kopieren", self.copy).pack(side="right")
        frame = tk.Frame(top, bg=BG)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        mono = tkfont.Font(family=pick_font("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono",
                                            "Courier New"), size=9)
        self.text = tk.Text(frame, bg=CARD, fg=FG, insertbackground=FG, relief="flat", font=mono,
                            wrap="none", padx=8, pady=8)
        sb = ttk.Scrollbar(frame, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.insert("end", "\n".join(app.log_lines) + ("\n" if app.log_lines else ""))
        self.text.see("end")
        self.text.configure(state="disabled")

    def append(self, line: str) -> None:
        if not self.top.winfo_exists():
            return
        at_end = self.text.yview()[1] > 0.99
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n")
        self.text.configure(state="disabled")
        if at_end:
            self.text.see("end")

    def copy(self) -> None:
        self.top.clipboard_clear()
        self.top.clipboard_append("\n".join(self.app.log_lines))


# ----------------------------------------------------------------------- #
def main() -> None:
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LuOS.LuAirPlay")
        except Exception:
            pass
    root = tk.Tk(className="lu-airplay")
    App(root)
    root.mainloop()
