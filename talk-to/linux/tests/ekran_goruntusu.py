"""Arayüzün ekran görüntülerini örnek verilerle üretir (tasarımı denetlemek için).

    xvfb-run -a env GSK_RENDERER=cairo python3 tests/ekran_goruntusu.py cikti_klasoru [genislik]
"""

import os
import shutil
import subprocess
import sys
import traceback
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
tmp = tempfile.mkdtemp()
os.environ["TALKTO_CONFIG_DIR"] = tmp + "/cfg"
os.environ["TALKTO_CACHE_DIR"] = tmp + "/cache"

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import GLib, Graphene, Gtk  # noqa: E402

from talkto.hub import Hub  # noqa: E402
from talkto.ui.app import App  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "ekran")
WIDTH = int(sys.argv[2]) if len(sys.argv) > 2 else 920
OUT.mkdir(parents=True, exist_ok=True)


def factory(config, emit):
    config.set("port", 47690)
    config.set("setup_done", not os.environ.get("KURULUM"))  # KURULUM=1: kurulum yardımcısının adımları
    config.set("name", "masaustu")
    config.set("wireless", True)
    config.set("simple_mode", not os.environ.get("TAM"))  # TAM=1: bütün özellikler görünür
    config.set("receive_dir", str(Path.home() / "Downloads" / "TalkToAndroid"))
    config.save_command(None, "Yedeği başlat", "rsync -a ~/Belgeler /mnt/yedek")
    config.save_command(None, "Sunucu durumu", "systemctl --user status sunucu")
    config.trust("pixel", "Pixel 8", "Google Pixel 8", "x", "benim")
    config.trust("tablet", "Galaxy Tab", "Samsung SM-X200", "y", "misafir")
    return Hub(config, emit, enable_media=False, enable_discovery=False)


app = App(hub_factory=factory)


# PyGObject 3.46 öncesi (Ubuntu 22.04: 3.42) Gsk.RenderNode'u Python nesnesine çeviremiyor,
# Gtk.Snapshot.to_node() çöküyor. Orada pencere X sunucusundan ImageMagick ile çekilir.
OLD_GI = gi.version_info < (3, 46) or os.environ.get("TALKTO_SNAP") == "x11"


def snap_x11(widget, path):
    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11
    surface = widget.get_native().get_surface()
    target = str(surface.get_xid()) if isinstance(surface, GdkX11.X11Surface) else "root"
    if not shutil.which("import"):
        print("ImageMagick yok, görüntü atlandı:", path)
        return
    subprocess.run(["import", "-window", target, str(path)], check=True)


def snap(widget, name):
    path = OUT / f"{name}.png"
    if OLD_GI:
        snap_x11(widget, path)
    else:
        w, h = widget.get_width(), widget.get_height()
        paintable = Gtk.WidgetPaintable.new(widget)
        s = Gtk.Snapshot()
        paintable.snapshot(s, w, h)
        node = s.to_node()
        if node is None:  # pencere bu değişiklikten sonra henüz çizilmedi: sonraki turda yeniden dene
            raise NotReady(name)
        tex = widget.get_native().get_renderer().render_texture(node, Graphene.Rect().init(0, 0, w, h))
        tex.save_to_png(str(path))
    print("kaydedildi", path)


