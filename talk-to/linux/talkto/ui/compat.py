"""Eski GTK/libadwaita sürümleriyle uyumluluk (Ubuntu 22.04: GTK 4.6, libadwaita 1.1).

Yeni sürümlerde libadwaita'nın kendi parçaları kullanılır; yoksa aynı arayüzü
sunan küçük yedekler devreye girer. Pencere kodu yalnızca bu modülü kullanır.
"""

from gi.repository import Adw, Gio, GLib, GObject, Gtk

ADW = (Adw.get_major_version(), Adw.get_minor_version())
HAS_USE_MARKUP = Adw.PreferencesRow.find_property("use-markup") is not None  # 1.2+

SUGGESTED, DESTRUCTIVE = "suggested", "destructive"


# ---- satırlar -------------------------------------------------------------------

def row(title="", subtitle="", cls=Adw.ActionRow, **kw):
    """Dışarıdan gelen metin (bildirim, cihaz adı) işaretleme (markup) sayılmasın."""
    if HAS_USE_MARKUP:
        r = cls(title=title, use_markup=False, **kw)
        if subtitle:
            r.set_subtitle(subtitle)
    else:  # 1.1: başlıklar her zaman işaretleme; kaçışla
        r = cls(title=GLib.markup_escape_text(title or ""), **kw)
        if subtitle:
            r.set_subtitle(GLib.markup_escape_text(subtitle))
    return r


def esc(text) -> str:
    """İşaretleme (markup) kullanan satırlara dışarıdan metin (dosya yolu vb.) koymadan önce."""
    return GLib.markup_escape_text(text or "")


