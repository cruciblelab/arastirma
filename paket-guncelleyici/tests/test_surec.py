"""Uygulamanın süreçlerini bulma ve "Durmaya zorla": sahte /proc ile eşleşme kuralları, gerçek süreçle durdurma."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from guncelleyici import surec  # noqa: E402

FILES = {"/usr/bin/talk-to-android", "/usr/lib/talk-to-android/talkto/__main__.py", "/opt/Foo/foo",
         "/usr/bin/foo-launcher"}


def fake_proc(procs):
    """procs: [(pid, exe, argv, durum)]: bu kullanıcının süreçleri gibi."""
    d = Path(tempfile.mkdtemp())
    for pid, exe, argv, state in procs:
        p = d / str(pid)
        p.mkdir()
        if exe:
            os.symlink(exe, p / "exe")
        (p / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        (p / "stat").write_text(f"{pid} ({os.path.basename(argv[0])[:15]}) {state} 1 1")
    return str(d)


class FindTest(unittest.TestCase):
    def test_rules(self):
        proc = fake_proc([
            (10, "/opt/Foo/foo", ["/opt/Foo/foo", "--type=renderer"], "S"),            # programı paketin
            (11, "/opt/Foo/foo (deleted)", ["/opt/Foo/foo"], "S"),                      # güncellemeden sonra
            (12, "/usr/bin/python3.12", ["python3", "-m", "talkto", "--gizli"], "S"),   # -m modül
            (13, "/usr/bin/dash", ["/bin/sh", "/usr/bin/foo-launcher"], "S"),           # betik
            (14, "/usr/bin/python3.12", ["python3", "-m", "http.server"], "S"),         # başka modül
            (15, "/usr/bin/bash", ["bash"], "S"),                                       # ilgisiz
            (16, "/opt/Foo/foo", ["/opt/Foo/foo"], "Z"),                                # bitmiş
            (17, "/opt/Bar/bar", ["bar"], "S"),                                         # komut adıyla
        ])
        self.assertEqual(surec.find("x", "bar", files=FILES, proc=proc, me=1), [10, 11, 12, 13, 17])
        self.assertEqual(surec.find("x", "python3", files=FILES, proc=proc, me=1), [10, 11, 12, 13])  # genel ad
        self.assertEqual(surec.find("x", None, files=FILES, proc=proc, me=12), [10, 11, 13])  # kendisi hariç

    def test_other_users_are_never_matched(self):
        proc = fake_proc([(10, "/opt/Foo/foo", ["/opt/Foo/foo"], "S")])
        self.assertEqual(surec.find("x", None, files=FILES, proc=proc, uid=os.getuid() + 1, me=1), [])

    def test_stop_real_processes(self):
        """Gerçek süreç: kibarca kapanan ve SIGTERM'i yok sayan (zorla kapatılır)."""
        polite = subprocess.Popen(["sleep", "60"])
        stubborn = subprocess.Popen([sys.executable, "-c", "import signal,time;signal.signal(signal.SIGTERM,"
                                     "signal.SIG_IGN);print('hazir',flush=True);time.sleep(60)"],
                                    stdout=subprocess.PIPE, text=True)
        stubborn.stdout.readline()
        try:
            left = surec.stop([polite.pid, stubborn.pid], grace=0.5)
            polite.wait(5)
            stubborn.wait(5)
        finally:
            for p in (polite, stubborn):
                if p.poll() is None:
                    p.kill()
        self.assertEqual(left, [])
        self.assertLess(stubborn.returncode, 0)  # zorla (SIGKILL)

    def test_finds_a_real_running_script(self):
        """Gerçek süreç, paket dosyası gibi verilen bir betikten çalışıyor."""
        d = Path(tempfile.mkdtemp())
        script = d / "uyg"
        script.write_text("#!/bin/sh\nsleep 60\n")
        script.chmod(0o755)
        p = subprocess.Popen(["/bin/sh", str(script)])
        try:
            self.assertIn(p.pid, surec.find("x", None, files={str(script)}))
            self.assertEqual(surec.stop([p.pid], grace=1), [])
        finally:
            if p.poll() is None:
                p.kill()
            p.wait()


if __name__ == "__main__":
    unittest.main()
