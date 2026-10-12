"""Arayüz (GTK 4 + libadwaita; Ubuntu 22.04'teki libadwaita 1.1'de olan parçalarla).

Akış: dosya → okunuyor → özet (sürüm, yayıncı, değişiklikler, tek ana düğme) → kuruluyor → bitti/olmadı.
Kaldırma: kurulu uygulamalar → seç → özet (başka ne gidecek) → kaldırılıyor → bitti/olmadı.
Olmayınca apt'nin çıktısı anlaşılır bir açıklamaya çevrilir (hatalar.py); onarılabiliyorsa "Onar" düğmesi.
Riskli durumlarda (farklı yayıncı, paket kaldırma, eski sürüme dönme) ana düğme ancak kullanıcı ilgili
kutuyu işaretleyince açılır: karar kullanıcıda, ama bilerek verilir.
"""

import os
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import APP_ID, __version__, apt, calisan, dil, durdur, hatalar, iliski, imza, paket, veriler, yayinci  # noqa: E402,E501
from .dil import N_, _t, _tn  # noqa: E402


def verdict_text(v):
    return {
        paket.KUR: (_t("Yeni kurulum"), _t("Bu bilgisayarda kurulu değil.")),
        paket.GUNCELLE: (_t("Güncelleme"), _t("Daha yeni bir sürüm.")),
        paket.AYNI: (_t("Aynı sürüm"), _t("Bu sürüm zaten kurulu; yeniden kurulabilir.")),
        paket.ESKI: (_t("Eski sürüm"), _t("Kurulu olandan daha eski. Geri dönmek ayarları bozabilir.")),
        paket.UYUMSUZ: (_t("Bu bilgisayara uygun değil"), _t("Paket başka bir işlemci mimarisi için.")),
    }[v]


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", _t(","))
        n /= 1024
    return str(n)


def desktop_app(desktop_id):
    """Kurulu masaüstü uygulaması ya da None (PyGObject bulunamayınca istisna atar)."""
    try:
        return Gio.DesktopAppInfo.new(desktop_id)
    except TypeError:
        return None


