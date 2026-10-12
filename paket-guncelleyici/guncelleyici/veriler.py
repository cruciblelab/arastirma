"""Uygulamanın ev klasöründeki verileri: önbellek, ayarlar, kayıtlı veriler (bul, boyutunu söyle, çöpe taşı).

Paket yöneticisi yalnızca sistem dosyalarını bilir; bir uygulamanın kişisel verisi kullanıcının ev klasöründe,
XDG klasörlerinde durur (~/.cache, ~/.config, ~/.local/share, ~/.local/state). Hangi klasörün hangi uygulamaya
ait olduğunu tutan bir kayıt yok: klasör adı çoğunlukla uygulamanın paket adı, masaüstü kimliği, çalıştırdığı
komut ya da adıdır. Burada yalnızca **tam ad eşleşmesi** sayılır (benzer adlı başka uygulamanın klasörü
önerilmesin) ve ortak klasörler (gtk-3.0, autostart, dconf…) hiç önerilmez. Yine de yanlış eşleşme olabilir:
bu yüzden hiçbir şey kalıcı silinmez, çöp kutusuna taşınır; çöp kutusu kullanılamazsa dokunulmaz.
"""

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from .dil import N_, _t

ROOTS = (("onbellek", ".cache"), ("ayar", ".config"), ("veri", ".local/share"), ("veri", ".local/state"))
KIND_NAMES = {"onbellek": N_("Önbellek"), "ayar": N_("Ayarlar"), "veri": N_("Kayıtlı veriler")}


def kind_name(kind: str) -> str:
    return _t(KIND_NAMES[kind])
# Birden çok uygulamanın ya da masaüstünün ortak klasörleri: adı tutsa bile önerilmez.
SHARED = {
    "gtk-2.0", "gtk-3.0", "gtk-4.0", "autostart", "applications", "icons", "fonts", "fontconfig", "mime", "menus",
    "dconf", "pulse", "pipewire", "wireplumber", "systemd", "keyrings", "trash", "thumbnails", "gvfs-metadata",
    "tracker3", "goa-1.0", "ibus", "user-dirs.dirs", "user-dirs.locale", "mimeapps.list", "recently-used.xbel",
    "gnome-session", "session", "sounds", "themes", "flatpak", "snap", "xdg-desktop-portal", "nautilus-python",
    "update-notifier", "ubuntu-advantage", "evolution", "gnome-shell", "mesa_shader_cache", "fontconfig",
}
APT_ARCHIVES = Path("/var/cache/apt/archives")


@dataclass
class Klasor:
    path: Path
    kind: str  # onbellek / ayar / veri
    size: int

    @property
    def label(self) -> str:
        return kind_name(self.kind)


def size_of(path: Path) -> int:
    total = 0
    try:
        if path.is_symlink() or path.is_file():
            return path.lstat().st_size
    except OSError:
        return 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def exec_name(desktop_path: str) -> str | None:
    """Masaüstü dosyasındaki komutun adı (Exec=/usr/bin/foo --x %U → foo; env VAR=1 foo → foo)."""
    try:
        text = Path(desktop_path).read_text(errors="replace")
    except OSError:
        return None
    in_entry = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
        elif in_entry and line.startswith("Exec="):
            try:
                parts = shlex.split(line[5:])
            except ValueError:
                parts = line[5:].split()
            while parts and (parts[0] == "env" or ("=" in parts[0] and not parts[0].startswith("/"))):
                parts.pop(0)
            return os.path.basename(parts[0]) if parts else None
    return None


def keys(package: str, desktop_id: str, exe: str | None, name: str) -> set[str]:
    """Uygulamanın klasör adı olabilecek adları (küçük harfle)."""
    did = desktop_id.removesuffix(".desktop")
    out = {package, did, exe or "", name, name.replace(" ", ""), name.replace(" ", "-"), name.replace(" ", "_")}
    if did.count(".") >= 2:  # org.gnome.Calculator → Calculator
        out.add(did.rsplit(".", 1)[1])
    return {k.casefold() for k in out if k and len(k) >= 3 and k.casefold() not in SHARED}


def find(package: str, desktop_id: str, name: str, home: Path | None = None,
         desktop_dir: str = "/usr/share/applications") -> list[Klasor]:
    home = home or Path.home()
    want = keys(package, desktop_id, exec_name(os.path.join(desktop_dir, desktop_id)), name)
    found = []
    for kind, rel in ROOTS:
        base = home / rel
        try:
            entries = sorted(base.iterdir())
        except OSError:
            continue
        for p in entries:
            if p.name.casefold() in want and p.is_dir() and not p.is_symlink():
                found.append(Klasor(p, kind, size_of(p)))
    return found


def running(package: str, desktop_id: str, desktop_dir: str = "/usr/share/applications") -> bool:
    """Uygulama şu an açık mı (açıkken ayarlarını silmek yarım kalır: kapanırken yeniden yazabilir)."""
    from . import surec
    return bool(surec.find(package, exec_name(os.path.join(desktop_dir, desktop_id))))


def trash(paths: list[Path]) -> tuple[list[Path], list[str]]:
    """Çöp kutusuna taşır; taşınamayana dokunmaz. (taşınanlar, hatalar)"""
    from gi.repository import Gio, GLib
    moved, errors = [], []
    for p in paths:
        try:
            Gio.File.new_for_path(str(p)).trash(None)
            moved.append(p)
        except GLib.Error as e:
            errors.append(f"{p}: {e.message}")
    return moved, errors


def apt_cache_size(archives: Path = APT_ARCHIVES) -> int:
    """apt'nin indirip sakladığı paket dosyaları (kurulduktan sonra gerekmez; "apt-get clean" siler)."""
    try:
        return sum(p.stat().st_size for p in archives.glob("*.deb"))
    except OSError:
        return 0
