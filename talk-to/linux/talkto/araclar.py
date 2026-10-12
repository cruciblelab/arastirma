"""Geliştirici araçları: USB'deki telefonda adb ile yapılan işler (Tercihler → Araçlar).

Telefonun normal ayarlarından yapılamayanlar ya da zahmetli olanlar: uygulamayı zorla durdurmak, verisini silmek,
sistem uygulamasını bu kullanıcı için kaldırmak (geri yüklenebilir), silinmeyen dosyaları (ör. Android/data)
silmek, kayıt almak, kurtarma moduna başlatmak. Hepsi adb'nin "shell" kullanıcısıyla çalışır: root gerekmez,
telefona kalıcı zarar veremez; sistem uygulaması kaldırmak bile yalnızca bu kullanıcı için gizler.

Güvenlik sınırları:
- Paket adları ve yollar doğrulanır; uzak kabuğa giden her değer tırnaklanır (shlex.quote).
- Dosya silme yalnızca paylaşılan depolamada (/sdcard, /storage/emulated/0): sistem bölümleri gezilebilir ama
  silinemez.
"""

import asyncio
import posixpath
import re
import shlex
from dataclasses import dataclass

from .usb import _adb

PACKAGE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
SHARED = ("/sdcard", "/storage/emulated/0")
REBOOT_MODES = {"": "Normal", "recovery": "Kurtarma (recovery)", "bootloader": "Önyükleyici (bootloader / fastboot)"}
# toybox `ls -la`: izinler, bağ, sahip, grup, boyut, tarih, saat, ad
_LS = re.compile(r"^([dlcbps-][rwxsStT-]{9})\S*\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\d{4}-\d\d-\d\d)\s+(\d\d:\d\d)\s+(.+)$")


def valid_package(name: str) -> bool:
    return bool(PACKAGE.match(name or "")) and len(name) <= 255


def deletable(path: str) -> bool:
    """Yalnızca paylaşılan depolamanın içindekiler (kökün kendisi değil)."""
    p = posixpath.normpath(path or "/")
    return any(p.startswith(root + "/") for root in SHARED)


def parse_packages(text: str) -> set[str]:
    return {line[8:].strip() for line in text.splitlines() if line.startswith("package:") and line[8:].strip()}


@dataclass
class Paket:
    name: str
    system: bool
    enabled: bool
    installed: bool  # bu kullanıcı için kurulu (kaldırılmış sistem uygulamasında False)


@dataclass
class Girdi:
    name: str
    is_dir: bool
    size: int
    when: str
    link: bool = False


def parse_ls(text: str) -> list[Girdi]:
    out = []
    for line in text.splitlines():
        m = _LS.match(line.strip())
        if not m:
            continue
        perms, size, day, clock, name = m.groups()
        link = perms[0] == "l"
        if link and " -> " in name:
            name = name.split(" -> ", 1)[0]
        if name in (".", ".."):
            continue
        out.append(Girdi(name, perms[0] == "d", int(size), f"{day} {clock}", link))
    return sorted(out, key=lambda g: (not g.is_dir, g.name.casefold()))


async def shell(serial: str, command: str, timeout: float = 30) -> tuple[int, str]:
    return await _adb("-s", serial, "shell", command, timeout=timeout)


async def packages(serial: str) -> list[Paket]:
    """Kurulu uygulamalar; bu kullanıcı için kaldırılmış sistem uygulamaları da (geri yüklemek için)."""
    # "-s -u": bu kullanıcı için kaldırılmış olanlar dahil bütün sistem paketleri (yalnız "-s" onları göstermez).
    results = await asyncio.gather(*(shell(serial, f"pm list packages {flag}")
                                     for flag in ("", "-s -u", "-d", "-u")))
    if any(rc != 0 for rc, _ in results):
        rc, out = next(r for r in results if r[0] != 0)
        raise RuntimeError(out.strip() or f"pm çıkış kodu {rc}")
    installed, system, disabled, every = (parse_packages(out) for _, out in results)
    names = installed | (every & system)
    return sorted((Paket(n, n in system, n not in disabled, n in installed) for n in names),
                  key=lambda p: (p.system, p.name))


