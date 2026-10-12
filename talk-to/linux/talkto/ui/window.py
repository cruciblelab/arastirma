"""Ana pencere: Telefonlar · Medya · Dosyalar · Bildirimler · Komutlar; ayrıca Tercihler penceresi."""

import json
import time
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango

from .. import features, pc, setup_checks
from ..config import Config
from . import compat, system

KIND = {"usb": "USB", "wifi": "Wi-Fi", "bluetooth": "Bluetooth"}


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return str(n)


def mmss(ms: int) -> str:
    s = max(0, int(ms) // 1000)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


row = compat.row


def icon_button(icon, tooltip, cb, *classes):
    b = Gtk.Button(icon_name=icon, tooltip_text=tooltip, valign=Gtk.Align.CENTER,
                   css_classes=["flat", *classes])
    b.connect("clicked", lambda *_: cb())
    return b


class DynamicGroup(Adw.PreferencesGroup):
    """Satırları sık sık baştan kurulan grup."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.rows = []

    def set_rows(self, rows):
        for r in self.rows:
            self.remove(r)
        self.rows = list(rows)
        for r in self.rows:
            self.add(r)


class MediaCard(Gtk.Box):
    """Çalan parça kartı. compact: mini oynatıcıdaki küçük hali (çerçevesiz, küçük kapak)."""

    def __init__(self, win, device_id, compact=False):
        super().__init__(spacing=14 if compact else 18,
                         css_classes=["media-mini"] if compact else ["card", "media-card"])
        self.win, self.device_id = win, device_id
        self.state = {}
        self.art_id = None
        art = 88 if compact else 128

        self.art_stack = Gtk.Stack(valign=Gtk.Align.START)
        ph = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=36 if compact else 48,
                       css_classes=["art-placeholder"], width_request=art, height_request=art)
        self.pic = compat.picture(width_request=art, height_request=art,
                               css_classes=["art"], overflow=Gtk.Overflow.HIDDEN)
        self.art_stack.add_named(ph, "yok")
        self.art_stack.add_named(self.pic, "var")
        self.append(self.art_stack)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.source = Gtk.Label(xalign=0, css_classes=["caption", "dim-label"], ellipsize=Pango.EllipsizeMode.END)
        self.title = Gtk.Label(xalign=0, css_classes=["heading" if compact else "title-3"],
                               ellipsize=Pango.EllipsizeMode.END)
        self.artist = Gtk.Label(xalign=0, css_classes=["dim-label"], ellipsize=Pango.EllipsizeMode.END)
        for w in (self.source, self.title, self.artist):
            col.append(w)

        self.progress = Gtk.Scale(draw_value=False, hexpand=True, margin_top=2 if compact else 6)
        self.progress.set_range(0, 1)
        self.progress.connect("change-value", self._on_seek)
        col.append(self.progress)
        times = Gtk.Box(css_classes=["caption", "dim-label"])
        self.pos_label = Gtk.Label(xalign=0, hexpand=True)
        self.dur_label = Gtk.Label(xalign=1)
        times.append(self.pos_label)
        times.append(self.dur_label)
        col.append(times)

        controls = Gtk.Box(spacing=8 if compact else 12, halign=Gtk.Align.CENTER, margin_top=0 if compact else 4)
        controls.append(icon_button("media-skip-backward-symbolic", "Önceki",
                                    lambda: self._cmd("previous"), "circular"))
        self.play = Gtk.Button(icon_name="media-playback-start-symbolic", tooltip_text="Oynat / duraklat",
                               css_classes=["circular", "suggested-action", "play-button"],
                               valign=Gtk.Align.CENTER)
        self.play.connect("clicked", lambda *_: self._cmd("play_pause"))
        controls.append(self.play)
        controls.append(icon_button("media-skip-forward-symbolic", "Sonraki",
                                    lambda: self._cmd("next"), "circular"))
        col.append(controls)

        vol = Gtk.Box(spacing=6, margin_top=2)
        vol.append(Gtk.Image(icon_name="audio-volume-high-symbolic", css_classes=["dim-label"]))
        self.volume = Gtk.Scale(draw_value=False, hexpand=True)
        self.volume.set_range(0, 100)
        self.volume.connect("change-value", self._on_volume)
        vol.append(self.volume)
        self.vol_box = vol
        col.append(vol)
        self.append(col)
        self._pending: dict[str, int] = {}
        self._timers: dict[str, int] = {}

    def _cmd(self, action, value=None):
        self.win.app.call("media_control", self.device_id, action, value)

    def _later(self, action, value):
        """Sürüklerken her fare hareketi telefona gitmesin: son değer 150 ms sonra bir kez gönderilir."""
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

    def update(self, device_name, st):
        self.state = dict(st)
        self.source.set_text(f"{device_name} · {st.get('player') or 'Medya'}")
        self.title.set_text(st.get("title") or "Bilinmeyen parça")
        self.artist.set_text(st.get("artist") or "")
        self.artist.set_visible(bool(st.get("artist")))
        self.play.set_icon_name("media-playback-pause-symbolic" if st.get("playing")
                                else "media-playback-start-symbolic")
        dur = st.get("duration_ms") or 0
        self.progress.set_visible(dur > 0)
        self.progress.set_sensitive(bool(st.get("can_seek")))
        self.progress.set_range(0, max(dur, 1))
        self.vol_box.set_visible(st.get("volume") is not None)
        if st.get("volume") is not None:
            self.volume.set_value(st["volume"])
        self.tick()

    def set_art(self, path):
        if path:
            self.pic.set_filename(path)
            self.art_stack.set_visible_child_name("var")
        else:
            self.art_stack.set_visible_child_name("yok")

    def tick(self):
        st = self.state
        pos = st.get("position_ms") or 0
        if st.get("playing") and st.get("received_at"):
            pos += int((time.monotonic() - st["received_at"]) * 1000)
        dur = st.get("duration_ms") or 0
        if dur:
            pos = min(pos, dur)
            self.progress.set_value(pos)
            self.pos_label.set_text(mmss(pos))
            self.dur_label.set_text(mmss(dur))
        else:
            self.pos_label.set_text("")
            self.dur_label.set_text("")


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Talk To Android", default_width=920, default_height=700)
        self.app = app
        self.set_size_request(360, 480)
        self.status = {}
        self.usb = {}
        self._updating = False
        self.transfers: dict[str, dict] = {}
        self._tr_rows: dict[str, tuple] = {}  # anahtar → (satır, ilerleme çubuğu)
        self._running_cmds: set[str] = set()  # "Burada dene" ile süren komutlar
        self.media_cards: dict[str, MediaCard] = {}
        self.art_paths: dict[str, str] = {}
        self.ringing: set[str] = set()

        self.toasts = Adw.ToastOverlay()
        view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        self.stack = Adw.ViewStack(vexpand=True)
        bottom = Adw.ViewSwitcherBar(stack=self.stack)
        if hasattr(Adw, "Breakpoint"):  # libadwaita 1.4+
            switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
            header.set_title_widget(switcher)
            bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
            bp.add_setter(bottom, "reveal", True)
            bp.add_setter(switcher, "visible", False)
            self.add_breakpoint(bp)
        else:  # eski libadwaita: dar pencerede başlık sığmazsa sekmeler alta iner
            title = Adw.ViewSwitcherTitle(stack=self.stack, title="Talk To Android")
            header.set_title_widget(title)
            title.bind_property("title-visible", bottom, "reveal", GObject.BindingFlags.SYNC_CREATE)
        menu = Gio.Menu()
        menu.append("Mini oynatıcı", "app.mini-player")
        menu.append("Tercihler", "app.preferences")
        menu.append("Kurulum yardımcısı", "app.setup")
        menu.append("Hakkında", "app.about")
        menu.append("Tamamen kapat", "app.quit")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Menü"))
        view.append(header)
        self.banner = compat.Banner()
        view.append(self.banner)
        view.append(self.stack)
        view.append(bottom)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        # GNOME HIG: görünüm değiştiricide 3–5 görünüm. Bağlantı yolları ve genel ayarlar Tercihler'de.
        self._sig = {}
        self.f = features.enabled(app.config)
        # Araçlar (bilgisayar komutları, telefon araçları, terminal): ana pencerede sekme değil, Tercihler'de.
        self.prefs_pages = [self._build_features(), self._build_preferences(), self._build_commands()]
        self.prefs_window = None
        # Basit modda Dosyalar sayfası gizlenir (talkto.features).
        self.pages = {
            "telefonlar": compat.add_page(self.stack, self._build_phones(), "telefonlar", "Telefonlar",
                                          "phone-symbolic"),
            "medya": compat.add_page(self.stack, self._build_media(), "medya", "Medya",
                                     "media-playback-start-symbolic"),
            "dosyalar": compat.add_page(self.stack, self._build_files(), "dosyalar", "Dosyalar", "folder-symbolic"),
            "bildirimler": compat.add_page(self.stack, self._build_notifications(), "bildirimler", "Bildirimler",
                                           "preferences-system-notifications-symbolic"),
        }

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        drop.connect("enter", lambda *_: self.dropzone.add_css_class("drop-active") or Gdk.DragAction.COPY)
        drop.connect("leave", lambda *_: self.dropzone.remove_css_class("drop-active"))
        self.add_controller(drop)

        act = Gio.SimpleAction.new("usb", GLib.VariantType.new("s"))
        act.connect("activate", self._on_usb_action)
        self.add_action(act)
        act = Gio.SimpleAction.new("phone", GLib.VariantType.new("s"))
        act.connect("activate", self._on_phone_action)
        self.add_action(act)

        self.apply_features()
        GLib.timeout_add(500, self._tick)

    # ---- yardımcılar --------------------------------------------------------

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=3))

    def _set(self, key, value):
        if not self._updating:
            self.app.call("set_option", key, value)

    def target(self):
        """Dosya/medya için hedef: en son bağlanan telefon."""
        sessions = self.status.get("sessions") or []
        return sessions[-1] if sessions else None

    def open_preferences(self, page=None):
        """Özellikler, bağlantı yolları ve genel ayarlar (Ctrl+,): ayrı pencere, ana pencere sade kalır."""
        if self.prefs_window is None:
            self.prefs_window = Adw.PreferencesWindow(transient_for=self, title="Tercihler", modal=False,
                                                      hide_on_close=True, default_width=640, default_height=720)
            for p in self.prefs_pages:
                self.prefs_window.add(p)
        if page is not None:
            self.prefs_window.set_visible_page(self.prefs_pages[page])
        self._update_data_rows()
        self.prefs_window.present()

    # ---- basit mod -------------------------------------------------------------

    def _build_features(self):
        page = Adw.PreferencesPage(title="Özellikler", icon_name="view-grid-symbolic")
        g = Adw.PreferencesGroup(
            description="Hafif telefon sürümünden farklı: hiçbir şey kaldırılmaz, yalnızca ekran sadeleşir. "
                        "Telefonun neye izinli olduğunu profili belirler.")
        self.sw_simple = compat.SwitchRow(
            title="Basit mod", subtitle="Yalnızca bildirimler, çalan müzik ve telefonu bul görünür")
        self.sw_simple.set_active(self.app.config["simple_mode"])
        self.sw_simple.connect("notify::active", lambda r, _: self._set_feature_option("simple_mode", r.get_active()))
        g.add(self.sw_simple)
        page.add(g)

        self.extras_group = Adw.PreferencesGroup(
            title="Basit modda da göster", description="İhtiyaç duyduğunda tek tek ekle.")
        self.sw_extras = {}
        for key, (title, sub) in features.EXTRAS.items():
            sw = compat.SwitchRow(title=title, subtitle=sub, active=key in self.app.config["extras"])
            sw.connect("notify::active", lambda r, _, k=key: self._set_extra(k, r.get_active()))
            self.extras_group.add(sw)
            self.sw_extras[key] = sw
        page.add(self.extras_group)
        return page

    def _set_feature_option(self, key, value):
        if self._updating:
            return
        self.app.config.set(key, value)
        self.apply_features()

    def _set_extra(self, key, on):
        extras = [k for k in self.app.config["extras"] if k != key] + ([key] if on else [])
        self._set_feature_option("extras", extras)

    def apply_features(self):
        """Basit mod ve eklenen özelliklere göre sayfaları, düğmeleri ve grupları gösterir/gizler."""
        cfg = self.app.config
        self.f = features.enabled(cfg)
        simple = cfg["simple_mode"]
        self.extras_group.set_sensitive(simple)
        self.pages["dosyalar"].set_visible("files" in self.f)
        for g in self.cmd_groups:
            g.set_visible("commands" in self.f)
        self.cmd_off.set_visible("commands" not in self.f)
        self.mirror_group.set_visible("mirror" in self.f)
        if not self.pages.get(self.stack.get_visible_child_name()).get_visible():
            self.stack.set_visible_child_name("telefonlar")
        self.profile_group.set_visible("profiles" in self.f)
        hidden = [features.EXTRAS[k][0].lower() for k in features.EXTRAS if k not in self.f]
        self.simple_row.set_subtitle("Gizli: " + ", ".join(hidden) + ". Tercihler → Özellikler'den eklenir."
                                     if hidden else "Bütün eklenebilir özellikler açık.")
        self.simple_group.set_visible(simple)
        if self.status:
            self._sig.pop("trusted", None)
            self._update_devices()
            self._update_hero()
        if self.usb:
            self.update_usb(self.usb)

    # ---- Telefonlar -----------------------------------------------------------

    def _build_phones(self):
        """İlk sayfa: durum, bağlı telefon, USB'deki telefonun işleri, eşleşmiş telefonlar, profiller (L2)."""
        page = Adw.PreferencesPage()

        hero_group = Adw.PreferencesGroup()
        hero = Gtk.Box(spacing=18, css_classes=["hero"])
        icon_box = Gtk.Box(css_classes=["hero-icon-box"], valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        self.hero_icon = Gtk.Image(icon_name="computer-symbolic", pixel_size=36, width_request=64,
                                   height_request=64)
        icon_box.append(self.hero_icon)
        hero.append(icon_box)
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER, hexpand=True)
        self.hero_title = Gtk.Label(xalign=0, wrap=True, css_classes=["title-1"])
        self.hero_sub = Gtk.Label(xalign=0, wrap=True, css_classes=["hero-sub"])
        self.hero_chips = Gtk.Box(spacing=6, margin_top=6)
        texts.append(self.hero_title)
        texts.append(self.hero_sub)
        texts.append(self.hero_chips)
        self.hero_button = Gtk.Button(label="Bağlantı ayarları", halign=Gtk.Align.START, margin_top=6,
                                      css_classes=["pill", "hero-button"])
        self.hero_button.connect("clicked", lambda *_: self._on_hero_button())
        texts.append(self.hero_button)
        hero.append(texts)
        hero_group.add(hero)
        page.add(hero_group)

        # Her telefon tek satır: bağlantı, USB ve eşleşme aynı yerde (eskiden aynı telefon üç grupta görünüyordu).
        self.phones_group = DynamicGroup(title="Telefonlar")
        page.add(self.phones_group)
        self._trusted_open = False
        self.profile_group = DynamicGroup(
            title="Profiller",
            description="Profil, telefonun bu bilgisayarda neler yapabileceğini belirler; değişiklik bağlı telefona "
                        "hemen uygulanır.")
        add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Yeni profil", css_classes=["flat"],
                         valign=Gtk.Align.CENTER)
        add.connect("clicked", lambda *_: self.app.call("save_profile", None, {"name": "Yeni profil"}))
        self.profile_group.set_header_suffix(add)
        page.add(self.profile_group)

        self.simple_group = Adw.PreferencesGroup()
        self.simple_row = row("Basit mod açık", "")
        self.simple_row.set_subtitle_lines(3)
        self.simple_row.add_prefix(Gtk.Image(icon_name="view-grid-symbolic"))
        b = Gtk.Button(label="Özellik ekle", valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda *_: self.open_preferences(0))
        self.simple_row.add_suffix(b)
        self.simple_group.add(self.simple_row)
        page.add(self.simple_group)
        return page

    # ---- Tercihler (bağlantı yolları ve genel) -----------------------------------

    def _build_preferences(self):
        page = Adw.PreferencesPage(title="Bağlantı", icon_name="network-wireless-symbolic")

        g = self.wifi_group = Adw.PreferencesGroup(title="Kablosuz (Wi-Fi)")
        self.sw_wireless = compat.SwitchRow(title="Kablosuz bağlantıyı aç",
                                         subtitle="Açıkken bu bilgisayar yerel ağda görünür")
        self.sw_wireless.connect("notify::active", lambda r, _: self._set("wireless", r.get_active()))
        g.add(self.sw_wireless)
        self.addr_row = Adw.ActionRow(title="Adres", css_classes=["property"])
        self.addr_row.add_suffix(icon_button("edit-copy-symbolic", "Kopyala", self._copy_address))
        g.add(self.addr_row)
        self.pw_row = compat.PasswordEntryRow(title="Şifre (isteğe bağlı)", show_apply_button=True)
        self.pw_row.set_text(self.app.config["password"])
        self.pw_row.connect("apply", self._on_password)
        g.add(self.pw_row)
        self.fp_row = Adw.ActionRow(
            title="Güvenlik kodu", css_classes=["property"],
            tooltip_text="Telefon ilk bağlandığında aynı kodu gösterir. Farklıysa araya biri girmiş olabilir.")
        self.fp_row.add_prefix(Gtk.Image(icon_name="security-high-symbolic"))
        g.add(self.fp_row)
        page.add(g)

        g = Adw.PreferencesGroup(
            title="USB (kablo)",
            description="Telefonda USB hata ayıklama açık olmalı. İnternet gerekmez; en hızlı yol.")
        self.sw_usb = compat.SwitchRow(title="USB bağlantısı", subtitle="Takılı telefon “Telefonlar” sayfasında görünür")
        self.sw_usb.connect("notify::active", lambda r, _: self._set("usb", r.get_active()))
        g.add(self.sw_usb)
        page.add(g)

        g = Adw.PreferencesGroup(
            title="Bluetooth",
            description="Önce telefonu sistemin Bluetooth ayarlarından bu bilgisayarla eşleştir. Bildirim, medya ve "
                        "komutlar için yeterli; büyük dosyalarda Wi-Fi ya da USB çok daha hızlı.")
        self.sw_bt = compat.SwitchRow(title="Bluetooth bağlantısı")
        self.sw_bt.connect("notify::active", lambda r, _: self._set_bluetooth(r.get_active()))
        g.add(self.sw_bt)
        self.bt_row = Adw.ActionRow(title="Durum", css_classes=["property"])
        self.bt_row.set_subtitle_lines(3)
        self.bt_icon = Gtk.Image(icon_name="bluetooth-symbolic")
        self.bt_row.add_prefix(self.bt_icon)
        g.add(self.bt_row)
        page.add(g)

        from .. import mirror
        g = self.mirror_group = Adw.PreferencesGroup(
            title="Telefonun ekranı", description="Yeni ayar, ekran bir sonraki açılışında uygulanır.")
        keys = list(mirror.PRESETS)
        self.mirror_row = Adw.ComboRow(title="Görüntü", model=Gtk.StringList.new([mirror.PRESETS[k][0] for k in keys]))
        cur = self.app.config["mirror_preset"]
        self.mirror_row.set_selected(keys.index(cur) if cur in keys else 0)
        self.mirror_row.set_subtitle(mirror.PRESETS[keys[self.mirror_row.get_selected()]][1])

        def on_preset(r, _):
            key = keys[r.get_selected()]
            r.set_subtitle(mirror.PRESETS[key][1])
            self._set("mirror_preset", key)
        self.mirror_row.connect("notify::selected", on_preset)
        g.add(self.mirror_row)
        self.sw_mirror_audio = compat.SwitchRow(
            title="Telefonun sesi bilgisayardan çalsın",
            subtitle="Ekran açıkken (Android 11 ve üstü). Kapalıysa ses telefonda kalır")
        self.sw_mirror_audio.set_active(self.app.config["mirror_audio"])
        self.sw_mirror_audio.connect("notify::active", lambda r, _: self._set("mirror_audio", r.get_active()))
        g.add(self.sw_mirror_audio)
        page.add(g)

        g = Adw.PreferencesGroup(title="Genel")
        self.name_row = compat.EntryRow(title="Bu bilgisayarın adı", show_apply_button=True)
        self.name_row.set_text(self.app.config["name"])
        self.name_row.connect("apply", lambda r: self._set("name", r.get_text().strip()[:64] or "Linux"))
        g.add(self.name_row)
        self.sw_bg = compat.SwitchRow(title="Pencere kapanınca arka planda çalışsın",
                                   subtitle="Telefon bağlı kalır, bildirimler gelmeye devam eder")
        self.sw_bg.set_active(self.app.config["run_in_background"])
        self.sw_bg.connect("notify::active", lambda r, _: self._set("run_in_background", r.get_active()))
        g.add(self.sw_bg)
        self.sw_autostart = compat.SwitchRow(title="Oturum açılınca başlat",
                                          subtitle="Pencere açılmadan arka planda başlar; telefon kendiliğinden bağlanır")
        self.sw_autostart.set_active(system.autostart_enabled())
        self.sw_autostart.connect("notify::active", lambda r, _: system.set_autostart(r.get_active()))
        g.add(self.sw_autostart)
        page.add(g)
        page.add(self._build_data_group())  # en altta: sıfırlama gibi geri dönüşü zahmetli işler
        return page

    def _build_data_group(self):
        """Veriler: önbellek, indirilen scrcpy, sıfırlama (bkz. talkto.veriler)."""
        from .. import veriler
        g = Adw.PreferencesGroup(title="Veriler", description="Telefondan alınan dosyalar bunlardan etkilenmez.")
        b = Gtk.Button(label="Temizle", valign=Gtk.Align.CENTER)
        self.cache_row = Adw.ActionRow(title="Önbellek")
        self.cache_row.add_suffix(b)

        def clear(*_):
            freed = veriler.clear_cache()
            self._prefs_toast(f"Önbellek temizlendi ({human_size(freed)})")
            self._update_data_rows()
        b.connect("clicked", clear)
        g.add(self.cache_row)

        self.scrcpy_row = Adw.ActionRow(title="İndirilen scrcpy")
        b = Gtk.Button(label="Sil", valign=Gtk.Align.CENTER)

        def drop(*_):
            freed = veriler.remove_scrcpy()
            self._prefs_toast(f"scrcpy silindi ({human_size(freed)}); gerekince yeniden indirilir")
            self._update_data_rows()
        b.connect("clicked", drop)
        self.scrcpy_row.add_suffix(b)
        g.add(self.scrcpy_row)

        r = Adw.ActionRow(title="Uygulamayı sıfırla",
                          subtitle="Eşleşmeler, profiller, komutlar ve ayarlar silinir (çöp kutusuna taşınır); "
                                   "uygulama yeniden başlar ve kurulum yardımcısı açılır.")
        r.set_subtitle_lines(4)
        b = Gtk.Button(label="Sıfırla…", valign=Gtk.Align.CENTER, css_classes=["destructive-action"])
        b.connect("clicked", lambda *_: self._confirm_reset())
        r.add_suffix(b)
        g.add(r)
        self._update_data_rows()
        return g

    def _prefs_toast(self, text):
        if self.prefs_window and self.prefs_window.get_visible():
            self.prefs_window.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=3))
        else:
            self.toast(text)

    def _update_data_rows(self):
        from .. import veriler
        self.cache_row.set_subtitle(f"Albüm kapakları, simgeler, eski günlükler · {human_size(veriler.cache_size())}")
        d = veriler.scrcpy_dir()
        self.scrcpy_row.set_visible(d.exists())
        if d.exists():
            self.scrcpy_row.set_subtitle(f"Telefonun ekranı için; gerekince yeniden indirilir · "
                                         f"{human_size(veriler.size_of(d))}")

    def _confirm_reset(self):
        ident = Gtk.CheckButton(valign=Gtk.Align.START)
        box = Gtk.Box(spacing=8, margin_top=6)
        box.append(ident)
        box.append(Gtk.Label(label="Bu bilgisayarın kimliğini de yenile (telefonlarda bu bilgisayarı unutup yeniden "
                                   "eşleşmek gerekir)", wrap=True, xalign=0, max_width_chars=44))
        self.app.confirm("Talk To Android sıfırlansın mı?",
                         "Eşleşmiş telefonlar, profiller, komutlar ve bütün ayarlar silinir; uygulama yeniden başlar "
                         "ve kurulum yardımcısı açılır. Silinenler çöp kutusuna taşınır, gerekirse oradan geri "
                         "alınır. Telefondan alınan dosyalar kalır.",
                         "Sıfırla", lambda: self.app.reset_app(ident.get_active()), destructive=True, extra=box)

    def _copy_address(self):
        addrs = self.status.get("addresses") or []
        if addrs:
            self.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(
                f"{addrs[0]}:{self.status.get('port')}"))
            self.toast("Adres kopyalandı")

    def _on_password(self, r):
        pw = r.get_text()
        self._set("password", pw)
        self.toast("Şifre kaydedildi" if pw else "Şifre kaldırıldı; yeni telefonlar için onay istenecek")

    def _set_bluetooth(self, on):
        if not self._updating:
            self.app.set_bluetooth(on)

    def sync_autostart(self):
        """Kurulum yardımcısından açıldıysa anahtar da açık görünsün."""
        if self.sw_autostart.get_active() != system.autostart_enabled():
            self.sw_autostart.set_active(system.autostart_enabled())

    def update_status(self, st):
        self.status = st
        self._updating = True
        try:
            self.sw_wireless.set_active(st["wireless"])
            self.sw_usb.set_active(st["usb"])
            self.sw_bt.set_active(st["bluetooth"])
            self.sync_autostart()
        finally:
            self._updating = False
        bt = st.get("bt") or {}
        self.bt_row.set_subtitle(bt.get("message", "") if st["bluetooth"] else "Kapalı")
        self.bt_icon.set_from_icon_name("bluetooth-active-symbolic" if st["bluetooth"] and bt.get("available")
                                        else "bluetooth-disabled-symbolic")

        self._update_hero()
        if self.usb:
            self.update_usb(self.usb)  # USB satırı bağlı/bağlı değil durumuna göre değişir
        addrs = st["addresses"]
        self.addr_row.set_subtitle("  ·  ".join(f"{a}:{st['port']}" for a in addrs) if addrs else "Ağ bulunamadı")
        self.addr_row.set_sensitive(st["wireless"])
        self.wifi_group.set_description(
            "Telefon ve bilgisayar aynı ağdaysa telefondaki uygulamada bu bilgisayar görünür. " +
            ("Şifre var: yeni telefon ilk bağlanışta bu şifreyi sorar."
             if st["password_set"] else
             "Şifre yok: her yeni telefon için burada onay penceresi açılır."))
        self.fp_row.set_subtitle(st["short_fp"])
        self.banner.set_title(GLib.markup_escape_text(st["error"] or ""))
        self.banner.set_revealed(bool(st["error"]))

        self._update_devices()
        self._update_media_page()
        self._update_files_target()
        self._update_commands()

    def _update_hero(self):
        st = self.status
        bt = st.get("bt") or {}
        sessions = st["sessions"]
        ways = [w for w, on in (("Wi-Fi", st["wireless"]), ("USB", st["usb"]),
                                ("Bluetooth", st["bluetooth"] and bt.get("available"))) if on]
        if sessions:
            self.hero_icon.set_from_icon_name("phone-symbolic")
            names = ", ".join(s["name"] for s in sessions)
            self.hero_title.set_text(names if len(sessions) < 3 else f"{len(sessions)} telefon bağlı")
            problems = sum(len(s.get("problems", [])) for s in sessions)
            ready = "Bağlı. Bildirimler, müzik ve dosyalar hazır." if "files" in self.f else \
                "Bağlı. Bildirimler ve müzik hazır."
            self.hero_sub.set_text(ready if not problems else "Bağlı, ama dikkat edilecek bir şey var: aşağıdaki uyarıya bak.")
        elif (d := self._usb_connectable()) is not None:
            # Telefon USB'de, uygulaması hazır: telefona gitmeden buradan bağlanılır.
            self.hero_icon.set_from_icon_name("phone-symbolic")
            self.hero_title.set_text(f"{setup_checks.display_name(d)} USB'de")
            self.hero_sub.set_text("“Bağlan”a bas: telefonda Talk To Linux açılır ve bağlanır, telefonda bir şey "
                                   "seçmen gerekmez. İlk seferde burada iki ekrandaki numarayı karşılaştırırsın.")
        elif ways:
            self.hero_icon.set_from_icon_name("computer-symbolic")
            self.hero_title.set_text("Telefon bekleniyor")
            self.hero_sub.set_text(f"{st['name']} hazır: {', '.join(ways)}. Telefonda Talk To Linux'u açınca bu "
                                   "bilgisayar listede görünür.")
        else:
            self.hero_icon.set_from_icon_name("network-offline-symbolic")
            self.hero_title.set_text("Bağlantı kapalı")
            self.hero_sub.set_text("Telefonun bağlanabilmesi için Wi-Fi, USB ya da Bluetooth'tan birini aç.")
        self.hero_button.set_visible(not sessions)
        self.hero_button.set_label("Bağlan" if not sessions and self._usb_connectable() else "Bağlantı ayarları")
        # Baloncuklar yalnızca yazıları değişince yeniden kurulur: açık bilgi penceresi her durum
        # güncellemesinde (pil, telefon bilgisi) kapanmasın.
        chips = [(s["device_id"], s["kind"], s.get("battery")) for s in sessions]
        if not self._changed("hero_chips", chips):
            self.hero_chips.set_visible(bool(sessions))
            return
        child = self.hero_chips.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.hero_chips.remove(child)
            child = nxt
        for s in sessions:
            text = KIND.get(s["kind"], s["kind"])
            if s.get("battery"):
                b = s["battery"]
                text += f" · %{b['level']}" + (" ⚡" if b["charging"] else "")
            # Baloncuğa tıklayınca telefonun sistem bilgileri (model, Android, pil, depolama, bellek...).
            chip = Gtk.MenuButton(label=text, css_classes=["chip", "chip-button"],
                                  tooltip_text="Telefonun sistem bilgileri")
            chip.set_create_popup_func(lambda b, did=s["device_id"]: self._phone_info_popup(b, did))
            self.hero_chips.append(chip)
        self.hero_chips.set_visible(bool(sessions))

    def _phone_info_popup(self, button, device_id):
        """Açılırken son bilinen bilgiler gösterilir ve telefondan tazesi istenir (gelince yeniden çizilir)."""
        from .. import telefon_bilgi
        self.app.call("request_phone_info", device_id)
        s = next((x for x in self.status.get("sessions", []) if x["device_id"] == device_id), {})
        grid = Gtk.Grid(column_spacing=14, row_spacing=6, margin_top=10, margin_bottom=10, margin_start=12,
                        margin_end=12)
        lines = telefon_bilgi.rows(s.get("info")) or [("", "Telefon bilgileri alınıyor… (telefondaki Talk To "
                                                           "Linux 0.9.2 ya da sonrası gerekir)")]
        title = Gtk.Label(label=s.get("name") or "Telefon", xalign=0, css_classes=["heading"])
        grid.attach(title, 0, 0, 2, 1)
        for i, (k, v) in enumerate(lines, start=1):
            grid.attach(Gtk.Label(label=k, xalign=0, css_classes=["dim-label"]), 0, i, 1, 1)
            grid.attach(Gtk.Label(label=v, xalign=0, wrap=True, max_width_chars=44, selectable=True), 1, i, 1, 1)
        pop = button.get_popover() or Gtk.Popover()
        pop.set_child(grid)
        button.set_popover(pop)

    def _usb_connectable(self):
        """Bağlı telefon yokken USB'de uygulaması hazır (güncel) ilk telefon; yoksa None."""
        if not self.usb or (self.status or {}).get("sessions"):
            return None
        return next((d for d in self.usb.get("devices", []) if d.get("state") == "device" and d.get("app")
                     and not d.get("installing") and not setup_checks.app_outdated(d, self.usb)), None)

    def _on_hero_button(self):
        d = self._usb_connectable()
        if d:
            self.app.connect_phone(d["serial"])
        else:
            self.open_preferences()

    def update_usb(self, snap):
        self.usb = snap
        self.araclar.update(snap)
        if self.status:
            self._update_hero()
        if not self._changed("usb_rows", snap, [(s["device_id"], s.get("adb_serial"))
                                                 for s in (self.status or {}).get("sessions", [])],
                             self.app.installing_adb, sorted(self.f)):
            return
        rows = []
        if not snap.get("running"):
            pass
        elif not snap.get("adb"):
            can = system.adb_install_command() is not None
            r = row("adb kurulu değil", "USB bağlantısı için gerekli. “Kur”a basınca bilgisayarın şifresi sorulur."
                    if can else "Dağıtımının paket yöneticisinden “adb” ya da “android-tools” paketini kur.")
            r.add_prefix(Gtk.Image(icon_name="dialog-warning-symbolic"))
            if can:
                if self.app.installing_adb:
                    r.add_suffix(Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER))
                else:
                    b = Gtk.Button(label="Kur", valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
                    b.connect("clicked", lambda *_: self.app.install_adb())
                    r.add_suffix(b)
            rows.append(r)
        for ph in snap.get("unseen", []) if snap.get("running") else []:
            if ph.get("adb") and snap.get("adb"):
                sub = ("USB hata ayıklama açık ama bu bilgisayarın telefona erişim izni yok. Kabloyu çıkarıp tak; "
                       "düzelmezse “android-sdk-platform-tools-common” paketini kur.")
            else:
                sub = "Takılı ama USB hata ayıklama kapalı. Telefonda:\n" + "\n".join(
                    f"{i}. {text}" for i, (_t, text) in enumerate(setup_checks.dev_guide(ph), 1)) + \
                    "\nİstemezsen Wi-Fi ya da Bluetooth kullan."
            r = row(ph["name"], sub)
            r.set_subtitle_lines(12)
            r.add_prefix(Gtk.Image(icon_name="dialog-information-symbolic"))
            rows.append(r)
        if not snap.get("running") or not snap.get("adb"):
            pass
        elif not snap.get("devices") and not snap.get("unseen") and not self.app.config["simple_mode"]:
            # Basit modda kablo şart değil (Wi-Fi yeter): boş "USB bekleniyor" satırı kalabalık yapmasın.
            r = row("Telefon bekleniyor", "Telefonu USB ile tak ve USB hata ayıklamayı aç. Telefonda Talk To Linux "
                                          "yoksa buradan tek tıkla kurulur." if snap.get("apk") else
                    "Telefonu USB ile tak ve USB hata ayıklamayı aç")
            r.set_subtitle_lines(3)
            r.add_prefix(Gtk.Image(icon_name="media-removable-symbolic"))
            rows.append(r)
        for d in snap.get("devices", []):
            state = d["state"]
            if state == "device" and self.status and setup_checks.session_of(d, self.status.get("sessions", [])):
                continue  # bağlı telefonun kendi satırında gösterilir (USB'de olduğu orada yazar)
            if state == "device":
                session = None
                missing = setup_checks.perms_missing(d, session)
                if session:
                    sub = "Bağlı" + (f" · eksik izin: {', '.join(missing)}" if missing else "")
                elif d["tunnel"]:
                    sub = "Bağlanmaya hazır: “Bağlan”a bas (telefonda bir şey seçmen gerekmez)"
                else:
                    sub = "USB tüneli kurulamadı: kabloyu çıkarıp tak"
                if d.get("app") is False and snap.get("apk"):
                    sub = "Telefonda Talk To Linux yok: sağdaki düğme kurar, açar ve bağlar"
                elif setup_checks.app_outdated(d, snap):
                    sub = (f"Telefondaki Talk To Linux eski ({d['app_version']}; bu bilgisayardaki "
                           f"{snap['apk_version']}): sağdaki düğmeyle güncelle")
                elif setup_checks.xiaomi(d) and d.get("xiaomi_permissions") is False and missing:
                    # Yalnızca eksik izin varken önemli: bağlanmayı engellemez.
                    sub += ("\nEksik izinler bilgisayardan verilemiyor (Xiaomi: “USB hata ayıklama (Güvenlik "
                            "ayarları)” kapalı); telefonda Talk To Linux → İzinler'den ver")
                icon = "emblem-ok-symbolic" if d["tunnel"] else "dialog-warning-symbolic"
            elif state == "unauthorized":
                sub, icon = "Telefonda “USB hata ayıklamaya izin ver” onayını ver", "dialog-question-symbolic"
            elif state == "no":  # adb: "no permissions (udev ...)"
                sub, icon = ("Bu bilgisayarın telefona erişim izni yok. Kabloyu çıkarıp tak; düzelmezse "
                             "“android-sdk-platform-tools-common” paketini kur."), "dialog-warning-symbolic"
            elif state == "offline":
                sub, icon = "Telefon yanıt vermiyor: kabloyu çıkarıp tekrar tak", "dialog-warning-symbolic"
            else:
                sub, icon = f"Durum: {state}", "dialog-warning-symbolic"
            r = row(setup_checks.display_name(d), sub)
            r.add_prefix(Gtk.Image(icon_name=icon))
            if state == "device":
                self._usb_actions(r, d, snap)
            rows.append(r)
        self._usb_rows_cache = rows
        if self.status:
            self._build_session_rows()  # bağlı telefonun satırı da USB bilgisini (takılı, eksik izin) gösterir
        self._render_phones()

    def _usb_actions(self, r, d, snap):
        """Tek ana iş düğme olarak (kur, güncelle, bağlan ya da eksik izinleri tamamla), gerisi "⋯" menüsünde."""
        serial = d["serial"]
        busy = d.get("installing") or d.get("setting_up")
        session = setup_checks.session_of(d, self.status.get("sessions", [])) if self.status else None
        missing = setup_checks.perms_missing(d, session)
        if busy:
            r.add_suffix(Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER))
        elif d.get("app") is False and snap.get("apk"):
            b = Gtk.Button(label="Kur ve bağlan", valign=Gtk.Align.CENTER, css_classes=["suggested-action"],
                           tooltip_text="USB üzerinden telefona kurar, açar ve bağlar")
            b.connect("clicked", lambda *_: self.app.install_phone_app(serial))
            r.add_suffix(b)
        elif setup_checks.app_outdated(d, snap):
            b = Gtk.Button(label="Talk To Linux'u güncelle", valign=Gtk.Align.CENTER,
                           css_classes=["suggested-action"],
                           tooltip_text=f"{d['app_version']} → {snap['apk_version']}; eşleşme ve ayarlar korunur")
            b.connect("clicked", lambda *_: self.app.install_phone_app(serial))
            r.add_suffix(b)
        elif not session and d.get("app"):
            b = Gtk.Button(label="Bağlan", valign=Gtk.Align.CENTER, css_classes=["suggested-action"],
                           tooltip_text="Telefonda Talk To Linux'u açar ve USB'den bağlar")
            b.connect("clicked", lambda *_: self.app.connect_phone(serial))
            r.add_suffix(b)
        elif missing and not (setup_checks.xiaomi(d) and d.get("xiaomi_permissions") is False):
            b = Gtk.Button(label="İzinleri tamamla", valign=Gtk.Align.CENTER, css_classes=["suggested-action"],
                           tooltip_text="Eksik olanlar: " + ", ".join(missing) + ". Telefonda verilmiş olanlara "
                                        "dokunulmaz.")
            b.connect("clicked", lambda *_: self.app.phone_setup(serial))
            r.add_suffix(b)
        menu = Gio.Menu()
        items = []
        if "mirror" in self.f:
            items.append(("Telefonun ekranını aç", "mirror"))
            if ":" not in serial:
                items.append(("Kablosuz ekranı hazırla", "wireless"))
        if d.get("app"):
            items += [("Telefonu ayarla (izinler)", "setup"), ("Talk To Linux'u güncelle", "install")]
        for label, act in items:
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value("win.usb", GLib.Variant("s", f"{act}|{serial}|{d.get('model') or ''}"))
            menu.append_item(item)
        if items:
            r.add_suffix(Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu, valign=Gtk.Align.CENTER,
                                        tooltip_text="Diğer işlemler", css_classes=["flat"]))

    def _on_usb_action(self, _action, param):
        act, serial, model = param.unpack().split("|", 2)
        if act == "mirror":
            self.app.mirror_usb(serial, model or None)
        elif act == "wireless":
            self.app.prepare_wireless(serial)
        elif act == "setup":
            self.app.phone_setup(serial)
        elif act == "install":
            self.app.install_phone_app(serial)

    # ---- Telefonlar sayfasının satırları ------------------------------------------

    def _changed(self, key, *data) -> bool:
        """Grup yalnızca içeriği gerçekten değişince yeniden kurulsun (açık satırlar kapanmasın)."""
        sig = json.dumps(data, sort_keys=True, default=str)
        if self._sig.get(key) == sig:
            return False
        self._sig[key] = sig
        return True

    @staticmethod
    def _problem_row(text, title="Uyarı"):
        r = row(title, text)
        r.set_subtitle_lines(4)
        r.add_prefix(Gtk.Image(icon_name="dialog-warning-symbolic", css_classes=["warning"]))
        return r

    def _render_phones(self):
        """Telefonlar grubu: bağlı telefonlar (USB'de olduğu, eksik izni aynı satırda), USB'de bağlı olmayan
        telefonlar, sonra tek satıra katlanmış eşleşmiş telefonlar."""
        if not self.status:
            return
        if self.phones_group.rows:
            for r in self.phones_group.rows:
                if isinstance(r, Adw.ExpanderRow):
                    self._trusted_open = r.get_expanded()
        rows = list(getattr(self, "_session_rows_cache", [])) + list(getattr(self, "_usb_rows_cache", []))
        exp = self._trusted_expander()
        if exp:
            rows.append(exp)
        self.phones_group.set_rows(rows)
        self.phones_group.set_visible(bool(rows))

    def _usb_device_of(self, s):
        return next((d for d in (self.usb or {}).get("devices", [])
                     if d.get("state") == "device" and d["serial"] == s.get("adb_serial")), None)

    def _phone_row(self, s):
        """Bağlı telefonun tek satırı: durum, tek ana iş, gerisi ⋮ menüsünde."""
        did = s["device_id"]
        d = self._usb_device_of(s)
        snap = self.usb or {}
        sub = ["Bağlı · " + KIND.get(s["kind"], s["kind"]) + (f" {s['ip']}" if s["kind"] == "wifi" else "")]
        if s.get("battery"):
            b = s["battery"]
            sub.append(f"%{b['level']} pil" + (", şarj oluyor" if b["charging"] else ""))
        if d and s["kind"] != "usb":
            sub.append("USB'de takılı")
        if "profiles" in self.f:
            sub.append(f"profil: {s.get('profile_name', '?')}")
        lines = [" · ".join(sub)]
        missing = setup_checks.perms_missing(d, s) if d else None
        outdated = bool(d and setup_checks.app_outdated(d, snap))
        locked = bool(d and setup_checks.xiaomi(d) and d.get("xiaomi_permissions") is False)
        if outdated:
            lines.append(f"Telefondaki Talk To Linux eski ({d['app_version']} → {snap['apk_version']})")
        elif missing:
            lines.append("Eksik izin: " + ", ".join(missing) + (" (Xiaomi: telefonda Talk To Linux → İzinler'den ver)"
                                                                 if locked else ""))
        r = row(s["name"], "\n".join(lines))
        r.set_subtitle_lines(4)
        r.add_prefix(Gtk.Image(icon_name="phone-symbolic", pixel_size=24))
        ringing = did in self.ringing
        busy = d and (d.get("installing") or d.get("setting_up"))
        primary = None
        if busy:
            r.add_suffix(Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER))
        elif outdated:
            primary = ("Güncelle", lambda: self.app.install_phone_app(d["serial"]), "install")
        elif missing and not locked:
            primary = ("İzinleri tamamla", lambda: self.app.phone_setup(d["serial"]), "setup")
        else:
            primary = ("Çalmayı durdur" if ringing else "Telefonu bul", lambda: self._ring(did), "ring")
        if primary:
            b = Gtk.Button(label=primary[0], valign=Gtk.Align.CENTER,
                           css_classes=["suggested-action"] if primary[2] != "ring" or ringing else [],
                           tooltip_text="Sessizde olsa da telefon 30 saniye yüksek sesle çalar"
                           if primary[2] == "ring" else None)
            b.connect("clicked", lambda *_, f=primary[1]: f())
            r.add_suffix(b)
        items = []
        if not primary or primary[2] != "ring":
            items.append(("Telefonu bul", "ring"))
        if s["kind"] != "bluetooth" and "mirror" in self.f:
            items.append(("Telefonun ekranını aç", "mirror"))
            if d and ":" not in d["serial"]:
                items.append(("Kablosuz ekranı hazırla", "wireless"))
        if "files" in self.f:
            items += [("Dosya gönder", "files"), ("Panoyu telefona gönder", "clipboard")]
        if d and d.get("app"):
            if not primary or primary[2] != "setup":
                items.append(("Telefondaki izinleri tamamla", "setup"))
            if not primary or primary[2] != "install":
                items.append(("Talk To Linux'u yeniden kur", "install"))
        items += [("Bağlantıyı kes", "disconnect"), ("Unut…", "forget")]
        menu = Gio.Menu()
        for label, act in items:
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value("win.phone", GLib.Variant("s", f"{act}|{did}|{d['serial'] if d else ''}"))
            menu.append_item(item)
        r.add_suffix(Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu, valign=Gtk.Align.CENTER,
                                    tooltip_text="Diğer işlemler", css_classes=["flat"]))
        return r

    def _on_phone_action(self, _action, param):
        act, did, serial = param.unpack().split("|", 2)
        if act == "ring":
            self._ring(did)
        elif act == "mirror":
            self.app.mirror_session(did)
        elif act == "wireless":
            self.app.prepare_wireless(serial)
        elif act == "files":
            self.pick_files(did)
        elif act == "clipboard":
            self.app.send_clipboard(did)
        elif act == "setup":
            self.app.phone_setup(serial)
        elif act == "install":
            self.app.install_phone_app(serial)
        elif act == "disconnect":
            self.app.call("disconnect", did)
        elif act == "forget":
            t = next((t for t in self.status.get("trusted", []) if t["device_id"] == did), None)
            if t:
                self._confirm_forget(t)

    def _trusted_expander(self):
        """Eşleşmiş telefonlar: tek satıra katlanmış (yer kaplamasın); açınca profil ve “unut”."""
        trusted = self.status.get("trusted", [])
        if not trusted:
            return None
        profiles = self.status.get("profiles", {})
        connected = {s["device_id"] for s in self.status.get("sessions", [])}
        others = [t["name"] for t in trusted if t["device_id"] not in connected]
        exp = Adw.ExpanderRow(title=GLib.markup_escape_text(f"Eşleşmiş telefonlar ({len(trusted)})"),
                              subtitle=GLib.markup_escape_text(
                                  ("Şu an bağlı değil: " + ", ".join(others[:4])) if others else
                                  "Yeniden bağlanırken onay ya da şifre istemez"))
        exp.add_prefix(Gtk.Image(icon_name="emblem-shared-symbolic"))
        pids = list(profiles)
        names = Gtk.StringList.new([profiles[p]["name"] for p in pids])
        for t in sorted(trusted, key=lambda t: (t["device_id"] not in connected, -t["paired_at"])):
            when = time.strftime("%d.%m.%Y", time.localtime(t["paired_at"]))
            sub = (f"{t['model']} · " if t["model"] else "") + f"eşleşme {when}" + \
                (" · bağlı" if t["device_id"] in connected else "")
            if "profiles" in self.f:
                r = row(t["name"], sub, cls=Adw.ComboRow, model=names)
                if t["profile"] in pids:
                    r.set_selected(pids.index(t["profile"]))
                r.connect("notify::selected", lambda r, _, d=t["device_id"]:
                          self.app.call("assign_profile", d, pids[r.get_selected()]))
            else:
                r = row(t["name"], sub)
            r.add_suffix(icon_button("user-trash-symbolic", "Unut (yeniden bağlanırken onay ya da şifre gerekir)",
                                     lambda t=t: self._confirm_forget(t)))
            exp.add_row(r)
        exp.set_expanded(self._trusted_open)
        return exp

    def _build_session_rows(self) -> bool:
        """Bağlı telefonların satırları; yalnızca satırda görünen bilgi değişince yeniden kurulur (müzik konumu
        gibi sık değişenler hariç): yoksa açık ⋮ menüsü her durum güncellemesinde kapanırdı."""
        sessions = self.status.get("sessions", [])
        shown = [{k: s.get(k) for k in ("device_id", "name", "kind", "ip", "battery", "profile_name", "problems",
                                         "adb_serial")} for s in sessions]
        usb = self.usb or {}
        if not self._changed("phones", shown, sorted(self.ringing), usb.get("devices"), usb.get("apk_version"),
                             self.status.get("trusted"),
                             {k: v["name"] for k, v in self.status.get("profiles", {}).items()}, sorted(self.f)):
            return False
        rows = []
        for s in sessions:
            rows.append(self._phone_row(s))
            for text in s.get("problems", []):
                rows.append(self._problem_row(text))
        self._session_rows_cache = rows
        return True

    def _update_devices(self):
        if self._build_session_rows():
            if self.usb:
                self._sig.pop("usb_rows", None)
                self.update_usb(self.usb)  # USB'deki telefon bağlandıysa ayrı satırından kalkar
            else:
                self._render_phones()
        problems = [(s["name"], text) for s in self.status.get("sessions", []) for text in s.get("problems", [])]
        if self._changed("notif_problems", problems):
            self.notif_problems.set_rows([self._problem_row(t, n) for n, t in problems])

        profiles = self.status.get("profiles", {})
        trusted = self.status.get("trusted", [])
        if self._changed("profiles", profiles, self.status.get("default_profile"),
                         [t["profile"] for t in trusted]):
            self._render_profiles(profiles, trusted)

    def _render_profiles(self, profiles, trusted):
        # Bir izni değiştirince bütün satırlar yeniden kurulur: açık olan profil açık kalsın.
        open_ids = {pid for pid, r in zip(getattr(self, "_profile_ids", []), self.profile_group.rows)
                    if r.get_expanded()}
        self._profile_ids = list(profiles)
        rows = []
        default = self.status.get("default_profile")
        for pid, prof in profiles.items():
            count = sum(1 for t in trusted if t["profile"] == pid)
            sub = [f"{count} telefon"] + (["yeni telefonlar bununla başlar"] if pid == default else [])
            exp = row(prof["name"], " · ".join(sub), cls=Adw.ExpanderRow)
            exp.set_expanded(pid in open_ids)
            exp.add_prefix(Gtk.Image(icon_name="avatar-default-symbolic"))
            name = compat.EntryRow(title="Profil adı", show_apply_button=True, text=prof["name"])
            name.connect("apply", lambda r, p=pid: self.app.call("save_profile", p, {"name": r.get_text()}))
            exp.add_row(name)
            for key, label in Config.PERMISSIONS.items():
                sw = compat.SwitchRow(title=label, active=bool(prof.get(key)))
                sw.connect("notify::active", lambda r, _, p=pid, k=key:
                           self.app.call("save_profile", p, {k: r.get_active()}))
                exp.add_row(sw)
            folder = Adw.ActionRow(title="Kayıt klasörü", css_classes=["property"],
                                   subtitle=compat.esc(prof.get("receive_dir") or "Genel ayar (Dosyalar sayfası)"))
            folder.add_suffix(icon_button("document-edit-symbolic", "Bu profil için klasör seç",
                                          lambda p=pid: self._choose_profile_dir(p)))
            if prof.get("receive_dir"):
                folder.add_suffix(icon_button("edit-clear-symbolic", "Genel ayara dön",
                                              lambda p=pid: self.app.call("save_profile", p, {"receive_dir": ""})))
            exp.add_row(folder)
            actions = Adw.ActionRow()
            if pid != default:
                b = Gtk.Button(label="Yeni telefonlar bununla başlasın", valign=Gtk.Align.CENTER)
                b.connect("clicked", lambda *_, p=pid: self._set("default_profile", p))
                actions.add_suffix(b)
            if len(profiles) > 1:
                b = Gtk.Button(label="Sil", valign=Gtk.Align.CENTER, css_classes=["destructive-action"])
                b.connect("clicked", lambda *_, p=pid, n=prof["name"]: self.app.confirm(
                    f"“{n}” profili silinsin mi?", "Bu profildeki telefonlar varsayılan profile geçer.", "Sil",
                    lambda: self.app.call("delete_profile", p), destructive=True))
                actions.add_suffix(b)
            if actions.get_first_child():
                exp.add_row(actions)
            rows.append(exp)
        self.profile_group.set_rows(rows)

    def _choose_profile_dir(self, pid):
        compat.choose_folder(self, "Bu profildeki telefonlardan gelen dosyalar nereye kaydedilsin?", None,
                             lambda path: self.app.call("save_profile", pid, {"receive_dir": path}))

    def _ring(self, did):
        on = did not in self.ringing
        (self.ringing.add if on else self.ringing.discard)(did)
        self.app.call("ring", did, on)
        self._update_devices()
        if on:
            GLib.timeout_add_seconds(30, lambda: (self.ringing.discard(did), self._update_devices(), False)[-1])

    def _confirm_forget(self, t):
        self.app.confirm(f"“{t['name']}” unutulsun mu?",
                         "Eşleşme silinir; bu telefon bir dahaki bağlantıda yeniden numara karşılaştırması ya da "
                         "şifre isteyecek.",
                         "Unut", lambda: self.app.call("forget", t["device_id"]), destructive=True)

    # ---- Medya ----------------------------------------------------------------

    def _build_media(self):
        page = Adw.PreferencesPage()
        self.media_group = Adw.PreferencesGroup(title="Telefonda çalan")
        self.media_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.media_empty = Adw.StatusPage(
            icon_name="audio-x-generic-symbolic", title="Telefonda çalan bir şey yok",
            description="Spotify, YouTube Music ya da başka bir uygulamada müzik açınca burada görünür.\n"
                        "Telefonda Talk To Linux uygulamasına “bildirim erişimi” verilmiş olmalı.")
        self.media_empty.add_css_class("compact")
        self.media_box.append(self.media_empty)
        self.media_group.add(self.media_box)
        page.add(self.media_group)

        g = Adw.PreferencesGroup(
            title="Masaüstünde",
            description="Telefonda çalan, üst çubuktaki medya denetiminde ve klavyenin medya tuşlarında da çalışır.")
        mini = row("Mini oynatıcı", "Küçük ayrı pencere: oynat/duraklat, ileri, ses, konum")
        mini.add_prefix(Gtk.Image(icon_name="audio-x-generic-symbolic"))
        b = Gtk.Button(label="Aç", valign=Gtk.Align.CENTER)
        b.connect("clicked", lambda *_: self.app.open_mini_player())
        mini.add_suffix(b)
        g.add(mini)
        self.sw_pin = compat.SwitchRow(title="Müzik başlayınca mini oynatıcıyı aç",
                                       subtitle="Telefonda müzik başlayınca mini oynatıcı kendiliğinden açılır")
        self.sw_pin.set_active(self.app.config["mini_player_pinned"])
        self.sw_pin.connect("notify::active", lambda r, _: not self._updating and self.app.set_pinned(r.get_active()))
        g.add(self.sw_pin)
        self.sw_popup = compat.SwitchRow(title="Şarkı değişince bildirim göster",
                                         subtitle="Ekranın üstünde kısa süre görünür; duraklat ve sonraki düğmeleriyle")
        self.sw_popup.set_active(self.app.config["track_popup"])
        self.sw_popup.connect("notify::active", lambda r, _: self.app.config.set("track_popup", r.get_active()))
        g.add(self.sw_popup)
        page.add(g)

        g = Adw.PreferencesGroup(title="Bu bilgisayar")
        self.sw_share_media = compat.SwitchRow(
            title="Bu bilgisayarda çalanı telefondan kontrol et",
            subtitle="Spotify, tarayıcıda YouTube, VLC… (MPRIS destekleyen her oynatıcı)")
        self.sw_share_media.set_active(self.app.config["share_media"])
        self.sw_share_media.connect("notify::active", lambda r, _: self._set("share_media", r.get_active()))
        g.add(self.sw_share_media)
        page.add(g)
        return page

    def sync_pin(self):
        """Mini oynatıcıdaki düğmeyle değişince buradaki anahtar da güncellensin."""
        self._updating = True
        try:
            self.sw_pin.set_active(self.app.config["mini_player_pinned"])
        finally:
            self._updating = False

    def _update_media_page(self):
        sessions = {s["device_id"]: s for s in self.status.get("sessions", [])}
        for did in list(self.media_cards):
            if did not in sessions:
                self.media_box.remove(self.media_cards.pop(did))
        any_active = False
        for did, s in sessions.items():
            st = s.get("media") or {}
            if st.get("active"):
                any_active = True
                card = self.media_cards.get(did)
                if not card:
                    card = self.media_cards[did] = MediaCard(self, did)
                    self.media_box.append(card)
                card.update(s["name"], st)
                card.set_art(self.art_paths.get(st.get("art_id") or ""))
                card.set_visible(True)
            elif did in self.media_cards:
                self.media_cards[did].set_visible(False)
        self.media_empty.set_visible(not any_active)

    def update_media(self, device_id, state):
        for s in self.status.get("sessions", []):
            if s["device_id"] == device_id:
                s["media"] = state
        self._update_media_page()

    def update_media_art(self, device_id, art_id, path):
        self.art_paths[art_id] = path
        card = self.media_cards.get(device_id)
        if card and card.state.get("art_id") == art_id:
            card.set_art(path)

    def _tick(self):
        for c in self.media_cards.values():
            if c.get_visible():
                c.tick()
        return True

    # ---- Dosyalar -------------------------------------------------------------

    def _build_files(self):
        page = Adw.PreferencesPage()

        g = Adw.PreferencesGroup(title="Telefona gönder")
        self.dropzone = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["dropzone"])
        self.dropzone.append(Gtk.Image(icon_name="document-send-symbolic", pixel_size=40,
                                       css_classes=["dim-label"]))
        self.drop_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, css_classes=["title-4"])
        self.dropzone.append(self.drop_label)
        self.drop_button = Gtk.Button(label="Dosya seç", halign=Gtk.Align.CENTER,
                                      css_classes=["pill", "suggested-action"], margin_top=6)
        self.drop_button.connect("clicked", lambda *_: self.pick_files(None))
        self.dropzone.append(self.drop_button)
        g.add(self.dropzone)
        page.add(g)

        g = Adw.PreferencesGroup(title="Telefondan gelenler")
        self.dir_row = Adw.ActionRow(title="Kayıt klasörü", css_classes=["property"])
        self.dir_row.set_subtitle(compat.esc(self.app.config["receive_dir"]))
        self.dir_row.add_prefix(Gtk.Image(icon_name="folder-download-symbolic"))
        self.dir_row.add_suffix(icon_button("folder-open-symbolic", "Klasörü aç", self.open_receive_dir))
        self.dir_row.add_suffix(icon_button("document-edit-symbolic", "Klasörü değiştir", self._choose_dir))
        g.add(self.dir_row)
        self.sw_accept = compat.SwitchRow(title="Gelen dosyaları sormadan kabul et",
                                       subtitle="Kapalıysa her dosya için onay penceresi açılır")
        self.sw_accept.set_active(self.app.config["auto_accept"])
        self.sw_accept.connect("notify::active", lambda r, _: self._set("auto_accept", r.get_active()))
        g.add(self.sw_accept)
        page.add(g)

        self.transfer_group = DynamicGroup(title="Aktarımlar")
        page.add(self.transfer_group)
        self._render_transfers()
        return page

    def _update_files_target(self):
        t = self.target()
        if t:
            self.drop_label.set_text(f"Dosyaları buraya bırak, {t['name']} cihazına gitsin")
        else:
            self.drop_label.set_text("Telefon bağlanınca dosyaları buraya bırakarak gönderebilirsin")
        self.drop_button.set_sensitive(bool(t))

    def open_receive_dir(self):
        d = Path(self.app.config["receive_dir"]).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        compat.open_path(self, str(d))

    def _choose_dir(self):
        def done(path):
            self._set("receive_dir", path)
            self.dir_row.set_subtitle(compat.esc(path))
        compat.choose_folder(self, "Gelen dosyalar nereye kaydedilsin?",
                             str(Path(self.app.config["receive_dir"]).expanduser().parent), done)

    def pick_files(self, device_id):
        did = device_id or (self.target() or {}).get("device_id")
        if not did:
            return
        compat.choose_files(self, "Telefona gönderilecek dosyalar",
                            lambda paths: [self.app.call("send_file", did, p) for p in paths])

    def _on_drop(self, _target, value, _x, _y):
        self.dropzone.remove_css_class("drop-active")
        if "files" not in self.f:
            self.toast("Dosya gönderme basit modda kapalı: Tercihler → Özellikler")
            return False
        t = self.target()
        if not t:
            self.toast("Önce bir telefon bağla")
            return False
        n = 0
        for f in value.get_files():
            p = f.get_path()
            if p and Path(p).is_file():
                self.app.call("send_file", t["device_id"], p)
                n += 1
        if n:
            self.toast(f"{n} dosya {t['name']} cihazına gönderiliyor")
            self.stack.set_visible_child_name("dosyalar")
        return n > 0

    @staticmethod
    def _transfer_text(tr):
        arrow = "Telefondan" if tr["direction"] == "in" else "Telefona"
        size = human_size(tr["size"])
        text = {"waiting": "bekliyor", "active": f"{human_size(tr['done'])} / {size}", "done": size,
                "failed": f"başarısız: {tr.get('error') or ''}", "rejected": "reddedildi",
                "cancelled": "iptal edildi"}.get(tr["state"], tr["state"])
        return f"{arrow} ({tr['device']}) · {text}"

    def update_transfer(self, tr):
        key = tr.get("key") or f"{tr['device_id']}:{tr['direction']}:{tr['tid']}"
        old = self.transfers.get(key)
        tr["at"] = old["at"] if old else time.time()
        self.transfers[key] = tr
        # İlerleme olaylarında satırlar baştan kurulmaz (0,2 sn'de bir): "İptal"e basılabilsin.
        live = self._tr_rows.get(key)
        if old and live and old["state"] in ("active", "waiting") and tr["state"] in ("active", "waiting"):
            r, bar = live
            r.set_subtitle(self._transfer_text(tr))
            if bar:
                bar.set_fraction(tr["done"] / tr["size"] if tr["size"] else 0)
            return
        if len(self.transfers) > 30:
            for k in sorted(self.transfers, key=lambda k: self.transfers[k]["at"])[:-30]:
                del self.transfers[k]
        self._render_transfers()

    def _render_transfers(self):
        rows = []
        self._tr_rows = {}
        for key, tr in sorted(self.transfers.items(), key=lambda kv: -kv[1]["at"]):
            state = tr["state"]
            r = row(tr["name"], self._transfer_text(tr))
            r.add_prefix(Gtk.Image(icon_name="go-down-symbolic" if tr["direction"] == "in" else "go-up-symbolic"))
            bar = None
            if state in ("active", "waiting"):
                bar = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=110)
                bar.set_fraction(tr["done"] / tr["size"] if tr["size"] else 0)
                r.add_suffix(bar)
                r.add_suffix(icon_button("process-stop-symbolic", "İptal",
                                         lambda t=tr: self.app.call("cancel_transfer", t["device_id"],
                                                                    t["direction"], t["tid"])))
            elif state == "done" and tr.get("path"):
                b = Gtk.Button(label="Aç", valign=Gtk.Align.CENTER, css_classes=["flat"])
                b.connect("clicked", lambda *_, p=tr["path"]: self.app.open_path(p))
                r.add_suffix(b)
                r.add_suffix(icon_button("folder-open-symbolic", "Klasörde göster",
                                         lambda p=tr["path"]: self.app.show_in_folder(p)))
            elif state == "done":
                r.add_suffix(Gtk.Image(icon_name="emblem-ok-symbolic", css_classes=["success"]))
            elif state in ("failed", "rejected"):
                r.add_suffix(Gtk.Image(icon_name="dialog-warning-symbolic", css_classes=["error"]))
            rows.append(r)
            self._tr_rows[key] = (r, bar)
        if not rows:
            rows.append(row("Henüz aktarım yok", "Telefonda bir dosyayı “Paylaş → Talk To Linux” ile gönderebilirsin"))
        self.transfer_group.set_rows(rows)

    # ---- Bildirimler ----------------------------------------------------------

    def _build_notifications(self):
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup()
        self.sw_notif = compat.SwitchRow(title="Telefon bildirimlerini masaüstünde göster",
                                      subtitle="Telefonda Talk To Linux uygulamasına “bildirim erişimi” verilmiş olmalı")
        self.sw_notif.set_active(self.app.config["show_notifications"])
        self.sw_notif.connect("notify::active", lambda r, _: self._set("show_notifications", r.get_active()))
        g.add(self.sw_notif)
        page.add(g)
        self.notif_problems = DynamicGroup()
        page.add(self.notif_problems)
        self.notif_group = DynamicGroup(title="Son bildirimler")
        page.add(self.notif_group)
        self.notif_empty = Adw.StatusPage(
            icon_name="preferences-system-notifications-symbolic", title="Henüz bildirim yok",
            description="Telefona gelen bildirimler burada ve masaüstü bildiriminde görünür.")
        self.notif_empty.add_css_class("compact")
        empty_group = Adw.PreferencesGroup()
        empty_group.add(self.notif_empty)
        page.add(empty_group)
        self.notifs = []
        self._render_notifications()
        return page

    def add_notification(self, n):
        self.notifs.insert(0, n)
        del self.notifs[50:]
        self._render_notifications()

    def _render_notifications(self):
        rows = []
        for n in self.notifs:
            r = row(n["title"] or n["app"], n["text"])
            r.set_subtitle_lines(3)
            if n.get("icon"):
                img = Gtk.Image.new_from_file(n["icon"])
                img.set_pixel_size(32)
            else:
                img = Gtk.Image(icon_name="preferences-system-notifications-symbolic", pixel_size=24)
            r.add_prefix(img)
            meta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            meta.append(Gtk.Label(label=n["app"], xalign=1, css_classes=["caption-heading"]))
            meta.append(Gtk.Label(label=time.strftime("%H:%M", time.localtime(n["time"])), xalign=1,
                                  css_classes=["dim-label", "notif-time"]))
            r.add_suffix(meta)
            rows.append(r)
        self.notif_group.set_rows(rows)
        self.notif_group.set_visible(bool(rows))
        if hasattr(self, "notif_empty"):
            self.notif_empty.set_visible(not rows)

    # ---- Komutlar -------------------------------------------------------------

    def _build_commands(self):
        from .araclar import Araclar
        page = Adw.PreferencesPage(title="Araçlar", icon_name="applications-utilities-symbolic")
        self.araclar = Araclar(self)
        page.add(self.araclar.group)
        self.cmd_off = Adw.PreferencesGroup(
            title="Bilgisayar komutları",
            description="Telefondan bu bilgisayarı kilitlemek, ekran görüntüsü almak ve kendi komutlarını çalıştırmak "
                        "için: Özellikler'de “Bilgisayar komutları”nı aç.")
        page.add(self.cmd_off)
        g = Adw.PreferencesGroup(
            title="Hazır komutlar",
            description="Telefondaki “Bilgisayar” sekmesinde görünür. Telefon yalnızca listelenenleri çalıştırabilir; "
                        "profilinde izin olmalı.")
        for p in pc.PRESETS:
            r = row(p["name"], " ".join(p["argv"]))
            r.add_prefix(Gtk.Image(icon_name="system-shutdown-symbolic" if p.get("power")
                                   else "system-lock-screen-symbolic"))
            g.add(r)
        for title, sub in (("Ekran görüntüsü", "Alınır ve telefona gönderilir (ilk seferde bilgisayar izin sorabilir)"),
                           ("Sistem durumu ve ses", "İşlemci, bellek, disk, pil; bilgisayarın ses düzeyi")):
            r = row(title, sub)
            r.add_prefix(Gtk.Image(icon_name="emblem-system-symbolic"))
            g.add(r)
        page.add(g)

        self.cmd_group = DynamicGroup(
            title="Özel komutlar",
            description="Kendi komutun (ör. “Yedeği başlat”). Senin kullanıcınla çalışır, çıktısı telefona döner; "
                        "en çok 2 dakika.")
        add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Komut ekle", css_classes=["flat"],
                         valign=Gtk.Align.CENTER)
        add.connect("clicked", lambda *_: self._edit_command(None))
        self.cmd_group.set_header_suffix(add)
        page.add(self.cmd_group)

        self.cmd_log_group = DynamicGroup(title="Telefondan çalıştırılanlar",
                                          description="Telefondan tetiklenen her komut burada ve masaüstü bildiriminde görünür.")
        page.add(self.cmd_log_group)
        self.cmd_log = []
        self._render_cmd_log()
        self.cmd_groups = [g, self.cmd_group, self.cmd_log_group]

        g = Adw.PreferencesGroup()
        terminal = row("Terminalden kullanım", "Uygulama açıkken bağlı telefona terminalden iş yaptırmak için",
                       cls=Adw.ExpanderRow)
        terminal.add_prefix(Gtk.Image(icon_name="utilities-terminal-symbolic"))
        g.add(terminal)
        for cmd, what in (("talk-to-android durum", "bağlı telefonlar, pil, profil"),
                          ("talk-to-android gonder foto.jpg rapor.pdf", "dosyaları telefona gönder"),
                          ("talk-to-android bildirim \"Derleme bitti\" \"0 hata\"", "telefonda bildirim göster"),
                          ("echo merhaba | talk-to-android pano", "telefonun panosuna kopyala"),
                          ("talk-to-android cal", "telefonu çaldır"),
                          ("talk-to-android medya sonraki", "telefondaki müziği atla")):
            r = row(cmd, what)
            r.add_css_class("monospace")
            r.add_suffix(icon_button("edit-copy-symbolic", "Kopyala", lambda c=cmd: self._copy(c)))
            terminal.add_row(r)
        page.add(g)
        return page

    def _copy(self, text):
        self.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(text))
        self.toast("Kopyalandı")

    def _update_commands(self):
        cmds = self.status.get("commands", [])
        if not self._changed("commands", cmds):
            return
        rows = []
        for c in cmds:
            r = row(c["name"], c["command"])
            r.add_prefix(Gtk.Image(icon_name="utilities-terminal-symbolic"))
            r.add_suffix(icon_button("media-playback-start-symbolic", "Burada dene", lambda c=c: self._try_command(c)))
            r.add_suffix(icon_button("document-edit-symbolic", "Düzenle", lambda c=c: self._edit_command(c)))
            r.add_suffix(icon_button("user-trash-symbolic", "Sil", lambda c=c: self.app.confirm(
                f"“{c['name']}” silinsin mi?", "Telefondaki listeden de kalkar.", "Sil",
                lambda: self.app.call("delete_command", c["id"]), destructive=True)))
            rows.append(r)
        if not rows:
            rows.append(row("Henüz özel komut yok", "Başlığın yanındaki + ile ekle"))
        self.cmd_group.set_rows(rows)

    def _edit_command(self, c):
        box = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        name = compat.EntryRow(title="Ad (telefonda görünür)", text=c["name"] if c else "")
        cmd = compat.EntryRow(title="Linux komutu", text=c["command"] if c else "")
        box.append(name)
        box.append(cmd)

        def save():
            if name.get_text().strip() and cmd.get_text().strip():
                self.app.call("save_command", c["id"] if c else None, name.get_text(), cmd.get_text())
        self.app.confirm("Komutu düzenle" if c else "Yeni komut",
                         "Telefondan bu adla tetiklenir; komut bu bilgisayarda senin kullanıcınla çalışır.",
                         "Kaydet", save, extra=box)

    def _try_command(self, c):
        if c["id"] in self._running_cmds:
            self.toast(f"{c['name']} zaten çalışıyor")
            return
        self._running_cmds.add(c["id"])
        self.toast(f"{c['name']} çalışıyor…")
        fut = self.app.hub.submit(pc.run_command(c["id"], [c], {"commands": True}))

        def show(res):
            self._running_cmds.discard(c["id"])
            self.app.show_output(c["name"], res)
            return False

        def done(f):
            try:
                res = f.result()
            except Exception as e:  # noqa: BLE001 — sonuç penceresinde gösterilir
                res = {"ok": False, "output": str(e)}
            GLib.idle_add(show, res)
        fut.add_done_callback(done)

    def add_command_log(self, d):
        self.cmd_log.insert(0, {**d, "time": time.time()})
        del self.cmd_log[20:]
        self._render_cmd_log()

    def _render_cmd_log(self):
        rows = [row(x["name"], f"{x['device']} · {time.strftime('%H:%M:%S', time.localtime(x['time']))}")
                for x in self.cmd_log]
        self.cmd_log_group.set_rows(rows)
        self.cmd_log_group.set_visible(bool(rows))
