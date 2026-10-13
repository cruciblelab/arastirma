"""Protokol 1.0: PROTOCOL.md'deki tablonun messages.json ile aynı olması ve denetleyicinin gerçekten yakalaması."""

import asyncio
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "protocol"))
sys.path.insert(0, str(ROOT / "linux"))

import check  # noqa: E402


class SpecTest(unittest.TestCase):
    def test_document_is_generated_from_spec(self):
        r = subprocess.run([sys.executable, str(ROOT / "protocol" / "table.py"), "--check"], capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_every_spec_is_understood(self):
        for name, m in check.MESSAGES.items():
            self.assertIn(m["from"], ("phone", "pc", "both"), name)
            for field, spec in m["fields"].items():
                with self.subTest(f"{name}.{field}"):
                    check.matches(spec, None)  # bilinmeyen tür ValueError verir

    def test_no_turkish_values(self):
        """Protokol değerleri İngilizce (gösterilen yazılar her uygulamanın kendi dilinde)."""
        text = (ROOT / "protocol" / "messages.json").read_text(encoding="utf-8")
        self.assertFalse(set("çğışöüÇĞİŞÖÜ") & set(text))


class CheckTest(unittest.TestCase):
    def test_good(self):
        self.assertEqual(check.problems({"type": "battery", "level": 76, "charging": True}, "phone"), [])
        self.assertEqual(check.problems({"type": "media_state", "active": False}, "pc"), [])
        self.assertEqual(check.problems({"type": "hello", "proto": 1, "device_id": "abcdef12", "name": "x",
                                         "platform": "android", "app": "talk-to-linux", "token": None,
                                         "features": ["qr1"], "commit": "a" * 64}, "phone"), [])

    def test_catches(self):
        self.assertEqual(check.problems({"type": "battery", "level": -1, "charging": True}, "phone"),
                         ["battery.level: -1 is not int:0..100"])
        self.assertEqual(check.problems({"type": "battery", "level": 5}, "phone"), ["battery.charging: missing"])
        self.assertEqual(check.problems({"type": "battery", "level": 5, "charging": True}, "pc"),
                         ["battery: sent by pc, the protocol says phone"])
        self.assertEqual(check.problems({"type": "phone_status", "flavor": "tam", "sdk": 34, "notif_access": True,
                                         "listener": True, "player": None, "notifications_sent": 0,
                                         "version": "0.20.0"}, "phone"),
                         ["phone_status.flavor: 'tam' is not enum:full|play|lite"])
        self.assertEqual(check.problems({"type": "ring", "loud": True}, "pc"),
                         ["ring.loud: not in protocol/messages.json"])
        self.assertEqual(check.problems({"type": "dance"}, "pc"), ["dance: not in protocol/messages.json"])
        self.assertEqual(check.problems({"type": "media_art", "art_id": "zz", "mime": "image/png", "data": "!!"},
                                        "pc"),
                         ["media_art.art_id: 'zz' is not hex:16", "media_art.data: '!!' is not b64"])

    def test_hook_catches_real_sends(self):
        """Testlerdeki izleme gerçekten bağlı: bilgisayar tanımsız bir ileti gönderirse yakalanır."""
        import protokol_denetimi
        from talkto import hub

        class Fake:
            closed = True  # sıraya koymadan dön

        with protokol_denetimi.izle() as found:
            asyncio.run(hub.Session.send(Fake(), {"type": "dance"}))
        self.assertEqual(found, ["dance: not in protocol/messages.json"])


if __name__ == "__main__":
    unittest.main()
