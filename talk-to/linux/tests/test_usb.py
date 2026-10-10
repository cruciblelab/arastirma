"""USB: takılı telefonun sysfs'ten tanınması (adb görmese de) ve adb çıktısının okunması."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto.usb import parse_devices, usb_phones  # noqa: E402


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

    def test_parse_adb_states(self):
        out = ("List of devices attached\n"
               "P8\tdevice\n"
               "abc\tunauthorized\n"
               "xyz\tno permissions (missing udev rules? user is in the plugdev group); see [http://x]\n")
        self.assertEqual(parse_devices(out), {"P8": "device", "abc": "unauthorized", "xyz": "no"})


if __name__ == "__main__":
    unittest.main()
