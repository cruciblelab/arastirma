"""
ÖN KAYITSIZ KEŞİF ANALİZLERİ (README "Bulgular", bölüm 5). calistir.py'den SONRA, 3. aşamadaki bağımsız yeniden analiz
ve şeytanın avukatı ajanlarının itirazlarını kontrol etmek için yazıldı. Sonuçları ön kayıtlı kararlar gibi okunmamalı.

    python kesif.py      (önce calistir.py çalışmış olmalı: veriler .veri/cekicilik/ altında)

E1  UvA: 5 cm boyun etkisi, kadının kendi boyuna göre gruplar
E2  UvA: "profil kadından uzun" göstergesi (doğrusal boy sabitken)
E3  UvA: SS başına adil karşılaştırma: 1 SS fotoğraf ↔ 7 cm boy (≈ 1 erkek boy SS'si) ↔ 15 IQ
E4  MA: tasarım aralığının ucundan ucuna (±2 nüfus SS) omuz-kalça ve boy etkisi
E5  KO: her beden özelliği tek başına (yalnız yaş sabit) SOI-R davranışı yordar mı?
"""

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
V = KOK.parents[2] / ".veri" / "cekicilik"
CIKTI = KOK / "ciktilar"
rng = np.random.default_rng(20261024)
BOOT = 2000
SATIR = []


def kisi_ici(df, grup, y, terimler):
    xc = df[terimler] - df.groupby(grup)[terimler].transform("mean")
    yc = df[y] - df.groupby(grup)[y].transform("mean")
    benzersiz, idx = np.unique(df[grup].to_numpy(), return_inverse=True)
    X, yv = xc.to_numpy(float), yc.to_numpy(float)
    k = X.shape[1]
    xtx = np.zeros((len(benzersiz), k, k))
    xty = np.zeros((len(benzersiz), k))
    np.add.at(xtx, idx, X[:, :, None] * X[:, None, :])
    np.add.at(xty, idx, X * yv[:, None])
    b = np.linalg.solve(xtx.sum(0), xty.sum(0))
    ag = rng.multinomial(len(benzersiz), np.full(len(benzersiz), 1 / len(benzersiz)), size=BOOT).astype(float)
    dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty) for a in ag])
    return b, dg, len(benzersiz)


def ekle(analiz, terim, nokta, dg, n, not_=""):
    lo, hi = np.percentile(dg, [2.5, 97.5])
    SATIR.append(dict(analiz=analiz, terim=terim, deger=nokta, lo=lo, hi=hi, n=n, not_=not_))
    print(f"{analiz:3s} {terim:45s} {nokta:8.3f} [{lo:7.3f}, {hi:7.3f}]  n={n} {not_}")


def havuz_z(s):
    v = np.unique(s.to_numpy(float))
    return (s - v.mean()) / v.std(ddof=1)


# ---------------------------------------------------------------- UvA
u = pd.read_csv(V / "uva_conjoint_kadin.csv", sep=";", decimal=",", encoding="utf-8-sig")
u["secildi"] = u.Response * 100.0
u["cek"], u["bio"], u["mes"] = havuz_z(u.Attractiveness), havuz_z(u.Bio), havuz_z(u.Occupation)
u["boy5"] = (u.Height - 180) / 5
u["iq15"] = (u.Intelligence - 100) / 15
L = ["cek", "boy5", "iq15", "bio", "mes"]

# E1
kb = u["Height.in.cm"]
for ad, maske in (("< 163 cm", kb < 163), ("163-169 cm", (kb >= 163) & (kb < 170)), (">= 170 cm", kb >= 170),
                  (">= 175 cm", kb >= 175)):
    b, dg, n = kisi_ici(u[maske], "Participants", "secildi", L)
    taban = u[maske].Response.mean() * 100
    ekle("E1", f"5 cm boy, kadın boyu {ad}", b[1], dg[:, 1], n, f"taban %{taban:.1f}")

# E2
u["uzun_mu"] = (u.Height > u["Height.in.cm"]).astype(float)
b, dg, n = kisi_ici(u, "Participants", "secildi", L + ["uzun_mu"])
ekle("E2", "profil kadından uzun (doğrusal boy sabit)", b[-1], dg[:, -1], n,
     f"profillerin %{(1 - u.uzun_mu.mean()) * 100:.1f}'i kadından uzun değil")

