"""Ana pencere: Bağlantı · Cihazlar · Medya · Dosyalar · Bildirimler."""

import json
import time
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from .. import pc
from ..config import Config
from . import system

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


def row(title="", subtitle="", cls=Adw.ActionRow, **kw):
    """Dışarıdan gelen metin (bildirim, cihaz adı) işaretleme sayılmasın."""
    r = cls(title=title, use_markup=False, **kw)
    if subtitle:
        r.set_subtitle(subtitle)
    return r


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
    def __init__(self, win, device_id):
        super().__init__(spacing=18, css_classes=["card", "media-card"])
        self.win, self.device_id = win, device_id
        self.state = {}
        self.art_id = None

        self.art_stack = Gtk.Stack(valign=Gtk.Align.START)
        ph = Gtk.Image(icon_name="audio-x-generic-symbolic", pixel_size=48,
                       css_classes=["art-placeholder"], width_request=128, height_request=128)
        self.pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, width_request=128, height_request=128,
                               css_classes=["art"], overflow=Gtk.Overflow.HIDDEN)
        self.art_stack.add_named(ph, "yok")
        self.art_stack.add_named(self.pic, "var")
        self.append(self.art_stack)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        self.source = Gtk.Label(xalign=0, css_classes=["caption", "dim-label"], ellipsize=Pango.EllipsizeMode.END)
        self.title = Gtk.Label(xalign=0, css_classes=["title-3"], ellipsize=Pango.EllipsizeMode.END)
        self.artist = Gtk.Label(xalign=0, css_classes=["dim-label"], ellipsize=Pango.EllipsizeMode.END)
        for w in (self.source, self.title, self.artist):
            col.append(w)

        self.progress = Gtk.Scale(draw_value=False, hexpand=True, margin_top=6)
        self.progress.set_range(0, 1)
        self.progress.connect("change-value", self._on_seek)
        col.append(self.progress)
        times = Gtk.Box(css_classes=["caption", "dim-label"])
        self.pos_label = Gtk.Label(xalign=0, hexpand=True)
        self.dur_label = Gtk.Label(xalign=1)
        times.append(self.pos_label)
        times.append(self.dur_label)
        col.append(times)

        controls = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER, margin_top=4)
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
        self._vol_sent = 0.0

    def _cmd(self, action, value=None):
        self.win.app.call("media_control", self.device_id, action, value)

    def _on_seek(self, _scale, _scroll, value):
        self._cmd("seek", int(value))
        self.state["position_ms"] = int(value)
        self.state["received_at"] = time.monotonic()
        return False

    def _on_volume(self, _scale, _scroll, value):
        now = time.monotonic()
        if now - self._vol_sent > 0.08:
            self._vol_sent = now
            self._cmd("volume", int(max(0, min(100, value))))
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
        self.media_cards: dict[str, MediaCard] = {}
        self.art_paths: dict[str, str] = {}
        self.ringing: set[str] = set()

        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(switcher)
        menu = Gio.Menu()
        menu.append("Hakkında", "app.about")
        menu.append("Tamamen kapat", "app.quit")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Menü"))
        view.add_top_bar(header)
        self.banner = Adw.Banner()
        view.add_top_bar(self.banner)
        bottom = Adw.ViewSwitcherBar(stack=self.stack)
        view.add_bottom_bar(bottom)
        view.set_content(self.stack)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
        bp.add_setter(bottom, "reveal", True)
        bp.add_setter(switcher, "visible", False)
        self.add_breakpoint(bp)

        self.stack.add_titled_with_icon(self._build_connection(), "baglanti", "Bağlantı",
                                        "network-wireless-symbolic")
        self.stack.add_titled_with_icon(self._build_devices(), "cihazlar", "Cihazlar", "phone-symbolic")
        self.stack.add_titled_with_icon(self._build_media(), "medya", "Medya", "media-playback-start-symbolic")
        self.stack.add_titled_with_icon(self._build_files(), "dosyalar", "Dosyalar", "folder-symbolic")
        self.stack.add_titled_with_icon(self._build_notifications(), "bildirimler", "Bildirimler",
                                        "preferences-system-notifications-symbolic")
        self.stack.add_titled_with_icon(self._build_commands(), "komutlar", "Komutlar", "utilities-terminal-symbolic")

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        drop.connect("enter", lambda *_: self.dropzone.add_css_class("drop-active") or Gdk.DragAction.COPY)
        drop.connect("leave", lambda *_: self.dropzone.remove_css_class("drop-active"))
        self.add_controller(drop)

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

    # ---- Bağlantı -----------------------------------------------------------

    def _build_connection(self):
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
        hero.append(texts)
        hero_group.add(hero)
        page.add(hero_group)

        g = self.wifi_group = Adw.PreferencesGroup(title="Kablosuz (Wi-Fi)")
        self.sw_wireless = Adw.SwitchRow(title="Kablosuz bağlantıyı aç",
                                         subtitle="Açıkken bu bilgisayar yerel ağda görünür")
        self.sw_wireless.connect("notify::active", lambda r, _: self._set("wireless", r.get_active()))
        g.add(self.sw_wireless)
        self.addr_row = Adw.ActionRow(title="Adres", css_classes=["property"])
        self.addr_row.add_suffix(icon_button("edit-copy-symbolic", "Kopyala", self._copy_address))
        g.add(self.addr_row)
        self.pw_row = Adw.PasswordEntryRow(title="Şifre (isteğe bağlı)", show_apply_button=True)
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
            description="Telefonda Geliştirici seçenekleri → USB hata ayıklama açık olmalı. "
                        "Her yeni telefon için burada onay istenir.")
        self.sw_usb = Adw.SwitchRow(title="USB bağlantısı", subtitle="adb ile tünel kurulur, internet gerekmez")
        self.sw_usb.connect("notify::active", lambda r, _: self._set("usb", r.get_active()))
        g.add(self.sw_usb)
        page.add(g)
        self.usb_group = DynamicGroup()
        page.add(self.usb_group)

        g = Adw.PreferencesGroup(
            title="Bluetooth",
            description="Önce telefonu sistemin Bluetooth ayarlarından bu bilgisayarla eşleştir; sonra telefondaki "
                        "uygulamada bilgisayarı “Bluetooth” altında seç. Her yeni telefon için burada onay istenir. "
                        "Bildirim, medya ve komutlar için yeterli; büyük dosyalarda Wi-Fi ya da USB çok daha hızlı.")
        self.sw_bt = Adw.SwitchRow(title="Bluetooth bağlantısı")
        self.sw_bt.connect("notify::active", lambda r, _: self._set_bluetooth(r.get_active()))
        g.add(self.sw_bt)
        self.bt_row = Adw.ActionRow(title="Durum", css_classes=["property"])
        self.bt_row.set_subtitle_lines(3)
        self.bt_icon = Gtk.Image(icon_name="bluetooth-symbolic")
        self.bt_row.add_prefix(self.bt_icon)
        g.add(self.bt_row)
        page.add(g)

        g = Adw.PreferencesGroup(title="Genel")
        self.name_row = Adw.EntryRow(title="Bu bilgisayarın adı", show_apply_button=True)
        self.name_row.set_text(self.app.config["name"])
        self.name_row.connect("apply", lambda r: self._set("name", r.get_text().strip()[:64] or "Linux"))
        g.add(self.name_row)
        self.sw_bg = Adw.SwitchRow(title="Pencere kapanınca arka planda çalışsın",
                                   subtitle="Telefon bağlı kalır, bildirimler gelmeye devam eder")
        self.sw_bg.set_active(self.app.config["run_in_background"])
        self.sw_bg.connect("notify::active", lambda r, _: self._set("run_in_background", r.get_active()))
        g.add(self.sw_bg)
        self.sw_autostart = Adw.SwitchRow(title="Oturum açılınca başlat",
                                          subtitle="Pencere açılmadan arka planda başlar; telefon kendiliğinden bağlanır")
        self.sw_autostart.set_active(system.autostart_enabled())
        self.sw_autostart.connect("notify::active", lambda r, _: system.set_autostart(r.get_active()))
        g.add(self.sw_autostart)
        page.add(g)
        return page

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

    def update_status(self, st):
        self.status = st
        self._updating = True
        try:
            self.sw_wireless.set_active(st["wireless"])
            self.sw_usb.set_active(st["usb"])
            self.sw_bt.set_active(st["bluetooth"])
        finally:
            self._updating = False
        bt = st.get("bt") or {}
        self.bt_row.set_subtitle(bt.get("message", "") if st["bluetooth"] else "Kapalı")
        self.bt_icon.set_from_icon_name("bluetooth-active-symbolic" if st["bluetooth"] and bt.get("available")
                                        else "bluetooth-disabled-symbolic")

        sessions = st["sessions"]
        if sessions:
            self.hero_icon.set_from_icon_name("phone-symbolic")
            names = ", ".join(s["name"] for s in sessions)
            self.hero_title.set_text(names if len(sessions) < 3 else f"{len(sessions)} cihaz bağlı")
            self.hero_sub.set_text("Bağlı. Bildirimler, medya ve dosyalar hazır.")
        elif st["listening"] or (st["bluetooth"] and bt.get("available")):
            self.hero_icon.set_from_icon_name("computer-symbolic")
            self.hero_title.set_text(st["name"])
            ways = [w for w, on in (("kablosuz", st["wireless"]), ("USB", st["usb"]),
                                    ("Bluetooth", st["bluetooth"] and bt.get("available"))) if on]
            self.hero_sub.set_text(f"Telefon bekleniyor ({', '.join(ways)}).")
        else:
            self.hero_icon.set_from_icon_name("network-offline-symbolic")
            self.hero_title.set_text(st["name"])
            self.hero_sub.set_text("Bağlantı kapalı. Aşağıdan kablosuz, USB ya da Bluetooth bağlantısını aç.")
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
            self.hero_chips.append(Gtk.Label(label=text, css_classes=["chip"]))
        self.hero_chips.set_visible(bool(sessions))

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

    def update_usb(self, snap):
        self.usb = snap
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
        elif not snap.get("devices"):
            r = row("Telefon bekleniyor", "Telefonu USB ile tak ve USB hata ayıklamayı aç. Telefonda Talk To Linux "
                                          "yoksa buradan tek tıkla kurulur." if snap.get("apk") else
                    "Telefonu USB ile tak ve USB hata ayıklamayı aç")
            r.set_subtitle_lines(3)
            r.add_prefix(Gtk.Image(icon_name="media-removable-symbolic"))
            rows.append(r)
        for d in snap.get("devices", []):
            state = d["state"]
            if state == "device":
                sub = "Tünel hazır: telefondaki uygulamada “USB” seç" if d["tunnel"] else "Tünel kurulamadı"
                if d.get("app") is False and snap.get("apk"):
                    sub = "Telefonda Talk To Linux yok: sağdaki düğmeyle kur, sonra uygulamada “USB” seç"
                icon = "emblem-ok-symbolic" if d["tunnel"] else "dialog-warning-symbolic"
            elif state == "unauthorized":
                sub, icon = "Telefonda “USB hata ayıklamaya izin ver” onayını ver", "dialog-question-symbolic"
            else:
                sub, icon = f"Durum: {state}", "dialog-warning-symbolic"
            r = row(d.get("model") or d["serial"], sub)
            r.add_prefix(Gtk.Image(icon_name=icon))
            if state == "device" and snap.get("apk"):
                if d.get("installing"):
                    r.add_suffix(Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER))
                else:
                    label = "Talk To Linux'u güncelle" if d.get("app") else "Talk To Linux'u kur"
                    b = Gtk.Button(label=label, valign=Gtk.Align.CENTER,
                                   css_classes=[] if d.get("app") else ["suggested-action"],
                                   tooltip_text="USB üzerinden telefona kurar ve açar")
                    b.connect("clicked", lambda *_, sr=d["serial"]: self.app.install_phone_app(sr))
                    r.add_suffix(b)
            rows.append(r)
        self.usb_group.set_rows(rows)

    # ---- Cihazlar -------------------------------------------------------------

    def _build_devices(self):
        page = Adw.PreferencesPage()
        self.connected_group = DynamicGroup(title="Bağlı cihazlar")
        page.add(self.connected_group)
        self.trusted_group = DynamicGroup(
            title="Güvenilen cihazlar",
            description="Bu telefonlar bir kez onaylandı; tekrar bağlanırken onay ya da şifre sorulmaz. "
                        "Bağlandıkları anda tanınır ve seçili profilleri uygulanır.")
        page.add(self.trusted_group)
        self.profile_group = DynamicGroup(
            title="Profiller",
            description="Profil, bir telefonun bu bilgisayarda neleri yapabileceğini belirler. "
                        "Her telefon bir profile bağlıdır; profili değiştirmek bağlı telefona hemen uygulanır.")
        add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Yeni profil", css_classes=["flat"],
                         valign=Gtk.Align.CENTER)
        add.connect("clicked", lambda *_: self.app.call("save_profile", None, {"name": "Yeni profil"}))
        self.profile_group.set_header_suffix(add)
        page.add(self.profile_group)
        self._sig = {}
        return page

    def _changed(self, key, *data) -> bool:
        """Grup yalnızca içeriği gerçekten değişince yeniden kurulsun (açık satırlar kapanmasın)."""
        sig = json.dumps(data, sort_keys=True, default=str)
        if self._sig.get(key) == sig:
            return False
        self._sig[key] = sig
        return True

    def _update_devices(self):
        rows = []
        for s in self.status.get("sessions", []):
            sub = [KIND.get(s["kind"], s["kind"]), s["ip"] if s["kind"] == "wifi" else None]
            if s.get("battery"):
                b = s["battery"]
                sub.append(f"%{b['level']} pil" + (", şarj oluyor" if b["charging"] else ""))
            sub.append(f"profil: {s.get('profile_name', '?')}")
            r = row(s["name"], " · ".join(x for x in sub if x))
            r.add_prefix(Gtk.Image(icon_name="phone-symbolic", pixel_size=24))
            did = s["device_id"]
            r.add_suffix(icon_button("document-send-symbolic", "Dosya gönder", lambda d=did: self.pick_files(d)))
            r.add_suffix(icon_button("edit-paste-symbolic", "Panoyu telefona gönder",
                                     lambda d=did: self.app.send_clipboard(d)))
            ringing = did in self.ringing
            r.add_suffix(icon_button("audio-volume-high-symbolic",
                                     "Çalmayı durdur" if ringing else "Telefonu çaldır (bul)",
                                     lambda d=did: self._ring(d), *(["accent"] if ringing else [])))
            r.add_suffix(icon_button("window-close-symbolic", "Bağlantıyı kes",
                                     lambda d=did: self.app.call("disconnect", d)))
            rows.append(r)
        if not rows:
            rows.append(row("Henüz bağlı telefon yok", "Telefonda Talk To Linux uygulamasını açıp bu bilgisayarı seç"))
        self.connected_group.set_rows(rows)

        profiles = self.status.get("profiles", {})
        trusted = self.status.get("trusted", [])
        if self._changed("trusted", trusted, {k: v["name"] for k, v in profiles.items()}):
            self._render_trusted(trusted, profiles)
        if self._changed("profiles", profiles, self.status.get("default_profile"),
                         [t["profile"] for t in trusted]):
            self._render_profiles(profiles, trusted)

    def _render_trusted(self, trusted, profiles):
        rows = []
        pids = list(profiles)
        names = Gtk.StringList.new([profiles[p]["name"] for p in pids])
        for t in sorted(trusted, key=lambda t: -t["paired_at"]):
            when = time.strftime("%d.%m.%Y", time.localtime(t["paired_at"]))
            r = row(t["name"], f"{t['model']} · eşleşme {when}" if t["model"] else f"eşleşme {when}",
                    cls=Adw.ComboRow, model=names)
            if t["profile"] in pids:
                r.set_selected(pids.index(t["profile"]))
            r.connect("notify::selected", lambda r, _, d=t["device_id"]:
                      self.app.call("assign_profile", d, pids[r.get_selected()]))
            r.add_suffix(icon_button("user-trash-symbolic", "Unut (bir daha onay/şifre gerekir)",
                                     lambda t=t: self._confirm_forget(t)))
            rows.append(r)
        if not rows:
            rows.append(row("Henüz yok"))
        self.trusted_group.set_rows(rows)

    def _render_profiles(self, profiles, trusted):
        rows = []
        default = self.status.get("default_profile")
        for pid, prof in profiles.items():
            count = sum(1 for t in trusted if t["profile"] == pid)
            sub = [f"{count} telefon"] + (["yeni telefonlar bununla başlar"] if pid == default else [])
            exp = Adw.ExpanderRow(title=prof["name"], subtitle=" · ".join(sub), use_markup=False)
            exp.add_prefix(Gtk.Image(icon_name="avatar-default-symbolic"))
            name = Adw.EntryRow(title="Profil adı", show_apply_button=True, text=prof["name"])
            name.connect("apply", lambda r, p=pid: self.app.call("save_profile", p, {"name": r.get_text()}))
            exp.add_row(name)
            for key, label in Config.PERMISSIONS.items():
                sw = Adw.SwitchRow(title=label, active=bool(prof.get(key)))
                sw.connect("notify::active", lambda r, _, p=pid, k=key:
                           self.app.call("save_profile", p, {k: r.get_active()}))
                exp.add_row(sw)
            folder = Adw.ActionRow(title="Kayıt klasörü", css_classes=["property"],
                                   subtitle=prof.get("receive_dir") or "Genel ayar (Dosyalar sayfası)")
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
        dlg = Gtk.FileDialog(title="Bu profildeki telefonlardan gelen dosyalar nereye kaydedilsin?")

        def done(d, res):
            try:
                f = d.select_folder_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                self.app.call("save_profile", pid, {"receive_dir": f.get_path()})
        dlg.select_folder(self, None, done)

    def _ring(self, did):
        on = did not in self.ringing
        (self.ringing.add if on else self.ringing.discard)(did)
        self.app.call("ring", did, on)
        self._update_devices()
        if on:
            GLib.timeout_add_seconds(30, lambda: (self.ringing.discard(did), self._update_devices(), False)[-1])

    def _confirm_forget(self, t):
        self.app.confirm(f"“{t['name']}” unutulsun mu?",
                         "Bu telefon bir dahaki bağlantıda yeniden onay ya da şifre isteyecek.",
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

        g = Adw.PreferencesGroup(title="Bu bilgisayar")
        self.sw_share_media = Adw.SwitchRow(
            title="Bu bilgisayarda çalanı telefondan kontrol et",
            subtitle="Spotify, tarayıcıda YouTube, VLC… (MPRIS destekleyen her oynatıcı)")
        self.sw_share_media.set_active(self.app.config["share_media"])
        self.sw_share_media.connect("notify::active", lambda r, _: self._set("share_media", r.get_active()))
        g.add(self.sw_share_media)
        page.add(g)
        return page

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
        self.dir_row.set_subtitle(self.app.config["receive_dir"])
        self.dir_row.add_prefix(Gtk.Image(icon_name="folder-download-symbolic"))
        self.dir_row.add_suffix(icon_button("folder-open-symbolic", "Klasörü aç", self.open_receive_dir))
        self.dir_row.add_suffix(icon_button("document-edit-symbolic", "Klasörü değiştir", self._choose_dir))
        g.add(self.dir_row)
        self.sw_accept = Adw.SwitchRow(title="Gelen dosyaları sormadan kabul et",
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
        Gtk.FileLauncher.new(Gio.File.new_for_path(str(d))).launch(self, None, None)

    def _choose_dir(self):
        dlg = Gtk.FileDialog(title="Gelen dosyalar nereye kaydedilsin?")
        dlg.set_initial_folder(Gio.File.new_for_path(str(Path(self.app.config["receive_dir"]).expanduser().parent)))

        def done(d, res):
            try:
                f = d.select_folder_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                self._set("receive_dir", f.get_path())
                self.dir_row.set_subtitle(f.get_path())
        dlg.select_folder(self, None, done)

    def pick_files(self, device_id):
        did = device_id or (self.target() or {}).get("device_id")
        if not did:
            return
        dlg = Gtk.FileDialog(title="Telefona gönderilecek dosyalar")

        def done(d, res):
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error:
                return
            for i in range(files.get_n_items()):
                p = files.get_item(i).get_path()
                if p:
                    self.app.call("send_file", did, p)
        dlg.open_multiple(self, None, done)

    def _on_drop(self, _target, value, _x, _y):
        self.dropzone.remove_css_class("drop-active")
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

    def update_transfer(self, tr):
        key = f"{tr['device_id']}:{tr['direction']}:{tr['tid']}"
        tr["at"] = self.transfers.get(key, {}).get("at", time.time())
        self.transfers[key] = tr
        if len(self.transfers) > 30:
            for k in sorted(self.transfers, key=lambda k: self.transfers[k]["at"])[:-30]:
                del self.transfers[k]
        self._render_transfers()

    def _render_transfers(self):
        rows = []
        for tr in sorted(self.transfers.values(), key=lambda t: -t["at"]):
            arrow = "Telefondan" if tr["direction"] == "in" else "Telefona"
            size = human_size(tr["size"])
            state = tr["state"]
            text = {"waiting": "bekliyor", "active": f"{human_size(tr['done'])} / {size}", "done": size,
                    "failed": f"başarısız: {tr.get('error') or ''}", "rejected": "reddedildi",
                    "cancelled": "iptal edildi"}.get(state, state)
            r = row(tr["name"], f"{arrow} ({tr['device']}) · {text}")
            r.add_prefix(Gtk.Image(icon_name="go-down-symbolic" if tr["direction"] == "in" else "go-up-symbolic"))
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
        if not rows:
            rows.append(row("Henüz aktarım yok", "Telefonda bir dosyayı “Paylaş → Talk To Linux” ile gönderebilirsin"))
        self.transfer_group.set_rows(rows)

    # ---- Bildirimler ----------------------------------------------------------

    def _build_notifications(self):
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup()
        self.sw_notif = Adw.SwitchRow(title="Telefon bildirimlerini masaüstünde göster",
                                      subtitle="Telefonda Talk To Linux uygulamasına “bildirim erişimi” verilmiş olmalı")
        self.sw_notif.set_active(self.app.config["show_notifications"])
        self.sw_notif.connect("notify::active", lambda r, _: self._set("show_notifications", r.get_active()))
        g.add(self.sw_notif)
        page.add(g)
        self.notif_group = DynamicGroup(title="Son bildirimler")
        page.add(self.notif_group)
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
        if not rows:
            rows.append(row("Henüz bildirim yok"))
        self.notif_group.set_rows(rows)

    # ---- Komutlar -------------------------------------------------------------

    def _build_commands(self):
        page = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(
            title="Hazır komutlar",
            description="Telefondaki uygulamada “Bilgisayar” bölümünde görünür. Telefon yalnızca burada listelenenleri "
                        "tetikleyebilir; profilde “komut çalıştırabilir” açık olmalı (güç komutları için ayrıca "
                        "“uyku / kapat / yeniden başlat”).")
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
            description="Kendi Linux komutlarını ekle (ör. “Yedeği başlat”: rsync -a ~/Belgeler /mnt/yedek). "
                        "Komut senin kullanıcınla, ev klasöründe sh -c ile çalışır; çıktısı telefona döner. "
                        "En çok 2 dakika sürebilir.")
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

        g = Adw.PreferencesGroup(
            title="Terminalden kullanım",
            description="Uygulama açıkken (arka planda da olur) bağlı telefona terminalden iş yaptırabilirsin.")
        for cmd, what in (("talk-to-android durum", "bağlı telefonlar, pil, profil"),
                          ("talk-to-android gonder foto.jpg rapor.pdf", "dosyaları telefona gönder"),
                          ("talk-to-android bildirim \"Derleme bitti\" \"0 hata\"", "telefonda bildirim göster"),
                          ("echo merhaba | talk-to-android pano", "telefonun panosuna kopyala"),
                          ("talk-to-android cal", "telefonu çaldır"),
                          ("talk-to-android medya sonraki", "telefondaki müziği atla")):
            r = row(cmd, what)
            r.add_css_class("monospace")
            r.add_suffix(icon_button("edit-copy-symbolic", "Kopyala", lambda c=cmd: self._copy(c)))
            g.add(r)
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
            rows.append(row("Henüz özel komut yok", "Sağ üstteki + ile ekle"))
        self.cmd_group.set_rows(rows)

    def _edit_command(self, c):
        box = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        name = Adw.EntryRow(title="Ad (telefonda görünür)", text=c["name"] if c else "")
        cmd = Adw.EntryRow(title="Linux komutu", text=c["command"] if c else "")
        box.append(name)
        box.append(cmd)

        def save():
            if name.get_text().strip() and cmd.get_text().strip():
                self.app.call("save_command", c["id"] if c else None, name.get_text(), cmd.get_text())
        self.app.confirm("Komutu düzenle" if c else "Yeni komut",
                         "Telefondan bu adla tetiklenir; komut bu bilgisayarda senin kullanıcınla çalışır.",
                         "Kaydet", save, extra=box)

    def _try_command(self, c):
        self.toast(f"{c['name']} çalışıyor…")
        fut = self.app.hub.submit(pc.run_command(c["id"], [c], {"commands": True}))

        def done(f):
            res = f.result()
            GLib.idle_add(lambda: self.app.show_output(c["name"], res) and False)
        fut.add_done_callback(done)

    def add_command_log(self, d):
        self.cmd_log.insert(0, {**d, "time": time.time()})
        del self.cmd_log[20:]
        self._render_cmd_log()

    def _render_cmd_log(self):
        rows = [row(x["name"], f"{x['device']} · {time.strftime('%H:%M:%S', time.localtime(x['time']))}")
                for x in self.cmd_log]
        if not rows:
            rows.append(row("Henüz yok"))
        self.cmd_log_group.set_rows(rows)
