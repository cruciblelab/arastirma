"""Talk To Android çekirdeği: TLS sunucusu, kimlik doğrulama, oturumlar ve özellikler.

Arayüzden bağımsızdır. Arayüz Hub'ı ayrı bir iş parçacığında çalışan asyncio
döngüsünde çalıştırır (HubThread), komutları submit() ile gönderir ve olayları
emit geri çağrısıyla alır: emit(olay_adı, sözlük).

Olaylar: status, usb, ask, ask_closed, notification, notification_removed,
media, media_art, transfer, clipboard, open_url, connected, disconnected, error,
screenshot, command_run.
"""

import asyncio
import base64
import binascii
import collections
import hashlib
import itertools
import logging
import mimetypes
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
from .netinfo import interfaces
from .protocol import CHUNK, ProtocolError, encode_binary, encode_json, read_frame
from .transfers import Incoming
from .usb import AdbWatcher

log = logging.getLogger("talkto")

PING_EVERY = 15
READ_TIMEOUT = 50
APPROVAL_TIMEOUT = 60
PASSWORD_TIMEOUT = 120
MAX_FAILURES = 5
FAILURE_WINDOW = 600
_PKG = re.compile(r"^[A-Za-z0-9._]{1,200}$")
_ART = re.compile(r"^[0-9a-f]{8,64}$")


