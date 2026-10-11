"""Sağ tık listesi: sistem önbelleği (mimeinfo.cache) olmasa da uygulama .deb için listede çıkmalı.

Ayrı bir süreçte, geçici XDG klasörleriyle (gerçek kullanıcı ayarlarına dokunmadan): masaüstü dosyası var,
önbellek yok → listede değil; ensure_listed sonrası listede; varsayılan yapma ancak istenince.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECK = r'''
import sys
sys.path.insert(0, sys.argv[1])
from guncelleyici import iliski
assert iliski.app_info() is not None, "masaüstü dosyası bulunamadı"
before = iliski.listed()
changed = iliski.ensure_listed()
print(before, changed, iliski.listed(), iliski.listed("application/x-deb"), iliski.is_default(),
      iliski.ensure_listed())
print(iliski.make_default(), iliski.is_default())
'''


class AssociationTest(unittest.TestCase):
    def test_listed_without_system_cache(self):
        d = Path(tempfile.mkdtemp())
        apps = d / "share/applications"
        apps.mkdir(parents=True)
        shutil.copy(ROOT / "data/lab.crucible.PaketGuncelleyici.desktop", apps)
        # Ubuntu'daki gibi önbellekte yalnızca başka bir kurucu kayıtlı (App Center): bizimki önbellekte yok.
        (apps / "baska-kurucu.desktop").write_text("[Desktop Entry]\nType=Application\nName=Başka\n"
                                                  "Exec=paket-guncelleyici %F\n"
                                                  "MimeType=application/vnd.debian.binary-package;\n")
        (apps / "mimeinfo.cache").write_text("[MIME Cache]\n"
                                             "application/vnd.debian.binary-package=baska-kurucu.desktop;\n")
        env = dict(os.environ, XDG_DATA_DIRS=str(d / "share"), XDG_DATA_HOME=str(d / "home-data"),
                   XDG_CONFIG_HOME=str(d / "config"), PATH=f"{d}:{os.environ['PATH']}")
        # Exec'teki komut bulunamazsa GLib uygulamayı yok sayar: sahte bir paket-guncelleyici.
        (d / "paket-guncelleyici").write_text("#!/bin/sh\n")
        (d / "paket-guncelleyici").chmod(0o755)
        res = subprocess.run([sys.executable, "-c", CHECK, str(ROOT)], env=env, capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        first, second = res.stdout.splitlines()
        self.assertEqual(first, "False True True True False False")  # eklenir; varsayılan değişmez; ikinci kez gerekmez
        self.assertEqual(second, "True True")
        mimeapps = (d / "config/mimeapps.list").read_text()
        self.assertIn("application/vnd.debian.binary-package=lab.crucible.PaketGuncelleyici.desktop", mimeapps)


if __name__ == "__main__":
    unittest.main()
