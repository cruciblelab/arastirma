"""USB bağlantısı: adb ile telefona 'reverse' tüneli kurulur.

Telefondaki uygulama 127.0.0.1:47600'e bağlanır; adb bunu bilgisayardaki
127.0.0.1:47600'e taşır. Bu yüzden telefonda "USB hata ayıklama" açık olmalı
ve telefon bilgisayarın adb anahtarını bir kez onaylamalıdır.
"""

import asyncio
import logging
import shutil

log = logging.getLogger("talkto.usb")
INTERVAL = 2.5


async def _adb(*args, timeout=8.0) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        "adb", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 1, "zaman aşımı"
    return proc.returncode, out.decode("utf-8", "replace")


def parse_devices(text: str) -> dict[str, str]:
    devices = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            devices[parts[0]] = parts[1]
    return devices


class AdbWatcher:
    """Bağlanan her telefona tünel kurar; durumu on_change ile bildirir."""

    def __init__(self, port: int, on_change):
        self.port = port
        self.on_change = on_change
        self.devices: dict[str, dict] = {}
        self._task = None

    @staticmethod
    def available() -> bool:
        return shutil.which("adb") is not None

    def snapshot(self) -> dict:
        return {"adb": self.available(), "running": self._task is not None,
                "devices": [dict(serial=s, **d) for s, d in self.devices.items()]}

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._loop())
            self.on_change(self.snapshot())

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None
        for serial, d in list(self.devices.items()):
            if d.get("tunnel"):
                await _adb("-s", serial, "reverse", "--remove", f"tcp:{self.port}", timeout=4)
        self.devices.clear()
        self.on_change(self.snapshot())

    async def _loop(self):
        had_adb = self.available()
        while True:
            if self.available() != had_adb:  # adb sonradan kuruldu ya da kaldırıldı
                had_adb = not had_adb
                self.on_change(self.snapshot())
            if self.available():
                try:
                    await self._poll()
                except Exception:
                    log.exception("adb yoklaması başarısız")
            await asyncio.sleep(INTERVAL)

    async def _poll(self):
        rc, out = await _adb("devices")
        if rc != 0:
            return
        seen = parse_devices(out)
        changed = False
        for serial in list(self.devices):
            if serial not in seen:
                del self.devices[serial]
                changed = True
        for serial, state in seen.items():
            d = self.devices.setdefault(serial, {"state": None, "tunnel": False, "model": serial})
            if d["state"] != state:
                d["state"] = state
                d["tunnel"] = False
                changed = True
            if state == "device" and not d["tunnel"]:
                rc, out = await _adb("-s", serial, "reverse", f"tcp:{self.port}", f"tcp:{self.port}")
                d["tunnel"] = rc == 0
                if rc != 0:
                    log.warning("adb reverse başarısız (%s): %s", serial, out.strip())
                rc, model = await _adb("-s", serial, "shell", "getprop", "ro.product.model")
                if rc == 0 and model.strip():
                    d["model"] = model.strip()
                changed = True
        if changed:
            self.on_change(self.snapshot())
