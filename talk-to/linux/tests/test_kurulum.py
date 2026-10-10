"""Kurulum yardımcısının denetimleri: hangi durumda ne söyleniyor, hangi düğme çıkıyor."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import setup_checks  # noqa: E402

STATUS = {"usb": True, "wireless": False, "port": 47600, "addresses": ["192.168.1.34"], "sessions": [],
          "bluetooth": True, "bt": {"available": True, "message": "Hazır"}}


def step(steps, key):
    return next(s for s in steps if s.key == key)


def item(s, prefix):
    return next(i for i in s.items if i.title.startswith(prefix))


class SetupChecksTest(unittest.TestCase):
    def test_fresh_computer(self):
        steps = setup_checks.steps(dict(STATUS, usb=False), {"adb": False, "apk": "/x.apk", "devices": []}, ufw=False)
        self.assertEqual([s.key for s in steps], ["hos-geldin", "telefon", "usb", "wifi", "ekler"])
        usb = step(steps, "usb")
        adb = item(usb, "adb")
        self.assertEqual((adb.ok, adb.action, adb.action_label), (False, "install_adb", "Kur"))
        self.assertEqual(item(usb, "USB bağlantısı").action, "enable_usb")
        self.assertFalse(any(i.title.startswith("Telefon") for i in usb.items))  # adb yokken telefon denetlenemez
        self.assertFalse(item(step(steps, "telefon"), "Bağlı telefon").ok)
        self.assertEqual(item(step(steps, "wifi"), "Kablosuz").action, "enable_wireless")

    def test_usb_phone_states(self):
        def phone(usb):
            return step(setup_checks.steps(STATUS, dict({"adb": True, "apk": "/x.apk"}, **usb), ufw=False), "usb").items

        self.assertIn("takılı değil", phone({"devices": []})[2].title)
        self.assertIn("hata ayıklama kapalı",
                      phone({"devices": [], "unseen": [{"serial": "s", "name": "Xiaomi Redmi", "adb": False}]})[2].title)
        self.assertIn("onay bekliyor", phone({"devices": [{"serial": "s", "state": "unauthorized"}]})[2].title)
        items = phone({"devices": [{"serial": "S1", "state": "device", "model": "Pixel 8", "app": False}]})
        self.assertTrue(items[2].ok)
        self.assertEqual(items[3].action, "install_phone_app:S1")
        items = phone({"devices": [{"serial": "S1", "state": "device", "model": "Pixel 8", "app": True}]})
        self.assertTrue(items[3].ok)

    def test_firewall_and_extras(self):
        steps = setup_checks.steps(dict(STATUS, wireless=True), {"adb": True, "devices": []}, ufw=True, autostart=True)
        fw = item(step(steps, "wifi"), "Güvenlik duvarı")
        self.assertEqual((fw.ok, fw.action, fw.optional), (False, "allow_firewall", True))
        self.assertIn("47600/tcp", fw.text)
        ekler = step(steps, "ekler")
        self.assertTrue(item(ekler, "Bluetooth").ok)
        self.assertTrue(item(ekler, "Oturum").ok)
        no_fw = setup_checks.steps(STATUS, {"adb": True, "devices": []}, ufw=False)
        self.assertFalse(any(i.title.startswith("Güvenlik") for i in step(no_fw, "wifi").items))

    def test_ufw_conf(self):
        with tempfile.TemporaryDirectory() as d:
            conf = Path(d) / "ufw.conf"
            conf.write_text("# ufw\nENABLED=yes\nLOGLEVEL=low\n")
            self.assertTrue(setup_checks.ufw_enabled(conf))
            conf.write_text("ENABLED=no\n")
            self.assertFalse(setup_checks.ufw_enabled(conf))
            self.assertFalse(setup_checks.ufw_enabled(Path(d) / "yok"))


if __name__ == "__main__":
    unittest.main()
