"""Eşleştirme ve kimlik doğrulama hesapları (PROTOKOL.md, "Kimlik doğrulama").

Android tarafı (net/Auth.kt) aynı hesapları yapar; iki tarafın aynı sonucu
verdiği protokol/test-vektorleri.json ile denetlenir.
"""

import hashlib
import hmac
import re
import secrets

_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def new_nonce() -> str:
    return secrets.token_hex(16)


def new_token() -> str:
    return secrets.token_hex(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_proof(password: str, nonce: str, server_fp: str) -> str:
    """HMAC-SHA256(anahtar=şifre, ileti="nonce:parmakizi").

    Parmak izi iletiye girdiği için araya giren biri (kendi sertifikasıyla)
    aldığı kanıtı gerçek sunucuya aktaramaz.
    """
    msg = f"{nonce}:{server_fp}".encode("utf-8")
    return hmac.new(password.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def pairing_code(nonce: str, server_fp: str, device_id: str) -> str:
    """İki ekranda da gösterilen 6 haneli onay kodu.

    Telefon kodu kendi gördüğü sertifikadan hesaplar; araya giren biri varsa
    kodlar farklı çıkar.
    """
    d = hashlib.sha256(f"{nonce}:{server_fp}:{device_id}".encode("utf-8")).digest()
    return f"{int.from_bytes(d[:4], 'big') % 1_000_000:06d}"


def short_fingerprint(fp: str) -> str:
    """Ekranda karşılaştırmak için: 'A1B2 C3D4 E5F6 0718'."""
    s = fp[:16].upper()
    return " ".join(s[i:i + 4] for i in range(0, 16, 4))


def valid_device_id(value) -> bool:
    return isinstance(value, str) and bool(_ID.match(value))


def equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
