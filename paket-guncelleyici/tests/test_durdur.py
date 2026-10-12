"""Durmaya zorlama: ne yapıldığının anlaşılması (risk) ve yönetici olarak çalışan yardımcının denetimleri.

Gerçek kilitle uçtan uca deneme test_uctan_uca.py'de (CI, sudo -n).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guncelleyici import apt, durdur  # noqa: E402


def fake_proc(procs):
    """procs: [(pid, comm, cmdline)] → sahte /proc klasörü."""
    d = Path(tempfile.mkdtemp())
    for pid, comm, cmd in procs:
        p = d / str(pid)
        p.mkdir()
        (p / "comm").write_text(comm + "\n")
        (p / "cmdline").write_bytes(cmd.replace(" ", "\0").encode() + b"\0")
    (d / "self").mkdir()  # sayı olmayan girdiler atlanır
    return str(d)


class RiskTest(unittest.TestCase):
    def test_downloading_is_safe(self):
        proc = fake_proc([(10, "unattended-upgr", "/usr/bin/python3 /usr/bin/unattended-upgrade"),
                          (11, "http", "/usr/lib/apt/methods/http")])
        self.assertEqual(durdur.risk(proc), (durdur.GUVENLI, []))

    def test_installing_names_packages(self):
        proc = fake_proc([(10, "unattended-upgr", "/usr/bin/python3 /usr/bin/unattended-upgrade"),
                          (12, "dpkg", "/usr/bin/dpkg --status-fd 10 --no-triggers --unpack --auto-deconfigure "
                                       "/var/cache/apt/archives/firefox_131.0_amd64.deb "
                                       "/var/cache/apt/archives/thunderbird_128.3_amd64.deb")])
        self.assertEqual(durdur.risk(proc), (durdur.KURUYOR, ["firefox", "thunderbird"]))

    def test_kernel_and_boot_loader_are_never_stopped(self):
        for procs in ([(12, "dpkg", "/usr/bin/dpkg --status-fd 10 --unpack "
                                    "/var/cache/apt/archives/linux-image-6.8.0-45-generic_6.8.0-45.45_amd64.deb")],
                      [(12, "dpkg", "/usr/bin/dpkg --configure grub-efi-amd64-signed")],
                      [(13, "update-initramf", "/bin/sh /usr/sbin/update-initramfs -u -k all")],
                      [(14, "dkms", "/usr/sbin/dkms autoinstall")]):
            with self.subTest(procs[0][2]):
                self.assertEqual(durdur.risk(fake_proc(procs))[0], durdur.CEKIRDEK)

    def test_unrelated_mentions_do_not_block(self):
        proc = fake_proc([(20, "gedit", "/usr/bin/gedit /etc/default/grub"),
                          (21, "less", "/usr/bin/less /usr/share/doc/linux-image/changelog")])
        self.assertEqual(durdur.risk(proc)[0], durdur.GUVENLI)


class HelperTest(unittest.TestCase):
    def test_holds_lock(self):
        f = Path(tempfile.mkdtemp()) / "locks"
        f.write_text("1: POSIX  ADVISORY  WRITE 4321 08:02:131090 0 EOF\n"
                     "2: FLOCK  ADVISORY  WRITE 999 00:1a:5 0 EOF\n")
        self.assertTrue(durdur.holds_lock(4321, str(f), {131090}))
        self.assertFalse(durdur.holds_lock(4321, str(f), {777}))  # başka dosyanın kilidi
        self.assertFalse(durdur.holds_lock(999, str(f), {131090}))

    def test_refuses_what_is_not_a_package_tool(self):
        # Bu test süreci (python3) bir paket aracı değil: yetki olsa da dokunulmaz.
        self.assertEqual(durdur.main(["durdur.py", str(os.getpid())]), 3)
        self.assertEqual(durdur.main(["durdur.py", "abc"]), 2)
        self.assertEqual(durdur.main(["durdur.py"]), 2)

    def test_command(self):
        old = os.environ.get("PAKET_GUNCELLEYICI_YETKI")
        try:
            os.environ["PAKET_GUNCELLEYICI_YETKI"] = "pkexec"
            cmd = apt.force_stop_command(1234)
            self.assertEqual(cmd[:4], ["pkexec", "/usr/bin/python3", "-I", str(Path(durdur.__file__))])
            self.assertEqual(cmd[-1], "1234")
            os.environ["PAKET_GUNCELLEYICI_YETKI"] = "sh -c"  # başka bir şey verilemez
            self.assertEqual(apt.force_stop_command(1)[0], "pkexec")
        finally:
            if old is None:
                os.environ.pop("PAKET_GUNCELLEYICI_YETKI", None)
            else:
                os.environ["PAKET_GUNCELLEYICI_YETKI"] = old

    def test_helper_runs_alone(self):
        """Yönetici olarak yalnızca bu dosya çalışır (python3 -I): paketin geri kalanını içe aktarmamalı."""
        import ast
        tree = ast.parse(Path(durdur.__file__).read_text())
        rel = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level > 0]
        self.assertEqual(rel, [])


if __name__ == "__main__":
    unittest.main()
