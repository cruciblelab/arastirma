"""Karekodun içeriği ve kareleri (gömülü qrcodegen)."""

import asyncio
import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import karekod  # noqa: E402


class KarekodTest(unittest.TestCase):
    def test_hosts_order(self):
        addrs = ["172.17.0.1", "100.101.102.103", "192.168.1.34", "10.0.0.5", "192.168.122.1", "x", "192.168.1.34",
                 "85.105.1.2"]
        self.assertEqual(karekod.hosts(addrs), ["192.168.1.34", "10.0.0.5", "100.101.102.103", "172.17.0.1",
                                                "192.168.122.1"])

    def test_link(self):
        link = karekod.link(["192.168.1.34"], 47600, "ab" * 32, "cd" * 16, "Ali'nin bilgisayarı & ev")
        self.assertEqual(link, "talkto://pair?v=1&h=192.168.1.34&p=47600&fp=" + "ab" * 32 + "&k=" + "cd" * 16
                         + "&n=Ali%27nin%20bilgisayar%C4%B1%20%26%20ev")

    def test_shared_vector(self):
        """Android aynı kareleri ZXing ile çözer (AuthTest.qrMatrixDecodes): vektör bu kodla güncel olmalı."""
        import json
        vec = json.loads((Path(__file__).resolve().parents[2] / "protocol" / "vectors.json").read_text())["qr_matrix"]
        rows = ["".join("1" if c else "0" for c in r) for r in karekod.matrix(vec["text"])]
        self.assertEqual(rows, vec["rows"])

    def test_matrix(self):
        link = karekod.link(["192.168.1.34", "10.0.0.5"], 47600, "ab" * 32, "cd" * 16, "x" * 40)
        m = karekod.matrix(link)
        self.assertEqual(len(m), len(m[0]))
        self.assertLessEqual(len(m), 69)  # sürüm 13 ya da altı: telefon kamerası rahat okur
        self.assertTrue(all(m[r][c] for r, c in ((0, 0), (0, 6), (6, 0), (6, 6))))  # konum işaretinin köşeleri


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
class QrWindowTest(unittest.TestCase):
    def test_show_scan_pair_close(self):
        """Pencere karekodu gösterir; telefon okuyunca onaysız eşleşir, pencere kapanır, karekod geçersizleşir."""
        from urllib.parse import parse_qs, urlsplit
        from sahte_telefon import FakePhone
        from talkto.hub import Hub
        from talkto.ui.app import App
        tmp = tempfile.mkdtemp()
        os.environ["TALKTO_CONFIG_DIR"] = tmp + "/cfg"
        os.environ["TALKTO_CACHE_DIR"] = tmp + "/cache"
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        def factory(config, emit):
            for k, v in (("port", port), ("wireless", False), ("usb", True), ("bluetooth", False),
                         ("setup_done", True)):
                config.set(k, v)
            return Hub(config, emit, enable_media=False, enable_discovery=False)

        app = App(hub_factory=factory)
        seen, phone = {}, []

        def connect(key):
            async def run():
                p = FakePhone("telefon-karekod-1")
                r = await p.connect(port=port, qr_key=key)
                await p.close()
                return r
            phone.append(asyncio.run(run()))

        steps = []

        def step():
            steps.append(1)
            try:
                if len(steps) == 1:
                    app.show_qr()
                elif "link" not in seen:
                    w = app.qr_window
                    if w is None:
                        return True
                    seen["link"] = True
                    seen["matrix"] = bool(w.matrix)
                    seen["note"] = w.note.get_text()
                    key = app.hub.qr_key()
                    seen["key_in_link"] = key is not None
                    threading.Thread(target=connect, args=(key,), daemon=True).start()
                elif (phone and app.qr_window is None) or len(steps) > 40:
                    seen["phone"] = list(phone)
                    seen["closed"] = app.qr_window is None
                    seen["key_after"] = app.hub.qr_key()
                    seen["trusted"] = "telefon-karekod-1" in app.config.trusted()
                    app._quit()
                    return False
            except Exception as e:  # noqa: BLE001
                seen["error"] = repr(e)
                app._quit()
                return False
            return True

        GLib.timeout_add(300, step)
        app.run([])
        self.assertNotIn("error", seen)
        self.assertTrue(seen["matrix"])
        self.assertIn("Wi-Fi bağlantısı açıldı", seen["note"])
        self.assertEqual(seen["phone"], ["welcome"])
        self.assertTrue(seen["closed"])
        self.assertIsNone(seen["key_after"])
        self.assertTrue(seen["trusted"])


if __name__ == "__main__":
    unittest.main()
