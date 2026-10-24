"""Macht das Videofenster der Engine zu einem normalen, verschiebbaren Fenster (Windows).

GStreamers d3d11videosink erzeugt sein eigenes Fenster genau in Videogröße (z. B. 1920x1080
oder 886x1920 im Hochformat). Auf einem 1080p-Bildschirm ist das bildschirmfüllend, die
Titelleiste liegt oberhalb des Bildschirms – man kann das Fenster weder greifen noch
verschieben. Die App findet deshalb die Fenster des Engine-Prozesses und
  * passt sie in den Arbeitsbereich des Monitors ein (Seitenverhältnis bleibt),
  * gibt ihnen Titelleiste, Rahmen, Titel und Icon,
  * merkt sich, wohin der Nutzer das Fenster geschoben/gezogen hat.

Die Geometrie-Funktionen sind plattformunabhängig (und getestet); nur `VideoWindowManager`
spricht die Win32-API an.
"""

from __future__ import annotations

import sys
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

IS_WINDOWS = sys.platform.startswith("win")


class Rect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def intersection_area(self, other: "Rect") -> int:
        w = min(self.right, other.right) - max(self.left, other.left)
        h = min(self.bottom, other.bottom) - max(self.top, other.top)
        return max(0, w) * max(0, h)


# Rahmenstärken (links, oben, rechts, unten), die Windows um den Client-Bereich legt
Frame = Tuple[int, int, int, int]

MIN_CLIENT = 160


def fit_size(content_w: int, content_h: int, box_w: int, box_h: int) -> Tuple[int, int]:
    """Größte Größe mit dem Seitenverhältnis content_w:content_h, die in box_w x box_h passt."""
    if content_w <= 0 or content_h <= 0:
        content_w, content_h = 16, 9
    box_w, box_h = max(1, box_w), max(1, box_h)
    scale = min(box_w / content_w, box_h / content_h)
    w = max(1, round(content_w * scale))
    h = max(1, round(content_h * scale))
    return min(w, box_w), min(h, box_h)


def window_rect_for_client(left: int, top: int, client_w: int, client_h: int, frame: Frame) -> Rect:
    fl, ft, fr, fb = frame
    return Rect(left, top, left + fl + client_w + fr, top + ft + client_h + fb)


def plan_window(content_w: int, content_h: int, work: Rect, frame: Frame,
                scale_percent: int = 70, saved: Optional[Rect] = None) -> Rect:
    """Fensterrechteck (inkl. Rahmen) für ein Video mit content_w x content_h.

    Ohne gespeicherte Position: `scale_percent` % des Arbeitsbereichs, zentriert.
    Mit gespeicherter Position: das gespeicherte Rechteck ist der Rahmen, in den das Video
    (mit seinem aktuellen Seitenverhältnis) eingepasst und zentriert wird. So bleibt die vom
    Nutzer gewählte Position/Größe erhalten, auch wenn das iPhone gedreht wurde.
    Das Ergebnis liegt immer vollständig im Arbeitsbereich.
    """
    fl, ft, fr, fb = frame
    max_client_w = max(MIN_CLIENT, work.width - fl - fr)
    max_client_h = max(MIN_CLIENT, work.height - ft - fb)

    if saved is not None and saved.width > fl + fr and saved.height > ft + fb:
        box_w = min(saved.width - fl - fr, max_client_w)
        box_h = min(saved.height - ft - fb, max_client_h)
        cw, ch = fit_size(content_w, content_h, max(MIN_CLIENT, box_w), max(MIN_CLIENT, box_h))
        cx = (saved.left + saved.right) // 2
        cy = (saved.top + saved.bottom) // 2
    else:
        pct = max(20, min(100, scale_percent)) / 100.0
        cw, ch = fit_size(content_w, content_h, int(max_client_w * pct), int(max_client_h * pct))
        cx = (work.left + work.right) // 2
        cy = (work.top + work.bottom) // 2

    cw, ch = min(cw, max_client_w), min(ch, max_client_h)
    win_w, win_h = fl + cw + fr, ft + ch + fb
    left = cx - win_w // 2
    top = cy - win_h // 2
    # vollständig in den Arbeitsbereich schieben (Titelleiste immer erreichbar)
    left = max(work.left, min(left, work.right - win_w))
    top = max(work.top, min(top, work.bottom - win_h))
    return Rect(left, top, left + win_w, top + win_h)


