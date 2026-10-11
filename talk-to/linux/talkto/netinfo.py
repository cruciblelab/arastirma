"""Yerel IPv4 adresleri ve yayın (broadcast) adresleri."""

import json
import socket
import subprocess


def interfaces() -> list[dict]:
    """[{'name', 'addr', 'broadcast'}] — döngü (lo) ve kapalı arayüzler hariç."""
    out = []
    try:
        res = subprocess.run(["ip", "-j", "-4", "addr", "show", "up"],
                             capture_output=True, text=True, timeout=3)
        for iface in json.loads(res.stdout or "[]"):
            if "LOOPBACK" in iface.get("flags", []):
                continue
            for a in iface.get("addr_info", []):
                if a.get("family") == "inet" and a.get("local"):
                    out.append({"name": iface.get("ifname", "?"), "addr": a["local"],
                                "broadcast": a.get("broadcast") or "255.255.255.255"})
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    if not out:
        # 'ip' yoksa: varsayılan rotanın adresini öğrenmek için bağlanmadan UDP soketi.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                out.append({"name": "?", "addr": s.getsockname()[0], "broadcast": "255.255.255.255"})
        except OSError:
            pass
    return out


_LOOPBACK_HEX = ("0100007F", "00000000000000000000000001000000", "0000000000000000FFFF00000100007F")


def loopback_peer_uid(peer_port: int, local_port: int, tables=("/proc/net/tcp", "/proc/net/tcp6")) -> int | None:
    """127.0.0.1 üzerinden bize bağlanan soketin sahibi olan kullanıcı (Linux /proc/net/tcp).

    Bağlananın kaydında yerel adres 127.0.0.1:peer_port, uzak adres 127.0.0.1:local_port olur.
    Bulunamazsa None.
    """
    want_local, want_remote = f"{peer_port:04X}", f"{local_port:04X}"
    for table in tables:
        try:
            with open(table, encoding="ascii") as fh:
                lines = fh.read().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            if len(f) < 8:
                continue
            (la, lp), (ra, rp) = f[1].split(":"), f[2].split(":")
            if lp == want_local and rp == want_remote and la in _LOOPBACK_HEX and ra in _LOOPBACK_HEX:
                try:
                    return int(f[7])
                except ValueError:
                    return None
    return None
