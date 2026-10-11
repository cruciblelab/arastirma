"""Paket bilgisi, sürüm karşılaştırması ve imza durumları (gerçek .deb ve GPG anahtarlarıyla)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from yardimci import build_deb, make_key

from guncelleyici import arsiv, imza, paket

HAVE = all(shutil.which(t) for t in ("gpg", "gpgv", "dpkg-deb", "dpkg"))


class ControlTest(unittest.TestCase):
    def test_multiline(self):
        c = paket.control("Package: a\nDescription: kısa\n uzun\n .\n son\nVersion: 1\n")
        self.assertEqual(c["Description"], "kısa\nuzun\n.\nson")
        self.assertEqual(c["Version"], "1")

    def test_verdict(self):
        archs = {"all", "amd64"}
        self.assertEqual(paket.verdict("1.0", None, "all", archs), paket.KUR)
        self.assertEqual(paket.verdict("0.7.1", "0.7.0", "all", archs), paket.GUNCELLE)
        self.assertEqual(paket.verdict("0.10", "0.9", "all", archs), paket.GUNCELLE)  # sayı, metin değil
        self.assertEqual(paket.verdict("1.0~rc1", "1.0", "all", archs), paket.ESKI)  # Debian kuralı
        self.assertEqual(paket.verdict("1.0", "1.0", "amd64", archs), paket.AYNI)
        self.assertEqual(paket.verdict("1.0", None, "arm64", archs), paket.UYUMSUZ)


@unittest.skipUnless(HAVE, "gpg, gpgv ya da dpkg yok")
class DebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        cls.secret, cls.public, cls.fpr = make_key(cls.d, "yayinci")
        cls.other_secret, cls.other_public, cls.other_fpr = make_key(cls.d, "baskasi")

    def test_read(self):
        p = paket.read(str(build_deb(self.d, version="2.0", key=self.public)))
        self.assertEqual((p.package, p.version, p.arch), ("deneme-uygulama", "2.0", "all"))
        self.assertEqual(p.name, "Deneme Uygulaması")
        self.assertEqual(p.summary, "Deneme paketi")
        self.assertIn("İkinci paragraf.", p.description)
        self.assertEqual(p.icon_ext, ".svg")
        self.assertTrue(p.icon_data.startswith(b"<svg"))
        self.assertEqual(p.keyring, self.public)
        self.assertEqual(p.desktop_ids, ["lab.deneme.deneme-uygulama.desktop"])
        self.assertIsNone(p.installed)
        self.assertEqual(p.verdict, paket.KUR)

    def test_not_a_deb(self):
        f = self.d / "sahte.deb"
        f.write_text("merhaba")
        with self.assertRaises(ValueError):
            paket.read(str(f))
        with self.assertRaises(ValueError):
            arsiv.parcalar(str(f))

    def anchors(self, installed_key=None, pinned=None):
        root, pins = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        if installed_key:
            (root / "usr/share/keyrings").mkdir(parents=True)
            (root / "usr/share/keyrings/deneme-uygulama-paket.gpg").write_bytes(installed_key)
        if pinned:
            imza.remember("deneme-uygulama", pinned, pins)
        return imza.anchors("deneme-uygulama", installed_key is not None, root, pins)

    def check(self, deb, known):
        return imza.check(str(deb), "deneme-uygulama", paket.read(str(deb)).keyring, known)

    def test_same_publisher(self):
        deb = build_deb(self.d, version="3.0", key=self.public, secret=self.secret)
        s = self.check(deb, self.anchors(installed_key=self.public))
        self.assertEqual((s.state, s.fingerprint, s.anchor), (imza.AYNI, self.fpr, "kurulu"))
        self.assertFalse(s.needs_confirmation)
        s = self.check(deb, self.anchors(pinned=self.public))
        self.assertEqual((s.state, s.anchor), (imza.AYNI, "onaylanan"))

    def test_first_time(self):
        deb = build_deb(self.d, version="3.1", key=self.public, secret=self.secret)
        s = self.check(deb, self.anchors())
        self.assertEqual((s.state, s.fingerprint), (imza.ILK, self.fpr))
        self.assertFalse(s.needs_confirmation)

    def test_different_publisher(self):
        # Başkası kendi anahtarını pakete koyup imzalamış: imza kendi içinde geçerli ama yayıncı farklı.
        deb = build_deb(self.d, version="9.9.9", key=self.other_public, secret=self.other_secret)
        s = self.check(deb, self.anchors(installed_key=self.public))
        self.assertEqual((s.state, s.fingerprint), (imza.FARKLI, self.other_fpr))
        self.assertTrue(s.needs_confirmation)

    def test_unsigned(self):
        deb = build_deb(self.d, version="3.2", key=self.public)
        self.assertEqual(self.check(deb, self.anchors()).state, imza.IMZASIZ)
        self.assertFalse(self.check(deb, self.anchors()).needs_confirmation)
        # Önceki sürüm imzalıydı: imzayı kaldırarak denetimden kaçılamaz.
        s = self.check(deb, self.anchors(installed_key=self.public))
        self.assertEqual(s.state, imza.IMZASIZ)
        self.assertTrue(s.needs_confirmation)

    def test_tampered(self):
        deb = build_deb(self.d, version="3.3", key=self.public, secret=self.secret)
        members = arsiv.parcalar(str(deb))
        members = [(n, b + b"\0" if n.startswith("data.tar") else b) for n, b in members]
        bad = self.d / "bozuk.deb"
        bad.write_bytes(self._ar(members))
        s = imza.check(str(bad), "deneme-uygulama", self.public, self.anchors(installed_key=self.public))
        self.assertEqual(s.state, imza.BOZUK)
        self.assertTrue(s.needs_confirmation)

    @staticmethod
    def _ar(members):
        from yardimci import imzala
        return imzala.write_ar(members)

    def test_remember(self):
        pins = Path(tempfile.mkdtemp())
        imza.remember("x", b"anahtar", pins)
        self.assertEqual((pins / "x.gpg").read_bytes(), b"anahtar")


if __name__ == "__main__":
    unittest.main()
