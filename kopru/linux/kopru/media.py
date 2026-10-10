"""Bilgisayarda çalan medya (Spotify, tarayıcıda YouTube, VLC...) MPRIS D-Bus
arayüzünden okunur ve kontrol edilir. Çağrılar senkron Gio D-Bus çağrılarıdır;
hub bunları ayrı iş parçacığında (asyncio.to_thread) çalıştırır."""

import hashlib
import logging
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("kopru.medya")

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
IFACE_ROOT = "org.mpris.MediaPlayer2"
IFACE_PLAYER = "org.mpris.MediaPlayer2.Player"
MAX_ART = 600 * 1024


class Mpris:
    def __init__(self):
        from gi.repository import Gio, GLib  # yalnızca masaüstünde gerekir
        self.Gio, self.GLib = Gio, GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.current = None
        self._art_cache: dict[str, tuple[str, str, bytes] | None] = {}

    def _call(self, name, iface, method, args=None, timeout=1500):
        return self.bus.call_sync(name, PATH, iface, method, args, None,
                                  self.Gio.DBusCallFlags.NONE, timeout, None)

    def _get_all(self, name, iface) -> dict:
        res = self.bus.call_sync(name, PATH, "org.freedesktop.DBus.Properties", "GetAll",
                                 self.GLib.Variant("(s)", (iface,)), None,
                                 self.Gio.DBusCallFlags.NONE, 1500, None)
        return res.unpack()[0]

    def players(self) -> list[str]:
        res = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                 "ListNames", None, None, self.Gio.DBusCallFlags.NONE, 1500, None)
        return sorted(n for n in res.unpack()[0] if n.startswith(PREFIX))

    def state(self) -> dict:
        """Etkin oynatıcının durumu: önce çalan, yoksa son seçilen, yoksa ilk."""
        try:
            names = self.players()
        except Exception as e:
            log.debug("D-Bus erişilemedi: %s", e)
            return {"active": False}
        props = {}
        for n in names:
            try:
                props[n] = self._get_all(n, IFACE_PLAYER)
            except Exception:
                pass
        if not props:
            self.current = None
            return {"active": False}
        playing = [n for n, p in props.items() if p.get("PlaybackStatus") == "Playing"]
        if playing:
            self.current = self.current if self.current in playing else playing[0]
        elif self.current not in props:
            self.current = next(iter(props))
        p = props[self.current]
        md = p.get("Metadata", {}) or {}
        try:
            identity = self._get_all(self.current, IFACE_ROOT).get("Identity") or self.current[len(PREFIX):]
        except Exception:
            identity = self.current[len(PREFIX):]
        artist = md.get("xesam:artist") or []
        art = self._art(md.get("mpris:artUrl") or "")
        volume = p.get("Volume")
        return {
            "active": True,
            "player": identity,
            "title": md.get("xesam:title") or "",
            "artist": ", ".join(artist) if isinstance(artist, list) else str(artist),
            "album": md.get("xesam:album") or "",
            "playing": p.get("PlaybackStatus") == "Playing",
            "position_ms": int(p.get("Position", 0) or 0) // 1000,
            "duration_ms": int(md.get("mpris:length", 0) or 0) // 1000,
            "volume": round(volume * 100) if isinstance(volume, float) else None,
            "can_seek": bool(p.get("CanSeek", False)),
            "art_id": art[0] if art else None,
            "_track": md.get("mpris:trackid"),
        }

    def art(self, art_id: str):
        """(mime, bytes) — state() içinde önbelleğe alınmış kapak."""
        for v in self._art_cache.values():
            if v and v[0] == art_id:
                return v[1], v[2]
        return None

    def _art(self, url: str):
        if not url:
            return None
        if url in self._art_cache:
            return self._art_cache[url]
        data = None
        try:
            if url.startswith("file://"):
                p = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path))
                if p.stat().st_size <= MAX_ART:
                    data = p.read_bytes()
            elif url.startswith(("https://", "http://")):
                with urllib.request.urlopen(url, timeout=4) as r:
                    data = r.read(MAX_ART + 1)
                    if len(data) > MAX_ART:
                        data = None
        except Exception as e:
            log.debug("kapak alınamadı %s: %s", url, e)
        entry = None
        if data:
            mime = "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
            entry = (hashlib.sha256(data).hexdigest()[:16], mime, data)
        if len(self._art_cache) > 32:
            self._art_cache.clear()
        self._art_cache[url] = entry
        return entry

    def control(self, action: str, value=None):
        if not self.current:
            return
        name = self.current
        GLib = self.GLib
        if action in ("play_pause", "play", "pause", "next", "previous"):
            method = {"play_pause": "PlayPause", "play": "Play", "pause": "Pause",
                      "next": "Next", "previous": "Previous"}[action]
            self._call(name, IFACE_PLAYER, method)
        elif action == "seek" and isinstance(value, (int, float)):
            st = self.state()
            if st.get("active") and st.get("_track"):
                self._call(name, IFACE_PLAYER, "SetPosition",
                           GLib.Variant("(ox)", (st["_track"], int(max(0, value)) * 1000)))
        elif action == "volume" and isinstance(value, (int, float)):
            self._call(name, "org.freedesktop.DBus.Properties", "Set",
                       GLib.Variant("(ssv)", (IFACE_PLAYER, "Volume",
                                              GLib.Variant("d", max(0.0, min(1.0, value / 100))))))
