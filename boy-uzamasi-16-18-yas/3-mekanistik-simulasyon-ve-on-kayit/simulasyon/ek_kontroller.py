"""
Ön kayıtlı testlerden SONRA yapılan ek kontroller (keşifsel; hipotez testi yerine geçmez).
calistir.py'den sonra çalıştırılır:

    python ek_kontroller.py

1) Türk uyarlaması (erkek) kaldı: optimizasyon mu yetersizdi, model mi? Izgara taraması.
2) Ö6a katsayısı, uyarlamadaki zamanlama kaymasına duyarlı mı?
3) Ö7 kaldı: sanal kohortun 16→18 büyümesi Türk referansı ve Berkeley ile karşılaştırma.
"""

import glob
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from calistir import _dagilim, _ornekle
from model import simule_et
from veri import berkeley, berkeley_matris, turk_referans

KOK = Path(__file__).parent


def main():
    kal, _ = pickle.loads(Path(glob.glob(str(KOK / ".onbellek/kalibrasyon_tam_*.pkl"))[0]).read_bytes())
    d = berkeley()
    veri = {c: berkeley_matris(d, c)[1:] for c in ("erkek", "kiz")}
    uy = json.loads((KOK / "ciktilar/ozet.json").read_text(encoding="utf-8"))["D_uyarlama"]
    ref = turk_referans()
    sat = []

    # 1) Izgara taraması (erkek)
    c = "erkek"
    pop = kal[c][0]
    mu, kov = _dagilim(kal, veri, c)
    r = ref[(ref.cinsiyet == c) & (ref.yas >= 9) & (ref.yas <= 18)]
    Z = np.random.default_rng(200).standard_normal((4000, len(mu)))
    L = np.linalg.cholesky(kov)
    en_iyi = None
    for dTp in np.arange(-1.5, 1.51, 0.25):
        for olcek in (0.97, 0.975, 0.98, 0.985, 0.99, 0.995, 1.0):
            X = mu + Z @ L.T
            ind = dict(Gb=np.exp(X[:, 0]) * olcek, Gg=np.exp(X[:, 1]) * olcek, Tp=X[:, 2] + dTp,
                       Ap=np.clip(np.exp(X[:, 3]) - 0.5, 0, None))
            h = simule_et(ind, pop, np.exp(X[:, 4]) * olcek, np.exp(X[:, 5]) * olcek, t1=18.0,
                          kayit_yaslari=r.yas.values)["boy"].mean(1)
            e = float(np.sqrt(np.mean((h - r.ortalama.values) ** 2)))
            if en_iyi is None or e < en_iyi[0]:
                en_iyi = (e, float(dTp), olcek)
    sat.append(dict(kontrol="TR uyarlama erkek: ızgara en iyi RMSE (cm)", deger=en_iyi[0],
                    not_=f"dTp {en_iyi[1]:+.2f}, ölçek {en_iyi[2]:.3f}; optimizasyonun bulduğu RMSE {uy['erkek']['rmse']:.2f}"))

    # 2) ve 3)
    for c in ("erkek", "kiz"):
        pop = kal[c][0]
        mu, kov = _dagilim(kal, veri, c)
        kaymalar = [uy[c]["dTp"]] + ([en_iyi[1]] if c == "erkek" else [])
        tr = ref[ref.cinsiyet == c].set_index("yas").ortalama
        for dTp in kaymalar:
            ind, b0, g0 = _ornekle(mu, kov, 8000, np.random.default_rng(9), dTp, uy[c]["olcek"])
            H = simule_et(ind, pop, b0, g0, t1=30.0, kayit_yaslari=[14.0, 15.0, 16.0, 17.0, 18.0, 30.0])["boy"]
            g, gp, rr = H[2] - H[1], H[1] - H[0], H[5] - H[2]
            yav = g < gp
            sat.append(dict(kontrol=f"Ö6a katsayısı {c} 16 yaş, dTp {dTp:+.2f}",
                            deger=float(np.sum(g[yav] * rr[yav]) / np.sum(g[yav] ** 2)), not_=""))
            sat.append(dict(kontrol=f"Sanal kohort ort. 16→18 uzama {c}, dTp {dTp:+.2f} (cm)",
                            deger=float(np.mean(H[4] - H[2])),
                            not_=f"Türk referansı (kesitsel) {tr[18.0] - tr[16.0]:.2f}; Berkeley medyan "
                                 f"{'2.3' if c == 'erkek' else '0.7'}"))
    t = pd.DataFrame(sat)
    t.to_csv(KOK / "ciktilar/Ek_kontroller.csv", index=False, float_format="%.3f")
    print(t.to_string(index=False))


if __name__ == "__main__":
    main()
