""""Sorun bildir": GitHub'da yeni sorun sayfası, sürüm ve sistem bilgisi önceden yazılmış olarak açılır.

Hiçbir şey kendiliğinden gönderilmez: sayfa kullanıcının tarayıcısında açılır, gönderip göndermemek ona kalır.
Günlük dosyası eklenmez (kişisel bilgi içerebilir); yalnızca yeri yazılır, istersen kendin eklersin.
"""

import platform
import subprocess
import urllib.parse
from pathlib import Path

from . import __version__
from .config import cache_dir

ISSUES = "https://github.com/cruciblelab/arastirma/issues/new"


def _os_name() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def _gnome() -> str:
    try:
        out = subprocess.run(["gnome-shell", "--version"], capture_output=True, text=True, timeout=5).stdout
        return out.strip() or "-"
    except (OSError, subprocess.SubprocessError):
        return "-"


def report_url(phones: list[str] | None = None) -> str:
    body = "\n".join([
        "**Ne oldu?**", "", "", "**Ne bekliyordun?**", "", "", "**Nasıl tekrar olur?** (adım adım)", "", "",
        "---",
        f"- Talk To Android: {__version__}",
        f"- Sistem: {_os_name()}",
        f"- Masaüstü: {_gnome()}",
        f"- Telefon(lar): {', '.join(phones) if phones else 'bağlı değil'}",
        f"- Günlük (istersen ekle; kişisel bilgi içerebilir, göz at): `{cache_dir() / 'gunluk.txt'}`",
    ])
    return ISSUES + "?" + urllib.parse.urlencode({"title": "", "body": body})
