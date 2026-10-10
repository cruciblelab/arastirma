"""Komut satırı (talk-to-android gonder/pano/bildirim...) ile çalışan uygulama
arasındaki yerel soket. Yalnızca aynı kullanıcı bağlanabilir: soket kullanıcının
$XDG_RUNTIME_DIR klasöründe, izni 600, ayrıca bağlanan sürecin kullanıcı kimliği
(SO_PEERCRED) denetlenir.

Protokol: istemci bir satır JSON yollar, sunucu bir satır JSON cevap verir.
"""

import asyncio
import json
import logging
import os
import socket
import struct
from pathlib import Path

from .config import config_dir

log = logging.getLogger("talkto.ipc")


def socket_path() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base and Path(base).is_dir():
        return Path(base) / "talk-to-android.sock"
    return config_dir() / "komut.sock"


def _peer_uid(sock) -> int | None:
    try:
        creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        return struct.unpack("3i", creds)[1]
    except (OSError, AttributeError):
        return None


class IpcServer:
    def __init__(self, hub, path: Path):
        self.hub = hub
        self.path = Path(path)
        self.server = None

    async def start(self):
        if self.path.exists():
            # Önceki çalışmadan kalmış olabilir; biri dinliyorsa dokunma.
            try:
                r, w = await asyncio.wait_for(asyncio.open_unix_connection(str(self.path)), 1)
                w.close()
                raise OSError("başka bir Talk To Android zaten çalışıyor")
            except (ConnectionRefusedError, FileNotFoundError, asyncio.TimeoutError):
                self.path.unlink(missing_ok=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        old = os.umask(0o177)
        try:
            self.server = await asyncio.start_unix_server(self._client, str(self.path), limit=2 ** 20)
        finally:
            os.umask(old)
        os.chmod(self.path, 0o600)

    async def stop(self):
        if self.server:
            self.server.close()
            self.server = None
        self.path.unlink(missing_ok=True)

    async def _client(self, reader, writer):
        try:
            if _peer_uid(writer.get_extra_info("socket")) not in (None, os.getuid()):
                return
            line = await asyncio.wait_for(reader.readline(), 10)
            try:
                req = json.loads(line)
                res = await self.handle(req if isinstance(req, dict) else {})
            except (ValueError, KeyError, TypeError) as e:
                res = {"ok": False, "error": f"geçersiz istek: {e}"}
            writer.write(json.dumps(res, ensure_ascii=False).encode() + b"\n")
            await writer.drain()
        except (asyncio.TimeoutError, ConnectionError):
            pass
        finally:
            writer.close()

    def _pick(self, want: str | None):
        sessions = list(self.hub.sessions.values())
        if not sessions:
            raise LookupError("Bağlı telefon yok.")
        if not want:
            return sessions[-1]
        w = want.casefold()
        for s in sessions:
            if s.device_id == want or w in s.name.casefold():
                return s
        raise LookupError(f"“{want}” adında bağlı telefon yok. Bağlı olanlar: {', '.join(s.name for s in sessions)}")

    async def handle(self, req: dict) -> dict:
        cmd = req.get("cmd")
        hub = self.hub
        if cmd == "status":
            st = hub.status()
            return {"ok": True, "name": st["name"], "wireless": st["wireless"], "usb": st["usb"],
                    "bluetooth": bool(st["bluetooth"] and st["bt"].get("available")), "addresses": st["addresses"], "port": st["port"],
                    "sessions": [{k: s[k] for k in ("name", "kind", "battery", "profile_name")}
                                 for s in st["sessions"]]}
        try:
            s = self._pick(req.get("device"))
        except LookupError as e:
            return {"ok": False, "error": str(e)}
        if cmd == "send":
            results = []
            for p in req.get("paths", []):
                path = Path(p)
                if not path.is_file():
                    results.append({"name": p, "state": "failed", "error": "dosya yok"})
                    continue
                r = await hub.send_file(s.device_id, str(path)) or {"state": "failed", "error": "bağlantı yok"}
                results.append({"name": path.name, "state": r.get("state"), "error": r.get("error")})
            return {"ok": all(r["state"] == "done" for r in results), "device": s.name, "results": results}
        if cmd == "clipboard":
            await hub.send_clipboard(s.device_id, str(req.get("text", "")))
        elif cmd == "notify":
            await hub.notify(s.device_id, str(req.get("title", "")), str(req.get("text", "")))
        elif cmd == "ring":
            await hub.ring(s.device_id, bool(req.get("on", True)))
        elif cmd == "media":
            await hub.media_control(s.device_id, str(req.get("action")))
        else:
            return {"ok": False, "error": f"bilinmeyen komut: {cmd}"}
        return {"ok": True, "device": s.name}
