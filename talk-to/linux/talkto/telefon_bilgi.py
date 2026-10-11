"""Telefonun sistem bilgileri (phone_info iletisi): temizleme ve gösterilecek satırlar.

Bilgisayarda üst karttaki baloncuğa (ör. "USB · %76") tıklayınca açılan pencerecikte görünür.
"""

import time


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _text(v, limit):
    return v[:limit] if isinstance(v, str) else ""


def clean(msg: dict) -> dict:
    def part(name, *keys):
        d = msg.get(name) if isinstance(msg.get(name), dict) else {}
        return {k: _num(d.get(k)) for k in keys}
    battery = part("battery", "level", "temp_c")
    b = msg.get("battery") if isinstance(msg.get("battery"), dict) else {}
    battery.update(charging=bool(b.get("charging")), health=_text(b.get("health"), 30) or None)
    return {"manufacturer": _text(msg.get("manufacturer"), 60), "model": _text(msg.get("model"), 60),
            "android": _text(msg.get("android"), 20), "sdk": _num(msg.get("sdk")),
            "security_patch": _text(msg.get("security_patch"), 20), "app_version": _text(msg.get("app_version"), 40),
            "uptime_s": _num(msg.get("uptime_s")), "network": _text(msg.get("network"), 30) or None,
            "battery": battery, "storage": part("storage", "total", "free"), "ram": part("ram", "total", "free"),
            "received": time.time()}


def size(n) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return ""


def _usage(d: dict, verb: str) -> str | None:
    total, free = d.get("total"), d.get("free")
    if not total or free is None:
        return None
    used = total - free
    return f"{size(used)} / {size(total)} {verb} (%{round(used * 100 / total)})"


def rows(info: dict | None) -> list[tuple[str, str]]:
    """[(başlık, değer)]: yalnızca bilinenler."""
    if not info:
        return []
    out = []
    name = " ".join(x for x in (info.get("manufacturer"), info.get("model")) if x)
    if name:
        out.append(("Model", name))
    if info.get("android"):
        v = f"Android {info['android']}" + (f" (API {info['sdk']})" if info.get("sdk") else "")
        if info.get("security_patch"):
            v += f" · güvenlik yaması {info['security_patch']}"
        out.append(("Sistem", v))
    b = info.get("battery") or {}
    if b.get("level") is not None:
        v = f"%{b['level']:.0f}" + (" · şarj oluyor" if b.get("charging") else "")
        if b.get("temp_c") is not None:
            v += f" · {b['temp_c']:.1f} °C".replace(".", ",")
        if b.get("health"):
            v += f" · sağlık: {b['health']}"
        out.append(("Pil", v))
    for key, label, verb in (("storage", "Depolama", "dolu"), ("ram", "Bellek", "kullanımda")):
        u = _usage(info.get(key) or {}, verb)
        if u:
            out.append((label, u))
    if info.get("network"):
        out.append(("Ağ", info["network"]))
    if info.get("uptime_s"):
        s = int(info["uptime_s"])
        d, h, m = s // 86400, s // 3600 % 24, s // 60 % 60
        out.append(("Açık kalma", (f"{d} gün " if d else "") + f"{h} sa {m} dk"))
    if info.get("app_version"):
        out.append(("Talk To Linux", info["app_version"]))
    return out