def fill():
    win = app.window
    win.set_default_size(WIDTH, int(sys.argv[3]) if len(sys.argv) > 3 else 760)
    st = app.hub.status()
    st["addresses"] = ["192.168.1.34"]
    st["sessions"] = [{
        "device_id": "pixel", "name": "Pixel 8", "model": "Pixel 8", "kind": "wifi", "ip": "192.168.1.52",
        "battery": {"level": 76, "charging": True},
        "media": {"active": True, "player": "Spotify", "title": "Gesi Bağları", "artist": "Sezen Aksu",
                  "playing": True, "position_ms": 83_000, "duration_ms": 241_000, "volume": 60,
                  "can_seek": True, "received_at": time.monotonic()}}]
    st["sessions"][0].update(profile="benim", profile_name="Benim telefonum")
    if os.environ.get("SORUN"):  # telefon bildirim dinleyicisinin bağlı olmadığını bildirmiş
        from talkto.hub import phone_problems
        st["sessions"][0]["problems"] = phone_problems({"flavor": "tam", "notif_access": True, "listener": False},
                                                      {"notifications": True, "media": True})
    st["bt"] = {"available": True, "message": "Hazır. Telefonu önce sistemin Bluetooth ayarlarından bu bilgisayarla eşleştir."}
    if os.environ.get("USB_HAZIR") or os.environ.get("USB_KAPALI"):  # telefon USB'de, henüz bağlı değil
        st["sessions"] = []
    if os.environ.get("AYNI_TELEFON"):  # Wi-Fi'den bağlı telefon USB'de de takılı: tek satır
        st["sessions"][0]["adb_serial"] = "38XYZ"
        st["trusted"] = [{"device_id": d, "name": n, "model": m, "paired_at": 1760000000 - i * 86400, "profile": "benim"}
                         for i, (d, n, m) in enumerate((("pixel", "Pixel 8", "Pixel 8"),
                                                        ("eski", "Redmi Note 9", "M2003J15SC")))]
    app.on_event("status", st)
    if st["sessions"]:
        app.on_event("media", {"device_id": "pixel", "state": st["sessions"][0]["media"]})
    FAKE["st"] = st
    pages[:] = [p for p in pages if win.pages[p].get_visible()]
    if os.environ.get("ADB_YOK"):  # adb kurulu değilken görünen "Kur" düğmesi
        from talkto.ui import system
        system.adb_install_command = lambda: ["pkexec", "apt-get", "install", "-y", "adb"]
        app.on_event("usb", {"adb": False, "running": True, "devices": []})
    elif os.environ.get("USB_HAZIR"):
        app.on_event("usb", {"adb": True, "running": True, "apk": "/x.apk", "apk_version": "0.9.0", "devices": [
            {"serial": "38XYZ", "state": "device", "tunnel": True, "model": "2311DRK48G", "name": "POCO X6 Pro",
             "maker": "Xiaomi", "xiaomi_permissions": False, "app": True, "app_version": "0.9.0",
             "perms": {"post": True, "listener": True, "battery": False}}]})
    elif os.environ.get("USB_KAPALI"):  # telefon takılı ama USB hata ayıklama kapalı
        app.on_event("usb", {"adb": True, "running": True, "apk": "/x.apk", "devices": [],
                             "unseen": [{"serial": "abc", "name": "Xiaomi Redmi Note 12", "adb": False,
                                         "vendor": "2717"}]})
    else:
        app.on_event("usb", {"adb": True, "running": True, "apk": "/usr/share/talk-to-android/talk-to-linux.apk",
                             "devices": [{"serial": "38XYZ", "state": "device", "tunnel": True, "model": "Pixel 8", "app": False}]})
    for i, (t, x, a) in enumerate([("Ayşe", "Akşam yemeğe geliyor musun?", "WhatsApp"),
                                   ("Kargo yolda", "Siparişin bugün teslim edilecek.", "Trendyol"),
                                   ("Yeni video", "Kanal yeni bir video yükledi", "YouTube")]):
        app.on_event("notification", {"device_id": "pixel", "device": "Pixel 8", "key": str(i), "package": "x",
                                      "app": a, "title": t, "text": x, "time": time.time() - i * 300})
    app.on_event("transfer", {"device_id": "pixel", "device": "Pixel 8", "direction": "in", "tid": 1,
                              "name": "IMG_20261010_142233.jpg", "size": 3_400_000, "done": 3_400_000,
                              "state": "done", "path": "/tmp/x.jpg"})
    app.on_event("transfer", {"device_id": "pixel", "device": "Pixel 8", "direction": "out", "tid": 2,
                              "name": "sunum.pdf", "size": 12_000_000, "done": 7_100_000, "state": "active"})
    return False


FAKE = {}
pages = ["telefonlar", "medya", "dosyalar", "bildirimler"]
step = {"i": 0}


class NotReady(Exception):
    pass


def guard(fn):
    """Zamanlayıcı geri çağrısındaki istisnayı GLib yalnızca yazdırır; uygulama açık kalır ve CI saatlerce
    bekler. Bu yüzden hata olursa süreç hemen başarısız biter (henüz çizilmemiş pencere hariç: o turda
    hiçbir şey ilerlemez, zamanlayıcı bir sonraki turda aynı adımı yeniden dener)."""
    def wrapped(*args):
        try:
            return fn(*args)
        except NotReady as e:
            print("henüz çizilmedi, yeniden denenecek:", e)
            return True
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            os._exit(1)
    return wrapped


