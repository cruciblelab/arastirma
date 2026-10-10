"""İlk açılış: masaüstü arayüzü için gereken GTK4 + libadwaita yoksa terminal
açtırmadan kurar.

Ubuntu'nun Uygulama Merkezi yerel .deb kurarken eksik bağımlılıkları kendisi
indirmediği için paket yalnızca python3'e bağımlıdır; geri kalanı burada,
bilgisayarın kendi şifre penceresiyle (pkexec) dağıtımın paket yöneticisinden
kurulur. Bu modül gi'yi içe aktarmaz (yoksa çalışamazdı).
"""

import os
import shutil
import subprocess
import sys

PACKAGES = {
    "apt-get": ["python3-gi", "gir1.2-gtk-4.0", "gir1.2-adw-1", "python3-cryptography"],
    "dnf": ["python3-gobject", "gtk4", "libadwaita", "python3-cryptography"],
    "pacman": ["python-gobject", "gtk4", "libadwaita", "python-cryptography"],
    "zypper": ["python3-gobject", "typelib-1_0-Gtk-4_0", "typelib-1_0-Adw-1", "python3-cryptography"],
}
INSTALL = {
    "apt-get": ["install", "-y"],
    "dnf": ["install", "-y"],
    "pacman": ["-S", "--noconfirm", "--needed"],
    "zypper": ["--non-interactive", "install"],
}

CHECK = ("import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); "
         "from gi.repository import Adw; "
         "assert (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 4), 'libadwaita 1.4+ gerekli'")


def gui_available() -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-c", CHECK], capture_output=True, text=True)
    return r.returncode == 0, (r.stderr.strip().splitlines() or [""])[-1]


def _tell(title: str, text: str, error=False):
    """Pencere kütüphanesi henüz yokken kullanıcıya haber ver (zenity, yoksa bildirim)."""
    print(f"{title}: {text}", file=sys.stderr)
    if shutil.which("zenity"):
        subprocess.run(["zenity", "--error" if error else "--info", "--title", title, "--text", text, "--width", "420"],
                       stderr=subprocess.DEVNULL)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, text], stderr=subprocess.DEVNULL)


def _ask(title: str, text: str) -> bool:
    if shutil.which("zenity"):
        return subprocess.run(["zenity", "--question", "--title", title, "--text", text, "--width", "420",
                               "--ok-label", "Kur", "--cancel-label", "Vazgeç"],
                              stderr=subprocess.DEVNULL).returncode == 0
    return True  # zenity yoksa pkexec'in şifre penceresi zaten onay yerine geçer


def ensure_gui() -> bool:
    """Arayüz çalışabilir hâldeyse True. Değilse kurmayı önerir; olmazsa açıklayıcı hata gösterir."""
    ok, why = gui_available()
    if ok:
        return True
    title = "Talk To Android"
    if "libadwaita 1.4+" in why:
        _tell(title, "Bu Linux sürümündeki libadwaita çok eski (1.4 ya da üstü gerekiyor). "
                     "Ubuntu 24.04, Debian 13, Fedora 39 ya da daha yenisi gerekli.", error=True)
        return False
    tool = next((t for t in PACKAGES if shutil.which(t)), None)
    if not tool or not shutil.which("pkexec") or not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        _tell(title, "GTK4 ve libadwaita kurulu değil. Paket yöneticinden şunları kur: "
                     + " ".join(PACKAGES.get(tool or "apt-get")), error=True)
        return False
    pkgs = PACKAGES[tool]
    if not _ask(title, "Talk To Android'in penceresi için birkaç sistem paketi gerekiyor:\n\n"
                       + ", ".join(pkgs) + "\n\nŞimdi kurulsun mu? Bilgisayarın şifresi sorulacak."):
        return False
    r = subprocess.run(["pkexec", shutil.which(tool), *INSTALL[tool], *pkgs], capture_output=True, text=True)
    if r.returncode != 0:
        msg = {126: "Kurulum iptal edildi.", 127: "Yetki verilmedi."}.get(
            r.returncode, (r.stderr or r.stdout).strip()[-400:] or f"çıkış kodu {r.returncode}")
        _tell(title, "Paketler kurulamadı: " + msg, error=True)
        return False
    ok, why = gui_available()
    if not ok:
        _tell(title, "Paketler kuruldu ama arayüz yine açılamadı: " + why, error=True)
    return ok