def row(title, subtitle="", icon=None, css=None):
    r = Adw.ActionRow(title=GLib.markup_escape_text(title), subtitle=GLib.markup_escape_text(subtitle or ""))
    r.set_subtitle_lines(6)
    if icon:
        r.add_prefix(Gtk.Image(icon_name=icon, css_classes=css or []))
    return r


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Paket Güncelleyici"), default_width=560, default_height=720)
        self.app = app
        self.pkg: paket.Paket | None = None
        self.sig: imza.Sonuc | None = None
        self.sim: apt.Deneme | None = None
        self.copy: str | None = None
        self.checks: list[Gtk.CheckButton] = []
        self.busy = False
        self.card: yayinci.Kart | None = None
        self.site: yayinci.Dogrulama | None = None  # site doğrulamasının sonucu (bitince)
        self._generation = 0  # başka paket açılınca eski doğrulamanın sonucu yok sayılır

        self.toasts = Adw.ToastOverlay()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar()
        self.title = Adw.WindowTitle(title=_t("Paket Güncelleyici"))
        header.set_title_widget(self.title)
        self.open_btn = Gtk.Button(icon_name="document-open-symbolic", tooltip_text=_t("Başka bir paket aç"))
        self.open_btn.connect("clicked", lambda *_: self.choose())
        header.pack_start(self.open_btn)
        # Geri: uygulamanın verileri / kaldırma özeti / sonuç sayfasından listeye (ya da boş sayfaya) döner.
        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text=_t("Geri (Alt+Sol)"), visible=False)
        self.back_btn.connect("clicked", lambda *_: self.go_back())
        header.pack_start(self.back_btn)
        self.apps_btn = Gtk.Button(icon_name="view-list-symbolic", tooltip_text=_t("Kurulu uygulamalar (kaldırmak ya da verilerini temizlemek için)"))
        self.apps_btn.connect("clicked", lambda *_: self.show_apps())
        header.pack_start(self.apps_btn)
        menu = Gio.Menu()
        langs = Gio.Menu()
        langs.append(_t("Sistem dili"), f"app.dil::{dil.SYSTEM}")
        for code, name in dil.available():
            langs.append(name, f"app.dil::{code}")
        menu.append_submenu(_t("Dil") + " (Language)", langs)
        menu.append(_t("Hakkında"), "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text=_t("Menü")))
        box.append(header)
        self.stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        box.append(self.stack)
        self.toasts.set_child(box)
        self.set_content(self.toasts)

        empty = Adw.StatusPage(icon_name="package-x-generic-symbolic", title=_t("Bir paket dosyası aç"),
                               description=_t("Bir .deb dosyasına sağ tıklayıp “Birlikte aç → Paket Güncelleyici”yi "
                                              "seç ya da buradan seç. Kurulu sürümle karşılaştırılır, yayıncının "
                                              "imzası denetlenir; kurmadan önce ne değişeceği gösterilir."))
        eb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER)
        b = Gtk.Button(label=_t("Dosya seç"), css_classes=["pill", "suggested-action"])
        b.connect("clicked", lambda *_: self.choose())
        eb.append(b)
        b = Gtk.Button(label=_t("Kurulu uygulamalar"), css_classes=["pill"],
                       tooltip_text=_t("Kaldırmak ya da verilerini temizlemek için: paketle kurulmuş uygulamalar, "
                                       "dosyadan kurulanlar üstte"))
        b.connect("clicked", lambda *_: self.show_apps())
        eb.append(b)
        # Çift tıklayınca .deb'ler bununla açılsın: yalnızca kullanıcı isterse (varsayılanı değiştirir).
        self.default_btn = Gtk.Button(label=_t("Çift tıklayınca .deb dosyaları bununla açılsın"), css_classes=["flat"])
        self.default_btn.connect("clicked", lambda *_: self._make_default())
        self.default_btn.set_visible(iliski.app_info() is not None and not iliski.is_default())
        eb.append(self.default_btn)
        empty.set_child(eb)
        self.stack.add_named(empty, "bos")

        # Kurulu uygulamalar: arama + liste (yüklenirken dönen gösterge).
        apps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search = Gtk.SearchEntry(placeholder_text=_t("Uygulama ara"), margin_top=12, margin_start=18,
                                      margin_end=18, margin_bottom=6)
        self.search.connect("search-changed", lambda *_: self.app_list.invalidate_filter())
        self.search.connect("activate", lambda *_: self._open_first_match())
        apps.append(self.search)
        self.apps_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.app_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"],
                                    margin_top=6, margin_bottom=18, valign=Gtk.Align.START)
        self.app_list.set_filter_func(self._app_filter)
        self.apps_scroll.set_child(Adw.Clamp(maximum_size=640, child=self.app_list, margin_start=12, margin_end=12))
        apps.append(self.apps_scroll)
        self.stack.add_named(apps, "liste")
        self.mode = "kur"  # ana düğme: "kur" ya da "kaldir"
        self.target = None  # kaldırılacak uygulama (apt.Uygulama)
        self.output: list[str] = []  # son işin apt çıktısı (Ayrıntılar ve açıklama için)

        loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER)
        loading.append(Gtk.Spinner(spinning=True, width_request=32, height_request=32))
        loading.append(Gtk.Label(label=_t("Paket okunuyor, imza denetleniyor…"), css_classes=["dim-label"]))
        self.stack.add_named(loading, "okunuyor")

        # Özet: içerik kayar, tek ana düğme altta hep görünür.
        detail = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.detail_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        detail.append(self.detail_scroll)
        detail.append(Gtk.Separator())
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=12, margin_bottom=12,
                      margin_start=18, margin_end=18)
        self.primary = Gtk.Button(halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
        self.primary.connect("clicked", lambda *_: {"kur": self.install, "kaldir": self.remove,
                                                     "veri": self.clean_data}[self.mode]())
        self.blocker = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, css_classes=["caption", "dim-label"])
        bar.append(self.primary)
        bar.append(self.blocker)
        detail.append(bar)
        self.stack.add_named(detail, "ozet")

        self.progress_page = Adw.StatusPage(icon_name="software-update-available-symbolic")
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.progress = Gtk.ProgressBar(show_text=False)
        self.progress_text = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, css_classes=["dim-label"])
        pbox.append(self.progress)
        pbox.append(self.progress_text)
        # Sırada beklerken: kilidi tutan işlemi durmaya zorla (önce ne olacağı söylenir, karar kullanıcıda).
        self.force_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, visible=False, margin_top=6)
        self.force_text = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, css_classes=["caption"],
                                    visible=False)
        self.force_btn = Gtk.Button(label=_t("Durmaya zorla…"), halign=Gtk.Align.CENTER, css_classes=["pill"])
        self.force_btn.connect("clicked", lambda *_a: self._force_ask())
        self.force_confirm = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER, visible=False)
        b = Gtk.Button(label=_t("Vazgeç"), css_classes=["pill"])
        b.connect("clicked", lambda *_a: self._force_cancel())
        self.force_confirm.append(b)
        self.force_go = Gtk.Button(label=_t("Durdur"), css_classes=["pill", "destructive-action"])
        self.force_go.connect("clicked", lambda *_a: self._force_run())
        self.force_confirm.append(self.force_go)
        for w in (self.force_text, self.force_btn, self.force_confirm):
            self.force_box.append(w)
        pbox.append(self.force_box)
        clamp = Adw.Clamp(maximum_size=420, child=pbox)
        self.progress_page.set_child(clamp)
        self.stack.add_named(self.progress_page, "kuruluyor")

        self.result_page = Adw.StatusPage()
        rbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.result_buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        rbox.append(self.result_buttons)
        # Ham apt çıktısı: açıklamanın yerine değil, istenirse diye (yayıncıya iletmek için seçilebilir).
        self.result_detail = Gtk.Expander(label=_t("Ayrıntılar (apt çıktısı)"))
        self.result_detail_text = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=["monospace", "caption"],
                                            margin_top=6)
        self.result_detail.set_child(self.result_detail_text)
        rbox.append(Adw.Clamp(maximum_size=520, child=self.result_detail))
        self.result_page.set_child(rbox)
        self.stack.add_named(self.result_page, "sonuc")

        self.stack.connect("notify::visible-child-name", lambda *_: self._update_back())
        keys = Gtk.ShortcutController()
        keys.add_shortcut(Gtk.Shortcut(trigger=Gtk.ShortcutTrigger.parse_string("<Alt>Left"),
                                       action=Gtk.CallbackAction.new(lambda *_: self.go_back() or True)))
        self.add_controller(keys)

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)
        self.connect("close-request", self._on_close)

    # ---- dosya ----------------------------------------------------------------------

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=4))

    def _on_close(self, *_):
        if self.busy:
            self.toast(_t("Kurulum sürüyor; bitince kapanabilir"))
            return True
        return False

    def choose(self):
        if self.busy:
            return
        dlg = Gtk.FileChooserNative(title=_t("Paket dosyası seç"), transient_for=self,
                                    action=Gtk.FileChooserAction.OPEN, accept_label=_t("Aç"))
        flt = Gtk.FileFilter(name=_t("Debian paketleri (.deb)"))
        flt.add_pattern("*.deb")
        flt.add_mime_type("application/vnd.debian.binary-package")
        dlg.add_filter(flt)

        def done(d, response):
            if response == Gtk.ResponseType.ACCEPT and d.get_file() and d.get_file().get_path():
                self.load(d.get_file().get_path())
            d.destroy()
        dlg.connect("response", done)
        dlg.show()
        self._chooser = dlg  # çöp toplayıcı kapatmasın

    def _on_drop(self, _t, value, _x, _y):
        files = [f.get_path() for f in value.get_files() if f.get_path()]
        if files and not self.busy:
            self.load(files[0])
            return True
        return False

    def load(self, path: str):
        """Okuma ve denetimler ayrı iş parçacığında: büyük pakette pencere donmasın."""
        self.stack.set_visible_child_name("okunuyor")
        self.title.set_subtitle(os.path.basename(path))

        def work():
            try:
                copy = apt.private_copy(path)
                pkg = paket.read(copy)
                pkg.path = copy
                known = imza.anchors(pkg.package, pkg.installed is not None)
                sig = imza.check(copy, pkg.package, pkg.keyring, known)
                card = yayinci.parse(pkg.publisher)
                old_card = yayinci.installed(pkg.package, imza.owned_by) if pkg.installed else None
                sim = (apt.simulate(copy, apt.flags_for(pkg.verdict, True))
                       if pkg.verdict != paket.UYUMSUZ else apt.Deneme())
                if pkg.verdict != paket.UYUMSUZ and apt.dpkg_interrupted():
                    sim.errors.insert(0, apt.INTERRUPTED)
                # Varsayılan öncelik: dönen bekleme göstergesinin çizimleri sonucu geciktirmesin.
                GLib.idle_add(self.show_package, path, copy, pkg, sig, sim, card, old_card,
                              priority=GLib.PRIORITY_DEFAULT)
            except Exception as e:  # noqa: BLE001 — kullanıcıya anlaşılır biçimde gösterilir
                GLib.idle_add(self.show_error, _t("Paket okunamadı"), str(e), priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=work, daemon=True).start()

    # ---- özet -----------------------------------------------------------------------

    def show_package(self, original, copy, pkg, sig, sim, card=None, old_card=None):
        self._pkg_args = (original, copy, pkg, sig, sim, card, old_card)  # listeden geri dönünce yeniden göstermek için
        self.pkg, self.sig, self.sim, self.copy = pkg, sig, sim, copy
        self.card, self.site = card, None
        self._generation += 1
        self.checks = []
        page = Adw.PreferencesPage()

        head = Adw.PreferencesGroup()
        top = Gtk.Box(spacing=16, margin_bottom=6)
        top.append(self._icon(pkg))
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER, hexpand=True)
        texts.append(Gtk.Label(label=pkg.name, xalign=0, wrap=True, css_classes=["title-1"]))
        if pkg.summary:
            texts.append(Gtk.Label(label=pkg.summary, xalign=0, wrap=True, css_classes=["dim-label"]))
        texts.append(Gtk.Label(label=_t("Paket: {name}").format(name=pkg.package), xalign=0,
                               css_classes=["caption", "dim-label"],
                               ellipsize=Pango.EllipsizeMode.END))
        top.append(texts)
        head.add(top)
        page.add(head)

        title, sub = verdict_text(pkg.verdict)
        g = Adw.PreferencesGroup(title=_t("Sürüm"))
        versions = (_t("Kurulu {old}  →  bu dosya {new}").format(old=pkg.installed, new=pkg.version) if pkg.installed
                    else _t("Bu dosya {new}").format(new=pkg.version))
        icon = {paket.GUNCELLE: "software-update-available-symbolic", paket.KUR: "list-add-symbolic",
                paket.AYNI: "view-refresh-symbolic", paket.ESKI: "edit-undo-symbolic",
                paket.UYUMSUZ: "dialog-error-symbolic"}[pkg.verdict]
        r = row(title, f"{versions}\n{sub}", icon,
                ["error"] if pkg.verdict == paket.UYUMSUZ else ["warning"] if pkg.verdict == paket.ESKI else [])
        g.add(r)
        if pkg.verdict == paket.ESKI:
            g.add(self._check(_t("Eski sürüme dönmek istiyorum")))
        page.add(g)

        page.add(self._signature_group(pkg, sig))
        if card:
            page.add(self._publisher_group(sig, card, old_card))
        changes = self._changes_group(pkg, sim)
        if changes:
            page.add(changes)

        g = Adw.PreferencesGroup(title=_t("Ayrıntılar"))
        g.add(row(_t("Dosya"), original, "document-open-symbolic"))
        g.add(row(_t("Boyut"), human_size(pkg.size), "drive-harddisk-symbolic"))
        if pkg.maintainer:
            g.add(row(_t("Paketi hazırlayan"), pkg.maintainer + "  " + _t("(pakette yazan; imza değil)"),
                      "avatar-default-symbolic"))
        if pkg.homepage:
            g.add(row(_t("Ana sayfa"), pkg.homepage, "web-browser-symbolic"))
        if pkg.installed:
            r = row(_t("Kurulu sürümü kaldır"),
                    _t("{name} {version} bu bilgisayardan kaldırılır (önce ne olacağı gösterilir).").format(
                        name=pkg.name, version=pkg.installed), "user-trash-symbolic")
            b = Gtk.Button(label=_t("Kaldır"), valign=Gtk.Align.CENTER, css_classes=["flat"])
            b.connect("clicked", lambda *_: self.prepare_remove(apt.Uygulama(
                pkg.package, pkg.installed, pkg.name, pkg.icon_name, (pkg.desktop_ids or [""])[0], False)))
            r.add_suffix(b)
            g.add(r)
        if pkg.description:
            exp = Adw.ExpanderRow(title=_t("Açıklama"))
            lbl = Gtk.Label(label=pkg.description, wrap=True, xalign=0, selectable=True, margin_top=8,
                            margin_bottom=8, margin_start=12, margin_end=12)
            exp.add_row(lbl)
            g.add(exp)
        page.add(g)

        self.mode = "kur"
        self.primary.set_label(self._primary_label(pkg))
        self.primary.set_css_classes(["pill", "destructive-action" if pkg.verdict == paket.ESKI or sig.needs_confirmation
                                      else "suggested-action"])

        self.detail_scroll.set_child(page)
        self._update_primary()
        self.stack.set_visible_child_name("ozet")
        return False

    def _icon(self, pkg):
        size = 64
        if pkg.icon_name and Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).has_icon(pkg.icon_name):
            return Gtk.Image(icon_name=pkg.icon_name, pixel_size=size)
        if pkg.icon_data:
            try:
                tex = Gdk.Texture.new_from_bytes(GLib.Bytes.new(pkg.icon_data))
                img = Gtk.Image.new_from_paintable(tex)
                img.set_pixel_size(size)
                return img
            except GLib.Error:
                pass
        return Gtk.Image(icon_name="package-x-generic", pixel_size=size)

    def _check(self, label):
        c = Gtk.CheckButton(label=label, margin_top=6, margin_bottom=6, margin_start=12)
        c.connect("toggled", lambda *_: self._update_primary())
        self.checks.append(c)
        return c

    def _signature_group(self, pkg, sig):
        g = Adw.PreferencesGroup(title=_t("Yayıncı"))
        fpr = imza.grouped(sig.fingerprint) if sig.fingerprint else ""
        if sig.state == imza.AYNI:
            text = (_t("İmza kurulu sürümün anahtarıyla tutuyor. Paket, kurulu sürümü yayımlayan kişiden geliyor.")
                    if sig.anchor == "kurulu" else
                    _t("İmza daha önce onayladığın anahtarla tutuyor. Paket, kurulu sürümü yayımlayan kişiden "
                       "geliyor."))
            g.add(row(_t("Aynı yayıncı"), text, "security-high-symbolic", ["success"]))
        elif sig.state == imza.ILK:
            g.add(row(_t("İmzalı, yayıncı ilk kez görülüyor"),
                      _t("Bu yayıncıdan daha önce imzalı paket kurulmamış. Parmak izini yayıncının sitesinde yazanla "
                         "karşılaştır (yayıncı bir doğrulama adresi verdiyse bu aşağıda kendiliğinden yapılır). "
                         "Kurarsan bu anahtar kaydedilir; sonraki sürümler bununla denetlenir."),
                      "security-medium-symbolic", ["warning"]))
        elif sig.state == imza.FARKLI:
            g.add(row(_t("Farklı yayıncı"),
                      _t("İmza geçerli ama kurulu sürümü yayımlayan anahtar değil. Başka biri hazırlamış olabilir: "
                         "yayıncı anahtarını değiştirdiğini duyurmadıysa kurma."), "dialog-warning-symbolic", ["error"]))
            g.add(self._check(_t("Yayıncının değiştiğini biliyorum, yine de kur")))
        elif sig.state == imza.BOZUK:
            g.add(row(_t("İmza tutmuyor"),
                      _t("Paket imzalı ama imza içerikle uyuşmuyor: dosya bozulmuş ya da değiştirilmiş olabilir. "
                         "Paketi yayıncının sitesinden yeniden indir."), "dialog-error-symbolic", ["error"]))
            g.add(self._check(_t("Riskini biliyorum, yine de kur")))
        else:
            if sig.had_anchor:
                g.add(row(_t("İmzasız (önceki sürüm imzalıydı)"),
                          _t("Kurulu sürüm imzalıydı, bu dosya değil. Yayıncı imzalamayı bırakmadıysa bu dosya başka "
                             "birinden gelmiş olabilir."), "dialog-warning-symbolic", ["error"]))
                g.add(self._check(_t("İmzasız olduğunu biliyorum, yine de kur")))
            else:
                g.add(row(_t("İmzasız"),
                          _t("Yayıncı bu paketi imzalamamış; kimden geldiği denetlenemiyor. Güvendiğin bir yerden "
                             "indirdiysen kurabilirsin (çoğu .deb imzasızdır)."), "security-low-symbolic",
                          ["dim-label"]))
        if fpr:
            r = Adw.ActionRow(title=_t("Parmak izi"), subtitle=fpr, css_classes=["property"])
            if hasattr(r, "set_subtitle_selectable"):  # libadwaita 1.3+
                r.set_subtitle_selectable(True)
            g.add(r)
        return g

    def _publisher_group(self, sig, card, old_card):
        """Yayıncının pakette yazan kartı ve (imzalıysa) sitesinin bu anahtarı yayımlayıp yayımlamadığı."""
        g = Adw.PreferencesGroup(title=_t("Yayıncı bilgisi"),
                                 description=_t("Pakette yayıncının kendi yazdığı bilgi. Gerçekten ona ait olduğunu "
                                                "aşağıdaki site doğrulaması gösterir."))
        lines = [_t("Kurum: {value}").format(value=card.kurum) if card.kurum else "",
                 _t("Yetkili: {value}").format(value=card.yetkili) if card.yetkili else "",
                 _t("Web: {value}").format(value=card.web) if card.web else "",
                 _t("İletişim: {value}").format(value=card.iletisim) if card.iletisim else ""]
        r = row(card.yayinci, "\n".join(x for x in lines if x), "avatar-default-symbolic")
        if card.web:
            b = Gtk.Button(icon_name="web-browser-symbolic", tooltip_text=_t("Siteyi aç"), valign=Gtk.Align.CENTER,
                           css_classes=["flat"])
            b.connect("clicked", lambda *_: Gtk.show_uri(self, card.web, Gdk.CURRENT_TIME))
            r.add_suffix(b)
        g.add(r)
        diff = yayinci.changed(old_card, card)
        if diff:
            g.add(row(_t("Yayıncı bilgisi değişmiş"),
                      _t("Kurulu sürümde {fields} farklıydı: önce “{old}”").format(
                          fields=", ".join(diff), old=old_card.yayinci)
                      + (f" ({old_card.web})" if old_card.web else "") + ".", "dialog-warning-symbolic", ["warning"]))
        if sig.state not in (imza.AYNI, imza.ILK, imza.FARKLI):
            g.add(row(_t("Site doğrulaması yapılamaz"),
                      _t("Paketin geçerli bir imzası yok; yukarıdaki bilgi kimin yazdığı bilinmeyen bir beyan."),
                      "security-low-symbolic", ["dim-label"]))
            return g
        # Kurulu sürüm bir doğrulama adresi verdiyse o kullanılır: yeni paket kendi adresini yazarak
        # kendini doğrulatamasın (yayıncı anahtar değiştirdiyse eski sitesinde yeni anahtarı yayımlar).
        anchor = old_card if old_card and old_card.dogrulama else card
        if not anchor.dogrulama:
            g.add(row(_t("Doğrulama adresi yok"),
                      _t("Yayıncı, parmak izini yayımladığı bir adres vermemiş; bilgi doğrulanamıyor."),
                      "security-low-symbolic", ["dim-label"]))
            return g
        self.site_from_installed = anchor is old_card
        self.site_row = row(_t("Site doğrulanıyor…"), yayinci.short_url(anchor.dogrulama), None)
        self.site_spinner = Gtk.Spinner(spinning=True)
        self.site_row.add_prefix(self.site_spinner)
        g.add(self.site_row)
        gen, fpr = self._generation, sig.fingerprint

        def work():
            res = yayinci.verify(anchor.dogrulama, fpr, anchor.web)
            GLib.idle_add(self._show_site, gen, res, priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=work, daemon=True).start()
        return g

    def _show_site(self, gen, res):
        if gen != self._generation:
            return False
        self.site = res
        where = yayinci.short_url(res.url)
        self.site_row.remove(self.site_spinner)
        if res.state == yayinci.DOGRULANDI and res.same_site:
            title, text, icon, css = (_t("Site doğruladı"),
                                      _t("{site} bu imzanın parmak izini yayımlıyor: anahtar, bu sitenin "
                                         "sahibine ait.").format(site=where), "emblem-ok-symbolic", ["success"])
        elif res.state == yayinci.DOGRULANDI:
            title, text, icon, css = (_t("Site doğruladı, ama başka bir adreste"),
                                      _t("{site} bu parmak izini yayımlıyor; ancak bu adres yayıncının web "
                                         "sitesiyle aynı yerde değil. Bu yalnızca o adresi yönetenin anahtarı "
                                         "onayladığını gösterir.").format(site=where), "dialog-warning-symbolic",
                                      ["warning"])
        elif res.state == yayinci.LISTEDE_YOK:
            title, text, icon, css = (_t("Site bu anahtarı listelemiyor"),
                                      _t("{site} açıldı ama bu imzanın parmak izi orada yok. Yayıncı anahtarını "
                                         "değiştirmiş ve siteyi güncellememiş olabilir; ya da paket "
                                         "başkasından.").format(site=where),
                                      "dialog-warning-symbolic", ["error"])
        else:
            title, text, icon, css = (_t("Site doğrulanamadı"),
                                      _t("{site} adresine ulaşılamadı ({reason}). İnternet yoksa normal; "
                                         "yukarıdaki imza denetimi bundan bağımsız.").format(
                                          site=where, reason=res.detail), "network-offline-symbolic", ["dim-label"])
        if self.site_from_installed:
            text += "\n" + _t("(Kurulu sürümün verdiği doğrulama adresi kullanıldı.)")
        self.site_row.set_title(GLib.markup_escape_text(title))
        self.site_row.set_subtitle(GLib.markup_escape_text(text))
        self.site_row.add_prefix(Gtk.Image(icon_name=icon, css_classes=css))
        return False

    def _changes_group(self, pkg, sim):
        if pkg.verdict == paket.UYUMSUZ:
            return None
        g = Adw.PreferencesGroup(title=_t("Kurulunca"), description=_t("apt'nin denemesi; henüz hiçbir şey değişmedi."))
        extra = sim.extra(pkg.package)
        if sim.errors:
            g.add(self._explain_row(hatalar.explain(sim.errors, None, "kurulum")))
            return g
        if extra:
            more = len(extra) - 12
            names = ", ".join(n for n, _o, _v in extra[:12]) + (
                " " + _tn("ve {n} paket daha", more).format(n=more) if more > 0 else "")
            g.add(row(_tn("Ayrıca {n} paket kurulacak ya da güncellenecek", len(extra)).format(n=len(extra)), names,
                      "list-add-symbolic"))
        if sim.remove:
            g.add(row(_tn("{n} paket kaldırılacak", len(sim.remove)).format(n=len(sim.remove)),
                      ", ".join(sim.remove[:20]), "user-trash-symbolic", ["error"]))
            g.add(self._check(_t("Bu paketlerin kaldırılmasını onaylıyorum")))
        if not extra and not sim.remove:
            g.add(row(_t("Yalnızca bu paket"), _t("Başka paket kurulmayacak ya da kaldırılmayacak."),
                      "emblem-ok-symbolic", ["success"]))
        return g

    @staticmethod
    def _primary_label(pkg):
        return {paket.KUR: _t("Kur"), paket.GUNCELLE: _t("{version} sürümüne güncelle").format(version=pkg.version),
                paket.AYNI: _t("Yeniden kur"),
                paket.ESKI: _t("{version} sürümüne geri dön").format(version=pkg.version),
                paket.UYUMSUZ: _t("Kurulamaz")}[pkg.verdict]

    def _update_primary(self):
        pkg, sim = self.pkg, self.sim
        reason = ""
        if self.mode == "veri":
            chosen = [k for c, k in self.data_checks if c.get_active()]
            total = sum(k.size for k in chosen)
            self.primary.set_label(_t("Seçilenleri temizle ({size})").format(size=human_size(total)) if chosen
                                   else _t("Seçilenleri temizle"))
            self.primary.set_sensitive(bool(chosen))
            self.blocker.set_label(_t("Çöp kutusuna taşınır: geri almak için Dosyalar → Çöp → Geri yükle. "
                                      "Şifre gerekmez.") if chosen else _t("Temizlenecek klasörü işaretle."))
            return
        if self.mode == "kaldir":
            if sim.errors:
                reason = _t("apt bu paketi kaldıramayacağını söylüyor (yukarıda).")
            elif not all(c.get_active() for c in self.checks):
                reason = _t("Devam etmek için yukarıdaki kutuyu işaretle.")
            self.primary.set_sensitive(not reason)
            self.blocker.set_label(reason or _t("Kaldırmak için bilgisayarın şifresi sorulur."))
            return
        if pkg.verdict == paket.UYUMSUZ:
            reason = _t("Paket “{arch}” için; bu bilgisayar {mine}.").format(
                arch=pkg.arch, mine=", ".join(sorted(paket.architectures() - {"all"})))
        elif sim.errors:
            reason = _t("apt bu paketi kuramayacağını söylüyor (yukarıda).")
        elif not all(c.get_active() for c in self.checks):
            reason = _t("Devam etmek için yukarıdaki kutuyu işaretle.")
        self.primary.set_sensitive(not reason)
        self.blocker.set_label(reason or _t("Kurulum için bilgisayarın şifresi sorulur."))

    # ---- kurulum --------------------------------------------------------------------

    def install(self):
        pkg = self.pkg
        allow_remove = bool(self.sim.remove)  # kaldırma varsa onay kutusu işaretlenmiş olmalı (_update_primary)
        cmd = apt.install_command(self.copy, apt.flags_for(pkg.verdict, allow_remove))
        # Kurulumdan önce açık olan uygulamanın bağlantısı: sonra değişirse kendini yeniden başlatmış demektir.
        self._owners_before = {d: calisan.owner(calisan.bus_name(d)) for d in pkg.desktop_ids}
        self._run(cmd, _t("{name} kuruluyor").format(name=pkg.name), "kurulum", self._installed)

    def _run(self, cmd, title, op, on_exit):
        """apt/dpkg'yi yönetici olarak çalıştırır; ilerleme, kilit beklemesi; bitince on_exit(çıkış kodu)."""
        self.busy = True
        self.open_btn.set_sensitive(False)
        self.apps_btn.set_sensitive(False)
        self.progress_page.set_title(title)
        self.progress_page.set_description("")
        self.progress.set_fraction(0)
        self.progress_text.set_label(_t("Şifre bekleniyor…"))
        self._force_reset()
        self.stack.set_visible_child_name("kuruluyor")
        self._pulse = GLib.timeout_add(150, self._pulse_tick)
        self._waiting = False
        self._op, self._on_done = op, on_exit
        self.output = []
        try:
            proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        except GLib.Error as e:
            self._failed(hatalar.Aciklama(_t("Başlatılamadı"), e.message))
            return
        self.parser = apt.Ayristirici()
        self.errors = []
        self._read(proc, proc.get_stdout_pipe())
        proc.wait_async(None, self._on_exit)

    def _pulse_tick(self):
        if self._waiting or self.progress.get_fraction() == 0:
            self.progress.pulse()
        return True

    def _read(self, proc, stream):
        def got(s, res):
            try:
                data = s.read_bytes_finish(res)
            except GLib.Error:
                return
            if data.get_size() == 0:
                for o in self.parser.flush():
                    self._event(o)
                return
            for o in self.parser.feed(data.get_data().decode("utf-8", "replace")):
                self._event(o)
            s.read_bytes_async(4096, GLib.PRIORITY_DEFAULT, None, got)
        stream.read_bytes_async(4096, GLib.PRIORITY_DEFAULT, None, got)

    def _event(self, o):
        if o.kind == "kilit":
            self._waiting = True
            if not getattr(self, "_forcing", False):  # durdururken kilidi kısa süre bizim onarımımız tutar
                self._holder = (o.pid, o.holder)
            who = apt.holder_text(o.holder)
            self.progress_text.set_label(
                (_t("Sırada: {who} şu an paket kilidini tutuyor (süreç {pid}).").format(who=who, pid=o.pid)
                 if o.pid else _t("Sırada: {who} şu an paket kilidini tutuyor.").format(who=who)) + " " +
                _t("O bitince kurulum kendiliğinden başlar; bir şey yapmana gerek yok."))
            if o.pid and not getattr(self, "_forcing", False):
                self.force_box.set_visible(True)
        elif o.kind == "ilerleme":
            self._waiting = False
            if self.force_box.get_visible() and not getattr(self, "_forcing", False):
                self._force_reset()
            if o.percent is not None:
                self.progress.set_fraction(max(0.02, min(1.0, o.percent / 100)))
            self.progress_text.set_label(o.text)
        elif o.kind == "hata":
            self.errors.append(o.text)
        # Açıklama ve Ayrıntılar için: hatalar "E: " ile, ilerleme satırları atlanarak (çok uzun olmasın).
        if o.kind != "ilerleme":
            self.output.append(("E: " + o.text) if o.kind == "hata" and not o.text.startswith("E: ") else o.text)
            del self.output[:-300]

    # ---- durmaya zorlama ----------------------------------------------------------------------

    FORCE_STATES = {"istendi": N_("Durması istendi; o anki paketi bitirmesi bekleniyor…"),
                    "zorla": N_("Kendiliğinden durmadı; zorla durduruluyor…"),
                    "dpkg-bekleniyor": N_("Yarıda kalan paketin bitmesi bekleniyor…"),
                    "tamamlaniyor": N_("Yarım kalan iş tamamlanıyor…"),
                    "bitti": N_("Durduruldu. Kurulum başlıyor…")}

    def _force_reset(self):
        self._forcing = False
        self._holder = None
        self.force_box.set_visible(False)
        self.force_text.set_visible(False)
        self.force_btn.set_visible(True)
        self.force_btn.set_sensitive(True)
        self.force_confirm.set_visible(False)

    def _force_ask(self):
        """Durdurmadan önce ne olacağını söyle: hazırlanıyorsa güvenli, paket kuruyorsa yarım kalabilir (sonra
        tamamlanır), çekirdek ya da önyükleyici kuruluyorsa hiç durdurulmaz."""
        pid, holder = getattr(self, "_holder", None) or (None, None)
        if not pid:
            return
        level, pkgs = durdur.risk()
        who = apt.holder_text(holder)
        self.force_go.set_visible(True)
        if level == durdur.CEKIRDEK:
            text = _t("Şu an çekirdek ya da önyükleyici kuruluyor. Bunu yarıda kesmek bilgisayarın açılmamasına yol "
                      "açabilir; durdurulmaz. Bitmesini bekle: kurulum sonra kendiliğinden başlar.")
            self.force_go.set_visible(False)
        elif level == durdur.KURUYOR:
            names = ", ".join(pkgs[:3]) + ("…" if len(pkgs) > 3 else "")
            text = (_t("{who} şu an paket kuruyor ({names}).").format(who=who, names=names) if names else
                    _t("{who} şu an paket kuruyor.").format(who=who))
            text += " " + _t("Durdurursan o paket yarım kalabilir; ardından yarım kalan iş kendiliğinden "
                             "tamamlanır (dpkg --configure -a). Kalan güncellemeler sonra yeniden yapılabilir. "
                             "Beklemek en güvenlisi.")
            self.force_go.set_label(_t("Yine de durdur"))
        else:
            text = _t("{who} henüz paket kurmuyor (indiriyor ya da hazırlanıyor); durdurmak güvenli. Yarım kalan "
                      "güncellemesi sonra yeniden yapılabilir.").format(who=who)
            self.force_go.set_label(_t("Durdur"))
        if self.force_go.get_visible():
            text += " " + _t("Bilgisayarın şifresi sorulur.")
        self.force_text.set_label(text)
        self.force_text.set_visible(True)
        self.force_btn.set_visible(False)
        self.force_confirm.set_visible(True)

    def _force_cancel(self):
        self.force_text.set_visible(False)
        self.force_confirm.set_visible(False)
        self.force_btn.set_visible(True)

    def _force_run(self):
        pid = self._holder[0]
        self._forcing = True
        self.force_confirm.set_visible(False)
        self.force_text.set_label(_t("Şifre bekleniyor…"))
        try:
            proc = Gio.Subprocess.new(apt.force_stop_command(pid),
                                      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        except GLib.Error as e:
            self._force_done(-1, e.message)
            return
        lines = []
        parser = apt.Ayristirici()

        def got(stream, res):
            try:
                data = stream.read_bytes_finish(res)
            except GLib.Error:
                return
            if data.get_size() == 0:
                return
            for o in parser.feed(data.get_data().decode("utf-8", "replace")):
                lines.append(o.text)
                if o.text.startswith("durum: "):
                    state = o.text.split()[1]
                    if state in self.FORCE_STATES:
                        self.force_text.set_label(_t(self.FORCE_STATES[state]))
            stream.read_bytes_async(4096, GLib.PRIORITY_DEFAULT, None, got)
        proc.get_stdout_pipe().read_bytes_async(4096, GLib.PRIORITY_DEFAULT, None, got)

        def finished(p, res):
            try:
                p.wait_finish(res)
            except GLib.Error:
                pass
            self._force_done(p.get_exit_status(), "\n".join(lines[-5:]))
        proc.wait_async(None, finished)

    def _force_done(self, code, detail=""):
        self.output.append(detail)
        if code == 0:
            self._forcing = False  # sıradaki kurulum ilerleyince kutu kalkar
            self.force_text.set_label(_t(self.FORCE_STATES["bitti"]))
            self.force_btn.set_visible(False)
            return
        text = {126: _t("Şifre penceresi kapatıldı; hiçbir şey durdurulmadı."),
                127: _t("Yönetici izni verilmedi; hiçbir şey durdurulmadı."),
                3: _t("Kilidi artık başka bir işlem tutuyor ya da bu bir paket aracı değil; dokunulmadı."),
                4: _t("Şu an çekirdek ya da önyükleyici kuruluyor; durdurulmadı. Bitmesini bekle."),
                5: _t("İşlem durmadı.")}.get(code, _t("Durdurulamadı (çıkış kodu {code}).").format(code=code))
        self._forcing = False
        self.force_text.set_label(text)
        self.force_btn.set_visible(True)

    def _on_exit(self, proc, res):
        try:
            proc.wait_finish(res)
        except GLib.Error:
            pass
        self._on_done(proc.get_exit_status())

    def _installed(self, code):
        if code == 0 and paket.installed_version(self.pkg.package) == self.pkg.version:
            if self.sig.state in (imza.ILK, imza.FARKLI) and self.pkg.keyring:
                try:
                    imza.remember(self.pkg.package, self.pkg.keyring)
                except OSError:
                    pass
            self._finished(True)
        else:
            self._failed(hatalar.explain(self.output, code, "kurulum"))

    def _update_back(self):
        page = self.stack.get_visible_child_name()
        self.back_btn.set_visible(not self.busy and page in ("ozet", "sonuc") or
                                  (page == "liste" and self.pkg is not None and not self.busy))

    def go_back(self):
        """Sayfadan çık: uygulama sayfalarından listeye (yeniden okunur: kaldırılan gitmiş olsun), listeden ya da
        paket sayfasından açık pakete / boş sayfaya."""
        if self.busy:
            return
        page = self.stack.get_visible_child_name()
        if page in ("ozet", "sonuc") and (self.mode in ("veri", "kaldir") or getattr(self, "_op", None) == "temizlik"):
            self.show_apps()
        elif page == "liste" and self.pkg is not None:
            original = self._pkg_args[0]
            self.title.set_subtitle(os.path.basename(original))
            self.show_package(*self._pkg_args)
        elif page in ("ozet", "sonuc", "liste"):
            self.title.set_subtitle("")
            self.stack.set_visible_child_name("bos")

    def _open_first_match(self):
        """Aramada Enter: tek eşleşme varsa onun verilerini aç."""
        rows = []
        child = self.app_list.get_first_child()
        while child:
            if getattr(child, "paket_ara", None) and child.get_child_visible():
                rows.append(child)
            child = child.get_next_sibling()
        if len(rows) == 1:
            a = next((a for a in self.apps if f"{a.name} {a.package}".casefold() == rows[0].paket_ara), None)
            if a:
                self.show_data(a)

    def _end_job(self):
        GLib.source_remove(self._pulse) if getattr(self, "_pulse", None) else None
        self._pulse = None
        self.busy = False
        self.open_btn.set_sensitive(True)
        self.apps_btn.set_sensitive(True)
        child = self.result_buttons.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.result_buttons.remove(child)
            child = nxt
        self.result_detail.set_visible(False)
        self.result_detail.set_expanded(False)

    def _result_button(self, label, cb, suggested=False):
        b = Gtk.Button(label=label, css_classes=["pill", "suggested-action"] if suggested else ["pill"])
        b.connect("clicked", lambda *_: cb())
        self.result_buttons.append(b)
        return b

    def _failed(self, ac: hatalar.Aciklama):
        """Olmadı: anlaşılır açıklama, onarılabiliyorsa onarım düğmesi, tekrar dene, ham çıktı."""
        self._end_job()
        self.last_error = ac
        self.result_page.set_icon_name("dialog-error-symbolic")
        self.result_page.set_title(GLib.markup_escape_text(ac.title))
        self.result_page.set_description(GLib.markup_escape_text(ac.text))
        if ac.fix:
            self._result_button(ac.fix_label, lambda: self.repair(ac.fix), suggested=True)
        self._result_button(_t("Tekrar dene"), self._retry, suggested=not ac.fix)
        self._result_button(_t("Kapat"), self.close)
        if ac.detail:
            self.result_detail_text.set_label(ac.detail)
            self.result_detail.set_visible(True)
        self.stack.set_visible_child_name("sonuc")

    def _retry(self):
        if getattr(self, "_op", None) == "temizlik":
            self.show_apps()
        elif self.mode == "kaldir" and self.target:
            self.prepare_remove(self.target)
        elif self.pkg:
            self.load(self.pkg.path)
        else:
            self.stack.set_visible_child_name("bos")

    def repair(self, kind):
        """Paket sistemini onar: yarım kalan kurulumu tamamla ya da bozuk bağımlılıkları düzelt."""
        def done(code):
            if code != 0:
                self._failed(hatalar.explain(self.output, code, "onarım"))
                return
            self._end_job()
            self.result_page.set_icon_name("emblem-ok-symbolic")
            self.result_page.set_title(_t("Paket sistemi onarıldı"))
            self.result_page.set_description(_t("Şimdi yeniden deneyebilirsin."))
            self._result_button(_t("Tekrar dene"), self._retry, suggested=True)
            self._result_button(_t("Kapat"), self.close)
            self.stack.set_visible_child_name("sonuc")
        self._run(apt.repair_command(kind), _t("Paket sistemi onarılıyor"), "onarım", done)

    def _finished(self, ok):
        self._end_job()
        pkg = self.pkg
        if ok:
            self.result_page.set_icon_name("emblem-ok-symbolic")
            self.result_page.set_title(_t("{name} {version} kuruldu").format(name=pkg.name, version=pkg.version))
            self.result_page.set_description("")
            app_id = next((d for d in pkg.desktop_ids if desktop_app(d)), None)
            if app_id:
                self._result_for_app(app_id)
        b = Gtk.Button(label=_t("Kapat"), css_classes=["pill"])
        b.connect("clicked", lambda *_a: self.close())
        self.result_buttons.append(b)
        self.stack.set_visible_child_name("sonuc")

    def _result_for_app(self, app_id):
        """Uygulama açıksa yeni sürümün devreye girmesi için ne gerektiğini söyle (ve yapabiliyorsak yap)."""
        pkg, name = self.pkg, calisan.bus_name(app_id)
        before = getattr(self, "_owners_before", {}).get(app_id)
        if before and calisan.restarts_itself(desktop_app(app_id)):
            # Yeni sürüm kendini yeniler; bellekteki eski sürüm de yeniliyor mu, bağlantının değişmesinden anla.
            self.result_page.set_description(
                _t("{name} açık; yeni sürümle yeniden başlaması bekleniyor…").format(name=pkg.name))
            deadline = GLib.get_monotonic_time() + self.RESTART_WAIT * 1_000_000

            def wait():
                now = calisan.owner(name)
                if now and now != before:
                    self.result_page.set_description(_t("{name} yeni sürümle yeniden başladı.").format(name=pkg.name))
                    return False
                if GLib.get_monotonic_time() > deadline:
                    self._offer_restart(app_id, waited=True)
                    return False
                return True
            GLib.timeout_add(300, wait)
            return
        self._offer_restart(app_id)

    RESTART_WAIT = 15  # sn: kendini yenileyen uygulama dosya değişiminden birkaç saniye sonra yeniden başlar

    def _offer_restart(self, app_id, waited=False):
        pkg, name = self.pkg, calisan.bus_name(app_id)
        if calisan.running(name):
            if calisan.can_quit(name):
                self.result_page.set_description(
                    (_t("{name} kendiliğinden yeniden başlamadı (açık olan eski sürüm bunu bilmiyor olabilir).")
                     if waited else _t("{name} şu an açık ve hâlâ eski sürüm çalışıyor.")).format(name=pkg.name)
                    + " " + _t("Yeni sürüm için yeniden başlat (kaydedilmemiş işin varsa önce kaydet)."))
                b = Gtk.Button(label=_t("Yeniden başlat"), css_classes=["pill", "suggested-action"])
                b.connect("clicked", lambda btn: self._restart(btn, app_id))
                self.result_buttons.prepend(b)  # "Kapat"tan önce
                return
            self.result_page.set_description(
                _t("{name} şu an açık ve hâlâ eski sürüm çalışıyor.").format(name=pkg.name) + " " +
                _t("Yeni sürüm, uygulamayı kapatıp yeniden açınca devreye girer."))
            return
        b = Gtk.Button(label=_t("Aç"), css_classes=["pill", "suggested-action"])
        b.connect("clicked", lambda *_: self._launch(app_id))
        self.result_buttons.prepend(b)

    def _restart(self, button, app_id):
        name = calisan.bus_name(app_id)
        button.set_sensitive(False)
        button.set_label(_t("Kapatılıyor…"))
        if not calisan.quit_app(name):
            self.toast(_t("Uygulama kapatılamadı; kendin kapatıp yeniden aç"))
            return
        deadline = GLib.get_monotonic_time() + 10 * 1_000_000

        def wait():
            if not calisan.running(name):
                self._launch(app_id)
                return False
            if GLib.get_monotonic_time() > deadline:
                button.set_label(_t("Yeniden başlat"))
                button.set_sensitive(True)
                self.toast(_t("Uygulama kapanmadı (bir şey soruyor olabilir); kapatıp yeniden aç"))
                return False
            return True
        GLib.timeout_add(200, wait)

    def _launch(self, desktop_id):
        info = desktop_app(desktop_id)
        if info:
            info.launch([], None)
        self.close()

    # ---- kurulu uygulamalar ve kaldırma -----------------------------------------------

    def _make_default(self):
        if iliski.make_default():
            self.default_btn.set_visible(False)
            self.toast(_t(".deb dosyaları artık çift tıklayınca Paket Güncelleyici ile açılır"))
        else:
            self.toast(_t("Varsayılan yapılamadı"))

    def show_apps(self):
        if self.busy:
            return
        self.title.set_subtitle(_t("Kurulu uygulamalar"))
        self._clear(self.app_list)
        spin = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER, margin_top=18, margin_bottom=18)
        spin.append(Gtk.Spinner(spinning=True))
        spin.append(Gtk.Label(label=_t("Uygulamalar okunuyor…"), css_classes=["dim-label"]))
        self.app_list.append(spin)
        self.stack.set_visible_child_name("liste")

        def work():
            try:
                apps = apt.installed_apps()
            except Exception as e:  # noqa: BLE001 — kullanıcıya gösterilir
                GLib.idle_add(self.show_error, _t("Uygulamalar okunamadı"), str(e), priority=GLib.PRIORITY_DEFAULT)
                return
            GLib.idle_add(self._fill_apps, apps, priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _clear(box):
        child = box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt

    def _fill_apps(self, apps):
        self._clear(self.app_list)
        self.apps = apps
        for a in apps:
            sub = f"{a.package} · {a.version}" + (" · " + _t("bir .deb dosyasından kuruldu") if a.local else "")
            r = Adw.ActionRow(title=GLib.markup_escape_text(a.name), subtitle=GLib.markup_escape_text(sub))
            r.paket_ara = f"{a.name} {a.package}".casefold()
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            r.add_prefix(Gtk.Image(icon_name=a.icon if a.icon and theme.has_icon(a.icon) else
                                   "application-x-executable-symbolic", pixel_size=32))
            b = Gtk.Button(label=_t("Veriler"), valign=Gtk.Align.CENTER, css_classes=["flat"],
                           tooltip_text=_t("Önbelleğini ya da ayarlarını temizle (uygulama kalır)"))
            b.connect("clicked", lambda _b, a=a: self.show_data(a))
            r.add_suffix(b)
            b = Gtk.Button(label=_t("Kaldır"), valign=Gtk.Align.CENTER, css_classes=["flat"])
            b.connect("clicked", lambda _b, a=a: self.prepare_remove(a))
            r.add_suffix(b)
            self.app_list.append(r)
        cache = veriler.apt_cache_size()
        if cache > 0:  # en üstte: indirilmiş paket dosyaları (apt-get clean)
            r = Adw.ActionRow(title=_t("Paket önbelleği (apt)"),
                              subtitle=_t("İndirilip saklanan paket dosyaları · {size}. Kurulu programlara "
                                          "dokunmaz.").format(size=human_size(cache)))
            r.add_prefix(Gtk.Image(icon_name="drive-harddisk-symbolic", pixel_size=32))
            b = Gtk.Button(label=_t("Temizle"), valign=Gtk.Align.CENTER, css_classes=["flat"])
            b.connect("clicked", lambda *_: self.clean_apt_cache(cache))
            r.add_suffix(b)
            self.app_list.prepend(r)
        if not apps:
            self.app_list.append(Gtk.Label(label=_t("Paketle kurulmuş masaüstü uygulaması bulunamadı."),
                                           css_classes=["dim-label"], margin_top=18, margin_bottom=18))
        return False

    def _app_filter(self, r):
        # Satırın arama metni (ad + paket adı). Eskiden metni olmayan satır "eşleşiyor" sayılıyordu ve her satır
        # görünür kalıyordu: arama hiç süzmüyordu.
        q = self.search.get_text().strip().casefold()
        return not q or q in getattr(r, "paket_ara", "")

    def prepare_remove(self, a):
        """Kaldırmadan önce deneme: başka hangi paketler gidecek (yetki istemez)."""
        if self.busy:
            return
        self.mode, self.target = "kaldir", a
        self.title.set_subtitle(a.name)
        self.stack.set_visible_child_name("okunuyor")

        def work():
            sim = apt.simulate_remove(a.package)
            if apt.dpkg_interrupted():
                sim.errors.insert(0, apt.INTERRUPTED)
            GLib.idle_add(self.show_remove, a, sim, priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=work, daemon=True).start()

    def show_remove(self, a, sim):
        self.mode, self.target, self.sim = "kaldir", a, sim
        self.checks = []
        page = Adw.PreferencesPage()
        head = Adw.PreferencesGroup()
        top = Gtk.Box(spacing=16, margin_bottom=6)
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        top.append(Gtk.Image(icon_name=a.icon if a.icon and theme.has_icon(a.icon) else "package-x-generic",
                             pixel_size=64))
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER, hexpand=True)
        texts.append(Gtk.Label(label=a.name, xalign=0, wrap=True, css_classes=["title-1"]))
        texts.append(Gtk.Label(label=_t("Paket: {name}").format(name=a.package) + f" · {a.version}", xalign=0,
                               css_classes=["caption", "dim-label"],
                               ellipsize=Pango.EllipsizeMode.END))
        top.append(texts)
        head.add(top)
        page.add(head)

        g = Adw.PreferencesGroup(title=_t("Kaldırılınca"),
                                 description=_t("apt'nin denemesi; henüz hiçbir şey değişmedi."))
        if sim.errors:
            g.add(self._explain_row(hatalar.explain(sim.errors, None, "kaldırma")))
        else:
            others = [p for p in sim.remove if p != a.package]
            g.add(row(_t("{name} kaldırılacak").format(name=a.name),
                      _t("Programın dosyaları silinir. Ev klasöründeki kişisel ayarların ve belgelerin silinmez."),
                      "user-trash-symbolic"))
            if others:
                more = len(others) - 20
                g.add(row(_tn("Ayrıca {n} paket kaldırılacak", len(others)).format(n=len(others)),
                          ", ".join(others[:20]) +
                          (" " + _tn("ve {n} paket daha", more).format(n=more) if more > 0 else "") +
                          "\n" + _t("Bunlar bu uygulamaya bağlı olanlar."), "dialog-warning-symbolic", ["warning"]))
                meta = [p for p in others if p.endswith("-desktop") or p.endswith("-desktop-minimal")]
                if meta:
                    g.add(row(_t("Bilgi: {names}").format(names=", ".join(meta)),
                              _t("Bu bir “paket listesi” paketidir; kaldırılması masaüstünü bozmaz, yalnızca ileride "
                                 "sürüm yükseltirken bu uygulamanın yeniden kurulmamasına yol açar."),
                              "dialog-information-symbolic", ["dim-label"]))
                g.add(self._check(_t("Bunların da kaldırılmasını onaylıyorum")))
            self.purge_check = Gtk.CheckButton(label=_t("Sistem genelindeki ayarlarını da sil (/etc altındakiler)"),
                                               margin_top=6, margin_bottom=6, margin_start=12)
            g.add(self.purge_check)
        page.add(g)
        self.primary.set_label(_t("{name} uygulamasını kaldır").format(name=a.name))
        self.primary.set_css_classes(["pill", "destructive-action"])
        self.detail_scroll.set_child(page)
        self._update_primary()
        self.stack.set_visible_child_name("ozet")
        return False

    def _explain_row(self, ac: hatalar.Aciklama):
        r = row(ac.title, ac.text, "dialog-error-symbolic", ["error"])
        if ac.fix:
            b = Gtk.Button(label=ac.fix_label, valign=Gtk.Align.CENTER, css_classes=["suggested-action"])
            b.connect("clicked", lambda *_: self.repair(ac.fix))
            r.add_suffix(b)
        return r

    def remove(self):
        a = self.target
        purge = bool(getattr(self, "purge_check", None) and self.purge_check.get_active())

        def done(code):
            if code == 0 and paket.installed_version(a.package) is None:
                self._end_job()
                self.result_page.set_icon_name("emblem-ok-symbolic")
                self.result_page.set_title(_t("{name} kaldırıldı").format(name=a.name))
                left = veriler.find(a.package, a.desktop_id, a.name)
                if left:
                    self.result_page.set_description(
                        _t("Ev klasöründe verileri kaldı ({size}): ayarlar, önbellek. İstersen onları da "
                           "temizle.").format(size=human_size(sum(k.size for k in left))))
                    self._result_button(_t("Kalan verileri göster"), lambda: self.show_data(a), suggested=True)
                else:
                    self.result_page.set_description("")
                self._result_button(_t("Kurulu uygulamalar"), self.show_apps, suggested=not left)
                self._result_button(_t("Kapat"), self.close)
                self.stack.set_visible_child_name("sonuc")
            else:
                self._failed(hatalar.explain(self.output, code, "kaldırma"))
        self._run(apt.remove_command(a.package, purge), _t("{name} kaldırılıyor").format(name=a.name), "kaldırma",
                  done)

    # ---- veriler ----------------------------------------------------------------------

    def show_data(self, a):
        """Uygulamanın ev klasöründeki verileri: önbellek (işaretli gelir), ayarlar ve kayıtlı veriler."""
        if self.busy:
            return
        self.mode, self.target = "veri", a
        self.title.set_subtitle(a.name)
        self.stack.set_visible_child_name("okunuyor")

        def work():
            found = veriler.find(a.package, a.desktop_id, a.name)
            is_running = veriler.running(a.package, a.desktop_id)
            GLib.idle_add(self._fill_data, a, found, is_running, priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=work, daemon=True).start()

    def _fill_data(self, a, found, is_running):
        self.data_checks = []
        page = Adw.PreferencesPage()
        head = Adw.PreferencesGroup()
        top = Gtk.Box(spacing=16, margin_bottom=6)
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        top.append(Gtk.Image(icon_name=a.icon if a.icon and theme.has_icon(a.icon) else "package-x-generic",
                             pixel_size=64))
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER, hexpand=True)
        texts.append(Gtk.Label(label=a.name, xalign=0, wrap=True, css_classes=["title-1"]))
        texts.append(Gtk.Label(label=_t("Ev klasöründeki verileri · toplam {size}").format(
                                   size=human_size(sum(k.size for k in found))),
                               xalign=0, css_classes=["caption", "dim-label"]))
        top.append(texts)
        head.add(top)
        page.add(head)
        if is_running:
            g = Adw.PreferencesGroup()
            g.add(row(_t("Uygulama şu an açık"),
                      _t("Önce kapat: açıkken temizlenen ayarlar kapanırken yeniden yazılabilir."),
                      "dialog-warning-symbolic", ["warning"]))
            page.add(g)
        g = Adw.PreferencesGroup(
            title=_t("Klasörler"),
            description=_t("Adı bu uygulamayla tam eşleşen klasörler. Önbelleği temizlemek güvenlidir (uygulama "
                           "yeniden oluşturur); ayarları temizlemek uygulamayı ilk kurulduğu hâline döndürür."))
        home = str(Path.home())
        for k in found:
            shown = "~" + str(k.path)[len(home):] if str(k.path).startswith(home) else str(k.path)
            r = row(shown, f"{veriler.kind_name(k.kind)} · {human_size(k.size)}")
            c = Gtk.CheckButton(active=k.kind == "onbellek", valign=Gtk.Align.CENTER)
            c.connect("toggled", lambda *_: self._update_primary())
            r.add_prefix(c)
            r.set_activatable_widget(c)
            self.data_checks.append((c, k))
            g.add(r)
        if not found:
            g.add(row(_t("Bulunamadı"), _t("Ev klasöründe bu uygulamanın adını taşıyan bir veri klasörü yok. Bazı "
                                            "uygulamalar verisini başka adla tutar; bunlar burada görünmez."),
                      "dialog-information-symbolic",
                      ["dim-label"]))
        page.add(g)
        self.primary.set_css_classes(["pill", "destructive-action"])
        self.detail_scroll.set_child(page)
        self._update_primary()
        self.stack.set_visible_child_name("ozet")
        return False

    def clean_data(self):
        a = self.target
        chosen = [k for c, k in self.data_checks if c.get_active()]
        moved, errors = veriler.trash([k.path for k in chosen])
        freed = sum(k.size for k in chosen if k.path in moved)
        if errors:
            self.toast(_tn("{n} klasör taşınamadı (dokunulmadı): {first}", len(errors)).format(
                n=len(errors), first=errors[0]))
        if moved:
            self.toast(_t("{size} çöp kutusuna taşındı").format(size=human_size(freed)))
        self.show_data(a)

    def clean_apt_cache(self, size):
        def done(code):
            if code != 0:
                self._failed(hatalar.explain(self.output, code, "temizlik"))
                return
            self._end_job()
            self.result_page.set_icon_name("emblem-ok-symbolic")
            self.result_page.set_title(_t("Paket önbelleği temizlendi"))
            self.result_page.set_description(_t("{size} boşaldı.").format(size=human_size(size)))
            self._result_button(_t("Kurulu uygulamalar"), self.show_apps, suggested=True)
            self._result_button(_t("Kapat"), self.close)
            self.stack.set_visible_child_name("sonuc")
        self._run(apt.clean_command(), _t("Paket önbelleği temizleniyor"), "temizlik", done)

    def show_error(self, title, text):
        self.result_detail.set_visible(False)
        self.result_page.set_icon_name("dialog-error-symbolic")
        self.result_page.set_title(title)
        self.result_page.set_description(GLib.markup_escape_text(text))
        child = self.result_buttons.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.result_buttons.remove(child)
            child = nxt
        b = Gtk.Button(label=_t("Başka dosya seç"), css_classes=["pill", "suggested-action"])
        b.connect("clicked", lambda *_: self.choose())
        self.result_buttons.append(b)
        self.stack.set_visible_child_name("sonuc")
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN | Gio.ApplicationFlags.NON_UNIQUE)
        a = Gio.SimpleAction.new("about", None)
        a.connect("activate", self._about)
        self.add_action(a)
        a = Gio.SimpleAction.new_stateful("dil", GLib.VariantType.new("s"), GLib.Variant("s", dil.SYSTEM))
        a.connect("change-state", self._language)
        self.add_action(a)
        self._lang_action = a

    def _window(self):
        w = Window(self)
        w.present()
        return w

    def do_startup(self):
        Adw.Application.do_startup(self)
        dil.setup()
        self._lang_action.set_state(GLib.Variant("s", dil.chosen()))
        try:
            iliski.ensure_listed()  # sağ tık → "Başka uygulamayla aç" listesinde görünsün
        except Exception:  # noqa: BLE001 — ilişki eklenemese de uygulama açılsın
            pass

    def do_activate(self):
        self._window()

    def do_open(self, files, _n, _hint):
        for f in files:
            if f.get_path():
                self._window().load(f.get_path())

    def _language(self, action, value):
        """Menü → Dil: seçilir, saklanır ve açık pencereler yeni dille yeniden kurulur (iş sürmüyorsa)."""
        action.set_state(value)
        dil.choose(value.get_string())
        dil.setup(value.get_string())  # menüde seçilen, ortam değişkeninden önce gelir
        for w in list(self.get_windows()):
            if not isinstance(w, Window):
                continue
            if w.busy:
                w.toast(_t("Dil, bu iş bitip pencere yeniden açılınca değişir"))
                continue
            path = w._pkg_args[0] if w.pkg is not None and getattr(w, "_pkg_args", None) else None
            new = self._window()
            if path and os.path.isfile(path):
                new.load(path)
            w.destroy()

    def _about(self, *_a):
        w = self.get_active_window()
        about = Gtk.AboutDialog(transient_for=w, modal=True, program_name=_t("Paket Güncelleyici"),
                                version=__version__, logo_icon_name=APP_ID,
                                comments=_t(".deb dosyasını kurulu sürümle karşılaştırır, yayıncının imzasını "
                                            "denetler ve kurar."),
                                website="https://github.com/cruciblelab/arastirma", authors=[_t("Crucible ekibi")])
        credits = _t("translator-credits")  # çevirmenler kendi .po dosyalarında adlarını yazar
        if credits != "translator-credits":
            about.set_translator_credits(credits)
        about.present()


def run(argv) -> int:
    return App().run(argv)
