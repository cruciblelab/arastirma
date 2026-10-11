""".deb imzası (paket/deb-imzala.py): imzala, doğrula, kurcalanmış paket ve yanlış anahtar.

gpg, gpgv ve dpkg-deb ister; yoksa atlanır.
"""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("deb_imzala", HERE / "paket" / "deb-imzala.py")
imza = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imza)

HAVE = all(shutil.which(t) for t in ("gpg", "gpgv", "dpkg-deb"))


def make_key(d: Path, name: str):
    home = d / f"gpg-{name}"
    home.mkdir(mode=0o700)
    env = dict(os.environ, GNUPGHOME=str(home))
    subprocess.run(["gpg", "--batch", "--quiet", "--passphrase", "", "--quick-gen-key", f"{name} <{name}@x.invalid>",
                    "ed25519", "sign", "never"], env=env, check=True, capture_output=True)
    secret, public = d / f"{name}.asc", d / f"{name}.gpg"
    secret.write_bytes(subprocess.run(["gpg", "--batch", "--armor", "--export-secret-keys"], env=env,
                                      check=True, capture_output=True).stdout)
    public.write_bytes(subprocess.run(["gpg", "--export"], env=env, check=True, capture_output=True).stdout)
    fpr = subprocess.run(["gpg", "--list-keys", "--with-colons"], env=env, check=True,
                         capture_output=True, text=True).stdout
    return secret, public, next(line.split(":")[9] for line in fpr.splitlines() if line.startswith("fpr"))


@unittest.skipUnless(HAVE, "gpg, gpgv ya da dpkg-deb yok")
class DebSignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.secret, cls.public, cls.fpr = make_key(cls.dir, "yayinci")
        _, cls.other_public, _ = make_key(cls.dir, "baskasi")

    def build(self, version="1.0") -> Path:
        root = self.dir / f"kok-{version}"
        (root / "DEBIAN").mkdir(parents=True, exist_ok=True)
        (root / "usr/share/deneme").mkdir(parents=True, exist_ok=True)
        (root / "usr/share/deneme/dosya").write_text("merhaba\n")
        (root / "DEBIAN/control").write_text(f"Package: deneme\nVersion: {version}\nArchitecture: all\n"
                                             "Maintainer: x <x@x.invalid>\nDescription: deneme\n")
        out = self.dir / f"deneme_{version}_all.deb"
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(root), str(out)], check=True,
                       capture_output=True)
        return out

    def test_sign_and_verify(self):
        deb = self.build()
        with self.assertRaisesRegex(ValueError, "imzasız"):
            imza.verify(str(deb), str(self.public))
        imza.sign(str(deb), str(self.secret))
        self.assertEqual(imza.verify(str(deb), str(self.public)), self.fpr)
        # dpkg imza parçasını yok sayar: paket hâlâ okunur.
        info = subprocess.run(["dpkg-deb", "-f", str(deb), "Version"], capture_output=True, text=True, check=True)
        self.assertEqual(info.stdout.strip(), "1.0")
        # Yeniden imzalamak ikinci bir imza parçası eklemez.
        imza.sign(str(deb), str(self.secret))
        names = [n for n, _ in imza.read_ar(deb.read_bytes())]
        self.assertEqual(names.count(imza.SIG), 1)

    def test_wrong_key_and_tampering(self):
        deb = self.build("2.0")
        imza.sign(str(deb), str(self.secret))
        with self.assertRaisesRegex(ValueError, "tutmuyor"):
            imza.verify(str(deb), str(self.other_public))
        members = imza.read_ar(deb.read_bytes())
        members = [(n, b + b"x" if n.startswith("data.tar") else b) for n, b in members]
        deb.write_bytes(imza.write_ar(members))
        with self.assertRaisesRegex(ValueError, "tutmuyor"):
            imza.verify(str(deb), str(self.public))


if __name__ == "__main__":
    unittest.main()
