"""Bluetooth bağlantısı: BlueZ'e bir RFCOMM sunucu profili kaydedilir.

Telefon, işletim sisteminin Bluetooth ayarlarından bu bilgisayarla önceden
eşleştirilmiş olmalıdır (RequireAuthentication). Telefon profile bağlanınca
BlueZ, NewConnection ile bağlı soketin dosya tanıtıcısını verir; aynı TLS +
onay/belirteç akışı bu soket üzerinde çalışır.

Gio D-Bus geri çağrıları GLib ana döngüsünde gelir; bu yüzden sınıf masaüstü
arayüzünün iş parçacığında oluşturulur.
"""

import logging
import socket

from gi.repository import Gio, GLib

log = logging.getLogger("talkto.bluetooth")

SERVICE_UUID = "a3c5e9d4-7b1f-4c6e-9d2a-5f8b3e1c7a90"  # Android tarafı: BluetoothLink.kt
PROFILE_PATH = "/lab/crucible/TalkToAndroid/bluetooth"
INTROSPECTION = """
<node>
  <interface name="org.bluez.Profile1">
    <method name="Release"/>
    <method name="NewConnection">
      <arg type="o" name="device" direction="in"/>
      <arg type="h" name="fd" direction="in"/>
      <arg type="a{sv}" name="properties" direction="in"/>
    </method>
    <method name="RequestDisconnection">
      <arg type="o" name="device" direction="in"/>
    </method>
  </interface>
</node>
"""


class BluetoothServer:
    def __init__(self, on_socket, on_state):
        """on_socket(sock, adres, ad), on_state({'available', 'message'})"""
        self.on_socket = on_socket
        self.on_state = on_state
        self.bus = None
        self.reg_id = None
        self.registered = False

    def start(self):
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            names = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                       "ListNames", None, None, Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
        except GLib.Error as e:
            self._state(False, f"Sistem D-Bus'ına erişilemedi: {e.message}")
            return
        if "org.bluez" not in names:
            self._state(False, "Bluetooth servisi (BlueZ) çalışmıyor ya da bilgisayarda Bluetooth yok.")
            return
        node = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)
        try:
            self.reg_id = self.bus.register_object(PROFILE_PATH, node.interfaces[0], self._on_call, None, None)
        except GLib.Error as e:
            self._state(False, f"Bluetooth profili hazırlanamadı: {e.message}")
            return
        opts = {
            "Name": GLib.Variant("s", "Talk To Android"),
            "Role": GLib.Variant("s", "server"),
            "RequireAuthentication": GLib.Variant("b", True),
            "RequireAuthorization": GLib.Variant("b", False),
            "AutoConnect": GLib.Variant("b", False),
        }
        self.bus.call("org.bluez", "/org/bluez", "org.bluez.ProfileManager1", "RegisterProfile",
                      GLib.Variant("(osa{sv})", (PROFILE_PATH, SERVICE_UUID, opts)), None,
                      Gio.DBusCallFlags.NONE, 5000, None, self._registered)

    def _registered(self, bus, res):
        try:
            bus.call_finish(res)
        except GLib.Error as e:
            self._state(False, f"BlueZ profili kaydetmedi: {e.message}")
            return
        self.registered = True
        self._state(True, "Hazır. Telefonu önce sistemin Bluetooth ayarlarından bu bilgisayarla eşleştir.")

    def stop(self):
        if self.bus and self.registered:
            try:
                self.bus.call_sync("org.bluez", "/org/bluez", "org.bluez.ProfileManager1", "UnregisterProfile",
                                   GLib.Variant("(o)", (PROFILE_PATH,)), None, Gio.DBusCallFlags.NONE, 2000, None)
            except GLib.Error:
                pass
        if self.bus and self.reg_id:
            self.bus.unregister_object(self.reg_id)
        self.reg_id = None
        self.registered = False
        self._state(False, "Kapalı")

    def _state(self, ok, message):
        self.on_state({"available": ok, "message": message})

    def _device_name(self, path: str) -> str:
        try:
            v = self.bus.call_sync("org.bluez", path, "org.freedesktop.DBus.Properties", "Get",
                                   GLib.Variant("(ss)", ("org.bluez.Device1", "Alias")), None,
                                   Gio.DBusCallFlags.NONE, 1000, None)
            return v.unpack()[0]
        except GLib.Error:
            return path.rsplit("/", 1)[-1]

    def _on_call(self, conn, sender, path, iface, method, params, invocation):
        if method == "NewConnection":
            device, fd_index, _props = params.unpack()
            fd_list = invocation.get_message().get_unix_fd_list()
            try:
                fd = fd_list.get(fd_index)
            except GLib.Error as e:
                invocation.return_dbus_error("org.bluez.Error.Rejected", e.message)
                return
            address = device.rsplit("dev_", 1)[-1].replace("_", ":")
            sock = socket.socket(fileno=fd)
            invocation.return_value(None)
            log.info("Bluetooth bağlantısı: %s (%s)", self._device_name(device), address)
            self.on_socket(sock, address, self._device_name(device))
        else:  # Release, RequestDisconnection
            invocation.return_value(None)
