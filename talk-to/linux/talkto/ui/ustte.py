"""Pencereyi diğerlerinin üstünde tutmak (mini oynatıcı).

GTK 4'te bunun için bir çağrı yok. X11'de pencere yöneticisinden standart yolla istenir
(_NET_WM_STATE_ABOVE, libX11 ile). Wayland'de uygulamanın kendini üstte tutması güvenlik gereği yasak.

Wayland'de çıkış yolu: masaüstü X11 uygulamaları için XWayland'i de çalıştırır (DISPLAY). Mini oynatıcı
o ekranda açılırsa ona X11 penceresi gibi davranılır: üstte tutulabilir ve konumu verilebilir (tepecik ekranın
üst ortasına yerleşir). Bedeli: ölçekli (HiDPI) ekranda biraz bulanık görünebilir. XWayland yoksa kullanıcıya
pencere menüsünden ("Her zaman üstte") nasıl yapılacağı söylenir.

Eskiden mini oynatıcı pencere menüsünü kendisi açmaya çalışıyordu (show_window_menu); GTK 4.6 +
Wayland'de pencerenin çökmesine yol açtığı bildirildi, o yol kaldırıldı.
"""

import ctypes
import ctypes.util
import logging
import os

log = logging.getLogger("talkto.ustte")

WAYLAND_HINT = ("Wayland'de uygulamalar kendini üstte tutamıyor. Mini oynatıcının boş bir yerine sağ tıkla "
                "(ya da Alt+Boşluk) → “Her zaman üstte”.")

_x11 = None  # Wayland oturumunda açılan XWayland ekranı (bir kez)


def _gdkx11():
    try:
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
        return GdkX11
    except (ImportError, ValueError):
        return None


def is_x11(display) -> bool:
    x = _gdkx11()
    return bool(x and isinstance(display, x.X11Display))


def x11_display():
    """Üstte tutmanın mümkün olduğu ekran: X11 oturumunda varsayılan ekran, Wayland'de XWayland; yoksa None."""
    global _x11
    from gi.repository import Gdk
    default = Gdk.Display.get_default()
    if is_x11(default):
        return default
    if _x11 is None:
        _x11 = False
        if os.environ.get("DISPLAY") and ctypes.util.find_library("X11") and _gdkx11():
            try:
                d = Gdk.DisplayManager.get().open_display(os.environ["DISPLAY"])
            except Exception as e:  # noqa: BLE001 - açılamazsa eski yol (yönerge)
                log.info("XWayland açılamadı: %s", e)
                d = None
            _x11 = d if is_x11(d) else False
    return _x11 or None


def _x11_xid(window) -> int | None:
    x = _gdkx11()
    surface = window.get_surface()
    return surface.get_xid() if x and isinstance(surface, x.X11Surface) else None


def supported(window) -> bool:
    return _x11_xid(window) is not None and ctypes.util.find_library("X11") is not None


class _ClientMessage(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int), ("data", ctypes.c_long * 5)]


class _XEvent(ctypes.Union):
    _fields_ = [("xclient", _ClientMessage), ("pad", ctypes.c_long * 24)]


def keep_above(window, on: bool) -> bool:
    """X11'de pencere yöneticisinden pencereyi üstte tutmasını ister; olmadıysa False."""
    xid = _x11_xid(window)
    lib = ctypes.util.find_library("X11")
    if xid is None or lib is None:
        return False
    try:
        x = ctypes.CDLL(lib)
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XDefaultRootWindow.restype = ctypes.c_ulong
        x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x.XInternAtom.restype = ctypes.c_ulong
        x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long,
                                 ctypes.POINTER(_XEvent)]
        x.XFlush.argtypes = [ctypes.c_void_p]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        d = x.XOpenDisplay(window.get_display().get_name().encode())
        if not d:
            return False
        try:
            ev = _XEvent()
            ev.xclient.type = 33  # ClientMessage
            ev.xclient.send_event = 1
            ev.xclient.window = xid
            ev.xclient.message_type = x.XInternAtom(d, b"_NET_WM_STATE", 0)
            ev.xclient.format = 32
            ev.xclient.data[0] = 1 if on else 0  # _NET_WM_STATE_ADD / _REMOVE
            ev.xclient.data[1] = x.XInternAtom(d, b"_NET_WM_STATE_ABOVE", 0)
            ev.xclient.data[3] = 1  # istek sıradan bir uygulamadan
            mask = (1 << 20) | (1 << 19)  # SubstructureRedirectMask | SubstructureNotifyMask
            ok = x.XSendEvent(d, x.XDefaultRootWindow(d), 0, mask, ctypes.byref(ev)) != 0
            x.XFlush(d)
            return ok
        finally:
            x.XCloseDisplay(d)
    except (OSError, AttributeError) as e:
        log.info("üstte tutulamadı: %s", e)
        return False


def move(window, x: int, y: int) -> bool:
    """X11 penceresini ekranda (x, y)'ye taşır (Wayland penceresinde mümkün değil)."""
    xid = _x11_xid(window)
    lib = ctypes.util.find_library("X11")
    if xid is None or lib is None:
        return False
    try:
        xl = ctypes.CDLL(lib)
        xl.XOpenDisplay.restype = ctypes.c_void_p
        xl.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xl.XMoveWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int]
        xl.XFlush.argtypes = [ctypes.c_void_p]
        xl.XCloseDisplay.argtypes = [ctypes.c_void_p]
        name = window.get_display().get_name().encode()
        d = xl.XOpenDisplay(name)
        if not d:
            return False
        try:
            xl.XMoveWindow(d, xid, int(x), int(y))
            xl.XFlush(d)
            return True
        finally:
            xl.XCloseDisplay(d)
    except (OSError, AttributeError) as e:
        log.info("taşınamadı: %s", e)
        return False


def top_center(window) -> bool:
    """X11 penceresini bulunduğu ekranın üst ortasına (üst çubuğun hemen altına) yerleştirir."""
    surface = window.get_surface()
    if _x11_xid(window) is None or surface is None:
        return False
    mon = window.get_display().get_monitor_at_surface(surface)
    if mon is None:
        return False
    geo = mon.get_workarea() if hasattr(mon, "get_workarea") else mon.get_geometry()
    scale = surface.get_scale_factor()
    return move(window, (geo.x + (geo.width - window.get_width()) // 2) * scale, geo.y * scale)
