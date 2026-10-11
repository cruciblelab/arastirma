"""apt denemesinin ve kurulum çıktısının ayrıştırılması (yetki gerektirmez)."""

import os
import unittest
from unittest import mock

import yardimci  # noqa: F401  (sys.path)
from guncelleyici import apt

SIM = """NOTE: This is only a simulation!
Reading package lists...
Note, selecting 'talk-to-android' instead of '/tmp/x/talk-to-android_0.7.1_all.deb'
The following packages will be upgraded:
  talk-to-android
Inst gir1.2-adw-1 (1.1.7-0ubuntu0.22.04.1 Ubuntu:22.04/jammy-updates [amd64])
Inst talk-to-android [0.7.0] (0.7.1 local-deb [all])
Remv eski-paket [2.0]
Conf talk-to-android (0.7.1 local-deb [all])
"""

UNMET = """Some packages could not be installed.
The following packages have unmet dependencies:
 deneme : Depends: olmayan-paket but it is not installable
E: Unable to correct problems, you have held broken packages.
"""


class SimulationTest(unittest.TestCase):
    def test_parse(self):
        d = apt.parse_simulation(SIM)
        self.assertEqual(d.install, [("gir1.2-adw-1", None, "1.1.7-0ubuntu0.22.04.1"),
                                     ("talk-to-android", "0.7.0", "0.7.1")])
        self.assertEqual(d.extra("talk-to-android"), [("gir1.2-adw-1", None, "1.1.7-0ubuntu0.22.04.1")])
        self.assertEqual(d.remove, ["eski-paket"])
        self.assertEqual(d.errors, [])

    def test_unmet(self):
        d = apt.parse_simulation(UNMET)
        self.assertIn("deneme : Depends: olmayan-paket but it is not installable", d.errors)
        self.assertTrue(any("broken packages" in e for e in d.errors))

    def test_flags(self):
        self.assertEqual(apt.flags_for("guncelle", False), ["--no-remove"])
        self.assertEqual(apt.flags_for("ayni", True), ["--reinstall"])
        self.assertEqual(apt.flags_for("eski", False), ["--allow-downgrades", "--no-remove"])

    def test_elevation_whitelist(self):
        with mock.patch.dict(os.environ, {"PAKET_GUNCELLEYICI_YETKI": "sh -c 'kötü'"}):
            self.assertEqual(apt.install_command("/x.deb", [])[0], "pkexec")
        with mock.patch.dict(os.environ, {"PAKET_GUNCELLEYICI_YETKI": "sudo -n"}):
            self.assertEqual(apt.install_command("/x.deb", [])[:3], ["sudo", "-n", "/usr/bin/apt-get"])
        cmd = apt.install_command("/x.deb", ["--no-remove"])
        self.assertEqual(cmd[-1], "/x.deb")
        self.assertIn("APT::Status-Fd=1", cmd)


class OutputTest(unittest.TestCase):
    def test_lock_english_and_turkish(self):
        en = ("Waiting for cache lock: Could not get lock /var/lib/dpkg/lock-frontend. "
              "It is held by process 1073 (unattended-upgr)... 12s")
        tr = ("Önbellek kilidi bekleniyor: /var/lib/dpkg/lock-frontend kilidi alınamadı. "
              "1073 süreci tarafından tutuluyor (unattended-upgr)... 95 sn.")
        for line in (en, tr):
            o = apt.parse_line(line)
            self.assertEqual((o.kind, o.pid, o.holder), ("kilit", 1073, "unattended-upgr"))
        self.assertEqual(apt.holder_text("unattended-upgr"), "Ubuntu'nun otomatik güncellemesi")

    def test_status_and_errors(self):
        o = apt.parse_line("pmstatus:talk-to-android:42.8571:Configuring talk-to-android (all)")
        self.assertEqual((o.kind, round(o.percent), o.text), ("ilerleme", 43, "Configuring talk-to-android (all)"))
        self.assertEqual(apt.parse_line("E: Sub-process /usr/bin/dpkg returned an error code (1)").kind, "hata")
        self.assertEqual(apt.parse_line("pmerror:/tmp/x.deb:50:dependency problems").text, "dependency problems")
        self.assertIsNone(apt.parse_line("   "))

    def test_stream_splits_carriage_returns(self):
        p = apt.Ayristirici()
        ev = p.feed("Waiting for cache lock: Could not get lock /var/lib/dpkg/lock-frontend. It is held by "
                    "process 9 (apt)... 1s\rWaiting for cache lock: Could not get lock /var/lib/dpkg/lock-fr")
        self.assertEqual([e.kind for e in ev], ["kilit"])
        ev = p.feed("ontend. It is held by process 9 (apt)... 2s\npmstatus:x:10:Unpacking x\npmstat")
        self.assertEqual([e.kind for e in ev], ["kilit", "ilerleme"])
        ev = p.feed("us:x:100:Installed x")
        self.assertEqual(ev, [])
        self.assertEqual([e.percent for e in p.flush()], [100.0])


if __name__ == "__main__":
    unittest.main()
