import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luairplay import engine  # noqa: E402
from luairplay.engine import (OutputParser, build_args, effective_rotation,  # noqa: E402
                             local_ipv4_addresses, video_sink_args)
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

    def test_network_announcement(self):
        p = OutputParser()
        ev = p.feed("mDNS: announcing on IPv4 192.168.1.23 (network adapter: WLAN)")
        self.assertEqual([(e.kind, e.text, e.detail) for e in ev if e.kind != "log"],
                         [("network", "192.168.1.23", "WLAN")])
        ev = p.feed("mDNS: announcing on IPv4 10.0.0.5 (default route)")
        self.assertEqual([(e.kind, e.text, e.detail) for e in ev if e.kind != "log"],
                         [("network", "10.0.0.5", "")])
        self.assertEqual(kinds(p.feed("mDNS: announcing on IPv4 0.0.0.0 (no usable network adapter found)")),
                         ["network", "warning"])

    def test_disconnect_after_normal_teardown(self):
        """Nach normalem Beenden meldet die Engine nur 'Connection closed on socket'."""
        p = OutputParser()
        p.feed("Accepted IPv4 client on socket 7, port 7000")
        p.feed("connection request from Lunas iPhone (iPhone16,1) with deviceID = X")
        ev = p.feed("Connection closed on socket 7")
        self.assertEqual([(e.kind, e.text) for e in ev if e.kind != "log"],
                         [("disconnected", "Lunas iPhone")])

    def test_video_geometry_and_end(self):
        p = OutputParser()
        ev = p.feed("*** codec is h264: geometry is (w,h)=(1920,1080) (source); (x,y)=(0,0); "
                    "(w,h)=(886,1920)")
        self.assertEqual([(e.kind, e.text) for e in ev if e.kind != "log"], [("video_size", "886x1920")])
        ev = p.feed("*** codec is h265: geometry is (w,h)=(1280,720) (source); (x,y)=(0,0); (w,h)=(0,0)")
        self.assertEqual([(e.kind, e.text) for e in ev if e.kind != "log"], [("video_size", "1280x720")])
        self.assertEqual(kinds(p.feed("GStreamer: End-Of-Stream (video)")), ["mirror_end"])

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
        self.assertEqual(a[0], str(Path("/x/uxplay")))
        self.assertIn("-nh", a)
        self.assertEqual(a[a.index("-n") + 1], "Wohnzimmer")
        self.assertEqual(a[a.index("-s") + 1], "1920x1080@60")
        self.assertNotIn("-pin", a)
        self.assertIn("-nohold", a)
        self.assertTrue((Path(self.tmp.name) / "engine.rc").exists())

    def test_options(self):
        with mock.patch.object(engine, "IS_WINDOWS", False):
            self._test_options()

    def test_windows_fullscreen_and_user_sink(self):
        with mock.patch.object(engine, "IS_WINDOWS", True):
            a = self.args(fullscreen=True)
            self.assertNotIn("-fs", a)
            self.assertIn("fullscreen=true", a[a.index("-vs") + 1])
            # eigenes -vs in den Zusatzoptionen: keine d3d11-Optionen, die daran kleben bleiben
            a = self.args(fullscreen=True, extra_args="-vs d3d12videosink")
            self.assertEqual(a.count("-vs"), 1)
            self.assertIn("-fs", a)
            self.assertEqual(a[a.index("-vs") + 1], "d3d12videosink")

    def test_effective_rotation(self):
        """Das Videofenster muss wissen, ob die Engine Breite und Höhe tauscht."""
        self.assertEqual(effective_rotation(Settings()), "")
        self.assertEqual(effective_rotation(Settings(rotation="L")), "L")
        self.assertEqual(effective_rotation(Settings(extra_args="-r R")), "R")
        self.assertEqual(effective_rotation(Settings(rotation="L", extra_args="-vsync no -r R")), "R")
        self.assertEqual(effective_rotation(Settings(extra_args="-f I")), "")

    def _test_options(self):
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

    def test_local_ipv4_addresses(self):
        ips = local_ipv4_addresses()
        self.assertIsInstance(ips, list)
        self.assertFalse(any(ip.startswith("127.") for ip in ips))

    def test_fullscreen_keeps_alt_enter_on_windows(self):
        """Mit -fs schaltet UxPlay Alt+Enter bei d3d11/d3d12 ab – deshalb Sink-Optionen."""
        a = video_sink_args("", True, windows=True)
        self.assertEqual(a[0], "-vs")
        self.assertTrue(a[1].startswith("d3d11videosink "))
        self.assertIn("ALT_ENTER", a[1])
        self.assertIn("fullscreen=true", a[1])
        self.assertNotIn("-fs", a)
        a = video_sink_args("d3d12videosink", True, windows=True)
        self.assertIn("fullscreen-on-alt-enter=true", a[1])
        self.assertNotIn("-fs", a)
        self.assertEqual(video_sink_args("glimagesink", True, windows=True), ["-vs", "glimagesink", "-fs"])
        self.assertEqual(video_sink_args("", False, windows=True), ["-vs", "d3d11videosink"])
        self.assertEqual(video_sink_args("", True, windows=False), ["-fs"])
        self.assertEqual(video_sink_args("", False, windows=False), [])

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
