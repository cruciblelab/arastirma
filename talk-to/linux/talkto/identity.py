"""Kendinden imzalı TLS sertifikası: ilk açılışta bir kez üretilir.

Telefon bu sertifikanın SHA-256 parmak izini ilk bağlantıda kaydeder ve
sonraki bağlantılarda değişmişse bağlanmayı reddeder.
"""

import datetime
import hashlib
import os
import ssl
import subprocess
from pathlib import Path


class Identity:
    def __init__(self, directory: Path, common_name: str):
        self.cert_path = Path(directory) / "sertifika.pem"
        self.key_path = Path(directory) / "anahtar.pem"
        if not (self.cert_path.exists() and self.key_path.exists()):
            Path(directory).mkdir(parents=True, exist_ok=True)
            _generate(self.cert_path, self.key_path, common_name)
        der = ssl.PEM_cert_to_DER_cert(self.cert_path.read_text())
        self.fingerprint = hashlib.sha256(der).hexdigest()

    def server_context(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(self.cert_path, self.key_path)
        return ctx


def _generate(cert_path: Path, key_path: Path, cn: str):
    try:
        _generate_cryptography(cert_path, key_path, cn)
    except ImportError:
        _generate_openssl(cert_path, key_path, cn)
    os.chmod(key_path, 0o600)


def _generate_cryptography(cert_path, key_path, cn):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn[:64] or "talkto")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650 * 3))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _generate_openssl(cert_path, key_path, cn):
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
         "-nodes", "-days", "10950", "-subj", f"/CN={cn[:64] or 'talkto'}",
         "-keyout", str(key_path), "-out", str(cert_path)],
        check=True, capture_output=True,
    )
