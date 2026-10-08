"""
Karşılaştırma için referans anatomi çizimleri: indir, SHA-256 ile doğrula. Görseller repoya konmaz (.veri/ önbelleği).

Kaynak: Henry Gray, Anatomy of the Human Body, 20. baskı (1918). Kamu malı; Wikimedia Commons üzerinden.
Commons'ta dosyanın özgün sürümü indirilir (küçük resim değil), böylece özet değişmez.
"""

import hashlib
import urllib.request
from pathlib import Path

ONBELLEK = Path(__file__).resolve().parents[3] / ".veri" / "gray1918"

KAYNAKLAR = {
    "gray966": dict(dosya="Gray966.png", sha256="327fcfe5218f7b0c467a8184872559f592b5bfbfacb509c8f9011848b659fd5f",
                    aciklama="Fig. 966: göğüs kafesi, önden-yandan (kaburga eğimi, kıkırdaklar, kaburga kavsi)"),
    "gray115": dict(dosya="Gray115.png", sha256="58c26a85d58f0594dbd405d2a3c6d8305b9258e0883123d6d91f35cd66a013a6",
                    aciklama="Fig. 115: göğüs kemiği ve kaburga kıkırdakları, önden"),
}


def indir(ad: str) -> Path:
    k = KAYNAKLAR[ad]
    ONBELLEK.mkdir(parents=True, exist_ok=True)
    hedef = ONBELLEK / k["dosya"]
    if not hedef.exists():
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{k['dosya']}"
        # Wikimedia, açıklayıcı olmayan User-Agent ile gelen istekleri 429 ile reddediyor
        istek = urllib.request.Request(url, headers={"User-Agent": "arastirma-iskelet/1.0 (https://github.com/cruciblelab/arastirma; egitim amacli)"})
        with urllib.request.urlopen(istek, timeout=60) as r:
            hedef.write_bytes(r.read())
    ozet = hashlib.sha256(hedef.read_bytes()).hexdigest()
    if ozet != k["sha256"]:
        hedef.unlink()
        raise RuntimeError(f"{ad}: SHA-256 uyuşmuyor ({ozet}); dosya silindi.")
    return hedef
