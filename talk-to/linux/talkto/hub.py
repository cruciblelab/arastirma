"""Talk To çekirdeği: TLS sunucusu, kimlik doğrulama, oturumlar ve özellikler.

Arayüzden bağımsızdır. Arayüz Hub'ı ayrı bir iş parçacığında çalışan asyncio
döngüsünde çalıştırır (HubThread), komutları submit() ile gönderir ve olayları
emit geri çağrısıyla alır: emit(olay_adı, sözlük).

Olaylar: status, usb, ask, ask_closed, notification, notification_removed,
media, media_art, transfer, clipboard, open_url, connected, disconnected, error,
screenshot, command_run, phone_crash.
"""

import asyncio
import base64
import binascii
import collections
import hashlib
import itertools
import logging
import mimetypes
import os
import re
import secrets
import socket
import ssl
import threading
import time
from pathlib import Path

from . import PROTOCOL_VERSION, __version__, auth, pc
from .config import Config, cache_dir
from .discovery import Announcer
from .identity import Identity
from . import netinfo
from .netinfo import interfaces
from .protocol import CHUNK, ProtocolError, encode_binary, encode_json, read_frame
from .transfers import Incoming
from . import karekod, mirror, phone_setup
from .usb import AdbWatcher

log = logging.getLogger("talkto")

PING_EVERY = 15
READ_TIMEOUT = 50
# Bir yazma bu kadar ilerlemezse karşı taraf okumuyor sayılır ve bağlantı koparılır
# (yavaş Bluetooth'ta ~800 KB'lık kapak ya da 256 KB'lık parça bile birkaç saniye sürer).
WRITE_TIMEOUT = 120
APPROVAL_TIMEOUT = 60
PASSWORD_TIMEOUT = 120
MAX_FAILURES = 5
MAX_FAILURES_LOCAL = 20  # 127.0.0.1 (USB tüneli): vazgeçip yeniden denemek daha sık
FAILURE_WINDOW = 600
MAX_INFLIGHT = 2         # aynı adresten aynı anda süren kimlik doğrulama
MAX_PENDING_ASKS = 3     # aynı anda açık onay penceresi
MAX_INCOMING = 4         # bir telefondan aynı anda gelen (ya da onay bekleyen) aktarım
MAX_UNAUTHENTICATED = 16 # kimliği doğrulanmamış toplam bağlantı
PREAUTH_MAX_JSON = 64 * 1024
# Bilgisayarın desteklediği el sıkışma özellikleri (PROTOKOL.md): pair2 = taahhütlü onay kodu,
# pw2 = PBKDF2'li şifre kanıtı.
FEATURES = ("pair2", "pw2", "qr1")
_PKG = re.compile(r"^[A-Za-z0-9._]{1,200}$")
_ART = re.compile(r"^[0-9a-f]{8,64}$")


def _s(value, limit=4000) -> str:
    return value[:limit] if isinstance(value, str) else ""


def phone_problems(phone: dict, perms: dict, show_notifications: bool = True) -> list[str]:
    """Telefonun bildirdiği durumdan, bildirim ve müziğin neden gelmeyeceğini anlatan uyarılar."""
    out = []
    if phone.get("flavor") == "hafif":
        out.append("Telefondaki Talk To hafif sürüm: bildirimler ve telefonda çalan müzik gelmez. "
                   "Telefonu USB ile tak; Telefonlar sayfasındaki “Tam sürüme yükselt” düğmesi tam sürümü kurar.")
    elif phone.get("notif_access") is False:
        out.append("Telefonda bildirim erişimi kapalı: bildirimler ve telefonda çalan müzik gelmez. "
                   "Telefonda Talk To'yu aç ve “İzin ver”e dokun.")
    elif phone.get("listener") is False:
        out.append("Bildirim erişimi açık ama Android bildirim dinleyicisini başlatmamış. Telefonda Talk To'yu "
                   "bir kez aç; düzelmezse Ayarlar → Bildirim erişimi'nde kapatıp aç ya da telefonu yeniden başlat.")
    if not perms.get("notifications"):
        out.append("Bu telefonun profili bildirimlere izin vermiyor (Telefonlar → Profiller).")
    elif not show_notifications:
        out.append("Bildirimleri gösterme kapalı (Bildirimler sayfası).")
    if not perms.get("media"):
        out.append("Bu telefonun profili medya kontrolüne izin vermiyor (Telefonlar → Profiller).")
    from .usb import version_tuple
    if phone.get("version") and version_tuple(phone["version"]) < version_tuple(__version__):
        out.append(f"Telefondaki Talk To eski ({phone['version']}; bu bilgisayardaki {__version__}). Bazı "
                   "özellikler çalışmayabilir. Telefonu USB ile takınca Telefonlar sayfasından tek tıkla güncellenir.")
    return out


def _int(value, default=0) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


class TransferFailed(Exception):
    pass


