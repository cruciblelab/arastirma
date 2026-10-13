"""Eşleştirme ve kimlik doğrulama hesapları (PROTOCOL.md, "4. Handshake and authentication").

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


# Şifre anahtarı türetme turları: sahte bir sunucu kanıtı ele geçirse bile şifreyi çevrimdışı
# denemesi yavaş olsun. Android (Auth.kt) aynı değeri kullanır.
PBKDF2_ROUNDS = 100_000
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def password_key(password: str, server_fp: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), f"talkto:{server_fp}".encode("utf-8"),
                               PBKDF2_ROUNDS, 32)


def password_proof2(password: str, nonce: str, server_fp: str) -> str:
    """Sürüm 2: HMAC-SHA256(anahtar=PBKDF2(şifre, "talkto:parmakizi"), ileti="nonce:parmakizi")."""
    msg = f"{nonce}:{server_fp}".encode("utf-8")
    return hmac.new(password_key(password, server_fp), msg, hashlib.sha256).hexdigest()


def valid_commit(value) -> bool:
    return isinstance(value, str) and bool(_HEX64.match(value))


def commit_of(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def pairing_code2(nonce: str, secret: str, server_fp: str, device_id: str) -> str:
    """Sürüm 2 onay kodu: telefonun rastgele değeri (önceden taahhüt edilmiş) koda girer.

    Telefon hello'da SHA-256(secret)'i yollar, bilgisayarın nonce'unu gördükten sonra secret'i
    açıklar. Araya giren biri nonce'u telefonun değerini bilmeden seçmek zorunda kaldığından
    iki ekranda aynı kodu ancak milyonda bir şansla tutturabilir.
    """
    d = hashlib.sha256(f"{nonce}:{secret}:{server_fp}:{device_id}".encode("utf-8")).digest()
    return f"{int.from_bytes(d[:4], 'big') % 1_000_000:06d}"


def new_qr_key() -> str:
    return secrets.token_hex(16)


def qr_proof(key: str, nonce: str, server_fp: str, device_id: str) -> str:
    """Karekodla eşleşme: HMAC-SHA256(anahtar=karekoddaki anahtar, ileti="qr:nonce:parmakizi:device_id").

    Anahtar ağdan hiç gitmez. Parmak izi iletiye girdiği için araya giren biri (kendi sertifikasıyla)
    aldığı kanıtı gerçek bilgisayara aktaramaz; nonce her bağlantıda yeni olduğu için tekrar oynatılamaz.
    """
    msg = f"qr:{nonce}:{server_fp}:{device_id}".encode("utf-8")
    return hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


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