def pick_work_area(saved: Optional[Rect], work_areas: List[Rect], fallback: Rect) -> Tuple[Optional[Rect], Rect]:
    """Monitor für ein gespeichertes Rechteck wählen. Liegt es auf keinem Monitor mehr
    (z. B. zweiter Bildschirm abgesteckt), wird die Position verworfen."""
    if saved is None or not work_areas:
        return None, fallback
    best = max(work_areas, key=lambda w: w.intersection_area(saved))
    if best.intersection_area(saved) <= 0:
        return None, fallback
    return saved, best


def fits_inside(r: Rect, work: Rect, frame: Frame = (0, 0, 0, 0)) -> bool:
    """Liegt r (GetWindowRect) sichtbar im Arbeitsbereich? Unter Windows 10/11 zählen die
    unsichtbaren Greifränder links/rechts/unten mit; ein angedocktes (Win+Pfeil) oder bündig an
    Bildschirmrand/Taskleiste geschobenes Fenster ragt deshalb um diese Ränder hinaus."""
    left, _, right, bottom = frame
    return (work.left <= r.left + left and work.top <= r.top
            and r.right - right <= work.right and r.bottom - bottom <= work.bottom)


def rect_from_list(value) -> Optional[Rect]:
    if isinstance(value, (list, tuple)) and len(value) == 4 and all(isinstance(v, int) for v in value):
        r = Rect(*value)
        if r.width > 0 and r.height > 0:
            return r
    return None


# --------------------------------------------------------------------------- #
# Win32
# --------------------------------------------------------------------------- #

