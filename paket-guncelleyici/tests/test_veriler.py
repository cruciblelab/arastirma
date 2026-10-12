"""Uygulamanın ev klasöründeki verileri: doğru klasörler bulunur (tam ad), ortak klasörler önerilmez;
pencerede önbellek işaretli gelir, seçim boyutu düğmede, temizlenen çöpe taşınır."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guncelleyici import veriler  # noqa: E402


def fake_home():
    home = Path(tempfile.mkdtemp())
    apps = home / "apps"
    apps.mkdir()
    (apps / "org.example.FooApp.desktop").write_text(
        "[Desktop Entry]\nName=Foo App\nExec=env GDK_BACKEND=x11 /usr/bin/foo-bin --yeni %U\nType=Application\n"
        "[Desktop Action yeni]\nExec=/usr/bin/baska\n")
    for rel, size in ((".cache/foo-bin", 3000), (".config/Foo App", 10), (".local/share/FooApp", 500),
                      (".config/foo-application", 7), (".config/gtk-3.0", 5), (".local/state/foo", 1)):
        d = home / rel
        d.mkdir(parents=True)
        (d / "x").write_bytes(b"a" * size)
    return home, apps


class VerilerTest(unittest.TestCase):
    def test_exec_name(self):
        home, apps = fake_home()
        self.assertEqual(veriler.exec_name(str(apps / "org.example.FooApp.desktop")), "foo-bin")
        self.assertIsNone(veriler.exec_name(str(apps / "yok.desktop")))

    def test_find_exact_names_only(self):
        home, apps = fake_home()
        found = veriler.find("foo", "org.example.FooApp.desktop", "Foo App", home=home, desktop_dir=str(apps))
        got = {(str(k.path.relative_to(home)), k.kind, k.size) for k in found}
        self.assertEqual(got, {(".cache/foo-bin", "onbellek", 3000), (".config/Foo App", "ayar", 10),
                               (".local/share/FooApp", "veri", 500), (".local/state/foo", "veri", 1)})
        # benzer ad (foo-application) ve ortak klasör (gtk-3.0) yok
        self.assertNotIn("gtk-3.0", veriler.keys("gtk-3.0", "x.desktop", None, "GTK"))

    def test_apt_cache_size(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.deb").write_bytes(b"x" * 100)
        (d / "lock").write_bytes(b"x" * 5)
        self.assertEqual(veriler.apt_cache_size(d), 100)


try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk  # noqa: F401
    HAVE = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
except (ImportError, ValueError):
    HAVE = False


@unittest.skipUnless(HAVE, "GTK4/libadwaita ya da ekran yok")
class VerilerPencereTest(unittest.TestCase):
    def test_cache_checked_by_default_and_trashed(self):
        from yardimci import shared_app
        from guncelleyici import apt
        from guncelleyici.ui import Window
        win = Window(shared_app())
        home, _ = fake_home()
        ks = [veriler.Klasor(home / ".cache/foo-bin", "onbellek", 3000),
              veriler.Klasor(home / ".config/Foo App", "ayar", 2048)]
        a = apt.Uygulama("foo", "1.0", "Foo App", None, "org.example.FooApp.desktop", True)
        win.mode, win.target = "veri", a
        win._fill_data(a, ks, True)
        self.assertEqual(win.primary.get_label(), "Seçilenleri temizle (2,9 KB)")
        win.data_checks[0][0].set_active(False)
        self.assertFalse(win.primary.get_sensitive())
        win.data_checks[1][0].set_active(True)
        trashed = []
        with mock.patch.object(veriler, "trash", lambda ps: (trashed.extend(ps) or (list(ps), []))), \
                mock.patch.object(win, "show_data", lambda a: None):
            win.clean_data()
        self.assertEqual(trashed, [home / ".config/Foo App"])
        win.destroy()


if __name__ == "__main__":
    unittest.main()
