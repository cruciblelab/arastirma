"""Telefonun ekranını bilgisayarda açıp fare ve klavyeyle kullanmak (scrcpy).

scrcpy telefona adb üzerinden bağlanır: USB'de doğrudan, Wi-Fi'de ise telefonun adb'si
ağdan dinlemeye alınmış olmalı (`adb tcpip 5555`; telefon USB ile takılıyken bir kez,
telefon yeniden başlayınca sıfırlanır). Telefon her yeni bilgisayarı yine kendi
"USB hata ayıklamaya izin ver" sorusuyla onaylar.
"""

import shutil
import subprocess

from .usb import _adb

TCP_PORT = 5555


def available() -> bool:
    return shutil.which("scrcpy") is not None


def install_command() -> list[str] | None:
    """Dağıtımın paket yöneticisiyle scrcpy kurma komutu; pkexec şifreyi grafik pencerede sorar."""
    if not shutil.which("pkexec"):
        return None
    for tool, cmd in (
        ("apt-get", ["apt-get", "install", "-y", "scrcpy"]),
        ("dnf", ["dnf", "install", "-y", "scrcpy"]),
        ("pacman", ["pacman", "-S", "--noconfirm", "--needed", "scrcpy"]),
        ("zypper", ["zypper", "--non-interactive", "install", "scrcpy"]),
    ):
        path = shutil.which(tool)
        if path:
            return ["pkexec", path, *cmd[1:]]
    return None


class Mirror:
    """Açık scrcpy pencereleri (aynı telefon için ikinci pencere açılmaz)."""

    def __init__(self):
        self.procs: dict[str, subprocess.Popen] = {}

    def running(self, serial: str) -> bool:
        p = self.procs.get(serial)
        return p is not None and p.poll() is None

    def start(self, serial: str, title: str) -> tuple[bool, str]:
        if not available():
            return False, "scrcpy kurulu değil"
        if self.running(serial):
            return True, "Telefonun ekranı zaten açık"
        try:
            self.procs[serial] = subprocess.Popen(
                ["scrcpy", "-s", serial, "--window-title", title, "--stay-awake"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
        except OSError as e:
            return False, f"scrcpy açılamadı: {e}"
        return True, "Telefonun ekranı açılıyor"

    def stop_all(self):
        for p in self.procs.values():
            if p.poll() is None:
                p.terminate()
        self.procs.clear()


async def enable_wireless(serial: str) -> tuple[bool, str]:
    """USB ile takılı telefonun adb'sini ağdan dinlemeye alır (telefon yeniden başlayınca kapanır)."""
    rc, out = await _adb("-s", serial, "tcpip", str(TCP_PORT), timeout=15)
    if rc != 0:
        return False, out.strip() or "adb tcpip başarısız"
    return True, "Hazır: kabloyu çıkarınca da Wi-Fi'den telefonun ekranı açılabilir"


async def connect_wireless(ip: str) -> tuple[str | None, str]:
    """Wi-Fi'deki telefonun adb'sine bağlanır; başarılıysa adb seri adı (ip:port)."""
    target = f"{ip}:{TCP_PORT}"
    rc, out = await _adb("connect", target, timeout=10)
    text = out.strip()
    if rc == 0 and ("connected to" in text or "already connected" in text):
        rc, state = await _adb("-s", target, "get-state", timeout=5)
        if rc == 0 and state.strip() == "device":
            return target, "bağlandı"
        return None, ("Telefon bu bilgisayara izin vermedi. Telefonda çıkan “USB hata ayıklamaya izin ver” "
                      "sorusunu onayla ve tekrar dene.")
    return None, ("Telefonun ekranına Wi-Fi'den ulaşılamadı. Telefonu bir kez USB ile takıp Bağlantı → USB'de "
                  "“Kablosuz ekranı hazırla”ya bas (telefon yeniden başlayınca tekrar gerekir).")
