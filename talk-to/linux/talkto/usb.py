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
# Telefondaki uygulama başka anahtarla imzalı: üzerine kurulamaz, önce kaldırılmalı.
CONFLICT = ("Telefondaki Talk To Linux başka bir anahtarla imzalanmış; güncellemek için kaldırıp yeniden kurmak "
            "gerekiyor. Eşleşme ve bildirim erişimi sıfırlanır.")


# Android telefon üreticilerinin USB kimlikleri (adb'nin udev kurallarından; en yaygınları).
ANDROID_VENDORS = {
    "18d1", "04e8", "2717", "12d1", "339b", "2a70", "22b8", "22d9", "2d95", "1004", "0fce",
    "0bb4", "19d2", "17ef", "0b05", "2e04", "1ebf", "29a9", "2ae5", "1bbb", "0e8d", "2916",
}
USB_ROOT = "/sys/bus/usb/devices"


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def usb_phones(root: str = USB_ROOT) -> list[dict]:
    """Kabloyla takılı Android telefonlar (adb'den bağımsız, sysfs'ten).

    adb yalnızca USB hata ayıklama açık telefonları görür; bu liste, takılı olup
    adb'nin göremediği telefonu fark edip kullanıcıya ne yapacağını söylemek için.
    """
    phones = []
    base = Path(root)
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return phones
    for dev in entries:
        if ":" in dev.name or not (dev / "idVendor").exists():
            continue
        vendor = _read(dev / "idVendor").lower()
        ifaces = []
        for itf in base.glob(dev.name + ":*"):
            ifaces.append((_read(itf / "bInterfaceClass").lower(), _read(itf / "bInterfaceSubClass").lower(),
                           _read(itf / "bInterfaceProtocol").lower(), _read(itf / "interface")))
        adb = any(c == "ff" and sc == "42" and pr == "01" for c, sc, pr, _ in ifaces)
        mtp = any("MTP" in name or c == "06" for c, _, _, name in ifaces)
        known = vendor in ANDROID_VENDORS and not all(c in ("03", "09") for c, _, _, _ in ifaces)
        if not (adb or mtp or known):
            continue
        name = " ".join(x for x in (_read(dev / "manufacturer"), _read(dev / "product")) if x)
        phones.append({"serial": _read(dev / "serial"), "name": name or "Android telefon", "adb": adb})
    return phones


def find_apk() -> Path | None:
    """Telefona kurulacak Talk To Linux APK'sı: paketle gelen, kur.sh'nin kopyaladığı ya da kaynakta derlenen."""
    here = Path(__file__).resolve().parent
    candidates = [os.environ.get("TALKTO_APK"),
                  "/usr/share/talk-to-android/talk-to-linux.apk",
                  str(here.parent / "talk-to-linux.apk"),
                  str(here.parents[1] / "android/app/build/outputs/apk/tam/release/app-tam-release.apk")]
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
        self.unseen: list[dict] = []  # takılı ama adb'nin göremediği telefonlar
        self._task = None

    @staticmethod
    def available() -> bool:
        return shutil.which("adb") is not None

    def snapshot(self) -> dict:
        apk = find_apk()
        return {"adb": self.available(), "running": self._task is not None, "apk": str(apk) if apk else None,
                "devices": [dict(serial=s, **d) for s, d in self.devices.items()], "unseen": list(self.unseen)}

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
        self.unseen = []
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
            unseen = [p for p in usb_phones()
                      if not (p["serial"] in self.devices or (not p["serial"] and self.devices))]
            if unseen != self.unseen:
                self.unseen = unseen
                self.on_change(self.snapshot())
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

    async def install_app(self, serial: str, replace: bool = False) -> tuple[bool, str]:
        """Telefona Talk To Linux'u USB üzerinden kurar (ya da günceller) ve açar.

        Play Protect'in internetten yüklenen uygulamalara uyguladığı engel adb ile
        kurulumda geçerli değildir. replace: imza farklıysa önce kaldır (CONFLICT dönünce
        kullanıcıya sorulup tekrar çağrılır).
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
            if replace:
                await _adb("-s", serial, "uninstall", PHONE_PACKAGE, timeout=60)
            rc, out = await _adb("-s", serial, "install", "-r", str(apk), timeout=180)
            if rc != 0 or "Success" not in out:
                if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out:
                    return False, CONFLICT
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
