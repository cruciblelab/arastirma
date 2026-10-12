"""Gerçek GNOME Shell'de mini oynatıcının ⋮ menüsü (kabukta.sh içinde çalışır). Argüman: kaynak ÇIKTI ÜSTTE(1/0)

0.12.0'da "odak kaybında menüyü kapat" kuralı XWayland'de (üstte tut) menüyü açıldığı anda kapatıyordu: X11'de menü
açılırken pencere bir anlığına odağı kaybedip geri alıyor. Burada: ⋮'ye tıklanınca menü açık kalmalı, başka bir yere
tıklanınca kapanmalı (XWayland'de GTK odağın gittiğini fark etmiyor; pencere yöneticisine sorulur)."""
import json, os, sys, tempfile
sys.path.insert(0, sys.argv[1]); OUT = sys.argv[2]; ONTOP = sys.argv[3] == "1"
t = tempfile.mkdtemp(); os.environ["TALKTO_CONFIG_DIR"] = t + "/c"; os.environ["TALKTO_CACHE_DIR"] = t + "/k"
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Gio, GLib
from talkto.hub import Hub
from talkto.ui import ustte
from talkto.ui.app import App


def f(config, emit):
    for k, v in (("port", 47702), ("setup_done", True), ("wireless", False), ("usb", False), ("bluetooth", False),
                 ("mini_on_top", ONTOP), ("mini_compact", False)):
        config.set(k, v)
    return Hub(config, emit, enable_media=False, enable_discovery=False)


app = App(hub_factory=f)
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def cek(m, *a):  # eşzamansız: kabuk X11 penceresinin çizilmesini beklerken bu süreç tıkanmasın
    sig = {"Shot": "(s)", "Click": "(dd)"}[m]
    bus.call("test.Cek", "/test/Cek", "test.Cek", m, GLib.Variant(sig, a), None, 0, 10000, None, None)


def menu_open():
    b = app.mini.menu_button.get_popover()
    return bool(b and b.get_visible())


seen = {}


def menu_xy():
    """⋮ düğmesinin ekrandaki yeri. Kabuk ilk pencereyi sol üste, üst çubuğun (32 px) hemen altına yerleştirir."""
    from gi.repository import Graphene
    m = app.mini
    b = m.menu_button
    ok, p = b.compute_point(m, Graphene.Point().init(b.get_width() / 2, b.get_height() / 2))
    seen["xy"] = (p.x, p.y + 32)
    return seen["xy"]


steps = [
    lambda: app.open_mini_player(),
    lambda: seen.update(display=type(app.mini.get_display()).__name__),
    lambda: cek("Click", *map(float, menu_xy())),
    lambda: None,
    lambda: (seen.update(open_after_click=menu_open()), cek("Shot", f"{OUT}/mini-menu-acik.png")),
    lambda: cek("Click", 900.0, 600.0),  # ana pencerenin boş bir yeri
    lambda: None,
    lambda: (seen.update(closed_after_outside=not menu_open()), cek("Shot", f"{OUT}/mini-menu-disari.png")),
]
i = [0]


def tick():
    try:
        steps[i[0]]()
    except Exception as e:  # noqa: BLE001
        seen.setdefault("errors", []).append(f"{i[0]}: {e!r}")
    i[0] += 1
    if i[0] >= len(steps):
        json.dump(seen, open(f"{OUT}/mini-menu-{'x11' if ONTOP else 'wayland'}.json", "w"))
        app._quit()
        return False
    return True


GLib.timeout_add(1500, tick)
app.run([])
