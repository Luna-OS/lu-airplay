import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luairplay import engine  # noqa: E402
from luairplay.engine import OutputParser, build_args  # noqa: E402
from luairplay.settings import Settings  # noqa: E402


def kinds(events):
    return [e.kind for e in events if e.kind != "log"]


class ParserTest(unittest.TestCase):
    def test_session_lifecycle(self):
        p = OutputParser()
        self.assertEqual(kinds(p.feed("Initialized server socket(s)")), ["ready"])
        self.assertEqual(kinds(p.feed("Accepted IPv4 client on socket 12, port 7000")), [])
        ev = p.feed("connection request from Lucas iPhone (iPhone15,2) with deviceID = AA:BB")
        self.assertEqual(kinds(ev), ["client"])
        self.assertEqual(ev[-1].text, "Lucas iPhone")
        self.assertEqual(ev[-1].detail, "iPhone15,2")
        self.assertEqual(kinds(p.feed("Accepted IPv4 client on socket 13, port 7000")), [])
        self.assertEqual(kinds(p.feed("raop_rtp_mirror starting mirroring")), ["mirroring"])
        self.assertEqual(kinds(p.feed("Removing connection for socket 13")), [])
        ev = p.feed("Removing connection for socket 12")
        self.assertEqual(kinds(ev), ["disconnected"])
        self.assertEqual(ev[-1].text, "Lucas iPhone")

    def test_name_with_parentheses(self):
        ev = OutputParser().feed("connection request from Max (Arbeit) (iPad13,4) with deviceID = X")
        self.assertEqual(ev[-1].text, "Max (Arbeit)")
        self.assertEqual(ev[-1].detail, "iPad13,4")

    def test_pin_and_errors(self):
        p = OutputParser()
        ev = p.feed('*** CLIENT MUST NOW ENTER PIN = "4711" AS AIRPLAY PASSWORD')
        self.assertEqual((kinds(ev), ev[-1].text), (["pin"], "4711"))
        self.assertEqual(kinds(p.feed("*** ERROR: GStreamer gst_parse_launch failed to create video "
                                      "pipeline 1")), ["warning"])
        self.assertEqual(kinds(p.feed("*** ERROR: dnssd_register_raop failed with error code -1")),
                         ["error"])
        self.assertEqual(kinds(p.feed("*** ERROR lost connection with client (network problem?)")),
                         ["lost"])

    def test_every_line_is_logged(self):
        ev = OutputParser().feed("irgendwas")
        self.assertEqual([(e.kind, e.text) for e in ev], [("log", "irgendwas")])


class ArgsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(engine, "config_dir", return_value=Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def args(self, **kw):
        s = Settings(name="Wohnzimmer", pin="1234")
        for k, v in kw.items():
            setattr(s, k, v)
        return build_args(s, Path("/x/uxplay"))

    def test_defaults(self):
        a = self.args()
        self.assertEqual(a[0], "/x/uxplay")
        self.assertIn("-nh", a)
        self.assertEqual(a[a.index("-n") + 1], "Wohnzimmer")
        self.assertEqual(a[a.index("-s") + 1], "1920x1080@60")
        self.assertNotIn("-pin", a)
        self.assertIn("-nohold", a)
        self.assertTrue((Path(self.tmp.name) / "engine.rc").exists())

    def test_options(self):
        a = self.args(resolution="4K", fps=30, pin_enabled=True, fullscreen=True, audio=False,
                      takeover=False, port=7100, rotation="R", extra_args="-vsync no")
        self.assertEqual(a[a.index("-s") + 1], "3840x2160@30")
        self.assertIn("-h265", a)
        self.assertEqual(a[a.index("-pin") + 1], "1234")
        self.assertIn("-reg", a)
        self.assertIn("-fs", a)
        self.assertEqual(a[a.index("-as") + 1], "0")
        self.assertNotIn("-nohold", a)
        self.assertEqual(a[a.index("-p") + 1], "7100")
        self.assertEqual(a[a.index("-r") + 1], "R")
        self.assertEqual(a[-2:], ["-vsync", "no"])

    def test_audio_only(self):
        a = self.args(video=False, fullscreen=True)
        self.assertEqual(a[a.index("-vs") + 1], "0")
        self.assertNotIn("-fs", a)

    def test_empty_name_falls_back(self):
        a = self.args(name="  ")
        self.assertEqual(a[a.index("-n") + 1], "Lu AirPlay")


class SettingsTest(unittest.TestCase):
    def test_roundtrip_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp,
                                                                                 "APPDATA": tmp}):
            s = Settings.load()
            self.assertTrue(s.name)
            self.assertRegex(s.pin, r"^[1-9]\d{3}$")
            s.name, s.fps = "Büro", 30
            s.save()
            s2 = Settings.load()
            self.assertEqual((s2.name, s2.fps, s2.pin), ("Büro", 30, s.pin))


if __name__ == "__main__":
    unittest.main()
