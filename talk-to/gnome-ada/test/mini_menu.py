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


win = {}


def ask_window():
    """Mini oynatıcının ekrandaki yeri kabuğa sorulur (kabuk pencereyi her seferinde başka yere koyabiliyor)."""
    def done(c, r):
        win["rect"] = c.call_finish(r).unpack()
    bus.call("test.Cek", "/test/Cek", "test.Cek", "Win", GLib.Variant("(s)", ("Telefonda çalan",)), None, 0, 10000,
             None, done)


def on_screen(widget):
    from gi.repository import Graphene
    ok, p = widget.compute_point(app.mini, Graphene.Point().init(widget.get_width() / 2, widget.get_height() / 2))
    x, y, w, h = win["rect"]
    return x + p.x, y + p.y


def menu_open():
    b = app.mini.menu_button.get_popover()
    return bool(b and b.get_visible())


seen = {}


def menu_xy():
    seen["xy"] = on_screen(app.mini.menu_button)
    return seen["xy"]


def close_xy():
    """Kapat (X) düğmesi: mini oynatıcıda "window-close-symbolic" simgeli düğme."""
    from gi.repository import Graphene, Gtk
    m = app.mini
    def walk(w):
        while w is not None:
            if isinstance(w, Gtk.Button) and w.get_icon_name() == "window-close-symbolic" and w.get_mapped():
                return w
            r = walk(w.get_first_child())
            if r:
                return r
            w = w.get_next_sibling()
        return None
    return on_screen(walk(m.get_first_child()))


def outside():
    """Mini oynatıcının dışında kalan bir nokta (ekranın alt yarısı; mini oynatıcı üstte, küçük)."""
    x, y, w, h = win["rect"]
    return 640.0, float(max(600, y + h + 60))


steps = [
    lambda: app.open_mini_player(),
    lambda: (seen.update(display=type(app.mini.get_display()).__name__), ask_window()),
    # Üstte tutulurken: kullanıcı başka bir penceredeyken mini oynatıcının ⋮'sine tıklar (mini odakta değil).
    # (Wayland'de mini oynatıcı üstte durmaz; tıklanan ana pencere onu örter, bu adım orada anlamsız.)
    lambda: ONTOP and cek("Click", *outside()),
    lambda: seen.update(mini_focused_before=ustte.is_focused(app.mini)),
    lambda: cek("Click", *map(float, menu_xy())),
    lambda: None,
    lambda: (seen.update(open_after_click=menu_open()), cek("Shot", f"{OUT}/mini-menu-acik.png")),
    lambda: cek("Click", *outside()),  # mini oynatıcının dışında, ana pencerenin boş bir yeri
    lambda: None,
    lambda: (seen.update(closed_after_outside=not menu_open()), cek("Shot", f"{OUT}/mini-menu-disari.png")),
    lambda: cek("Click", *map(float, close_xy())),  # X: mini oynatıcı kapanmalı
    lambda: None,
    lambda: seen.update(closed_by_x=app.mini is None),
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
