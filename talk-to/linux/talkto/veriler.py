"""Uygulamanın kendi verileri: önbelleği temizlemek, indirilen scrcpy'yi silmek, uygulamayı sıfırlamak.

- Önbellek (~/.cache/talk-to-android): albüm kapakları, uygulama simgeleri, ekran görüntüleri, eski günlükler.
  Değeri yok, kalıcı silinir. Açık günlük dosyaları (gunluk.txt, cokme.txt) kalır: süreç onlara yazıyor.
- İndirilen scrcpy (~/.local/share/talk-to-android/scrcpy): gerekince yeniden indirilir, kalıcı silinir.
- Sıfırlama (~/.config/talk-to-android): eşleşmeler, profiller, komutlar, ayarlar; istenirse bu bilgisayarın
  kimliği (sertifika). Bunlar kalıcı silinmez, çöp kutusuna taşınır (yanlışlıkla sıfırlanırsa geri alınır);
  çöp kutusu kullanılamazsa yanına tarihli bir yedek klasörüne taşınır. Telefondan alınan dosyalar
  (İndirilenler/TalkToAndroid) ve güvenlik duvarı izni olduğu gibi kalır.
"""

import logging
import os
import shutil
import time
from pathlib import Path

from .config import cache_dir, config_dir

log = logging.getLogger("talkto.veriler")

KEEP_IN_CACHE = {"gunluk.txt", "cokme.txt"}
SETTINGS = ("ayarlar.json",)
IDENTITY = ("sertifika.pem", "anahtar.pem")


def size_of(path: Path) -> int:
    """Klasörün (ya da dosyanın) toplam boyutu; bağlantılar izlenmez."""
    try:
        if path.is_symlink() or path.is_file():
            return path.lstat().st_size
    except OSError:
        return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def cache_entries(base: Path | None = None) -> list[Path]:
    base = base or cache_dir()
    try:
        return sorted(p for p in base.iterdir() if p.name not in KEEP_IN_CACHE)
    except OSError:
        return []


def cache_size(base: Path | None = None) -> int:
    return sum(size_of(p) for p in cache_entries(base))


def _remove(p: Path):
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p, ignore_errors=True)
    else:
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def clear_cache(base: Path | None = None) -> int:
    """Önbelleği temizler; boşalan yer (bayt)."""
    freed = 0
    for p in cache_entries(base):
        n = size_of(p)
        _remove(p)
        if not p.exists():
            freed += n
    log.info("önbellek temizlendi: %d bayt", freed)
    return freed


def scrcpy_dir() -> Path:
    from .mirror import data_dir
    return data_dir() / "scrcpy"


def remove_scrcpy() -> int:
    d = scrcpy_dir()
    n = size_of(d) if d.exists() else 0
    _remove(d)
    log.info("indirilen scrcpy silindi: %d bayt", n)
    return n


def reset_paths(identity: bool, base: Path | None = None) -> list[Path]:
    base = base or config_dir()
    names = SETTINGS + (IDENTITY if identity else ())
    return [base / n for n in names if (base / n).exists()]


def to_trash(paths: list[Path], backup_root: Path | None = None) -> str:
    """Dosyaları çöp kutusuna taşır; olmazsa tarihli yedek klasörüne. Nereye gittiğini söyler."""
    left = []
    try:
        from gi.repository import Gio, GLib
        for p in paths:
            try:
                Gio.File.new_for_path(str(p)).trash(None)
            except GLib.Error as e:
                log.info("çöpe taşınamadı (%s): %s", p, e.message)
                left.append(p)
    except ImportError:
        left = list(paths)
    if not left:
        return "çöp kutusuna taşındı"
    root = backup_root or config_dir().parent
    dest = root / f"talk-to-android-yedek-{time.strftime('%Y%m%d-%H%M%S')}"
    dest.mkdir(parents=True, exist_ok=True)
    for p in left:
        shutil.move(str(p), str(dest / p.name))
    return f"{dest} klasörüne taşındı"


def reset(identity: bool, base: Path | None = None, backup_root: Path | None = None) -> str:
    paths = reset_paths(identity, base)
    where = to_trash(paths, backup_root) if paths else "silinecek bir şey yoktu"
    log.warning("uygulama sıfırlandı (kimlik %s): %s", "yenilendi" if identity else "korundu", where)
    return where
