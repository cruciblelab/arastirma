"""Ekran görüntüsü: xdg-desktop-portal (GNOME, KDE, Wayland ve X11'de çalışır).

İlk seferde masaüstü "Talk To Android ekran görüntüsü alabilsin mi?" diye
sorabilir. Portal yoksa ya da izin verilmezse çağıran taraf komut satırı
araçlarına (gnome-screenshot, spectacle, grim...) düşer.
"""

import secrets

from gi.repository import Gio, GLib

PORTAL = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"


def take_screenshot(done):
    """done(yol | None, hata | None) ana iş parçacığında çağrılır."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error as e:
        done(None, e.message)
        return
    token = "talkto" + secrets.token_hex(6)
    sender = bus.get_unique_name()[1:].replace(".", "_")
    handle = f"{PATH}/request/{sender}/{token}"
    state = {"sub": 0, "finished": False, "timer": 0}

    def finish(path, err):
        if state["finished"]:
            return
        state["finished"] = True
        if state["sub"]:
            bus.signal_unsubscribe(state["sub"])
        if state["timer"]:
            GLib.source_remove(state["timer"])
        done(path, err)

    def on_response(_c, _s, _p, _i, _sig, params):
        code, results = params.unpack()
        uri = results.get("uri") if code == 0 else None
        finish(Gio.File.new_for_uri(uri).get_path() if uri else None, None if uri else "izin verilmedi")

    def on_called(b, res):
        try:
            b.call_finish(res)
        except GLib.Error as e:
            finish(None, e.message)

    def on_timeout():
        state["timer"] = 0
        finish(None, "zaman aşımı")
        return False

    state["sub"] = bus.signal_subscribe(PORTAL, "org.freedesktop.portal.Request", "Response", handle, None,
                                        Gio.DBusSignalFlags.NONE,
                                        on_response)
    state["timer"] = GLib.timeout_add_seconds(60, on_timeout)
    opts = {"handle_token": GLib.Variant("s", token), "interactive": GLib.Variant("b", False)}
    bus.call(PORTAL, PATH, "org.freedesktop.portal.Screenshot", "Screenshot",
             GLib.Variant("(sa{sv})", ("", opts)), GLib.VariantType("(o)"),
             Gio.DBusCallFlags.NONE, 10000, None, on_called)
