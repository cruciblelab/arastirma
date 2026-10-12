"""Bir uygulamanın çalışan süreçleri ve "Durmaya zorla" (Android'deki gibi).

Hangi sürecin hangi uygulamaya ait olduğunu tutan bir kayıt yok; şöyle bulunur — yalnızca bu kullanıcının
süreçleri arasında (başka kullanıcınınkine ve sisteme hiç dokunulmaz):
- sürecin programı (/proc/PID/exe; güncellemeden sonra "(deleted)" ekli olabilir) paketin bir dosyasıysa,
- komut satırındaki ilk iki öğeden biri paketin bir dosyasıysa ("python3 /usr/bin/x", "sh /usr/bin/x"),
- "python3 -m modul" biçimindeyse ve modül paketin içindeyse (ör. Talk To),
- komutun adı masaüstü dosyasındaki komutla aynıysa (python3, sh gibi genel adlar sayılmaz).
"""

import os
import signal
import subprocess
import time

GENERIC = {"python", "python3", "sh", "bash", "dash", "env", "java", "node", "perl", "ruby", "flatpak", "snap",
           "bwrap", "electron", "gjs", "mono", "wine", "xdg-open"}


def package_files(package: str) -> set[str]:
    try:
        res = subprocess.run(["dpkg-query", "-L", package], capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, LC_ALL="C.UTF-8"))
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return {ln.strip() for ln in res.stdout.splitlines() if ln.startswith("/")}


def _read(path: str, binary=False):
    try:
        with open(path, "rb" if binary else "r") as f:
            return f.read()
    except OSError:
        return None


def _modules(files: set[str]) -> set[str]:
    """Paketin içindeki Python modülleri ("-m ad" ile çalışanlar): .../ad/__main__.py → ad."""
    out = set()
    for f in files:
        if f.endswith("/__main__.py"):
            out.add(os.path.basename(os.path.dirname(f)))
    return out


def find(package: str, exe_name: str | None = None, *, files: set[str] | None = None, proc: str = "/proc",
         uid: int | None = None, me: int | None = None) -> list[int]:
    """Bu kullanıcının, bu pakete ait çalışan süreçleri."""
    files = package_files(package) if files is None else files
    uid = os.getuid() if uid is None else uid
    me = os.getpid() if me is None else me
    mods = _modules(files)
    name = exe_name if exe_name and exe_name not in GENERIC else None
    out = []
    try:
        entries = os.listdir(proc)
    except OSError:
        return []
    for e in entries:
        if not e.isdigit() or int(e) == me:
            continue
        base = f"{proc}/{e}"
        try:
            if os.stat(base).st_uid != uid:
                continue
        except OSError:
            continue
        stat = _read(f"{base}/stat") or ""
        if stat.rsplit(")", 1)[-1].split()[:1] == ["Z"]:  # bitmiş, toplanmayı bekliyor
            continue
        try:
            exe = os.readlink(f"{base}/exe").removesuffix(" (deleted)")
        except OSError:
            exe = ""
        raw = _read(f"{base}/cmdline", binary=True) or b""
        argv = [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]
        hit = (exe in files or any(a in files for a in argv[:2])
               or any(argv[i] == "-m" and argv[i + 1].split(".")[0] in mods for i in range(min(len(argv) - 1, 3)))
               or (name is not None and argv and os.path.basename(argv[0]) == name))
        if hit:
            out.append(int(e))
    return sorted(out)


def _alive(pid: int, proc: str = "/proc") -> bool:
    stat = _read(f"{proc}/{pid}/stat")
    return bool(stat) and stat.rsplit(")", 1)[-1].split()[:1] != ["Z"]


def stop(pids: list[int], grace: float = 3.0) -> list[int]:
    """Önce kapanmasını ister (SIGTERM), süre dolunca zorla (SIGKILL). Hâlâ yaşayanları döndürür."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for p in pids:
            try:
                os.kill(p, sig)
            except (ProcessLookupError, PermissionError):
                pass
        end = time.monotonic() + (grace if sig == signal.SIGTERM else 2.0)
        while time.monotonic() < end and any(_alive(p) for p in pids):
            time.sleep(0.1)
        pids = [p for p in pids if _alive(p)]
        if not pids:
            break
    return pids
