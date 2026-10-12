"""Sıfırdan başlama: ayarlar dışarıdan silinince (Paket Güncelleyici'de "verileri temizle") bellekteki eski ayarlar
geri yazılmaz ve uygulama sıfırdan başlar; arka planda başlayan uygulamada kurulum yardımcısı ilk görünüşte açılır.

Pencere testi ekran ister; ekran yoksa atlanır (CI'da TALKTO_TEST_STRICT=1 iken atlanmaz).
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto.config import Config  # noqa: E402


class WipedConfigTest(unittest.TestCase):
    def test_not_rewritten_after_external_wipe(self):
        d = Path(tempfile.mkdtemp()) / "cfg"
        cfg = Config(d)
        cfg.set("setup_done", True)
        self.assertTrue((d / "ayarlar.json").exists())
        self.assertFalse(cfg.wiped())
        shutil.move(str(d), str(d.parent / "cop"))  # çöp kutusuna taşınmış gibi
        self.assertTrue(cfg.wiped())
        cfg.set("wireless", False)  # çalışan uygulama bir ayar yazar
        self.assertFalse(d.exists(), "temizlenen ayarlar geri yazıldı")
        self.assertFalse(Config(d)["setup_done"])  # yeni süreç sıfırdan başlar

    def test_first_run_creates_file(self):
        d = Path(tempfile.mkdtemp()) / "yeni"
        cfg = Config(d)
        self.assertTrue((d / "ayarlar.json").exists())
        self.assertFalse(cfg.wiped())


class DefaultAutostartTest(unittest.TestCase):
    """Bilgisayar yeniden başlayınca telefon kendiliğinden bağlansın: "oturum açılınca başlat" bir kez açılır,
    kullanıcı kapatırsa yeniden açılmaz."""

    def test_once(self):
        try:
            from talkto.ui import system
            from talkto.ui.app import App
        except (ImportError, ValueError) as e:
            self.skipTest(f"GTK yok: {e}")
        tmp = Path(tempfile.mkdtemp())
        old = dict(os.environ)
        try:
            os.environ["XDG_CONFIG_HOME"] = str(tmp / "xdg")
            os.environ.pop("TALKTO_CONFIG_DIR", None)

            class Host:
                _default_autostart = App._default_autostart
            h = Host()
            h.config = Config(tmp / "cfg")
            h._default_autostart()
            self.assertTrue(system.autostart_enabled())
            self.assertIn("--arka-planda", (tmp / "xdg/autostart").joinpath(
                next(p.name for p in (tmp / "xdg/autostart").iterdir())).read_text())
            system.set_autostart(False)  # kullanıcı kapattı
            h._default_autostart()
            self.assertFalse(system.autostart_enabled())
            os.environ["TALKTO_CONFIG_DIR"] = str(tmp / "test")  # testler gerçek oturuma dokunmaz
            h2 = Host()
            h2.config = Config(tmp / "cfg2")
            h2._default_autostart()
            self.assertFalse(system.autostart_enabled())
        finally:
            os.environ.clear()
            os.environ.update(old)


try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib, Gtk
    HAVE = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check()
except (ImportError, ValueError):
    HAVE = False

if not HAVE and os.environ.get("TALKTO_TEST_STRICT"):
    raise RuntimeError("arayüz testleri çalıştırılamıyor: GTK4/libadwaita ya da ekran yok")


@unittest.skipUnless(HAVE, "GTK4/libadwaita ya da ekran yok")
class HiddenStartTest(unittest.TestCase):
    def test_setup_opens_on_first_show_and_wipe_restarts(self):
        tmp = tempfile.mkdtemp()
        os.environ["TALKTO_CONFIG_DIR"] = tmp + "/cfg"
        os.environ["TALKTO_CACHE_DIR"] = tmp + "/cache"
        from talkto.hub import Hub
        from talkto.ui.app import App

        def factory(config, emit):
            for k, v in (("port", 47693), ("wireless", False), ("usb", False), ("bluetooth", False),
                         ("run_in_background", True)):
                config.set(k, v)
            return Hub(config, emit, enable_media=False, enable_discovery=False)

        app = App(start_hidden=True, hub_factory=factory)  # oturum açılışı / güncelleme sonrası gibi
        restarts = []
        app._restart = lambda args, before=None: restarts.append(args)
        seen = {}
        steps = []

        def step():
            i = len(steps)
            steps.append(i)
            try:
                if i == 0:
                    seen["hidden"] = (app.window is not None and not app.window.get_visible(), app.setup_window)
                    app.activate()  # kullanıcı simgeye tıkladı
                elif i == 1:
                    seen["setup_after_show"] = app.setup_window is not None
                    app.setup_window.close()
                elif i == 2:
                    app.activate()
                elif i == 3:
                    seen["not_again"] = app.setup_window is None  # kapatılan yardımcı her açılışta dayatılmaz
                    shutil.move(tmp + "/cfg", tmp + "/cop")
                    app.config.set("mini_size", "buyuk")
                    seen["not_rewritten"] = not os.path.exists(tmp + "/cfg/ayarlar.json")
                elif i < 8 and not restarts:
                    pass  # denetim 2 sn'de bir
                else:
                    seen["restarts"] = list(restarts)
                    seen["env"] = os.environ.get("TALKTO_SIFIRLANDI")
                    app._quit()
                    return False
            except Exception as e:  # noqa: BLE001
                seen["error"] = repr(e)
                app._quit()
                return False
            return True

        GLib.timeout_add(700, step)
        app.run([])
        os.environ.pop("TALKTO_SIFIRLANDI", None)
        self.assertNotIn("error", seen)
        self.assertEqual(seen["hidden"], (True, None))
        self.assertTrue(seen["setup_after_show"])
        self.assertTrue(seen["not_again"])
        self.assertTrue(seen["not_rewritten"])
        self.assertEqual(seen["restarts"], [[]])  # sıfırdan, pencere görünür başlar
        self.assertEqual(seen["env"], "dis")


if __name__ == "__main__":
    unittest.main()
