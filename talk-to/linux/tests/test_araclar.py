"""Geliştirici araçları (talkto.araclar): sahte adb ile paket listesi, dosya listesi, güvenlik sınırları."""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import araclar  # noqa: E402

LS = """total 24
drwxrws--- 4 u0_a12 media_rw 3452 2026-10-10 12:01 .
drwx--x--x 4 root   sdcard_rw 4096 2026-01-01 00:00 ..
drwxrws--- 2 u0_a12 media_rw 3452 2026-10-10 12:01 Android
-rw-rw---- 1 u0_a12 media_rw 1048576 2026-10-11 09:30 büyük video.mp4
lrwxrwxrwx 1 root root 21 2026-01-01 00:00 bağ -> /storage/self/primary
"""

ADB = r'''#!/bin/sh
echo "$*" >> "$LOG"
case "$*" in
  *"pm list packages -s -u"*) printf 'package:com.android.chrome\npackage:com.miui.weather\npackage:com.miui.msa\n' ;;
  *"pm list packages -d"*) printf 'package:com.miui.weather\n' ;;
  *"pm list packages -u"*) printf 'package:com.android.chrome\npackage:com.miui.weather\npackage:com.miui.msa\npackage:org.example.app\n' ;;
  *"pm list packages"*) printf 'package:com.android.chrome\npackage:com.miui.weather\npackage:org.example.app\n' ;;
  *"ls -la"*) cat "$LSFILE" ;;
  *"pm clear"*) echo Success ;;
  *"pm uninstall"*) echo "Failure [not installed for 0]" ;;
  *"logcat -d"*) echo "10-12 10:00:00.000 1 1 I test: merhaba" ;;
esac
exit 0
'''


class AraclarTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "adb").write_text(ADB)
        (self.tmp / "adb").chmod(0o755)
        (self.tmp / "ls.txt").write_text(LS)
        self.log = self.tmp / "log"
        self.old = dict(os.environ)
        os.environ.update(PATH=f"{self.tmp}:{os.environ['PATH']}", LOG=str(self.log), LSFILE=str(self.tmp / "ls.txt"))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old)

    def run_(self, coro):
        return asyncio.run(coro)

    def test_packages_include_removed_system_apps(self):
        got = {p.name: (p.system, p.enabled, p.installed) for p in self.run_(araclar.packages("S"))}
        # com.miui.msa: bu kullanıcı için kaldırılmış sistem uygulaması → "Geri yükle" için listede
        self.assertEqual(got, {"org.example.app": (False, True, True), "com.android.chrome": (True, True, True),
                               "com.miui.weather": (True, False, True), "com.miui.msa": (True, True, False)})

    def test_list_dir_parses_toybox_ls(self):
        entries = self.run_(araclar.list_dir("S", "/sdcard"))
        self.assertEqual([(e.name, e.is_dir, e.size, e.link) for e in entries],
                         [("Android", True, 3452, False), ("bağ", False, 21, True),
                          ("büyük video.mp4", False, 1048576, False)])
        self.assertIn("ls -la /sdcard/", self.log.read_text())

    def test_delete_only_in_shared_storage_and_quoted(self):
        ok, msg = self.run_(araclar.delete("S", "/system/app"))
        self.assertFalse(ok)
        self.assertFalse(self.run_(araclar.delete("S", "/sdcard"))[0])  # kökün kendisi değil
        self.assertFalse(self.run_(araclar.delete("S", "/sdcard/../system"))[0])
        ok, _ = self.run_(araclar.delete("S", "/sdcard/Android/data/x y; reboot"))
        self.assertTrue(ok)
        self.assertIn("rm -rf -- '/sdcard/Android/data/x y; reboot'", self.log.read_text())

    def test_app_actions(self):
        self.assertEqual(self.run_(araclar.app_action("S", "com.miui.weather", "clear")), (True, "Success"))
        ok, text = self.run_(araclar.app_action("S", "com.miui.weather", "uninstall"))
        self.assertFalse(ok)  # "Failure" yazdıysa olmadı sayılır
        self.assertEqual(self.run_(araclar.app_action("S", "a; reboot", "clear")), (False, "geçersiz istek"))
        self.assertIn("pm uninstall -k --user 0 com.miui.weather", self.log.read_text())

    def test_logcat_and_reboot(self):
        dest = self.tmp / "kayit.txt"
        self.assertTrue(self.run_(araclar.logcat("S", str(dest)))[0])
        self.assertIn("merhaba", dest.read_text())
        self.assertFalse(self.run_(araclar.reboot("S", "format"))[0])
        self.assertTrue(self.run_(araclar.reboot("S", "recovery"))[0])
        self.assertIn("-s S reboot recovery", self.log.read_text())


if __name__ == "__main__":
    unittest.main()
