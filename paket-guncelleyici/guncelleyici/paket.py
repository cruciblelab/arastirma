"""Paket bilgisi ve karar: bu dosya kurulu sürüme göre yeni kurulum mu, güncelleme mi, eski sürüm mü?

Ubuntu'nun Uygulama Merkezi yerel .deb dosyasında sürümleri karşılaştırmıyor (o adla paket kuruluysa
yalnızca "kaldır" gösteriyor). Burada karşılaştırma dpkg'nin kendi kuralıyla yapılır.
"""

import os
import re
import subprocess
from configparser import ConfigParser
from dataclasses import dataclass, field

from . import arsiv

# Karar: dosya ile kurulu sürüm arasındaki ilişki
KUR, GUNCELLE, AYNI, ESKI, UYUMSUZ = "kur", "guncelle", "ayni", "eski", "uyumsuz"
ICON_DIRS = ("scalable", "512x512", "256x256", "128x128", "96x96", "64x64", "48x48")


@dataclass
class Paket:
    path: str
    package: str
    version: str
    arch: str
    summary: str
    description: str = ""
    maintainer: str = ""
    homepage: str = ""
    size: int = 0
    installed: str | None = None  # kurulu sürüm (yoksa None)
    verdict: str = KUR
    name: str = ""  # masaüstü dosyasındaki uygulama adı (yoksa paket adı)
    icon_name: str | None = None
    icon_data: bytes | None = None  # paketin içindeki simge (henüz kurulu değilse gösterilir)
    icon_ext: str = ".png"
    desktop_ids: list[str] = field(default_factory=list)
    keyring: bytes | None = None  # paketin içindeki yayıncı anahtarı (/usr/share/keyrings/<paket>-paket.gpg)
    publisher: bytes | None = None  # yayıncı kartı (/usr/share/keyrings/<paket>-paket.json, bkz. yayinci.py)

    @property
    def keyring_path(self) -> str:
        return f"usr/share/keyrings/{self.package}-paket.gpg"

    @property
    def publisher_path(self) -> str:
        return f"usr/share/keyrings/{self.package}-paket.json"


def control(text: str) -> dict[str, str]:
    """Debian denetim dosyası (RFC 822 benzeri): çok satırlı alanlar birleştirilir."""
    out, key = {}, None
    for line in text.splitlines():
        if line[:1] in (" ", "\t") and key:
            out[key] += "\n" + line[1:]
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            out[key] = value.strip()
    return out


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, env=dict(os.environ, LC_ALL="C.UTF-8"))


def installed_version(package: str) -> str | None:
    res = _run("dpkg-query", "-W", "-f", "${db:Status-Status} ${Version}", package)
    if res.returncode != 0:
        return None
    status, _, version = res.stdout.strip().partition(" ")
    return version if status == "installed" else None


def compare(a: str, b: str) -> int:
    """dpkg kuralıyla: a < b ise -1, eşitse 0, büyükse 1."""
    if _run("dpkg", "--compare-versions", a, "eq", b).returncode == 0:
        return 0
    return -1 if _run("dpkg", "--compare-versions", a, "lt", b).returncode == 0 else 1


def architectures() -> set[str]:
    archs = {"all"}
    for cmd in (("dpkg", "--print-architecture"), ("dpkg", "--print-foreign-architectures")):
        archs.update(_run(*cmd).stdout.split())
    return archs


def verdict(version: str, installed: str | None, arch: str, archs: set[str]) -> str:
    if arch not in archs:
        return UYUMSUZ
    if installed is None:
        return KUR
    c = compare(version, installed)
    return GUNCELLE if c > 0 else AYNI if c == 0 else ESKI


def _desktop(data: bytes) -> tuple[str | None, str | None]:
    cp = ConfigParser(interpolation=None, strict=False)
    try:
        cp.read_string(data.decode("utf-8", "replace"))
        entry = cp["Desktop Entry"]
    except Exception:  # noqa: BLE001 — bozuk masaüstü dosyası adı/simgeyi yalnızca eksik bırakır
        return None, None
    if entry.get("NoDisplay", "").lower() == "true":
        return None, None
    lang = (os.environ.get("LANG") or "").split(".")[0]
    name = entry.get(f"Name[{lang}]") or entry.get(f"Name[{lang[:2]}]") or entry.get("Name")
    return name, entry.get("Icon")


def read(path: str) -> Paket:
    path = os.path.abspath(path)
    res = _run("dpkg-deb", "-f", path)
    if res.returncode != 0:
        raise ValueError("Bu dosya bir .deb paketi olarak okunamadı.")
    c = control(res.stdout)
    if not c.get("Package") or not c.get("Version"):
        raise ValueError("Paketin adı ya da sürümü yok.")
    summary, _, rest = c.get("Description", "").partition("\n")
    p = Paket(path=path, package=c["Package"], version=c["Version"], arch=c.get("Architecture", "all"),
              summary=summary.strip(), description="\n".join(
                  "" if line.strip() == "." else line for line in rest.splitlines()).strip(),
              maintainer=re.sub(r"\s*<[^>]*>", "", c.get("Maintainer", "")), homepage=c.get("Homepage", ""),
              size=os.path.getsize(path))
    p.installed = installed_version(p.package)
    p.verdict = verdict(p.version, p.installed, p.arch, architectures())

    def wanted(name: str) -> bool:
        return (name in (p.keyring_path, p.publisher_path)
                or (name.startswith("usr/share/applications/") and name.endswith(".desktop"))
                or (name.startswith("usr/share/icons/hicolor/") and "/apps/" in name)
                or name.startswith("usr/share/pixmaps/"))
    files = arsiv.dosyalar(path, wanted)
    p.keyring = files.get(p.keyring_path)
    p.publisher = files.get(p.publisher_path)
    for name in sorted(n for n in files if n.endswith(".desktop")):
        title, icon = _desktop(files[name])
        if title is None:
            continue
        p.desktop_ids.append(os.path.basename(name))
        if not p.name:
            p.name, p.icon_name = title, icon
    p.name = p.name or p.package
    if p.icon_name:
        for size in ICON_DIRS:
            for ext in (".svg", ".png"):
                data = files.get(f"usr/share/icons/hicolor/{size}/apps/{p.icon_name}{ext}")
                if data:
                    p.icon_data, p.icon_ext = data, ext
                    break
            if p.icon_data:
                break
        else:
            for ext in (".svg", ".png"):
                if f"usr/share/pixmaps/{p.icon_name}{ext}" in files:
                    p.icon_data, p.icon_ext = files[f"usr/share/pixmaps/{p.icon_name}{ext}"], ext
                    break
    return p
