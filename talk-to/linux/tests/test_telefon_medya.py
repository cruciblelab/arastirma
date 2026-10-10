"""Telefonun müziği masaüstünde MPRIS oynatıcısı olarak görünüyor ve oradan kontrol ediliyor mu.

Oturum D-Bus'ı gerekir; yoksa atlanır:
    dbus-run-session -- python3 -m unittest tests.test_telefon_medya -v
"""

import os
import shutil
import subprocess
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from gi.repository import GLib
    from talkto.ui.phone_mpris import PhonePlayers, bus_name
    HAVE = bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS")) and shutil.which("gdbus") is not None
except (ImportError, ValueError):
    HAVE = False

STATE = {"active": True, "player": "Spotify", "title": "Şarkı", "artist": "Sanatçı", "album": "Albüm",
         "playing": True, "position_ms": 5000, "duration_ms": 200000, "volume": 50, "can_seek": True,
         "art_id": None}


@unittest.skipUnless(HAVE, "oturum D-Bus'ı yok")
class PhoneMprisTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.players = PhonePlayers(lambda *a: self.calls.append(a))
        self.players.update("tel1", "Pixel 8", dict(STATE))
        self.name = bus_name("tel1")

    def tearDown(self):
        self.players.keep_only([])

    def gdbus(self, *args) -> str:
        """gdbus'ı ayrı süreçte çalıştırırken bu süreçteki D-Bus nesnelerinin yanıt verebilmesi için döngüyü döndür."""
        out = {}

        def run():
            out["r"] = subprocess.run(["gdbus", "call", "--session", "--dest", self.name,
                                       "--object-path", "/org/mpris/MediaPlayer2", *args],
                                      capture_output=True, text=True, timeout=10)
        t = threading.Thread(target=run)
        t.start()
        ctx = GLib.MainContext.default()
        while t.is_alive():
            ctx.iteration(False)
            t.join(0.01)
        self.assertEqual(out["r"].returncode, 0, out["r"].stderr)
        return out["r"].stdout

    def prop(self, iface, name) -> str:
        return self.gdbus("--method", "org.freedesktop.DBus.Properties.Get", iface, name)

    def test_metadata_and_status(self):
        md = self.prop("org.mpris.MediaPlayer2.Player", "Metadata")
        self.assertIn("Şarkı", md)
        self.assertIn("Sanatçı", md)
        self.assertIn("int64 200000000", md)
        self.assertIn("Playing", self.prop("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))
        self.assertIn("Spotify (Pixel 8)", self.prop("org.mpris.MediaPlayer2", "Identity"))

    def test_controls_go_to_phone(self):
        self.gdbus("--method", "org.mpris.MediaPlayer2.Player.Next")
        self.gdbus("--method", "org.mpris.MediaPlayer2.Player.PlayPause")
        self.gdbus("--method", "org.mpris.MediaPlayer2.Player.SetPosition",
                   "/lab/crucible/TalkToAndroid/track/1", "60000000")
        self.assertEqual(self.calls, [("tel1", "next", None), ("tel1", "play_pause", None), ("tel1", "seek", 60000)])

    def test_not_listed_as_pc_media_and_removed_when_inactive(self):
        from talkto.media import Mpris
        self.assertNotIn(self.name, Mpris().players())  # telefonun şarkısı telefona geri yansımasın
        self.players.update("tel1", "Pixel 8", {"active": False})
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)
        r = subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path",
                            "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.NameHasOwner", self.name],
                           capture_output=True, text=True, timeout=10)
        self.assertIn("false", r.stdout)


if __name__ == "__main__":
    unittest.main()
