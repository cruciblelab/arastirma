"""Mini oynatıcı: telefonda çalanı küçük, ayrı bir pencerede gösterir.

Tasarım: başlık çubuğu yok, pencerenin her yerinden sürüklenir; solda kapak, sağda parça, altında
oynat/duraklat ve ince ilerleme. Pencerenin boyutu içerikle değişmez (boş hâl ile çalan hâl aynı yeri
kaplar): yeniden boyutlanamayan pencerenin içeriği büyüyünce GTK 4.6 Wayland'de protokol hatasıyla
uygulamayı kapatabiliyordu.

📌 "Üstte tut": X11'de pencereyi diğerlerinin üstünde tutar; Wayland'de buna izin yok, nasıl yapılacağını
söyler (boş yere sağ tık → "Her zaman üstte"). Müzik başlayınca kendiliğinden açılması ayrı bir ayar
(Medya sayfası / Tercihler). Pencere menüsünü kendimiz açmaya çalışmak GTK 4.6 + Wayland'de çöküyordu;
o düğme kaldırıldı.
"""

import time

from gi.repository import Adw, GLib, Gtk, Pango

from . import compat, ustte


def _mmss(ms: int) -> str:
    s = max(0, int(ms) // 1000)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _pin_icon():
    from gi.repository import Gdk
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    return "view-pin-symbolic" if theme.has_icon("view-pin-symbolic") else "starred-symbolic"


def _small(icon, tooltip, toggle=False):
    cls = Gtk.ToggleButton if toggle else Gtk.Button
    return cls(icon_name=icon, tooltip_text=tooltip, valign=Gtk.Align.CENTER,
               css_classes=["flat", "circular", "mini-tool"])


class MiniPlayer(Adw.Window):
    WIDTH, HEIGHT = 440, 148

    def __init__(self, app):
        super().__init__(application=app, title="Telefonda çalan", default_width=self.WIDTH,
                         default_height=self.HEIGHT, resizable=True)
        self.set_size_request(360, self.HEIGHT)
        self.app = app
        self.device_id = None
        self.state: dict = {}
        self._pending: dict[str, int] = {}
        self._timers: dict[str, int] = {}
        self._art = None
        self._pin_guard = False

        self.toasts = Adw.ToastOverlay()
        handle = Gtk.WindowHandle()  # boş yerden tutup sürüklemek için
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["mini-player"])
        top = Gtk.Box(spacing=14)

        self.art_stack = Gtk.Stack(valign=Gtk.Align.START)
        ph = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=30, css_classes=["art-placeholder"],
                       width_request=76, height_request=76)
        self.pic = compat.picture(width_request=76, height_request=76, css_classes=["art"],
                                  overflow=Gtk.Overflow.HIDDEN)
        self.art_stack.add_named(ph, "yok")
        self.art_stack.add_named(self.pic, "var")
        top.append(self.art_stack)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True, valign=Gtk.Align.CENTER)
        head = Gtk.Box(spacing=2)
        self.source = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END,
                                css_classes=["caption", "dim-label"])
        head.append(self.source)
        self.pin = _small(_pin_icon(), "Üstte tut: diğer pencerelerin üstünde kalsın", toggle=True)
        self.pin.connect("toggled", self._on_pin)
        head.append(self.pin)
        self.hint = Gtk.Popover(child=Gtk.Label(label=ustte.WAYLAND_HINT, wrap=True, max_width_chars=34,
                                                margin_top=8, margin_bottom=8, margin_start=8, margin_end=8))
        self.hint.set_parent(self.pin)
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

        bottom = Gtk.Box(spacing=8)
        self.pos_label = Gtk.Label(css_classes=["caption", "dim-label", "numeric"], width_chars=5, xalign=0)
        self.progress = Gtk.Scale(draw_value=False, hexpand=True, css_classes=["mini-progress"])
        self.progress.set_range(0, 1)
        self.progress.connect("change-value", self._on_seek)
        self.dur_label = Gtk.Label(css_classes=["caption", "dim-label", "numeric"], width_chars=5, xalign=1)
        for w in (self.pos_label, self.progress, self.dur_label):
            bottom.append(w)
        root.append(bottom)

        handle.set_child(root)
        self.toasts.set_child(handle)
        self.set_content(self.toasts)
        self._timer = GLib.timeout_add(500, self._tick)
        self.connect("close-request", self._on_close)
        self.show_state(None, "", {"active": False})

    # ---- düğmeler ---------------------------------------------------------------

    def _on_pin(self, btn):
        """Üstte tut: X11'de gerçekten; Wayland'de yasak, nasıl yapılacağı gösterilir."""
        if self._pin_guard:
            return
        if ustte.supported(self) and ustte.keep_above(self, btn.get_active()):
            self.toast("Diğer pencerelerin üstünde" if btn.get_active() else "Artık üstte tutulmuyor")
            return
        self._pin_guard = True
        btn.set_active(False)
        self._pin_guard = False
        self.hint.popup()

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=3))

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
        self.hint.unparent()
        GLib.source_remove(self._timer)
        for t in self._timers.values():
            GLib.source_remove(t)
        self._timers.clear()
        self.app.mini = None
        return False

    # ---- durum ------------------------------------------------------------------

    def show_state(self, device_id, device_name, state, art_path=None):
        active = bool(device_id and state.get("active"))
        self.device_id = device_id if active else None
        self.state = dict(state) if active else {}
        for w in (self.prev, self.play, self.next, self.volume, self.progress):
            w.set_sensitive(active)
        if not active:
            self.source.set_text("Telefonda çalan")
            self.title_label.set_text("Şu an bir şey çalmıyor")
            self.artist.set_text("Spotify ya da YouTube'da müzik açınca burada görünür")
            self.art_stack.set_visible_child_name("yok")
            self.play.set_icon_name("media-playback-start-symbolic")
            self.progress.set_range(0, 1)
            self.progress.set_value(0)
            self.pos_label.set_text("")
            self.dur_label.set_text("")
            return
        self.source.set_text(" · ".join(x for x in (state.get("player"), device_name) if x))
        self.title_label.set_text(state.get("title") or "Bilinmeyen parça")
        self.artist.set_text(state.get("artist") or "")
        self.play.set_icon_name("media-playback-pause-symbolic" if state.get("playing")
                                else "media-playback-start-symbolic")
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
        self._art = art_path
        self.art_stack.set_visible_child_name("var" if art_path else "yok")
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
