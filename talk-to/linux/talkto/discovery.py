"""Yerel ağda keşif: Wi-Fi bağlantısı açıkken bilgisayar kendini UDP yayınıyla
duyurur ve telefonun 'probe' paketine doğrudan cevap verir."""

import asyncio
import json
import logging
import socket

from . import PROTOCOL_VERSION, UDP_PORT
from .netinfo import interfaces

log = logging.getLogger("talkto.kesif")
INTERVAL = 3.0


class _Proto(asyncio.DatagramProtocol):
    def __init__(self, owner):
        self.owner = owner

    def datagram_received(self, data, addr):
        try:
            msg = json.loads(data)
        except ValueError:
            return
        if isinstance(msg, dict) and msg.get("talkto") == PROTOCOL_VERSION and msg.get("type") == "probe":
            self.owner.reply(addr)


class Announcer:
    def __init__(self, info_fn, port: int = UDP_PORT):
        self.info_fn = info_fn  # -> duyurulacak sözlük
        self.port = port
        self.transport = None
        self._task = None

    async def start(self):
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("0.0.0.0", self.port))
        except OSError as e:
            # Port doluysa yalnızca yayın yaparız; probe cevabı olmaz.
            log.warning("UDP %d bağlanamadı (%s); yalnızca duyuru yapılacak", self.port, e)
            sock.bind(("0.0.0.0", 0))
        self.transport, _ = await loop.create_datagram_endpoint(lambda: _Proto(self), sock=sock)
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None
        if self.transport:
            self.transport.close()
            self.transport = None

    def _packet(self) -> bytes:
        return json.dumps({"talkto": PROTOCOL_VERSION, "type": "announce", **self.info_fn()}).encode()

    def reply(self, addr):
        if self.transport:
            self.transport.sendto(self._packet(), addr)

    async def _loop(self):
        while True:
            targets = {i["broadcast"] for i in await asyncio.to_thread(interfaces)}
            targets.add("255.255.255.255")
            pkt = self._packet()
            for t in targets:
                try:
                    self.transport.sendto(pkt, (t, self.port))
                except OSError:
                    pass
            await asyncio.sleep(INTERVAL)
