"""Telefonun kendi başına yapamadığı, bilgisayarda Linux komutlarıyla yapılan işler.

Telefon yalnızca burada tanımlı hazır komutları ya da kullanıcının bilgisayarda
eklediği özel komutları adıyla (id) tetikleyebilir; telefondan rastgele komut
metni gelmez ve çalıştırılmaz.
"""

import asyncio
import os
import re
import shutil
import socket
import time
from pathlib import Path

PRESETS = [
    {"id": "kilitle", "name": "Ekranı kilitle", "icon": "lock", "argv": ["loginctl", "lock-session"]},
    {"id": "uyku", "name": "Uyku", "icon": "sleep", "argv": ["systemctl", "suspend"], "power": True},
    {"id": "yeniden", "name": "Yeniden başlat", "icon": "restart", "argv": ["systemctl", "reboot"], "power": True},
    {"id": "kapat", "name": "Bilgisayarı kapat", "icon": "power", "argv": ["systemctl", "poweroff"], "power": True},
]
OUTPUT_LIMIT = 8000
TIMEOUT = 120


def command_list(custom: list[dict], profile: dict) -> list[dict]:
    """Telefona gösterilecek komutlar (profilin izin verdikleri)."""
    if not profile.get("commands"):
        return []
    out = []
    for p in PRESETS:
        if p.get("power") and not profile.get("power"):
            continue
        out.append({"id": p["id"], "name": p["name"], "icon": p["icon"], "power": bool(p.get("power"))})
    for c in custom:
        out.append({"id": c["id"], "name": c["name"], "icon": "terminal", "power": False})
    return out


async def run_command(cid: str, custom: list[dict], profile: dict) -> dict:
    if not profile.get("commands"):
        return {"ok": False, "output": "Bu telefonun profili komut çalıştırmaya izin vermiyor."}
    preset = next((p for p in PRESETS if p["id"] == cid), None)
    if preset:
        if preset.get("power") and not profile.get("power"):
            return {"ok": False, "output": "Bu telefonun profili güç komutlarına izin vermiyor."}
        if not shutil.which(preset["argv"][0]):
            return {"ok": False, "output": f"{preset['argv'][0]} bulunamadı"}
        argv = preset["argv"]
    else:
        c = next((c for c in custom if c["id"] == cid), None)
        if not c:
            return {"ok": False, "output": "Komut bulunamadı (bilgisayarda silinmiş olabilir)."}
        argv = ["sh", "-c", c["command"]]
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, cwd=str(Path.home()), start_new_session=True)
    except OSError as e:
        return {"ok": False, "output": str(e)}
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"ok": False, "output": f"{TIMEOUT} saniyede bitmedi, durduruldu."}
    text = out.decode("utf-8", "replace")
    if len(text) > OUTPUT_LIMIT:
        text = "…" + text[-OUTPUT_LIMIT:]
    return {"ok": proc.returncode == 0, "code": proc.returncode, "output": text}


# ---- sistem bilgisi ---------------------------------------------------------------

_last_cpu: tuple[int, int] | None = None


def _cpu_percent() -> float | None:
    global _last_cpu
    try:
        f = [int(x) for x in Path("/proc/stat").read_text().splitlines()[0].split()[1:]]
    except (OSError, ValueError):
        return None
    idle, total = f[3] + (f[4] if len(f) > 4 else 0), sum(f)
    prev, _last_cpu = _last_cpu, (idle, total)
    if not prev or total == prev[1]:
        return None
    return round(100 * (1 - (idle - prev[0]) / (total - prev[1])), 1)


def _meminfo() -> tuple[int, int]:
    info = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
    except (OSError, ValueError):
        return 0, 0
    total = info.get("MemTotal", 0)
    return total - info.get("MemAvailable", 0), total


def _battery() -> dict | None:
    for d in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            return {"level": int((d / "capacity").read_text()),
                    "charging": (d / "status").read_text().strip() in ("Charging", "Full")}
        except (OSError, ValueError):
            continue
    return None


def _os_name() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return "Linux"


def sysinfo() -> dict:
    used, total = _meminfo()
    disk = shutil.disk_usage(Path.home())
    try:
        uptime = int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError):
        uptime = 0
    vol = volume_get()
    return {"host": socket.gethostname(), "os": _os_name(), "cpu": _cpu_percent(),
            "cores": os.cpu_count() or 1, "load": round(os.getloadavg()[0], 2),
            "mem_used": used, "mem_total": total, "disk_used": disk.used, "disk_total": disk.total,
            "battery": _battery(), "uptime": uptime, "time": int(time.time()),
            "volume": vol[0] if vol else None, "muted": vol[1] if vol else False}


# ---- bilgisayar sesi (PipeWire: wpctl, PulseAudio: pactl) -----------------------------

def _run(argv) -> str | None:
    import subprocess
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def volume_get() -> tuple[int, bool] | None:
    if shutil.which("wpctl"):
        out = _run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        m = re.search(r"Volume:\s*([\d.]+)", out or "")
        if m:
            return round(float(m.group(1)) * 100), "MUTED" in out
    if shutil.which("pactl"):
        out = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        m = re.search(r"(\d+)%", out or "")
        mute = _run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]) or ""
        if m:
            return int(m.group(1)), "yes" in mute.lower() or "evet" in mute.lower()
    return None


def volume_set(value: int | None = None, toggle_mute: bool = False) -> bool:
    if shutil.which("wpctl"):
        ok = True
        if value is not None:
            ok = _run(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@",
                       f"{max(0, min(100, value)) / 100:.2f}"]) is not None
        if toggle_mute:
            ok = _run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]) is not None and ok
        return ok
    if shutil.which("pactl"):
        ok = True
        if value is not None:
            ok = _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{max(0, min(100, value))}%"]) is not None
        if toggle_mute:
            ok = _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]) is not None and ok
        return ok
    return False


# ---- ekran görüntüsü (arayüzsüz kipte; masaüstünde önce portal denenir) ---------------

def screenshot_with_tools(path: Path) -> bool:
    for argv in (["gnome-screenshot", "-f", str(path)], ["spectacle", "-b", "-n", "-o", str(path)],
                 ["grim", str(path)], ["scrot", "-o", str(path)], ["import", "-window", "root", str(path)]):
        if shutil.which(argv[0]) and _run(argv) is not None and path.exists() and path.stat().st_size > 0:
            return True
    return False
