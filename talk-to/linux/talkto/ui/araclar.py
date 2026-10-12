"""Tercihler → Araçlar: USB'deki telefon için geliştirici araçları (bkz. talkto.araclar).

Uygulamalar ve Dosyalar ayrı pencerelerde açılır; her iş bağlantı iş parçacığında (adb) yapılır, sonuç arayüze
döner. Geri dönüşü zor işler (veriyi silmek, kaldırmak, silmek, yeniden başlatmak) önce sorar.
"""

import posixpath
import subprocess
import time
from pathlib import Path

from gi.repository import Adw, Gio, GLib, Gtk

from .. import araclar
from . import compat


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return str(n)


def _row(title, subtitle=""):
    r = Adw.ActionRow(title=GLib.markup_escape_text(title), subtitle=GLib.markup_escape_text(subtitle or ""))
    r.set_subtitle_lines(3)
    return r


class Araclar:
    """Araçlar sayfasındaki "Telefon araçları" grubu."""

    def __init__(self, win):
        self.win = win
        self.app = win.app
        self.devices: list[dict] = []
        self.serial = None
        self.group = Adw.PreferencesGroup(
            title="Telefon araçları",
            description="USB'deki telefonda adb ile; geliştiriciler ve telefonu kurtarmak için. Root gerekmez. "
                        "Sistem uygulamasını kaldırmak bile yalnızca bu kullanıcı için gizler, geri yüklenebilir.")
        self.empty = _row("USB'de hazır telefon yok",
                          "Telefonu USB ile tak ve USB hata ayıklamayı aç (Telefonlar sayfası adım adım gösterir).")
        self.empty.add_prefix(Gtk.Image(icon_name="dialog-information-symbolic"))
        self.group.add(self.empty)
        self.pick = Adw.ComboRow(title="Telefon", model=Gtk.StringList.new([]))
        self.pick.connect("notify::selected", lambda *_: self._picked())
        self.group.add(self.pick)
        self.rows = []

        def tool(title, sub, label, cb, icon):
            r = _row(title, sub)
            r.add_prefix(Gtk.Image(icon_name=icon))
            b = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda *_: cb())
            r.add_suffix(b)
            self.group.add(r)
            self.rows.append(r)
            return r

        tool("Uygulamalar", "Zorla durdur, verilerini sil, devre dışı bırak, kaldır ya da geri yükle (sistem "
             "uygulamaları dahil)", "Aç", self.open_apps, "view-app-grid-symbolic")
        tool("Dosyalar", "Telefonun depolamasını gez; silinmeyen dosyaları (ör. Android/data) sil, bilgisayara al",
             "Aç", self.open_files, "folder-symbolic")
        tool("Telefonun kabuğu", "adb shell bir terminal penceresinde", "Aç", self.open_shell,
             "utilities-terminal-symbolic")
        tool("Sistem kaydı (logcat)", "Telefonun şu ana kadarki kaydını alınan dosyalar klasörüne yaz (hata "
             "bildirmek için)", "Kaydet", self.save_logcat, "text-x-generic-symbolic")
        self.anim = compat.SwitchRow(title="Animasyonlar",
                                     subtitle="Kapalıyken telefon daha çevik görünür (Geliştirici seçenekleri)")
        self.anim.connect("notify::active", lambda r, _: not self._sync and self._set_anim(r.get_active()))
        self._sync = False
        self.group.add(self.anim)
        self.rows.append(self.anim)
        r = _row("Yeniden başlat", "Normal, kurtarma (recovery) ya da önyükleyici (fastboot)")
        r.add_prefix(Gtk.Image(icon_name="system-reboot-symbolic"))
        menu = Gio.Menu()
        for mode, name in araclar.REBOOT_MODES.items():
            item = Gio.MenuItem.new(name, None)
            item.set_action_and_target_value("arac.reboot", GLib.Variant("s", mode))
            menu.append_item(item)
        r.add_suffix(Gtk.MenuButton(label="Seç", menu_model=menu, valign=Gtk.Align.CENTER))
        self.group.add(r)
        self.rows.append(r)
        actions = Gio.SimpleActionGroup()
        a = Gio.SimpleAction.new("reboot", GLib.VariantType.new("s"))
        a.connect("activate", lambda _a, v: self.confirm_reboot(v.get_string()))
        actions.add_action(a)
        self.group.insert_action_group("arac", actions)
        self.group.connect("map", lambda *_: self._refresh_anim())  # telefona yalnızca sayfa açılınca sorulur
        self.update({})

    # ---- telefon seçimi ---------------------------------------------------------------

    def update(self, snap):
        devices = [d for d in snap.get("devices", []) if d.get("state") == "device" and ":" not in d["serial"]]
        if [d["serial"] for d in devices] == [d["serial"] for d in self.devices]:
            return
        self.devices = devices
        self.pick.set_model(Gtk.StringList.new([d.get("name") or d.get("model") or d["serial"] for d in devices]))
        self.empty.set_visible(not devices)
        self.pick.set_visible(len(devices) > 1)
        for r in self.rows:
            r.set_sensitive(bool(devices))
        self._picked()

    def _picked(self):
        i = self.pick.get_selected()
        self.serial = self.devices[i]["serial"] if self.devices and 0 <= i < len(self.devices) else None
        if self.group.get_mapped():
            self._refresh_anim()

    def _refresh_anim(self):
        if self.serial and getattr(self.app, "hub", None):
            self.run(araclar.animations_on(self.serial), self._got_anim)

    def _got_anim(self, on):
        if on is not None:
            self._sync = True
            self.anim.set_active(on)
            self._sync = False

    def name(self):
        d = next((d for d in self.devices if d["serial"] == self.serial), {})
        return d.get("name") or d.get("model") or self.serial or "Telefon"

    # ---- ortak --------------------------------------------------------------------------

    def run(self, coro, done):
        """İşi bağlantı iş parçacığında yürütür; sonucu (ya da hatayı) arayüzde done'a verir."""
        fut = self.app.hub.submit(coro)

        def finished(f):
            try:
                res = f.result()
            except Exception as e:  # noqa: BLE001 — kullanıcıya gösterilir
                GLib.idle_add(lambda: self.toast(f"Olmadı: {e}") or False)
                return
            GLib.idle_add(lambda: done(res) or False)
        fut.add_done_callback(finished)

    def toast(self, text):
        self.win._prefs_toast(text)

    # ---- araçlar --------------------------------------------------------------------------

    def open_shell(self):
        cmd = araclar.terminal_command(self.serial) if self.serial else None
        if not cmd:
            self.toast("Terminal bulunamadı; terminalde: adb shell")
            return
        try:
            subprocess.Popen(cmd, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError as e:
            self.toast(f"Terminal açılamadı: {e}")

    def save_logcat(self):
        folder = Path(self.app.config["receive_dir"] or Path.home())
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"logcat-{self.name().replace(' ', '_')}-{time.strftime('%Y%m%d-%H%M%S')}.txt"
        self.toast("Sistem kaydı alınıyor…")
        self.run(araclar.logcat(self.serial, str(dest)),
                 lambda r: self.toast(f"Kaydedildi: {dest}" if r[0] else f"Kayıt alınamadı: {r[1]}"))

    def _set_anim(self, on):
        if self.serial:
            self.run(araclar.animations(self.serial, on),
                     lambda r: self.toast(("Animasyonlar açık" if on else "Animasyonlar kapalı") if r[0]
                                          else f"Olmadı: {r[1]}"))

    def confirm_reboot(self, mode):
        if not self.serial:
            return
        name = araclar.REBOOT_MODES.get(mode, mode)
        self.app.confirm(f"{self.name()} yeniden başlatılsın mı?",
                         f"Kip: {name}." + (" Kurtarma ve önyükleyici menüsünden telefonun tuşlarıyla çıkılır."
                                            if mode else ""),
                         "Yeniden başlat", lambda: self.run(araclar.reboot(self.serial, mode),
                                                            lambda r: self.toast("Yeniden başlatılıyor" if r[0]
                                                                                 else f"Olmadı: {r[1]}")),
                         destructive=True)

    def open_apps(self):
        if self.serial:
            AppsWindow(self, self.serial).present()

    def open_files(self):
        if self.serial:
            FilesWindow(self, self.serial).present()


class _ToolWindow(Adw.Window):
    def __init__(self, tools, serial, title):
        super().__init__(title=title, transient_for=tools.win.prefs_window or tools.win, default_width=560,
                         default_height=640, modal=False)
        self.tools, self.serial = tools, serial
        self.toasts = Adw.ToastOverlay()
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.header = Adw.HeaderBar(title_widget=Adw.WindowTitle(title=title, subtitle=tools.name()))
        self.box.append(self.header)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"], margin_top=12,
                                margin_bottom=12, valign=Gtk.Align.START)
        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(Adw.Clamp(maximum_size=640, child=self.list, margin_start=12, margin_end=12))
        self.box.append(scroll)
        self.toasts.set_child(self.box)
        self.set_content(self.toasts)

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=4))

    def clear(self):
        child = self.list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.list.remove(child)
            child = nxt

    def busy(self, text):
        self.clear()
        b = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER, margin_top=18, margin_bottom=18)
        b.append(Gtk.Spinner(spinning=True))
        b.append(Gtk.Label(label=text, css_classes=["dim-label"]))
        self.list.append(b)

    def confirm(self, heading, body, label, ok):
        dlg = compat.Dialog(self, heading, body)
        dlg.add_response("cancel", "Vazgeç")
        dlg.add_response("ok", label)
        dlg.set_appearance("ok", compat.DESTRUCTIVE)
        dlg.set_close_response("cancel")
        dlg.on_response(lambda r: ok() if r == "ok" else None)
        dlg.present()


