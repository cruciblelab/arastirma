""".deb dosyasının içi: ar arşivi parçaları ve veri arşivinden seçilen dosyalar.

`ar` (binutils) Ubuntu masaüstünde kurulu gelmiyor; arşiv burada okunur. Veri arşivi
(gz/xz/zstd) `dpkg-deb --fsys-tarfile` ile açılır, böylece sıkıştırma türü dert olmaz.
"""

import subprocess
import tarfile

from .dil import _t

MAGIC = b"!<arch>\n"
IMZA = "_gpgorigin"  # debsigs biçimindeki yayıncı imzası


def parcalar(path: str) -> list[tuple[str, bytes]]:
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(MAGIC):
        raise ValueError(_t("Bu bir .deb paketi değil."))
    out, pos = [], len(MAGIC)
    while pos + 60 <= len(data):
        head = data[pos:pos + 60]
        if head[58:60] != b"`\n":
            raise ValueError(_t("Paket dosyası bozuk."))
        name = head[:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(head[48:58].decode("ascii").strip())
        pos += 60
        out.append((name, data[pos:pos + size]))
        pos += size + (size % 2)
    return out


def imzali_icerik(members) -> bytes:
    """İmzanın kapsadığı bayt dizisi: debian-binary + control.tar.* + data.tar.* (debsigs)."""
    parts = [b for n, b in members if n == "debian-binary" or n.startswith(("control.tar", "data.tar"))]
    if len(parts) != 3:
        raise ValueError(_t("Paket dosyası eksik ya da bozuk."))
    return b"".join(parts)


def dosyalar(path: str, sec, en_cok: int = 2 * 1024 * 1024) -> dict[str, bytes]:
    """Veri arşivinden sec(ad) True dönen dosyaları okur (ad başında './' olmadan)."""
    proc = subprocess.Popen(["dpkg-deb", "--fsys-tarfile", path], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    out = {}
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for m in tar:
                name = m.name[2:] if m.name.startswith("./") else m.name.lstrip("/")
                if m.isfile() and m.size <= en_cok and sec(name):
                    f = tar.extractfile(m)
                    if f:
                        out[name] = f.read()
    except tarfile.TarError as e:
        raise ValueError(_t("Paketin içi okunamadı: {error}").format(error=e)) from e
    finally:
        proc.stdout.close()
        proc.wait()
    return out
