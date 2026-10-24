import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luairplay.winvideo import Rect, fit_size, fits_inside, pick_work_area, plan_window, rect_from_list  # noqa: E402

WORK = Rect(0, 0, 1920, 1040)          # 1080p-Monitor minus Taskleiste
FRAME = (8, 31, 8, 8)                  # typischer Windows-10/11-Rahmen


def inside(r: Rect, work: Rect) -> bool:
    return work.left <= r.left and work.top <= r.top and r.right <= work.right and r.bottom <= work.bottom


class FitTest(unittest.TestCase):
    def test_keeps_aspect(self):
        self.assertEqual(fit_size(1920, 1080, 960, 960), (960, 540))
        self.assertEqual(fit_size(886, 1920, 1000, 960), (443, 960))

    def test_degenerate_content(self):
        self.assertEqual(fit_size(0, 0, 1600, 900), (1600, 900))


class PlanTest(unittest.TestCase):
    def test_fullscreen_sized_video_becomes_window(self):
        """Der eigentliche Bug: 1920x1080-Video auf 1080p-Monitor."""
        r = plan_window(1920, 1080, WORK, FRAME, scale_percent=70)
        self.assertTrue(inside(r, WORK))
        self.assertGreaterEqual(r.top, WORK.top)               # Titelleiste sichtbar
        client_w, client_h = r.width - 16, r.height - 39
        self.assertAlmostEqual(client_w / client_h, 16 / 9, delta=0.01)
        self.assertLess(r.width, WORK.width)
        # zentriert
        self.assertAlmostEqual((r.left + r.right) / 2, 960, delta=1)

    def test_portrait_iphone_fits_height(self):
        r = plan_window(886, 1920, WORK, FRAME, scale_percent=90)
        self.assertTrue(inside(r, WORK))
        self.assertLessEqual(r.height, int((1040 - 39) * 0.9) + 39)
        self.assertLess(r.width, r.height)

    def test_restores_saved_box_with_new_aspect(self):
        saved = Rect(100, 100, 900, 600)                       # vom Nutzer gewählt (Querformat)
        r = plan_window(886, 1920, WORK, FRAME, saved=saved)   # jetzt Hochformat
        self.assertTrue(inside(r, WORK))
        self.assertLessEqual(r.height, saved.height)
        self.assertAlmostEqual((r.left + r.right) / 2, 500, delta=1)
        self.assertAlmostEqual((r.top + r.bottom) / 2, 350, delta=1)

    def test_saved_partly_offscreen_is_pulled_in(self):
        saved = Rect(1700, 900, 2500, 1400)
        r = plan_window(1920, 1080, WORK, FRAME, saved=saved)
        self.assertTrue(inside(r, WORK))

    def test_second_monitor_with_negative_coordinates(self):
        left_monitor = Rect(-1280, 0, 0, 984)
        r = plan_window(1920, 1080, left_monitor, FRAME, scale_percent=70)
        self.assertTrue(inside(r, left_monitor))

    def test_tiny_work_area_never_negative(self):
        r = plan_window(1920, 1080, Rect(0, 0, 300, 200), FRAME)
        self.assertGreater(r.width, 0)
        self.assertGreater(r.height, 0)
        self.assertGreaterEqual(r.left, 0)
        self.assertGreaterEqual(r.top, 0)


class SavedTest(unittest.TestCase):
    def test_pick_monitor(self):
        areas = [Rect(0, 0, 1920, 1040), Rect(1920, 0, 3840, 1040)]
        saved = Rect(2000, 100, 2800, 600)
        self.assertEqual(pick_work_area(saved, areas, areas[0]), (saved, areas[1]))

    def test_saved_on_unplugged_monitor_is_dropped(self):
        areas = [Rect(0, 0, 1920, 1040)]
        self.assertEqual(pick_work_area(Rect(4000, 0, 4800, 500), areas, areas[0]), (None, areas[0]))

    def test_fits_inside(self):
        self.assertTrue(fits_inside(Rect(10, 10, 800, 600), WORK))
        self.assertFalse(fits_inside(Rect(0, 0, 1936, 1119), WORK))   # GStreamers 0,0-Fenster
        self.assertFalse(fits_inside(Rect(-10, 0, 800, 600), WORK))

    def test_rect_from_list(self):
        self.assertEqual(rect_from_list([1, 2, 300, 400]), Rect(1, 2, 300, 400))
        for bad in ([], [1, 2, 3], [0, 0, 0, 0], "x", None, [1, 2, 3, "4"]):
            self.assertIsNone(rect_from_list(bad))


if __name__ == "__main__":
    unittest.main()
