"""Mini oynatıcı: telefonda çalanı küçük, ayrı bir pencerede gösterir.

İki hâli var:
- normal: solda kapak, sağda parça, oynat/duraklat, ses ve ince ilerleme;
- tepecik: tek satırlık ince şerit (küçük kapak, parça, dalga, oynat). Pencereyi ekranın üstüne sürükleyince
  (masaüstü normalde tam ekran yapardı) tepeciğe döner; X11 penceresiyse ekranın üst ortasına yerleşir.

Ayarlar ⋮ menüsünde: üstte tut, tepecik, boyut (küçük/orta/büyük), müzik başlayınca kendiliğinden açılma.
Başlık çubuğu yok; pencerenin her yerinden sürüklenir. Boyut ön ayarla değişir (set_default_size); pencere
yeniden boyutlanabilir kalır: boyutu sabit pencerenin içeriği büyüyünce GTK 4.6 Wayland'de protokol hatasıyla
uygulama kapanabiliyordu. Boş hâl ile çalan hâl aynı yeri kaplar.

Üstte tut (bkz. ustte): X11'de doğrudan; Wayland'de pencere XWayland'de açılır ve orada üstte tutulur;
XWayland de yoksa nasıl yapılacağı söylenir. Pencere hangi ekranda açılacağını oluşturulurken bilir; bu
yüzden Wayland'de üstte tutmayı açıp kapatmak pencereyi yeniden açar (app.set_mini_on_top).

Dalga gerçek sesten gelmez (telefon ses verisi göndermiyor): çalarken oynar, duraklayınca durur.
"""

import time

from gi.repository import Adw, Gio, GLib, Gtk, Pango

from . import compat, ustte

# boyut: (normal genişlik, kapak), (tepecik genişlik, kapak). Küçükte ses ve ilerleme çubuğu gizlenir.
SIZES = {"kucuk": ((340, 64), (300, 34)), "orta": ((440, 96), (340, 40)), "buyuk": ((560, 136), (400, 48))}
SIZE_NAMES = {"kucuk": "Küçük", "orta": "Orta", "buyuk": "Büyük"}
ART_WAIT_MS = 4000  # yeni kapak bu kadar gelmezse (kapaksız şarkı) eski kapak kaldırılır
TRACK_GAP_MS = 3000  # şarkı değişirken telefon bir an "çalmıyor" diyebilir: o arada boşa düşmesin
BLUR_CLOSE_MS = 250  # pencere bu kadar odaksız kalırsa açık menüler kapanır
MENU_WATCH_MS = 300  # XWayland'de menü açıkken odak bu aralıkla pencere yöneticisine sorulur


