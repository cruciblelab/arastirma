"""Ada Place: üst adanın temaları, canlı önizlemeyle (Ada sekmesinde).

Her kart küçük bir masaüstü gösterir: üst çubuk ve ondan sarkan ada (çalan şarkı, dalga ve temanın süsleri:
bulut, sis, yıldız...). Süsler adadakiyle aynı çizimdir (ada_sahne.py = gnome-ada/src/sahne.js). Karta tıklayınca
tema seçilir; ada da hemen değişir.

Boşuna çizmez: kartlar durgun bir resimdir; yalnızca farenin üstünde durduğu kart oynar, o da pencere öndeyken
(odaktayken), sekme görünürken ve sistemde canlandırmalar açıkken. (Seçili kartın da sürekli oynaması Talk To'ya
%4 iş çıkarıyordu: ölçüldü.) pycairo (python3-gi-cairo)
yoksa kartlar düz renkli durur.
"""

import math
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .. import ada_temalar  # noqa: E402
from . import ada_sahne  # noqa: E402
from . import compat  # noqa: E402,F401 (GTK 4.6'nın sonlandırma uyarısı süzgeci; tek başına kullanılınca da)

try:
    gi.require_foreign("cairo")
    HAVE_CAIRO = ada_sahne.cairo is not None
except ImportError:
    HAVE_CAIRO = False

CARD_W, CARD_H = 232, 70
FPS = 15
SCALE = 1.35  # önizlemedeki ada gerçeğinden biraz büyük (süsler seçilsin)


def water(cr, aw, ah, colors, radius, t, amp_level, sc=1.0):
    """Adanın alt kenarındaki su (eklentideki Water ile aynı biçim): şerit, adanın biçimine kırpılmış."""
    rgb = ada_sahne.rgb
    h = min(11 * sc, round(ah * 0.4))
    cr.save()
    ada_sahne.shape(cr, aw, ah, radius)
    cr.clip()
    cr.translate(0, ah - h)
    base, amp, phase = h * 0.6, h * 1.6 * amp_level, t * 4
    for color, alpha, speed, shift in ((colors["wave2"], 0.45, 1.0, 0.0), (colors["wave1"], 0.8, 1.6, 1.7)):
        cr.move_to(0, h)
        x = 0.0
        while x <= aw + 3:
            cr.line_to(x, base + amp * (math.sin(x / (22 * sc) + phase * speed + shift) +
                                        0.35 * math.sin(x / (9.5 * sc) - phase * speed * 1.3)))
            x += 3
        cr.line_to(aw, h)
        cr.close_path()
        cr.set_source_rgba(*rgb(color), alpha)
        cr.fill()
    cr.restore()