class AppsWindow(_ToolWindow):
    def __init__(self, tools, serial):
        super().__init__(tools, serial, "Uygulamalar")
        self.search = Gtk.SearchEntry(placeholder_text="Paket ara")
        self.search.connect("search-changed", lambda *_: self.list.invalidate_filter())
        self.header.pack_start(self.search)
        self.system = Gtk.ToggleButton(label="Sistem", tooltip_text="Sistem uygulamalarını da göster")
        self.system.connect("toggled", lambda *_: self.list.invalidate_filter())
        self.header.pack_end(self.system)
        self.list.set_filter_func(self._filter)
        self.packages = []
        acts = Gio.SimpleActionGroup()
        a = Gio.SimpleAction.new("do", GLib.VariantType.new("s"))
        a.connect("activate", lambda _a, v: self._ask(*v.get_string().split("|", 1)))
        acts.add_action(a)
        self.insert_action_group("app", acts)
        self.load()

    def load(self):
        self.busy("Uygulamalar okunuyor…")
        self.tools.run(araclar.packages(self.serial), self._fill)

    def _filter(self, r):
        p = getattr(r, "paket", None)
        if p is None:
            return True
        q = self.search.get_text().strip().casefold()
        return (self.system.get_active() or not p.system) and (not q or q in p.name.casefold())

    def _fill(self, packages):
        self.clear()
        self.packages = packages
        for p in packages:
            state = ["sistem" if p.system else "kullanıcı"]
            if not p.installed:
                state.append("bu kullanıcı için kaldırılmış")
            elif not p.enabled:
                state.append("devre dışı")
            r = _row(p.name, " · ".join(state))
            r.paket = p
            menu = Gio.Menu()
            acts = (["restore"] if not p.installed else
                    ["stop", "clear", "enable" if not p.enabled else "disable", "uninstall"])
            for act in acts:
                item = Gio.MenuItem.new(araclar.APP_ACTIONS[act][0], None)
                item.set_action_and_target_value("app.do", GLib.Variant("s", f"{act}|{p.name}"))
                menu.append_item(item)
            r.add_suffix(Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu, valign=Gtk.Align.CENTER,
                                        css_classes=["flat"]))
            self.list.append(r)
        self.list.invalidate_filter()

    def _ask(self, act, package):
        label = araclar.APP_ACTIONS[act][0]
        texts = {"clear": "Uygulamanın bütün verileri (giriş, ayarlar, indirilenler) silinir; geri alınamaz.",
                 "uninstall": "Bu kullanıcı için kaldırılır; sistem uygulamasıysa listede “Geri yükle” ile geri gelir.",
                 "disable": "Uygulama çalışmaz ve menüde görünmez; “Etkinleştir” ile geri açılır. Bazı sistem "
                            "uygulamalarını kapatmak telefonun özelliklerini bozabilir."}
        go = lambda: self.tools.run(araclar.app_action(self.serial, package, act),  # noqa: E731
                                    lambda r: self._done(label, package, r))
        if act in texts:
            self.confirm(f"{package}: {label.lower()}?", texts[act], label, go)
        else:
            go()

    def _done(self, label, package, res):
        ok, text = res
        self.toast(f"{package}: {label.lower()} tamam" if ok else f"{package}: olmadı ({text[:120]})")
        if ok:
            self.load()


