"""Uçtan uca: gerçek Talk To (sahte telefon olaylarıyla) GNOME Shell 46'nın içinde; üst ada eklentisi.
Sıra: müzik → şarkı değişir (ada büyür) → oynat'a tıkla → sola sürükle (bildirimler) → arama gelir → Yanıtla'ya
tıkla → zamanlayıcı sayfası → 1 dk. Ekran görüntüleri ve eylemler OUT klasörüne."""
import json, os, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
OUT = sys.argv[2]
ART = sys.argv[3]
t = tempfile.mkdtemp(); os.environ["TALKTO_CONFIG_DIR"] = t + "/c"; os.environ["TALKTO_CACHE_DIR"] = t + "/k"
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gio, GLib
from talkto.hub import Hub
from talkto.ui.app import App

def f(config, emit):
    for k, v in (("port", 47701), ("setup_done", True), ("wireless", False), ("usb", False), ("bluetooth", False),
                 ("run_in_background", True), ("track_popup", False)):
        config.set(k, v)
    return Hub(config, emit, enable_media=False, enable_discovery=False)

app = App(hub_factory=f)
calls = []
app.call = lambda *a: calls.append(a) or open(f"{OUT}/eylemler.txt", "a").write(repr(a) + "\n")
bus = None

def cek(method, *args):
    sig = {"Shot": "(s)", "Click": "(dd)", "Drag": "(dddd)"}[method]
    bus.call_sync("test.Cek", "/test/Cek", "test.Cek", method, GLib.Variant(sig, args), None, 0, 10000, None)

def song(title, playing=True):
    return {"active": True, "player": "Spotify", "title": title, "artist": "Sezen Aksu", "playing": playing,
            "position_ms": 1000, "duration_ms": 200000, "volume": 50, "can_seek": True, "art_id": "k1",
            "received_at": time.monotonic()}

sess = {"device_id": "p", "name": "POCO X6 Pro", "kind": "wifi", "ip": "1.2.3.4", "problems": [],
        "media": {"active": False}, "profile_name": "Benim telefonum", "battery": {"level": 76, "charging": False}}
call = {"device_id": "p", "device": "POCO", "key": "k1", "app": "WhatsApp", "caller": "Babam", "text": "Gelen arama",
        "actions": [{"i": 0, "title": "Reddet"}, {"i": 1, "title": "Yanıtla"}], "state": "ringing"}
X = 640
steps = [
    lambda: (app.art_paths.__setitem__("k1", ART), app.on_event("status", {**app.hub.status(), "sessions": [sess]}),
             app.on_event("media", {"device_id": "p", "state": song("Firuze")})),
    lambda: cek("Shot", f"{OUT}/1-kucuk.png"),
    lambda: app.on_event("media", {"device_id": "p", "state": song("Gesi Bağları")}),
    lambda: cek("Shot", f"{OUT}/2-sarki-degisti.png"),
    lambda: cek("Click", X, 190.0),  # büyük sayfadaki oynat/duraklat
    lambda: cek("Drag", X + 120.0, 120.0, X - 80.0, 120.0),  # sola sürükle → bildirimler
    lambda: app.on_event("notification", {"device_id": "p", "device": "POCO", "key": "n1", "package": "x",
                                         "app": "WhatsApp", "title": "Ayşe", "text": "Geliyor musun?",
                                         "time": time.time()}),
    lambda: cek("Shot", f"{OUT}/3-bildirim.png"),
    lambda: app.on_event("call", call),
    lambda: cek("Shot", f"{OUT}/4-arama.png"),
    lambda: cek("Click", X + 44.0, 135.0),  # Yanıtla
    lambda: app.on_event("call_ended", {"device_id": "p", "key": "k1"}),
    lambda: cek("Drag", X + 150.0, 110.0, X - 120.0, 110.0),
    lambda: cek("Drag", X + 150.0, 110.0, X - 120.0, 110.0),
    # Gerçek hub kendi durumunu (telefonsuz) yayınlayabilir: telefon bağlı durumu yeniden ver.
    lambda: (app.on_event("status", {**app.hub.status(), "sessions": [sess]}), cek("Shot", f"{OUT}/5-zamanlayici.png")),
    lambda: cek("Click", X - 137.0, 115.0),  # 1 dk (telefonda da)
    lambda: None,
    lambda: (cek("Shot", f"{OUT}/6-sayac.png"),
             open(f"{OUT}/durum.json", "w").write(json.dumps(app.ada.state(), ensure_ascii=False))),
    lambda: app.quit(),
]
i = [0]
def tick():
    global bus
    if bus is None:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    try:
        steps[i[0]]()
    except Exception as e:  # noqa
        print("adım", i[0], "hata", e, flush=True)
    i[0] += 1
    return i[0] < len(steps)
GLib.timeout_add(1500, tick)
app.run([])
json.dump({"ada_state": None}, open(f"{OUT}/bitti.json", "w"))
