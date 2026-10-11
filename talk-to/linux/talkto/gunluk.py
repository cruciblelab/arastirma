"""Günlük ve çökme kaydı: ~/.cache/talk-to-android/gunluk.txt ve cokme.txt.

Masaüstünden başlatılan uygulamanın çıktısı hiçbir yerde görünmez; bir hata ya da çökme olunca
nedeni bu dosyalarda kalır ("Hakkında → Hata ayıklama bilgisi" yerine dosyayı göndermek yeter).
Python hataları gunluk.txt'ye, yorumlayıcının kendisinin çökmesi (C katmanında, ör. GTK) cokme.txt'ye
yazılır. Dosyalar küçük tutulur (en çok ~3 MB).
"""

import faulthandler
import logging
import logging.handlers
import sys
import time

from .config import cache_dir

_crash_file = None


def setup(level=logging.INFO):
    global _crash_file
    handlers = [logging.StreamHandler()]
    d = cache_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(d / "gunluk.txt", maxBytes=1_000_000, backupCount=2,
                                                             encoding="utf-8"))
        crash = d / "cokme.txt"
        if crash.exists() and crash.stat().st_size > 1_000_000:
            crash.replace(d / "cokme.eski.txt")
        _crash_file = open(crash, "a", encoding="utf-8")  # noqa: SIM115 — süreç boyunca açık kalmalı
        _crash_file.write(f"\n--- başladı {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        _crash_file.flush()
        faulthandler.enable(file=_crash_file, all_threads=True)
    except OSError:
        faulthandler.enable()
    logging.basicConfig(level=level, format="%(asctime)s %(name)s: %(message)s", handlers=handlers, force=True)

    def hook(kind, value, tb):
        logging.getLogger("talkto").error("yakalanmamış hata", exc_info=(kind, value, tb))
    sys.excepthook = hook  # GTK geri çağrılarındaki hatalar da buraya düşer
