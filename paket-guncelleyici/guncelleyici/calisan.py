"""Kurulan uygulama şu an açık mı; açıksa kapatıp yeni sürümle yeniden açmak.

Paket güncellenince diskteki dosyalar yenilenir ama açık uygulama bellekteki eski sürümle çalışmaya
devam eder (Hakkında'da eski sürüm görünür). GTK/GApplication uygulamaları oturum veriyolunda masaüstü
dosyasının adıyla (ör. lab.crucible.TalkToAndroid) kayıtlıdır ve çoğu "quit" eylemini org.gtk.Actions
üzerinden sunar; öyleyse "Yeniden başlat" düğmesi gösterilir. Kendini güncellenince yeniden başlatan
uygulamalar masaüstü dosyasında bunu söyler (X-Guncellenince-Yeniden-Baslar=true); onlar için bir şey
yapmaya gerek yoktur.
"""

from gi.repository import Gio, GLib

KENDI_YENILER = "X-Guncellenince-Yeniden-Baslar"


def bus_name(desktop_id: str) -> str:
    return desktop_id[:-len(".desktop")] if desktop_id.endswith(".desktop") else desktop_id


def object_path(name: str) -> str:
    return "/" + name.replace(".", "/").replace("-", "_")


def _call(dest, path, iface, method, args, reply):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    return bus.call_sync(dest, path, iface, method, args, GLib.VariantType(reply) if reply else None,
                         Gio.DBusCallFlags.NO_AUTO_START, 3000, None)


def running(name: str) -> bool:
    try:
        return _call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                     GLib.Variant("(s)", (name,)), "(b)").unpack()[0]
    except GLib.Error:
        return False


def can_quit(name: str) -> bool:
    try:
        actions = _call(name, object_path(name), "org.gtk.Actions", "List", None, "(as)").unpack()[0]
    except GLib.Error:
        return False
    return "quit" in actions


def quit_app(name: str) -> bool:
    try:
        _call(name, object_path(name), "org.gtk.Actions", "Activate",
              GLib.Variant("(sava{sv})", ("quit", [], {})), None)
        return True
    except GLib.Error:
        return False


def restarts_itself(info) -> bool:
    try:
        return bool(info and info.get_boolean(KENDI_YENILER))
    except (AttributeError, TypeError):
        return False
