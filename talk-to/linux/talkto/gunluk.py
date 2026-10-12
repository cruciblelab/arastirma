"""Günlük ve çökme kaydı: ~/.cache/talk-to-android/gunluk.txt ve cokme.txt.

Masaüstünden başlatılan uygulamanın çıktısı hiçbir yerde görünmez; bir hata ya da çökme olunca
nedeni bu dosyalarda kalır ("Hakkında → Hata ayıklama bilgisi" yerine dosyayı göndermek yeter).
Python hataları gunluk.txt'ye, yorumlayıcının kendisinin çökmesi (C katmanında, ör. GTK) cokme.txt'ye
yazılır. Dosyalar küçük tutulur (en çok ~3 MB).

Donma bekçisi: arayüz (GTK ana döngüsü) birkaç saniyeden uzun yanıt vermezse bütün iş parçacıklarının
o anki yığını kendiliğinden günlüğe ve cokme.txt'ye yazılır; bir daha yanıt verince o da yazılır.
`talk-to-android teshis` aynı raporu istendiği anda yazar (arayüz donmuşken de çalışır: komutu bağlantı
iş parçacığı karşılar) ve açık pencerelerin durumunu (görünür mü, modal mı, kime bağlı) ekler.
"""

import faulthandler
import logging
import logging.handlers
import os
import sys
import threading
import time
import traceback

from .config import cache_dir

_crash_file = None
log = logging.getLogger("talkto.teshis")


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
    from . import __version__
    logging.getLogger("talkto").info("Talk To %s başladı (süreç %d)", __version__, os.getpid())


def stacks() -> str:
    """Bütün iş parçacıklarının o anki Python yığını (okunur metin)."""
    names = {t.ident: t.name for t in threading.enumerate()}
    out = []
    for ident, frame in sys._current_frames().items():
        out.append(f"--- {names.get(ident, ident)}\n" + "".join(traceback.format_stack(frame)))
    return "\n".join(out)


def report(reason: str):
    """Yığınları günlüğe ve cokme.txt'ye yazar (C katmanındaki yeri de faulthandler gösterir)."""
    log.warning("%s; iş parçacıkları:\n%s", reason, stacks())
    if _crash_file:
        try:
            _crash_file.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} {reason} ---\n")
            _crash_file.flush()
            faulthandler.dump_traceback(file=_crash_file, all_threads=True)
            _crash_file.flush()
        except (OSError, ValueError):
            pass


class Bekci:
    """Ana döngü bekçisi: beat() ana döngüden düzenli çağrılır; check() başka iş parçacığından bakar."""

    def __init__(self, limit: float = 6.0, clock=time.monotonic, on_stall=None, on_recover=None):
        self.limit = limit
        self.clock = clock
        self.last = clock()
        self.stalled_at = None  # bildirilmiş takılmanın başladığı an
        self.on_stall = on_stall or (lambda sec: report(f"arayüz {sec:.0f} sn'dir yanıt vermiyor"))
        self.on_recover = on_recover or (lambda sec: log.warning("arayüz yeniden yanıt veriyor (%.0f sn takıldı)", sec))

    def beat(self):
        now = self.clock()
        if self.stalled_at is not None:
            self.on_recover(now - self.stalled_at)
            self.stalled_at = None
        self.last = now
        return True

    def check(self):
        idle = self.clock() - self.last
        if idle > self.limit and self.stalled_at is None:
            self.stalled_at = self.last
            self.on_stall(idle)

    def start(self):
        def run():
            while True:
                time.sleep(1)
                self.check()
        threading.Thread(target=run, daemon=True, name="donma-bekcisi").start()
