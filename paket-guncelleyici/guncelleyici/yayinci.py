"""Yayıncı bilgisi: paketi kim yayımlıyor, nasıl ulaşılır, ve bu anahtar gerçekten onun mu?

Paket, imzalayan anahtarın yanında kısa bir yayıncı kartı taşır:
/usr/share/keyrings/<paket>-paket.json

    {"yayinci": "Crucible ekibi",                     zorunlu: kişi ya da ekip adı
     "kurum": "...", "yetkili": "...",                isteğe bağlı
     "web": "https://...",                            yayıncının sitesi
     "iletisim": "https://.../issues" ya da e-posta,
     "dogrulama": "https://.../YAYINCI.txt"}          parmak izini yayımlayan sayfa

Kart veri arşivinin içinde olduğu için imzanın kapsamındadır: imzalı pakette sonradan değiştirilemez.
Ama içindeki her şey yayıncının **kendi beyanıdır**; herkes pakete "Mozilla" yazabilir. Bunu bağlayan
tek şey **site doğrulaması**: "dogrulama" adresindeki sayfa imzanın parmak izini içeriyorsa, o adresi
yöneten kişi bu anahtarı kendisininmiş gibi yayımlıyor demektir (sertifika yerine web sitesinin
kendisi). Doğrulama adresi web sitesiyle aynı yerde değilse ayrıca söylenir.
"""

import json
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ALANLAR = ("yayinci", "kurum", "yetkili", "web", "iletisim", "dogrulama")
EN_COK_KART = 16 * 1024
EN_COK_SAYFA = 64 * 1024

DOGRULANDI, LISTEDE_YOK, ULASILAMADI = "dogrulandi", "listede_yok", "ulasilamadi"


@dataclass
class Kart:
    yayinci: str
    kurum: str = ""
    yetkili: str = ""
    web: str = ""
    iletisim: str = ""
    dogrulama: str = ""


@dataclass
class Dogrulama:
    state: str
    url: str
    detail: str = ""
    same_site: bool = True  # doğrulama adresi web sitesiyle aynı yerde mi


def json_path(package: str) -> str:
    return f"usr/share/keyrings/{package}-paket.json"


def _https(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and bool(parts.hostname) and not parts.username and not parts.password


def _email(text: str) -> bool:
    return bool(re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", text))


def parse(data: bytes | None) -> Kart | None:
    """Bozuk, aşırı büyük ya da adsız kart yok sayılır; geçersiz adresler boş bırakılır."""
    if not data or len(data) > EN_COK_KART:
        return None
    try:
        raw = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    clean = {}
    for k in ALANLAR:
        v = raw.get(k)
        if isinstance(v, str):
            clean[k] = " ".join("".join(ch for ch in v if ch.isprintable()).split())[:200]
    if not clean.get("yayinci"):
        return None
    for k in ("web", "dogrulama"):
        if clean.get(k) and not _https(clean[k]):
            clean[k] = ""
    if clean.get("iletisim") and not (_https(clean["iletisim"]) or _email(clean["iletisim"])):
        clean["iletisim"] = ""
    return Kart(**clean)


def installed(package: str, owned_by) -> Kart | None:
    """Kurulu sürümün kartı (yalnızca o pakete aitse)."""
    path = Path("/") / json_path(package)
    if not path.is_file() or not owned_by(path, package):
        return None
    try:
        return parse(path.read_bytes())
    except OSError:
        return None


def changed(old: Kart | None, new: Kart | None) -> list[str]:
    """Kurulu sürümden bu yana değişen önemli alanlar (yayıncı değişimi işareti)."""
    if not old or not new:
        return []
    names = {"yayinci": "ad", "web": "web sitesi", "dogrulama": "doğrulama adresi"}
    return [names[k] for k in names if getattr(old, k) != getattr(new, k)]


def _site(host: str) -> str:
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def same_site(web: str, url: str) -> bool:
    """Doğrulama adresi web sitesinin kendisinde (ya da alt alanında) mı?

    GitHub'da site github.com/<sahip>; aynı sahibin raw.githubusercontent.com/<sahip> ve
    <sahip>.github.io adresleri de aynı yer sayılır.
    """
    if not web or not url:
        return False
    w, u = urlsplit(web), urlsplit(url)
    wh, uh = _site(w.hostname or ""), _site(u.hostname or "")
    if wh == "github.com":
        owner = (w.path.strip("/").split("/") or [""])[0].lower()
        if not owner:
            return False
        first = (u.path.strip("/").split("/") or [""])[0].lower()
        return (uh in ("github.com", "raw.githubusercontent.com") and first == owner) or uh == f"{owner}.github.io"
    return uh == wh or uh.endswith("." + wh)


def short_url(url: str) -> str:
    p = urlsplit(url)
    return (p.hostname or "") + (p.path if p.path not in ("", "/") else "")


def lists(text: str, fingerprint: str) -> bool:
    """Sayfa parmak izini içeriyor mu (boşluk ve büyük/küçük harf fark etmez)."""
    flat = re.sub(r"\s+", "", text).upper()
    return bool(fingerprint) and fingerprint.upper() in flat


class _OnlyHttps(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _https(newurl):
            raise urllib.error.URLError("güvenli olmayan adrese yönlendirdi")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify(url: str, fingerprint: str, web: str = "", timeout: float = 8,
           context: ssl.SSLContext | None = None) -> Dogrulama:
    """Doğrulama sayfasını indirir (yalnızca https, en çok 64 KB) ve parmak izini arar."""
    result = Dogrulama(ULASILAMADI, url, same_site=same_site(web, url))
    if not _https(url):
        result.detail = "adres https değil"
        return result
    opener = urllib.request.build_opener(_OnlyHttps, urllib.request.HTTPSHandler(context=context))
    req = urllib.request.Request(url, headers={"User-Agent": "paket-guncelleyici"})
    try:
        with opener.open(req, timeout=timeout) as res:
            body = res.read(EN_COK_SAYFA + 1)
    except urllib.error.HTTPError as e:
        result.detail = f"sayfa bulunamadı ({e.code})" if e.code == 404 else f"site {e.code} döndü"
        return result
    except (urllib.error.URLError, OSError, ValueError) as e:
        reason = getattr(e, "reason", e)
        result.detail = "zaman aşımı" if "timed out" in str(reason) else str(reason)
        return result
    if len(body) > EN_COK_SAYFA:
        result.detail = "sayfa çok büyük"
        return result
    result.state = DOGRULANDI if lists(body.decode("utf-8", "replace"), fingerprint) else LISTEDE_YOK
    return result
