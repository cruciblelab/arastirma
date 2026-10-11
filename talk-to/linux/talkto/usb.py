"""USB bağlantısı: adb ile telefona 'reverse' tüneli kurulur.

Telefondaki uygulama 127.0.0.1:47600'e bağlanır; adb bunu bilgisayardaki
127.0.0.1:47600'e taşır. Bu yüzden telefonda "USB hata ayıklama" açık olmalı
ve telefon bilgisayarın adb anahtarını bir kez onaylamalıdır.
"""

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

log = logging.getLogger("talkto.usb")
INTERVAL = 2.5
PHONE_PACKAGE = "lab.crucible.talktolinux"
PHONE_ACTIVITY = PHONE_PACKAGE + "/.ui.MainActivity"
# Bilgisayardaki "Bağlan": telefondaki uygulamayı USB tünelinden bağlanacak şekilde açar (0.9.0+). Telefonda
# yalnızca adb'nin açabildiği bir kapı (DUMP izniyle korunur); başka uygulamalar kullanamaz.
PHONE_CONNECT = PHONE_PACKAGE + "/.ui.UsbBaglan"
# Telefondaki uygulama başka anahtarla imzalı: üzerine kurulamaz, önce kaldırılmalı.
CONFLICT = ("Telefondaki Talk To Linux başka bir anahtarla imzalanmış; güncellemek için kaldırıp yeniden kurmak "
            "gerekiyor. Eşleşme ve bildirim erişimi sıfırlanır.")


# Android telefon üreticilerinin USB kimlikleri (adb'nin udev kurallarından; en yaygınları).
ANDROID_VENDORS = {
    "18d1", "04e8", "2717", "12d1", "339b", "2a70", "22b8", "22d9", "2d95", "1004", "0fce",
    "0bb4", "19d2", "17ef", "0b05", "2e04", "1ebf", "29a9", "2ae5", "1bbb", "0e8d", "2916",
    # 51-android.rules'tan diğerleri: Acer, Dell, Foxconn, Fujitsu, Hisense, Kyocera, Nvidia, Pantech,
    # Pegatron, Qualcomm, Sharp, Sony, Toshiba, Meizu, Unisoc/Spreadtrum, Rockchip, Allwinner, Essential.
    "0502", "413c", "0489", "04c5", "109b", "0482", "0955", "10a9", "1d4d", "05c6", "04dd", "054c",
    "0930", "2a45", "1782", "2207", "1f3a", "2e17",
}
XIAOMI = ("xiaomi", "redmi", "poco")
USB_ROOT = "/sys/bus/usb/devices"
# Telefon üreticileri başka aygıt da yapar (Lenovo dock, Samsung SSD, Asus klavye...): adlarından ele.
NOT_PHONE = re.compile(r"ethernet|\blan\b|dock|hub|keyboard|mouse|receiver|camera|webcam|audio|headset|speaker|"
                       r"card reader|bluetooth|fingerprint|ssd|disk|storage|monitor|display|printer", re.I)
# Telefonda olmayan arayüz sınıfları: ses, yazıcı, yığın depolama, görüntü.
NOT_PHONE_CLASSES = {"01", "07", "08", "0e"}


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
        name = " ".join(x for x in (_read(dev / "manufacturer"), _read(dev / "product")) if x)
        android = vendor in ANDROID_VENDORS
        # 06 (resim aktarımı) fotoğraf makinelerinde de var: yalnızca telefon üreticisinde ya da adı MTP ise.
        mtp = any("MTP" in label or (c == "06" and android) for c, _, _, label in ifaces)
        # Yalnızca şarj modunda telefon çoğunlukla tek bir üreticiye özel (ff) arayüz gösterir;
        # bağlantı paylaşımında e0/02/0a.
        known = android and all(c in ("ff", "06", "e0", "02", "0a") for c, _, _, _ in ifaces)
        if not adb and (NOT_PHONE.search(name) or any(c in NOT_PHONE_CLASSES for c, _, _, _ in ifaces)):
            continue
        if not (adb or mtp or known):
            continue
        phones.append({"serial": _read(dev / "serial"), "name": name or "Android telefon", "adb": adb})
    return phones


def usb_devices(root: str = USB_ROOT) -> list[str]:
    """Takılı bütün USB aygıtları "Ad (vvvv:pppp)" olarak: telefon tanınmadığında ne görüldüğünü göstermek için."""
    out = []
    base = Path(root)
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return out
    for dev in entries:
        if ":" in dev.name or not (dev / "idVendor").exists() or _read(dev / "bDeviceClass") == "09":
            continue  # 09: USB hub'ları (bilgisayarın kendi kök hub'ları dahil)
        name = " ".join(x for x in (_read(dev / "manufacturer"), _read(dev / "product")) if x) or "Adsız aygıt"
        out.append(f"{name} ({_read(dev / 'idVendor')}:{_read(dev / 'idProduct')})")
    return out


