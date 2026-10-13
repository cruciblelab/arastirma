"""Üst ada başarım ölçümü: gerçek GNOME Shell + gerçek Talk To (sahte telefon). Her durumda SURE saniye boyunca
kabuğun (gnome-shell) ve Talk To'nun işlemci süresi ölçülür; sonuç OUT/olcum.json. Kullanım: olcum.sh ÇIKTI."""
import json, os, sys, tempfile, time
sys.path.insert(0, sys.argv[1])
OUT = sys.argv[2]
t = tempfile.mkdtemp(); os.environ["TALKTO_CONFIG_DIR"] = t + "/c"; os.environ["TALKTO_CACHE_DIR"] = t + "/k"
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gio, GLib
from talkto.hub import Hub
from talkto.ui.app import App

SURE = float(os.environ.get("SURE", "10"))

def f(config, emit):
    for k, v in (("port", 47702), ("setup_done", True), ("wireless", False), ("usb", False), ("bluetooth", False),
                 ("run_in_background", True), ("track_popup", False), ("ada_idle_pause", 6)):
        try:
            config.set(k, v)
        except KeyError:
            pass
    return Hub(config, emit, enable_media=False, enable_discovery=False)

app = App(hub_factory=f)
app.call = lambda *a: None
bus = None

def cek(method, *args):
    sig = {"Click": "(dd)", "Move": "(dd)", "Find": "(s)"}[method]
    r = bus.call_sync("test.Cek", "/test/Cek", "test.Cek", method, GLib.Variant(sig, args), None, 0, 10000, None)
    return r.unpack() if r else None

def shell_cpu():
    for d in os.listdir("/proc"):
        try:
            if d.isdigit() and open(f"/proc/{d}/comm").read().strip() == "gnome-shell":
                fl = open(f"/proc/{d}/stat").read().rsplit(")", 1)[1].split()
                return (int(fl[11]) + int(fl[12])) / os.sysconf("SC_CLK_TCK")
        except OSError:
            pass
    return 0.0

def own_cpu():
    x = os.times()
    return x.user + x.system

sess = {"device_id": "p", "name": "POCO X6 Pro", "kind": "wifi", "ip": "1.2.3.4", "problems": [],
        "media": {"active": False}, "profile_name": "Benim telefonum", "battery": {"level": 76, "charging": False}}

def song(playing=True):
    return {"active": True, "player": "Spotify", "title": "Firuze", "artist": "Sezen Aksu", "playing": playing,
            "position_ms": 1000, "duration_ms": 200000, "volume": 50, "can_seek": True, "received_at": time.monotonic()}

def kart(key):
    """Ada Place'teki bir kartın ekrandaki ortası (pencere ekranın ortasında varsayılır)."""
    c = app.window.ada_place.cards[key]
    sw = app.window.ada_place.get_ancestor(__import__("gi.repository.Gtk", fromlist=["Gtk"]).ScrolledWindow)
    if sw is not None:  # kart görünsün
        ok, r = c.compute_bounds(sw.get_child())
        if ok:
            sw.get_vadjustment().set_value(max(0, r.get_y() - 100))
    ok, b = c.compute_bounds(app.window)
    w, h = app.window.get_width(), app.window.get_height()
    return (1280 - w) / 2 + b.get_x() + b.get_width() / 2, (800 - h) / 2 + b.get_y() + 30

def tema(key):
    app.ada.action({"do": "set", "key": "ada_theme", "value": key})

def hareket(m):
    app.ada.action({"do": "set", "key": "ada_motion", "value": m})

def phone(playing):
    app.on_event("status", {**app.hub.status(), "sessions": [sess]})
    app.on_event("media", {"device_id": "p", "state": song(playing) if playing is not None else {"active": False}})

POS = {"x": 640.0, "y": 600.0}

def wiggle():  # kullanıcı fareyi oynatıyor (boşta sayılmasın)
    cek("Move", POS["x"] + (time.monotonic() * 7) % 30, POS["y"])

def at(x, y):
    POS.update(x=x, y=y)

# (ad, hazırlık, ölçerken fare oynasın mı)
SCENES = [
    ("bos_deniz", lambda: (tema("deniz"), phone(None)), True),
    ("muzik_deniz", lambda: (tema("deniz"), phone(True)), True),
    ("muzik_kuzey", lambda: (tema("kuzey"), phone(True)), True),
    ("bos_kuzey", lambda: (tema("kuzey"), phone(None)), True),
    ("muzik_kar", lambda: (tema("kar"), phone(True)), True),
    ("muzik_kuzey_yavas", lambda: (tema("kuzey"), phone(True), hareket("yavas")), True),
    ("muzik_kuzey_uzakta", lambda: (hareket("canli"), tema("kuzey"), phone(True)), False),
    # Talk To'nun Ada sekmesi açık; fare pencerenin dışında (ekranın sol alt köşesi), sonra bir kartın üstünde
    ("pencere_ada_sekmesi", lambda: (at(4.0, 790.0), tema("deniz"), phone(None), app.present(),
                                    app.window.stack.set_visible_child_name("ada")), True),
]
res = {}
state = {"i": -1, "phase": "prep", "t0": 0, "s0": 0, "o0": 0}

def tick():
    global bus
    if bus is None:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    if state["i"] == -1:  # açılış: hub kendi durumunu yayınlasın
        state["i"] = 0
        state["phase"] = "prep"
        state["t0"] = time.monotonic()
        return True
    if state["i"] >= len(SCENES):
        json.dump(res, open(f"{OUT}/olcum.json", "w"), indent=1)
        app.quit()
        return False
    name, prep, move = SCENES[state["i"]]
    now = time.monotonic()
    if state["phase"] == "prep":
        prep()
        state.update(phase="settle", t0=now)
    elif state["phase"] == "settle":
        if move:
            wiggle()
        if now - state["t0"] > (8 if not move else 3):  # uzakta: ada boşta beklemesini fark etsin
            state.update(phase="measure", t0=now, s0=shell_cpu(), o0=own_cpu())
    elif state["phase"] == "measure":
        if move:
            wiggle()
        if now - state["t0"] >= SURE:
            dt = now - state["t0"]
            res[name] = {"kabuk": round(100 * (shell_cpu() - state["s0"]) / dt, 1),
                         "talkto": round(100 * (own_cpu() - state["o0"]) / dt, 1)}
            print(name, res[name], flush=True)
            state.update(i=state["i"] + 1, phase="prep")
    return True

GLib.timeout_add(500, tick)
app.run([])
