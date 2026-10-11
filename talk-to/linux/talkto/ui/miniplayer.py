"""Mini oynatıcı: telefonda çalanı küçük, ayrı bir pencerede gösterir.

"Sabitle" açıkken müzik başlayınca kendiliğinden açılır. Uygulama pencereyi diğerlerinin üstünde
tutamaz (Wayland buna izin vermez, GTK 4'te böyle bir çağrı da yok); "Üstte tut" düğmesi pencere
yöneticisinin kendi menüsünü açar, oradan "Her zaman üstte" seçilir.
"""

from gi.repository import Adw, Gtk, GLib

from .window import MediaCard


def _pin_icon():
    from gi.repository import Gdk
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    return "view-pin-symbolic" if theme.has_icon("view-pin-symbolic") else "starred-symbolic"


class MiniPlayer(Adw.Window):
    def __init__(self, app):
        super().__init__(application=app, title="Telefonda çalan", default_width=440, resizable=False)
        self.app = app
        self.card: MediaCard | None = None

        self.toasts = Adw.ToastOverlay()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar(css_classes=["flat"])
        self.title = Adw.WindowTitle(title="Telefonda çalan")
        header.set_title_widget(self.title)

        self.pin = Gtk.ToggleButton(icon_name=_pin_icon(), active=app.config["mini_player_pinned"])
        self.pin.connect("toggled", self._on_pin)
        self._pin_tooltip()
        header.pack_start(self.pin)

        # Pencere menüsü yalnızca bir tıklama olayıyla açılabilir: düğmenin kendi tıklamasından önce yakalanır.
        top = Gtk.Button(icon_name="go-top-symbolic", tooltip_text="Diğer pencerelerin üstünde tut")
        click = Gtk.GestureClick(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", self._on_top)
        top.add_controller(click)
        header.pack_start(top)

        home = Gtk.Button(icon_name="go-home-symbolic", tooltip_text="Talk To Android'i aç")
        home.connect("clicked", lambda *_: app.present())
        header.pack_end(home)
        box.append(header)

        self.stack = Gtk.Stack(margin_start=14, margin_end=14, margin_bottom=14)
        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER,
                        height_request=120)
        empty.append(Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=32, css_classes=["dim-label"]))
        empty.append(Gtk.Label(label="Telefonda çalan bir şey yok", css_classes=["heading"]))
        self.empty_sub = Gtk.Label(label="Spotify ya da YouTube'da müzik açınca burada görünür.",
                                   wrap=True, justify=Gtk.Justification.CENTER, css_classes=["dim-label"])
        empty.append(self.empty_sub)
        self.stack.add_named(empty, "yok")
        self.holder = Gtk.Box()
        self.stack.add_named(self.holder, "var")
        box.append(self.stack)
        self.toasts.set_child(box)
        self.set_content(self.toasts)
        self._timer = GLib.timeout_add(500, self._tick)
        self.connect("close-request", self._on_close)

    def _pin_tooltip(self):
        self.pin.set_tooltip_text("Sabitlendi: müzik başlayınca kendiliğinden açılır" if self.pin.get_active() else
                                  "Sabitle: müzik başlayınca kendiliğinden açılsın")

    def _on_pin(self, btn):
        self.app.set_pinned(btn.get_active())
        self._pin_tooltip()
        self.toast("Müzik başlayınca mini oynatıcı kendiliğinden açılacak" if btn.get_active() else
                   "Sabitleme kaldırıldı")

    def sync_pin(self):
        if self.pin.get_active() != self.app.config["mini_player_pinned"]:
            self.pin.set_active(self.app.config["mini_player_pinned"])

    def _on_top(self, gesture, _n, _x, _y):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        surface = self.get_surface()
        shown = False
        try:
            shown = bool(surface and surface.show_window_menu(gesture.get_current_event()))
        except (AttributeError, TypeError):
            pass
        self.toast("Açılan menüden “Her zaman üstte”yi seç" if shown else
                   "Alt+Boşluk ile pencere menüsünü aç ve “Her zaman üstte”yi seç")

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=3))

    def _on_close(self, *_):
        GLib.source_remove(self._timer)
        self.app.mini = None
        return False

    def _tick(self):
        if self.card and self.get_visible():
            self.card.tick()
        return True

    def show_state(self, device_id, device_name, state, art_path=None):
        if not device_id or not state.get("active"):
            self.stack.set_visible_child_name("yok")
            return
        if not self.card or self.card.device_id != device_id:
            if self.card:
                self.holder.remove(self.card)
            self.card = MediaCard(self, device_id, compact=True)
            self.card.set_hexpand(True)
            self.holder.append(self.card)
        self.card.update(device_name, state)
        self.card.set_art(art_path)
        self.stack.set_visible_child_name("var")