def version_tuple(v: str | None) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


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


def parse_perms(package_dump: str) -> dict:
    """`dumpsys package` çıktısından bildirim gösterme izni (Android 13+; daha eskide None)."""
    m = re.search(r"android\.permission\.POST_NOTIFICATIONS: granted=(true|false)", package_dump)
    return {"post": (m.group(1) == "true") if m else None}


def apk_version(apk: Path | None) -> str | None:
    """Paketteki telefon uygulamasının sürümü: APK'nın yanındaki .surum dosyasından (paket üretilirken yazılır)
    ya da kaynakta derlenmişse build.gradle.kts'ten. Bilinmiyorsa None (o zaman "eski" uyarısı verilmez)."""
    if not apk:
        return None
    side = apk.with_name(apk.name + ".surum")
    if side.is_file():
        return _read(side) or None
    for parent in apk.parents:
        gradle = parent / "build.gradle.kts"
        if gradle.is_file() and parent.name == "app":
            m = re.search(r'versionName\s*=\s*"([^"]+)"', _read(gradle))
            return m.group(1) if m else None
    return None


async def _adb(*args, timeout=8.0) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "adb", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except OSError as e:  # adb uygulama açıkken kaldırıldı
        return 127, f"adb çalıştırılamadı: {e.strerror or e}"
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 1, "zaman aşımı"
    return proc.returncode, out.decode("utf-8", "replace")


def parse_devices(text: str) -> dict[str, str]:
    """`adb devices` çıktısı. adb sunucusu yeni başlıyorsa önce "* daemon ..." satırları gelir."""
    lines = text.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if line.startswith("List of devices")), len(lines))
    devices = {}
    for line in lines[start:]:
        parts = line.split()
        if len(parts) >= 2 and not line.startswith("*"):
            devices[parts[0]] = parts[1]
    return devices


