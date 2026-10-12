"""Masaüstü bildirimleri: org.freedesktop.Notifications (GNOME, KDE, XFCE, ...).

Telefon bildirimini telefonda silinince masaüstünden de kaldırabilmek için
bildirim numaraları anahtara göre tutulur.
"""

import logging

from gi.repository import Gio, GLib

from .. import APP_ID

log = logging.getLogger("talkto.bildirim")
NAME = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"


class Notifier:
    def __init__(self):
        self.ids: dict[str, int] = {}
        self.actions: dict[int, dict] = {}
        # Notify cevabı (numara) gelmeden aynı anahtar güncellenir ya da kapatılırsa: sıraya alınır,
        # yoksa ikinci bir bildirim açılır ve ilki masaüstünde sahipsiz kalırdı.
        self.pending: dict[str, dict] = {}
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self.bus.signal_subscribe(NAME, NAME, "ActionInvoked", PATH, None,
                                      Gio.DBusSignalFlags.NONE, self._on_action)
            self.bus.signal_subscribe(NAME, NAME, "NotificationClosed", PATH, None,
                                      Gio.DBusSignalFlags.NONE, self._on_closed)
        except GLib.Error as e:
            log.warning("bildirim servisine bağlanılamadı: %s", e.message)
            self.bus = None

    def show(self, title: str, body: str = "", *, key: str | None = None, app_name: str = "Talk To",
             icon: str | None = None, actions: dict | None = None, urgent=False, resident=False,
             sound: str | None = None):
        """actions: {'kimlik': ('Etiket', geri_çağrı)}; resident: düğmeye basınca kapanmasın (ör. ses +/−)."""
        if not self.bus:
            return
        if key and key in self.pending:
            self.pending[key].update(next=(title, body, dict(key=key, app_name=app_name, icon=icon,
                                                             actions=actions, urgent=urgent, resident=resident,
                                                             sound=sound)),
                                     close=False)
            return
        if key:
            self.pending[key] = {"next": None, "close": False}
        replaces = self.ids.get(key, 0) if key else 0
        acts = []
        for k, (label, _) in (actions or {}).items():
            acts += [k, label]
        hints = {"desktop-entry": GLib.Variant("s", APP_ID),
                 "urgency": GLib.Variant("y", 2 if urgent else 1)}
        if resident:
            hints["resident"] = GLib.Variant("b", True)
        if sound:  # freedesktop ses teması adı (ör. alarm-clock-elapsed)
            hints["sound-name"] = GLib.Variant("s", sound)
        args = GLib.Variant("(susssasa{sv}i)", (
            app_name, replaces, icon or APP_ID, title, GLib.markup_escape_text(body or ""),
            acts, hints, -1))
        self.bus.call(NAME, PATH, NAME, "Notify", args, GLib.VariantType("(u)"),
                      Gio.DBusCallFlags.NONE, 3000, None, self._shown, (key, actions))

    def _shown(self, bus, res, data):
        key, actions = data
        waiting = self.pending.pop(key, None) if key else None
        try:
            nid = bus.call_finish(res).unpack()[0]
        except GLib.Error as e:
            log.debug("bildirim gösterilemedi: %s", e.message)
            nid = None
        if nid is not None:
            if key:
                self.ids[key] = nid
            if actions:
                self.actions[nid] = actions
        if waiting and waiting["close"]:
            self.close(key)
        elif waiting and waiting["next"]:
            title, body, kw = waiting["next"]
            self.show(title, body, **kw)

    def close(self, key: str):
        if key in self.pending:  # numarası henüz gelmedi: gelince kapatılır
            self.pending[key].update(close=True, next=None)
            return
        nid = self.ids.pop(key, None)
        if nid and self.bus:
            self.bus.call(NAME, PATH, NAME, "CloseNotification", GLib.Variant("(u)", (nid,)),
                          None, Gio.DBusCallFlags.NONE, 3000, None, None)

    def _on_action(self, _bus, _sender, _path, _iface, _signal, params):
        nid, action = params.unpack()
        cb = self.actions.get(nid, {}).get(action)
        if cb:
            cb[1]()

    def _on_closed(self, _bus, _sender, _path, _iface, _signal, params):
        nid = params.unpack()[0]
        self.actions.pop(nid, None)
        for k, v in list(self.ids.items()):
            if v == nid:
                del self.ids[k]
