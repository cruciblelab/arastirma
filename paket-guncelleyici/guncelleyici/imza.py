"""Yayıncı imzası: bu dosya, kurulu sürümü yayımlayan kişiden mi geliyor?

Android'in APK güncellemesinde aynı sertifikayı istemesi ya da Talk To'nun eşleşmede güvenlik kodunu
ilk seferde kaydetmesi gibi:

- Paket debsigs biçiminde imzalıysa ("_gpgorigin" parçası) imza önce **güven çapalarıyla** denenir:
  kurulu paketin kendi anahtarı (/usr/share/keyrings/<paket>-paket.gpg, o pakete ait olmalı) ve
  kullanıcının daha önce onayladığı anahtar (~/.config/paket-guncelleyici/anahtarlar/<paket>.gpg).
  Tutarsa: AYNI yayıncı.
- Tutmazsa paketin içindeki anahtarla denenir. Çapa yoksa İLK kez görülen yayıncı (parmak izi
  gösterilir, kurulunca kaydedilir); çapa varsa FARKLI yayıncı (ayrıca onay ister).
- İmza yoksa İMZASIZ; daha önce imzalı bir sürüm kurulmuşsa bu da farklı yayıncı gibi ele alınır
  (imzayı kaldırarak denetimden kaçılmasın).

İmza her zaman bütün paket içeriğini (debian-binary + control + data) kapsar; tek bayt değişse tutmaz.
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import arsiv

AYNI, ILK, FARKLI, IMZASIZ, BOZUK = "ayni", "ilk", "farkli", "imzasiz", "bozuk"


def pins_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "paket-guncelleyici" / "anahtarlar"


@dataclass
class Sonuc:
    state: str
    fingerprint: str | None = None
    anchor: str | None = None  # "kurulu" ya da "onaylanan"
    had_anchor: bool = False  # daha önce bir yayıncı anahtarı biliniyordu

    @property
    def needs_confirmation(self) -> bool:
        return self.state in (FARKLI, BOZUK) or (self.state == IMZASIZ and self.had_anchor)


def grouped(fpr: str) -> str:
    return " ".join(fpr[i:i + 4] for i in range(0, len(fpr), 4))


def _gpgv(sig: bytes, payload: bytes, keyring: bytes) -> str | None:
    with tempfile.TemporaryDirectory() as d:
        sig_path, ring = os.path.join(d, "imza"), os.path.join(d, "anahtar.gpg")
        Path(sig_path).write_bytes(sig)
        Path(ring).write_bytes(keyring)
        try:
            res = subprocess.run(["gpgv", "--status-fd", "1", "--keyring", ring, sig_path, "-"],
                                 input=payload, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
    if res.returncode != 0:
        return None
    for line in res.stdout.decode(errors="replace").splitlines():
        if line.startswith("[GNUPG:] VALIDSIG "):
            return line.split()[-1]
    return None


def owned_by(path: Path, package: str) -> bool:
    res = subprocess.run(["dpkg-query", "-S", str(path)], capture_output=True, text=True)
    return res.returncode == 0 and any(line.split(":")[0].strip() == package
                                       for line in res.stdout.splitlines())


def anchors(package: str, installed: bool, root: Path = Path("/"), pins: Path | None = None):
    """[(tür, anahtar baytları)] — imzanın tutması beklenen anahtarlar."""
    out = []
    key = root / "usr/share/keyrings" / f"{package}-paket.gpg"
    if installed and key.is_file() and (root != Path("/") or owned_by(key, package)):
        out.append(("kurulu", key.read_bytes()))
    pin = (pins or pins_dir()) / f"{package}.gpg"
    if pin.is_file():
        out.append(("onaylanan", pin.read_bytes()))
    return out


def check(deb_path: str, package: str, embedded_key: bytes | None, known) -> Sonuc:
    """known: anchors() sonucu."""
    members = arsiv.parcalar(deb_path)
    sig = next((b for n, b in members if n == arsiv.IMZA), None)
    if sig is None:
        return Sonuc(IMZASIZ, had_anchor=bool(known))
    payload = arsiv.imzali_icerik(members)
    for kind, ring in known:
        fpr = _gpgv(sig, payload, ring)
        if fpr:
            return Sonuc(AYNI, fpr, kind, had_anchor=True)
    fpr = _gpgv(sig, payload, embedded_key) if embedded_key else None
    if not fpr:
        # İmza var ama ne bilinen ne de paketteki anahtarla tutuyor: içerik değişmiş ya da anahtar eksik.
        return Sonuc(BOZUK, had_anchor=bool(known))
    return Sonuc(FARKLI if known else ILK, fpr, had_anchor=bool(known))


def remember(package: str, key: bytes, pins: Path | None = None):
    """Kullanıcının onayladığı (ilk kez görülen) yayıncı anahtarını sonraki sürümler için kaydeder."""
    d = pins or pins_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{package}.gpg.tmp"
    tmp.write_bytes(key)
    os.replace(tmp, d / f"{package}.gpg")
