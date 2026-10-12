"""Uçtan uca: gerçek Talk To (sahte telefon olaylarıyla) GNOME Shell 46'nın içinde; üst ada eklentisi.
Sıra: müzik → şarkı değişir (ada büyür) → oynat'a tıkla → sola sürükle (bildirimler) → arama gelir → Yanıtla'ya
tıkla → zamanlayıcı sayfası → 1 dk → yukarı kaydır (normal, sonra ince şerit) → üstüne gel (normal görünür) → ayrıl
(ince) → tıkla (normal). Düğmelerin yeri kabuğa sorulur (Find). Ekran görüntüleri, eylemler ve boyutlar OUT'a."""
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
    sig = {"Shot": "(s)", "Click": "(dd)", "Drag": "(dddd)", "Move": "(dd)", "Scroll": "(ddd)", "Find": "(s)"}[method]
    r = bus.call_sync("test.Cek", "/test/Cek", "test.Cek", method, GLib.Variant(sig, args), None, 0, 10000, None)
    return r.unpack() if r else None

def find(cls):
    x, y, w, h = cek("Find", cls)
    if w < 0:
        raise RuntimeError(f"{cls} bulunamadı")
    return x, y, w, h

def click(cls):
    x, y, w, h = find(cls)
    cek("Click", x + w / 2, y + h / 2)

def drag_left(far=False):
    x, y, w, h = find("ada")
    # far: adanın dışında bırak (GNOME 42'de bırakma adaya gelmiyor, sürükleme takılı kalıyordu)
    cek("Drag", x + w * 0.8, y + h * 0.5, x - 60 if far else x + w * 0.8 - 200, y + h * 0.5)

def ada_center():
    x, y, w, h = find("ada")
    return x + w / 2, y + h / 2

boy = {}
def olc(name):
    boy[name] = find("ada")
    open(f"{OUT}/boyutlar.json", "w").write(json.dumps(boy))

def olc_cls(cls):
    x, y, w, h = cek("Find", cls)
    boy[cls] = [x, y, w, h]
    open(f"{OUT}/boyutlar.json", "w").write(json.dumps(boy))

def song(title, playing=True):
    return {"active": True, "player": "Spotify", "title": title, "artist": "Sezen Aksu", "playing": playing,
            "position_ms": 1000, "duration_ms": 200000, "volume": 50, "can_seek": True, "art_id": "k1",
            "received_at": time.monotonic()}

sess = {"device_id": "p", "name": "POCO X6 Pro", "kind": "wifi", "ip": "1.2.3.4", "problems": [],
        "media": {"active": False}, "profile_name": "Benim telefonum", "battery": {"level": 76, "charging": False}}
call = {"device_id": "p", "device": "POCO", "key": "k1", "app": "WhatsApp", "caller": "Babam", "text": "Gelen arama",
        "actions": [{"i": 0, "title": "Reddet"}, {"i": 1, "title": "Yanıtla"}], "state": "ringing"}
X = 640
phone_again = lambda: app.on_event("status", {**app.hub.status(), "sessions": [sess]})  # noqa: E731
steps = [
    lambda: (app.art_paths.__setitem__("k1", ART), phone_again(),
             app.on_event("media", {"device_id": "p", "state": song("Firuze")})),
    # Gerçek hub açılışta kendi (telefonsuz) durumunu yayınlar: sahte telefonu ve şarkıyı yeniden ver.
    lambda: (phone_again(), app.on_event("media", {"device_id": "p", "state": song("Firuze")})),
    *[lambda: None] * 4,  # müzik başlayınca ada büyür; ~5 sn sonra küçülür
    lambda: (cek("Shot", f"{OUT}/1-kucuk.png"), olc("normal")),
    lambda: app.on_event("media", {"device_id": "p", "state": song("Gesi Bağları")}),
    lambda: (cek("Shot", f"{OUT}/2-sarki-degisti.png"), olc("buyuk")),
    lambda: click("ada-buyuk-dugme"),  # oynat/duraklat
    lambda: drag_left(far=True),  # sola sürükle, adanın dışında bırak → bildirimler
    lambda: app.on_event("notification", {"device_id": "p", "device": "POCO", "key": "n1", "package": "x",
                                         "app": "WhatsApp", "title": "Ayşe", "text": "Geliyor musun?",
                                         "time": time.time(), "icon": ART}),  # uygulamanın simgesi
    lambda: cek("Shot", f"{OUT}/3-bildirim.png"),
    lambda: app.on_event("call", call),
    lambda: cek("Shot", f"{OUT}/4-arama.png"),
    lambda: click("ada-yesil-dugme"),  # Yanıtla
    # Sürerken: hoparlör (açık: düğmesi "kapat" diyor) ve sessiz düğmeleri yazı değil simge
    lambda: app.on_event("call", dict(call, state="ongoing", actions=[
        {"i": 0, "title": "Kapat"}, {"i": 1, "title": "Hoparlörü kapat"}, {"i": 2, "title": "Sessiz"}])),
    lambda: (cek("Shot", f"{OUT}/4b-gorusme.png"), olc_cls("ada-acik"), olc_cls("ada-kapali"),
             click("ada-acik")),  # hoparlöre bas
    lambda: app.on_event("call_ended", {"device_id": "p", "key": "k1"}),
    lambda: drag_left(),
    lambda: drag_left(),
    lambda: (phone_again(), cek("Shot", f"{OUT}/5-zamanlayici.png")),
    lambda: click("ada-sure"),  # 1 dk (telefonda da)
    lambda: None,
    lambda: (cek("Shot", f"{OUT}/6-sayac.png"),
             open(f"{OUT}/durum.json", "w").write(json.dumps(app.ada.state(), ensure_ascii=False))),
    # Yukarı kaydırma: büyük → normal → ince şerit.
    lambda: cek("Scroll", *ada_center(), -1.0),
    lambda: olc("kaydir1"),
    lambda: cek("Scroll", *ada_center(), -1.0),
    lambda: (olc("ince"), cek("Shot", f"{OUT}/7-ince.png")),
    lambda: cek("Move", 640.0, 600.0),
    lambda: cek("Move", *ada_center()),  # üstüne gel: normal hâl görünür
    lambda: (olc("bakis"), cek("Shot", f"{OUT}/8-bakis.png")),
    lambda: cek("Move", 640.0, 600.0),
    lambda: olc("ayrilinca"),
    lambda: click("ada"),  # tıkla: normale döner
    lambda: cek("Move", 640.0, 600.0),
    lambda: (olc("tiklayinca"), cek("Shot", f"{OUT}/9-normal.png")),
    # Diğer → Özelleştir: ada büyür; tema (Gece) ve kip (Taşan dalgalar) seçilir, ✕ ile kapanır.
    lambda: click("ada"),
    lambda: drag_left(),
    lambda: drag_left(),  # son sayfa: Diğer (fazlası son sayfada kalır)
    lambda: click("ada-ozellestir"),
    lambda: (olc("ozellestir"), cek("Shot", f"{OUT}/10-ozellestir.png")),
    lambda: click("ada-tema-gece"),
    lambda: click("ada-kip-tasan"),
    lambda: (cek("Shot", f"{OUT}/11-tasan.png"), olc_cls("ada-tasan"),
             open(f"{OUT}/durum2.json", "w").write(json.dumps(app.ada.state(), ensure_ascii=False))),
    lambda: click("ada-kapat-ozel"),
    lambda: cek("Move", 640.0, 600.0),
    *[lambda: None] * 5,
    lambda: (olc("ozel_kapandi"), cek("Shot", f"{OUT}/12-kapandi.png")),
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
