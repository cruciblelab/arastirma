"""İlerleme penceresi: indirme ya da kurulum sürerken ne olduğu görünsün, bitince sonucu yazsın.

Uzun işler (adb'yi kurmak, scrcpy'yi indirmek) yalnızca kısa bir bildirimle başlayıp sessizce bitince
kullanıcı ne olduğunu anlamıyordu. Bu pencere işin adını, ilerlemeyi (yüzde ya da belirsiz),
apt'nin kilit beklemesini ("Ubuntu kendi güncellemesini yapıyor") ve sonucu gösterir.

Pencerenin boyutu içerikle değişmez (bkz. miniplayer: GTK 4.6 Wayland'de boyutu sabit pencerenin
büyümesi uygulamayı kapatabiliyordu).
"""

import re

from gi.repository import Adw, Gio, GLib, Gtk, Pango

_LOCK = re.compile(r"(\d+)\D*?\(([^)]+)\)")
HOLDERS = {"unattended-upgr": "Ubuntu'nun otomatik güncellemesi", "packagekitd": "Uygulama Merkezi",
           "apt": "başka bir apt komutu", "apt-get": "başka bir apt komutu", "dpkg": "başka bir paket kurulumu"}


def parse_apt_line(line: str):
    """("kilit", metin) | ("yuzde", oran, metin) | ("satir", metin) | None"""
    line = line.strip()
    if not line:
        return None
    if line.startswith(("pmstatus:", "dlstatus:")):
        parts = line.split(":", 3)
        try:
            return ("yuzde", float(parts[2]) / 100, parts[3])
        except (IndexError, ValueError):
            return None
    if "/var/lib/dpkg/lock" in line or "/var/lib/apt/lists/lock" in line:
        m = _LOCK.search(line.split("lock", 1)[-1])
        who = HOLDERS.get(m.group(2), m.group(2)) if m else "başka bir paket işlemi"
        return ("kilit", f"Sırada: {who} şu an paket kilidini tutuyor. O bitince kurulum kendiliğinden başlar.")
    return ("satir", line)


class ProgressWindow(Adw.Window):
    def __init__(self, parent, title, text="", icon="folder-download-symbolic", cancel=None):
        super().__init__(transient_for=parent, modal=True, title=title, default_width=440, default_height=320,
                         resizable=True, hide_on_close=False)
        self.set_size_request(360, 320)
        self.cancel_cb = cancel
        self.finished = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(Adw.HeaderBar(show_end_title_buttons=False, css_classes=["flat"],
                                 title_widget=Gtk.Box()))
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, vexpand=True, margin_start=28,
                       margin_end=28, valign=Gtk.Align.CENTER)
        self.icon = Gtk.Image(icon_name=icon, pixel_size=48, css_classes=["dim-label"])
        self.heading = Gtk.Label(label=title, wrap=True, justify=Gtk.Justification.CENTER, css_classes=["title-3"])
        self.bar = Gtk.ProgressBar(margin_top=6)
        self.label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER, lines=3,
                               ellipsize=Pango.EllipsizeMode.END, height_request=54, valign=Gtk.Align.START,
                               css_classes=["dim-label"])
        for w in (self.icon, self.heading, self.bar, self.label):
            body.append(w)
        box.append(body)
        self.button = Gtk.Button(label="Durdur" if cancel else "Kapat", halign=Gtk.Align.CENTER, margin_bottom=18,
                                 margin_top=6, css_classes=["pill"], sensitive=bool(cancel))
        self.button.connect("clicked", self._on_button)
        box.append(self.button)
        self.set_content(box)
        self._pulse = GLib.timeout_add(120, self._tick)
        self._indeterminate = True
        self.connect("close-request", self._on_close_request)
        self.after_close = None

    def _tick(self):
        if self._indeterminate and not self.finished:
            self.bar.pulse()
        return not self.finished

    def _on_close_request(self, *_):
        if not self.finished and not self.cancel_cb:
            return True  # yönetici olarak süren kurulum yarıda bırakılamaz; bitince kapanır
        if not self.finished and self.cancel_cb:
            self.cancel_cb()
        return False

    def _on_button(self, *_):
        if self.finished:
            self.close()
        elif self.cancel_cb:
            self.button.set_sensitive(False)
            self.label.set_text("Durduruluyor…")
            self.cancel_cb()

    def set_text(self, text):
        self.label.set_text(text)

    def set_fraction(self, fraction):
        if fraction is None:
            self._indeterminate = True
        else:
            self._indeterminate = False
            self.bar.set_fraction(max(0.0, min(1.0, fraction)))

    def finish(self, ok, title, text=""):
        self.finished = True
        self.icon.set_from_icon_name("emblem-ok-symbolic" if ok else "dialog-error-symbolic")
        self.icon.set_css_classes(["success"] if ok else ["error"])
        self.heading.set_label(title)
        self.label.set_text(text)
        self.bar.set_visible(ok)
        if ok:
            self.bar.set_fraction(1)
        self.button.set_label("Kapat")
        self.button.set_sensitive(True)
        self.button.add_css_class("suggested-action")


def run_privileged(parent, title, cmd, on_done, icon="system-software-install-symbolic"):
    """pkexec ile bir kurulum komutunu çalıştırır; çıktıyı izleyip pencerede gösterir.

    on_done(ok, mesaj) — pencere sonucu da kendisi yazar.
    """
    win = ProgressWindow(parent, title, "Bilgisayarın şifresi soruluyor…", icon)
    win.present()
    try:
        proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
    except GLib.Error as e:
        win.finish(False, "Kurulamadı", e.message)
        on_done(False, e.message)
        return win
    state = {"buf": "", "last": ""}

    def handle(line):
        ev = parse_apt_line(line)
        if not ev:
            return
        if ev[0] == "kilit":
            win.set_fraction(None)
            win.set_text(ev[1])
        elif ev[0] == "yuzde":
            win.set_fraction(ev[1])
            win.set_text(ev[2])
        else:
            state["last"] = ev[1]
            if win._indeterminate:
                win.set_text(ev[1][:160])

    def got(stream, res):
        try:
            data = stream.read_bytes_finish(res)
        except GLib.Error:
            return
        if data.get_size() == 0:
            handle(state["buf"])
            return
        state["buf"] += data.get_data().decode("utf-8", "replace")
        parts = re.split(r"[\r\n]", state["buf"])
        state["buf"] = parts.pop()
        for p in parts:
            handle(p)
        stream.read_bytes_async(4096, GLib.PRIORITY_DEFAULT, None, got)
    proc.get_stdout_pipe().read_bytes_async(4096, GLib.PRIORITY_DEFAULT, None, got)

    def exited(p, res):
        try:
            p.wait_finish(res)
        except GLib.Error:
            pass
        status = p.get_exit_status()
        ok = status == 0
        msg = {126: "Şifre penceresi kapatıldı; hiçbir şey değişmedi.",
               127: "Yönetici izni verilmedi; hiçbir şey değişmedi."}.get(status, "" if ok else state["last"][-200:])
        on_done(ok, msg)
    proc.wait_async(None, exited)
    return win