APP_ACTIONS = {
    "stop": ("Zorla durdur", "am force-stop {p}"),
    "clear": ("Verilerini sil", "pm clear {p}"),
    "disable": ("Devre dışı bırak", "pm disable-user --user 0 {p}"),
    "enable": ("Etkinleştir", "pm enable {p}"),
    "uninstall": ("Kaldır (bu kullanıcı için)", "pm uninstall -k --user 0 {p}"),
    "restore": ("Geri yükle", "cmd package install-existing {p}"),
}


async def app_action(serial: str, package: str, action: str) -> tuple[bool, str]:
    if not valid_package(package) or action not in APP_ACTIONS:
        return False, "geçersiz istek"
    rc, out = await shell(serial, APP_ACTIONS[action][1].format(p=shlex.quote(package)))
    text = out.strip()
    ok = rc == 0 and not re.search(r"Failure|Exception|Error|not allowed|failed", text, re.I)
    return ok, text


async def list_dir(serial: str, path: str) -> list[Girdi]:
    rc, out = await shell(serial, f"ls -la {shlex.quote(posixpath.normpath(path))}/")
    if rc != 0 and not out.strip():
        raise RuntimeError(f"ls çıkış kodu {rc}")
    entries = parse_ls(out)
    if not entries and rc != 0:
        raise RuntimeError(out.strip().splitlines()[-1] if out.strip() else "okunamadı")
    return entries


async def delete(serial: str, path: str) -> tuple[bool, str]:
    if not deletable(path):
        return False, "Yalnızca telefonun paylaşılan depolamasındaki (/sdcard) dosyalar silinebilir."
    rc, out = await shell(serial, f"rm -rf -- {shlex.quote(posixpath.normpath(path))}", timeout=120)
    return rc == 0 and not out.strip(), out.strip()


async def pull(serial: str, path: str, dest: str) -> tuple[bool, str]:
    rc, out = await _adb("-s", serial, "pull", "-a", posixpath.normpath(path), dest, timeout=3600)
    return rc == 0, out.strip().splitlines()[-1] if out.strip() else ""


async def reboot(serial: str, mode: str) -> tuple[bool, str]:
    if mode not in REBOOT_MODES:
        return False, "geçersiz kip"
    rc, out = await _adb("-s", serial, "reboot", *([mode] if mode else []), timeout=20)
    return rc == 0, out.strip()


async def logcat(serial: str, dest: str) -> tuple[bool, str]:
    """Telefonun sistem kaydının (logcat) şu ana kadarki hâlini dosyaya yazar."""
    rc, out = await _adb("-s", serial, "logcat", "-d", "-v", "threadtime", timeout=120)
    if rc != 0:
        return False, out.strip()[-300:]
    with open(dest, "w", encoding="utf-8") as f:
        f.write(out)
    return True, dest


async def animations(serial: str, on: bool) -> tuple[bool, str]:
    """Geliştirici seçeneklerindeki üç animasyon ölçeği: kapalı (0) telefonu daha çevik gösterir."""
    v = "1" if on else "0"
    rc, out = await shell(serial, "; ".join(f"settings put global {k} {v}" for k in
                                            ("window_animation_scale", "transition_animation_scale",
                                             "animator_duration_scale")))
    return rc == 0, out.strip()


async def animations_on(serial: str) -> bool | None:
    rc, out = await shell(serial, "settings get global animator_duration_scale")
    if rc != 0:
        return None
    return out.strip() not in ("0", "0.0")


def terminal_command(serial: str) -> list[str] | None:
    """Telefonun kabuğunu (adb shell) bir terminal penceresinde açan komut."""
    import shutil
    adb = shutil.which("adb") or "adb"
    for term, args in (("gnome-terminal", ["--"]), ("kgx", ["--"]), ("konsole", ["-e"]), ("xfce4-terminal", ["-x"]),
                       ("x-terminal-emulator", ["-e"]), ("xterm", ["-e"])):
        if shutil.which(term):
            return [term, *args, adb, "-s", serial, "shell"]
    return None
