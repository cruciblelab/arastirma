"""Android JVM testinin (LiveServerTest.kt) bağlanacağı gerçek sunucu.

Bağlantıları Wi-Fi sayar (şifre yolu denensin diye), 'gonder-tetik' dosyası
yazılınca o cihaza örnek bir dosya gönderir. İlk satıra 'PORT SHA KLASOR' yazar.
"""

import asyncio
import hashlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
tmp = Path(tempfile.mkdtemp(prefix="talkto-canli-"))
os.environ["TALKTO_CACHE_DIR"] = str(tmp / "cache")

from talkto.config import Config  # noqa: E402
from talkto.hub import Hub, Session  # noqa: E402


async def main():
    cfg = Config(tmp / "cfg")
    cfg.set("usb", True)
    cfg.set("password", "test-sifre")
    cfg.set("receive_dir", str(tmp / "gelen"))
    cfg.save_command(None, "Selam", "echo canli-merhaba")
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        cfg.set("port", s.getsockname()[1])
    hub = Hub(cfg, lambda e, d: print(f"[{e}] {d}", file=sys.stderr, flush=True) if e != "status" else None,
              enable_media=False, enable_discovery=False)
    hub.usb.available = staticmethod(lambda: False)

    async def as_wifi(reader, writer):
        await Session(hub, reader, writer, "wifi", "10.0.0.9").run()
    hub._on_connection = as_wifi
    await hub.start()

    sample = tmp / "bilgisayardan.bin"
    sample.write_bytes(os.urandom(700_000))
    print(cfg["port"], hashlib.sha256(sample.read_bytes()).hexdigest(), tmp / "gelen", flush=True)
    trigger = tmp / "gonder-tetik"
    while True:
        await asyncio.sleep(0.2)
        if trigger.exists():
            device = trigger.read_text().strip()
            trigger.unlink()
            await asyncio.sleep(0.3)
            await hub.send_file(device, str(sample))

asyncio.run(main())
