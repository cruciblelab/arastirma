"""apt ile kurulum: önce deneme (ne kurulacak, ne kaldırılacak), sonra yönetici izniyle gerçek kurulum.

Deneme (`apt-get -s`) yetki istemez ve kilide takılmaz; kullanıcıya kurmadan önce ne olacağı gösterilir.
Gerçek kurulum `pkexec apt-get install` ile yapılır: şifre penceresinde çalışacak komut görünür.
Ubuntu'nun kendi otomatik güncellemesi (unattended-upgrades) paket kilidini tutuyorsa apt bekler
(DPkg::Lock::Timeout); bekleme satırları ayrıştırılıp "sırada" olarak gösterilir.
"""

import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

LOCK_WAIT_SECONDS = 2 * 60 * 60

_INST = re.compile(r"^Inst (\S+)(?: \[([^\]]+)\])? \(([^ )]+)")
_REMV = re.compile(r"^Remv (\S+)(?: \[([^\]]+)\])?")


@dataclass
class Deneme:
    install: list[tuple[str, str | None, str]] = field(default_factory=list)  # (paket, eski, yeni)
    remove: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def extra(self, package: str):
        """Bu paketin dışında kurulacak/yükseltilecek olanlar."""
        return [i for i in self.install if i[0] != package]


def parse_simulation(text: str) -> Deneme:
    d = Deneme()
    unmet = False
    for line in text.splitlines():
        if m := _INST.match(line):
            d.install.append((m.group(1), m.group(2), m.group(3)))
        elif m := _REMV.match(line):
            d.remove.append(m.group(1))
        elif line.startswith("E: "):
            d.errors.append(line[3:].strip())
        elif "unmet dependencies" in line:
            unmet = True
        elif unmet and line.startswith(" ") and ":" in line:
            d.errors.append(" ".join(line.split()))
    return d


def simulate(path: str, flags: list[str]) -> Deneme:
    res = subprocess.run(["apt-get", "-s", "-q", "install", *flags, path], capture_output=True, text=True,
                         env=dict(os.environ, LC_ALL="C.UTF-8"), timeout=120)
    d = parse_simulation(res.stdout + "\n" + res.stderr)
    if res.returncode != 0 and not d.errors:
        d.errors.append((res.stderr or res.stdout).strip().splitlines()[-1] if (res.stderr or res.stdout).strip()
                        else "apt bu paketi kuramayacağını söyledi.")
    return d


def flags_for(verdict: str, allow_remove: bool) -> list[str]:
    flags = []
    if verdict == "ayni":
        flags.append("--reinstall")
    elif verdict == "eski":
        flags.append("--allow-downgrades")
    if not allow_remove:
        flags.append("--no-remove")  # deneme göstermediği bir şey kaldırılacaksa apt hiç başlamaz
    return flags


def private_copy(path: str) -> str:
    """Denetlenen ve kurulan dosya aynı olsun: kullanıcının klasöründeki dosya arada değiştirilemesin."""
    d = tempfile.mkdtemp(prefix="paket-guncelleyici-")
    os.chmod(d, 0o755)  # apt dosyayı ayrı bir kullanıcıyla (_apt) da okuyabilsin; yazma yalnız bizde
    dst = os.path.join(d, os.path.basename(path))
    shutil.copyfile(path, dst)
    os.chmod(dst, 0o644)
    return dst


def install_command(path: str, flags: list[str]) -> list[str]:
    # Yalnızca testler için (CI'da şifre penceresi yok): "sudo -n".
    elevate = shlex.split(os.environ.get("PAKET_GUNCELLEYICI_YETKI", "pkexec"))
    if elevate not in (["pkexec"], ["sudo", "-n"]):
        elevate = ["pkexec"]
    return [*elevate, "/usr/bin/apt-get", "install", "-y", "-q", *flags,
            "-o", f"DPkg::Lock::Timeout={LOCK_WAIT_SECONDS}", "-o", "APT::Status-Fd=1", "-o", "Dpkg::Use-Pty=0",
            "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold", path]


# ---- kurulum çıktısı ------------------------------------------------------------------------