def is_network_serial(serial: str) -> bool:
    """Wi-Fi üzerinden adb (ip:5555 ya da mDNS ile eşleşmiş) USB sayılmaz, ona tünel kurulmaz."""
    return ":" in serial or "_adb-tls-" in serial


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
                "apk_version": apk_version(apk),
                "devices": [dict(serial=s, **d) for s, d in self.devices.items()], "unseen": list(self.unseen),
                "usb_devices": usb_devices() if self._task is not None else []}

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
        seen = {k: v for k, v in parse_devices(out).items() if not is_network_serial(k)}
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
            if state == "device" and d["tunnel"] and not await self._tunnel_alive(serial):
                # adb sunucusu yeniden başladı, telefon "adb tcpip"e geçti ya da USB modu değişti.
                log.info("adb reverse tüneli düşmüş, yeniden kuruluyor (%s)", serial)
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
                await self.details(serial, d)
                changed = True
        if changed:
            self.on_change(self.snapshot())

    async def details(self, serial: str, d: dict | None = None):
        """Kurulumda gereken ayrıntılar: üretici, Xiaomi'nin ek güvenlik anahtarları, telefondaki uygulamanın sürümü."""
        d = d or self.devices.get(serial)
        if not d or d.get("state") != "device":
            return

        async def prop(name):
            rc, out = await _adb("-s", serial, "shell", "getprop", name, timeout=5)
            return out.strip() if rc == 0 else ""
        d["maker"] = await prop("ro.product.manufacturer")
        # "2311DRK48G" yerine "POCO X6 Pro" gibi bilinen adı (yalnızca bazı üreticiler yazar).
        d["name"] = await prop("ro.product.marketname") or await prop("ro.product.vendor.marketname") or None
        if d["maker"].casefold() in XIAOMI:
            # MIUI/HyperOS: adb'nin izin vermesi ve uygulama kurması ayrı anahtarlar ister.
            d["xiaomi_permissions"] = await prop("persist.security.adbinput") == "1"
            d["xiaomi_install"] = await prop("persist.security.adbinstall") == "1"
        d["app"] = await self._app_installed(serial)
        d["app_version"] = None
        d["perms"] = {}
        if d["app"]:
            rc, out = await _adb("-s", serial, "shell", "dumpsys", "package", PHONE_PACKAGE, timeout=10)
            m = re.search(r"versionName=(\S+)", out) if rc == 0 else None
            d["app_version"] = m.group(1) if m else None
            d["perms"] = await self._perms(serial, out if rc == 0 else "")

    async def _perms(self, serial: str, package_dump: str) -> dict:
        """Telefondaki izinlerin şu anki durumu (bağlantı gerekmeden, adb'den okunur): telefonda elle verilenler
        de görünür, bilgisayar onları yeniden istemez. Değer None: okunamadı ya da bu Android'de gerekmiyor."""
        perms = parse_perms(package_dump)
        if "service.NotificationListener" not in package_dump:
            perms["listener"] = None  # hafif sürümde bildirim erişimi yok
            return perms | await self._battery(serial)
        rc, out = await _adb("-s", serial, "shell", "settings", "get", "secure", "enabled_notification_listeners",
                             timeout=5)
        perms["listener"] = (PHONE_PACKAGE + "/") in out if rc == 0 else None
        return perms | await self._battery(serial)

    @staticmethod
    async def _battery(serial: str) -> dict:
        rc, out = await _adb("-s", serial, "shell", "dumpsys", "deviceidle", "whitelist", timeout=5)
        return {"battery": PHONE_PACKAGE in out if rc == 0 else None}

    async def connect_phone(self, serial: str) -> tuple[bool, str]:
        """Bilgisayardaki "Bağlan": tüneli kurar ve telefondaki uygulamayı USB'den bağlanacak şekilde açar."""
        d = self.devices.get(serial)
        if not d or d.get("state") != "device":
            return False, "Telefon USB'de görünmüyor ya da USB hata ayıklama onaylanmadı."
        if not d.get("tunnel"):
            rc, out = await _adb("-s", serial, "reverse", f"tcp:{self.port}", f"tcp:{self.port}")
            d["tunnel"] = rc == 0
            if rc != 0:
                return False, "USB tüneli kurulamadı: " + (out.strip().splitlines() or ["adb hatası"])[-1][:200]
        rc, out = await _adb("-s", serial, "shell", "am", "start", "-n", PHONE_CONNECT, timeout=10)
        if rc != 0 or "Error" in out or "Exception" in out:
            if "does not exist" in out:
                return False, "Telefondaki Talk To Linux bilgisayardan bağlanmayı bilmiyor (eski sürüm); önce güncelle."
            if "Permission Denial" in out or "SecurityException" in out:
                return False, ("Telefon bu bilgisayarın uygulamayı açmasına izin vermedi. Telefonda Talk To Linux'u "
                               "açıp “USB kablosu”na dokun.")
            return False, (out.strip().splitlines() or ["adb hatası"])[-1][:200]
        return True, "Telefonda Talk To Linux açıldı, bağlanıyor…"

    async def refresh(self):
        """Telefondaki ayarlar değişmiş olabilir: ayrıntılar yeniden okunur, değiştiyse bildirilir."""
        before = repr(self.devices)
        for serial in list(self.devices):
            await self.details(serial)
        if repr(self.devices) != before:
            self.on_change(self.snapshot())

    async def _tunnel_alive(self, serial: str) -> bool:
        rc, out = await _adb("-s", serial, "reverse", "--list", timeout=4)
        # Komut başarısızsa (eski adb, kısa kopma) tüneli yıkıp yeniden kurmak yerine bir sonraki yoklamayı bekle.
        return rc != 0 or f"tcp:{self.port}" in out

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
        if d.get("installing"):
            return False, "Kurulum zaten sürüyor; telefonda bitmesini bekle."
        d["installing"] = True
        self.on_change(self.snapshot())
        try:
            if replace:
                await _adb("-s", serial, "uninstall", PHONE_PACKAGE, timeout=60)
            rc, out = await _adb("-s", serial, "install", "-r", str(apk), timeout=180)
            if rc != 0 or "Success" not in out:
                if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out:
                    return False, CONFLICT
                if "INSTALL_FAILED_USER_RESTRICTED" in out or "INSTALL_FAILED_ABORTED" in out:
                    return False, ("Telefon USB'den kurulumu engelledi. Geliştirici seçeneklerinde "
                                   "“USB üzerinden yükle” (Xiaomi) gibi bir ayarı aç ve telefondaki soruyu onayla.")
                return False, out.strip().splitlines()[-1] if out.strip() else f"adb hata kodu {rc}"
            d["app"] = True
            await self.details(serial, d)
            # Yeni sürüm bilgisayardan bağlanmayı bilir: açılır ve USB'den bağlanır; eskisi yalnızca açılır.
            ok, _ = await self.connect_phone(serial)
            if not ok:
                await _adb("-s", serial, "shell", "am", "start", "-n", PHONE_ACTIVITY)
            return True, ("Talk To Linux telefona kuruldu ve bağlanıyor…" if ok else
                          "Talk To Linux telefona kuruldu ve açıldı.")
        finally:
            d["installing"] = False
            self.on_change(self.snapshot())
