"""Pencereyi diğerlerinin üstünde tutmak (mini oynatıcı).

GTK 4'te bunun için bir çağrı yok. X11'de pencere yöneticisinden standart yolla istenir
(_NET_WM_STATE_ABOVE, libX11 ile). Wayland'de uygulamanın kendini üstte tutması güvenlik gereği yasak:
yalnızca kullanıcı pencere menüsünden ("Her zaman üstte") seçebilir; uygulama bunu söyler.

Eskiden mini oynatıcı pencere menüsünü kendisi açmaya çalışıyordu (show_window_menu); GTK 4.6 +
Wayland'de pencerenin çökmesine yol açtığı bildirildi, o yol kaldırıldı.
"""

import ctypes
import ctypes.util
import logging

log = logging.getLogger("talkto.ustte")

WAYLAND_HINT = ("Wayland'de uygulamalar kendini üstte tutamıyor. Mini oynatıcının boş bir yerine sağ tıkla → "
                "“Her zaman üstte”.")


def _x11_xid(window) -> int | None:
    try:
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
    except (ImportError, ValueError):
        return None
    surface = window.get_surface()
    return surface.get_xid() if isinstance(surface, GdkX11.X11Surface) else None


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
        d = x.XOpenDisplay(None)
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
