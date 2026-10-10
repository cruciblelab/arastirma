"""Arayüzün ekran görüntülerini örnek verilerle üretir (tasarımı denetlemek için).

    xvfb-run -a env GSK_RENDERER=cairo python3 tests/ekran_goruntusu.py cikti_klasoru [genislik]
"""

import os
import sys
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
    config.set("name", "masaustu")
    config.set("wireless", True)
    config.set("receive_dir", str(Path.home() / "Downloads" / "TalkToAndroid"))
    config.save_command(None, "Yedeği başlat", "rsync -a ~/Belgeler /mnt/yedek")
    config.save_command(None, "Sunucu durumu", "systemctl --user status sunucu")
    config.trust("pixel", "Pixel 8", "Google Pixel 8", "x", "benim")
    config.trust("tablet", "Galaxy Tab", "Samsung SM-X200", "y", "misafir")
    return Hub(config, emit, enable_media=False, enable_discovery=False)


app = App(hub_factory=factory)


def snap(widget, name):
    w, h = widget.get_width(), widget.get_height()
    paintable = Gtk.WidgetPaintable.new(widget)
    s = Gtk.Snapshot()
    paintable.snapshot(s, w, h)
    node = s.to_node()
    tex = widget.get_native().get_renderer().render_texture(node, Graphene.Rect().init(0, 0, w, h))
    tex.save_to_png(str(OUT / f"{name}.png"))
    print("kaydedildi", OUT / f"{name}.png")


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
    st["bt"] = {"available": True, "message": "Hazır. Telefonu önce sistemin Bluetooth ayarlarından bu bilgisayarla eşleştir."}
    app.on_event("status", st)
    FAKE["st"] = st
    if os.environ.get("ADB_YOK"):  # adb kurulu değilken görünen "Kur" düğmesi
        from talkto.ui import system
        system.adb_install_command = lambda: ["pkexec", "apt-get", "install", "-y", "adb"]
        app.on_event("usb", {"adb": False, "running": True, "devices": []})
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
pages = ["baglanti", "cihazlar", "medya", "dosyalar", "bildirimler", "komutlar"]
step = {"i": 0}


def shoot():
    win = app.window
    i = step["i"]
    if 0 < i <= len(pages):
        snap(win, f"{i:02d}-{pages[i - 1]}")
    if i < len(pages):
        app.on_event("status", FAKE["st"])  # hub'ın gerçek durum güncellemeleri örnek veriyi ezmesin
        if pages[i] == "cihazlar" and win.profile_group.rows:
            win.profile_group.rows[0].set_expanded(True)
        win.stack.set_visible_child_name(pages[i])
        step["i"] += 1
        return True
    if i == len(pages):
        win.stack.set_visible_child_name("baglanti")
        app._ask({"id": "x", "kind": "pair", "name": "Pixel 8", "model": "Pixel 8", "code": "482913",
                  "transport": "bluetooth", "ip": "AA:BB:CC:DD:EE:FF",
                  "profiles": {"benim": "Benim telefonum", "misafir": "Misafir"}, "default_profile": "benim"})
        app.window.add_command_log({"device": "Pixel 8", "id": "kilitle", "name": "Ekranı kilitle"})
        step["i"] += 1
        return True
    # Eski libadwaita'da onay penceresi ayrı bir pencere; varsa onu çek.
    others = [w for w in Gtk.Window.list_toplevels() if w is not win and w.get_visible() and w.get_width() > 50]
    snap(others[0] if others else win, f"{i:02d}-onay")
    app._quit()
    return False


def start():
    fill()
    GLib.timeout_add(900, shoot)
    return False


app.connect("activate", lambda *_: GLib.timeout_add(600, start))
app.run([])
