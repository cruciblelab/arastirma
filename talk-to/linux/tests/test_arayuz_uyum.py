"""Arayüz uyumluluk katmanı (ui/compat.py): yeni ve eski libadwaita'da aynı davranış.

Ekran gerektirir; ekran yoksa atlanır:
    xvfb-run -a python3 -m unittest tests.test_arayuz_uyum -v
Ubuntu 22.04 kütüphaneleriyle denemek için LD_LIBRARY_PATH ve GI_TYPELIB_PATH
GTK 4.6 / libadwaita 1.1'i gösterecek şekilde ayarlanır (bkz. README).
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, GLib, Gtk
    HAVE = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check()
except (ImportError, ValueError):
    HAVE = False


@unittest.skipUnless(HAVE, "GTK4/libadwaita ya da ekran yok")
class CompatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Adw.init()
        from talkto.ui import compat
        cls.c = compat
        print(f"\nGTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}, "
              f"libadwaita {compat.ADW[0]}.{compat.ADW[1]}", file=sys.stderr)

    def test_switch_row(self):
        r = self.c.SwitchRow("Başlık", "alt", active=True)
        seen = []
        r.connect("notify::active", lambda w, _: seen.append(w.get_active()))
        self.assertTrue(r.get_active())
        r.set_active(False)
        self.assertEqual(seen, [False])
        self.assertFalse(r.get_active())

    def test_entry_row_apply(self):
        for factory in (self.c.EntryRow, self.c.PasswordEntryRow):
            r = factory("Ad", text="eski", show_apply_button=True)
            got = []
            r.connect("apply", lambda w: got.append(w.get_text()))
            r.set_text("yeni")
            r.emit("apply")
            self.assertEqual(got, ["yeni"])

    def test_row_escapes_markup(self):
        r = self.c.row("A & B <i>", "x < y")
        self.assertIn("A", r.get_title())  # çökmeden oluşturuldu; işaretleme olarak yorumlanmadı

    def test_dialog_response(self):
        win = Gtk.Window()
        d = self.c.Dialog(win, "Başlık", "Gövde", Gtk.Label(label="ek"))
        d.add_response("reject", "Reddet")
        d.add_response("accept", "Bağlan")
        d.set_appearance("accept", self.c.SUGGESTED)
        d.set_close_response("reject")
        got = []
        d.on_response(got.append)
        d.present()
        if d.kind == "own":
            d.d._respond("accept")
        else:
            d.d.emit("response", "accept")
        self.assertEqual(got, ["accept"])

    def test_fallback_dialog_close_counts_as_reject(self):
        if self.c.ADW >= (1, 2):
            self.skipTest("bu libadwaita'da kendi diyaloğu var")
        win = Gtk.Window()
        d = self.c.Dialog(win, "Başlık", "")
        d.add_response("reject", "Reddet")
        d.add_response("accept", "Bağlan")
        d.set_close_response("reject")
        got = []
        d.on_response(got.append)
        d.present()
        d.d.close()
        ctx = GLib.MainContext.default()
        while ctx.pending():
            ctx.iteration(False)
        self.assertEqual(got, ["reject"])

    def test_window_builds(self):
        """Bütün sayfalarıyla ana pencere bu sürümde kurulabiliyor mu."""
        import tempfile
        tmp = tempfile.mkdtemp()
        os.environ["TALKTO_CONFIG_DIR"] = tmp + "/cfg"
        os.environ["TALKTO_CACHE_DIR"] = tmp + "/cache"
        from talkto.config import Config
        from talkto.ui.window import Window

        class FakeApp(Adw.Application):
            pass
        app = FakeApp(application_id="lab.crucible.TalkToAndroidTest")
        app.config = Config()
        app.installing_adb = False
        app.call = lambda *a: None
        w = Window(app)
        w.update_usb({"adb": True, "running": True, "apk": "/x.apk",
                      "devices": [{"serial": "S", "state": "device", "tunnel": True, "model": "Pixel",
                                   "app": False}]})
        self.assertIsNotNone(w.stack.get_child_by_name("komutlar"))


if __name__ == "__main__":
    unittest.main()