def draw_card(cr, w, h, theme, t, playing=True, clock="13:15"):
    """Bir kartın resmi: masaüstü, üst çubuk ve sarkan ada (ada_sahne ile süsler)."""
    rgb = ada_sahne.rgb
    # masaüstü ve üst çubuk (temadan bağımsız, hep aynı: temalar yan yana karşılaştırılsın)
    g = ada_sahne.cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgba(0, *rgb("#3d3846"), 1)
    g.add_color_stop_rgba(1, *rgb("#5e5c64"), 1)
    cr.set_source(g)
    cr.rectangle(0, 0, w, h)
    cr.fill()
    bar = 12
    cr.set_source_rgba(0, 0, 0, 1)
    cr.rectangle(0, 0, w, bar)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, 0.85)
    cr.select_font_face("Sans", ada_sahne.cairo.FONT_SLANT_NORMAL, ada_sahne.cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(8)
    cr.move_to(w / 2 - 12, 9)
    cr.show_text(clock)

    colors = theme["colors"]
    sc = SCALE
    aw, ah = min(w - 24, 176), 29 * sc
    x0, y0 = (w - aw) / 2, bar
    radius = min(18 * sc, ah / 2)
    cr.save()
    cr.translate(x0, y0)
    # Adadaki sıra: zemin, süsler, alttaki su, en üstte yazı
    ada_sahne.background(cr, aw, ah, colors, radius)
    ada_sahne.paint(cr, aw, ah, t, theme["fx"], scale=sc, radius=radius)
    water(cr, aw, ah, colors, radius, t, 0.22 if playing else 0.05, sc)
    cr.set_source_rgba(*rgb(colors["text"]), 1)
    cr.select_font_face("Sans", ada_sahne.cairo.FONT_SLANT_NORMAL, ada_sahne.cairo.FONT_WEIGHT_BOLD)
    cr.set_font_size(9.5 * sc)
    cr.move_to(14 * sc, ah / 2 + 3.3 * sc)
    cr.show_text("Firuze")
    cr.select_font_face("Sans", ada_sahne.cairo.FONT_SLANT_NORMAL, ada_sahne.cairo.FONT_WEIGHT_NORMAL)
    cr.set_source_rgba(*rgb(colors["text"]), 0.72)
    cr.set_font_size(8.5 * sc)
    cr.move_to(aw - 34 * sc, ah / 2 + 3 * sc)
    cr.show_text("%76")
    cr.restore()


def _fallback_css(themes) -> str:
    rules = []
    for key, th in themes.items():
        c = th["colors"]
        rules.append(f".ada-ornek-{key} {{ background-image: linear-gradient(to bottom, {c['bg1']}, {c['bg2']}); "
                     f"border-bottom: 4px solid {c['wave1']}; border-radius: 0 0 16px 16px; }}")
    return "\n".join(rules)


class ThemeCard(Gtk.Button):
    def __init__(self, key, theme, on_pick, on_hover, place=None):
        super().__init__(css_classes=["flat", "ada-kart", f"ada-kart-{key}"], tooltip_text=theme["desc"])
        self.key, self.theme, self.place = key, theme, place
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        if HAVE_CAIRO:
            self.area = Gtk.DrawingArea(content_width=CARD_W, content_height=CARD_H, css_classes=["ada-kart-resim"],
                                        overflow=Gtk.Overflow.HIDDEN)
            self.area.set_draw_func(self._draw)
            box.append(self.area)
        else:
            self.area = None
            box.append(Gtk.Box(css_classes=[f"ada-ornek-{key}"], width_request=CARD_W - 40, height_request=36,
                               halign=Gtk.Align.CENTER))
        head = Gtk.Box(spacing=6)
        head.append(Gtk.Label(label=theme["name"], xalign=0, hexpand=True, css_classes=["ada-kart-ad"]))
        # Simge değil yazı: GTK 4.6'da çok sayıda GtkImage yok edilirken kritik uyarı basılıyor.
        self.check = Gtk.Label(label="✓", visible=False, css_classes=["accent", "ada-kart-ad"])
        head.append(self.check)
        box.append(head)
        desc = Gtk.Label(label=theme["desc"], xalign=0, wrap=True, max_width_chars=28, css_classes=["dim-label", "caption"])
        box.append(desc)
        self.set_child(box)
        self.connect("clicked", lambda *_: on_pick(key))
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: on_hover(key, True))
        motion.connect("leave", lambda *_: on_hover(key, False))
        self.add_controller(motion)
        self.t = 8.0  # durgun resim: süsler dağılmış hâlde

    def _draw(self, _area, cr, w, h):
        theme, clock = self.theme, "13:15"
        cycle_on = self.place.cycle if self.place is not None else True
        if "cycle" in theme and (not theme.get("cycle_optional") or cycle_on):
            # saate göre: durgunken şimdiki saat, oynarken (fare üstündeyken) bütün gün 12 saniyede geçer
            lt = time.localtime()
            hour = (lt.tm_hour + lt.tm_min / 60 + (self.t - 8.0) * 2) % 24
            theme = ada_temalar.resolve(theme, hour, cycle_on)
            clock = f"{int(hour):02d}:{int(hour % 1 * 60):02d}"
        draw_card(cr, w, h, theme, self.t, clock=clock)

    def set_selected(self, on):
        self.check.set_visible(on)
        if on:
            self.add_css_class("secili")
        else:
            self.remove_css_class("secili")

    def tick(self, t):
        self.t = t
        if self.area is not None:
            self.area.queue_draw()


