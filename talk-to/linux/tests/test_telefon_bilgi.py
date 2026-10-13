"""Telefonun sistem bilgileri: telefondan gelen iletinin temizlenmesi ve gösterilen satırlar."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import telefon_bilgi  # noqa: E402

MSG = {"type": "phone_info", "manufacturer": "Xiaomi", "model": "2311DRK48G", "android": "14", "sdk": 34,
       "security_patch": "2026-08-01", "app_version": "0.9.2", "uptime_s": 2 * 86400 + 3 * 3600 + 15 * 60,
       "battery": {"level": 76, "charging": True, "temp_c": 31.5, "health": "good"},
       "storage": {"total": 256 * 2**30, "free": 64 * 2**30}, "ram": {"total": 12 * 2**30, "free": 5 * 2**30},
       "network": "wifi", "fingerprint": "Xiaomi/garnet/garnet:14/UKQ1/V816:user/release-keys"}


class PhoneInfoTest(unittest.TestCase):
    def test_rows(self):
        rows = dict(telefon_bilgi.rows(telefon_bilgi.clean(MSG)))
        self.assertEqual(rows["Model"], "Xiaomi 2311DRK48G")
        self.assertEqual(rows["Sistem"], "Android 14 (API 34) · güvenlik yaması 2026-08-01")
        self.assertEqual(rows["Pil"], "%76 · şarj oluyor · 31,5 °C · sağlık: iyi")
        self.assertEqual(rows["Depolama"], "192,0 GB / 256,0 GB dolu (%75)")
        self.assertEqual(rows["Bellek"], "7,0 GB / 12,0 GB kullanımda (%58)")
        self.assertEqual(rows["Açık kalma"], "2 gün 3 sa 15 dk")
        self.assertEqual(rows["Ağ"], "Wi-Fi")

    def test_old_turkish_values(self):
        """0.19 ve önceki telefonlar ağ ve pil sağlığını Türkçe gönderiyordu: olduğu gibi gösterilir."""
        rows = dict(telefon_bilgi.rows(telefon_bilgi.clean(dict(MSG, network="mobil veri",
                                                                battery={"level": 5, "health": "iyi"}))))
        self.assertEqual(rows["Ağ"], "mobil veri")
        self.assertEqual(rows["Pil"], "%5 · sağlık: iyi")

    def test_bad_input(self):
        bad = {"model": 5, "battery": "x", "storage": {"total": "çok", "free": True}, "sdk": True,
               "manufacturer": "A" * 500}
        info = telefon_bilgi.clean(bad)
        self.assertEqual(len(info["manufacturer"]), 60)
        self.assertEqual(dict(telefon_bilgi.rows(info)), {"Model": "A" * 60})
        self.assertEqual(telefon_bilgi.rows(None), [])


if __name__ == "__main__":
    unittest.main()