# E3
b, dg, n = kisi_ici(u, "Participants", "secildi", L)
boy7 = dg[:, 1] * 7 / 5
ekle("E3", "1 SS fotoğraf çekiciliği (yp)", b[0], dg[:, 0], n)
ekle("E3", "7 cm boy (yp)", b[1] * 7 / 5, boy7, n)
ekle("E3", "15 IQ (yp)", b[2], dg[:, 2], n)
oran = dg[:, 0] / boy7
pozitif = boy7 > 0
ekle("E3", "oran: fotoğraf / 7 cm boy (yalnız boy > 0 örnekler)", b[0] / (b[1] * 7 / 5), oran[pozitif], n,
     f"bootstrap örneklerinin %{pozitif.mean() * 100:.0f}'inde boy > 0")

# ---------------------------------------------------------------- MA
with zipfile.ZipFile(V / "aich2026_s1.zip") as z:
    ad_x = [x for x in z.namelist() if x.endswith("HumanStudyData.xlsx")][0]
    ma = pd.read_excel(io.BytesIO(z.read(ad_x)), sheet_name="inperson_female_attractiveness")
ma = ma.dropna(subset=["rating"]).copy()
ma["fh"] = ma.figheight.astype(float)
ma["fh_alt"], ma["fh_ust"] = np.minimum(ma.fh, 0), np.maximum(ma.fh, 0)
M1 = ["zShape", "qshape", "zpenis", "qpenis", "fh_alt", "fh_ust"]
b, dg, n = kisi_ici(ma, "participant", "rating", M1)
zs_lo, zs_hi = ma.zShape.min(), ma.zShape.max()


def sekil(bb, z):
    return bb[..., 0] * z + bb[..., 1] * z ** 2


aralik_sekil = sekil(b, zs_hi) - sekil(b, zs_lo)
aralik_sekil_dg = sekil(dg, zs_hi) - sekil(dg, zs_lo)
aralik_boy = 2 * b[5] + 2 * b[4]
aralik_boy_dg = 2 * dg[:, 5] + 2 * dg[:, 4]
ekle("E4", "omuz-kalça: en düşük → en yüksek düzey (puan)", aralik_sekil, aralik_sekil_dg, n)
ekle("E4", "boy: 163 → 187 cm (puan)", aralik_boy, aralik_boy_dg, n)
ekle("E4", "oran: omuz-kalça / boy (uçtan uca)", aralik_sekil / aralik_boy, aralik_sekil_dg / aralik_boy_dg, n)
ekle("E4", "boy: 175 → 187 cm (puan)", 2 * b[5], 2 * dg[:, 5], n)
ekle("E4", "boy: 163 → 175 cm (puan)", 2 * b[4], 2 * dg[:, 4], n)

# ---------------------------------------------------------------- KO
ko = pd.read_csv(V / "kordsmeyer2018.csv", sep=";", decimal=",", encoding="utf-8-sig")
OZ = {"height": "boy", "facial.attract": "yüz çekiciliği", "bodily.attract": "beden çekiciliği",
      "physicalstrength_mean": "kuvvet", "upperbodysize": "üst beden büyüklüğü (3B tarama)"}
for c in list(OZ) + ["AgeT1", "SOIbehaviour"]:
    ko[c] = pd.to_numeric(ko[c].astype(str).str.strip().str.replace(",", ".", regex=False), errors="coerce")
for c, ad in OZ.items():
    g = ko.dropna(subset=[c, "AgeT1", "SOIbehaviour"])
    X = np.column_stack([np.ones(len(g)), *(((g[x] - g[x].mean()) / g[x].std()).to_numpy() for x in (c, "AgeT1"))])
    y = ((g.SOIbehaviour - g.SOIbehaviour.mean()) / g.SOIbehaviour.std()).to_numpy()
    bb = np.linalg.lstsq(X, y, rcond=None)[0]
    dgk = []
    for _ in range(BOOT):
        i = rng.integers(0, len(g), len(g))
        dgk.append(np.linalg.lstsq(X[i], y[i], rcond=None)[0][1])
    ekle("E5", f"SOI-R davranış ~ {ad} (+ yaş), SS", bb[1], np.array(dgk), len(g))

pd.DataFrame(SATIR).to_csv(CIKTI / "kesif.csv", index=False, float_format="%.3f")
(CIKTI / "kesif.json").write_text(json.dumps(SATIR, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
