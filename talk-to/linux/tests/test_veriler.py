"""Uygulamanın kendi verileri: önbellek temizleme, sıfırlama (çöp kutusuna ya da yedeğe; kalıcı silinmez)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import veriler  # noqa: E402


class VerilerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_clear_cache_keeps_open_logs(self):
        c = self.tmp / "cache"
        (c / "kapaklar").mkdir(parents=True)
        (c / "kapaklar" / "a.jpg").write_bytes(b"x" * 1000)
        (c / "scrcpy-ABC.log").write_text("y" * 10)
        (c / "gunluk.txt").write_text("açık günlük")
        (c / "cokme.txt").write_text("açık")
        self.assertEqual(veriler.cache_size(c), 1010)
        self.assertEqual(veriler.clear_cache(c), 1010)
        self.assertEqual(sorted(p.name for p in c.iterdir()), ["cokme.txt", "gunluk.txt"])

    def test_reset_moves_settings_keeps_identity(self):
        cfg = self.tmp / "cfg"
        cfg.mkdir()
        for n in ("ayarlar.json", "sertifika.pem", "anahtar.pem"):
            (cfg / n).write_text(n)
        self.assertEqual([p.name for p in veriler.reset_paths(False, cfg)], ["ayarlar.json"])
        self.assertEqual(len(veriler.reset_paths(True, cfg)), 3)
        where = veriler.reset(False, cfg, backup_root=self.tmp)
        self.assertFalse((cfg / "ayarlar.json").exists())
        self.assertTrue((cfg / "sertifika.pem").exists() and (cfg / "anahtar.pem").exists())
        if "yedek" in where:  # çöp kutusu yoksa (ör. /tmp) tarihli yedek klasörüne
            backup = next(self.tmp.glob("talk-to-android-yedek-*"))
            self.assertEqual((backup / "ayarlar.json").read_text(), "ayarlar.json")
        else:
            self.assertEqual(where, "çöp kutusuna taşındı")

    def test_backup_when_trash_unavailable(self):
        from unittest import mock
        f = self.tmp / "ayarlar.json"
        f.write_text("{}")
        with mock.patch.dict(sys.modules, {"gi.repository": None}):
            where = veriler.to_trash([f], backup_root=self.tmp)
        self.assertIn("talk-to-android-yedek-", where)
        self.assertFalse(f.exists())


if __name__ == "__main__":
    unittest.main()