_LOCK_PROC = re.compile(r"(\d+)\D*?\(([^)]+)\)")


@dataclass
class Olay:
    kind: str  # "kilit", "ilerleme", "hata", "bilgi"
    text: str = ""
    percent: float | None = None
    pid: int | None = None
    holder: str | None = None


def parse_line(line: str) -> Olay | None:
    line = line.strip()
    if not line:
        return None
    if line.startswith(("pmstatus:", "dlstatus:")):
        parts = line.split(":", 3)
        if len(parts) == 4:
            try:
                pct = float(parts[2])
            except ValueError:
                pct = None
            return Olay("ilerleme", parts[3], pct)
    if line.startswith("pmerror:"):
        parts = line.split(":", 3)
        return Olay("hata", parts[-1])
    if "/var/lib/dpkg/lock" in line or "/var/lib/apt/lists/lock" in line or "/var/cache/apt/archives/lock" in line:
        m = _LOCK_PROC.search(line.split("lock", 1)[-1])
        return Olay("kilit", line, pid=int(m.group(1)) if m else None, holder=m.group(2) if m else None)
    if line.startswith("E: "):
        return Olay("hata", line[3:])
    return Olay("bilgi", line)


class Ayristirici:
    """Akan çıktıyı satırlara böler (apt bekleme satırını \\r ile yeniler)."""

    def __init__(self):
        self.buf = ""

    def feed(self, chunk: str) -> list[Olay]:
        self.buf += chunk
        parts = re.split(r"[\r\n]", self.buf)
        self.buf = parts.pop()
        return [o for o in map(parse_line, parts) if o]

    def flush(self) -> list[Olay]:
        rest, self.buf = self.buf, ""
        o = parse_line(rest)
        return [o] if o else []


def holder_text(holder: str | None) -> str:
    names = {"unattended-upgr": "Ubuntu'nun otomatik güncellemesi", "packagekitd": "Uygulama Merkezi / Yazılım",
             "apt": "başka bir apt komutu", "apt-get": "başka bir apt komutu", "dpkg": "başka bir paket kurulumu",
             "aptd": "Yazılım Güncelleştirici", "snapd": "snap"}
    return names.get(holder or "", holder or "başka bir paket işlemi")


EXIT_TEXT = {126: "Şifre penceresi kapatıldı; hiçbir şey değişmedi.",
             127: "Yönetici izni verilmedi; hiçbir şey değişmedi."}


# ---- kaldırma ve onarım -----------------------------------------------------------------------

_PKG = re.compile(r"^[a-z0-9][a-z0-9+.-]+(:[a-z0-9-]+)?$")


def valid_package(name: str) -> bool:
    """Komut satırına giden paket adı: yalnızca Debian'ın izin verdiği karakterler (seçenek sanılmasın)."""
    return bool(_PKG.match(name or ""))


def _elevate() -> list[str]:
    # Yalnızca testler için (CI'da şifre penceresi yok): "sudo -n".
    elevate = shlex.split(os.environ.get("PAKET_GUNCELLEYICI_YETKI", "pkexec"))
    return elevate if elevate in (["pkexec"], ["sudo", "-n"]) else ["pkexec"]


_APT_OPTS = ["-o", f"DPkg::Lock::Timeout={LOCK_WAIT_SECONDS}", "-o", "APT::Status-Fd=1", "-o", "Dpkg::Use-Pty=0"]


INTERRUPTED = ("E: dpkg was interrupted, you must manually run 'dpkg --configure -a' to correct the problem.")


def dpkg_interrupted(updates_dir: str = "/var/lib/dpkg/updates") -> bool:
    """Yarıda kalmış bir dpkg işi var mı (yetki istemeden). apt'nin denemesi bunu görmüyor, ancak gerçek
    kurulumda "dpkg was interrupted" diye duruyor: önceden görüp kullanıcıya onarımı baştan sunmak için."""
    try:
        if any(n.isdigit() for n in os.listdir(updates_dir)):
            return True
    except OSError:
        pass
    try:
        res = subprocess.run(["dpkg", "--audit"], capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, LC_ALL="C.UTF-8"))
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bool(res.stdout.strip())


