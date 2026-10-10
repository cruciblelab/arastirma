"""talk-to-android                  masaüstü uygulaması
talk-to-android --arka-planda     pencere açmadan başla (oturum açılışında otomatik başlatma için)
talk-to-android --basliksiz       arayüzsüz (sunucu/test); yeni cihazlar yalnızca şifreyle bağlanır
talk-to-android durum|gonder|pano|bildirim|cal|medya ...   çalışan uygulamaya terminalden komut (bkz. cli.py)
"""

import asyncio
import logging
import sys


def headless(approve_all: bool):
    from .config import Config
    from .hub import Hub
    from .ipc import socket_path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

    def emit(event, data):
        if event == "ask":
            print(f"[onay] {data.get('name') or data.get('device')}: kod {data.get('code', '-')}", flush=True)
        elif event in ("status", "media", "usb"):
            return
        else:
            print(f"[{event}] {data}", flush=True)

    async def main():
        hub = Hub(Config(), emit, ipc_path=socket_path())
        hub.auto_approve = approve_all
        await hub.start()
        st = hub.status()
        print(f"Talk To Android arayüzsüz çalışıyor: {', '.join(st['addresses'])} port {st['port']} "
              f"(kablosuz={'açık' if st['wireless'] else 'kapalı'}, usb={'açık' if st['usb'] else 'kapalı'}) "
              f"güvenlik kodu {st['short_fp']}", flush=True)
        await asyncio.Event().wait()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


def main():
    argv = sys.argv
    from .cli import COMMANDS
    if len(argv) > 1 and (argv[1] in COMMANDS or argv[1] in ("-h", "--help", "--yardim")):
        from .cli import main as cli_main
        return cli_main(["yardim"] if argv[1].startswith("-") else argv[1:])
    if "--basliksiz" in argv:
        headless("--onayla-hepsi" in argv)
        return 0
    from .ui.app import run
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
