"""Telefonun ekranını bilgisayarda açıp fare ve klavyeyle kullanmak (scrcpy).

scrcpy telefona adb üzerinden bağlanır: USB'de doğrudan, Wi-Fi'de ise telefonun adb'si
ağdan dinlemeye alınmış olmalı (`adb tcpip 5555`; telefon USB ile takılıyken bir kez,
telefon yeniden başlayınca sıfırlanır). Telefon her yeni bilgisayarı yine kendi
"USB hata ayıklamaya izin ver" sorusuyla onaylar.
"""

import asyncio
import hashlib
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from .config import cache_dir
from .usb import _adb

TCP_PORT = 5555

# Dağıtımların paketindeki scrcpy çoğu zaman çok eski (Ubuntu 22.04: 1.21) ve yeni Android sürümlerinde
# açılmıyor. Resmi Linux derlemesi yönetici izni gerekmeden kullanıcının klasörüne indirilir; indirilen
# dosya aşağıdaki SHA-256 ile doğrulanır (sürüm ve özet koda sabit: başka bir dosya kurulmaz).
SCRCPY_VERSION = "5.0.1"
SCRCPY_URL = (f"https://github.com/Genymobile/scrcpy/releases/download/v{SCRCPY_VERSION}/"
              f"scrcpy-linux-x86_64-v{SCRCPY_VERSION}.tar.gz")
SCRCPY_SHA256 = "9f969d30cc574816077edecda65719c1c70b0aee1df1ba5fa00779ac07b8fd6e"
SCRCPY_SIZE = 17_883_742
MIN_SYSTEM_VERSION = (2, 0)


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(os.environ.get("TALKTO_DATA_DIR") or Path(base) / "talk-to-android")


def managed_path() -> Path:
    return data_dir() / "scrcpy" / f"v{SCRCPY_VERSION}" / "scrcpy"


def system_version(path: str | None = None) -> tuple[int, ...] | None:
    path = path or shutil.which("scrcpy")
    if not path:
        return None
    try:
        out = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"scrcpy (\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else None


def binary() -> str | None:
    """Kullanılacak scrcpy: indirilen resmi sürüm ya da yeterince yeni sistem paketi."""
    if os.access(managed_path(), os.X_OK):
        return str(managed_path())
    v = system_version()
    return shutil.which("scrcpy") if v and v >= MIN_SYSTEM_VERSION else None


def available() -> bool:
    return binary() is not None


def outdated_system() -> tuple[int, ...] | None:
    """Sistemde kurulu ama yeni Android'lerle çalışmayan eski scrcpy sürümü (yoksa None)."""
    v = system_version()
    return v if v and v < MIN_SYSTEM_VERSION and not os.access(managed_path(), os.X_OK) else None


def can_download() -> bool:
    return platform.machine() in ("x86_64", "AMD64")


def download(progress=None, cancel=None) -> Path:
    """Resmi scrcpy'yi indirir, SHA-256'yı denetler ve açar. progress(indirilen, toplam, aşama).

    Ağ, özet ya da arşiv hatasında OSError/ValueError; cancel (threading.Event) kurulunca durur.
    """
    final = managed_path().parent
    final.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".indir-", dir=final.parent))
    try:
        archive = work / "scrcpy.tar.gz"
        h = hashlib.sha256()
        done = 0
        req = urllib.request.Request(SCRCPY_URL, headers={"User-Agent": "talk-to-android"})
        with urllib.request.urlopen(req, timeout=30) as r, open(archive, "wb") as f:
            total = int(r.headers.get("Content-Length") or SCRCPY_SIZE)
            while True:
                if cancel is not None and cancel.is_set():
                    raise InterruptedError("İndirme durduruldu")
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if done > SCRCPY_SIZE * 2:
                    raise ValueError("Beklenenden büyük dosya geldi")
                if progress:
                    progress(done, total, "indiriliyor")
        if progress:
            progress(done, done, "doğrulanıyor")
        if h.hexdigest() != SCRCPY_SHA256:
            raise ValueError("İndirilen dosya doğrulanamadı (SHA-256 tutmuyor); kurulmadı.")
        out = work / "acik"
        with tarfile.open(archive) as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(out, filter="data")
            else:  # eski Python: arşivin dışına yazan ya da bağlantı olan girdiyi kabul etme
                for m in tar.getmembers():
                    if m.name.startswith("/") or ".." in Path(m.name).parts or m.issym() or m.islnk():
                        raise ValueError("Arşivde beklenmeyen girdi")
                tar.extractall(out)
        inner = next(out.iterdir())
        if not (inner / "scrcpy").is_file():
            raise ValueError("Arşivde scrcpy yok")
        shutil.rmtree(final, ignore_errors=True)
        inner.rename(final)
        return managed_path()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def install_command() -> list[str] | None:
    """Dağıtımın paket yöneticisiyle scrcpy kurma komutu (indirme yapılamayan mimarilerde)."""
    if not shutil.which("pkexec"):
        return None
    for tool, cmd in (
        ("apt-get", ["apt-get", "-o", "DPkg::Lock::Timeout=3600", "-o", "APT::Status-Fd=1", "install", "-y", "scrcpy"]),
        ("dnf", ["dnf", "install", "-y", "scrcpy"]),
        ("pacman", ["pacman", "-S", "--noconfirm", "--needed", "scrcpy"]),
        ("zypper", ["zypper", "--non-interactive", "install", "scrcpy"]),
    ):
        path = shutil.which(tool)
        if path:
            return ["pkexec", path, *cmd[1:]]
    return None


