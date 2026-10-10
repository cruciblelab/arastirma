"""Terminal açmadan yapılan sistem işleri: otomatik başlatma ve adb kurulumu."""

import os
import shlex
import shutil
import sys
from pathlib import Path

from .. import APP_ID


def _autostart_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / f"{APP_ID}.desktop"


def launcher() -> str:
    """Uygulamayı yeniden başlatacak komut (paket, kur.sh ya da kaynak klasörü)."""
    exe = shutil.which("talk-to-android")
    if exe:
        return shlex.quote(exe)
    pkg_parent = Path(__file__).resolve().parents[2]
    return f"env PYTHONPATH={shlex.quote(str(pkg_parent))} {shlex.quote(sys.executable)} -m talkto"


def autostart_enabled() -> bool:
    return _autostart_file().exists()


def set_autostart(on: bool):
    f = _autostart_file()
    if not on:
        f.unlink(missing_ok=True)
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "[Desktop Entry]\nType=Application\nName=Talk To Android\n"
        "Comment=Telefon bağlantısı arka planda\n"
        f"Exec={launcher()} --arka-planda\nIcon={APP_ID}\nTerminal=false\n"
        "X-GNOME-Autostart-enabled=true\n", encoding="utf-8")


def adb_install_command() -> list[str] | None:
    """Dağıtımın paket yöneticisiyle adb kurma komutu; pkexec şifreyi grafik pencerede sorar."""
    if not shutil.which("pkexec"):
        return None
    for tool, cmd in (
        ("apt-get", ["apt-get", "install", "-y", "adb"]),
        ("dnf", ["dnf", "install", "-y", "android-tools"]),
        ("pacman", ["pacman", "-S", "--noconfirm", "--needed", "android-tools"]),
        ("zypper", ["zypper", "--non-interactive", "install", "android-tools"]),
    ):
        path = shutil.which(tool)
        if path:
            return ["pkexec", path, *cmd[1:]]
    return None