class Hub:
    def __init__(self, config: Config, emit=None, identity: Identity | None = None,
                 enable_media=True, enable_discovery=True, ipc_path: Path | None = None):
        self.config = config
        self.identity = identity or Identity(config.dir, f"talkto-{config['name']}")
        self._emit = emit or (lambda event, data: None)
        self.enable_media = enable_media
        self.enable_discovery = enable_discovery
        self.auto_approve = False  # yalnızca test ve --basliksiz --onayla-hepsi
        self.sessions: dict[str, "Session"] = {}
        self.pending: dict[str, asyncio.Future] = {}
        self.failures: dict[str, collections.deque] = {}
        self.inflight: dict[str, int] = {}
        self.unauthenticated = 0
        self.notifications = collections.deque(maxlen=100)
        self.addresses: list[str] = []
        self.error: str | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.server = None
        self.bound = None
        self.announcer = Announcer(self._announce_info)
        self.announcing = False
        self.usb = AdbWatcher(config["port"], lambda snap: self.emit("usb", snap))
        self.mirror = mirror.Mirror()
        self.setting_up: set[str] = set()  # adb ile izinleri verilen telefonlar
        self.media = None
        self.media_state = {"active": False}
        self._tid = itertools.count(1)
        self._tasks: list[asyncio.Task] = []
        self.bt_state = {"available": False, "message": "Bluetooth denetlenmedi"}
        self.ui_screenshot = False  # masaüstü arayüzü ekran görüntüsünü portal ile alır
        self.ipc_path = ipc_path
        self.ipc = None
        self.qr: dict | None = None  # gösterilen karekodun anahtarı ve son geçerlilik anı

    # ---- yaşam döngüsü -------------------------------------------------

    def emit(self, event: str, data: dict | None = None):
        try:
            self._emit(event, data or {})
        except Exception:
            log.exception("olay işleyicisi hata verdi: %s", event)

    async def start(self):
        self.loop = asyncio.get_running_loop()
        if self.enable_media:
            try:
                from .media import Mpris
                self.media = await asyncio.to_thread(Mpris)
            except Exception as e:
                log.info("MPRIS kullanılamıyor: %s", e)
        await self.apply()
        self._tasks = [asyncio.create_task(self._media_loop()), asyncio.create_task(self._net_loop())]
        if self.ipc_path:
            from .ipc import IpcServer
            self.ipc = IpcServer(self, self.ipc_path)
            try:
                await self.ipc.start()
            except OSError as e:
                log.warning("komut satırı soketi açılamadı (%s): %s", self.ipc_path, e)
                self.ipc = None

    async def stop(self):
        for t in self._tasks:
            t.cancel()
        for s in list(self.sessions.values()):
            await s.close()
        if self.server:
            self.server.close()
            self.server = None
        await self.announcer.stop()
        await self.usb.stop()
        self.mirror.stop_all()
        if self.ipc:
            await self.ipc.stop()

    async def apply(self):
        """Ayarlara göre dinleyicileri (yeniden) kurar."""
        wireless, usb, port = self.config["wireless"], self.config["usb"], self.config["port"]
        host = "0.0.0.0" if wireless else ("127.0.0.1" if usb else None)
        want = (host, port) if host else None
        if want != self.bound:
            if self.server:
                self.server.close()  # açık oturumlar sürer; aşağıda gerekirse kapatılır
                self.server = None
            self.bound = None
            self.error = None
            if want:
                try:
                    self.server = await asyncio.start_server(
                        self._on_connection, host, port, ssl=self.identity.server_context(),
                        ssl_handshake_timeout=15, reuse_address=True)
                    self.bound = want
                except OSError as e:
                    self.error = f"{port} portu açılamadı: {e.strerror or e}"
                    log.error(self.error)
                    self.emit("error", {"message": self.error})
        if wireless and self.bound and self.enable_discovery and not self.announcing:
            await self.announcer.start()
            self.announcing = True
        elif (not wireless or not self.bound) and self.announcing:
            await self.announcer.stop()
            self.announcing = False
        if usb:
            await self.usb.start()
        else:
            await self.usb.stop()
        for s in list(self.sessions.values()):
            if ((s.kind == "wifi" and not wireless) or (s.kind == "usb" and not usb)
                    or (s.kind == "bluetooth" and not self.config["bluetooth"])):
                await s.close()
        self.addresses = [i["addr"] for i in await asyncio.to_thread(interfaces)]
        self.emit_status()

    def status(self) -> dict:
        return {
            "name": self.config["name"],
            "fingerprint": self.identity.fingerprint,
            "short_fp": auth.short_fingerprint(self.identity.fingerprint),
            "wireless": self.config["wireless"],
            "usb": self.config["usb"],
            "port": self.config["port"],
            "listening": self.bound is not None,
            "password_set": bool(self.config["password"]),
            "addresses": list(self.addresses),
            "error": self.error,
            "sessions": [dict(s.info(), adb_serial=self._serial_of(s)) for s in self.sessions.values()],
            "trusted": [{"device_id": k, "profile": self.config.profile_of(k)[0],
                         **{f: v[f] for f in ("name", "model", "paired_at")}}
                        for k, v in self.config.trusted().items()],
            "bluetooth": self.config["bluetooth"],
            "bt": dict(self.bt_state),
            "profiles": self.config.profiles(),
            "default_profile": self.config["default_profile"],
            "commands": self.config.commands(),
        }

    def emit_status(self):
        self.emit("status", self.status())

    def _announce_info(self) -> dict:
        return {"app": "talk-to-android", "id": self.config["device_id"], "name": self.config["name"],
                "port": self.config["port"],
                "fp": self.identity.fingerprint, "password": bool(self.config["password"])}

    async def _net_loop(self):
        while True:
            await asyncio.sleep(10)
            addrs = [i["addr"] for i in await asyncio.to_thread(interfaces)]
            if addrs != self.addresses:
                self.addresses = addrs
                self.emit_status()

    async def _on_connection(self, reader, writer):
        peer = writer.get_extra_info("peername") or ("?", 0)
        ip = peer[0]
        kind = "wifi"
        # adb reverse tüneli bağlantıyı bu kullanıcının adb sunucusundan 127.0.0.1'e getirir.
        # USB kapalıysa ya da bağlantıyı başka bir yerel kullanıcının süreci açtıysa "USB"
        # sayılmaz (şifre ve onay kuralları ağdaki gibi uygulanır).
        if ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1") and self.config["usb"]:
            uid = netinfo.loopback_peer_uid(peer[1], (writer.get_extra_info("sockname") or ("", 0))[1])
            if uid is None or uid == os.getuid():
                kind = "usb"
            else:
                log.info("127.0.0.1'den başka kullanıcının (uid %s) bağlantısı: USB sayılmadı", uid)
        if kind == "wifi":
            log.info("ağdan bağlantı geldi: %s", ip)  # TLS sonrası; hiç yoksa telefon ulaşamıyor (ağ/duvar)
        await Session(self, reader, writer, kind, ip).run()

    # ---- onay ve deneme sınırı -------------------------------------------

    async def ask(self, kind: str, data: dict, timeout: float):
        """Kullanıcıya sorar. Cevap: False (ret) ya da doğru bir değer (onayda seçilen profil olabilir)."""
        if self.auto_approve:
            return True
        rid = secrets.token_hex(8)
        fut = self.loop.create_future()
        self.pending[rid] = fut
        self.emit("ask", {"id": rid, "kind": kind, "timeout": timeout, **data})
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return False
        finally:
            self.pending.pop(rid, None)
            self.emit("ask_closed", {"id": rid})

    def blocked(self, ip: str) -> bool:
        q = self.failures.get(ip)
        now = time.monotonic()
        while q and now - q[0] > FAILURE_WINDOW:
            q.popleft()
        limit = MAX_FAILURES_LOCAL if ip in ("127.0.0.1", "::1") else MAX_FAILURES
        return bool(q) and len(q) >= limit

    def record_failure(self, ip: str):
        self.failures.setdefault(ip, collections.deque()).append(time.monotonic())

    # ---- oturum kaydı ---------------------------------------------------

    async def register(self, s: "Session"):
        old = self.sessions.get(s.device_id)
        self.sessions[s.device_id] = s
        if old and old is not s:
            await old.close()
        self.emit("connected", s.info())
        self.emit_status()
        await s.send_profile()
        if self.media_state.get("active") and s.perm("media") and self.config["share_media"]:
            await self._send_media(s, self.media_state)

    def unregister(self, s: "Session"):
        if self.sessions.get(s.device_id) is s:
            del self.sessions[s.device_id]
            self.emit("disconnected", s.info())
            self.emit_status()

    # ---- bilgisayardaki medya → telefon -----------------------------------

    async def _media_loop(self):
        while True:
            await asyncio.sleep(1.0)
            if not self.sessions or not self.media or not self.config["share_media"]:
                continue
            try:
                await self.refresh_media()
            except Exception:
                log.exception("medya yenilenemedi")

    async def refresh_media(self):
        st = await asyncio.to_thread(self.media.state)
        st.pop("_track", None)
        self.media_state = st
        for s in list(self.sessions.values()):
            if s.perm("media"):
                await self._send_media(s, st)

    async def media_off(self, s: "Session"):
        """Paylaşım ya da izin kapandı: telefondaki bilgisayar oynatıcısı donmuş kalmasın."""
        if s.media_key is not None:
            s.media_key = None
            await s.send({"type": "media_state", "active": False})

    async def _send_media(self, s: "Session", st: dict):
        key = {k: v for k, v in st.items() if k != "position_ms"}
        now = time.monotonic()
        if key == s.media_key and now - s.media_sent < 5:
            return
        art_id = st.get("art_id")
        # Telefon yalnızca son kapağı tutar: A→B→A geçişinde A'nın kapağı yeniden gitmeli.
        if art_id and art_id != s.last_art and self.media:
            art = self.media.art(art_id)
            if art:
                await s.send({"type": "media_art", "art_id": art_id, "mime": art[0],
                              "data": base64.b64encode(art[1]).decode()})
                s.last_art = art_id
        await s.send({"type": "media_state", **st})
        s.media_key, s.media_sent = key, now

    # ---- arayüzün çağırdığı komutlar (döngü iş parçacığında) ----------------

    def submit(self, coro):
        """Başka iş parçacığından çağrılır; concurrent.futures.Future döndürür."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def set_option(self, key: str, value):
        self.config.set(key, value)
        if key in ("wireless", "usb", "port"):
            await self.apply()
        else:
            if key == "share_media" and not value:
                for s in list(self.sessions.values()):
                    await self.media_off(s)
            if key == "phone_vibrate":  # telefon titreşim tercihini profil iletisiyle öğrenir
                for s in list(self.sessions.values()):
                    await s.send_profile()
            self.emit_status()

    # ---- karekodla eşleşme --------------------------------------------------

    async def qr_start(self) -> dict:
        """Yeni karekod (eskisi geçersiz olur). Karekod Wi-Fi içindir: Wi-Fi bağlantısı kapalıysa açılır."""
        turned_on = not self.config["wireless"]
        if turned_on:
            await self.set_option("wireless", True)
        elif not self.addresses:
            await self.apply()  # ağ sonradan bağlandıysa adresler henüz okunmamış olabilir
        key = auth.new_qr_key()
        self.qr = {"key": key, "until": time.monotonic() + karekod.SECONDS}
        return {"link": karekod.link(self.addresses, self.config["port"], self.identity.fingerprint, key,
                                     self.config["name"]),
                "hosts": karekod.hosts(self.addresses), "port": self.config["port"], "seconds": karekod.SECONDS,
                "wireless_turned_on": turned_on, "error": self.error,
                "listening": bool(self.bound) and self.bound[0] == "0.0.0.0"}

    def qr_stop(self):
        self.qr = None

    def qr_key(self) -> str | None:
        if self.qr and time.monotonic() < self.qr["until"]:
            return self.qr["key"]
        self.qr = None
        return None

    async def answer(self, rid: str, ok):
        fut = self.pending.get(rid)
        if fut and not fut.done():
            fut.set_result(ok)

    async def disconnect(self, device_id: str, reason: str = "disconnected"):
        s = self.sessions.get(device_id)
        if s:
            # Telefon "bye" görünce kendiliğinden yeniden bağlanmaz (eski sürümler yok sayar).
            await s.send({"type": "bye", "reason": reason})
            await s.close()

    async def forget(self, device_id: str):
        self.config.forget(device_id)
        await self.disconnect(device_id, "forgotten")
        self.emit_status()

    async def send_file(self, device_id: str, path: str) -> dict | None:
        """Gönderir ve bitince son durumu döndürür ('done', 'failed', 'rejected'...)."""
        s = self.sessions.get(device_id)
        if s:
            return await s.send_file(Path(path))
        return None

    async def cancel_transfer(self, device_id: str, direction: str, tid: int):
        s = self.sessions.get(device_id)
        if s:
            await s.cancel_transfer(direction, tid)

    async def media_control(self, device_id: str, action: str, value=None):
        s = self.sessions.get(device_id)
        if s:
            await s.send({"type": "media_control", "action": action, "value": value})

    async def request_phone_info(self, device_id: str):
        """Telefonun sistem bilgilerini yenile (baloncuğa tıklanınca)."""
        s = self.sessions.get(device_id)
        if s:
            await s.send({"type": "phone_info_request"})

    async def call_action(self, device_id: str, key: str, index: int):
        """Aramadaki düğme (Cevapla, Reddet, Kapat): telefondaki uygulamanın kendi düğmesine basılır."""
        s = self.sessions.get(device_id)
        log.info("arama düğmesi %s → %s", index, s.name if s else "telefon bağlı değil")
        if s:
            await s.send({"type": "call_action", "key": key, "action": int(index)})

    async def call_volume(self, device_id: str, up: bool):
        s = self.sessions.get(device_id)
        log.info("görüşme sesi %s → %s", "+" if up else "−", s.name if s else "telefon bağlı değil")
        if s:
            await s.send({"type": "call_volume", "dir": 1 if up else -1})

    async def ring(self, device_id: str, on: bool = True):
        s = self.sessions.get(device_id)
        if s:
            await s.send({"type": "ring" if on else "ring_stop"})

    async def phone_timer(self, device_id: str, seconds: int, label: str = ""):
        """Telefonda zamanlayıcı kurar (seconds=0: iptal)."""
        s = self.sessions.get(device_id)
        if s:
            await s.send({"type": "timer", "seconds": int(seconds), "label": label[:80]} if seconds > 0
                         else {"type": "timer_cancel"})

    async def send_clipboard(self, device_id: str, text: str):
        s = self.sessions.get(device_id)
        if s and text:
            await s.send({"type": "clipboard", "text": text[:1_000_000]})

    async def notify(self, device_id: str, title: str, text: str = ""):
        """Telefonda bildirim gösterir (ör. komut satırından: 'derleme bitti')."""
        s = self.sessions.get(device_id)
        if s:
            await s.send({"type": "notify", "title": title[:200], "text": text[:4000]})

    # ---- profiller ve komutlar ------------------------------------------------

    async def _push_profiles(self, only_profile: str | None = None):
        for s in list(self.sessions.values()):
            if only_profile is None or s.profile_id() == only_profile:
                await s.send_profile()
        self.emit_status()

    async def save_profile(self, pid: str | None, values: dict) -> str:
        pid = self.config.save_profile(pid, values)
        await self._push_profiles(pid)
        return pid

    async def delete_profile(self, pid: str):
        self.config.delete_profile(pid)
        await self._push_profiles()

    async def assign_profile(self, device_id: str, pid: str):
        self.config.assign_profile(device_id, pid)
        s = self.sessions.get(device_id)
        if s:
            await s.send_profile()
        self.emit_status()

    async def save_command(self, cid: str | None, name: str, command: str):
        self.config.save_command(cid, name, command)
        await self._push_profiles()

    async def delete_command(self, cid: str):
        self.config.delete_command(cid)
        await self._push_profiles()

    # ---- telefonun ekranı (scrcpy) -------------------------------------------------

    def _serial_of(self, s) -> str | None:
        """Bağlı oturum USB'deki hangi telefon (kurulum yardımcısı "bağlı" diyebilsin): modeli eşleşen; USB
        oturumunda tek telefon takılıysa o. Wi-Fi'deki başka bir telefon USB'dekiyle karıştırılmaz."""
        ready = {k: d for k, d in self.usb.devices.items() if d.get("state") == "device"}
        fp = (s.phone_info or {}).get("fingerprint")
        for serial, d in ready.items():  # en güvenilir: telefonun bildirdiği yapı parmak izi = adb'nin okuduğu
            if fp and d.get("fingerprint") == fp:
                return serial
        model = (s.model or "").casefold()
        for serial, d in ready.items():  # "Xiaomi 2311DRK48G" ↔ "2311DRK48G"
            if d.get("model") and str(d["model"]).casefold() in model:
                return serial
        return next(iter(ready)) if s.kind == "usb" and len(ready) == 1 else None

    def _adb_serial_for(self, s) -> str | None:
        """USB'deki oturumun adb seri numarası (bkz. _serial_of)."""
        return self._serial_of(s)

    def _mirror_opts(self) -> dict:
        preset = self.config["mirror_preset"]
        return {"preset": preset if preset in mirror.PRESETS else "akici", "audio": bool(self.config["mirror_audio"])}

    async def mirror_device(self, serial: str, title: str | None = None) -> tuple[bool, str]:
        """adb'nin gördüğü telefonun (USB ya da ip:port) ekranını açar."""
        d = self.usb.devices.get(serial, {})
        return await self.mirror.start_checked(serial, f"{title or d.get('model') or serial} · Talk To",
                                               **self._mirror_opts())

    async def mirror_session(self, device_id: str) -> tuple[bool, str]:
        """Bağlı telefonun ekranını açar: USB'de doğrudan, Wi-Fi'de adb'nin ağ bağlantısıyla."""
        s = self.sessions.get(device_id)
        if not s:
            return False, "Telefon bağlı değil"
        if not mirror.available():
            return False, "scrcpy kurulu değil"
        if not self.usb.available():
            return False, "adb kurulu değil (kurulum yardımcısının USB adımından kurulur)"
        if s.kind == "usb":
            serial = self._adb_serial_for(s)
            if not serial:
                return False, "Telefon adb'de görünmüyor; USB hata ayıklamanın açık ve onaylı olduğuna bak"
        elif s.kind == "wifi":
            serial, msg = await mirror.connect_wireless(s.ip)
            if not serial:
                return False, msg
        else:
            return False, "Bluetooth üzerinden ekran açılamaz; USB ya da Wi-Fi gerekir"
        return await self.mirror.start_checked(serial, f"{s.name} · Talk To", **self._mirror_opts())

    async def mirror_prepare_wireless(self, serial: str) -> tuple[bool, str]:
        ok, text = await mirror.enable_wireless(serial)
        if ok:
            # "adb tcpip" telefondaki adbd'yi yeniden başlatır: reverse tüneli düşer, sonraki yoklamada kurulur.
            if serial in self.usb.devices:
                self.usb.devices[serial]["tunnel"] = False
            text += ". USB bağlantısı birkaç saniye kopup kendiliğinden geri gelir."
        return ok, text

    async def refresh_usb(self):
        """Kurulum yardımcısı açıkken düzenli: telefondaki ayarlar (izinler, Xiaomi anahtarları) yeniden okunur."""
        await self.usb.refresh()

    async def connect_phone(self, serial: str) -> tuple[bool, str]:
        """Bilgisayardaki "Bağlan": telefondaki uygulama USB tünelinden bağlanacak şekilde açılır."""
        return await self.usb.connect_phone(serial)

    async def install_phone_app(self, serial: str, replace: bool = False) -> tuple[bool, str]:
        """Kurar ya da günceller; ardından izinler kendiliğinden verilir (yeni sürüm yeni izin isteyebilir,
        kullanıcının "Bilgisayar ayarlasın"a yeniden basmasını beklemeye gerek yok)."""
        ok, text = await self.usb.install_app(serial, replace)
        if not ok:
            return ok, text
        set_ok, summary = await self.phone_setup(serial)
        return True, text if set_ok else f"{text} {summary}"

    async def phone_setup(self, serial: str) -> tuple[bool, str]:
        """Talk To'nun telefondaki izinlerini USB'den verir; bağlı oturuma sonucu da yollar."""
        if serial in self.setting_up:
            return False, "Telefon zaten ayarlanıyor"
        d = self.usb.devices.get(serial)
        if not d or d.get("state") != "device":
            return False, "Telefon USB'de görünmüyor ya da USB hata ayıklama onaylanmadı"
        self.setting_up.add(serial)
        d["setting_up"] = True
        self.usb.on_change(self.usb.snapshot())
        try:
            items = await phone_setup.setup_phone(serial)
        finally:
            self.setting_up.discard(serial)
            d.pop("setting_up", None)
            self.usb.on_change(self.usb.snapshot())
        text = phone_setup.summary(items)
        for s in list(self.sessions.values()):
            if s.kind == "usb" and self._adb_serial_for(s) == serial:
                await s.send({"type": "setup_result", "items": items, "summary": text})
        return not any(i["ok"] is False for i in items), text

    # ---- Bluetooth -------------------------------------------------------------

    async def set_bt_state(self, state: dict):
        self.bt_state = state
        self.emit_status()

    async def accept_socket(self, sock: socket.socket, kind: str, peer: str):
        """Başka yoldan kabul edilmiş bir akış soketi (Bluetooth RFCOMM) üzerinde oturum açar."""
        if kind == "bluetooth" and not self.config["bluetooth"]:
            sock.close()
            return
        sock.setblocking(False)
        reader = asyncio.StreamReader(limit=2 ** 16)
        protocol = asyncio.StreamReaderProtocol(reader)
        try:
            transport, _ = await self.loop.connect_accepted_socket(
                lambda: protocol, sock, ssl=self.identity.server_context(), ssl_handshake_timeout=20)
        except (OSError, ssl.SSLError, asyncio.TimeoutError) as e:
            log.info("%s bağlantısında TLS kurulamadı: %s", kind, e)
            sock.close()
            return
        writer = asyncio.StreamWriter(transport, protocol, reader, self.loop)
        await Session(self, reader, writer, kind, peer).run()


