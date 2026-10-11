"""apt/dpkg hatalarının açıklamaları: gerçek çıktı örnekleriyle (İngilizce ve Türkçe)."""

import unittest

import yardimci  # noqa: F401  (guncelleyici'yi yola ekler)

from guncelleyici import hatalar


def ex(text, code=100, op="kurulum"):
    return hatalar.explain(text.strip().splitlines(), code, op)


class ExplainTest(unittest.TestCase):
    def test_interrupted(self):
        a = ex("E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a' to correct the problem.")
        self.assertEqual((a.title, a.fix), ("Önceki bir kurulum yarıda kalmış", "yarim"))
        a = ex("E: dpkg kesildi, sorunu düzeltmek için elle 'sudo dpkg --configure -a' komutunu çalıştırmalısınız.")
        self.assertEqual(a.fix, "yarim")
        self.assertEqual(a.fix_label, "Yarım kalan işi tamamla")

    def test_broken_dependencies(self):
        a = ex("""You might want to run 'apt --fix-broken install' to correct these.
The following packages have unmet dependencies:
 libfoo : Depends: libbar (>= 2) but 1.0 is to be installed
E: Unmet dependencies. Try 'apt --fix-broken install' with no packages (or specify a solution).""")
        # Belirli bir paket eksikse onu söyler (onarım bunu çözmez).
        self.assertEqual(a.title, "Gerekli bir paket bulunamadı")
        self.assertIn("libbar", a.text)
        a = ex("E: Unmet dependencies. Try 'apt --fix-broken install' with no packages (or specify a solution).")
        self.assertEqual((a.title, a.fix), ("Paket sisteminde bozuk bağımlılıklar var", "bagimlilik"))

    def test_not_installable_dependency(self):
        a = ex(" talk-to-android : Depends: python3 (>= 3.12) but 3.10.6-1~22.04 is to be installed\n"
               "E: Unable to correct problems, you have held broken packages.")
        self.assertEqual(a.title, "Gerekli bir paket bulunamadı")
        self.assertIn("python3", a.text)

    def test_overwrite(self):
        a = ex("dpkg: error processing archive /tmp/x.deb (--unpack):\n trying to overwrite '/usr/bin/foo', "
               "which is also in package foo-old 1.0\nErrors were encountered while processing:\n /tmp/x.deb")
        self.assertEqual(a.title, "Dosya çakışması")
        self.assertIn("/usr/bin/foo", a.text)
        self.assertIn("foo-old", a.text)

    def test_space_script_network_essential(self):
        self.assertEqual(ex("E: You don't have enough free space in /var/cache/apt/archives/.").title,
                         "Diskte yer kalmadı")
        a = ex("dpkg: error processing package x (--configure):\n installed x package post-installation script "
               "subprocess returned error exit status 1")
        self.assertEqual((a.title, a.fix), ("Paketin kendi betiği hata verdi", "yarim"))
        self.assertEqual(ex("E: Failed to fetch http://archive.ubuntu.com/x.deb  Temporary failure resolving "
                            "'archive.ubuntu.com'").title, "İnternete ulaşılamadı")
        a = ex("WARNING: The following essential packages will be removed.\nE: Essential packages were removed "
               "and -y was used without --allow-remove-essential.\nRemoving essential system-critical packages is "
               "not permitted. This might break the system.", op="kaldırma")
        self.assertEqual(a.title, "Sistemin temel bir paketi")
        self.assertEqual(ex("Package 'x' is not installed, so not removed", op="kaldırma").title,
                         "Zaten kurulu değil")

    def test_password_and_fallback(self):
        self.assertEqual(ex("", 126).title, "Şifre penceresi kapatıldı")
        self.assertEqual(ex("", 127).title, "Yönetici izni verilmedi")
        a = ex("bir şey\nE: Tuhaf bir hata", 100, op="kaldırma")
        self.assertEqual((a.title, a.text), ("Kaldırılmadı", "Tuhaf bir hata (çıkış kodu 100)"))
        self.assertIn("Tuhaf", a.detail)


if __name__ == "__main__":
    unittest.main()
