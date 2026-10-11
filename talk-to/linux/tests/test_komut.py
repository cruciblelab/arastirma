"""Bilgisayar komutları: zaman aşımında sh'nin başlattığı alt süreçler de durur."""

import asyncio
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import pc  # noqa: E402


def alive(pid: int) -> bool:
    """Ölmüş ama henüz toplanmamış (zombi) süreç çalışıyor sayılmaz (kapsayıcıda init toplamayabilir)."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return state != "Z"


class CommandTimeoutTest(unittest.TestCase):
    def test_timeout_kills_whole_group(self):
        with tempfile.TemporaryDirectory() as d:
            pidfile = Path(d) / "pid"
            custom = [{"id": "uzun", "name": "Uzun", "command": f"sleep 60 & echo $! > {pidfile}; wait"}]
            old = pc.TIMEOUT
            pc.TIMEOUT = 0.5
            started = time.monotonic()
            try:
                res = asyncio.run(pc.run_command("uzun", custom, {"commands": True}))
            finally:
                pc.TIMEOUT = old
            self.assertFalse(res["ok"])
            # Yalnızca sh öldürülseydi sleep çıkış borusunu 60 sn açık tutardı.
            self.assertLess(time.monotonic() - started, 10)
            child = int(pidfile.read_text())
            for _ in range(50):  # SIGKILL hemen işler; süreç tablosundan çıkması biraz sürebilir
                if not alive(child):
                    break
                time.sleep(0.02)
            else:
                os.kill(child, 9)
                self.fail("alt süreç (sleep) zaman aşımından sonra da çalışıyordu")


if __name__ == "__main__":
    unittest.main()
