"""Uygulama güncellenince (apt, Paket Güncelleyici, Yazılım Güncelleştirici) kendini yeni sürümle başlatır.

Talk To pencere kapansa da arka planda çalışır; paket güncellenince diskteki dosyalar yenilenir ama
bellekteki eski sürüm çalışmaya devam ederdi ("Hakkında" eski sürümü gösterirdi). Kendi sürüm dosyası
izlenir; değişince sürüm okunur, farklıysa (ve sürmekte olan bir dosya aktarımı yoksa) uygulama temiz
kapanıp aynı komutla yeniden başlar. Telefon birkaç saniye içinde kendiliğinden yeniden bağlanır.
"""

import re
from pathlib import Path

_VERSION = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.M)


def version_in(path: Path) -> str | None:
    """Sürüm dosyasındaki __version__ (dosya yoksa ya da yarım yazılmışsa None)."""
    try:
        m = _VERSION.search(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    return m.group(1) if m else None


def restart_argv(argv: list[str], window_visible: bool) -> list[str]:
    """Yeniden başlatma komutu: pencere açıksa açık, kapalıysa arka planda başlasın."""
    args = [a for a in argv[1:] if a != "--arka-planda"]
    if not window_visible:
        args.append("--arka-planda")
    return args
