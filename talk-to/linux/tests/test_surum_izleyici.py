"""Güncellenince yeniden başlama (talkto.surum_izleyici) ve gerçek süreçle uçtan uca deneme.

Uçtan uca test: uygulama arka planda başlatılır, sürüm dosyası "güncellenir" (apt'nin yaptığı gibi
yeni dosya yazılıp eskisinin üstüne taşınır); aynı süreç (aynı PID) yeni sürümle yeniden başlamalı.
Ekran ister; ekran yoksa atlanır (CI'da TALKTO_TEST_STRICT=1 iken atlanmaz).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from talkto import surum_izleyici  # noqa: E402


class SurumTest(unittest.TestCase):
    def test_version_in(self):
        d = Path(tempfile.mkdtemp())
        f = d / "__init__.py"
        f.write_text('"""x"""\nAPP_ID = "a"\n__version__ = "0.8.1"\n')
        self.assertEqual(surum_izleyici.version_in(f), "0.8.1")
        f.write_text("")  # dpkg yazarken yarım dosya
        self.assertIsNone(surum_izleyici.version_in(f))
        self.assertIsNone(surum_izleyici.version_in(d / "yok.py"))

    def test_restart_argv(self):
        self.assertEqual(surum_izleyici.restart_argv(["/x/__main__.py"], True), [])
        self.assertEqual(surum_izleyici.restart_argv(["/x/__main__.py"], False), ["--arka-planda"])
        self.assertEqual(surum_izleyici.restart_argv(["x", "--arka-planda"], True), [])
        self.assertEqual(surum_izleyici.restart_argv(["x", "--arka-planda"], False), ["--arka-planda"])


try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk  # noqa: F401
    HAVE = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
except (ImportError, ValueError):
    HAVE = False

if not HAVE and os.environ.get("TALKTO_TEST_STRICT"):
    raise RuntimeError("yeniden başlama testi çalıştırılamıyor: GTK4/libadwaita ya da ekran yok")


@unittest.skipUnless(HAVE, "GTK4/libadwaita ya da ekran yok")
class YenidenBaslamaTest(unittest.TestCase):
    def test_same_process_restarts_with_new_version(self):
        tmp = Path(tempfile.mkdtemp())
        lib = tmp / "lib"
        shutil.copytree(ROOT / "talkto", lib / "talkto", ignore=shutil.ignore_patterns("__pycache__"))
        cfg = tmp / "cfg"
        cfg.mkdir()
        (cfg / "ayarlar.json").write_text('{"setup_done": true, "wireless": false, "usb": false, "bluetooth": false,'
                                          ' "run_in_background": true, "port": 47693}')
        env = dict(os.environ, PYTHONPATH=str(lib), TALKTO_CONFIG_DIR=str(cfg), TALKTO_CACHE_DIR=str(tmp / "cache"),
                   XDG_RUNTIME_DIR=str(tmp / "run"), DBUS_SESSION_BUS_ADDRESS=os.environ.get(
                       "DBUS_SESSION_BUS_ADDRESS", ""))
        (tmp / "run").mkdir(mode=0o700)
        log = tmp / "cache" / "gunluk.txt"
        p = subprocess.Popen([sys.executable, "-m", "talkto", "--arka-planda"], env=env, cwd=tmp,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            def wait(cond, secs):
                end = time.monotonic() + secs
                while time.monotonic() < end:
                    if cond():
                        return True
                    time.sleep(0.3)
                return False

            def logged(text):
                return log.exists() and text in log.read_text(errors="replace")

            old_version = surum_izleyici.version_in(lib / "talkto" / "__init__.py")
            self.assertTrue(wait(lambda: logged(f"Talk To Android {old_version} başladı (süreç {p.pid})"), 20),
                            "uygulama başlamadı")
            time.sleep(1)
            self.assertIsNone(p.poll(), "uygulama başlarken kapandı")
            init = lib / "talkto" / "__init__.py"
            new = init.read_text().replace(f'__version__ = "{old_version}"', '__version__ = "99.0.0"')
            tmpf = init.with_name("__init__.py.dpkg-new")
            tmpf.write_text(new)
            os.replace(tmpf, init)  # dpkg gibi: yeni dosya yazılıp eskisinin üstüne taşınır
            self.assertTrue(wait(lambda: logged("99.0.0 kuruldu"), 20), "güncelleme fark edilmedi")
            # exec: aynı süreç numarası, yeni sürüm; arka planda başladığı için yine --arka-planda.
            self.assertTrue(wait(lambda: logged(f"Talk To Android 99.0.0 başladı (süreç {p.pid})"), 20),
                            "yeni sürümle başlamadı")
            time.sleep(1)
            self.assertIsNone(p.poll(), "yeniden başlarken kapandı")
            self.assertIn(b"--arka-planda", Path(f"/proc/{p.pid}/cmdline").read_bytes().split(b"\0"))
        finally:
            p.terminate()
            try:
                p.wait(10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    unittest.main()