class _SwitchRow(Adw.ActionRow):
    __gtype_name__ = "TalkToSwitchRow"
    active = GObject.Property(type=bool, default=False)

    def __init__(self, title="", subtitle="", active=False, **kw):
        super().__init__(title=title, **kw)
        if subtitle:
            self.set_subtitle(subtitle)
        sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.add_suffix(sw)
        self.set_activatable_widget(sw)
        self.bind_property("active", sw, "active",
                           GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        self.set_property("active", active)

    def get_active(self):
        return self.get_property("active")

    def set_active(self, value):
        self.set_property("active", bool(value))


def SwitchRow(title="", subtitle="", active=False, **kw):
    if hasattr(Adw, "SwitchRow"):
        r = Adw.SwitchRow(title=title, active=active, **kw)
        if subtitle:
            r.set_subtitle(subtitle)
        return r
    return _SwitchRow(title, subtitle, active, **kw)


class _EntryRow(Adw.ActionRow):
    __gtype_name__ = "TalkToEntryRow"
    __gsignals__ = {"apply": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, title="", text="", show_apply_button=True, password=False, **kw):
        super().__init__(title=title, **kw)
        self.entry = Gtk.PasswordEntry(show_peek_icon=True) if password else Gtk.Entry()
        self.entry.set_valign(Gtk.Align.CENTER)
        self.entry.set_hexpand(True)
        self.entry.set_size_request(180, -1)
        self.entry.set_text(text or "")
        self.entry.connect("activate", lambda *_: self.emit("apply"))
        self.add_suffix(self.entry)
        if show_apply_button:
            b = Gtk.Button(icon_name="object-select-symbolic", tooltip_text="Uygula", valign=Gtk.Align.CENTER,
                           css_classes=["flat"])
            b.connect("clicked", lambda *_: self.emit("apply"))
            self.add_suffix(b)

    def get_text(self):
        return self.entry.get_text()

    def set_text(self, text):
        self.entry.set_text(text or "")


def EntryRow(title="", text="", show_apply_button=False):
    if hasattr(Adw, "EntryRow"):
        return Adw.EntryRow(title=title, text=text or "", show_apply_button=show_apply_button)
    return _EntryRow(title, text, show_apply_button)


def PasswordEntryRow(title="", text="", show_apply_button=False):
    if hasattr(Adw, "PasswordEntryRow"):
        return Adw.PasswordEntryRow(title=title, text=text or "", show_apply_button=show_apply_button)
    return _EntryRow(title, text, show_apply_button, password=True)


# ---- uyarı şeridi -------------------------------------------------------------------

class _Banner(Gtk.Revealer):
    def __init__(self):
        super().__init__()
        self.label = Gtk.Label(wrap=True, margin_top=8, margin_bottom=8, margin_start=12, margin_end=12)
        box = Gtk.Box(css_classes=["compat-banner"])
        box.append(self.label)
        self.label.set_hexpand(True)
        self.set_child(box)

    def set_title(self, markup):
        self.label.set_markup(markup)

    def set_revealed(self, on):
        self.set_reveal_child(on)


def Banner():
    return Adw.Banner() if hasattr(Adw, "Banner") else _Banner()


# ---- sayfa ekleme ---------------------------------------------------------------------

def add_page(stack, child, name, title, icon):
    if hasattr(stack, "add_titled_with_icon"):
        return stack.add_titled_with_icon(child, name, title, icon)
    page = stack.add_titled(child, name, title)
    page.set_icon_name(icon)
    return page


# ---- diyaloglar -----------------------------------------------------------------------

class _FallbackDialog(Adw.Window):
    __gtype_name__ = "TalkToDialog"
    __gsignals__ = {"response": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self, parent, heading, body):
        super().__init__(modal=True, transient_for=parent, resizable=False, default_width=440)
        self._done = False
        self._close = None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24, margin_bottom=20,
                      margin_start=24, margin_end=24)
        box.append(Gtk.Label(label=heading, wrap=True, justify=Gtk.Justification.CENTER, css_classes=["title-2"]))
        if body:
            box.append(Gtk.Label(label=body, wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=50))
        self._extra = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self._extra)
        self._buttons = Gtk.Box(spacing=12, homogeneous=True, margin_top=12)
        box.append(self._buttons)
        self.set_content(box)
        self.connect("close-request", self._on_close_request)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, key, *_: key == 0xff1b and (self.close() or True))  # Esc
        self.add_controller(keys)
        self._by_id = {}

    def add_response(self, rid, label):
        b = Gtk.Button(label=label, hexpand=True)
        b.connect("clicked", lambda *_: self._respond(rid))
        self._by_id[rid] = b
        self._buttons.append(b)

    def set_appearance(self, rid, kind):
        self._by_id[rid].add_css_class("suggested-action" if kind == SUGGESTED else "destructive-action")

    def set_close_response(self, rid):
        self._close = rid

    def set_extra_child(self, w):
        self._extra.append(w)

    def _respond(self, rid):
        if self._done:
            return
        self._done = True
        self.emit("response", rid)
        self.destroy()

    def _on_close_request(self, *_):
        if not self._done:
            self._done = True
            self.emit("response", self._close or "close")
        return False

    def force_close(self):
        self._done = True
        self.destroy()


class Dialog:
    """AlertDialog (1.5+), MessageDialog (1.2+) ya da kendi yedeğimiz; aynı kullanım."""

    def __init__(self, parent, heading, body, extra=None):
        self.parent = parent
        if hasattr(Adw, "AlertDialog"):
            self.kind, self.d = "alert", Adw.AlertDialog(heading=heading, body=body)
        elif hasattr(Adw, "MessageDialog"):
            self.kind, self.d = "message", Adw.MessageDialog(transient_for=parent, heading=heading, body=body)
        else:
            self.kind, self.d = "own", _FallbackDialog(parent, heading, body)
        if extra:
            self.d.set_extra_child(extra)

    def add_response(self, rid, label):
        self.d.add_response(rid, label)

    def set_appearance(self, rid, kind):
        if self.kind == "own":
            self.d.set_appearance(rid, kind)
        else:
            self.d.set_response_appearance(rid, Adw.ResponseAppearance.SUGGESTED if kind == SUGGESTED
                                           else Adw.ResponseAppearance.DESTRUCTIVE)

    def set_close_response(self, rid):
        self.d.set_close_response(rid)

    def on_response(self, cb):
        self.d.connect("response", lambda _d, r: cb(r))

    def present(self):
        self.d.present(self.parent) if self.kind == "alert" else self.d.present()

    def close(self):
        if self.kind == "message":
            self.d.close()
        else:
            self.d.force_close()


