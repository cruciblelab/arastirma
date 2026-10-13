"""Karekodla telefon ekleme penceresi: telefon karekodu okur, onay sorulmadan eşleşir (bkz. talkto/karekod.py)."""

import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .. import karekod  # noqa: E402

QUIET = 4  # karekodun çevresindeki beyaz boşluk (kare); okuyucular bunu ister


def texture(m, size=300):
    """Karekodun resmi: hep beyaz zemin üstüne siyah (koyu temada da okunsun), kareler tam piksel (bulanık
    kenar yok). Cairo gerekmez (python3-gi-cairo her sistemde kurulu değil)."""
    n = len(m) + 2 * QUIET
    cell = max(1, size // n)
    side = n * cell
    rows = []
    for y in range(n):
        line = bytearray()
        for x in range(n):
            dark = QUIET <= x < n - QUIET and QUIET <= y < n - QUIET and m[y - QUIET][x - QUIET]
            line += (b"\x00\x00\x00" if dark else b"\xff\xff\xff") * cell
        rows.append(bytes(line) * cell)
    row_bytes = b"".join(rows)
    return Gdk.MemoryTexture.new(side, side, Gdk.MemoryFormat.R8G8B8, GLib.Bytes.new(row_bytes), side * 3)


class QrWindow(Adw.Window):
    def __init__(self, app, parent, info: dict):
        super().__init__(title="Karekodla telefon ekle", modal=False, default_width=440,
                         transient_for=parent, destroy_with_parent=True)
        self.app = app
        self.matrix = None
        self.until = 0.0
        self._timer = GLib.timeout_add_seconds(1, self._tick)

        view = Adw.ToolbarView() if hasattr(Adw, "ToolbarView") else None
        header = Adw.HeaderBar()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=18,
                      margin_start=24, margin_end=24)
        self.picture = Gtk.Picture(can_shrink=False, halign=Gtk.Align.CENTER, height_request=300)
        box.append(self.picture)
        self.left = Gtk.Label(css_classes=["dim-label", "caption"])
        box.append(self.left)
        self.again = Gtk.Button(label="Yeni karekod", halign=Gtk.Align.CENTER, css_classes=["pill"], visible=False)
        self.again.connect("clicked", lambda *_: self.app.show_qr(renew=True))
        box.append(self.again)
        steps = Gtk.Label(wrap=True, xalign=0, max_width_chars=48, use_markup=True, label=(
            "<b>1.</b> Telefonda Talk To'yu aç.\n"
            "<b>2.</b> “Karekodu tara”ya dokun ve bu karekodu göster.\n"
            "<b>3.</b> Bitti: burada onay sorulmaz, telefon kendiliğinden bağlanır."))
        box.append(steps)
        self.note = Gtk.Label(wrap=True, xalign=0, max_width_chars=48, css_classes=["dim-label"])
        box.append(self.note)
        if view:
            view.add_top_bar(header)
            view.set_content(box)
            self.set_content(view)
        else:  # libadwaita 1.1 (Ubuntu 22.04)
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            outer.append(header)
            outer.append(box)
            self.set_content(outer)
        self.connect("close-request", self._on_close)
        self.update(info)

    def update(self, info: dict):
        self.matrix = karekod.matrix(info["link"])
        self.until = time.monotonic() + info["seconds"]
        self.picture.set_paintable(texture(self.matrix))
        self.again.set_visible(False)
        notes = []
        if info.get("wireless_turned_on"):
            notes.append("Wi-Fi bağlantısı açıldı (karekod Wi-Fi içindir; Tercihler'den kapatılabilir).")
        if not info.get("listening"):
            notes.append(info.get("error") or "Bu bilgisayar ağda dinlemiyor; telefon bağlanamaz.")
        elif not info.get("hosts"):
            notes.append("Bu bilgisayar bir ağa bağlı görünmüyor. Wi-Fi'ye ya da kabloyla ağa bağlanınca "
                         "“Yeni karekod”a bas.")
        else:
            notes.append(f"Telefon ve bu bilgisayar aynı ağda olmalı (bu bilgisayar: {', '.join(info['hosts'][:3])}).")
        notes.append("Karekod 10 dakika geçerli ve bir kez kullanılır. Okuyan telefon eşleşir: ekranı başkasına "
                     "gösterme.")
        self.note.set_text("\n".join(notes))
        self._tick()

    def _tick(self):
        left = int(self.until - time.monotonic())
        if left > 0:
            self.left.set_text(f"{left // 60}:{left % 60:02d} kaldı")
            return True
        # Süre doldu: eski karekod ekranda kalmasın (geçmiyor zaten).
        if self.matrix:
            self.matrix = None
            self.picture.set_paintable(None)
        self.left.set_text("Karekodun süresi doldu")
        self.again.set_visible(True)
        return True

    def _on_close(self, *_):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        self.app.qr_closed(self)
        return False
