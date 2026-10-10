"""python3 -m kopru            masaüstü uygulaması
python3 -m kopru --arka-planda  pencere açmadan başla (oturum açılışında otomatik başlatma için)
python3 -m kopru --basliksiz    arayüzsüz (sunucu/test); yeni cihazlar yalnızca şifreyle bağlanır
"""

import asyncio
import logging
import sys


def headless(approve_all: bool):
    from .config import Config
    from .hub import Hub

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

    def emit(event, data):
        if event == "ask":
            print(f"[onay] {data.get('name') or data.get('device')}: kod {data.get('code', '-')}", flush=True)
        elif event in ("status", "media", "usb"):
            return
        else:
            print(f"[{event}] {data}", flush=True)

    async def main():
        hub = Hub(Config(), emit)
        hub.auto_approve = approve_all
        await hub.start()
        st = hub.status()
        print(f"Köprü arayüzsüz çalışıyor: {', '.join(st['addresses'])} port {st['port']} "
              f"(kablosuz={'açık' if st['wireless'] else 'kapalı'}, usb={'açık' if st['usb'] else 'kapalı'}) "
              f"güvenlik kodu {st['short_fp']}", flush=True)
        await asyncio.Event().wait()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


def main():
    argv = sys.argv
    if "--basliksiz" in argv:
        headless("--onayla-hepsi" in argv)
        return 0
    from .ui.app import run
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
