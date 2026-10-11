"""USB: takılı telefonun sysfs'ten tanınması (adb görmese de) ve adb çıktısının okunması."""

import asyncio
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto.usb import AdbWatcher, is_network_serial, parse_devices, usb_phones  # noqa: E402


def device(root: Path, name: str, vendor: str, ifaces, **attrs):
    d = root / name
    d.mkdir()
    (d / "idVendor").write_text(vendor + "\n")
    for k, v in attrs.items():
        (d / k).write_text(v + "\n")
    for i, (cls, sub, proto, label) in enumerate(ifaces):
        f = root / f"{name}:1.{i}"
        f.mkdir()
        (f / "bInterfaceClass").write_text(cls + "\n")
        (f / "bInterfaceSubClass").write_text(sub + "\n")
        (f / "bInterfaceProtocol").write_text(proto + "\n")
        if label:
            (f / "interface").write_text(label + "\n")


class UsbPhonesTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "usb1").mkdir()  # kök hub: idVendor yok sayılmaz ama arayüzü yok
        (self.root / "usb1" / "idVendor").write_text("1d6b\n")

    def test_phone_without_debugging(self):
        device(self.root, "1-2", "2717", [("06", "01", "01", "MTP")],
               manufacturer="Xiaomi", product="Redmi Note 12", serial="abc123")
        self.assertEqual(usb_phones(str(self.root)),
                         [{"serial": "abc123", "name": "Xiaomi Redmi Note 12", "adb": False}])

    def test_phone_with_adb_interface(self):
        device(self.root, "1-3", "18d1", [("06", "01", "01", "MTP"), ("ff", "42", "01", "ADB Interface")],
               product="Pixel 8", serial="P8")
        self.assertTrue(usb_phones(str(self.root))[0]["adb"])

    def test_keyboard_and_mouse_ignored(self):
        device(self.root, "1-4", "17ef", [("03", "01", "01", "")], product="Lenovo Keyboard")  # Lenovo da telefon üretir
        device(self.root, "1-5", "046d", [("03", "01", "02", "")], product="Mouse")
        self.assertEqual(usb_phones(str(self.root)), [])

    def test_missing_root(self):
        self.assertEqual(usb_phones(str(self.root / "yok")), [])

    def test_non_phones_from_phone_vendors(self):
        # Lenovo dock'un Ethernet'i üreticiye özel (ff) arayüzlü; Samsung SSD yığın depolama; fotoğraf makinesi PTP.
        device(self.root, "2-1", "17ef", [("ff", "ff", "00", "")], manufacturer="Lenovo", product="USB-C Dock Ethernet")
        device(self.root, "2-2", "04e8", [("08", "06", "50", "")], manufacturer="Samsung", product="PSSD T7")
        device(self.root, "2-3", "04a9", [("06", "01", "01", "")], manufacturer="Canon", product="EOS 250D")
        device(self.root, "2-4", "17ef", [("0e", "01", "00", ""), ("01", "01", "00", "")], product="Lenovo FHD Webcam")
        self.assertEqual(usb_phones(str(self.root)), [])

    def test_charging_only_and_tethering_phone(self):
        device(self.root, "3-1", "18d1", [("ff", "ff", "00", "")], manufacturer="Google", product="Pixel 8", serial="P")
        device(self.root, "3-2", "2717", [("e0", "01", "03", "RNDIS"), ("0a", "00", "00", "")],
               manufacturer="Xiaomi", product="Redmi", serial="R")
        self.assertEqual([p["serial"] for p in usb_phones(str(self.root))], ["P", "R"])

    def test_parse_adb_daemon_start(self):
        out = ("* daemon not running; starting now at tcp:5037\n* daemon started successfully\n"
               "List of devices attached\nP8\tdevice\n\n")
        self.assertEqual(parse_devices(out), {"P8": "device"})

    def test_network_serials(self):
        self.assertTrue(is_network_serial("192.168.1.5:5555"))
        self.assertTrue(is_network_serial("adb-R5CT-abc._adb-tls-connect._tcp"))
        self.assertFalse(is_network_serial("R5CT1234"))

    def test_parse_adb_states(self):
        out = ("List of devices attached\n"
               "P8\tdevice\n"
               "abc\tunauthorized\n"
               "xyz\tno permissions (missing udev rules? user is in the plugdev group); see [http://x]\n")
        self.assertEqual(parse_devices(out), {"P8": "device", "abc": "unauthorized", "xyz": "no"})


