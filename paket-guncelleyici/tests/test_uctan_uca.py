"""Uçtan uca: gerçek pencere, gerçek apt kurulumu, gerçek dpkg kilidi.

Yönetici yetkisi ister: yalnızca PAKET_GUNCELLEYICI_YETKI="sudo -n" iken (CI) ve ekran varken çalışır.
Sistemde "deneme-uygulama" adlı bir paket kurulur ve sonunda kaldırılır.
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from yardimci import build_deb, make_key, shared_app

ENABLED = os.environ.get("PAKET_GUNCELLEYICI_YETKI") == "sudo -n" and bool(os.environ.get("DISPLAY"))

if ENABLED:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib

    from guncelleyici import imza, paket
    from guncelleyici.ui import Window


def wait(cond, secs=120):
    """Ana döngüyü koşul sağlanana kadar çalıştırır (uygulamadaki gibi; kendi döngümüz önceliği bozmasın)."""
    end = time.monotonic() + secs
    loop = GLib.MainLoop()

    def check():
        if cond() or time.monotonic() > end:
            loop.quit()
            return False
        return True
    if not cond():
        GLib.timeout_add(50, check)
        loop.run()
    if not cond():
        raise AssertionError("süre doldu")


@unittest.skipUnless(ENABLED, "yalnızca CI'da (sudo -n ve ekran gerekir)")
class EndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        os.chmod(cls.d, 0o755)
        os.environ["XDG_CONFIG_HOME"] = str(cls.d / "ayar")
        cls.secret, cls.public, cls.fpr = make_key(cls.d, "yayinci")
        cls.other_secret, cls.other_public, _ = make_key(cls.d, "baskasi")
        v1 = build_deb(cls.d, version="1.0", key=cls.public, secret=cls.secret)
        subprocess.run(["sudo", "-n", "dpkg", "-r", "deneme-uygulama"], capture_output=True)  # önceki çalışmadan kalan
        subprocess.run(["sudo", "-n", "apt-get", "install", "-y", "-q", str(v1)], check=True, capture_output=True)
        cls.app = shared_app()

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["sudo", "-n", "dpkg", "-r", "deneme-uygulama"], capture_output=True)

    def open(self, deb):
        win = Window(self.app)
        win.present()
        win.load(str(deb))
        wait(lambda: win.stack.get_visible_child_name() in ("ozet", "sonuc"))
        return win

    def install(self, win, secs=120):
        self.assertTrue(win.primary.get_sensitive(), win.blocker.get_label())
        win.primary.emit("clicked")
        wait(lambda: win.stack.get_visible_child_name() == "sonuc", secs)
        return win.result_page.get_title()

    def test_1_update_same_publisher(self):
        win = self.open(build_deb(self.d, version="2.0", key=self.public, secret=self.secret))
        self.assertEqual((win.pkg.installed, win.pkg.verdict), ("1.0", paket.GUNCELLE))
        self.assertEqual((win.sig.state, win.sig.anchor, win.sig.fingerprint), (imza.AYNI, "kurulu", self.fpr))
        self.assertIn("2.0 sürümüne güncelle", win.primary.get_label())
        self.assertIn("kuruldu", self.install(win))
        self.assertEqual(paket.installed_version("deneme-uygulama"), "2.0")
        win.destroy()

    def test_2_different_publisher_needs_consent(self):
        win = self.open(build_deb(self.d, version="9.9", key=self.other_public, secret=self.other_secret))
        self.assertEqual(win.sig.state, imza.FARKLI)
        self.assertFalse(win.primary.get_sensitive())
        win.checks[0].set_active(True)
        self.assertTrue(win.primary.get_sensitive())
        win.destroy()
        self.assertEqual(paket.installed_version("deneme-uygulama"), "2.0")

    def test_3_waits_for_dpkg_lock(self):
        win = self.open(build_deb(self.d, version="2.1", key=self.public, secret=self.secret))
        # apt'nin kullandığı fcntl kilidini root olarak birkaç saniye tut (otomatik güncelleme gibi).
        holder = subprocess.Popen(["sudo", "-n", "python3", "-c",
                                   "import fcntl,time;f=open('/var/lib/dpkg/lock-frontend','w');"
                                   "fcntl.lockf(f,fcntl.LOCK_EX);print('tutuldu',flush=True);time.sleep(10)"],
                                  stdout=subprocess.PIPE, text=True)
        self.assertEqual(holder.stdout.readline().strip(), "tutuldu")
        win.primary.emit("clicked")
        wait(lambda: "Sırada" in win.progress_text.get_label(), 60)
        self.assertEqual(win.stack.get_visible_child_name(), "kuruluyor")
        wait(lambda: win.stack.get_visible_child_name() == "sonuc", 120)
        holder.wait()
        self.assertIn("kuruldu", win.result_page.get_title())
        self.assertEqual(paket.installed_version("deneme-uygulama"), "2.1")
        win.destroy()

    def test_4_downgrade_needs_consent(self):
        win = self.open(build_deb(self.d, version="1.5", key=self.public, secret=self.secret))
        self.assertEqual(win.pkg.verdict, paket.ESKI)
        self.assertFalse(win.primary.get_sensitive())
        for c in win.checks:
            c.set_active(True)
        self.assertIn("kuruldu", self.install(win))
        self.assertEqual(paket.installed_version("deneme-uygulama"), "1.5")
        win.destroy()


if __name__ == "__main__":
    unittest.main()
