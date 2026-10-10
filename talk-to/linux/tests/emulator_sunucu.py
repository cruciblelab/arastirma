"""Android emülatöründeki gerçek Talk To Linux uygulamasının bağlanacağı sunucu.

127.0.0.1:47600'de dinler (emülatörde `adb reverse tcp:47600 tcp:47600` ile USB yolu),
eşleşme isteklerini kendiliğinden onaylar ve olayları JSON satırları olarak yazar:
    python3 emulator_sunucu.py olaylar.jsonl
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
tmp = Path(tempfile.mkdtemp(prefix="talkto-emulator-"))
os.environ["TALKTO_CACHE_DIR"] = str(tmp / "cache")

from talkto.config import Config  # noqa: E402
from talkto.hub import Hub  # noqa: E402

OUT = Path(sys.argv[1])


async def main():
    cfg = Config(tmp / "cfg")
    cfg.set("usb", True)
    cfg.set("wireless", False)
    cfg.set("port", 47600)
    cfg.set("receive_dir", str(tmp / "gelen"))
    out = OUT.open("a", encoding="utf-8", buffering=1)
    hub = None

    def emit(event, data):
        if event == "status":
            data = {"sessions": [{k: s.get(k) for k in ("name", "kind", "phone", "problems")}
                                 for s in data.get("sessions", [])]}
        elif event in ("media_art", "transfer"):
            data = {k: v for k, v in data.items() if k != "data"}
        out.write(json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str) + "\n")
        if event == "ask":
            asyncio.get_running_loop().create_task(hub.answer(data["id"], True))

    hub = Hub(cfg, emit, enable_media=False, enable_discovery=False)
    hub.usb.available = staticmethod(lambda: False)  # tüneli betik kurar
    await hub.start()
    print("hazir", flush=True)
    await asyncio.Event().wait()

asyncio.run(main())
