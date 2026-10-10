"""USB bağlantısı: adb ile telefona 'reverse' tüneli kurulur.

Telefondaki uygulama 127.0.0.1:47600'e bağlanır; adb bunu bilgisayardaki
127.0.0.1:47600'e taşır. Bu yüzden telefonda "USB hata ayıklama" açık olmalı
ve telefon bilgisayarın adb anahtarını bir kez onaylamalıdır.
"""

import asyncio
import logging
import os
import shutil
from pathlib import Path

log = logging.getLogger("talkto.usb")
INTERVAL = 2.5
PHONE_PACKAGE = "lab.crucible.talktolinux"
PHONE_ACTIVITY = PHONE_PACKAGE + "/.ui.MainActivity"


def find_apk() -> Path | None:
    """Telefona kurulacak Talk To Linux APK'sı: paketle gelen, kur.sh'nin kopyaladığı ya da kaynakta derlenen."""
    here = Path(__file__).resolve().parent
    candidates = [os.environ.get("TALKTO_APK"),
                  "/usr/share/talk-to-android/talk-to-linux.apk",
                  str(here.parent / "talk-to-linux.apk"),
                  str(here.parents[1] / "android/app/build/outputs/apk/release/app-release.apk")]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return None


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
        apk = find_apk()
        return {"adb": self.available(), "running": self._task is not None, "apk": str(apk) if apk else None,
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
            d = self.devices.setdefault(serial, {"state": None, "tunnel": False, "model": serial,
                                                 "app": None, "installing": False})
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
                d["app"] = await self._app_installed(serial)
                changed = True
        if changed:
            self.on_change(self.snapshot())

    async def _app_installed(self, serial: str) -> bool:
        rc, out = await _adb("-s", serial, "shell", "pm", "path", PHONE_PACKAGE)
        return rc == 0 and "package:" in out

    async def install_app(self, serial: str) -> tuple[bool, str]:
        """Telefona Talk To Linux'u USB üzerinden kurar (ya da günceller) ve açar.

        Play Protect'in internetten yüklenen uygulamalara uyguladığı engel adb ile
        kurulumda geçerli değildir.
        """
        apk = find_apk()
        d = self.devices.get(serial)
        if not apk:
            return False, "Kurulacak APK bulunamadı."
        if not d or d.get("state") != "device":
            return False, "Telefon USB ile bağlı değil ya da USB hata ayıklama onaylanmadı."
        d["installing"] = True
        self.on_change(self.snapshot())
        try:
            rc, out = await _adb("-s", serial, "install", "-r", str(apk), timeout=180)
            if rc != 0 or "Success" not in out:
                if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out:
                    return False, ("Telefondaki Talk To Linux başka bir anahtarla imzalanmış. "
                                   "Telefonda onu kaldırıp tekrar dene.")
                if "INSTALL_FAILED_USER_RESTRICTED" in out:
                    return False, ("Telefon USB'den kurulumu engelledi. Geliştirici seçeneklerinde "
                                   "“USB üzerinden yükle” (Xiaomi) gibi bir ayarı aç ve telefondaki soruyu onayla.")
                return False, out.strip().splitlines()[-1] if out.strip() else f"adb hata kodu {rc}"
            d["app"] = True
            await _adb("-s", serial, "shell", "am", "start", "-n", PHONE_ACTIVITY)
            return True, "Talk To Linux telefona kuruldu ve açıldı."
        finally:
            d["installing"] = False
            self.on_change(self.snapshot())
