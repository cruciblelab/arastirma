"""Masaüstü bildirim düğmeleri gerçek oturum veriyolunda: sahte bir bildirim sunucusu (GNOME'un yerine)
"düğmeye basıldı" sinyali yollar, uygulamanın geri çağrısı çalışmalı.

Arama bildirimindeki Kapat / Ses düğmeleri bu yoldan çalışır. Oturum veriyolu yoksa atlanır
(CI'da TALKTO_TEST_STRICT=1 iken atlanmaz).
"""

import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from gi.repository import Gio, GLib
    HAVE = bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
except ImportError:
    HAVE = False

if not HAVE and os.environ.get("TALKTO_TEST_STRICT"):
    raise RuntimeError("bildirim testi çalıştırılamıyor: oturum veriyolu yok")

XML = """<node><interface name="org.freedesktop.Notifications">
  <method name="Notify"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/>
    <arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="as" direction="in"/>
    <arg type="a{sv}" direction="in"/><arg type="i" direction="in"/><arg type="u" direction="out"/></method>
  <method name="CloseNotification"><arg type="u" direction="in"/></method>
  <signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
  <signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
</interface></node>"""


def spin(cond, secs=5):
    ctx, end = GLib.MainContext.default(), time.monotonic() + secs
    while not cond() and time.monotonic() < end:
        ctx.iteration(False)
        time.sleep(0.01)
    return cond()


@unittest.skipUnless(HAVE, "oturum veriyolu yok")
class NotificationButtonsTest(unittest.TestCase):
    def setUp(self):
        # Sunucu ayrı bir bağlantıda: GNOME Shell gibi başka bir süreçmiş gibi.
        addr = os.environ["DBUS_SESSION_BUS_ADDRESS"]
        self.srv = Gio.DBusConnection.new_for_address_sync(
            addr, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION)
        self.shown = []

        def call(conn, sender, path, iface, method, params, inv):
            if method == "Notify":
                self.shown.append(params.unpack())
                inv.return_value(GLib.Variant("(u)", (len(self.shown),)))
            else:
                inv.return_value(None)
        info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
        self.reg = self.srv.register_object("/org/freedesktop/Notifications", info, call, None, None)
        owned = []
        self.own = Gio.bus_own_name_on_connection(self.srv, "org.freedesktop.Notifications",
                                                  Gio.BusNameOwnerFlags.REPLACE, lambda *_: owned.append(1), None)
        self.assertTrue(spin(lambda: owned), "sahte bildirim sunucusu ad alamadı")

    def tearDown(self):
        Gio.bus_unown_name(self.own)
        self.srv.unregister_object(self.reg)
        self.srv.close_sync(None)

    def test_resident_call_notification_buttons(self):
        from talkto.ui.notifier import Notifier
        n = Notifier()
        pressed = []
        n.show("WhatsApp görüşmesi: Ayşe", "Sesli arama", key="call|p|k", resident=True,
               actions={"a0": ("Kapat", lambda: pressed.append("kapat")),
                        "ses_artir": ("Ses +", lambda: pressed.append("ses+"))})
        self.assertTrue(spin(lambda: self.shown and n.ids.get("call|p|k")))
        app, _replaces, _icon, title, _body, actions, hints, _t = self.shown[0]
        self.assertEqual(title, "WhatsApp görüşmesi: Ayşe")
        self.assertEqual(actions, ["a0", "Kapat", "ses_artir", "Ses +"])
        self.assertTrue(hints.get("resident"))  # düğmeye basınca kapanmasın (ses birkaç kez)
        nid = n.ids["call|p|k"]
        for action in ("ses_artir", "ses_artir", "a0"):
            self.srv.emit_signal(None, "/org/freedesktop/Notifications", "org.freedesktop.Notifications",
                                 "ActionInvoked", GLib.Variant("(us)", (nid, action)))
        self.assertTrue(spin(lambda: len(pressed) == 3), pressed)
        self.assertEqual(pressed, ["ses+", "ses+", "kapat"])


if __name__ == "__main__":
    unittest.main()