if IS_WINDOWS:  # pragma: no cover - nur unter Windows ausführbar
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class _RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT),
                    ("dwFlags", wintypes.DWORD)]

    LONG_PTR = ctypes.c_ssize_t
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                         ctypes.POINTER(_RECT), wintypes.LPARAM)

    def _sig(fn, res, *args):
        f = getattr(user32, fn)
        f.restype = res
        f.argtypes = list(args)
        return f

    EnumWindows = _sig("EnumWindows", wintypes.BOOL, WNDENUMPROC, wintypes.LPARAM)
    EnumDisplayMonitors = _sig("EnumDisplayMonitors", wintypes.BOOL, wintypes.HDC,
                               ctypes.POINTER(_RECT), MONITORENUMPROC, wintypes.LPARAM)
    GetWindowThreadProcessId = _sig("GetWindowThreadProcessId", wintypes.DWORD, wintypes.HWND,
                                    ctypes.POINTER(wintypes.DWORD))
    IsWindow = _sig("IsWindow", wintypes.BOOL, wintypes.HWND)
    IsWindowVisible = _sig("IsWindowVisible", wintypes.BOOL, wintypes.HWND)
    IsIconic = _sig("IsIconic", wintypes.BOOL, wintypes.HWND)
    IsZoomed = _sig("IsZoomed", wintypes.BOOL, wintypes.HWND)
    GetWindow = _sig("GetWindow", wintypes.HWND, wintypes.HWND, wintypes.UINT)
    GetWindowRect = _sig("GetWindowRect", wintypes.BOOL, wintypes.HWND, ctypes.POINTER(_RECT))
    GetClientRect = _sig("GetClientRect", wintypes.BOOL, wintypes.HWND, ctypes.POINTER(_RECT))
    SetWindowPos = _sig("SetWindowPos", wintypes.BOOL, wintypes.HWND, wintypes.HWND, ctypes.c_int,
                        ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT)
    MonitorFromWindow = _sig("MonitorFromWindow", wintypes.HANDLE, wintypes.HWND, wintypes.DWORD)
    GetMonitorInfoW = _sig("GetMonitorInfoW", wintypes.BOOL, wintypes.HANDLE,
                           ctypes.POINTER(_MONITORINFO))
    AdjustWindowRectEx = _sig("AdjustWindowRectEx", wintypes.BOOL, ctypes.POINTER(_RECT),
                              wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    SetWindowTextW = _sig("SetWindowTextW", wintypes.BOOL, wintypes.HWND, wintypes.LPCWSTR)
    GetClassNameW = _sig("GetClassNameW", ctypes.c_int, wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    SendMessageW = _sig("SendMessageW", LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                        wintypes.LPARAM)
    LoadImageW = _sig("LoadImageW", wintypes.HANDLE, wintypes.HINSTANCE, wintypes.LPCWSTR,
                      wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT)
    SetForegroundWindow = _sig("SetForegroundWindow", wintypes.BOOL, wintypes.HWND)
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        GetWindowLong = _sig("GetWindowLongPtrW", LONG_PTR, wintypes.HWND, ctypes.c_int)
        SetWindowLong = _sig("SetWindowLongPtrW", LONG_PTR, wintypes.HWND, ctypes.c_int, LONG_PTR)
    else:
        GetWindowLong = _sig("GetWindowLongW", LONG_PTR, wintypes.HWND, ctypes.c_int)
        SetWindowLong = _sig("SetWindowLongW", LONG_PTR, wintypes.HWND, ctypes.c_int, LONG_PTR)

    GW_OWNER = 4
    GWL_STYLE, GWL_EXSTYLE = -16, -20
    WS_CAPTION, WS_SYSMENU, WS_THICKFRAME = 0x00C00000, 0x00080000, 0x00040000
    WS_MINIMIZEBOX, WS_MAXIMIZEBOX, WS_POPUP = 0x00020000, 0x00010000, 0x80000000
    WS_OVERLAPPEDWINDOW = WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
    WS_EX_TOPMOST = 0x00000008
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
    SWP_FRAMECHANGED, SWP_SHOWWINDOW = 0x20, 0x40
    HWND_TOPMOST, HWND_NOTOPMOST = wintypes.HWND(-1), wintypes.HWND(-2)
    MONITOR_DEFAULTTONEAREST = 2
    WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
    IMAGE_ICON, LR_LOADFROMFILE = 1, 0x10

    def _rect(r: "_RECT") -> Rect:
        return Rect(r.left, r.top, r.right, r.bottom)

    def _work_area_of(hwnd) -> Rect:
        mon = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        GetMonitorInfoW(mon, ctypes.byref(info))
        return _rect(info.rcWork)

    def _all_work_areas() -> List[Rect]:
        areas: List[Rect] = []

        def cb(hmon, hdc, lprect, lparam):
            info = _MONITORINFO()
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            if GetMonitorInfoW(hmon, ctypes.byref(info)):
                areas.append(_rect(info.rcWork))
            return True

        EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
        return areas

    def _frame_for(style: int, exstyle: int) -> Frame:
        r = _RECT(0, 0, 100, 100)
        AdjustWindowRectEx(ctypes.byref(r), style & 0xFFFFFFFF, False, exstyle & 0xFFFFFFFF)
        return (-r.left, -r.top, r.right - 100, r.bottom - 100)

    def top_level_windows_of(pid: int) -> List[int]:
        found: List[int] = []

        def cb(hwnd, lparam):
            owner = wintypes.DWORD()
            GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and IsWindowVisible(hwnd) and not GetWindow(hwnd, GW_OWNER):
                found.append(hwnd)
            return True

        EnumWindows(WNDENUMPROC(cb), 0)
        return found

    SendMessageTimeoutW = _sig("SendMessageTimeoutW", LONG_PTR, wintypes.HWND, wintypes.UINT,
                               wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                               ctypes.POINTER(ctypes.c_size_t))
    WM_SETTEXT = 0x000C
    SMTO_ABORTIFHUNG = 0x0002
    SWP_ASYNCWINDOWPOS = 0x4000

    def _send(hwnd, msg, wparam, lparam) -> None:
        """Nachricht an das Fenster der Engine, ohne die Oberfläche zu blockieren, falls deren
        Fenster-Thread gerade beschäftigt ist."""
        result = ctypes.c_size_t()
        SendMessageTimeoutW(hwnd, msg, wparam, lparam, SMTO_ABORTIFHUNG, 250, ctypes.byref(result))

    class _WinState:
        __slots__ = ("seen", "fitted", "away", "rect", "target", "settle", "content")

        def __init__(self) -> None:
            self.seen = 0          # Anzahl Abfragen seit dem Erscheinen
            self.fitted = False    # jemals eingepasst?
            self.away = False      # gerade (oder zuletzt) minimiert/maximiert/Vollbild
            self.rect = None       # zuletzt bekanntes Rechteck (Basis für "vom Nutzer bewegt")
            self.target = None     # Rechteck der eigenen, evtl. noch ausstehenden Positionierung
            self.settle = 0        # Abfragen, in denen die eigene Positionierung ankommen darf
            self.content = None    # Bildgröße, mit der das Fenster eingepasst wurde

    class VideoWindowManager:
        """Wird regelmäßig (alle ~300 ms) aus der Tk-Hauptschleife aufgerufen.

        GStreamer verschiebt/skaliert sein Fenster nach dem ersten Anzeigen nie wieder (auch nicht
        bei Drehung des iPhones); jede Sitzung bekommt aber ein neues Fenster. Vollbild (Alt+Enter)
        heißt: Rahmen weg + maximiert. Minimierte, maximierte und Vollbild-Fenster bleiben
        unangetastet. Kehrt ein Fenster in den Normalzustand zurück, bleibt die von Windows bzw.
        GStreamer wiederhergestellte Position erhalten – eingepasst wird nur ein Fenster, das noch
        nie eingepasst war (z. B. im Vollbild gestartet) oder das nicht auf seinen Monitor passt.
        """

        GRACE = 2              # Abfragen warten, bis ein neues Fenster fertig angezeigt ist
        GRACE_FULLSCREEN = 6   # ... länger, wenn GStreamer gleich in den Vollbildmodus wechselt
        SETTLE = 6

        def __init__(self, icon_path: Optional[str] = None,
                     on_saved: Optional[Callable[[List[int]], None]] = None) -> None:
            self.windows: Dict[int, _WinState] = {}
            self.icon_path = icon_path
            self.on_saved = on_saved
            self._icons = None
            self._topmost = False

        @property
        def known(self) -> Dict[int, "_WinState"]:
            return self.windows

        def _load_icons(self):
            if self._icons is None and self.icon_path:
                big = LoadImageW(None, self.icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
                small = LoadImageW(None, self.icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                self._icons = (big, small)
            return self._icons

        def poll(self, pid: Optional[int], title: str, scale_percent: int, always_on_top: bool,
                 saved: Optional[List[int]], fullscreen: bool,
                 video_size: Optional[Tuple[int, int]] = None) -> bool:
            """video_size gilt für das nächste neue Fenster. Rückgabe True, sobald ein Fenster damit
            eingepasst wurde – dann gehört die Größe zu diesem Fenster und ist für spätere Fenster
            derselben Verbindung (z. B. ein YouTube-Video nach dem Spiegeln) veraltet."""
            self._topmost = always_on_top
            used = False
            if not pid:
                self.windows.clear()
                return used
            current = top_level_windows_of(pid)
            for hwnd in list(self.windows):
                if hwnd not in current or not IsWindow(hwnd):
                    del self.windows[hwnd]
            for hwnd in current:
                st = self.windows.setdefault(hwnd, _WinState())
                st.seen += 1
                if st.seen == 1:
                    self._decorate(hwnd, title)
                if st.seen < (self.GRACE_FULLSCREEN if fullscreen else self.GRACE):
                    continue
                if self._is_fullscreen_or_maximized(hwnd):
                    st.away = True
                    st.settle = 0
                    continue
                if not st.fitted:
                    used |= self._fit(hwnd, st, scale_percent, rect_from_list(saved), video_size)
                elif st.away:
                    st.away = False
                    self._returned(hwnd, st, scale_percent, saved)
                else:
                    self._track(hwnd, st)
            return used

        def retitle(self, title: str) -> None:
            for hwnd in self.windows:
                self._decorate(hwnd, title, icon=False)

        def _decorate(self, hwnd, title: str, icon: bool = True) -> None:
            buf = ctypes.create_unicode_buffer(title)
            _send(hwnd, WM_SETTEXT, 0, ctypes.cast(buf, ctypes.c_void_p).value)
            icons = self._load_icons() if icon else None
            if icons:
                _send(hwnd, WM_SETICON, ICON_BIG, icons[0] or 0)
                _send(hwnd, WM_SETICON, ICON_SMALL, icons[1] or 0)

        @staticmethod
        def _is_fullscreen_or_maximized(hwnd) -> bool:
            if IsIconic(hwnd) or IsZoomed(hwnd):
                return True
            style = GetWindowLong(hwnd, GWL_STYLE)
            return not (style & WS_CAPTION)

        def _fit(self, hwnd, st: "_WinState", scale_percent: int, saved: Optional[Rect],
                 video_size: Optional[Tuple[int, int]]) -> bool:
            style = GetWindowLong(hwnd, GWL_STYLE)
            exstyle = GetWindowLong(hwnd, GWL_EXSTYLE)
            used = bool(video_size and video_size[0] > 0 and video_size[1] > 0)
            if used:
                cw, ch = video_size
            else:
                # Notbehelf: Windows hat das zu große Fenster evtl. schon gekappt
                client = _RECT()
                GetClientRect(hwnd, ctypes.byref(client))
                cw, ch = client.right - client.left, client.bottom - client.top
            saved, work = pick_work_area(saved, _all_work_areas(), _work_area_of(hwnd))
            target = plan_window(cw, ch, work, _frame_for(style, exstyle), scale_percent, saved)
            after = HWND_TOPMOST if self._topmost else HWND_NOTOPMOST
            SetWindowPos(hwnd, after, target.left, target.top, target.width, target.height,
                         SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS)
            st.fitted, st.target, st.settle = True, target, self.SETTLE
            st.content = (cw, ch)
            return used

        def _returned(self, hwnd, st: "_WinState", scale_percent: int, saved) -> None:
            """Zurück aus minimiert/maximiert/Vollbild: Wiederhergestelltes behalten."""
            now = self._rect_of(hwnd)
            if now is None:
                return
            frame = _frame_for(GetWindowLong(hwnd, GWL_STYLE), GetWindowLong(hwnd, GWL_EXSTYLE))
            if not fits_inside(now, _work_area_of(hwnd), frame):
                self._fit(hwnd, st, scale_percent, rect_from_list(saved), st.content)
                return
            if st.rect is not None and now != st.rect:
                self._report(st, now)      # z. B. maximiert auf anderen Monitor geschoben
            st.rect = now

        @staticmethod
        def _rect_of(hwnd) -> Optional[Rect]:
            r = _RECT()
            if not GetWindowRect(hwnd, ctypes.byref(r)):
                return None
            return _rect(r)

        def _report(self, st: "_WinState", now: Rect) -> None:
            st.rect = now
            if self.on_saved and now.width > 0 and now.height > 0:
                self.on_saved(list(now))

        def _track(self, hwnd, st: "_WinState") -> None:
            """Verschiebt/zieht der Nutzer das Fenster, Position merken."""
            now = self._rect_of(hwnd)
            if now is None:
                return
            if st.settle:
                # eigene (asynchrone) Positionierung ist evtl. noch unterwegs
                if now == st.target:
                    st.settle, st.rect = 0, now
                    return
                st.settle -= 1
                if st.settle:
                    return
                # kam nie exakt an (Rundung) oder der Nutzer hat inzwischen verschoben:
                # aktuelle Lage als vom Nutzer gewählt übernehmen
                self._report(st, now)
                return
            if now != st.rect:
                self._report(st, now)

        def set_topmost(self, on: bool) -> None:
            self._topmost = on
            for hwnd in self.windows:
                SetWindowPos(hwnd, HWND_TOPMOST if on else HWND_NOTOPMOST, 0, 0, 0, 0,
                             SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS)

else:
    class VideoWindowManager:  # type: ignore[no-redef]
        """Unter Linux/macOS verwaltet der Fenstermanager das Videofenster selbst."""

        def __init__(self, *args, **kwargs) -> None:
            pass

        def poll(self, *args, **kwargs) -> bool:
            return False

        def set_topmost(self, on: bool) -> None:
            pass

        def retitle(self, title: str) -> None:
            pass
