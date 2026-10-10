"""Testler için telefon tarafının Python ile yazılmış en küçük hâli.

Elle deneme için de kullanılabilir:
    python3 tests/sahte_telefon.py 192.168.1.20 --sifre gizli --dosya foto.jpg
"""

import asyncio
import hashlib
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kopru import PROTOCOL_VERSION, TCP_PORT, auth  # noqa: E402
from kopru.protocol import CHUNK, encode_binary, encode_json, read_frame  # noqa: E402


class FakePhone:
    def __init__(self, device_id="telefon-test-0001", name="Test Telefonu"):
        self.device_id = device_id
        self.name = name
        self.fp = None
        self.reader = self.writer = None
        self.code = None
        self.token = None

    async def connect(self, host="127.0.0.1", port=TCP_PORT, password=None, token=None, expect_fp=None):
        """Bağlanır ve kimlik doğrular. Sonuç: 'welcome' ya da auth_failed sebebi."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # sertifika aşağıda parmak iziyle sabitlenir
        self.reader, self.writer = await asyncio.open_connection(host, port, ssl=ctx)
        der = self.writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
        self.fp = hashlib.sha256(der).hexdigest()
        if expect_fp and expect_fp != self.fp:
            raise RuntimeError("parmak izi değişti")
        await self.send({"type": "hello", "proto": PROTOCOL_VERSION, "device_id": self.device_id,
                         "name": self.name, "model": "Python", "platform": "test", "token": token})
        hello = await self.recv()
        assert hello["type"] == "hello", hello
        msg = await self.recv()
        if msg["type"] == "auth_required":
            if msg["method"] == "password":
                await self.send({"type": "auth_password",
                                 "proof": auth.password_proof(password or "", msg["nonce"], self.fp)})
            else:
                self.code = auth.pairing_code(msg["nonce"], self.fp, self.device_id)
            msg = await self.recv()
        if msg["type"] == "welcome":
            self.token = msg.get("token") or token
            return "welcome"
        return msg.get("reason", msg["type"])

    async def send(self, msg):
        self.writer.write(encode_json(msg))
        await self.writer.drain()

    async def recv(self, timeout=10):
        """Sonraki JSON iletisi (ping'lere cevap verir, ikili çerçeveleri atlar)."""
        while True:
            kind, msg = await asyncio.wait_for(read_frame(self.reader), timeout)
            if kind == "json":
                if msg["type"] == "ping":
                    await self.send({"type": "pong"})
                    continue
                return msg

    async def recv_type(self, *types, timeout=10):
        while True:
            msg = await self.recv(timeout)
            if msg["type"] in types:
                return msg

    async def send_file(self, tid, name, data: bytes, sha=None):
        await self.send({"type": "file_offer", "transfer_id": tid, "name": name, "size": len(data)})
        reply = await self.recv_type("file_accept", "file_reject")
        if reply["type"] == "file_reject":
            return reply
        for i in range(0, len(data), CHUNK):
            self.writer.write(encode_binary(tid, data[i:i + CHUNK]))
            await self.writer.drain()
        await self.send({"type": "file_done", "transfer_id": tid,
                         "sha256": sha or hashlib.sha256(data).hexdigest()})
        return await self.recv_type("file_result")

    async def receive_file(self):
        """Bilgisayarın gönderdiği bir dosyayı kabul eder ve (ad, veri) döndürür."""
        offer = await self.recv_type("file_offer")
        tid = offer["transfer_id"]
        await self.send({"type": "file_accept", "transfer_id": tid})
        buf = bytearray()
        while True:
            kind, msg = await asyncio.wait_for(read_frame(self.reader), 10)
            if kind == "binary":
                assert msg[0] == tid
                buf += msg[1]
            elif msg["type"] == "file_done":
                ok = hashlib.sha256(buf).hexdigest() == msg["sha256"]
                await self.send({"type": "file_result", "transfer_id": tid, "ok": ok})
                return offer["name"], bytes(buf)
            elif msg["type"] == "ping":
                await self.send({"type": "pong"})

    async def close(self):
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except (ConnectionError, ssl.SSLError):
                pass


async def _main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=TCP_PORT)
    ap.add_argument("--sifre")
    ap.add_argument("--dosya")
    a = ap.parse_args()
    p = FakePhone()
    task = asyncio.create_task(p.connect(a.host, a.port, a.sifre))
    while not task.done():
        await asyncio.sleep(0.2)
        if p.code:
            print("Bilgisayarda onayla, kod:", p.code)
            p.code = None
    print("Sonuç:", task.result())
    if task.result() == "welcome":
        await p.send({"type": "battery", "level": 77, "charging": True})
        await p.send({"type": "notification", "key": "k1", "package": "com.ornek", "app": "Örnek",
                      "title": "Merhaba", "text": "Sahte telefondan bildirim"})
        if a.dosya:
            data = Path(a.dosya).read_bytes()
            print(await p.send_file(1, Path(a.dosya).name, data))
        await asyncio.sleep(2)
    await p.close()


if __name__ == "__main__":
    asyncio.run(_main())