class FilesWindow(_ToolWindow):
    def __init__(self, tools, serial):
        super().__init__(tools, serial, "Dosyalar")
        self.path = "/sdcard"
        self.up = Gtk.Button(icon_name="go-up-symbolic", tooltip_text="Üst klasör")
        self.up.connect("clicked", lambda *_: self.go(posixpath.dirname(self.path) or "/"))
        self.header.pack_start(self.up)
        self.place = Gtk.Label(css_classes=["caption", "dim-label"], xalign=0, margin_start=18, margin_top=8,
                               selectable=True, wrap=True)
        self.box.insert_child_after(self.place, self.header)
        acts = Gio.SimpleActionGroup()
        for name, cb in (("pull", self._pull), ("delete", self._delete)):
            a = Gio.SimpleAction.new(name, GLib.VariantType.new("s"))
            a.connect("activate", lambda _a, v, cb=cb: cb(v.get_string()))
            acts.add_action(a)
        self.insert_action_group("dosya", acts)
        self.go(self.path)

    def go(self, path):
        self.path = posixpath.normpath(path)
        self.place.set_label(self.path + ("" if araclar.deletable(self.path + "/x") else
                                          "  (salt okunur: yalnızca /sdcard altındakiler silinebilir)"))
        self.up.set_sensitive(self.path != "/")
        self.busy("Okunuyor…")
        self.tools.run(araclar.list_dir(self.serial, self.path), self._fill)

    def _fill(self, entries):
        self.clear()
        if not entries:
            self.list.append(_row("Boş klasör (ya da okuma izni yok)"))
        for g in entries:
            full = posixpath.join(self.path, g.name)
            r = _row(g.name, ("klasör" if g.is_dir else human_size(g.size)) + f" · {g.when}" +
                     (" · bağlantı" if g.link else ""))
            r.add_prefix(Gtk.Image(icon_name="folder-symbolic" if g.is_dir else "text-x-generic-symbolic"))
            if g.is_dir:
                r.set_activatable(True)
                r.connect("activated", lambda _r, p=full: self.go(p))
            menu = Gio.Menu()
            item = Gio.MenuItem.new("Bilgisayara al", None)
            item.set_action_and_target_value("dosya.pull", GLib.Variant("s", full))
            menu.append_item(item)
            if araclar.deletable(full):
                item = Gio.MenuItem.new("Sil", None)
                item.set_action_and_target_value("dosya.delete", GLib.Variant("s", full))
                menu.append_item(item)
            r.add_suffix(Gtk.MenuButton(icon_name="view-more-symbolic", menu_model=menu, valign=Gtk.Align.CENTER,
                                        css_classes=["flat"]))
            self.list.append(r)

    def _pull(self, path):
        folder = Path(self.tools.app.config["receive_dir"] or Path.home())
        folder.mkdir(parents=True, exist_ok=True)
        self.toast(f"Alınıyor: {posixpath.basename(path)}…")
        self.tools.run(araclar.pull(self.serial, path, str(folder)),
                       lambda r: self.toast(f"Alındı → {folder}" if r[0] else f"Alınamadı: {r[1]}"))

    def _delete(self, path):
        name = posixpath.basename(path)
        self.confirm(f"“{name}” silinsin mi?", f"{path}\nTelefondan kalıcı olarak silinir (çöp kutusu yok).", "Sil",
                     lambda: self.tools.run(araclar.delete(self.serial, path), lambda r: self._deleted(name, r)))

    def _deleted(self, name, res):
        ok, text = res
        self.toast(f"Silindi: {name}" if ok else f"Silinemedi: {text[:120]}")
        self.go(self.path)