FAKE_ADB = """#!/bin/sh
# Sahte adb: çağrıları günlüğe yazar; reverse listesi durum dosyasından.
echo "$*" >> "$ADB_LOG"
case "$*" in
  devices) printf 'List of devices attached\\nS1\\tdevice\\n10.0.0.2:5555\\tdevice\\n' ;;
  *"reverse --list"*) cat "$ADB_REV" 2>/dev/null || true ;;  # kural yoksa gerçek adb de boş ve 0 döner
  *"reverse tcp:"*) echo "UsbFfs tcp:47600 tcp:47600" > "$ADB_REV" ;;
  *getprop*) echo "Pixel 8" ;;
  *"pm path"*) echo "package:/data/app/x.apk" ;;
esac
"""


class AdbWatcherTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        adb = self.dir / "adb"
        adb.write_text(FAKE_ADB)
        adb.chmod(adb.stat().st_mode | stat.S_IEXEC)
        self.env = {"PATH": f"{self.dir}:{os.environ['PATH']}", "ADB_LOG": str(self.dir / "log"),
                    "ADB_REV": str(self.dir / "rev")}
        self.old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def tearDown(self):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def calls(self):
        return (self.dir / "log").read_text().splitlines()

    def test_tunnel_rebuilt_when_dropped(self):
        w = AdbWatcher(47600, lambda snap: None)

        async def run():
            await w._poll()
            self.assertEqual(list(w.devices), ["S1"])  # ip:5555 USB sayılmaz
            self.assertTrue(w.devices["S1"]["tunnel"])
            await w._poll()  # tünel duruyor: yeniden kurulmaz
            self.assertEqual(sum("reverse tcp:" in c for c in self.calls()), 1)
            (self.dir / "rev").unlink()  # adb sunucusu yeniden başladı, kural gitti
            await w._poll()
            self.assertEqual(sum("reverse tcp:" in c for c in self.calls()), 2)
            self.assertTrue(w.devices["S1"]["tunnel"])
            self.assertFalse(any("10.0.0.2" in c for c in self.calls()))

        asyncio.run(run())

    def test_install_not_started_twice(self):
        w = AdbWatcher(47600, lambda snap: None)
        w.devices["S1"] = {"state": "device", "installing": True}
        os.environ["TALKTO_APK"] = str(self.dir / "adb")  # var olan herhangi bir dosya
        try:
            ok, text = asyncio.run(w.install_app("S1"))
        finally:
            os.environ.pop("TALKTO_APK")
        self.assertFalse(ok)
        self.assertIn("zaten", text)



class ApkVersionTest(unittest.TestCase):
    """Paketteki telefon uygulamasının sürümü bilgisayarın sürümünden ayrı okunur (0.8.1'de aynı sanılıyordu:
    telefondaki 0.8.0 hep "eski" görünür, "Güncelle" aynı sürümü yeniden kurardı)."""

    def test_sidecar_and_source(self):
        import tempfile
        from talkto.usb import apk_version, parse_perms
        d = Path(tempfile.mkdtemp())
        apk = d / "talk-to-linux.apk"
        apk.write_bytes(b"PK")
        self.assertIsNone(apk_version(apk))  # bilinmiyorsa "eski" denmez
        (d / "talk-to-linux.apk.surum").write_text("0.9.0\n")
        self.assertEqual(apk_version(apk), "0.9.0")
        src = d / "android/app"
        (src / "build/outputs/apk/tam/release").mkdir(parents=True)
        (src / "build.gradle.kts").write_text('        versionCode = 14\n        versionName = "0.9.1"\n')
        self.assertEqual(apk_version(src / "build/outputs/apk/tam/release/app-tam-release.apk"), "0.9.1")
        self.assertIsNone(apk_version(None))
        self.assertEqual(parse_perms("android.permission.POST_NOTIFICATIONS: granted=false, flags=[ ]"),
                         {"post": False})
        self.assertEqual(parse_perms(""), {"post": None})


if __name__ == "__main__":
    unittest.main()
