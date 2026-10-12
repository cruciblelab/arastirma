"""Arayüzün ekran görüntülerini örnek paketlerle üretir (tasarımı denetlemek için).

    xvfb-run -a env GSK_RENDERER=cairo python3 tests/ekran_goruntusu.py cikti_klasoru
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from yardimci import build_deb, make_key

os.environ["PAKET_GUNCELLEYICI_DIL"] = "tr"  # önce Türkçe; sondaki "en-" adımları İngilizce

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import GLib, Graphene, Gtk  # noqa: E402

from guncelleyici import apt, dil, durdur, imza, paket, yayinci  # noqa: E402
from guncelleyici.ui import App, Window  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "ekran")
OUT.mkdir(parents=True, exist_ok=True)
TMP = Path(tempfile.mkdtemp())
SECRET, PUBLIC, FPR = make_key(TMP, "yayinci")
OTHER_SECRET, OTHER_PUBLIC, OTHER_FPR = make_key(TMP, "baskasi")
OLD_GI = gi.version_info < (3, 46) or os.environ.get("TALKTO_SNAP") == "x11"

SIM = apt.parse_simulation("Inst gir1.2-adw-1 (1.1.7 Ubuntu [amd64])\n"
                           "Inst talk-to-android [0.7.0] (0.7.1 local-deb [all])\n")


CARD = {"yayinci": "Crucible ekibi", "web": "https://github.com/cruciblelab/arastirma",
        "iletisim": "https://github.com/cruciblelab/arastirma/issues",
        "dogrulama": "https://raw.githubusercontent.com/cruciblelab/arastirma/talk-to/talk-to/YAYINCI.txt"}
FAKE_CARD = {"yayinci": "Crucible ekibi", "web": "https://crucible-indir.example",
             "dogrulama": "https://crucible-indir.example/anahtar.txt"}
# Ekran görüntüsünde ağa çıkılmaz: site doğrulamasının sonucu senaryoya göre verilir.
SITE = {}
yayinci.verify = lambda url, fpr, web="", **_: yayinci.Dogrulama(SITE.get("state", yayinci.DOGRULANDI), url,
                                                                 SITE.get("detail", ""), yayinci.same_site(web, url))


class NotReady(Exception):
    pass


def snap(widget, name):
    path = OUT / f"{name}.png"
    if OLD_GI:
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
        surface = widget.get_native().get_surface()
        target = str(surface.get_xid()) if isinstance(surface, GdkX11.X11Surface) else "root"
        if shutil.which("import"):
            subprocess.run(["import", "-window", target, str(path)], check=True)
    else:
        w, h = widget.get_width(), widget.get_height()
        s = Gtk.Snapshot()
        Gtk.WidgetPaintable.new(widget).snapshot(s, w, h)
        node = s.to_node()
        if node is None:
            raise NotReady(name)
        widget.get_native().get_renderer().render_texture(node, Graphene.Rect().init(0, 0, w, h)).save_to_png(str(path))
    print("kaydedildi", path)


def scenario(win, name):
    """Örnek bir paketi verilen durumla pencereye koyar."""
    old_card = None
    if name == "guncelleme":
        deb = build_deb(TMP, package="talk-to-android", version="0.7.1", key=PUBLIC, secret=SECRET, publisher=CARD)
        SITE["state"] = yayinci.DOGRULANDI
        pkg = paket.read(str(deb))
        pkg.name, pkg.summary = "Talk To Android", "Android telefonu USB, Wi-Fi ya da Bluetooth ile Linux'a bağlar"
        pkg.installed, pkg.verdict = "0.7.0", paket.GUNCELLE
        sig, sim = imza.Sonuc(imza.AYNI, FPR, "kurulu", True), SIM
    elif name == "ilk-kez":
        deb = build_deb(TMP, package="talk-to-android", version="0.7.1", key=PUBLIC, secret=SECRET, publisher=CARD)
        SITE["state"] = yayinci.DOGRULANDI
        pkg = paket.read(str(deb))
        pkg.name, pkg.summary = "Talk To Android", "Android telefonu USB, Wi-Fi ya da Bluetooth ile Linux'a bağlar"
        pkg.installed, pkg.verdict = "0.7.0", paket.GUNCELLE
        sig, sim = imza.Sonuc(imza.ILK, FPR), apt.Deneme(install=[("talk-to-android", "0.7.0", "0.7.1")])
    elif name == "farkli-yayinci":
        deb = build_deb(TMP, package="talk-to-android", version="9.9.9", key=OTHER_PUBLIC, secret=OTHER_SECRET,
                        publisher=FAKE_CARD)
        SITE.update(state=yayinci.ULASILAMADI, detail="Name or service not known")
        old_card = yayinci.parse(json.dumps(CARD).encode())
        pkg = paket.read(str(deb))
        pkg.name = "Talk To Android"
        pkg.installed, pkg.verdict = "0.7.1", paket.GUNCELLE
        sig = imza.Sonuc(imza.FARKLI, OTHER_FPR, had_anchor=True)
        sim = apt.parse_simulation("Inst talk-to-android [0.7.1] (9.9.9 local-deb [all])\nRemv openssh-server [1]\n")
    else:
        deb = build_deb(TMP, package="deneme-uygulama", version="1.0", key=None)
        pkg = paket.read(str(deb))
        pkg.installed, pkg.verdict = "1.2", paket.ESKI
        sig, sim = imza.Sonuc(imza.IMZASIZ), apt.Deneme(install=[("deneme-uygulama", "1.2", "1.0")])
    win.title.set_subtitle(deb.name)
    win.show_package(str(deb), str(deb), pkg, sig, sim, yayinci.parse(pkg.publisher), old_card)


app = App()
steps = ["bos", "guncelleme", "ilk-kez", "farkli-yayinci", "eski-imzasiz", "kilit", "durmaya-zorla", "bitti",
         "uygulamalar", "kaldir", "veriler", "hata-yarim", "en-bos", "en-guncelleme", "en-durmaya-zorla"]
state = {"i": 0, "win": None}


def guarded(fn):
    def wrapped(*a):
        try:
            return fn(*a)
        except NotReady as e:
            print("henüz çizilmedi:", e)
            return True
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            os._exit(1)
    return wrapped


@guarded
def tick():
    win, i = state["win"], state["i"]
    if i > 0:
        snap(win, f"{i:02d}-{steps[i - 1]}")
    if i == len(steps):
        app.quit()
        return False
    name = steps[i]
    if name.startswith("en-"):
        if dil.current != "en":  # İngilizce: yeni pencere (yazılar pencere kurulurken çevrilir)
            dil.setup("en")
            old, win = win, Window(app)
            win.set_default_size(560, 860)
            win.present()
            old.destroy()
            state["win"] = win
        name = name[3:]
    if name in ("guncelleme", "ilk-kez", "farkli-yayinci", "eski-imzasiz"):
        scenario(win, name)
    elif name == "kilit":
        scenario(win, "guncelleme")
        win.stack.set_visible_child_name("kuruluyor")
        win.progress_page.set_title("Talk To Android kuruluyor")
        win._waiting = True
        win._event(apt.parse_line("Waiting for cache lock: Could not get lock /var/lib/dpkg/lock-frontend. "
                                  "It is held by process 1073 (unattended-upgr)... 95s"))
        win.progress.pulse()
    elif name == "durmaya-zorla":
        if win.stack.get_visible_child_name() != "kuruluyor":  # İngilizce adımda kilit sahnesi yeniden kurulur
            scenario(win, "guncelleme")
            win.stack.set_visible_child_name("kuruluyor")
            win.progress_page.set_title(win.pkg.name)
            win._waiting = True
            win._event(apt.parse_line("Waiting for cache lock: Could not get lock /var/lib/dpkg/lock-frontend. "
                                      "It is held by process 1073 (unattended-upgr)... 95s"))
        # Otomatik güncelleme paket kuruyor (firefox): ne olacağı söylenir, karar kullanıcıda.
        durdur.risk = lambda: (durdur.KURUYOR, ["firefox", "thunderbird"])
        win._force_ask()
    elif name == "bitti":
        win.busy = False
        win._pulse = None
        win._finished(True)
    elif name == "uygulamalar":
        win._fill_apps([
            apt.Uygulama("talk-to-android", "0.9.2", "Talk To Android", None, "a.desktop", True),
            apt.Uygulama("paket-guncelleyici", "0.2.0", "Paket Güncelleyici", None, "b.desktop", True),
            apt.Uygulama("gnome-calculator", "1:42.2-0ubuntu1", "Hesap Makinesi", "org.gnome.Calculator", "c", False),
            apt.Uygulama("libreoffice-calc", "1:7.3.7-0ubuntu0.22.04.10", "LibreOffice Calc", None, "d", False)])
        win.stack.set_visible_child_name("liste")
    elif name == "kaldir":
        a = apt.Uygulama("gnome-calculator", "1:42.2-0ubuntu1", "Hesap Makinesi", "org.gnome.Calculator", "c", False)
        win.show_remove(a, apt.Deneme(remove=["gnome-calculator", "ubuntu-desktop", "ubuntu-desktop-minimal"]))
    elif name == "veriler":
        from guncelleyici import veriler
        a = apt.Uygulama("gnome-calculator", "1:42.2-0ubuntu1", "Hesap Makinesi", "org.gnome.Calculator", "c", False)
        home = Path.home()
        win.mode, win.target = "veri", a
        win._fill_data(a, [veriler.Klasor(home / ".cache/gnome-calculator", "onbellek", 2_400_000),
                           veriler.Klasor(home / ".local/share/gnome-calculator", "veri", 48_000),
                           veriler.Klasor(home / ".config/gnome-calculator", "ayar", 3_100)], False)
    elif name == "hata-yarim":
        from guncelleyici import hatalar
        win.mode = "kur"
        win._failed(hatalar.explain([
            "E: dpkg was interrupted, you must manually run 'dpkg --configure -a' to correct the problem."], 100))
    state["i"] += 1
    return True


def start(*_):
    state["win"] = app.get_active_window()
    state["win"].set_default_size(560, 860)
    GLib.timeout_add(1200, tick)
    GLib.timeout_add_seconds(120, lambda: os._exit(1))


app.connect("activate", lambda *_: GLib.idle_add(start))
sys.exit(app.run([]))