def _mmss(ms: int) -> str:
    s = max(0, int(ms) // 1000)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _small(icon, tooltip):
    return Gtk.Button(icon_name=icon, tooltip_text=tooltip, valign=Gtk.Align.CENTER,
                      css_classes=["flat", "circular", "mini-tool"])


class Wave(Gtk.Box):
    """Çalarken inip kalkan çubuklar (CSS animasyonu: yeniden yerleşim yok, işlemciyi yormaz)."""

    def __init__(self, height=16):
        super().__init__(spacing=2, valign=Gtk.Align.CENTER, height_request=height, css_classes=["mini-wave"])
        for i in range(4):
            self.append(Gtk.Box(width_request=3, css_classes=["bar", f"bar{i}"]))

    def set_playing(self, on):
        (self.add_css_class if on else self.remove_css_class)("playing")

    def set_loading(self, on):
        """Şarkılar arası geçiş: çubuklar sırayla hafifçe yanıp söner (çalmıyor gibi görünmesin)."""
        (self.add_css_class if on else self.remove_css_class)("loading")


def build_menu() -> Gio.Menu:
    menu = Gio.Menu()
    view = Gio.Menu()
    view.append("Üstte tut", "mini.top")
    view.append("Tepecik (ince şerit)", "mini.compact")
    menu.append_section(None, view)
    size = Gio.Menu()
    for key, name in SIZE_NAMES.items():
        item = Gio.MenuItem.new(name, None)
        item.set_action_and_target_value("mini.size", GLib.Variant("s", key))
        size.append_item(item)
    menu.append_submenu("Boyut", size)
    auto = Gio.Menu()
    auto.append("Müzik başlayınca kendiliğinden aç", "mini.auto")
    menu.append_section(None, auto)
    other = Gio.Menu()
    other.append("Talk To Android'i aç", "mini.home")
    other.append("Kapat", "mini.close")
    menu.append_section(None, other)
    return menu


class MiniPlayer(Adw.Window):
    WIDTH, HEIGHT = SIZES["orta"][0][0], 148

    def __init__(self, app, display=None):
        kw = {"display": display} if display is not None else {}
        super().__init__(application=app, title="Telefonda çalan", default_width=self.WIDTH,
                         default_height=self.HEIGHT, resizable=True, **kw)
        self.app = app
        self.device_id = None
        self.state: dict = {}
        self._pending: dict[str, int] = {}
        self._timers: dict[str, int] = {}
        self._art = None
        self._snapping = False
        cfg = app.config
        self.size_key = cfg["mini_size"] if cfg["mini_size"] in SIZES else "orta"
        self.compact = bool(cfg["mini_compact"])

        self._actions()
        menu = build_menu()
        self.toasts = Adw.ToastOverlay()
        handle = Gtk.WindowHandle()  # boş yerden tutup sürüklemek için
        self.stack = Gtk.Stack(hhomogeneous=False, vhomogeneous=False, interpolate_size=False)
        self.stack.add_named(self._normal(app, menu), "normal")
        self.stack.add_named(self._tepecik(menu), "tepecik")
        handle.set_child(self.stack)
        self.toasts.set_child(handle)
        self.set_content(self.toasts)

        twice = Gtk.GestureClick(button=1)  # tepecikte çift tık: normal hâle dön
        twice.connect("pressed", self._on_click)
        handle.add_controller(twice)

        self._timer = GLib.timeout_add(500, self._tick)
        self.connect("close-request", self._on_close)
        self.connect("notify::maximized", self._on_maximized)
        self.connect("notify::fullscreened", self._on_maximized)
        self.connect("map", lambda *_: GLib.timeout_add(150, self._after_map))
        # X11 penceresinde (Wayland'de üstte tutulurken XWayland) açık menü, masaüstünün Wayland tarafına yapılan
        # tıklamayı göremiyor ve kapanmıyordu: pencere odağı kaybedince menüler kapatılır. Menü açılırken X11'de
        # pencere bir anlığına odağı kaybedip geri alır; o an menüyü kapatmasın diye kısa bir süre beklenir.
        self._blur_id = 0
        self.connect("notify::is-active", self._on_active)
        # XWayland'de menü açıkken Wayland penceresine tıklanınca GTK odağın gittiğini hiç fark etmiyor; menü
        # açık kaldıkça pencere yöneticisine sorulur (ustte.is_focused).
        self._menu_watch = 0
        for b in (self.menu_button, self.c_menu_button):
            pop = b.get_popover()
            if pop is not None:
                pop.connect("notify::visible", self._on_menu_visible)
        if ustte.is_x11(self.get_display()) and not self.get_display().is_composited():
            self.add_css_class("x11-duz")  # saydamlık yoksa gölge payı ve yuvarlak köşeler siyah çıkar
        self.show_state(None, "", {"active": False})
        self._apply_mode()

    # ---- arayüz ------------------------------------------------------------------

    def _normal(self, app, menu):
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["mini-player"])
        top = Gtk.Box(spacing=14)

        self.art_stack = Gtk.Stack(valign=Gtk.Align.START)
        self.ph = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=30, css_classes=["art-placeholder"])
        self.pic = compat.picture(css_classes=["art"], overflow=Gtk.Overflow.HIDDEN)
        self.art_stack.add_named(self.ph, "yok")
        self.art_stack.add_named(self.pic, "var")
        top.append(self.art_stack)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True, valign=Gtk.Align.CENTER)
        head = Gtk.Box(spacing=2)
        self.wave = Wave(12)
        self.wave.set_margin_end(6)
        head.append(self.wave)
        self.source = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END,
                                css_classes=["caption", "dim-label"])
        head.append(self.source)
        self.menu_button = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu, valign=Gtk.Align.CENTER,
                                          tooltip_text="Ayarlar: üstte tut, tepecik, boyut",
                                          css_classes=["flat", "circular", "mini-tool"])
        head.append(self.menu_button)
        home = _small("go-home-symbolic", "Talk To Android'i aç")
        home.connect("clicked", lambda *_: app.present())
        head.append(home)
        close = _small("window-close-symbolic", "Kapat")
        close.connect("clicked", lambda *_: self.close())
        head.append(close)
        col.append(head)

        self.title_label = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, css_classes=["heading"])
        self.artist = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, css_classes=["dim-label"])
        col.append(self.title_label)
        col.append(self.artist)

        controls = Gtk.Box(spacing=4, margin_top=4)
        self.prev = _small("media-skip-backward-symbolic", "Önceki")
        self.prev.connect("clicked", lambda *_: self._cmd("previous"))
        self.play = Gtk.Button(icon_name="media-playback-start-symbolic", tooltip_text="Oynat / duraklat",
                               valign=Gtk.Align.CENTER, css_classes=["circular", "suggested-action", "mini-play"])
        self.play.connect("clicked", lambda *_: self._cmd("play_pause"))
        self.next = _small("media-skip-forward-symbolic", "Sonraki")
        self.next.connect("clicked", lambda *_: self._cmd("next"))
        for b in (self.prev, self.play, self.next):
            controls.append(b)
        controls.append(Gtk.Box(hexpand=True))
        self.vol_icon = Gtk.Image(icon_name="audio-volume-high-symbolic", css_classes=["dim-label"])
        controls.append(self.vol_icon)
        self.volume = Gtk.Scale(draw_value=False, width_request=96, valign=Gtk.Align.CENTER)
        self.volume.set_range(0, 100)
        self.volume.connect("change-value", self._on_volume)
        controls.append(self.volume)
        col.append(controls)
        top.append(col)
        root.append(top)

        bottom = self.bottom = Gtk.Box(spacing=8)
        self.pos_label = Gtk.Label(css_classes=["caption", "dim-label", "numeric"], width_chars=5, xalign=0)
        self.progress = Gtk.Scale(draw_value=False, hexpand=True, css_classes=["mini-progress"])
        self.progress.set_range(0, 1)
        self.progress.connect("change-value", self._on_seek)
        self.dur_label = Gtk.Label(css_classes=["caption", "dim-label", "numeric"], width_chars=5, xalign=1)
        for w in (self.pos_label, self.progress, self.dur_label):
            bottom.append(w)
        root.append(bottom)
        return root

    def _tepecik(self, menu):
        root = Gtk.Box(spacing=10, css_classes=["mini-tepecik"],
                       tooltip_text="Çift tıkla: büyüt")
        self.c_stack = Gtk.Stack(valign=Gtk.Align.CENTER)
        self.c_ph = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=18, css_classes=["art-placeholder"])
        self.c_pic = compat.picture(css_classes=["art"], overflow=Gtk.Overflow.HIDDEN)
        self.c_stack.add_named(self.c_ph, "yok")
        self.c_stack.add_named(self.c_pic, "var")
        root.append(self.c_stack)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        self.c_title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, css_classes=["heading", "mini-c-title"])
        self.c_artist = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, css_classes=["caption", "dim-label"])
        col.append(self.c_title)
        col.append(self.c_artist)
        root.append(col)
        self.c_wave = Wave(18)
        root.append(self.c_wave)
        self.c_play = Gtk.Button(icon_name="media-playback-start-symbolic", tooltip_text="Oynat / duraklat",
                                 valign=Gtk.Align.CENTER, css_classes=["circular", "flat", "mini-tool"])
        self.c_play.connect("clicked", lambda *_: self._cmd("play_pause"))
        root.append(self.c_play)
        self.c_next = _small("media-skip-forward-symbolic", "Sonraki")
        self.c_next.connect("clicked", lambda *_: self._cmd("next"))
        root.append(self.c_next)
        self.c_menu_button = Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu, valign=Gtk.Align.CENTER,
                                            tooltip_text="Ayarlar", css_classes=["flat", "circular", "mini-tool"])
        root.append(self.c_menu_button)
        return root

    def _actions(self):
        group = Gio.SimpleActionGroup()
        cfg = self.app.config

        def toggle(name, value, cb):
            a = Gio.SimpleAction.new_stateful(name, None, GLib.Variant("b", value))
            a.connect("change-state", lambda a, v: cb(v.get_boolean()))
            group.add_action(a)
            return a

        self.a_top = toggle("top", bool(cfg["mini_on_top"]), lambda on: self.app.set_mini_on_top(on))
        self.a_compact = toggle("compact", self.compact, self.set_compact)
        self.a_auto = toggle("auto", bool(cfg["mini_player_pinned"]), lambda on: self.app.set_pinned(on))
        self.a_size = Gio.SimpleAction.new_stateful("size", GLib.VariantType.new("s"),
                                                    GLib.Variant("s", self.size_key))
        self.a_size.connect("change-state", lambda a, v: self.set_size(v.get_string()))
        group.add_action(self.a_size)
        for name, cb in (("home", lambda: self.app.present()), ("close", lambda: self.close())):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", lambda *_, cb=cb: cb())
            group.add_action(a)
        self.insert_action_group("mini", group)

    def sync_actions(self):
        """Ayar başka yerden (Tercihler, app) değişince menüdeki işaretler de güncellensin."""
        cfg = self.app.config
        self.a_top.set_state(GLib.Variant("b", bool(cfg["mini_on_top"])))
        self.a_auto.set_state(GLib.Variant("b", bool(cfg["mini_player_pinned"])))

    # ---- boyut, tepecik, üstte tut ---------------------------------------------

    def set_size(self, key):
        if key not in SIZES:
            return
        self.size_key = key
        self.a_size.set_state(GLib.Variant("s", key))
        self.app.config.set("mini_size", key)
        self._apply_mode()

    def set_compact(self, on):
        self.compact = bool(on)
        self.a_compact.set_state(GLib.Variant("b", self.compact))
        self.app.config.set("mini_compact", self.compact)
        self._apply_mode()
        if self.compact and self.get_mapped():
            GLib.timeout_add(120, lambda: ustte.top_center(self) and False)

    def _apply_mode(self):
        (width, art), (c_width, c_art) = SIZES[self.size_key]
        for w in (self.ph, self.pic):
            w.set_size_request(art, art)
        self.ph.set_pixel_size(max(24, int(art / 2.5)))
        for w in (self.c_ph, self.c_pic):
            w.set_size_request(c_art, c_art)
        small, big = self.size_key == "kucuk", self.size_key == "buyuk"
        for w in (self.vol_icon, self.volume, self.bottom):
            w.set_visible(not small)
        self.title_label.set_css_classes(["title-3"] if big else ["heading"])
        self.stack.set_visible_child_name("tepecik" if self.compact else "normal")
        (self.add_css_class if self.compact else self.remove_css_class)("tepecik")
        target = c_width if self.compact else width
        h = self.stack.get_visible_child().measure(Gtk.Orientation.VERTICAL, target)[1]
        self.set_size_request(min(target, 300), h)
        self.set_default_size(target, h)

    def _on_maximized(self, *_):
        """Masaüstü pencereyi büyütmek ya da tam ekran yapmak isterse (ör. üste sürükleyince) tepeciğe dön."""
        if (self.is_maximized() or self.is_fullscreen()) and not self._snapping:
            self._snapping = True
            GLib.idle_add(self._snap)

    def _snap(self):
        if self.is_fullscreen():
            self.unfullscreen()
        self.unmaximize()
        if not self.compact:
            self.set_compact(True)
        GLib.timeout_add(250, self._after_snap)
        return False

    def _after_snap(self):
        # Büyütmeden dönen pencereye masaüstü eski boyutunu geri verir; tepecik boyutu yeniden uygulanır.
        self._snapping = False
        self.set_default_size(-1, -1)
        self._apply_mode()
        ustte.top_center(self)
        return False

    def _on_click(self, gesture, n_press, _x, _y):
        if n_press == 2 and self.compact:
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self.set_compact(False)

    def _on_active(self, *_):
        if self._blur_id:
            GLib.source_remove(self._blur_id)
            self._blur_id = 0
        if not self.is_active():
            self._blur_id = GLib.timeout_add(BLUR_CLOSE_MS, self._blurred)

    def _blurred(self):
        self._blur_id = 0
        if not self.is_active():
            self._close_menus()
        return False

    def _on_menu_visible(self, pop, _):
        if pop.get_visible() and not self._menu_watch and ustte.is_x11(self.get_display()):
            self._menu_watch = GLib.timeout_add(MENU_WATCH_MS, self._watch_menu)

    def _watch_menu(self):
        if not any(b.get_popover() and b.get_popover().get_visible() for b in (self.menu_button, self.c_menu_button)):
            self._menu_watch = 0
            return False
        if ustte.is_focused(self) is False:
            self._menu_watch = 0
            self._close_menus()
            return False
        return True

    def _close_menus(self):
        for b in (self.menu_button, self.c_menu_button):
            b.popdown()

    def _after_map(self):
        if self.app.config["mini_on_top"]:
            if ustte.supported(self) and ustte.keep_above(self, True):
                pass
            else:
                self.toast(ustte.WAYLAND_HINT, 8)
        if self.compact:
            ustte.top_center(self)
        return False

    def apply_top(self, on):
        """Aynı ekranda kalarak üstte tutmayı aç/kapat (X11 penceresi)."""
        return ustte.supported(self) and ustte.keep_above(self, on)

    # ---- düğmeler ---------------------------------------------------------------

    def toast(self, text, timeout=3):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=timeout))

    def _cmd(self, action, value=None):
        if self.device_id:
            self.app.call("media_control", self.device_id, action, value)

    def _later(self, action, value):
        """Sürüklerken her hareket telefona gitmesin: son değer 150 ms sonra bir kez gönderilir."""
        self._pending[action] = value
        if action not in self._timers:
            self._timers[action] = GLib.timeout_add(150, self._flush, action)

    def _flush(self, action):
        self._timers.pop(action, None)
        value = self._pending.pop(action, None)
        if value is not None:
            self._cmd(action, value)
        return False

    def _on_seek(self, _scale, _scroll, value):
        self._later("seek", int(value))
        self.state["position_ms"] = int(value)
        self.state["received_at"] = time.monotonic()
        return False

    def _on_volume(self, _scale, _scroll, value):
        self._later("volume", int(max(0, min(100, value))))
        return False

    def _on_close(self, *_):
        GLib.source_remove(self._timer)
        for attr in ("_blur_id", "_menu_watch"):
            if getattr(self, attr):
                GLib.source_remove(getattr(self, attr))
                setattr(self, attr, 0)
        for t in self._timers.values():
            GLib.source_remove(t)
        self._timers.clear()
        if self.app.mini is self:
            self.app.mini = None
        return False

    # ---- durum ------------------------------------------------------------------

    def set_loading(self, on):
        """Sıradaki şarkı bekleniyor (bkz. NowPlaying.loading): dalga "yükleniyor" olur, yazılar hafifçe söner."""
        on = bool(on) and bool(getattr(self, "state", None))
        for w in (self.wave, self.c_wave):
            w.set_loading(on)
            w.set_visible(w.get_visible() or on)
        for lbl in (self.title_label, self.c_title):
            (lbl.add_css_class if on else lbl.remove_css_class)("yukleniyor")

    def _art_wait_over(self):
        self._timers.pop("art_wait", None)
        self.app._refresh_mini()
        return False

    def _gap_over(self):
        self._timers.pop("gap", None)
        self._gap_done = True
        self.app._refresh_mini()
        return False

    def show_state(self, device_id, device_name, state, art_path=None):
        active = bool(device_id and state.get("active"))
        gap = self._timers.pop("gap", None)
        if active and gap:
            GLib.source_remove(gap)
        if not active and getattr(self, "state", None) and not getattr(self, "_gap_done", False):
            # Az önce çalıyordu: hemen "çalmıyor"a düşme, kısa bir süre son şarkı (duraklamış) kalsın.
            self._timers["gap"] = gap or GLib.timeout_add(TRACK_GAP_MS, self._gap_over)
            return  # düğmeler ve yazılar olduğu gibi kalır; "yükleniyor"u set_loading gösterir
        self._gap_done = False
        self.device_id = device_id if active else None
        self.state = dict(state) if active else {}
        for w in (self.prev, self.play, self.next, self.volume, self.progress, self.c_play, self.c_next):
            w.set_sensitive(active)
        playing = bool(active and state.get("playing"))
        self.wave.set_playing(playing)
        self.c_wave.set_playing(playing)
        self.wave.set_visible(active)
        if not active:
            self.source.set_text("Telefonda çalan")
            self.title_label.set_text("Şu an bir şey çalmıyor")
            self.artist.set_text("Spotify ya da YouTube'da müzik açınca burada görünür")
            self.c_title.set_text("Şu an bir şey çalmıyor")
            self.c_artist.set_text("Telefonda çalan")
            self.art_stack.set_visible_child_name("yok")
            self.c_stack.set_visible_child_name("yok")
            self._art = None  # sonraki şarkıda eski kapak "bekliyor" diye gösterilmesin
            for b in (self.play, self.c_play):
                b.set_icon_name("media-playback-start-symbolic")
            self.progress.set_range(0, 1)
            self.progress.set_value(0)
            self.pos_label.set_text("")
            self.dur_label.set_text("")
            return
        self.source.set_text(" · ".join(x for x in (state.get("player"), device_name) if x))
        title = state.get("title") or "Bilinmeyen parça"
        self.title_label.set_text(title)
        self.artist.set_text(state.get("artist") or "")
        self.c_title.set_text(title)
        self.c_artist.set_text(state.get("artist") or state.get("player") or "")
        icon = "media-playback-pause-symbolic" if playing else "media-playback-start-symbolic"
        for b in (self.play, self.c_play):
            b.set_icon_name(icon)
        dur = state.get("duration_ms") or 0
        self.progress.set_range(0, max(dur, 1))
        self.progress.set_sensitive(bool(state.get("can_seek")) and dur > 0)
        vol = state.get("volume")
        self.volume.set_sensitive(vol is not None)
        self.vol_icon.set_opacity(1 if vol is not None else 0.4)
        if vol is not None and not self._timers.get("volume"):
            self.volume.set_value(vol)
        if art_path and art_path != self._art:  # konum her güncellendiğinde kapak yeniden yüklenmesin
            self.pic.set_filename(art_path)
            self.c_pic.set_paintable(self.pic.get_paintable())
        # Yeni şarkının kapağı telefondan biraz sonra gelir: o arada boş simgeye düşmek yerine eski kapak soluk durur.
        if title != getattr(self, "_title", None):
            self._title, self._title_t = title, time.monotonic()
            if not art_path and self._art is not None and "art_wait" not in self._timers:
                self._timers["art_wait"] = GLib.timeout_add(ART_WAIT_MS + 50, self._art_wait_over)
        waiting = (not art_path and self._art is not None
                   and time.monotonic() - self._title_t < ART_WAIT_MS / 1000)
        for pic in (self.pic, self.c_pic):
            pic.set_opacity(0.4 if waiting else 1)
        if art_path:
            self._art = art_path
        name = "var" if (art_path or waiting) else "yok"
        self.art_stack.set_visible_child_name(name)
        self.c_stack.set_visible_child_name(name)
        self._tick()

    def _tick(self):
        st = self.state
        if not st or self._timers.get("seek"):
            return True
        pos = st.get("position_ms") or 0
        if st.get("playing") and st.get("received_at"):
            pos += int((time.monotonic() - st["received_at"]) * 1000)
        dur = st.get("duration_ms") or 0
        if dur:
            pos = min(pos, dur)
            self.progress.set_value(pos)
            self.pos_label.set_text(_mmss(pos))
            self.dur_label.set_text(_mmss(dur))
        else:
            self.pos_label.set_text("")
            self.dur_label.set_text("")
        return True
