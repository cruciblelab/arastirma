"""Telefonda çalan müziği bilgisayarda gerçek bir medya oynatıcısı gibi gösterir (MPRIS).

GNOME'un üst çubuktaki medya denetimi, klavyedeki oynat/duraklat/ileri tuşları ve
playerctl gibi araçlar bilgisayardaki oynatıcıları MPRIS D-Bus arayüzünden bulur.
Her bağlı telefon için "org.mpris.MediaPlayer2.talktoandroid.<kimlik>" adıyla bir
oynatıcı açılır; komutlar telefona "media_control" olarak gider.

Bilgisayardaki medyayı telefona taşıyan talkto.media bu adları atlar (yoksa telefonun
şarkısı telefona geri yansırdı).
"""

import hashlib
import logging
import time

from gi.repository import Gio, GLib

from ..config import cache_dir
from ..media import OWN_PREFIX

log = logging.getLogger("talkto.telefon_medya")

PATH = "/org/mpris/MediaPlayer2"
XML = """
<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/>
    <method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Pause"/>
    <method name="PlayPause"/>
    <method name="Stop"/>
    <method name="Play"/>
    <method name="Seek"><arg direction="in" name="Offset" type="x"/></method>
    <method name="SetPosition">
      <arg direction="in" name="TrackId" type="o"/>
      <arg direction="in" name="Position" type="x"/>
    </method>
    <method name="OpenUri"><arg direction="in" name="Uri" type="s"/></method>
    <signal name="Seeked"><arg name="Position" type="x"/></signal>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>
"""
NODE = Gio.DBusNodeInfo.new_for_xml(XML)
ROOT, PLAYER = NODE.interfaces[0], NODE.interfaces[1]
ACTIONS = {"Next": "next", "Previous": "previous", "Pause": "pause", "PlayPause": "play_pause",
           "Stop": "pause", "Play": "play"}


def bus_name(device_id: str) -> str:
    # D-Bus ad parçası rakamla başlayamaz ve yalnızca [A-Za-z0-9_] içerebilir.
    return OWN_PREFIX + "d" + hashlib.sha256(device_id.encode()).hexdigest()[:12]


