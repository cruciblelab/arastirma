#!/usr/bin/env python3
"""Talk To .deb paketini imzalar ya da imzasını doğrular (debsigs "_gpgorigin" biçimi).

    python3 paket/deb-imzala.py imzala  PAKET.deb GIZLI_ANAHTAR.asc
    python3 paket/deb-imzala.py dogrula PAKET.deb [ANAHTARLIK.gpg]

İmza, paketin içindeki "debian-binary", "control.tar.*" ve "data.tar.*" parçalarının art arda
eklenmiş hâlinin ayrık OpenPGP imzasıdır; paketin sonuna "_gpgorigin" adlı parça olarak eklenir.
dpkg ve apt "_" ile başlayan parçaları yok sayar, yani imzalı paket her yerde aynı kurulur;
debsig-verify ve Paket Güncelleyici bu parçayı okur. Yayıncının açık anahtarı paketin içinde
/usr/share/keyrings/talk-to-android-paket.gpg olarak durur: sonraki sürümün imzası, kurulu
sürümün bu anahtarıyla doğrulanır (Android'in APK güncellemesinde aynı sertifikayı istemesi gibi).

`ar` (binutils) Ubuntu masaüstünde kurulu gelmediği için arşiv burada okunup yazılır.
"""

import os
import shutil
import subprocess
import sys
import tempfile

MAGIC = b"!<arch>\n"
SIG = "_gpgorigin"


def read_ar(data: bytes) -> list[tuple[str, bytes]]:
    if not data.startswith(MAGIC):
        raise ValueError("bu bir .deb (ar arşivi) değil")
    out, pos = [], len(MAGIC)
    while pos + 60 <= len(data):
        head = data[pos:pos + 60]
        if head[58:60] != b"`\n":
            raise ValueError("bozuk ar başlığı")
        name = head[:16].decode("ascii").strip().rstrip("/")
        size = int(head[48:58].decode("ascii").strip())
        pos += 60
        out.append((name, data[pos:pos + size]))
        pos += size + (size % 2)
    return out


def write_ar(members: list[tuple[str, bytes]]) -> bytes:
    out = bytearray(MAGIC)
    for name, body in members:
        head = f"{name:<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(body):<10}".encode("ascii") + b"`\n"
        out += head + body + (b"\n" if len(body) % 2 else b"")
    return bytes(out)


def signed_payload(members) -> bytes:
    parts = [b for n, b in members if n == "debian-binary" or n.startswith(("control.tar", "data.tar"))]
    if len(parts) != 3:
        raise ValueError("paket parçaları eksik")
    return b"".join(parts)


def sign(deb: str, secret_key: str):
    with open(deb, "rb") as f:
        members = [m for m in read_ar(f.read()) if m[0] != SIG]
    home = tempfile.mkdtemp()
    try:
        env = dict(os.environ, GNUPGHOME=home)
        subprocess.run(["gpg", "--batch", "--quiet", "--import", secret_key], env=env, check=True)
        res = subprocess.run(["gpg", "--batch", "--quiet", "--pinentry-mode", "loopback", "--passphrase", "",
                              "--detach-sign", "--output", "-"], input=signed_payload(members), env=env,
                             capture_output=True, check=True)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    tmp = deb + ".tmp"
    with open(tmp, "wb") as f:
        f.write(write_ar(members + [(SIG, res.stdout)]))
    os.replace(tmp, deb)


def verify(deb: str, keyring: str) -> str:
    """İmza bu anahtarlıkla tutuyorsa yayıncının parmak izini döndürür, yoksa ValueError."""
    with open(deb, "rb") as f:
        members = read_ar(f.read())
    sig = next((b for n, b in members if n == SIG), None)
    if sig is None:
        raise ValueError("paket imzasız")
    with tempfile.TemporaryDirectory() as d:
        sig_path = os.path.join(d, "imza")
        with open(sig_path, "wb") as f:
            f.write(sig)
        res = subprocess.run(["gpgv", "--status-fd", "1", "--keyring", os.path.abspath(keyring), sig_path, "-"],
                             input=signed_payload(members), capture_output=True)
    for line in res.stdout.decode(errors="replace").splitlines():
        if line.startswith("[GNUPG:] VALIDSIG ") and res.returncode == 0:
            return line.split()[-1]  # birincil anahtarın parmak izi
    raise ValueError("imza bu anahtarla tutmuyor")


def main(argv):
    if len(argv) >= 3 and argv[1] == "imzala":
        sign(argv[2], argv[3])
        print("imzalandı:", argv[2])
    elif len(argv) >= 3 and argv[1] == "dogrula":
        keyring = argv[3] if len(argv) > 3 else os.path.join(os.path.dirname(__file__), "talk-to-android-paket.gpg")
        print("imza tutuyor, yayıncı:", verify(argv[2], keyring))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print("hata:", e, file=sys.stderr)
        sys.exit(1)