class Session:
    def __init__(self, hub: Hub, reader, writer, kind: str, ip: str):
        self.hub = hub
        self.config = hub.config
        self.reader = reader
        self.writer = writer
        self.kind = kind
        self.ip = ip
        self.device_id = None
        self.name = "?"
        self.model = ""
        self.app = ""
        self.registered = False
        self.closed = False
        self.battery = None
        self.phone_info = None  # telefonun sistem bilgileri (telefon_bilgi.clean)
        self.phone: dict = {}  # telefonun bildirdiği durum (bildirim erişimi, dinleyici, sürüm...)
        self.media = {"active": False}
        self.call_keys: set[str] = set()  # telefonda süren aramaların bildirim anahtarları
        self.media_key = None
        self.media_sent = 0.0
        self.last_art: str | None = None
        self.serial = next(hub._tid)  # bu bağlantıya özgü sayı (aktarım anahtarları için)
        self.offers: dict[int, asyncio.Task] = {}  # onay bekleyen gelen teklifler
        self.icons: dict[str, str] = {}
        self.crash_saved = False
        self.incoming: dict[int, Incoming] = {}
        self.outgoing: dict[int, dict] = {}
        self._progress_at: dict[tuple, float] = {}
        # Ağa yalnızca _write_loop yazar. Okuma döngüsü (ping'e pong, dosya sonucu...) ağın
        # boşalmasını hiç beklemez; yoksa iki taraf aynı anda yazarken ikisi de okumayı
        # bırakır ve bağlantı kalıcı kilitlenir.
        self._outq: collections.deque = collections.deque()
        self._out_ready = asyncio.Event()
        self._out_idle = asyncio.Event()
        self._out_idle.set()
        self._tasks: set[asyncio.Task] = set()

    def info(self) -> dict:
        pid, prof = self.config.profile_of(self.device_id)
        return {"device_id": self.device_id, "name": self.name, "model": self.model,
                "kind": self.kind, "ip": self.ip, "battery": self.battery, "info": self.phone_info,
                "media": self.media, "profile": pid, "profile_name": prof["name"], "phone": self.phone,
                "problems": phone_problems(self.phone, prof, self.config["show_notifications"])}

    # ---- profil -----------------------------------------------------------

    def profile_id(self) -> str:
        return self.config.profile_of(self.device_id)[0]

    def perm(self, name: str) -> bool:
        """Bu telefonun profili bu işe izin veriyor mu? (her çağrıda güncel ayardan okunur)"""
        return bool(self.config.profile_of(self.device_id)[1].get(name))

    async def send_profile(self):
        """Telefon kendisini hangi profille tanıdığımızı ve neye izin verildiğini bilsin."""
        pid, prof = self.config.profile_of(self.device_id)
        await self.send({"type": "profile", "id": pid, "name": prof["name"],
                         "permissions": {k: bool(prof.get(k)) for k in Config.PERMISSIONS},
                         "vibrate": bool(self.config["phone_vibrate"])})
        await self.send({"type": "commands", "items": pc.command_list(self.config.commands(), prof)})
        if not (prof.get("media") and self.config["share_media"]):
            await self.hub.media_off(self)
        if not prof.get("media") and self.media.get("active"):
            # İzin kalktı: telefonun oynatıcısı bilgisayarda (MPRIS) kapansın.
            self.media = {"active": False}
            self.hub.emit("media", {"device_id": self.device_id, "state": self.media})

    # ---- yazma ------------------------------------------------------------

    async def send(self, msg: dict):
        """İletiyi sıraya koyar ve hemen döner (gönderim sırası korunur)."""
        if not self.closed:
            self._enqueue(encode_json(msg), None)

    async def send_chunk(self, tid: int, data: bytes):
        """Dosya parçası: ağa yazılana kadar bekler (gönderen tarafta akış denetimi)."""
        if self.closed:
            raise ConnectionError("bağlantı kapandı")
        fut = asyncio.get_running_loop().create_future()
        self._enqueue(encode_binary(tid, data), fut)
        await fut

    def _enqueue(self, data: bytes, fut):
        self._outq.append((data, fut))
        self._out_idle.clear()
        self._out_ready.set()

    async def _write_loop(self):
        fut = None
        try:
            while True:
                while not self._outq:
                    self._out_idle.set()
                    self._out_ready.clear()
                    await self._out_ready.wait()
                data, fut = self._outq.popleft()
                self.writer.write(data)
                await asyncio.wait_for(self.writer.drain(), WRITE_TIMEOUT)
                if fut is not None and not fut.done():
                    fut.set_result(None)
                fut = None
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            log.info("%s (%s): %d sn yazılamadı, bağlantı koparılıyor", self.name, self.ip, WRITE_TIMEOUT)
            self._abort()
        except (ConnectionError, OSError, ssl.SSLError, RuntimeError) as e:
            log.info("%s (%s): yazma hatası: %s", self.name, self.ip, e)
            self._abort()
        finally:
            if fut is not None and not fut.done():  # yazılmakta olan parça kuyruktan çıkmıştı
                fut.set_exception(ConnectionError("bağlantı kapandı"))
            self._fail_pending()

    def _fail_pending(self):
        while self._outq:
            _, fut = self._outq.popleft()
            if fut is not None and not fut.done():
                fut.set_exception(ConnectionError("bağlantı kapandı"))
        self._out_idle.set()

    def _abort(self):
        """Bağlantıyı hemen kopar (TLS kapanışını beklemeden); okuma döngüsü de böylece biter."""
        transport = getattr(self.writer, "transport", None)
        if transport is not None:
            transport.abort()

    def _spawn(self, coro):
        t = asyncio.create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    # ---- ana döngü --------------------------------------------------------

    async def run(self):
        reason = None
        self._spawn(self._write_loop())
        if self.hub.unauthenticated >= MAX_UNAUTHENTICATED:
            log.info("çok fazla doğrulanmamış bağlantı; %s reddedildi", self.ip)
            await self.close()
            return
        self.hub.unauthenticated += 1
        try:
            try:
                authed = await asyncio.wait_for(self._handshake(), APPROVAL_TIMEOUT + PASSWORD_TIMEOUT + 30)
            finally:
                self.hub.unauthenticated -= 1
            if not authed:
                return
            self.registered = True
            await self.hub.register(self)
            self._spawn(self._pinger())
            while not self.closed:
                kind, payload = await asyncio.wait_for(read_frame(self.reader), READ_TIMEOUT)
                try:
                    if kind == "json":
                        await self._dispatch(payload)
                    else:
                        await self._on_chunk(*payload)
                except (ConnectionError, ProtocolError, asyncio.CancelledError):
                    raise
                except Exception:
                    # Tek bir iletinin hatası (ör. oynatıcının desteklemediği medya komutu, dolu disk)
                    # bütün bağlantıyı koparmasın.
                    log.exception("%s: ileti işlenemedi (%s)", self.name,
                                  payload.get("type") if kind == "json" else "parça")
        except asyncio.IncompleteReadError:
            reason = "karşı taraf kapattı"
        except (ConnectionError, asyncio.TimeoutError, ssl.SSLError, OSError) as e:
            reason = type(e).__name__
        except ProtocolError as e:
            reason = f"protokol hatası: {e}"
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("oturum hatası")
        finally:
            if reason:
                log.info("%s (%s) bağlantısı bitti: %s", self.name, self.ip, reason)
            await self.close()

    async def close(self):
        if self.closed:
            return
        self.closed = True
        # Sıradaki son iletiler (ör. auth_failed nedeni) gitsin; en fazla 2 sn.
        try:
            await asyncio.wait_for(self._out_idle.wait(), 2)
        except asyncio.TimeoutError:
            pass
        for t in list(self._tasks):
            t.cancel()
        self._fail_pending()
        for inc in self.incoming.values():
            inc.abort()
            self._transfer_event("in", inc.tid, inc.name, inc.size, inc.received, "failed", error="bağlantı koptu")
        self.incoming.clear()
        for o in self.outgoing.values():
            for f in ("accept", "result"):
                if o.get(f) and not o[f].done():
                    o[f].set_exception(TransferFailed("bağlantı koptu"))
        try:
            self.writer.close()
        except Exception:
            pass
        # Python 3.10'da TLS kapanışı karşı tarafın close_notify'ını süresiz bekleyebilir; soket
        # açık kalmasın diye kısa süre sonra kesin olarak kopar.
        try:
            asyncio.get_running_loop().call_later(3, self._abort)
        except RuntimeError:
            self._abort()
        if self.registered:
            self.hub.unregister(self)

    async def _pinger(self):
        while True:
            await asyncio.sleep(PING_EVERY)
            await self.send({"type": "ping"})

    # ---- el sıkışma ve kimlik doğrulama -------------------------------------

    async def _read_json(self, timeout) -> dict:
        while True:
            kind, msg = await asyncio.wait_for(
                read_frame(self.reader, max_json=PREAUTH_MAX_JSON, allow_binary=False), timeout)
            if kind == "json" and msg["type"] != "ping":
                return msg

    async def _handshake(self) -> bool:
        hello = await self._read_json(15)
        if hello.get("type") != "hello" or not auth.valid_device_id(hello.get("device_id")):
            raise ProtocolError("ilk ileti geçerli bir 'hello' değil")
        self.device_id = hello["device_id"]
        self.name = _s(hello.get("name"), 64) or "Telefon"
        self.model = _s(hello.get("model"), 64)
        self.app = _s(hello.get("app"), 40)
        features = hello.get("features") if isinstance(hello.get("features"), list) else []
        commit = hello.get("commit") if auth.valid_commit(hello.get("commit")) else None
        fp = self.hub.identity.fingerprint
        await self.send({"type": "hello", "proto": PROTOCOL_VERSION, "device_id": self.config["device_id"],
                         "name": self.config["name"], "platform": "linux", "app": "talk-to-android",
                         "version": __version__, "features": list(FEATURES)})

        trusted = self.config.trusted().get(self.device_id)
        token = hello.get("token")
        if trusted and isinstance(token, str) and auth.equal(auth.token_hash(token), trusted["token_hash"]):
            await self.send({"type": "welcome"})
            return True

        # Buradan sonrası bir deneme sayılır. Aynı adresten aynı anda en fazla 2 deneme;
        # başarıyla bitmeyen her deneme (yanlış şifre, ret, yarıda bırakma) hata olarak sayılır.
        if self.hub.blocked(self.ip) or self.hub.inflight.get(self.ip, 0) >= MAX_INFLIGHT:
            await self.send({"type": "auth_failed", "reason": "too_many_attempts"})
            return False
        self.hub.inflight[self.ip] = self.hub.inflight.get(self.ip, 0) + 1
        ok = False
        try:
            chosen = await self._authenticate(fp, features, commit, qr=hello.get("qr") is True)
            if chosen is False:
                return False
            ok = True
        finally:
            self.hub.inflight[self.ip] -= 1
            if not self.hub.inflight[self.ip]:
                del self.hub.inflight[self.ip]
            if not ok:
                self.hub.record_failure(self.ip)

        token = auth.new_token()
        self.config.trust(self.device_id, self.name, self.model, auth.token_hash(token), chosen)
        await self.send({"type": "welcome", "token": token})
        return True

    async def _authenticate(self, fp: str, features: list, commit: str | None, qr: bool = False):
        """Karekod, şifre ya da onayla kimlik doğrular. False: başarısız; None ya da profil kimliği: başarılı."""
        nonce = auth.new_nonce()
        if qr and "qr1" in features:
            return await self._authenticate_qr(fp, nonce)
        password = self.config["password"]
        if self.kind == "wifi" and password:
            await self.send({"type": "auth_required", "method": "password", "nonce": nonce})
            msg = await self._read_json(PASSWORD_TIMEOUT)
            proof = msg.get("proof") if msg.get("type") == "auth_password" else None
            if "pw2" in features:
                expected = await asyncio.to_thread(auth.password_proof2, password, nonce, fp)
            else:  # eski telefon
                expected = auth.password_proof(password, nonce, fp)
            if self.hub.blocked(self.ip) or not isinstance(proof, str) or not auth.equal(proof, expected):
                await self.send({"type": "auth_failed", "reason": "wrong_password"})
                return False
            self.hub.emit("paired_by_password", {"name": self.name, "model": self.model, "ip": self.ip})
            return None

        if sum(1 for _ in self.hub.pending) >= MAX_PENDING_ASKS:
            await self.send({"type": "auth_failed", "reason": "too_many_attempts"})
            return False
        if commit:
            # Sürüm 2: telefon rastgele değerini ancak nonce'u gördükten sonra açıklar.
            await self.send({"type": "auth_required", "method": "approval", "nonce": nonce, "pair": 2})
            reveal = await self._read_json(30)
            secret = reveal.get("secret") if reveal.get("type") == "pair_reveal" else None
            if not isinstance(secret, str) or not auth.equal(auth.commit_of(secret), commit):
                await self.send({"type": "auth_failed", "reason": "protocol"})
                return False
            code = auth.pairing_code2(nonce, secret, fp, self.device_id)
        else:  # eski telefon
            await self.send({"type": "auth_required", "method": "approval", "nonce": nonce})
            code = auth.pairing_code(nonce, fp, self.device_id)
        # Telefon beklerken bağlantıyı kapatırsa soruyu da kapat.
        watch = asyncio.create_task(read_frame(self.reader, max_json=PREAUTH_MAX_JSON, allow_binary=False))
        ask = asyncio.create_task(self.hub.ask("pair", {
            "name": self.name, "model": self.model, "code": code, "transport": self.kind, "ip": self.ip,
            "profiles": {k: v["name"] for k, v in self.config.profiles().items()},
            "default_profile": self.config.profile_of(self.device_id)[0],
        }, APPROVAL_TIMEOUT))
        done, _ = await asyncio.wait({watch, ask}, return_when=asyncio.FIRST_COMPLETED)
        if watch in done:
            ask.cancel()
            if not watch.cancelled():
                watch.exception()
            return False
        watch.cancel()
        await asyncio.gather(watch, return_exceptions=True)  # okuyucu serbest kalsın
        answer = ask.result()
        if not answer:
            await self.send({"type": "auth_failed", "reason": "rejected"})
            return False
        return answer if isinstance(answer, str) and answer in self.config.profiles() else None

    async def _authenticate_qr(self, fp: str, nonce: str):
        """Telefon ekrandaki karekodu okudu: anahtarı bildiğini kanıtlarsa onay sorulmadan eşleşir
        (şifre de sorulmaz; tek kullanımlık 128 bitlik anahtar şifreden güçlü). Varsayılan profil."""
        key = self.hub.qr_key()
        if not key:
            await self.send({"type": "auth_failed", "reason": "qr_expired"})
            return False
        await self.send({"type": "auth_required", "method": "qr", "nonce": nonce})
        msg = await self._read_json(30)
        proof = msg.get("proof") if msg.get("type") == "auth_qr" else None
        # Bu arada karekod kapatılmış ya da başka telefon kullanmış olabilir: anahtar hâlâ aynı olmalı.
        if (self.hub.blocked(self.ip) or not isinstance(proof, str) or self.hub.qr_key() != key
                or not auth.equal(proof, auth.qr_proof(key, nonce, fp, self.device_id))):
            await self.send({"type": "auth_failed", "reason": "wrong_qr"})
            return False
        self.hub.qr_stop()  # bir kez geçer
        self.hub.emit("paired_by_qr", {"name": self.name, "model": self.model, "ip": self.ip,
                                       "transport": self.kind})
        return None

    # ---- gelen iletiler -----------------------------------------------------

    async def _dispatch(self, msg: dict):
        t = msg["type"]
        hub = self.hub
        if t == "ping":
            await self.send({"type": "pong"})
        elif t == "battery":
            self.battery = {"level": max(0, min(100, _int(msg.get("level"), -1))),
                            "charging": bool(msg.get("charging"))}
            hub.emit_status()
        elif t == "phone_info":
            from . import telefon_bilgi
            self.phone_info = telefon_bilgi.clean(msg)
            hub.emit_status()
        elif t == "phone_status":
            player = msg.get("player")
            self.phone = {"flavor": _s(msg.get("flavor"), 20), "sdk": _int(msg.get("sdk")),
                          "notif_access": bool(msg.get("notif_access")), "listener": bool(msg.get("listener")),
                          "player": _s(player, 100) if isinstance(player, str) else None,
                          "notifications_sent": _int(msg.get("notifications_sent")),
                          "version": _s(msg.get("version"), 40) or None}
            hub.emit_status()
        elif t == "app_icon":
            if self.perm("notifications"):
                self._save_icon(msg)
        elif t == "notification":
            if not (self.config["show_notifications"] and self.perm("notifications")):
                return
            pkg = _s(msg.get("package"), 200)
            n = {"device_id": self.device_id, "device": self.name, "key": _s(msg.get("key"), 300),
                 "package": pkg, "app": _s(msg.get("app"), 100) or pkg, "title": _s(msg.get("title"), 500),
                 "text": _s(msg.get("text"), 4000), "time": time.time(), "icon": self.icons.get(pkg)}
            hub.notifications.appendleft(n)
            hub.emit("notification", n)
        elif t == "call":
            # Arama (WhatsApp, Instagram, telefon): çalıyor ya da sürüyor; düğmeler telefondaki uygulamanınki.
            if not (self.config["show_notifications"] and self.perm("notifications")):
                return
            pkg = _s(msg.get("package"), 200)
            actions = [{"i": _int(a.get("i")), "title": _s(a.get("title"), 40)}
                       for a in (msg.get("actions") or [])[:5] if isinstance(a, dict) and _s(a.get("title"), 40)]
            log.info("arama (%s): %s, %s, düğmeler %s", self.name, _s(msg.get("app"), 100), msg.get("state"),
                     [a["title"] for a in actions])
            self.call_keys.add(_s(msg.get("key"), 300))
            hub.emit("call", {"device_id": self.device_id, "device": self.name, "key": _s(msg.get("key"), 300),
                              "package": pkg, "app": _s(msg.get("app"), 100) or pkg,
                              "caller": _s(msg.get("caller"), 200), "text": _s(msg.get("text"), 300),
                              "state": "ringing" if msg.get("state") == "ringing" else "ongoing",
                              "actions": actions, "icon": self.icons.get(pkg)})
        elif t == "call_result":
            # Telefon düğmeye bastı mı, görüşme sesi değişti mi: gerçek telefonda sorunu görebilmek için.
            def num(v):
                return v if isinstance(v, int) and not isinstance(v, bool) else None
            r = {"device_id": self.device_id, "kind": "volume" if msg.get("kind") == "volume" else "action",
                 "title": _s(msg.get("title"), 60) or None, "error": _s(msg.get("error"), 300) or None,
                 "before": num(msg.get("before")), "after": num(msg.get("after")), "max": num(msg.get("max")),
                 "mode": _s(msg.get("mode"), 40) or None}
            if r["kind"] == "volume":
                log.info("görüşme sesi (%s): %s → %s / %s, kip: %s%s", self.name, r["before"], r["after"], r["max"],
                         r["mode"], f", hata: {r['error']}" if r["error"] else "")
            else:
                log.info("arama düğmesi (%s): %s → %s", self.name, r["title"], r["error"] or "basıldı")
            hub.emit("call_result", r)
        elif t == "call_ended":
            self.call_keys.discard(_s(msg.get("key"), 300))
            hub.emit("call_ended", {"device_id": self.device_id, "key": _s(msg.get("key"), 300)})
        elif t == "notification_removed":
            key = _s(msg.get("key"), 300)
            if key in self.call_keys:
                # Eski telefon uygulaması (0.13.0 ve öncesi) arama biterken düğmesiz güncellenen bildirimin
                # kalkmasını "arama bitti" diye değil "bildirim kalktı" diye gönderiyordu.
                self.call_keys.discard(key)
                hub.emit("call_ended", {"device_id": self.device_id, "key": key})
            else:
                hub.emit("notification_removed", {"device_id": self.device_id, "key": key})
        elif t == "media_state":
            self.media = self._clean_media(msg) if self.perm("media") else {"active": False}
            hub.emit("media", {"device_id": self.device_id, "state": self.media})
        elif t == "media_art":
            self._save_art(msg)
        elif t == "crash_report" and not self.crash_saved:
            self.crash_saved = True  # bağlantı başına bir rapor
            self._save_crash(_s(msg.get("text"), 20000))
        elif t == "media_control":
            if hub.media and self.config["share_media"] and self.perm("media"):
                action = _s(msg.get("action"), 20)
                value = msg.get("value")
                await asyncio.to_thread(hub.media.control, action, value if isinstance(value, (int, float)) else None)
                self.media_key = None
                await asyncio.sleep(0.15)
                await hub.refresh_media()
        elif t == "file_offer":
            self._spawn(self._on_offer(msg))
        elif t in ("file_accept", "file_reject"):
            o = self.outgoing.get(_int(msg.get("transfer_id")))
            if o and not o["accept"].done():
                o["accept"].set_result(t == "file_accept")
                o["reason"] = _s(msg.get("reason"), 200)
        elif t == "file_result":
            o = self.outgoing.get(_int(msg.get("transfer_id")))
            if o and o.get("result") and not o["result"].done():
                o["result"].set_result(msg)
        elif t == "file_done":
            await self._on_file_done(msg)
        elif t == "file_cancel":
            tid = _int(msg.get("transfer_id"))
            # İki uç da aktarımları 1'den numaralar; "direction" alıcının (bilgisayarın) gözünden
            # hangi yöndekinin iptal edildiğini söyler. Eski telefonlar göndermez: iki yöne de bak.
            direction = msg.get("direction")
            if direction != "out" and tid in self.offers:
                self.offers.pop(tid).cancel()
            if direction != "out" and tid in self.incoming:
                inc = self.incoming.pop(tid)
                inc.abort()
                self._transfer_event("in", tid, inc.name, inc.size, inc.received, "cancelled")
            o = self.outgoing.get(tid) if direction != "in" else None
            if o:
                o["cancelled"] = True
                for f in ("accept", "result"):
                    if o.get(f) and not o[f].done():
                        o[f].set_exception(TransferFailed("telefon iptal etti"))
        elif t == "clipboard":
            text = _s(msg.get("text"), 1_000_000)
            if text and self.perm("clipboard"):
                hub.emit("clipboard", {"device_id": self.device_id, "device": self.name, "text": text})
        elif t == "open_url":
            url = _s(msg.get("url"), 8000)
            if re.match(r"^https?://", url, re.I) and self.perm("open_url"):
                hub.emit("open_url", {"device_id": self.device_id, "device": self.name, "url": url})
        elif t == "run_command":
            self._spawn(self._run_command(_s(msg.get("id"), 80)))
        elif t == "sysinfo_request":
            await self.send({"type": "sysinfo", **await asyncio.to_thread(pc.sysinfo)})
        elif t == "pc_volume":
            if self.perm("media"):
                value = msg.get("value")
                await asyncio.to_thread(pc.volume_set, _int(value) if value is not None else None,
                                        bool(msg.get("toggle_mute")))
                await self.send({"type": "sysinfo", **await asyncio.to_thread(pc.sysinfo)})
        elif t == "setup_request":
            # Telefondaki "Bilgisayar ayarlasın": yalnızca USB'de (adb gerekir).
            serial = hub._adb_serial_for(self) if self.kind == "usb" and hub.usb.available() else None
            if not serial:
                await self.send({"type": "setup_result", "items": [], "summary":
                                 "Bunun için telefon USB ile bağlı ve USB hata ayıklama açık olmalı."})
            else:
                hub.emit("phone_setup", {"device_id": self.device_id, "device": self.name})
                self._spawn(hub.phone_setup(serial))
        elif t == "screenshot_request":
            if not self.perm("screenshot"):
                await self.send({"type": "command_result", "id": "ekran", "ok": False,
                                 "output": "Bu telefonun profili ekran görüntüsüne izin vermiyor."})
            elif hub.ui_screenshot:
                hub.emit("screenshot", {"device_id": self.device_id})
            else:
                self._spawn(self._screenshot_headless())
        # Bilinmeyen türler sessizce yok sayılır (ileri uyumluluk).

    async def _run_command(self, cid: str):
        _pid, prof = self.config.profile_of(self.device_id)
        allowed = {c["id"]: c["name"] for c in pc.command_list(self.config.commands(), prof)}
        name = allowed.get(cid, cid)
        if cid in allowed:  # izinsiz ya da bilinmeyen komut "çalıştırıldı" diye duyurulmaz
            self.hub.emit("command_run", {"device_id": self.device_id, "device": self.name, "id": cid, "name": name})
        res = await pc.run_command(cid, self.config.commands(), prof)
        await self.send({"type": "command_result", "id": cid, "name": name, **res})

    async def _screenshot_headless(self):
        path = cache_dir() / f"ekran-{time.strftime('%Y%m%d-%H%M%S')}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        if await asyncio.to_thread(pc.screenshot_with_tools, path):
            self.hub.emit("screenshot_taken", {"device_id": self.device_id})
            try:
                await self.send_file(path)
            finally:
                path.unlink(missing_ok=True)
        else:
            await self.send({"type": "command_result", "id": "ekran", "ok": False,
                             "output": "Ekran görüntüsü alınamadı (gnome-screenshot, spectacle ya da grim yok)."})

    @staticmethod
    def _clean_media(msg: dict) -> dict:
        if not msg.get("active"):
            return {"active": False}
        vol = msg.get("volume")
        art = msg.get("art_id")
        return {"active": True, "player": _s(msg.get("player"), 100), "title": _s(msg.get("title"), 300),
                "artist": _s(msg.get("artist"), 300), "album": _s(msg.get("album"), 300),
                "playing": bool(msg.get("playing")), "position_ms": max(0, _int(msg.get("position_ms"))),
                "duration_ms": max(0, _int(msg.get("duration_ms"))),
                "volume": max(0, min(100, _int(vol))) if vol is not None else None,
                "can_seek": bool(msg.get("can_seek")),
                "art_id": art if isinstance(art, str) and _ART.match(art) else None,
                "received_at": time.monotonic()}

    def _save_crash(self, text: str):
        """Telefondaki uygulama son çalışmasında çöktüyse raporunu kaydeder (nedeni bulunabilsin)."""
        if not text:
            return
        safe = re.sub(r"[^A-Za-z0-9_-]", "_", self.device_id)[:40]
        p = cache_dir() / f"telefon-cokme-{safe}-{time.strftime('%Y%m%d-%H%M%S')}.txt"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        except OSError as e:
            log.warning("telefonun çökme raporu kaydedilemedi: %s", e)
            return
        log.warning("%s: telefondaki uygulama son çalışmasında çökmüş; rapor %s", self.name, p)
        self.hub.emit("phone_crash", {"device_id": self.device_id, "device": self.name, "path": str(p)})

    def _decode_image(self, msg, limit) -> bytes | None:
        data = msg.get("data")
        if not isinstance(data, str) or len(data) > limit * 4 // 3 + 4:
            return None
        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            return None
        return raw if raw[:4] == b"\x89PNG" or raw[:3] == b"\xff\xd8\xff" else None

    def _save_icon(self, msg):
        pkg = msg.get("package")
        if not isinstance(pkg, str) or not _PKG.match(pkg):
            return
        raw = self._decode_image(msg, 200 * 1024)
        if raw is None:
            return
        d = cache_dir() / "simgeler"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{pkg}.png"
        if not p.exists() and len(self.icons) >= 300:
            return  # bir telefon sınırsız simge yazarak diski dolduramasın
        p.write_bytes(raw)
        self.icons[pkg] = str(p)

    def _save_art(self, msg):
        art_id = msg.get("art_id")
        if not isinstance(art_id, str) or not _ART.match(art_id):
            return
        raw = self._decode_image(msg, 1024 * 1024)
        if raw is None:
            return
        d = cache_dir() / "kapaklar"
        d.mkdir(parents=True, exist_ok=True)
        old = sorted(d.glob("*"), key=lambda p: p.stat().st_mtime)
        for p in old[:-20]:
            p.unlink(missing_ok=True)
        p = d / art_id
        p.write_bytes(raw)
        self.hub.emit("media_art", {"device_id": self.device_id, "art_id": art_id, "path": str(p)})

    # ---- dosya aktarımı -----------------------------------------------------

    def _transfer_event(self, direction, tid, name, size, done, state, **extra) -> dict:
        # Telefon her bağlantıda 1'den numaralar: arayüzde eski bağlantının satırıyla çakışmasın.
        ev = {"device_id": self.device_id, "device": self.name, "direction": direction,
              "tid": tid, "key": f"{self.device_id}:{self.serial}:{direction}:{tid}",
              "name": name, "size": size, "done": done, "state": state, **extra}
        self.hub.emit("transfer", ev)
        return ev

    def _progress(self, direction, tid, name, size, done):
        now = time.monotonic()
        if now - self._progress_at.get((direction, tid), 0) >= 0.2:
            self._progress_at[(direction, tid)] = now
            self._transfer_event(direction, tid, name, size, done, "active")

    async def _on_offer(self, msg):
        tid = _int(msg.get("transfer_id"))
        size = _int(msg.get("size"), -1)
        name = _s(msg.get("name"), 1000)
        if not 0 < tid < 2 ** 32 or tid in self.incoming or size < 0:
            await self.send({"type": "file_reject", "transfer_id": tid, "reason": "geçersiz teklif"})
            return
        if not self.perm("files"):
            await self.send({"type": "file_reject", "transfer_id": tid,
                             "reason": "bu telefonun profili dosya göndermeye izin vermiyor"})
            return
        if len(self.incoming) + len(self.offers) >= MAX_INCOMING:
            await self.send({"type": "file_reject", "transfer_id": tid,
                             "reason": "bilgisayar meşgul (çok fazla aktarım); birazdan tekrar dene"})
            return
        if not self.config["auto_accept"]:
            self._transfer_event("in", tid, name, size, 0, "waiting")
            # Telefon vazgeçerse (file_cancel) ya da bağlantı koparsa bu görev iptal edilir; soru penceresi
            # ask()'in finally'siyle kapanır ve sahipsiz .part oluşmaz.
            self.offers[tid] = asyncio.current_task()
            try:
                ok = await self.hub.ask("file", {"device": self.name, "name": name, "size": size}, 120)
            except asyncio.CancelledError:
                self._transfer_event("in", tid, name, size, 0, "failed" if self.closed else "cancelled",
                                     error="bağlantı koptu" if self.closed else "telefon vazgeçti")
                raise
            finally:
                self.offers.pop(tid, None)
            if not ok:
                self._transfer_event("in", tid, name, size, 0, "rejected")
                await self.send({"type": "file_reject", "transfer_id": tid, "reason": "reddedildi"})
                return
        try:
            folder = self.config.profile_of(self.device_id)[1].get("receive_dir") or self.config["receive_dir"]
            inc = Incoming(tid, name, size, Path(folder).expanduser())
        except (OSError, ValueError) as e:
            self._transfer_event("in", tid, name, size, 0, "failed", error=str(e))
            await self.send({"type": "file_reject", "transfer_id": tid, "reason": str(e)})
            return
        self.incoming[tid] = inc
        self._transfer_event("in", tid, inc.name, size, 0, "active")
        await self.send({"type": "file_accept", "transfer_id": tid})

    async def _on_chunk(self, tid: int, data: bytes):
        inc = self.incoming.get(tid)
        if not inc:
            return  # iptal edilmiş aktarımın kalan parçaları
        try:
            inc.write(data)
        except (OSError, ValueError) as e:
            self.incoming.pop(tid, None)
            inc.abort()
            self._transfer_event("in", tid, inc.name, inc.size, inc.received, "failed", error=str(e))
            await self.send({"type": "file_cancel", "transfer_id": tid, "direction": "out", "reason": str(e)})
            return
        self._progress("in", tid, inc.name, inc.size, inc.received)

    async def _on_file_done(self, msg):
        tid = _int(msg.get("transfer_id"))
        inc = self.incoming.pop(tid, None)
        if not inc:
            return
        try:
            path = inc.finish(_s(msg.get("sha256"), 64))
        except (OSError, ValueError) as e:
            self._transfer_event("in", tid, inc.name, inc.size, inc.received, "failed", error=str(e))
            await self.send({"type": "file_result", "transfer_id": tid, "ok": False, "reason": str(e)})
            return
        self._transfer_event("in", tid, path.name, inc.size, inc.size, "done", path=str(path))
        await self.send({"type": "file_result", "transfer_id": tid, "ok": True})

    async def send_file(self, path: Path) -> dict:
        tid = next(self.hub._tid)
        # UTF-8 olmayan dosya adı (eski arşivlerden) JSON'a yazılamaz: bozuk baytlar � olur.
        name = path.name.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        try:
            size = path.stat().st_size
        except OSError as e:
            return self._transfer_event("out", tid, name, 0, 0, "failed", error=str(e))
        o = {"accept": self.hub.loop.create_future(), "result": self.hub.loop.create_future(),
             "cancelled": False, "reason": ""}
        self.outgoing[tid] = o
        sent = 0
        final: dict = {}
        self._transfer_event("out", tid, name, size, 0, "waiting")
        try:
            await self.send({"type": "file_offer", "transfer_id": tid, "name": name, "size": size,
                             "mime": mimetypes.guess_type(name)[0] or "application/octet-stream"})
            if not await asyncio.wait_for(o["accept"], 120):
                final = self._transfer_event("out", tid, name, size, 0, "rejected", error=o["reason"])
                return final
            sha = hashlib.sha256()
            with open(path, "rb") as f:
                while True:
                    if o["cancelled"] or self.closed:
                        raise TransferFailed("iptal edildi")
                    data = await asyncio.to_thread(f.read, CHUNK)
                    if not data:
                        break
                    sha.update(data)
                    await self.send_chunk(tid, data)
                    sent += len(data)
                    self._progress("out", tid, name, size, sent)
            if sent != size:
                raise TransferFailed("dosya gönderilirken değişti")
            await self.send({"type": "file_done", "transfer_id": tid, "sha256": sha.hexdigest()})
            res = await asyncio.wait_for(o["result"], 60)
            if not res.get("ok"):
                raise TransferFailed(_s(res.get("reason"), 200) or "telefon dosyayı doğrulayamadı")
            final = self._transfer_event("out", tid, name, size, size, "done")
        except asyncio.TimeoutError:
            final = self._transfer_event("out", tid, name, size, sent, "failed", error="zaman aşımı")
            await self._cancel_out(tid, o)
        except (TransferFailed, OSError, ConnectionError, ValueError) as e:
            state = "cancelled" if o["cancelled"] else "failed"
            final = self._transfer_event("out", tid, name, size, sent, state, error=str(e))
            await self._cancel_out(tid, o)
        finally:
            self.outgoing.pop(tid, None)
            for f in (o["accept"], o["result"]):
                if f.done() and not f.cancelled():
                    f.exception()  # "hiç okunmadı" uyarısını sustur
        return final

    async def _cancel_out(self, tid, o):
        if not self.closed:
            try:
                await self.send({"type": "file_cancel", "transfer_id": tid, "direction": "in"})
            except (ConnectionError, OSError):
                pass

    async def cancel_transfer(self, direction: str, tid: int):
        if direction == "in" and tid in self.incoming:
            inc = self.incoming.pop(tid)
            inc.abort()
            self._transfer_event("in", tid, inc.name, inc.size, inc.received, "cancelled")
            await self.send({"type": "file_cancel", "transfer_id": tid, "direction": "out"})
        elif direction == "out" and tid in self.outgoing:
            o = self.outgoing[tid]
            o["cancelled"] = True
            for f in ("accept", "result"):
                if not o[f].done():
                    o[f].set_exception(TransferFailed("iptal edildi"))


class HubThread:
    """Hub'ı kendi asyncio döngüsüyle arka plan iş parçacığında çalıştırır."""

    def __init__(self, hub: Hub):
        self.hub = hub
        self.loop = asyncio.new_event_loop()
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="talkto-hub", daemon=True)

    def start(self):
        self.thread.start()
        self.ready.wait(10)

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.hub.start())
        self.ready.set()
        self.loop.run_forever()

    def stop(self):
        if self.loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self.hub.stop(), self.loop)
            try:
                fut.result(5)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