def simulate_remove(package: str, purge: bool = False) -> Deneme:
    """Kaldırınca başka ne gider: yetki istemeden deneme."""
    if not valid_package(package):
        return Deneme(errors=["Geçersiz paket adı."])
    res = subprocess.run(["apt-get", "-s", "-q", "purge" if purge else "remove", package], capture_output=True,
                         text=True, env=dict(os.environ, LC_ALL="C.UTF-8"), timeout=120)
    d = parse_simulation(res.stdout + "\n" + res.stderr)
    if res.returncode != 0 and not d.errors:
        out = (res.stderr or res.stdout).strip().splitlines()
        d.errors.append(out[-1] if out else "apt bu paketi kaldıramayacağını söyledi.")
    return d


def remove_command(package: str, purge: bool = False) -> list[str]:
    if not valid_package(package):
        raise ValueError("geçersiz paket adı")
    return [*_elevate(), "/usr/bin/apt-get", "purge" if purge else "remove", "-y", "-q", *_APT_OPTS, package]


def repair_command(kind: str) -> list[str]:
    """Onarım (hatalar.Aciklama.fix): yarım kalan işi tamamla ya da bozuk bağımlılıkları düzelt."""
    if kind == "yarim":
        return [*_elevate(), "/usr/bin/dpkg", "--configure", "-a"]
    if kind == "bagimlilik":
        return [*_elevate(), "/usr/bin/apt-get", "-f", "install", "-y", "-q", *_APT_OPTS,
                "-o", "Dpkg::Options::=--force-confdef", "-o", "Dpkg::Options::=--force-confold"]
    raise ValueError(kind)


# ---- kurulu uygulamalar -----------------------------------------------------------------------

@dataclass
class Uygulama:
    package: str
    version: str
    name: str
    icon: str | None
    desktop_id: str
    local: bool  # bir .deb dosyasından kuruldu (hiçbir paket kaynağında yok)


def parse_installed(apt_list: str) -> dict[str, tuple[str, bool]]:
    """`apt list --installed` → {paket: (sürüm, yerel mi)}."""
    out = {}
    for line in apt_list.splitlines():
        m = re.match(r"^([^/\s]+)/(\S+) (\S+) (\S+) \[([^\]]*)\]", line)
        if m:
            out[m.group(1)] = (m.group(3), "local" in m.group(5).split(","))
    return out


def parse_owners(dpkg_s: str) -> dict[str, str]:
    """`dpkg-query -S dosya...` → {dosya: paket} (ilk sahip; "diversion" satırları atlanır)."""
    out = {}
    for line in dpkg_s.splitlines():
        if line.startswith("diversion ") or ": " not in line:
            continue
        pkgs, path = line.split(": ", 1)
        out.setdefault(path.strip(), pkgs.split(",")[0].strip().split(":")[0])
    return out


def installed_apps(app_dir: str = "/usr/share/applications") -> list[Uygulama]:
    """Masaüstü menüsünde görünen, paketle kurulmuş uygulamalar; önce dosyadan kurulanlar, sonra ada göre."""
    from . import paket
    env = dict(os.environ, LC_ALL="C.UTF-8")
    installed = parse_installed(subprocess.run(["apt", "list", "--installed"], capture_output=True, text=True,
                                               env=env, timeout=60).stdout)
    files = sorted(str(p) for p in __import__("pathlib").Path(app_dir).glob("*.desktop"))
    owners = parse_owners(subprocess.run(["dpkg-query", "-S", *files], capture_output=True, text=True,
                                         env=env, timeout=60).stdout) if files else {}
    apps: dict[str, Uygulama] = {}
    for path in files:
        pkg = owners.get(path)
        if not pkg or pkg not in installed or pkg in apps:
            continue
        try:
            with open(path, "rb") as f:
                name, icon = paket._desktop(f.read())
        except OSError:
            continue
        if name is None:  # NoDisplay ya da bozuk
            continue
        version, local = installed[pkg]
        apps[pkg] = Uygulama(pkg, version, name, icon, os.path.basename(path), local)
    return sorted(apps.values(), key=lambda a: (not a.local, a.name.casefold()))
