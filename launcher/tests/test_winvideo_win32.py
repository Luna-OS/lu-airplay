"""Integrationstest gegen ein echtes Fenster eines fremden Prozesses (nur Windows, läuft im CI)."""

import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luairplay import winvideo  # noqa: E402

# Simuliert das d3d11videosink-Fenster: bildschirmgroß, bei 0,0, Titelleiste über dem Bildschirm
CHILD = textwrap.dedent("""
    import tkinter as tk
    root = tk.Tk()
    root.title("Direct3D11 renderer")
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{sw}x{sh}+0+-30")
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
            wins = winvideo.top_level_windows_of(proc.pid)
            if wins:
                time.sleep(0.5)  # Tk fertig zeichnen lassen
                return proc, winvideo.top_level_windows_of(proc.pid)[0]
            time.sleep(0.2)
        self.fail("Testfenster ist nicht erschienen")

    @staticmethod
    def rect(hwnd):
        r = winvideo._RECT()
        winvideo.GetWindowRect(hwnd, winvideo.ctypes.byref(r))
        return winvideo._rect(r)

    @staticmethod
    def title(hwnd):
        import ctypes
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def test_adopt_track_and_restore(self):
        saved = []
        icon = Path(winvideo.__file__).parent / "assets" / "icon.ico"
        mgr = winvideo.VideoWindowManager(icon_path=str(icon), on_saved=saved.append)

        proc, hwnd = self.start_child()
        work = winvideo._work_area_of(hwnd)
        mgr.poll(proc.pid, "Lu AirPlay – Test", 70, False, [], False)
        time.sleep(0.5)

        r = self.rect(hwnd)
        self.assertEqual(self.title(hwnd), "Lu AirPlay – Test")
        self.assertGreaterEqual(r.left, work.left)
        self.assertGreaterEqual(r.top, work.top)       # Titelleiste sichtbar
        self.assertLessEqual(r.right, work.right)
        self.assertLessEqual(r.bottom, work.bottom)
        self.assertLess(r.width, work.width)             # nicht mehr bildschirmfüllend
        style = winvideo.GetWindowLong(hwnd, winvideo.GWL_STYLE)
        self.assertTrue(style & winvideo.WS_CAPTION)
        self.assertTrue(style & winvideo.WS_THICKFRAME)

        # Nutzer verschiebt das Fenster -> Position wird gemeldet
        winvideo.SetWindowPos(hwnd, None, work.left + 10, work.top + 10, r.width, r.height,
                              winvideo.SWP_NOZORDER)
        time.sleep(0.3)
        mgr.poll(proc.pid, "Lu AirPlay – Test", 70, False, [], False)
        self.assertTrue(saved, "Verschieben wurde nicht erkannt")
        moved = winvideo.Rect(*saved[-1])
        self.assertEqual((moved.left, moved.top), (work.left + 10, work.top + 10))

        # neues Fenster (nächste Sitzung) öffnet an der gemerkten Stelle
        proc.kill()
        proc.wait(5)
        mgr.poll(proc.pid, "x", 70, False, list(moved), False)
        proc2, hwnd2 = self.start_child()
        mgr.poll(proc2.pid, "Lu AirPlay – Test", 70, False, list(moved), False)
        time.sleep(0.5)
        r2 = self.rect(hwnd2)
        self.assertAlmostEqual((r2.left + r2.right) / 2, (moved.left + moved.right) / 2, delta=3)
        self.assertAlmostEqual((r2.top + r2.bottom) / 2, (moved.top + moved.bottom) / 2, delta=3)

    def test_fullscreen_wish_is_left_alone(self):
        mgr = winvideo.VideoWindowManager()
        proc, hwnd = self.start_child()
        before = self.rect(hwnd)
        mgr.poll(proc.pid, "Lu AirPlay – Test", 70, False, [], True)
        time.sleep(0.3)
        self.assertEqual(self.rect(hwnd), before)


if __name__ == "__main__":
    unittest.main()
