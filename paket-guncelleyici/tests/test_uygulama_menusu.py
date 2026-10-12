"""Kurulu uygulamalar → ⋮ menüsü (Android'deki uygulama bilgisi gibi): Aç, Durmaya zorla, Verileri temizle, Kaldır.
Gerçek pencerede; "Durmaya zorla" gerçek bir süreci durdurur."""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _display():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check()
    except (ImportError, ValueError):
        return False


@unittest.skipUnless(_display(), "ekran yok")
class AppMenuTest(unittest.TestCase):
    def setUp(self):
        from yardimci import shared_app
        from guncelleyici import apt
        from guncelleyici.ui import Window
        self.app = shared_app()
        self.win = Window(self.app)
        self.win.present()
        self.a = apt.Uygulama("deneme-uygulama", "1.0", "Deneme", None, "yok.desktop", True)
        self.win._fill_apps([self.a])

    def tearDown(self):
        self.win.destroy()

    def items(self, model):
        out = []
        for i in range(model.get_n_items()):
            label = model.get_item_attribute_value(i, "label", None).unpack()
            action = model.get_item_attribute_value(i, "action", None).unpack()
            out.append((label, action))
        return out

    def row(self):
        child = self.win.app_list.get_first_child()
        while child and not getattr(child, "menu_button", None):
            child = child.get_next_sibling()
        return child

    def test_menu_items_follow_running_state(self):
        self.assertIsNotNone(self.row().menu_button)  # her uygulamanın yanında ⋮
        with mock.patch("guncelleyici.surec.find", return_value=[]):
            items = self.items(self.win._app_menu(self.a))
        # Masaüstü dosyası yok: "Aç" çıkmaz; çalışmıyor: "Durmaya zorla" soluk (eylemi olmayan).
        self.assertEqual(items, [("Durmaya zorla", "win.uyg-yok"), ("Verileri temizle…", "win.uyg-veri"),
                                 ("Kaldır…", "win.uyg-kaldir")])
        self.assertIsNone(self.win.lookup_action("uyg-yok"))
        with mock.patch("guncelleyici.surec.find", return_value=[1234]):
            items = self.items(self.win._app_menu(self.a))
        self.assertEqual(items[0], ("Durmaya zorla", "win.uyg-durdur"))
        self.assertIsNotNone(self.win.lookup_action("uyg-durdur"))

    def test_menu_actions_open_pages(self):
        self.win._app_menu(self.a)
        with mock.patch.object(self.win, "show_data") as data, mock.patch.object(self.win, "prepare_remove") as rm:
            self.win.activate_action("win.uyg-veri", None)
            self.win.activate_action("win.uyg-kaldir", None)
        data.assert_called_once_with(self.a)
        rm.assert_called_once_with(self.a)

    def test_force_stop_asks_then_stops(self):
        from gi.repository import GLib
        p = subprocess.Popen(["sleep", "60"])
        asked = []
        try:
            def confirm(title, body, ok, on_ok):
                asked.append((title, ok))
                on_ok()
            with mock.patch.object(self.win, "confirm", confirm), \
                    mock.patch("guncelleyici.surec.find", return_value=[p.pid]):
                self.win._app_menu(self.a)
                self.win.activate_action("win.uyg-durdur", None)
                loop = GLib.MainLoop()
                GLib.timeout_add(100, lambda: (p.poll() is None) or loop.quit())
                GLib.timeout_add(8000, loop.quit)
                loop.run()
            p.wait(5)
        finally:
            if p.poll() is None:
                p.kill()
        self.assertEqual(asked, [("Deneme durmaya zorlansın mı?", "Durmaya zorla")])  # önce sorar
        self.assertIsNotNone(p.returncode)

    def test_confirm_dialog_builds(self):
        """Onay penceresi hem libadwaita 1.1'de (Ubuntu 22.04) hem yenisinde kurulur."""
        self.win.confirm("Başlık", "Gövde", "Tamam", lambda: None)
        self.assertTrue(self.win._dialog.get_visible())
        self.win._dialog.destroy()


if __name__ == "__main__":
    unittest.main()