class PhonePlayer:
    """Bir telefonun oynatıcısı. control(device_id, action, value) komutu telefona iletir."""

    def __init__(self, bus, device_id: str, device_name: str, control):
        self.bus, self.device_id, self.device_name, self.control = bus, device_id, device_name, control
        self.state: dict = {"active": False}
        self.received = time.monotonic()
        self.track = 0
        self.regs = [bus.register_object(PATH, iface, self._method, self._get, self._set)
                     for iface in (ROOT, PLAYER)]
        self.owner = Gio.bus_own_name_on_connection(bus, bus_name(device_id), Gio.BusNameOwnerFlags.NONE,
                                                    None, None)

    def close(self):
        Gio.bus_unown_name(self.owner)
        for r in self.regs:
            self.bus.unregister_object(r)

    # ---- durum ----------------------------------------------------------------

    def position_us(self) -> int:
        st = self.state
        pos = st.get("position_ms", 0)
        if st.get("playing"):
            pos += (time.monotonic() - self.received) * 1000
        dur = st.get("duration_ms") or 0
        return int(min(pos, dur) if dur else pos) * 1000

    def update(self, state: dict):
        old = self.state
        predicted_ms = self.position_us() // 1000
        if (state.get("title"), state.get("artist")) != (old.get("title"), old.get("artist")):
            self.track += 1
        self.state, self.received = state, time.monotonic()
        changed = {k: self._value(k) for k in ("PlaybackStatus", "Metadata", "Volume", "CanSeek",
                                               "CanGoNext", "CanGoPrevious", "CanPlay", "CanPause")}
        self._emit(PLAYER.name, changed)
        self._emit(ROOT.name, {"Identity": self._value("Identity")})
        # Konum sürekli artar; yalnızca atlama olunca haber verilir (MPRIS kuralı).
        if not old.get("active") or abs(state.get("position_ms", 0) - predicted_ms) > 3000:
            self.bus.emit_signal(None, PATH, PLAYER.name, "Seeked", GLib.Variant("(x)", (self.position_us(),)))

    def art_changed(self, art_id: str):
        if self.state.get("art_id") == art_id:
            self._emit(PLAYER.name, {"Metadata": self._value("Metadata")})

    def _metadata(self) -> dict:
        st = self.state
        md = {"mpris:trackid": GLib.Variant("o", f"/lab/crucible/TalkToAndroid/track/{self.track}"),
              "xesam:title": GLib.Variant("s", st.get("title") or ""),
              "xesam:artist": GLib.Variant("as", [st["artist"]] if st.get("artist") else []),
              "xesam:album": GLib.Variant("s", st.get("album") or "")}
        if st.get("duration_ms"):
            md["mpris:length"] = GLib.Variant("x", int(st["duration_ms"]) * 1000)
        art = st.get("art_id")
        if art:
            path = cache_dir() / "kapaklar" / art
            if path.exists():
                md["mpris:artUrl"] = GLib.Variant("s", path.as_uri())
        return md

    def _value(self, prop: str):
        st, active = self.state, bool(self.state.get("active"))
        values = {
            "CanQuit": ("b", False), "CanRaise": ("b", False), "HasTrackList": ("b", False),
            "Identity": ("s", f"{st.get('player') or 'Telefon'} ({self.device_name})"),
            "DesktopEntry": ("s", "lab.crucible.TalkToAndroid"),
            "SupportedUriSchemes": ("as", []), "SupportedMimeTypes": ("as", []),
            "PlaybackStatus": ("s", "Playing" if st.get("playing") else ("Paused" if active else "Stopped")),
            "Rate": ("d", 1.0), "MinimumRate": ("d", 1.0), "MaximumRate": ("d", 1.0),
            "Metadata": ("a{sv}", self._metadata()),
            "Volume": ("d", (st.get("volume") or 0) / 100),
            "Position": ("x", self.position_us()),
            "CanGoNext": ("b", active), "CanGoPrevious": ("b", active), "CanPlay": ("b", active),
            "CanPause": ("b", active), "CanSeek": ("b", active and bool(st.get("can_seek"))),
            "CanControl": ("b", True),
        }
        sig, v = values[prop]
        return GLib.Variant(sig, v)

    def _emit(self, iface: str, changed: dict):
        self.bus.emit_signal(None, PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                             GLib.Variant("(sa{sv}as)", (iface, changed, [])))

    # ---- D-Bus geri çağrıları -------------------------------------------------

    def _get(self, _bus, _sender, _path, _iface, prop):
        try:
            return self._value(prop)
        except KeyError:
            return None

    def _set(self, _bus, _sender, _path, _iface, prop, value):
        if prop == "Volume":
            self.control(self.device_id, "volume", max(0, min(100, round(value.unpack() * 100))))
        return True

    def _method(self, _bus, _sender, _path, _iface, method, params, invocation):
        if method in ACTIONS:
            self.control(self.device_id, ACTIONS[method], None)
        elif method == "Seek":
            offset_ms = params.unpack()[0] // 1000
            self.control(self.device_id, "seek", max(0, self.position_us() // 1000 + offset_ms))
        elif method == "SetPosition":
            self.control(self.device_id, "seek", max(0, params.unpack()[1] // 1000))
        invocation.return_value(None)


class PhonePlayers:
    """Bağlı telefonların oynatıcılarını telefonun medya durumuna göre açar/kapatır."""

    def __init__(self, control):
        self.control = control
        self.players: dict[str, PhonePlayer] = {}
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            log.warning("D-Bus yok, telefon medyası masaüstüne eklenmeyecek: %s", e.message)
            self.bus = None

    def update(self, device_id: str, device_name: str, state: dict):
        if not self.bus:
            return
        p = self.players.get(device_id)
        if not state.get("active"):
            if p:
                p.close()
                del self.players[device_id]
            return
        if not p:
            p = self.players[device_id] = PhonePlayer(self.bus, device_id, device_name, self.control)
        p.update(state)

    def art(self, device_id: str, art_id: str):
        p = self.players.get(device_id)
        if p:
            p.art_changed(art_id)

    def keep_only(self, device_ids):
        for did in list(self.players):
            if did not in device_ids:
                self.players.pop(did).close()
