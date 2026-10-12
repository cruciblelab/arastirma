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

from . import APP_ID, __version__, apt, calisan, hatalar, iliski, imza, paket, veriler, yayinci  # noqa: E402

VERDICT = {
    paket.KUR: ("Yeni kurulum", "Bu bilgisayarda kurulu değil."),
    paket.GUNCELLE: ("Güncelleme", "Daha yeni bir sürüm."),
    paket.AYNI: ("Aynı sürüm", "Bu sürüm zaten kurulu; yeniden kurulabilir."),
    paket.ESKI: ("Eski sürüm", "Kurulu olandan daha eski. Geri dönmek ayarları bozabilir."),
    paket.UYUMSUZ: ("Bu bilgisayara uygun değil", "Paket başka bir işlemci mimarisi için."),
}


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}".replace(".", ",")
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
        super().__init__(application=app, title="Paket Güncelleyici", default_width=560, default_height=720)
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
        self.title = Adw.WindowTitle(title="Paket Güncelleyici")
        header.set_title_widget(self.title)
        self.open_btn = Gtk.Button(icon_name="document-open-symbolic", tooltip_text="Başka bir paket aç")
        self.open_btn.connect("clicked", lambda *_: self.choose())
        header.pack_start(self.open_btn)
        self.apps_btn = Gtk.Button(icon_name="view-list-symbolic", tooltip_text="Kurulu uygulamalar (kaldırmak ya da verilerini temizlemek için)")
        self.apps_btn.connect("clicked", lambda *_: self.show_apps())
        header.pack_start(self.apps_btn)
        menu = Gio.Menu()
        menu.append("Hakkında", "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Menü"))
        box.append(header)
        self.stack = Gtk.Stack(vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE)
        box.append(self.stack)
        self.toasts.set_child(box)
        self.set_content(self.toasts)

        empty = Adw.StatusPage(icon_name="package-x-generic-symbolic", title="Bir paket dosyası aç",
                               description="Bir .deb dosyasına sağ tıklayıp “Birlikte aç → Paket Güncelleyici”yi "
                                           "seç ya da buradan seç. Kurulu sürümle karşılaştırılır, yayıncının "
                                           "imzası denetlenir; kurmadan önce ne değişeceği gösterilir.")
        eb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER)
        b = Gtk.Button(label="Dosya seç", css_classes=["pill", "suggested-action"])
        b.connect("clicked", lambda *_: self.choose())
        eb.append(b)
        b = Gtk.Button(label="Kurulu uygulamalar", css_classes=["pill"],
                       tooltip_text="Kaldırmak ya da verilerini temizlemek için: paketle kurulmuş uygulamalar, dosyadan kurulanlar üstte")
        b.connect("clicked", lambda *_: self.show_apps())
        eb.append(b)
        # Çift tıklayınca .deb'ler bununla açılsın: yalnızca kullanıcı isterse (varsayılanı değiştirir).
        self.default_btn = Gtk.Button(label="Çift tıklayınca .deb dosyaları bununla açılsın", css_classes=["flat"])
        self.default_btn.connect("clicked", lambda *_: self._make_default())
        self.default_btn.set_visible(iliski.app_info() is not None and not iliski.is_default())
        eb.append(self.default_btn)
        empty.set_child(eb)
        self.stack.add_named(empty, "bos")

        # Kurulu uygulamalar: arama + liste (yüklenirken dönen gösterge).
        apps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search = Gtk.SearchEntry(placeholder_text="Uygulama ara", margin_top=12, margin_start=18,
                                      margin_end=18, margin_bottom=6)
        self.search.connect("search-changed", lambda *_: self.app_list.invalidate_filter())
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
        loading.append(Gtk.Label(label="Paket okunuyor, imza denetleniyor…", css_classes=["dim-label"]))
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
        clamp = Adw.Clamp(maximum_size=420, child=pbox)
        self.progress_page.set_child(clamp)
        self.stack.add_named(self.progress_page, "kuruluyor")

        self.result_page = Adw.StatusPage()
        rbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.result_buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        rbox.append(self.result_buttons)
        # Ham apt çıktısı: açıklamanın yerine değil, istenirse diye (yayıncıya iletmek için seçilebilir).
        self.result_detail = Gtk.Expander(label="Ayrıntılar (apt çıktısı)")
        self.result_detail_text = Gtk.Label(xalign=0, wrap=True, selectable=True, css_classes=["monospace", "caption"],
                                            margin_top=6)
        self.result_detail.set_child(self.result_detail_text)
        rbox.append(Adw.Clamp(maximum_size=520, child=self.result_detail))
        self.result_page.set_child(rbox)
        self.stack.add_named(self.result_page, "sonuc")

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)
        self.connect("close-request", self._on_close)

    # ---- dosya ----------------------------------------------------------------------

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=4))

    def _on_close(self, *_):
        if self.busy:
            self.toast("Kurulum sürüyor; bitince kapanabilir")
            return True
        return False

    def choose(self):
        if self.busy:
            return
        dlg = Gtk.FileChooserNative(title="Paket dosyası seç", transient_for=self,
                                    action=Gtk.FileChooserAction.OPEN, accept_label="Aç")
        flt = Gtk.FileFilter(name="Debian paketleri (.deb)")
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
                GLib.idle_add(self.show_error, "Paket okunamadı", str(e), priority=GLib.PRIORITY_DEFAULT)
        threading.Thread(target=work, daemon=True).start()

    # ---- özet -----------------------------------------------------------------------

    def show_package(self, original, copy, pkg, sig, sim, card=None, old_card=None):
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
        texts.append(Gtk.Label(label=f"Paket: {pkg.package}", xalign=0, css_classes=["caption", "dim-label"],
                               ellipsize=Pango.EllipsizeMode.END))
        top.append(texts)
        head.add(top)
        page.add(head)

        title, sub = VERDICT[pkg.verdict]
        g = Adw.PreferencesGroup(title="Sürüm")
        versions = (f"Kurulu {pkg.installed}  →  bu dosya {pkg.version}" if pkg.installed
                    else f"Bu dosya {pkg.version}")
        icon = {paket.GUNCELLE: "software-update-available-symbolic", paket.KUR: "list-add-symbolic",
                paket.AYNI: "view-refresh-symbolic", paket.ESKI: "edit-undo-symbolic",
                paket.UYUMSUZ: "dialog-error-symbolic"}[pkg.verdict]
        r = row(title, f"{versions}\n{sub}", icon,
                ["error"] if pkg.verdict == paket.UYUMSUZ else ["warning"] if pkg.verdict == paket.ESKI else [])
        g.add(r)
        if pkg.verdict == paket.ESKI:
            g.add(self._check("Eski sürüme dönmek istiyorum"))
        page.add(g)

        page.add(self._signature_group(pkg, sig))
        if card:
            page.add(self._publisher_group(sig, card, old_card))
        changes = self._changes_group(pkg, sim)
        if changes:
            page.add(changes)

        g = Adw.PreferencesGroup(title="Ayrıntılar")
        g.add(row("Dosya", original, "document-open-symbolic"))
        g.add(row("Boyut", human_size(pkg.size), "drive-harddisk-symbolic"))
        if pkg.maintainer:
            g.add(row("Paketi hazırlayan", pkg.maintainer + "  (pakette yazan; imza değil)", "avatar-default-symbolic"))
        if pkg.homepage:
            g.add(row("Ana sayfa", pkg.homepage, "web-browser-symbolic"))
        if pkg.installed:
            r = row("Kurulu sürümü kaldır", f"{pkg.name} {pkg.installed} bu bilgisayardan kaldırılır (önce ne "
                    "olacağı gösterilir).", "user-trash-symbolic")
            b = Gtk.Button(label="Kaldır", valign=Gtk.Align.CENTER, css_classes=["flat"])
            b.connect("clicked", lambda *_: self.prepare_remove(apt.Uygulama(
                pkg.package, pkg.installed, pkg.name, pkg.icon_name, (pkg.desktop_ids or [""])[0], False)))
            r.add_suffix(b)
            g.add(r)
        if pkg.description:
            exp = Adw.ExpanderRow(title="Açıklama")
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
        g = Adw.PreferencesGroup(title="Yayıncı")
        fpr = imza.grouped(sig.fingerprint) if sig.fingerprint else ""
        if sig.state == imza.AYNI:
            src = "kurulu sürümün anahtarıyla" if sig.anchor == "kurulu" else "daha önce onayladığın anahtarla"
            g.add(row("Aynı yayıncı", f"İmza {src} tutuyor. Paket, kurulu sürümü yayımlayan kişiden geliyor.",
                      "security-high-symbolic", ["success"]))
        elif sig.state == imza.ILK:
            g.add(row("İmzalı, yayıncı ilk kez görülüyor",
                      "Bu yayıncıdan daha önce imzalı paket kurulmamış. Parmak izini yayıncının sitesinde yazanla "
                      "karşılaştır (yayıncı bir doğrulama adresi verdiyse bu aşağıda kendiliğinden yapılır). "
                      "Kurarsan bu anahtar kaydedilir; sonraki sürümler bununla denetlenir.",
                      "security-medium-symbolic", ["warning"]))
        elif sig.state == imza.FARKLI:
            g.add(row("Farklı yayıncı",
                      "İmza geçerli ama kurulu sürümü yayımlayan anahtar değil. Başka biri hazırlamış olabilir: "
                      "yayıncı anahtarını değiştirdiğini duyurmadıysa kurma.", "dialog-warning-symbolic", ["error"]))
            g.add(self._check("Yayıncının değiştiğini biliyorum, yine de kur"))
        elif sig.state == imza.BOZUK:
            g.add(row("İmza tutmuyor",
                      "Paket imzalı ama imza içerikle uyuşmuyor: dosya bozulmuş ya da değiştirilmiş olabilir. "
                      "Paketi yayıncının sitesinden yeniden indir.", "dialog-error-symbolic", ["error"]))
            g.add(self._check("Riskini biliyorum, yine de kur"))
        else:
            if sig.had_anchor:
                g.add(row("İmzasız (önceki sürüm imzalıydı)",
                          "Kurulu sürüm imzalıydı, bu dosya değil. Yayıncı imzalamayı bırakmadıysa bu dosya başka "
                          "birinden gelmiş olabilir.", "dialog-warning-symbolic", ["error"]))
                g.add(self._check("İmzasız olduğunu biliyorum, yine de kur"))
            else:
                g.add(row("İmzasız",
                          "Yayıncı bu paketi imzalamamış; kimden geldiği denetlenemiyor. Güvendiğin bir yerden "
                          "indirdiysen kurabilirsin (çoğu .deb imzasızdır).", "security-low-symbolic", ["dim-label"]))
        if fpr:
            r = Adw.ActionRow(title="Parmak izi", subtitle=fpr, css_classes=["property"])
            if hasattr(r, "set_subtitle_selectable"):  # libadwaita 1.3+
                r.set_subtitle_selectable(True)
            g.add(r)
        return g

    def _publisher_group(self, sig, card, old_card):
        """Yayıncının pakette yazan kartı ve (imzalıysa) sitesinin bu anahtarı yayımlayıp yayımlamadığı."""
        g = Adw.PreferencesGroup(title="Yayıncı bilgisi",
                                 description="Pakette yayıncının kendi yazdığı bilgi. Gerçekten ona ait olduğunu "
                                             "aşağıdaki site doğrulaması gösterir.")
        lines = [f"Kurum: {card.kurum}" if card.kurum else "", f"Yetkili: {card.yetkili}" if card.yetkili else "",
                 f"Web: {card.web}" if card.web else "", f"İletişim: {card.iletisim}" if card.iletisim else ""]
        r = row(card.yayinci, "\n".join(x for x in lines if x), "avatar-default-symbolic")
        if card.web:
            b = Gtk.Button(icon_name="web-browser-symbolic", tooltip_text="Siteyi aç", valign=Gtk.Align.CENTER,
                           css_classes=["flat"])
            b.connect("clicked", lambda *_: Gtk.show_uri(self, card.web, Gdk.CURRENT_TIME))
            r.add_suffix(b)
        g.add(r)
        diff = yayinci.changed(old_card, card)
        if diff:
            g.add(row("Yayıncı bilgisi değişmiş",
                      f"Kurulu sürümde {', '.join(diff)} farklıydı: önce “{old_card.yayinci}”"
                      + (f" ({old_card.web})" if old_card.web else "") + ".", "dialog-warning-symbolic", ["warning"]))
        if sig.state not in (imza.AYNI, imza.ILK, imza.FARKLI):
            g.add(row("Site doğrulaması yapılamaz",
                      "Paketin geçerli bir imzası yok; yukarıdaki bilgi kimin yazdığı bilinmeyen bir beyan.",
                      "security-low-symbolic", ["dim-label"]))
            return g
        # Kurulu sürüm bir doğrulama adresi verdiyse o kullanılır: yeni paket kendi adresini yazarak
        # kendini doğrulatamasın (yayıncı anahtar değiştirdiyse eski sitesinde yeni anahtarı yayımlar).
        anchor = old_card if old_card and old_card.dogrulama else card
        if not anchor.dogrulama:
            g.add(row("Doğrulama adresi yok",
                      "Yayıncı, parmak izini yayımladığı bir adres vermemiş; bilgi doğrulanamıyor.",
                      "security-low-symbolic", ["dim-label"]))
            return g
        self.site_from_installed = anchor is old_card
        self.site_row = row("Site doğrulanıyor…", yayinci.short_url(anchor.dogrulama), None)
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
            title, text, icon, css = ("Site doğruladı",
                                      f"{where} bu imzanın parmak izini yayımlıyor: anahtar, bu sitenin "
                                      "sahibine ait.", "emblem-ok-symbolic", ["success"])
        elif res.state == yayinci.DOGRULANDI:
            title, text, icon, css = ("Site doğruladı, ama başka bir adreste",
                                      f"{where} bu parmak izini yayımlıyor; ancak bu adres yayıncının web "
                                      "sitesiyle aynı yerde değil. Bu yalnızca o adresi yönetenin anahtarı "
                                      "onayladığını gösterir.", "dialog-warning-symbolic", ["warning"])
        elif res.state == yayinci.LISTEDE_YOK:
            title, text, icon, css = ("Site bu anahtarı listelemiyor",
                                      f"{where} açıldı ama bu imzanın parmak izi orada yok. Yayıncı anahtarını "
                                      "değiştirmiş ve siteyi güncellememiş olabilir; ya da paket başkasından.",
                                      "dialog-warning-symbolic", ["error"])
        else:
            title, text, icon, css = ("Site doğrulanamadı",
                                      f"{where} adresine ulaşılamadı ({res.detail}). İnternet yoksa normal; "
                                      "yukarıdaki imza denetimi bundan bağımsız.", "network-offline-symbolic",
                                      ["dim-label"])
        if self.site_from_installed:
            text += "\n(Kurulu sürümün verdiği doğrulama adresi kullanıldı.)"
        self.site_row.set_title(GLib.markup_escape_text(title))
        self.site_row.set_subtitle(GLib.markup_escape_text(text))
        self.site_row.add_prefix(Gtk.Image(icon_name=icon, css_classes=css))
        return False

    def _changes_group(self, pkg, sim):
        if pkg.verdict == paket.UYUMSUZ:
            return None
        g = Adw.PreferencesGroup(title="Kurulunca", description="apt'nin denemesi; henüz hiçbir şey değişmedi.")
        extra = sim.extra(pkg.package)
        if sim.errors:
            g.add(self._explain_row(hatalar.explain(sim.errors, None, "kurulum")))
            return g
        if extra:
            names = ", ".join(n for n, _, _ in extra[:12]) + (f" ve {len(extra) - 12} paket daha"
                                                              if len(extra) > 12 else "")
            g.add(row(f"Ayrıca {len(extra)} paket kurulacak ya da güncellenecek", names, "list-add-symbolic"))
        if sim.remove:
            g.add(row(f"{len(sim.remove)} paket kaldırılacak", ", ".join(sim.remove[:20]), "user-trash-symbolic",
                      ["error"]))
            g.add(self._check("Bu paketlerin kaldırılmasını onaylıyorum"))
        if not extra and not sim.remove:
            g.add(row("Yalnızca bu paket", "Başka paket kurulmayacak ya da kaldırılmayacak.", "emblem-ok-symbolic",
                      ["success"]))
        return g

    @staticmethod
    def _primary_label(pkg):
        return {paket.KUR: "Kur", paket.GUNCELLE: f"{pkg.version} sürümüne güncelle", paket.AYNI: "Yeniden kur",
                paket.ESKI: f"{pkg.version} sürümüne geri dön", paket.UYUMSUZ: "Kurulamaz"}[pkg.verdict]

    def _update_primary(self):
        pkg, sim = self.pkg, self.sim
        reason = ""
        if self.mode == "veri":
            chosen = [k for c, k in self.data_checks if c.get_active()]
            total = sum(k.size for k in chosen)
            self.primary.set_label(f"Seçilenleri temizle ({human_size(total)})" if chosen else "Seçilenleri temizle")
            self.primary.set_sensitive(bool(chosen))
            self.blocker.set_label("Çöp kutusuna taşınır: geri almak için Dosyalar → Çöp → Geri yükle. "
                                   "Şifre gerekmez." if chosen else "Temizlenecek klasörü işaretle.")
            return
        if self.mode == "kaldir":
            if sim.errors:
                reason = "apt bu paketi kaldıramayacağını söylüyor (yukarıda)."
            elif not all(c.get_active() for c in self.checks):
                reason = "Devam etmek için yukarıdaki kutuyu işaretle."
            self.primary.set_sensitive(not reason)
            self.blocker.set_label(reason or "Kaldırmak için bilgisayarın şifresi sorulur.")
            return
        if pkg.verdict == paket.UYUMSUZ:
            reason = f"Paket “{pkg.arch}” için; bu bilgisayar {', '.join(sorted(paket.architectures() - {'all'}))}."
        elif sim.errors:
            reason = "apt bu paketi kuramayacağını söylüyor (yukarıda)."
        elif not all(c.get_active() for c in self.checks):
            reason = "Devam etmek için yukarıdaki kutuyu işaretle."
        self.primary.set_sensitive(not reason)
        self.blocker.set_label(reason or "Kurulum için bilgisayarın şifresi sorulur.")

    # ---- kurulum --------------------------------------------------------------------

    def install(self):
        pkg = self.pkg
        allow_remove = bool(self.sim.remove)  # kaldırma varsa onay kutusu işaretlenmiş olmalı (_update_primary)
        cmd = apt.install_command(self.copy, apt.flags_for(pkg.verdict, allow_remove))
        # Kurulumdan önce açık olan uygulamanın bağlantısı: sonra değişirse kendini yeniden başlatmış demektir.
        self._owners_before = {d: calisan.owner(calisan.bus_name(d)) for d in pkg.desktop_ids}
        self._run(cmd, f"{pkg.name} kuruluyor", "kurulum", self._installed)

    def _run(self, cmd, title, op, on_exit):
        """apt/dpkg'yi yönetici olarak çalıştırır; ilerleme, kilit beklemesi; bitince on_exit(çıkış kodu)."""
        self.busy = True
        self.open_btn.set_sensitive(False)
        self.apps_btn.set_sensitive(False)
        self.progress_page.set_title(title)
        self.progress_page.set_description("")
        self.progress.set_fraction(0)
        self.progress_text.set_label("Şifre bekleniyor…")
        self.stack.set_visible_child_name("kuruluyor")
        self._pulse = GLib.timeout_add(150, self._pulse_tick)
        self._waiting = False
        self._op, self._on_done = op, on_exit
        self.output = []
        try:
            proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        except GLib.Error as e:
            self._failed(hatalar.Aciklama("Başlatılamadı", e.message))
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
            who = apt.holder_text(o.holder)
            self.progress_text.set_label(
                f"Sırada: {who} şu an paket kilidini tutuyor" + (f" (süreç {o.pid})" if o.pid else "") +
                ". O bitince kurulum kendiliğinden başlar; bir şey yapmana gerek yok.")
        elif o.kind == "ilerleme":
            self._waiting = False
            if o.percent is not None:
                self.progress.set_fraction(max(0.02, min(1.0, o.percent / 100)))
            self.progress_text.set_label(o.text)
        elif o.kind == "hata":
            self.errors.append(o.text)
        # Açıklama ve Ayrıntılar için: hatalar "E: " ile, ilerleme satırları atlanarak (çok uzun olmasın).
        if o.kind != "ilerleme":
            self.output.append(("E: " + o.text) if o.kind == "hata" and not o.text.startswith("E: ") else o.text)
            del self.output[:-300]

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
        self._result_button("Tekrar dene", self._retry, suggested=not ac.fix)
        self._result_button("Kapat", self.close)
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
            self.result_page.set_title("Paket sistemi onarıldı")
            self.result_page.set_description("Şimdi yeniden deneyebilirsin.")
            self._result_button("Tekrar dene", self._retry, suggested=True)
            self._result_button("Kapat", self.close)
            self.stack.set_visible_child_name("sonuc")
        self._run(apt.repair_command(kind), "Paket sistemi onarılıyor", "onarım", done)

    def _finished(self, ok):
        self._end_job()
        pkg = self.pkg
        if ok:
            self.result_page.set_icon_name("emblem-ok-symbolic")
            self.result_page.set_title(f"{pkg.name} {pkg.version} kuruldu")
            self.result_page.set_description("")
            app_id = next((d for d in pkg.desktop_ids if desktop_app(d)), None)
            if app_id:
                self._result_for_app(app_id)
        b = Gtk.Button(label="Kapat", css_classes=["pill"])
        b.connect("clicked", lambda *_: self.close())
        self.result_buttons.append(b)
        self.stack.set_visible_child_name("sonuc")

    def _result_for_app(self, app_id):
        """Uygulama açıksa yeni sürümün devreye girmesi için ne gerektiğini söyle (ve yapabiliyorsak yap)."""
        pkg, name = self.pkg, calisan.bus_name(app_id)
        before = getattr(self, "_owners_before", {}).get(app_id)
        if before and calisan.restarts_itself(desktop_app(app_id)):
            # Yeni sürüm kendini yeniler; bellekteki eski sürüm de yeniliyor mu, bağlantının değişmesinden anla.
            self.result_page.set_description(f"{pkg.name} açık; yeni sürümle yeniden başlaması bekleniyor…")
            deadline = GLib.get_monotonic_time() + self.RESTART_WAIT * 1_000_000

            def wait():
                now = calisan.owner(name)
                if now and now != before:
                    self.result_page.set_description(f"{pkg.name} yeni sürümle yeniden başladı.")
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
                    (f"{pkg.name} kendiliğinden yeniden başlamadı (açık olan eski sürüm bunu bilmiyor olabilir). "
                     if waited else f"{pkg.name} şu an açık ve hâlâ eski sürüm çalışıyor. ")
                    + "Yeni sürüm için yeniden başlat (kaydedilmemiş işin varsa önce kaydet).")
                b = Gtk.Button(label="Yeniden başlat", css_classes=["pill", "suggested-action"])
                b.connect("clicked", lambda btn: self._restart(btn, app_id))
                self.result_buttons.prepend(b)  # "Kapat"tan önce
                return
            self.result_page.set_description(f"{pkg.name} şu an açık ve hâlâ eski sürüm çalışıyor. Yeni sürüm, "
                                             "uygulamayı kapatıp yeniden açınca devreye girer.")
            return
        b = Gtk.Button(label="Aç", css_classes=["pill", "suggested-action"])
        b.connect("clicked", lambda *_: self._launch(app_id))
        self.result_buttons.prepend(b)

    def _restart(self, button, app_id):
        name = calisan.bus_name(app_id)
        button.set_sensitive(False)
        button.set_label("Kapatılıyor…")
        if not calisan.quit_app(name):
            self.toast("Uygulama kapatılamadı; kendin kapatıp yeniden aç")
            return
        deadline = GLib.get_monotonic_time() + 10 * 1_000_000

        def wait():
            if not calisan.running(name):
                self._launch(app_id)
                return False
            if GLib.get_monotonic_time() > deadline:
                button.set_label("Yeniden başlat")
                button.set_sensitive(True)
                self.toast("Uygulama kapanmadı (bir şey soruyor olabilir); kapatıp yeniden aç")
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
            self.toast(".deb dosyaları artık çift tıklayınca Paket Güncelleyici ile açılır")
        else:
            self.toast("Varsayılan yapılamadı")

    def show_apps(self):
        if self.busy:
            return
        self.title.set_subtitle("Kurulu uygulamalar")
        self._clear(self.app_list)
        spin = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER, margin_top=18, margin_bottom=18)
        spin.append(Gtk.Spinner(spinning=True))
        spin.append(Gtk.Label(label="Uygulamalar okunuyor…", css_classes=["dim-label"]))
        self.app_list.append(spin)
        self.stack.set_visible_child_name("liste")

        def work():
            try:
                apps = apt.installed_apps()
            except Exception as e:  # noqa: BLE001 — kullanıcıya gösterilir
                GLib.idle_add(self.show_error, "Uygulamalar okunamadı", str(e), priority=GLib.PRIORITY_DEFAULT)
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
            sub = f"{a.package} · {a.version}" + (" · bir .deb dosyasından kuruldu" if a.local else "")
            r = Adw.ActionRow(title=GLib.markup_escape_text(a.name), subtitle=GLib.markup_escape_text(sub))
            r.paket_ara = f"{a.name} {a.package}".casefold()
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            r.add_prefix(Gtk.Image(icon_name=a.icon if a.icon and theme.has_icon(a.icon) else
                                   "application-x-executable-symbolic", pixel_size=32))
            b = Gtk.Button(label="Veriler", valign=Gtk.Align.CENTER, css_classes=["flat"],
                           tooltip_text="Önbelleğini ya da ayarlarını temizle (uygulama kalır)")
            b.connect("clicked", lambda _b, a=a: self.show_data(a))
            r.add_suffix(b)
            b = Gtk.Button(label="Kaldır", valign=Gtk.Align.CENTER, css_classes=["flat"])
            b.connect("clicked", lambda _b, a=a: self.prepare_remove(a))
            r.add_suffix(b)
            self.app_list.append(r)
        cache = veriler.apt_cache_size()
        if cache > 0:  # en üstte: indirilmiş paket dosyaları (apt-get clean)
            r = Adw.ActionRow(title="Paket önbelleği (apt)",
                              subtitle=f"İndirilip saklanan paket dosyaları · {human_size(cache)}. Kurulu "
                                       f"programlara dokunmaz.")
            r.add_prefix(Gtk.Image(icon_name="drive-harddisk-symbolic", pixel_size=32))
            b = Gtk.Button(label="Temizle", valign=Gtk.Align.CENTER, css_classes=["flat"])
            b.connect("clicked", lambda *_: self.clean_apt_cache(cache))
            r.add_suffix(b)
            self.app_list.prepend(r)
        if not apps:
            self.app_list.append(Gtk.Label(label="Paketle kurulmuş masaüstü uygulaması bulunamadı.",
                                           css_classes=["dim-label"], margin_top=18, margin_bottom=18))
        return False

    def _app_filter(self, r):
        q = self.search.get_text().strip().casefold()
        return not q or q in getattr(r.get_child(), "paket_ara", q) or q in getattr(r, "paket_ara", "")

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
        texts.append(Gtk.Label(label=f"Paket: {a.package} · {a.version}", xalign=0, css_classes=["caption", "dim-label"],
                               ellipsize=Pango.EllipsizeMode.END))
        top.append(texts)
        head.add(top)
        page.add(head)

        g = Adw.PreferencesGroup(title="Kaldırılınca", description="apt'nin denemesi; henüz hiçbir şey değişmedi.")
        if sim.errors:
            g.add(self._explain_row(hatalar.explain(sim.errors, None, "kaldırma")))
        else:
            others = [p for p in sim.remove if p != a.package]
            g.add(row(f"{a.name} kaldırılacak", "Programın dosyaları silinir. Ev klasöründeki kişisel ayarların ve "
                      "belgelerin silinmez.", "user-trash-symbolic"))
            if others:
                g.add(row(f"Ayrıca {len(others)} paket kaldırılacak", ", ".join(others[:20]) +
                          (f" ve {len(others) - 20} paket daha" if len(others) > 20 else "") +
                          "\nBunlar bu uygulamaya bağlı olanlar.", "dialog-warning-symbolic", ["warning"]))
                meta = [p for p in others if p.endswith("-desktop") or p.endswith("-desktop-minimal")]
                if meta:
                    g.add(row("Bilgi: " + ", ".join(meta), "Bu bir “paket listesi” paketidir; kaldırılması "
                              "masaüstünü bozmaz, yalnızca ileride sürüm yükseltirken bu uygulamanın yeniden "
                              "kurulmamasına yol açar.", "dialog-information-symbolic", ["dim-label"]))
                g.add(self._check("Bunların da kaldırılmasını onaylıyorum"))
            self.purge_check = Gtk.CheckButton(label="Sistem genelindeki ayarlarını da sil (/etc altındakiler)",
                                               margin_top=6, margin_bottom=6, margin_start=12)
            g.add(self.purge_check)
        page.add(g)
        self.primary.set_label(f"{a.name} uygulamasını kaldır")
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
                self.result_page.set_title(f"{a.name} kaldırıldı")
                left = veriler.find(a.package, a.desktop_id, a.name)
                if left:
                    self.result_page.set_description(
                        f"Ev klasöründe verileri kaldı ({human_size(sum(k.size for k in left))}): ayarlar, önbellek. "
                        f"İstersen onları da temizle.")
                    self._result_button("Kalan verileri göster", lambda: self.show_data(a), suggested=True)
                else:
                    self.result_page.set_description("")
                self._result_button("Kurulu uygulamalar", self.show_apps, suggested=not left)
                self._result_button("Kapat", self.close)
                self.stack.set_visible_child_name("sonuc")
            else:
                self._failed(hatalar.explain(self.output, code, "kaldırma"))
        self._run(apt.remove_command(a.package, purge), f"{a.name} kaldırılıyor", "kaldırma", done)

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
        texts.append(Gtk.Label(label=f"Ev klasöründeki verileri · toplam {human_size(sum(k.size for k in found))}",
                               xalign=0, css_classes=["caption", "dim-label"]))
        top.append(texts)
        head.add(top)
        page.add(head)
        if is_running:
            g = Adw.PreferencesGroup()
            g.add(row("Uygulama şu an açık", "Önce kapat: açıkken temizlenen ayarlar kapanırken yeniden yazılabilir.",
                      "dialog-warning-symbolic", ["warning"]))
            page.add(g)
        g = Adw.PreferencesGroup(
            title="Klasörler",
            description="Adı bu uygulamayla tam eşleşen klasörler. Önbelleği temizlemek güvenlidir (uygulama yeniden "
                        "oluşturur); ayarları temizlemek uygulamayı ilk kurulduğu hâline döndürür.")
        home = str(Path.home())
        for k in found:
            shown = "~" + str(k.path)[len(home):] if str(k.path).startswith(home) else str(k.path)
            r = row(shown, f"{k.label} · {human_size(k.size)}")
            c = Gtk.CheckButton(active=k.kind == "onbellek", valign=Gtk.Align.CENTER)
            c.connect("toggled", lambda *_: self._update_primary())
            r.add_prefix(c)
            r.set_activatable_widget(c)
            self.data_checks.append((c, k))
            g.add(r)
        if not found:
            g.add(row("Bulunamadı", "Ev klasöründe bu uygulamanın adını taşıyan bir veri klasörü yok. Bazı uygulamalar "
                      "verisini başka adla tutar; bunlar burada görünmez.", "dialog-information-symbolic",
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
            self.toast(f"{len(errors)} klasör taşınamadı (dokunulmadı): {errors[0]}")
        if moved:
            self.toast(f"{human_size(freed)} çöp kutusuna taşındı")
        self.show_data(a)

    def clean_apt_cache(self, size):
        def done(code):
            if code != 0:
                self._failed(hatalar.explain(self.output, code, "temizlik"))
                return
            self._end_job()
            self.result_page.set_icon_name("emblem-ok-symbolic")
            self.result_page.set_title("Paket önbelleği temizlendi")
            self.result_page.set_description(f"{human_size(size)} boşaldı.")
            self._result_button("Kurulu uygulamalar", self.show_apps, suggested=True)
            self._result_button("Kapat", self.close)
            self.stack.set_visible_child_name("sonuc")
        self._run(apt.clean_command(), "Paket önbelleği temizleniyor", "temizlik", done)

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
        b = Gtk.Button(label="Başka dosya seç", css_classes=["pill", "suggested-action"])
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

    def _window(self):
        w = Window(self)
        w.present()
        return w

    def do_startup(self):
        Adw.Application.do_startup(self)
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

    def _about(self, *_):
        w = self.get_active_window()
        about = Gtk.AboutDialog(transient_for=w, modal=True, program_name="Paket Güncelleyici", version=__version__,
                                logo_icon_name=APP_ID, comments=".deb dosyasını kurulu sürümle karşılaştırır, "
                                "yayıncının imzasını denetler ve kurar.",
                                website="https://github.com/cruciblelab/arastirma", authors=["Crucible ekibi"])
        about.present()


def run(argv) -> int:
    return App().run(argv)
