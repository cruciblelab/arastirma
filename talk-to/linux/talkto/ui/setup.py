"""Kurulum yardımcısı: ilk açılışta adım adım; her satırda durum, yapan düğme ve "Kontrol et".

Denetimler talkto.setup_checks'te; bu dosya yalnızca gösterir ve düğmeleri uygulamaya bağlar.
libadwaita 1.1'de olan parçalarla yazıldı (Ubuntu 22.04).
"""

from gi.repository import Adw, Gio, GLib, Gtk

from .. import setup_checks
from . import compat, system


class SetupAssistant(Adw.Window):
    def __init__(self, app, parent=None):
        super().__init__(title="Kurulum yardımcısı", default_width=620, default_height=680,
                         transient_for=parent, modal=False)
        self.app = app
        self.step = 0
        self.steps = []

        self.toasts = Adw.ToastOverlay()
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.title = Adw.WindowTitle(title="Kurulum yardımcısı")
        header = Adw.HeaderBar(title_widget=self.title)
        self.skip = Gtk.Button(label="Atla", css_classes=["flat"])
        self.skip.connect("clicked", lambda *_: self.finish())
        header.pack_end(self.skip)
        outer.append(header)

        scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        clamp = Adw.Clamp(maximum_size=560, margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.icon = Gtk.Image(pixel_size=56, halign=Gtk.Align.START)
        self.heading = Gtk.Label(xalign=0, wrap=True, css_classes=["title-1"])
        self.text = Gtk.Label(xalign=0, wrap=True, css_classes=["dim-label"])
        self.group = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        for w in (self.icon, self.heading, self.text, self.group):
            self.body.append(w)
        clamp.set_child(self.body)
        scroll.set_child(clamp)
        outer.append(scroll)

        bottom = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=10, margin_bottom=14,
                         margin_start=18, margin_end=18)
        self.progress = Gtk.ProgressBar()
        buttons = Gtk.Box(spacing=12, homogeneous=True)
        self.back = Gtk.Button(label="Geri")
        self.back.connect("clicked", lambda *_: self.go(-1))
        self.next = Gtk.Button(label="İleri", css_classes=["suggested-action"])
        self.next.connect("clicked", lambda *_: self.go(+1))
        buttons.append(self.back)
        buttons.append(self.next)
        bottom.append(self.progress)
        bottom.append(buttons)
        outer.append(bottom)

        self.toasts.set_child(outer)
        self.set_content(self.toasts)
        self.refresh()

    # ---- durum ----------------------------------------------------------------

    def _state(self):
        w = self.app.window
        status = getattr(w, "status", None) or self.app.hub.status()
        usb = getattr(w, "usb", None) or self.app.hub.usb.snapshot()
        return status, usb

    def refresh(self):
        status, usb = self._state()
        self.steps = setup_checks.steps(status, usb, autostart=system.autostart_enabled())
        self.step = max(0, min(self.step, len(self.steps) - 1))
        s = self.steps[self.step]
        last = self.step == len(self.steps) - 1
        self.title.set_subtitle(f"Adım {self.step + 1}/{len(self.steps)}")
        self.icon.set_from_icon_name(s.icon)
        self.heading.set_label(s.title)
        self.text.set_label(s.text)
        self.progress.set_fraction((self.step + 1) / len(self.steps))
        self.back.set_sensitive(self.step > 0)
        self.next.set_label("Başla" if self.step == 0 else ("Bitir" if last else "İleri"))
        self.skip.set_visible(not last)

        child = self.group.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.group.remove(child)
            child = nxt
        self.group.set_visible(bool(s.items))
        for item in s.items:
            self.group.append(self._row(item))

    def _row(self, item):
        r = compat.row(item.title, item.text)
        r.set_subtitle_lines(6)
        if item.ok is True:
            icon, cls = "emblem-ok-symbolic", ["success"]
        elif item.ok is False:
            icon, cls = "dialog-warning-symbolic", ["dim-label"] if item.optional else ["warning"]
        else:
            icon, cls = "dialog-information-symbolic", ["dim-label"]
        r.add_prefix(Gtk.Image(icon_name=icon, css_classes=cls))
        if item.ok is False:
            if item.action:
                b = Gtk.Button(label=item.action_label or "Yap", valign=Gtk.Align.CENTER,
                               css_classes=["suggested-action"])
                b.connect("clicked", lambda *_, a=item.action: self.run(a))
                r.add_suffix(b)
            check = Gtk.Button(label="Kontrol et", valign=Gtk.Align.CENTER, css_classes=["flat"])
            check.connect("clicked", lambda *_, t=item.title: self.check(t))
            r.add_suffix(check)
        return r

    def check(self, title):
        self.refresh()
        item = next((i for i in self.steps[self.step].items if i.title == title), None)
        done = item is None or item.ok  # başlığı değiştiyse (ör. "takılı değil" → "görünüyor") sorun çözülmüştür
        self.toast(f"✓ {title}: tamam" if done else f"{title}: henüz değil")

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=3))

    # ---- adımlar ------------------------------------------------------------------

    def go(self, delta):
        if self.step == len(self.steps) - 1 and delta > 0:
            self.finish()
            return
        self.step += delta
        self.refresh()

    def finish(self):
        self.app.config.set("setup_done", True)
        self.close()

    # ---- düğmeler -----------------------------------------------------------------

    def run(self, action):
        app = self.app
        if action == "install_adb":
            app.install_adb()
        elif action == "enable_usb":
            app.call("set_option", "usb", True)
        elif action == "enable_wireless":
            app.call("set_option", "wireless", True)
        elif action == "enable_bluetooth":
            app.set_bluetooth(True)
        elif action == "install_scrcpy":
            app._with_scrcpy(lambda: (self.toast("scrcpy hazır"), self.refresh()))
            return
        elif action == "enable_autostart":
            system.set_autostart(True)
        elif action == "allow_firewall":
            self._allow_firewall()
            return
        elif action.startswith("install_phone_app:"):
            app.install_phone_app(action.split(":", 1)[1])
            self.toast("Telefona kuruluyor; telefonda açılınca “USB kablosu”nu seç")
            return
        # Ayar değişikliği hub'da; kısa süre sonra durum güncellenince yeniden çizilir.
        GLib.timeout_add(600, lambda: (self.refresh(), False)[-1])

    def _allow_firewall(self):
        cmd = setup_checks.firewall_command(self.app.config["port"])
        if not cmd:
            self.toast("ufw ya da pkexec bulunamadı")
            return
        try:
            proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        except GLib.Error as e:
            self.toast(f"Olmadı: {e.message}")
            return

        def done(p, res):
            try:
                p.communicate_utf8_finish(res)
            except GLib.Error:
                pass
            ok = p.get_exit_status() == 0
            self.toast("Güvenlik duvarına izin eklendi" if ok else "İzin eklenemedi (iptal edildi ya da yetki yok)")
        proc.communicate_utf8_async(None, None, done)
