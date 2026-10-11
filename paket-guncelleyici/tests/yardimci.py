"""Testler için gerçek .deb paketleri ve GPG anahtarları üretir."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("deb_imzala", ROOT / "paket" / "deb-imzala.py")
imzala = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imzala)

ICON = (b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">'
        b'<rect width="16" height="16" fill="#c60"/></svg>')


def make_key(d: Path, name: str):
    """(gizli anahtar dosyası, açık anahtarlık baytları, parmak izi)"""
    home = d / f"gpg-{name}"
    home.mkdir(mode=0o700, exist_ok=True)
    env = dict(os.environ, GNUPGHOME=str(home))
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase", "", "--quick-gen-key", f"{name} <{name}@x.invalid>",
                    "ed25519", "sign", "never"], env=env, check=True, capture_output=True)
    secret = d / f"{name}.asc"
    secret.write_bytes(subprocess.run(["gpg", "--batch", "--armor", "--export-secret-keys"], env=env,
                                      check=True, capture_output=True).stdout)
    public = subprocess.run(["gpg", "--export"], env=env, check=True, capture_output=True).stdout
    out = subprocess.run(["gpg", "--list-keys", "--with-colons"], env=env, check=True, capture_output=True,
                         text=True).stdout
    return secret, public, next(line.split(":")[9] for line in out.splitlines() if line.startswith("fpr"))


def build_deb(d: Path, package="deneme-uygulama", version="1.0", arch="all", key=None, secret=None,
              depends="", desktop=True) -> Path:
    """key: pakete gömülecek açık anahtarlık; secret: imzalanacaksa gizli anahtar dosyası."""
    root = d / f"kok-{package}-{version}-{os.getpid()}-{len(list(d.iterdir()))}"
    (root / "DEBIAN").mkdir(parents=True)
    (root / f"usr/share/{package}").mkdir(parents=True)
    (root / f"usr/share/{package}/surum").write_text(version + "\n")
    if desktop:
        (root / "usr/share/applications").mkdir(parents=True)
        (root / f"usr/share/applications/lab.deneme.{package}.desktop").write_text(
            "[Desktop Entry]\nType=Application\nName=Deneme Uygulaması\nName[tr]=Deneme Uygulaması\n"
            f"Exec=true\nIcon=lab.deneme.{package}\n")
        (root / "usr/share/icons/hicolor/scalable/apps").mkdir(parents=True)
        (root / f"usr/share/icons/hicolor/scalable/apps/lab.deneme.{package}.svg").write_bytes(ICON)
    if key:
        (root / "usr/share/keyrings").mkdir(parents=True)
        (root / f"usr/share/keyrings/{package}-paket.gpg").write_bytes(key)
    ctl = (f"Package: {package}\nVersion: {version}\nArchitecture: {arch}\n"
           "Maintainer: Deneme <deneme@x.invalid>\nHomepage: https://example.invalid\n"
           "Description: Deneme paketi\n Uzun açıklama.\n .\n İkinci paragraf.\n")
    if depends:
        ctl += f"Depends: {depends}\n"
    (root / "DEBIAN/control").write_text(ctl)
    out = d / f"{package}_{version}_{arch}-{len(list(d.iterdir()))}.deb"
    subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(root), str(out)], check=True,
                   capture_output=True)
    if secret:
        imzala.sign(str(out), str(secret))
    return out