def watchdog():
    print("ekran görüntüsü 120 sn içinde bitmedi", file=sys.stderr)
    os._exit(1)


@guard
def shoot():
    win = app.window
    i = step["i"]
    n = len(pages)
    if 0 < i <= n:
        snap(win, f"{i:02d}-{pages[i - 1]}")
    if i < n:
        app.on_event("status", FAKE["st"])  # hub'ın gerçek durum güncellemeleri örnek veriyi ezmesin
        if pages[i] == "telefonlar" and win.profile_group.rows:
            win.profile_group.rows[0].set_expanded(True)
        win.stack.set_visible_child_name(pages[i])
        step["i"] += 1
        return True
    if i == n:  # Tercihler penceresi: özellikler (basit mod), sonra bağlantı yolları ve genel ayarlar
        win.open_preferences(0)
        if len(sys.argv) > 3:  # uzun ekran: Tercihler'in tamamı görünsün
            win.prefs_window.set_default_size(WIDTH, int(sys.argv[3]))
        win.prefs_window.set_default_size(WIDTH, 900)
        step["i"] += 1
        return True
    if i == n + 1:
        snap(win.prefs_window, f"{i:02d}-ozellikler")
        win.open_preferences(1)
        step["i"] += 1
        return True
    if i == n + 2:
        snap(win.prefs_window, f"{i:02d}-tercihler")
        win.open_preferences(2)
        step["i"] += 1
        return True
    if i == n + 3:
        snap(win.prefs_window, f"{i:02d}-araclar")
        win.prefs_window.close()
        app.on_event("status", FAKE["st"])
        app.on_event("media", {"device_id": "pixel", "state": FAKE["st"]["sessions"][0]["media"]})
        app.open_mini_player()
        step["i"] += 1
        return True
    if i == n + 4:
        # Mini oynatıcının hâlleri: orta, tepecik, küçük, büyük (her biri bir sonraki turda çizilir).
        m = step.setdefault("m", 0)
        names = ["mini-oynatici", "mini-tepecik", "mini-kucuk", "mini-buyuk"]
        snap(app.mini, f"{i:02d}-{names[m]}")
        print(names[m], app.mini.get_width(), app.mini.get_height())
        step["m"] = m + 1
        if m == 0:
            app.mini.set_compact(True)
        elif m == 1:
            app.mini.set_compact(False)
            app.mini.set_size("kucuk")
        elif m == 2:
            app.mini.set_size("buyuk")
        if m < 3:
            return True
        app.mini.set_size("orta")
        app.mini.close()
        win.stack.set_visible_child_name("telefonlar")
        app._ask({"id": "x", "kind": "pair", "name": "Pixel 8", "model": "Pixel 8", "code": "482913",
                  "transport": "bluetooth", "ip": "AA:BB:CC:DD:EE:FF",
                  "profiles": {"benim": "Benim telefonum", "misafir": "Misafir"}, "default_profile": "benim"})
        app.window.add_command_log({"device": "Pixel 8", "id": "kilitle", "name": "Ekranı kilitle"})
        step["i"] += 1
        return True
    # Eski libadwaita'da onay penceresi ayrı bir pencere; varsa onu çek.
    others = [w for w in Gtk.Window.list_toplevels()
              if w is not win and w is not win.prefs_window and w is not app.mini and w.get_visible()
              and w.get_width() > 50]
    snap(others[0] if others else win, f"{i:02d}-onay")
    app._quit()
    return False


@guard
def shoot_setup():
    """Kurulum yardımcısının her adımı (ilk açılışta kendiliğinden açılır)."""
    sw = app.setup_window
    i = step["i"]
    if i > 0:
        snap(sw, f"kurulum-{i}")
    if i < len(sw.steps):
        if i > 0:
            sw.go(+1)
        step["i"] += 1
        return True
    app._quit()
    return False


@guard
def start():
    fill()
    GLib.timeout_add(900, shoot_setup if os.environ.get("KURULUM") else shoot)
    return False


GLib.timeout_add_seconds(120, watchdog)
app.connect("activate", lambda *_: GLib.timeout_add(600, start))
app.run([])
