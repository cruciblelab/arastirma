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
    def phone_step(self, usb, status=STATUS, simple=False):
        return step(setup_checks.steps(status, dict({"adb": True, "apk": "/x.apk", "apk_version": "0.9.0"}, **usb),
                                       ufw=False, simple=simple), "telefon")

    def test_qr_first_and_usb_optional(self):
        """Hiçbir şey hazır değilken (adb yok, Wi-Fi kapalı) bile ilk satır karekod; USB satırları isteğe bağlı."""
        tel = self.phone_step({"adb": False, "devices": []}, dict(STATUS, wireless=False))
        self.assertEqual(tel.items[0].action, "show_qr")
        self.assertTrue(all(i.optional for i in tel.items if i.action in ("install_adb", "enable_usb")))

    def test_fresh_computer(self):
        steps = setup_checks.steps(dict(STATUS, usb=False), {"adb": False, "apk": "/x.apk", "devices": []}, ufw=False)
        self.assertEqual([s.key for s in steps], ["hos-geldin", "telefon", "wifi", "ekler"])
        tel = step(steps, "telefon")
        adb = item(tel, "USB için adb")
        self.assertEqual((adb.ok, adb.action, adb.action_label), (False, "install_adb", "Kur"))
        self.assertEqual(item(tel, "Karekodla bağla").action, "show_qr")  # Wi-Fi kapalıysa karekod açar
        tel = self.phone_step({"devices": []}, dict(STATUS, usb=False))
        self.assertEqual(item(tel, "USB bağlantısı kapalı").action, "enable_usb")

    def test_usb_phone_states(self):
        self.assertIsNone(item(self.phone_step({"devices": []}), "USB ile: telefon takılı değil").ok)
        self.assertFalse(item(self.phone_step({"devices": [], "unseen": [{"serial": "s", "name": "Xiaomi Redmi"}]}),
                              "Xiaomi Redmi takılı ama USB hata ayıklama kapalı").ok)
        self.assertFalse(item(self.phone_step({"devices": [{"serial": "s", "state": "unauthorized"}]}),
                              "Telefon onay bekliyor").ok)

    def test_dev_options_guide_by_brand(self):
        """Takılı ama hata ayıklaması kapalı telefon: markaya göre adım adım (Xiaomi'de HyperOS sürümü, ek anahtarlar)."""
        tel = self.phone_step({"devices": [], "unseen": [{"serial": "s", "name": "Xiaomi POCO", "vendor": "2717"}]})
        steps = [i.title for i in tel.items if i.title[:2] in ("1.", "2.", "3.", "4.")]
        self.assertEqual(steps[0], "1. Geliştirici seçeneklerini aç")
        self.assertIn("HyperOS sürümü", item(tel, "1.").text)
        self.assertIn("Ek ayarlar", item(tel, "2.").text)
        self.assertEqual(len(steps), 4)
        self.assertEqual(setup_checks.brand_of({"vendor": "04e8"}), "samsung")
        self.assertEqual(setup_checks.brand_of({"name": "realme RMX3085"}), "oppo")
        self.assertIn("Yazılım bilgileri", setup_checks.dev_guide({"vendor": "04e8"})[0][1])
        self.assertEqual(setup_checks.brand_of({"vendor": "abcd", "name": "Bilinmeyen"}), "")
        # Telefon onay bekliyorsa (adb görüyor) adımlar yerine yalnızca onay satırı.
        tel = self.phone_step({"devices": [{"serial": "s", "state": "unauthorized"}],
                               "unseen": [{"serial": "x", "name": "Xiaomi"}]})
        self.assertFalse(any(i.title.startswith("1.") for i in tel.items))

    def test_connect_from_computer(self):
        """USB'deki telefon telefona gitmeden bağlanır: kur → bağlan → bağlı."""
        dev = {"serial": "S1", "state": "device", "model": "2311DRK48G", "name": "POCO X6 Pro", "app": False}
        inst = item(self.phone_step({"devices": [dev]}), "POCO X6 Pro: Talk To yok")
        self.assertEqual((inst.action, inst.action_label), ("install_phone_app:S1", "Kur ve bağlan"))
        dev.update(app=True, app_version="0.9.0")
        tel = self.phone_step({"devices": [dev]}, dict(STATUS, wireless=True))
        conn = item(tel, "POCO X6 Pro USB'de")
        self.assertEqual((conn.ok, conn.action, conn.action_label), (False, "connect_usb:S1", "Bağlan"))
        # Karekod hep ilk ve önerilen yol (kablo varken de).
        self.assertEqual((tel.items[0].title, tel.items[0].action, tel.items[0].action_label),
                         ("Karekodla bağla (en kolayı)", "show_qr", "Karekodu göster"))
        st = dict(STATUS, sessions=[{"name": "Coşkun'un telefonu", "kind": "usb", "adb_serial": "S1",
                                     "phone": {"notif_access": True, "listener": True}}])
        tel = self.phone_step({"devices": [dev]}, st)
        self.assertTrue(item(tel, "Coşkun'un telefonu bağlı (USB)").ok)
        self.assertFalse(any(i.action and i.action.startswith("connect_usb") for i in tel.items))
        self.assertFalse(any(i.action == "show_qr" for i in tel.items))  # bağlıyken karekod önerilmez

    def test_permissions_given_on_phone_are_not_asked_again(self):
        """Telefonda elle verilen izinler adb'den okunur: bağlanmadan da "tamam" görünür, yeniden istenmez."""
        dev = {"serial": "S1", "state": "device", "model": "P", "app": True, "app_version": "0.9.0",
               "perms": {"post": True, "listener": True, "battery": True}}
        self.assertTrue(item(self.phone_step({"devices": [dev]}), "Telefondaki izinler tamam").ok)
        dev["perms"] = {"post": False, "listener": True, "battery": False}
        perms = item(self.phone_step({"devices": [dev]}), "Telefondaki izinler")
        self.assertEqual((perms.ok, perms.action, perms.action_label), (False, "phone_setup:S1", "Tamamla"))
        self.assertIn("pil", perms.text)
        self.assertIn("bildirim izni", perms.text)
        self.assertNotIn("bildirim erişimi", perms.text)
        # Telefonun kendi söylediği (bağlıyken) daha güncel: adb'nin eski okuması "eksik" dese de.
        dev["perms"] = {"listener": False}
        st = dict(STATUS, sessions=[{"name": "P", "kind": "usb", "adb_serial": "S1", "phone": {"notif_access": True}}])
        self.assertTrue(item(self.phone_step({"devices": [dev]}, st), "Telefondaki izinler tamam").ok)
        # Hiçbir bilgi yoksa satır çıkmaz (telefon takılı değil, bağlı değil).
        dev["perms"] = {}
        items = self.phone_step({"devices": [dev]}).items
        self.assertFalse(any(i.title.startswith("Telefondaki izinler") for i in items))

    def test_xiaomi_and_outdated_app(self):
        dev = {"serial": "S1", "state": "device", "model": "Redmi Note 12", "app": True, "app_version": "0.6.0",
               "maker": "Xiaomi", "xiaomi_permissions": False, "xiaomi_install": False,
               "perms": {"post": False, "listener": False, "battery": False}}
        tel = self.phone_step({"devices": [dev]})
        titles = [i.title for i in tel.items]
        self.assertIn("Xiaomi: “USB üzerinden yükle” kapalı", titles)
        self.assertIn("Xiaomi: “USB hata ayıklama (Güvenlik ayarları)” kapalı", titles)
        upd = item(tel, "Redmi Note 12: Talk To eski (0.6.0)")
        self.assertEqual((upd.ok, upd.action, upd.action_label), (False, "install_phone_app:S1", "Güncelle"))
        # İzinler Xiaomi ayarı açılmadan bilgisayardan verilemez: düğme yerine ne yapılacağı yazar.
        self.assertIsNone(item(tel, "Telefondaki izinler").action)
        # Ayarlar açılıp uygulama güncellenince uyarılar kalkar, "Bağlan" ve "Tamamla" çıkar.
        dev.update(xiaomi_permissions=True, xiaomi_install=True, app_version="0.9.0")
        tel = self.phone_step({"devices": [dev]})
        self.assertFalse(any(i.title.startswith(("Xiaomi", "Redmi Note 12: Talk To eski")) for i in tel.items))
        self.assertEqual(item(tel, "Redmi Note 12 USB'de").action, "connect_usb:S1")
        self.assertEqual(item(tel, "Telefondaki izinler").action, "phone_setup:S1")
        # Telefonda izinler verildiyse Xiaomi'nin "Güvenlik ayarları" anahtarı artık gerekmez.
        dev.update(xiaomi_permissions=False, perms={"post": True, "listener": True, "battery": True})
        self.assertFalse(any(i.title.startswith("Xiaomi") for i in self.phone_step({"devices": [dev]}).items))

    def test_play_and_light_versions_offer_full_upgrade(self):
        """Play'den (hilesiz) ya da hafif sürüm kuruluysa: buradaki tam sürüm aynı sürüm olsa da "Tam sürüme
        yükselt" çıkar ve neyin eksik olduğu söylenir. Telefondaki daha yeniyse tam sürüm onu eskitmez."""
        cases = {"0.9.0-play": "Play sürümü", "0.8.0-play": "Play sürümü", "0.9.0-hafif": "hafif sürüm"}
        for version, kind in cases.items():
            with self.subTest(version):
                dev = {"serial": "S1", "state": "device", "model": "Pixel 8", "app": True, "app_version": version}
                up = item(self.phone_step({"devices": [dev]}), f"Pixel 8: Talk To {kind}")
                self.assertEqual((up.ok, up.action, up.action_label),
                                 (False, "install_phone_app:S1", "Tam sürüme yükselt"))
                self.assertIn("eşleşme ve ayarlar korunur", up.text)
        self.assertIn("aramaları bilgisayardan cevaplanamaz", setup_checks.update_texts(
            {"app": True, "app_version": "0.9.0-play"}, {"apk_version": "0.9.0"})[1])
        self.assertIsNone(setup_checks.app_update({"app": True, "app_version": "0.9.1-play"}, {"apk_version": "0.9.0"}))
        self.assertIsNone(setup_checks.app_update({"app": True, "app_version": "0.9.0"}, {"apk_version": "0.9.0"}))
        self.assertEqual(setup_checks.app_update({"app": True, "app_version": "0.8.0"}, {"apk_version": "0.9.0"}),
                         "update")
        self.assertEqual([setup_checks.app_flavor(v) for v in ("0.18.0", "0.18.0-play", "0.18.0-hafif", None)],
                         ["tam", "play", "hafif", "tam"])

    def test_nothing_recognised_lists_usb_devices(self):
        info = item(self.phone_step({"devices": [], "usb_devices": ["Logitech USB Receiver (046d:c52b)"]}),
                    "Bu bilgisayarın gördüğü")
        self.assertIn("046d:c52b", info.text)

    def test_wifi_phone_permissions_from_its_status(self):
        st = dict(STATUS, sessions=[{"name": "Pixel", "kind": "wifi", "phone": {"notif_access": False}}])
        tel = self.phone_step({"devices": []}, st)
        self.assertTrue(item(tel, "Pixel bağlı (Wi-Fi)").ok)
        perms = item(tel, "Telefondaki izinler")
        self.assertEqual((perms.ok, perms.action), (False, None))
        self.assertIn("İzinler ve yetkiler", perms.text)

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

    def test_simple_mode_usb_optional(self):
        steps = setup_checks.steps(STATUS, {"adb": False, "devices": []}, ufw=False, simple=True)
        self.assertFalse(item(step(steps, "wifi"), "Kablosuz").optional)
        self.assertTrue(item(step(steps, "telefon"), "USB için adb").optional)
        self.assertEqual(item(step(steps, "telefon"), "Karekodla bağla").action, "show_qr")
        self.assertIn("Özellikler", steps[0].text)
        # Karekod varken USB her kipte isteğe bağlı: kablo ve geliştirici ayarı kurulumu "bitmemiş" göstermez.
        full = setup_checks.steps(STATUS, {"adb": False, "devices": []}, ufw=False)
        self.assertTrue(item(step(full, "telefon"), "USB için adb").optional)

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
