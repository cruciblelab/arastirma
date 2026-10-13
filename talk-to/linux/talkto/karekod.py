"""Karekodla eşleşme: bilgisayar ekranında gösterilen bağlantı ve onun karekodu.

Karekodda telefonun bağlanması için gereken her şey var: adresler, port, bilgisayarın güvenlik kodu
(sertifika parmak izi) ve tek kullanımlık bir anahtar. Telefon bilgisayara bağlanır, parmak izini
karekoddakiyle karşılaştırır ve anahtarı bildiğini kanıtlar (anahtarın kendisi ağdan gitmez); bilgisayar
da ekranda onay sormadan eşleşir. Anahtarı ancak ekranı gören bilebilir; süresi kısadır ve bir kez geçer.

    talkto://pair?v=1&h=192.168.1.34,10.0.0.5&p=47600&fp=<64 hex>&k=<32 hex>&n=<bilgisayarın adı>
"""

import ipaddress
from urllib.parse import quote

from .ucuncu.qrcodegen import QrCode

SCHEME = "talkto://pair"
SECONDS = 600  # karekod (anahtar) 10 dakika geçerli
MAX_HOSTS = 6


def _rank(addr: str) -> int:
    """Telefonun önce deneyeceği adresler: ev/iş ağı önce; Tailscale sonra; sanal köprüler (Docker) en son."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return 9
    if ip in ipaddress.ip_network("172.17.0.0/16") or ip in ipaddress.ip_network("192.168.122.0/24"):
        return 5  # Docker ve libvirt'in varsayılan köprüleri: telefon oraya ulaşamaz
    if ip in ipaddress.ip_network("100.64.0.0/10"):
        return 3
    if ip.is_private:
        return 0
    return 4  # internetteki adres


def hosts(addresses: list[str]) -> list[str]:
    seen = []
    for a in sorted(addresses, key=_rank):
        if a not in seen and _rank(a) != 4 and _rank(a) < 9:  # internet adresi: telefon zaten kabul etmez
            seen.append(a)
    return seen[:MAX_HOSTS]


def link(addresses: list[str], port: int, fp: str, key: str, name: str) -> str:
    return (f"{SCHEME}?v=1&h={','.join(hosts(addresses))}&p={int(port)}&fp={fp}&k={key}"
            f"&n={quote(name[:40], safe='')}")


def matrix(text: str) -> list[list[bool]]:
    """Karekodun kareleri (satır satır; True: koyu). Kenar boşluğu eklenmez."""
    qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    n = qr.get_size()
    return [[qr.get_module(x, y) for x in range(n)] for y in range(n)]
