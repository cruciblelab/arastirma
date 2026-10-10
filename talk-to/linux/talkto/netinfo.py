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