def about(parent, **kw):
    if hasattr(Adw, "AboutDialog"):
        Adw.AboutDialog(**kw).present(parent)
    elif hasattr(Adw, "AboutWindow"):
        Adw.AboutWindow(transient_for=parent, **kw).present()
    else:
        Gtk.AboutDialog(transient_for=parent, modal=True, program_name=kw["application_name"],
                        logo_icon_name=kw["application_icon"], version=kw["version"], comments=kw["comments"],
                        website=kw["website"], authors=[kw["developer_name"]]).present()


# ---- dosya seçme ve açma ------------------------------------------------------------------

_keep = []  # FileChooserNative, cevap gelene kadar yaşamalı


def choose_files(parent, title, done):
    """done([yol, ...])"""
    if hasattr(Gtk, "FileDialog"):
        dlg = Gtk.FileDialog(title=title)

        def fin(d, res):
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error:
                return
            done([p for p in (files.get_item(i).get_path() for i in range(files.get_n_items())) if p])
        dlg.open_multiple(parent, None, fin)
        return
    ch = Gtk.FileChooserNative(title=title, transient_for=parent, action=Gtk.FileChooserAction.OPEN,
                               select_multiple=True, accept_label="Seç")
    _native(ch, lambda: done([p for p in (f.get_path() for f in _list(ch.get_files())) if p]))


def choose_folder(parent, title, initial, done):
    """done(yol)"""
    if hasattr(Gtk, "FileDialog"):
        dlg = Gtk.FileDialog(title=title)
        if initial:
            dlg.set_initial_folder(Gio.File.new_for_path(initial))

        def fin(d, res):
            try:
                f = d.select_folder_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                done(f.get_path())
        dlg.select_folder(parent, None, fin)
        return
    ch = Gtk.FileChooserNative(title=title, transient_for=parent, action=Gtk.FileChooserAction.SELECT_FOLDER,
                               accept_label="Seç")
    if initial:
        try:
            ch.set_current_folder(Gio.File.new_for_path(initial))
        except GLib.Error:
            pass
    _native(ch, lambda: ch.get_file() and ch.get_file().get_path() and done(ch.get_file().get_path()))


def _list(model):
    return [model.get_item(i) for i in range(model.get_n_items())]


def _native(ch, on_accept):
    _keep.append(ch)

    def resp(_c, r):
        if r == Gtk.ResponseType.ACCEPT:
            on_accept()
        _keep.remove(ch)
    ch.connect("response", resp)
    ch.show()


def open_path(parent, path):
    if hasattr(Gtk, "FileLauncher"):
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).launch(parent, None, None)
    else:
        try:
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(path).get_uri(), None)
        except GLib.Error:
            pass


def show_in_folder(parent, path):
    if hasattr(Gtk, "FileLauncher"):
        Gtk.FileLauncher.new(Gio.File.new_for_path(path)).open_containing_folder(parent, None, None)
    else:
        f = Gio.File.new_for_path(path)
        open_path(parent, f.get_parent().get_path() if f.get_parent() else path)


def picture(**kw):
    """Gtk.Picture; 'content-fit' GTK 4.8+'da var."""
    if Gtk.Picture.find_property("content-fit") is not None:
        return Gtk.Picture(content_fit=Gtk.ContentFit.COVER, **kw)
    return Gtk.Picture(keep_aspect_ratio=False, **kw)
