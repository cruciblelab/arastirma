"""
Veri kaynakları: indir, SHA-256 ile doğrula, oku. Ham veri repoya konmaz (.veri/ önbelleği).

1) Berkeley Child Guidance Study (R sitar paketi): boy + oturma boyu (gövde), 9-21 yaş
2) Günöz ve ark. 2014 Türk boy referansı (JCRPE PDF): yaşa göre ortalama ve SD
3) Galton aileleri (R HistData paketi): anne-baba ve çocuk erişkin boyu
"""

import hashlib
import re
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ONBELLEK = Path(__file__).parent / ".veri"

KAYNAKLAR = {
    "sitar": dict(
        urller=["https://cran.r-project.org/src/contrib/sitar_1.5.0.tar.gz",
                "https://cran.r-project.org/src/contrib/Archive/sitar/sitar_1.5.0.tar.gz"],
        sha256="312466b96e1a38fea4d4bc591f91c69dfe7b425fb92aef9ccd02db00c40b97c5",
        dosya="sitar_1.5.0.tar.gz"),
    "histdata": dict(
        urller=["https://cran.r-project.org/src/contrib/HistData_1.1.1.tar.gz",
                "https://cran.r-project.org/src/contrib/Archive/HistData/HistData_1.1.1.tar.gz"],
        sha256="b602f00c07c1d954dba8a00bd4d772aa3f9188554c772f6f677d91a3000ce702",
        dosya="HistData_1.1.1.tar.gz"),
    "turk_referans": dict(
        urller=["https://jcrpe.org/pdf/cf9d60d6-523c-458a-a2e6-78728d3ffbb0/articles/Jcrpe.1260/JCRPE-6-28-En.pdf"],
        sha256="c76b81bc388d06554464f92d217d97f21231842bddef520546b8fbe169823f66",
        dosya="gunoz2014.pdf"),
}


def _indir(ad: str) -> Path:
    k = KAYNAKLAR[ad]
    ONBELLEK.mkdir(exist_ok=True)
    hedef = ONBELLEK / k["dosya"]
    if not hedef.exists():
        son = None
        for url in k["urller"]:
            try:
                istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(istek, timeout=60) as r:
                    hedef.write_bytes(r.read())
                break
            except Exception as e:
                son = e
        else:
            raise RuntimeError(f"{ad} indirilemedi: {son}")
    ozet = hashlib.sha256(hedef.read_bytes()).hexdigest()
    if ozet != k["sha256"]:
        hedef.unlink()
        raise RuntimeError(f"{ad}: SHA-256 uyuşmuyor ({ozet}); dosya silindi.")
    return hedef


def _rda(paket: str, uye: str, ad: str):
    import pyreadr
    hedef = ONBELLEK / f"{ad}.rda"
    if not hedef.exists():
        with tarfile.open(_indir(paket)) as tf:
            hedef.write_bytes(tf.extractfile(tf.getmember(uye)).read())
    return list(pyreadr.read_r(str(hedef)).values())[0]


def berkeley() -> pd.DataFrame:
    """Uzun tablo: id, cinsiyet, yas, boy, govde (oturma boyu), bacak."""
    d = _rda("sitar", "sitar/data/berkeley.rda", "berkeley")
    d = d.dropna(subset=["height"])
    out = pd.DataFrame({
        "id": d["id"].astype(str),
        "cinsiyet": d["sex"].astype(str).map({"1": "erkek", "2": "kiz"}),
        "yas": d["age"].astype(float),
        "boy": d["height"].astype(float),
        "govde": d["stem.length"].astype(float),
    })
    out["bacak"] = out.boy - out.govde
    return out.sort_values(["id", "yas"]).reset_index(drop=True)


def turk_referans() -> pd.DataFrame:
    """Günöz 2014, Tablo 1 (erkek) ve 2 (kız): yas, n, sd, ortalama.

    PDF'teki bilinen dizgi hatası: kız 16.0 yaş '0 SDS' sütunu 152.4 yazılmış;
    -1 SDS (156.5) + SD (5.90) = 162.4 olduğundan düzeltilir. Düzeltme her
    satırda tutarlılık kontrolüyle (ortalama ≈ -1SDS + SD) doğrulanır.
    """
    from pypdf import PdfReader
    metin = "\n".join(p.extract_text() for p in PdfReader(str(_indir("turk_referans"))).pages)
    satirlar = [s.split() for s in metin.splitlines()
                if re.match(r"^\s*\d{1,2}\.\d\s+\d+\s+\d\.\d\d\s", s)]
    if len(satirlar) != 50:
        raise RuntimeError(f"Türk referansı ayrıştırılamadı ({len(satirlar)} satır, 50 bekleniyordu)")
    kayit = []
    for i, s in enumerate(satirlar):
        yas, n, sd = float(s[0]), int(s[1]), float(s[2])
        eksi1, ort = float(s[5]), float(s[6])
        cins = "erkek" if i < 25 else "kiz"
        duzeltildi = False
        if abs((eksi1 + sd) - ort) > 0.3:
            ort = round(eksi1 + sd, 1)
            duzeltildi = True
        kayit.append(dict(cinsiyet=cins, yas=yas, n=n, sd=sd, ortalama=ort, duzeltildi=duzeltildi))
    return pd.DataFrame(kayit)


def galton() -> pd.DataFrame:
    g = _rda("histdata", "HistData/data/GaltonFamilies.RData", "galton")
    return pd.DataFrame({
        "aile": g["family"].astype(str),
        "baba": g["father"].astype(float) * 2.54,
        "anne": g["mother"].astype(float) * 2.54,
        "cinsiyet": g["gender"].astype(str).map({"male": "erkek", "female": "kiz"}),
        "boy": g["childHeight"].astype(float) * 2.54,
    })


YASLAR = np.round(np.arange(9.0, 21.01, 0.5), 2)


def berkeley_matris(d: pd.DataFrame, cinsiyet: str):
    """9-21 yaş yarım yıllık ızgarada bacak/gövde matrisleri (bireyler x yaşlar)."""
    x = d[(d.cinsiyet == cinsiyet) & (d.yas >= 9.0)].dropna(subset=["govde"])
    ids = sorted(x.id.unique())
    B = x.pivot_table(index="id", columns="yas", values="bacak").reindex(index=ids, columns=YASLAR)
    G = x.pivot_table(index="id", columns="yas", values="govde").reindex(index=ids, columns=YASLAR)
    return ids, B.values, G.values


if __name__ == "__main__":
    print(berkeley().groupby("cinsiyet").id.nunique())
    t = turk_referans()
    print(t[t.duzeltildi])
    print(t[t.yas.isin([16.0, 18.0])])
    print(galton().groupby("cinsiyet").size())
