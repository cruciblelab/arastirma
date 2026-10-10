"""talk-to-android komut satırı: çalışan uygulama üzerinden telefona iş yaptırır.

    talk-to-android durum
    talk-to-android gonder foto.jpg belge.pdf [-c Pixel]
    talk-to-android pano "metin"          (metin yoksa standart girdiden: echo x | talk-to-android pano)
    talk-to-android bildirim "Derleme bitti" "0 hata"
    talk-to-android cal [--durdur]        telefonu çaldır (bul)
    talk-to-android medya oynat|duraklat|sonraki|onceki
"""

import argparse
import json
import socket
import sys
from pathlib import Path

from .ipc import socket_path

COMMANDS = {"durum", "gonder", "pano", "bildirim", "cal", "medya", "yardim"}
MEDIA = {"oynat": "play", "duraklat": "pause", "oynat-duraklat": "play_pause",
         "sonraki": "next", "onceki": "previous"}
KIND = {"usb": "USB", "wifi": "Wi-Fi", "bluetooth": "Bluetooth"}


def request(req: dict, timeout: float = 3600) -> dict:
    path = socket_path()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect(str(path))
        except (FileNotFoundError, ConnectionRefusedError):
            raise SystemExit("Talk To Android çalışmıyor. Uygulamayı menüden aç "
                             "(ya da arka planda başlat: talk-to-android --arka-planda &).")
        s.sendall(json.dumps(req, ensure_ascii=False).encode() + b"\n")
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf or b'{"ok": false, "error": "cevap yok"}')


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="talk-to-android", description="Bağlı telefona terminalden iş yaptır.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="komut", required=True)
    sub.add_parser("durum", help="bağlantı durumu ve bağlı telefonlar")
    sub.add_parser("yardim", help="bu yardım")
    p = sub.add_parser("gonder", help="dosyaları telefona gönder")
    p.add_argument("dosyalar", nargs="+")
    p = sub.add_parser("pano", help="metni telefonun panosuna kopyala")
    p.add_argument("metin", nargs="?")
    p = sub.add_parser("bildirim", help="telefonda bildirim göster")
    p.add_argument("baslik")
    p.add_argument("metin", nargs="?", default="")
    p = sub.add_parser("cal", help="telefonu çaldır")
    p.add_argument("--durdur", action="store_true")
    p = sub.add_parser("medya", help="telefonda çalan medyayı kontrol et")
    p.add_argument("islem", choices=sorted(MEDIA))
    for name in ("gonder", "pano", "bildirim", "cal", "medya"):
        sub.choices[name].add_argument("-c", "--cihaz", help="telefon adı (birden fazla bağlıysa)")
    return ap


def main(argv: list[str]) -> int:
    ap = _parser()
    a = ap.parse_args(argv)
    if a.komut == "yardim":
        ap.print_help()
        return 0
    if a.komut == "durum":
        r = request({"cmd": "status"}, timeout=10)
        ways = [w for w, on in (("Wi-Fi", r["wireless"]), ("USB", r["usb"]), ("Bluetooth", r["bluetooth"])) if on]
        print(f"{r['name']} · açık bağlantılar: {', '.join(ways) or 'yok'}")
        if r["wireless"] and r["addresses"]:
            print("Adres: " + ", ".join(f"{x}:{r['port']}" for x in r["addresses"]))
        if not r["sessions"]:
            print("Bağlı telefon yok.")
        for s in r["sessions"]:
            bat = f" · %{s['battery']['level']} pil" if s.get("battery") else ""
            print(f"• {s['name']} ({KIND.get(s['kind'], s['kind'])}, profil: {s['profile_name']}){bat}")
        return 0

    req: dict = {"device": a.cihaz}
    if a.komut == "gonder":
        req.update(cmd="send", paths=[str(Path(f).expanduser().resolve()) for f in a.dosyalar])
    elif a.komut == "pano":
        text = a.metin if a.metin is not None else sys.stdin.read()
        if not text:
            print("Gönderilecek metin yok.", file=sys.stderr)
            return 1
        req.update(cmd="clipboard", text=text)
    elif a.komut == "bildirim":
        req.update(cmd="notify", title=a.baslik, text=a.metin)
    elif a.komut == "cal":
        req.update(cmd="ring", on=not a.durdur)
    elif a.komut == "medya":
        req.update(cmd="media", action=MEDIA[a.islem])
    r = request(req)
    if not r.get("ok") and "results" not in r:
        print(r.get("error", "başarısız"), file=sys.stderr)
        return 1
    if "results" in r:
        for x in r["results"]:
            mark = "✓" if x["state"] == "done" else "✗"
            extra = "" if x["state"] == "done" else f" ({x.get('error') or x['state']})"
            print(f"{mark} {x['name']} → {r.get('device', '')}{extra}")
        return 0 if r["ok"] else 1
    print(f"✓ {r['device']}")
    return 0