def _s(value, limit=4000) -> str:
    return value[:limit] if isinstance(value, str) else ""


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
        self.notifications = collections.deque(maxlen=100)
        self.addresses: list[str] = []
        self.error: str | None = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self.server = None
        self.bound = None
        self.announcer = Announcer(self._announce_info)
        self.announcing = False
        self.usb = AdbWatcher(config["port"], lambda snap: self.emit("usb", snap))
        self.media = None
        self.media_state = {"active": False}
        self._tid = itertools.count(1)
        self._tasks: list[asyncio.Task] = []
        self.bt_state = {"available": False, "message": "Bluetooth denetlenmedi"}
        self.ui_screenshot = False  # masaüstü arayüzü ekran görüntüsünü portal ile alır
        self.ipc_path = ipc_path
        self.ipc = None

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
            "sessions": [s.info() for s in self.sessions.values()],
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
        kind = "usb" if ip in ("127.0.0.1", "::1") else "wifi"
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
        return bool(q) and len(q) >= MAX_FAILURES

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
        if self.media_state.get("active") and s.perm("media"):
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

    async def _send_media(self, s: "Session", st: dict):
        key = {k: v for k, v in st.items() if k != "position_ms"}
        now = time.monotonic()
        if key == s.media_key and now - s.media_sent < 5:
            return
        art_id = st.get("art_id")
        if art_id and art_id not in s.art_sent and self.media:
            art = self.media.art(art_id)
            if art:
                await s.send({"type": "media_art", "art_id": art_id, "mime": art[0],
                              "data": base64.b64encode(art[1]).decode()})
                s.art_sent.add(art_id)
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
            self.emit_status()

    async def answer(self, rid: str, ok):
        fut = self.pending.get(rid)
        if fut and not fut.done():
            fut.set_result(ok)

    async def disconnect(self, device_id: str):
        s = self.sessions.get(device_id)
        if s:
            await s.close()

    async def forget(self, device_id: str):
        self.config.forget(device_id)
        await self.disconnect(device_id)
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

    async def ring(self, device_id: str, on: bool = True):
        s = self.sessions.get(device_id)
        if s:
            await s.send({"type": "ring" if on else "ring_stop"})

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
        self.media = {"active": False}
        self.media_key = None
        self.media_sent = 0.0
        self.art_sent: set[str] = set()
        self.icons: dict[str, str] = {}
        self.incoming: dict[int, Incoming] = {}
        self.outgoing: dict[int, dict] = {}
        self._progress_at: dict[tuple, float] = {}
        self._wlock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()

    def info(self) -> dict:
        pid, prof = self.config.profile_of(self.device_id)
        return {"device_id": self.device_id, "name": self.name, "model": self.model,
                "kind": self.kind, "ip": self.ip, "battery": self.battery,
                "media": self.media, "profile": pid, "profile_name": prof["name"]}

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
                         "permissions": {k: bool(prof.get(k)) for k in Config.PERMISSIONS}})
        await self.send({"type": "commands", "items": pc.command_list(self.config.commands(), prof)})

    # ---- yazma ------------------------------------------------------------

    async def send(self, msg: dict):
        if self.closed:
            return
        async with self._wlock:
            self.writer.write(encode_json(msg))
            await self.writer.drain()

    async def send_chunk(self, tid: int, data: bytes):
        async with self._wlock:
            if self.closed:
                raise ConnectionError("bağlantı kapandı")
            self.writer.write(encode_binary(tid, data))
            await self.writer.drain()

    def _spawn(self, coro):
        t = asyncio.create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    # ---- ana döngü --------------------------------------------------------

    async def run(self):
        reason = None
        try:
            if not await asyncio.wait_for(self._handshake(), APPROVAL_TIMEOUT + PASSWORD_TIMEOUT + 30):
                return
            self.registered = True
            await self.hub.register(self)
            self._spawn(self._pinger())
            while not self.closed:
                kind, payload = await asyncio.wait_for(read_frame(self.reader), READ_TIMEOUT)
                if kind == "json":
                    await self._dispatch(payload)
                else:
                    await self._on_chunk(*payload)
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
        for t in list(self._tasks):
            t.cancel()
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
        if self.registered:
            self.hub.unregister(self)

    async def _pinger(self):
        while True:
            await asyncio.sleep(PING_EVERY)
            await self.send({"type": "ping"})

    # ---- el sıkışma ve kimlik doğrulama -------------------------------------

    async def _read_json(self, timeout) -> dict:
        while True:
            kind, msg = await asyncio.wait_for(read_frame(self.reader), timeout)
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
        fp = self.hub.identity.fingerprint
        await self.send({"type": "hello", "proto": PROTOCOL_VERSION, "device_id": self.config["device_id"],
                         "name": self.config["name"], "platform": "linux", "app": "talk-to-android",
                         "version": __version__})

        trusted = self.config.trusted().get(self.device_id)
        token = hello.get("token")
        if trusted and isinstance(token, str) and auth.equal(auth.token_hash(token), trusted["token_hash"]):
            await self.send({"type": "welcome"})
            return True

        if self.hub.blocked(self.ip):
            await self.send({"type": "auth_failed", "reason": "too_many_attempts"})
            return False

        nonce = auth.new_nonce()
        password = self.config["password"]
        chosen = None
        if self.kind == "wifi" and password:
            await self.send({"type": "auth_required", "method": "password", "nonce": nonce})
            msg = await self._read_json(PASSWORD_TIMEOUT)
            proof = msg.get("proof") if msg.get("type") == "auth_password" else None
            if not isinstance(proof, str) or not auth.equal(proof, auth.password_proof(password, nonce, fp)):
                self.hub.record_failure(self.ip)
                await self.send({"type": "auth_failed", "reason": "wrong_password"})
                return False
        else:
            code = auth.pairing_code(nonce, fp, self.device_id)
            await self.send({"type": "auth_required", "method": "approval", "nonce": nonce})
            # Telefon beklerken bağlantıyı kapatırsa soruyu da kapat.
            watch = asyncio.create_task(read_frame(self.reader))
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
                self.hub.record_failure(self.ip)
                await self.send({"type": "auth_failed", "reason": "rejected"})
                return False
            if isinstance(answer, str) and answer in self.config.profiles():
                chosen = answer

        token = auth.new_token()
        self.config.trust(self.device_id, self.name, self.model, auth.token_hash(token), chosen)
        await self.send({"type": "welcome", "token": token})
        return True

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
        elif t == "app_icon":
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
        elif t == "notification_removed":
            hub.emit("notification_removed", {"device_id": self.device_id, "key": _s(msg.get("key"), 300)})
        elif t == "media_state":
            self.media = self._clean_media(msg) if self.perm("media") else {"active": False}
            hub.emit("media", {"device_id": self.device_id, "state": self.media})
        elif t == "media_art":
            self._save_art(msg)
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
            if tid in self.incoming:
                inc = self.incoming.pop(tid)
                inc.abort()
                self._transfer_event("in", tid, inc.name, inc.size, inc.received, "cancelled")
            o = self.outgoing.get(tid)
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
        name = next((c["name"] for c in pc.command_list(self.config.commands(), prof) if c["id"] == cid), cid)
        self.hub.emit("command_run", {"device_id": self.device_id, "device": self.name, "id": cid, "name": name})
        res = await pc.run_command(cid, self.config.commands(), prof)
        await self.send({"type": "command_result", "id": cid, "name": name, **res})

    async def _screenshot_headless(self):
        path = cache_dir() / f"ekran-{time.strftime('%Y%m%d-%H%M%S')}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        if await asyncio.to_thread(pc.screenshot_with_tools, path):
            await self.send_file(path)
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
        ev = {"device_id": self.device_id, "device": self.name, "direction": direction,
              "tid": tid, "name": name, "size": size, "done": done, "state": state, **extra}
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
        if not self.config["auto_accept"]:
            self._transfer_event("in", tid, name, size, 0, "waiting")
            ok = await self.hub.ask("file", {"device": self.name, "name": name, "size": size}, 120)
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
            await self.send({"type": "file_cancel", "transfer_id": tid, "reason": str(e)})
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
        name = path.name
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
        except (TransferFailed, OSError, ConnectionError) as e:
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
                await self.send({"type": "file_cancel", "transfer_id": tid})
            except (ConnectionError, OSError):
                pass

    async def cancel_transfer(self, direction: str, tid: int):
        if direction == "in" and tid in self.incoming:
            inc = self.incoming.pop(tid)
            inc.abort()
            self._transfer_event("in", tid, inc.name, inc.size, inc.received, "cancelled")
            await self.send({"type": "file_cancel", "transfer_id": tid})
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
