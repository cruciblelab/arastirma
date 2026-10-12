"""Telefonun pili azalınca uyarı: %15, %10, %5'te birer kez; şarja takılınca baştan. Ada ekrandaysa ada,
değilse masaüstü bildirimi."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import pil  # noqa: E402


def b(level, charging=False):
    return {"level": level, "charging": charging}


class TakipTest(unittest.TestCase):
    def test_each_threshold_once(self):
        t = pil.Takip()
        got = [t.check("p", b(lv)) for lv in (40, 16, 15, 14, 12, 10, 9, 6, 5, 4, 1)]
        self.assertEqual(got, [None, None, 15, None, None, 10, None, None, 5, None, None])

    def test_already_low_when_connecting_warns_once(self):
        t = pil.Takip()
        self.assertEqual(t.check("p", b(8)), 10)
        self.assertIsNone(t.check("p", b(7)))
        self.assertEqual(t.check("p", b(5)), 5)

    def test_charging_resets(self):
        t = pil.Takip()
        self.assertEqual(t.check("p", b(14)), 15)
        self.assertIsNone(t.check("p", b(14, charging=True)))
        self.assertEqual(t.check("p", b(14)), 15)  # kablo çıktı, hâlâ düşük: yeniden uyarır
        self.assertIsNone(t.check("p", b(-1)))
        self.assertIsNone(t.check("p", None))

    def test_phones_are_separate_and_forgotten(self):
        t = pil.Takip()
        self.assertEqual(t.check("a", b(12)), 15)
        self.assertEqual(t.check("b", b(12)), 15)
        t.keep_only({"b"})
        self.assertEqual(t.check("a", b(12)), 15)  # yeniden bağlandı

    def test_is_low(self):
        self.assertTrue(pil.is_low(b(15)))
        self.assertFalse(pil.is_low(b(16)))
        self.assertFalse(pil.is_low(b(5, charging=True)))
        self.assertFalse(pil.is_low(None))


class AppBatteryTest(unittest.TestCase):
    """App._check_battery: ada ekrandaysa ada uyarır, değilse bildirim; şarja takılınca bildirim kalkar."""

    def host(self, showing):
        try:
            from talkto.ui.app import App
        except (ImportError, ValueError) as e:
            self.skipTest(f"GTK yok: {e}")

        class Notifier:
            def __init__(self):
                self.shown, self.closed = [], []

            def show(self, title, body="", **kw):
                self.shown.append((title, body, kw))

            def close(self, key):
                self.closed.append(key)

        class Ada:
            def __init__(self):
                self.alerts = []

            def showing(self):
                return showing

            def battery_alert(self, did):
                self.alerts.append(did)

        class Host:
            _check_battery = App._check_battery

        h = Host()
        h.pil, h.notifier, h.ada = pil.Takip(), Notifier(), Ada()
        return h

    def test_ada_showing(self):
        h = self.host(True)
        h._check_battery([{"device_id": "p", "name": "POCO", "battery": b(14)}])
        self.assertEqual(h.ada.alerts, ["p"])
        self.assertEqual(h.notifier.shown, [])

    def test_no_ada_notification(self):
        h = self.host(False)
        h._check_battery([{"device_id": "p", "name": "POCO", "battery": b(14)}])
        h._check_battery([{"device_id": "p", "name": "POCO", "battery": b(13)}])  # aynı eşik: bir kez
        h._check_battery([{"device_id": "p", "name": "POCO", "battery": b(5)}])
        self.assertEqual([(t, kw["urgent"]) for t, _b, kw in h.notifier.shown],
                         [("POCO: pil %14", False), ("POCO: pil %5", True)])
        self.assertIn("kapanabilir", h.notifier.shown[-1][1])
        h._check_battery([{"device_id": "p", "name": "POCO", "battery": b(5, charging=True)}])
        self.assertIn("pil|p", h.notifier.closed)


if __name__ == "__main__":
    unittest.main()
