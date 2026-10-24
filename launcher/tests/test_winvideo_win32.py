"""Integrationstest gegen ein echtes Fenster eines fremden Prozesses (nur Windows, läuft im CI)."""

import ctypes
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luairplay import winvideo  # noqa: E402

# Simuliert das d3d11videosink-Fenster: in Videogröße bei 0,0, größer als der Arbeitsbereich
CHILD = textwrap.dedent("""
    import tkinter as tk
    root = tk.Tk()
    root.title("Direct3D11 renderer")
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{sw}x{sh}+0+0")
    root.configure(bg="black")
    root.after(60000, root.destroy)
    root.mainloop()
""")


@unittest.skipUnless(winvideo.IS_WINDOWS, "nur unter Windows")
class Win32VideoWindowTest(unittest.TestCase):
    def start_child(self):
        proc = subprocess.Popen([sys.executable, "-c", CHILD])
        self.addCleanup(proc.kill)
        deadline = time.time() + 20
        while time.time() < deadline:
            if winvideo.top_level_windows_of(proc.pid):
                time.sleep(0.5)  # Tk fertig zeichnen lassen
                return proc, winvideo.top_level_windows_of(proc.pid)[0]
            time.sleep(0.2)
        self.fail("Testfenster ist nicht erschienen")

    @staticmethod
    def rect(hwnd):
        r = winvideo._RECT()
        winvideo.GetWindowRect(hwnd, ctypes.byref(r))
        return winvideo._rect(r)

    @staticmethod
    def title(hwnd):
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    @staticmethod
    def polls(mgr, pid, n=10, **kw):
        args = dict(title="Lu AirPlay – Test", scale_percent=70, always_on_top=False, saved=[],
                    fullscreen=False, video_size=None)
        args.update(kw)
        results = []
        for _ in range(n):
            results.append(mgr.poll(pid, **args))
            time.sleep(0.15)
        return results

    def assert_fitted(self, hwnd, work):
        r = self.rect(hwnd)
        self.assertGreaterEqual(r.left, work.left)
        self.assertGreaterEqual(r.top, work.top)
        self.assertLessEqual(r.right, work.right)
        self.assertLessEqual(r.bottom, work.bottom)
        self.assertLess(r.width, work.width)
        return r

    def test_adopt_track_and_restore(self):
        saved = []
        icon = Path(winvideo.__file__).parent / "assets" / "icon.ico"
        mgr = winvideo.VideoWindowManager(icon_path=str(icon), on_saved=saved.append)

        proc, hwnd = self.start_child()
        work = winvideo._work_area_of(hwnd)
        self.polls(mgr, proc.pid, video_size=(1920, 1080))
        r = self.assert_fitted(hwnd, work)
        self.assertEqual(self.title(hwnd), "Lu AirPlay – Test")
        self.assertFalse(saved, "eigene Positionierung darf nicht als Nutzer-Bewegung zählen")
        client = winvideo._RECT()
        winvideo.GetClientRect(hwnd, ctypes.byref(client))
        self.assertAlmostEqual(client.right / client.bottom, 16 / 9, delta=0.03)

        # Nutzer verschiebt das Fenster -> Position wird gemeldet
        winvideo.SetWindowPos(hwnd, None, work.left + 10, work.top + 10, r.width, r.height,
                              winvideo.SWP_NOZORDER)
        self.polls(mgr, proc.pid, n=3, video_size=(1920, 1080))
        self.assertTrue(saved, "Verschieben wurde nicht erkannt")
        moved = winvideo.Rect(*saved[-1])
        self.assertEqual((moved.left, moved.top), (work.left + 10, work.top + 10))

        # neues Fenster (nächste Sitzung) öffnet an der gemerkten Stelle, jetzt im Hochformat
        proc.kill()
        proc.wait(5)
        mgr.poll(proc.pid, "x", 70, False, list(moved), False)
        proc2, hwnd2 = self.start_child()
        self.polls(mgr, proc2.pid, saved=list(moved), video_size=(886, 1920))
        r2 = self.rect(hwnd2)
        self.assertAlmostEqual((r2.left + r2.right) / 2, (moved.left + moved.right) / 2, delta=3)
        self.assertLessEqual(r2.height, moved.height + 1)
        self.assertLess(r2.width, r2.height)

    def test_snapped_window_kept_after_minimize(self):
        mgr = winvideo.VideoWindowManager()
        proc, hwnd = self.start_child()
        work = winvideo._work_area_of(hwnd)
        used = self.polls(mgr, proc.pid, video_size=(1920, 1080))
        self.assertEqual(used.count(True), 1, "Videogröße gilt nur für das erste Einpassen")

        # wie Win+Links: sichtbarer Rahmen bündig, GetWindowRect ragt um die Greifränder hinaus
        left, _, right, bottom = winvideo._frame_for(winvideo.GetWindowLong(hwnd, winvideo.GWL_STYLE),
                                                     winvideo.GetWindowLong(hwnd, winvideo.GWL_EXSTYLE))
        snapped = winvideo.Rect(work.left - left + 1, work.top,
                                work.left + work.width // 2 + right - 1, work.bottom + bottom - 1)
        winvideo.SetWindowPos(hwnd, None, snapped.left, snapped.top, snapped.width, snapped.height,
                              winvideo.SWP_NOZORDER)
        self.polls(mgr, proc.pid, n=3)
        self.assertEqual(self.rect(hwnd), snapped)

        ctypes.windll.user32.ShowWindowAsync(hwnd, 6)  # SW_MINIMIZE
        time.sleep(0.5)
        self.polls(mgr, proc.pid, n=3)
        ctypes.windll.user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
        self.polls(mgr, proc.pid, n=5)
        self.assertEqual(self.rect(hwnd), snapped, "angedocktes Fenster darf nicht verrutschen")

    def test_fullscreen_left_alone_and_refitted_on_return(self):
        mgr = winvideo.VideoWindowManager()
        proc, hwnd = self.start_child()
        work = winvideo._work_area_of(hwnd)
        # wie GStreamers Vollbild: Rahmen weg + maximiert
        style = winvideo.GetWindowLong(hwnd, winvideo.GWL_STYLE)
        winvideo.SetWindowLong(hwnd, winvideo.GWL_STYLE, style & ~winvideo.WS_OVERLAPPEDWINDOW)
        ctypes.windll.user32.ShowWindowAsync(hwnd, 3)  # SW_MAXIMIZE
        time.sleep(0.5)
        before = self.rect(hwnd)
        self.polls(mgr, proc.pid, fullscreen=True, video_size=(1920, 1080))
        self.assertEqual(self.rect(hwnd), before, "Vollbild darf nicht angefasst werden")

        # Alt+Enter: zurück in den Fenstermodus -> wird eingepasst
        winvideo.SetWindowLong(hwnd, winvideo.GWL_STYLE, style)
        ctypes.windll.user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE
        time.sleep(0.5)
        self.polls(mgr, proc.pid, fullscreen=True, video_size=(1920, 1080))
        self.assert_fitted(hwnd, work)


if __name__ == "__main__":
    unittest.main()