class AdaPlace(Adw.PreferencesGroup):
    """Tema galerisi: gruplar (tatlı, sakin, havalı), her temanın canlı önizlemesi."""

    def __init__(self, current: str, on_pick, cycle: bool = True):
        super().__init__(title="Ada Place",
                         description="Adanın görünümleri, tatlıdan havalıya. Birine tıkla: ada hemen değişir. "
                                     "Süsler adanın üstünden saydam geçer; yazıları kapatmaz, aramada çekilir.")
        self.cards: dict[str, ThemeCard] = {}
        self.cycle = cycle  # saate göre değişen temalar (Ada sekmesindeki anahtar)
        self._timer = 0
        self._t0 = time.monotonic()
        self.hovered = None
        self.selected = current
        self._root = None
        self._root_sig = 0
        if not HAVE_CAIRO:
            css = Gtk.CssProvider()
            css.load_from_data(_fallback_css(ada_temalar.THEMES).encode())
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self.add(Gtk.Label(label="Canlı önizleme için python3-gi-cairo paketi gerekli (yalnızca renkler "
                                     "gösteriliyor).", wrap=True, xalign=0, css_classes=["dim-label", "caption"]))
        for group, label in ada_temalar.GROUPS.items():
            self.add(Gtk.Label(label=label, xalign=0, css_classes=["heading"], margin_top=10, margin_bottom=4))
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, min_children_per_line=1,
                               max_children_per_line=4, column_spacing=8, row_spacing=8)
            for key, th in ada_temalar.THEMES.items():
                if th["group"] == group:
                    card = self.cards[key] = ThemeCard(key, th, on_pick, self._hover, self)
                    flow.append(card)
            self.add(flow)
        self.select(current)
        self.connect("map", lambda *_: self._mapped(True))
        self.connect("unmap", lambda *_: self._mapped(False))

    def set_cycle(self, on):
        self.cycle = on
        for card in self.cards.values():
            if card.area is not None and card.theme.get("cycle_optional"):
                card.area.queue_draw()

    def select(self, key):
        self.selected = key
        for k, card in self.cards.items():
            card.set_selected(k == key)
        self._update()

    def _hover(self, key, inside):
        if inside:
            self.hovered = key
        elif self.hovered == key:
            self.hovered = None
        self._update()

    def _mapped(self, on):
        # Pencerenin önde olup olmadığı (odak) değişince de karar yeniden verilir.
        if self._root is not None and self._root_sig:
            self._root.disconnect(self._root_sig)
            self._root, self._root_sig = None, 0
        if on:
            root = self.get_root()
            if root is not None and hasattr(root, "is_active"):
                self._root = root
                self._root_sig = root.connect("notify::is-active", lambda *_: self._update())
        self._update()

    def playing(self) -> list:
        """Şu an oynayan kartlar: yalnızca farenin üstündeki."""
        return [self.hovered] if self.hovered in self.cards else []

    def _wanted(self) -> bool:
        if not HAVE_CAIRO or not self.get_mapped() or not self.playing():
            return False
        s = Gtk.Settings.get_default()
        if s is not None and not s.get_property("gtk-enable-animations"):
            return False
        root = self.get_root()
        if root is None or (hasattr(root, "is_active") and not root.is_active()):
            return False  # pencere arkada: kullanıcı başka işte
        return not self._hidden()

    def _update(self):
        want = self._wanted()
        if want and not self._timer:
            self._timer = GLib.timeout_add(1000 // FPS, self._frame)
        elif not want and self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _hidden(self) -> bool:
        """Pencere simge durumunda ya da görünmüyor (GTK 4.12+ "askıda"): kimse bakmıyor, çizme."""
        root = self.get_root()
        surface = root.get_surface() if root is not None else None
        if surface is None or not hasattr(surface, "get_state"):
            return False
        flags = Gdk.ToplevelState.MINIMIZED | getattr(Gdk.ToplevelState, "SUSPENDED", 0)
        return bool(surface.get_state() & flags)

    def _frame(self):
        if not self._wanted():
            self._timer = 0
            return False
        t = time.monotonic() - self._t0 + 8.0
        for key in self.playing():
            self.cards[key].tick(t)
        return True
