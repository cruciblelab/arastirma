"""
Berkeley Child Guidance Study verisini indirir ve okur.

Kaynak: R paketi `sitar` (Cole TJ, CRAN), veri seti `berkeley`.
136 çocuk (66 erkek, 70 kız), Berkeley/Kaliforniya, 1928-29 doğumlu, kuzey Avrupa
kökenli; doğumdan 21 yaşa kadar, 8-21 yaş arası 6 ayda bir ölçüm.
Orijinal yayın: Tuddenham RD, Snyder MM (1954), Univ Calif Publ Child Dev 1:183-364.

Ham veri repoya konmaz; ilk çalıştırmada CRAN'dan indirilir, SHA-256 ile
doğrulanır ve .veri/ altına önbelleğe alınır.
"""

import hashlib
import tarfile
import urllib.request
from pathlib import Path

import pandas as pd

SURUM = "1.5.0"
SHA256 = "312466b96e1a38fea4d4bc591f91c69dfe7b425fb92aef9ccd02db00c40b97c5"
URLLER = [
    f"https://cran.r-project.org/src/contrib/sitar_{SURUM}.tar.gz",
    f"https://cran.r-project.org/src/contrib/Archive/sitar/sitar_{SURUM}.tar.gz",
]
ONBELLEK = Path(__file__).parent / ".veri"


def _indir() -> Path:
    ONBELLEK.mkdir(exist_ok=True)
    hedef = ONBELLEK / f"sitar_{SURUM}.tar.gz"
    if not hedef.exists():
        son_hata = None
        for url in URLLER:
            try:
                urllib.request.urlretrieve(url, hedef)
                break
            except Exception as e:  # bir sonraki adresi dene
                son_hata = e
        else:
            raise RuntimeError(f"sitar indirilemedi: {son_hata}")
    ozet = hashlib.sha256(hedef.read_bytes()).hexdigest()
    if ozet != SHA256:
        hedef.unlink()
        raise RuntimeError(f"SHA-256 uyuşmuyor ({ozet}); dosya silindi, veri doğrulanamadı.")
    return hedef


def berkeley() -> pd.DataFrame:
    """id, cinsiyet ('erkek'/'kiz'), yas, boy sütunlu uzun tablo (boyu olan satırlar)."""
    import pyreadr

    rda = ONBELLEK / "berkeley.rda"
    if not rda.exists():
        with tarfile.open(_indir()) as tf:
            uye = tf.getmember("sitar/data/berkeley.rda")
            rda.write_bytes(tf.extractfile(uye).read())
    d = pyreadr.read_r(str(rda))["berkeley"]
    d = d.dropna(subset=["height"])
    out = pd.DataFrame({
        "id": d["id"].astype(str),
        "cinsiyet": d["sex"].astype(str).map({"1": "erkek", "2": "kiz"}),
        "yas": d["age"].astype(float),
        "boy": d["height"].astype(float),
    })
    return out.sort_values(["id", "yas"]).reset_index(drop=True)


if __name__ == "__main__":
    df = berkeley()
    print(df.groupby("cinsiyet").id.nunique())
    print(df.head())