def quality_args(serial: str) -> list[str]:
    """Görüntü kalitesi. scrcpy'nin varsayılanı (8 Mbit/s, ekranın tam çözünürlüğü, sınırsız kare) yeni
    telefonların 2,7K / 120 Hz ekranında bulanık ve takılgan çıkıyordu (~10 kare/s): telefonun kodlayıcısı o
    çözünürlükte yetişemiyor, bit hızı da yetmiyor. Kısa kenar en çok 1920 piksele indirilir, bit hızı
    artırılır, kare hızı 60'ta tutulur. Wi-Fi'de (ip:port) bant genişliği az: daha düşük.
    """
    if ":" in serial:
        return ["--video-bit-rate=6M", "--max-size=1600", "--max-fps=60"]
    return ["--video-bit-rate=16M", "--max-size=1920", "--max-fps=60"]


class Mirror:
    """Açık scrcpy pencereleri (aynı telefon için ikinci pencere açılmaz)."""

    def __init__(self):
        self.procs: dict[str, subprocess.Popen] = {}
        self.logs: dict[str, Path] = {}

    def running(self, serial: str) -> bool:
        p = self.procs.get(serial)
        return p is not None and p.poll() is None

    def start(self, serial: str, title: str) -> tuple[bool, str]:
        exe = binary()
        if not exe:
            return False, "scrcpy kurulu değil"
        if self.running(serial):
            return True, "Telefonun ekranı zaten açık"
        log = cache_dir() / f"scrcpy-{re.sub(r'[^A-Za-z0-9._-]', '_', serial)}.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "wb") as out:  # çocuk süreç kendi kopyasını tutar
                # Sistemdeki adb kullanılır: iki ayrı adb sunucusu birbirini kapatıp USB tünelini düşürmesin.
                env = dict(os.environ)
                if shutil.which("adb"):
                    env["ADB"] = shutil.which("adb")
                self.procs[serial] = subprocess.Popen(
                    [exe, "-s", serial, "--window-title", title, "--stay-awake", *quality_args(serial)], env=env,
                    stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            return False, f"scrcpy açılamadı: {e}"
        self.logs[serial] = log
        return True, "Telefonun ekranı açılıyor"

    async def start_checked(self, serial: str, title: str, wait: float = 2.5) -> tuple[bool, str]:
        """Açar ve birkaç saniye bekler: scrcpy hemen hata verip kapanırsa nedenini döndürür."""
        already = self.running(serial)
        ok, msg = self.start(serial, title)
        if not ok or already:
            return ok, msg
        p = self.procs[serial]
        for _ in range(int(wait / 0.25)):
            await asyncio.sleep(0.25)
            if p.poll() is not None:
                break
        if p.poll() in (None, 0):  # çalışıyor ya da kullanıcı pencereyi kapattı
            return True, msg
        try:
            lines = self.logs[serial].read_text(errors="replace").strip().splitlines()
        except OSError:
            lines = []
        reason = next((ln for ln in reversed(lines) if "ERROR" in ln), lines[-1] if lines else f"çıkış kodu {p.returncode}")
        return False, f"scrcpy açılamadı: {reason.strip()[:200]}"

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
    return None, ("Telefonun ekranına Wi-Fi'den ulaşılamadı. Telefonu bir kez USB ile takıp Telefonlar sayfasında ⋯ → "
                  "“Kablosuz ekranı hazırla”ya bas (telefon yeniden başlayınca tekrar gerekir).")
