"""
Kadınların boy beklentisi, sürüm 1: söylenen, seçilen, yaşanan (ön kayıt: PLAN.md). Tek komut:

    python calistir.py

Veri (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  PI  Pisanski ve ark. 2022, OSF ah97w: kendi boyu + tercih edilen partner boyu (4 ülke)
  UV  Witmer ve ark. 2025, OSF 84abw: UvA seçim deneyi (profil boyu 170-189 cm)
  SL  Sleiman, Melios ve Dolan 2025, Dataverse G1H0UA (CC0): ikili seçim deneyi (172,7 / 182,9 cm)
      Ham dosyada IP ve konum var: indirilir, gerekli sütunlar alınır, ham dosya silinir.
  BR  IBGE POF 2008-09 (Brezilya): ölçülmüş boy, hane ve aile içi konum
Analizler A1-A3, B1-B5, C1-C4; teknik testler T0-T4; hipotezler H1-H8; karar kuralları K1-K4. Çıktılar ciktilar/ altında.
"""

import hashlib
import io
import json
import re
import time
import urllib.request
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
VERI_DIZIN = REPO / ".veri" / "boy-beklentisi"
VERI_DIZIN.mkdir(parents=True, exist_ok=True)
TOHUM = 20261031
rng = np.random.default_rng(TOHUM)

TR_KADIN = (160.5, 6.62)   # TBSA 2017, 19-30 yaş, ölçüm
TR_ERKEK = (174.7, 6.88)
IST_KADIN = (164.3, 5.9)   # İstanbul üniversiteli kadınlar (duyarlılık)
BOYLAR = np.arange(168, 189)
Z176 = (176 - TR_ERKEK[0]) / TR_ERKEK[1]
Z178 = (178 - TR_ERKEK[0]) / TR_ERKEK[1]

VERI = {
    "PI": dict(url="https://osf.io/download/ykw53/",
               sha256="312e65b3ac862b5523327a1bd538d54aa0fa58bda05acb21bec68d60596440e0",
               dosya=VERI_DIZIN / "pisanski2022.xlsx"),
    "UV": dict(url="https://osf.io/download/84abw/",
               sha256="e8de84b6255bd80252371b19b543e34107f4e862444f64587b22927e9a0c3205",
               dosya=REPO / ".veri" / "cekicilik" / "uva_conjoint_kadin.csv"),
    "SL": dict(url="https://dataverse.harvard.edu/api/access/datafile/11106018?format=original",
               sha256="2c30c10ff321b903c015952b41c27d5d17e063a51307736b139fd752e8e48f65",
               dosya=VERI_DIZIN / "sleiman_wide_HAM.dta"),
    "BR": dict(url="https://ftp.ibge.gov.br/Orcamentos_Familiares/Pesquisa_de_Orcamentos_Familiares_2008_2009/"
                   "Microdados/Dados_20231009.zip",
               sha256="cc2d5279dbdfd9276cde69066959b919e1a1ecaac4adf82582c6f177443ca265",
               dosya=VERI_DIZIN / "pof0809_dados.zip"),
    "BRd": dict(url="https://ftp.ibge.gov.br/Orcamentos_Familiares/Pesquisa_de_Orcamentos_Familiares_2008_2009/"
                    "Microdados/Programas_de_Leitura_20231009.zip",
                sha256="98d7eb83526801b356ebbd4074cb38976329e1023ed19bf84de3f2b8c5e6f2a5",
                dosya=VERI_DIZIN / "pof0809_leitura.zip"),
}
SL_TEMIZ = VERI_DIZIN / "sleiman_kadin_temiz.csv"
SL_SHA_KAYIT = VERI_DIZIN / "sleiman_ham_sha256.txt"
TESTLER, KARARLAR, OZET = [], [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK, IZGARA = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3", "#ecebe8"
MAVI, TURUNCU = "#2a78d6", "#d9822b"


def log(*a):
    print(f"[{time.time() - T0:6.1f} s]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'}  ({deger})")


def karar_kaydi(ad, soru, deger, karar):
    KARARLAR.append(dict(kural=ad, soru=soru, deger=deger, karar=karar))
    log(f"{ad}: {karar}  ({deger})")


def indir(v):
    if not v["dosya"].exists():
        v["dosya"].parent.mkdir(parents=True, exist_ok=True)
        istek = urllib.request.Request(v["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
        with urllib.request.urlopen(istek, timeout=600) as r:
            v["dosya"].write_bytes(r.read())
    return hashlib.sha256(v["dosya"].read_bytes()).hexdigest()


def aralik(x, axis=0):
    return np.percentile(x, [2.5, 97.5], axis=axis)


def yaz(n, lo, hi, nd=1):
    return f"{n:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]"


# ---------------------------------------------------------------- T0: veri bütünlüğü
sha = {}
for k, v in VERI.items():
    if k == "SL" and SL_TEMIZ.exists():
        sha[k] = SL_SHA_KAYIT.read_text().strip()
        continue
    sha[k] = indir(v)
if not SL_TEMIZ.exists():
    ham = pd.read_stata(VERI["SL"]["dosya"], convert_categoricals=False)
    tut = ["male_female", "which_set", "orientation", "age", "height"] + [f"mset{i}" for i in range(1, 17)]
    ham = ham[(ham.male_female == 0) & (ham.which_set == 1)][tut]   # kadın katılımcı, erkek profil setleri
    ham.reset_index(drop=True).to_csv(SL_TEMIZ, index_label="kadin")
    SL_SHA_KAYIT.write_text(sha["SL"])
    VERI["SL"]["dosya"].unlink()   # IP ve konum içeren ham dosya tutulmaz
    del ham
uyan = [k for k, v in VERI.items() if sha[k] == v["sha256"]]
test("T0", "Veri bütünlüğü: beş dosyanın SHA-256 özeti", ", ".join(f"{k} {'eşleşti' if k in uyan else 'UYUŞMADI'}" for k in VERI),
     "beşi de eşleşir", len(uyan) == len(VERI))

# ================================================================ A. SÖYLENEN (Pisanski 2022)
log("A: söylenen tercih (aralıklı regresyon)...")
p = pd.read_excel(VERI["PI"]["dosya"])
p["Height"] = pd.to_numeric(p.Height, errors="coerce")
p["HEIGHTpref_CM"] = pd.to_numeric(p.HEIGHTpref_CM, errors="coerce")
p = p[(p.Sex == "Female") & p.Preferredsex_selfreport.isin(["PrefersOppositeSex", "FePrefersOppositeSex"])]
p = p.dropna(subset=["Height", "HEIGHTpref_CM"])
p = p[p.Height.between(130, 210)]
IZGARA_SIL = np.array([165, 170, 175, 180, 185.0])


def sil_aralik(g):
    return (-np.inf if g == 165 else g - 2.5), (np.inf if g == 185 else g + 2.5)


def tercih_aralik(v):
    if v in IZGARA_SIL:
        return sil_aralik(v)
    if v % 5 == 2.5 and 165 < v < 185:          # iki komşu silüetin ortası
        return sil_aralik(v - 2.5)[0], sil_aralik(v + 2.5)[1]
    return sil_aralik(IZGARA_SIL[np.abs(IZGARA_SIL - v).argmin()])


ULKELER = ["Canada", "Cuba", "Norway", "USA"]


def pi_veri(baglam):
    d = p[p.Relationship_context == baglam].drop_duplicates("ID_NUMBER")
    lo, hi = zip(*d.HEIGHTpref_CM.map(tercih_aralik))
    ulke = np.column_stack([(d.Country == u).astype(float) - (d.Country == ULKELER[0]).astype(float) for u in ULKELER[1:]])
    X = np.column_stack([np.ones(len(d)), d.Height - 165, ulke])
    return X, np.array(lo), np.array(hi), d


def aralikli_fit(X, lo, hi, bas=None):
    def nll(t):
        mu, s = X @ t[:-1], np.exp(t[-1])
        pr = norm.cdf((hi - mu) / s) - norm.cdf((lo - mu) / s)
        return -np.log(np.clip(pr, 1e-300, None)).sum()
    if bas is None:
        bas = np.r_[178.0, 0.3, np.zeros(X.shape[1] - 2), np.log(6.0)]
    r = minimize(nll, bas, method="BFGS")
    return np.r_[r.x[:-1], np.exp(r.x[-1])]


def pi_boot(X, lo, hi, B=1000):
    t0 = aralikli_fit(X, lo, hi)
    bas = np.r_[t0[:-1], np.log(t0[-1])]
    dg = []
    for _ in range(B):
        i = rng.integers(0, len(X), len(X))
        dg.append(aralikli_fit(X[i], lo[i], hi[i], bas))
    return t0, np.array(dg)


def turk_pay(t, h, kadin=TR_KADIN):
    a, b, s = t[0], t[1], t[-1]
    mu = a + b * (kadin[0] - 165)
    return norm.cdf((h - mu) / np.sqrt(s ** 2 + (b * kadin[1]) ** 2))


X, lo, hi, dpi = pi_veri("LongTerm")
test("T4", "PI uzun süreli bağlamda kendi boyu ve tercihi olan kadın", f"{len(dpi)} kadın", "≥ 300", len(dpi) >= 300)
tA, dgA = pi_boot(X, lo, hi)
medyan_tr = tA[0] + tA[1] * (TR_KADIN[0] - 165)
dg_medyan = dgA[:, 0] + dgA[:, 1] * (TR_KADIN[0] - 165)
m_lo, m_hi = aralik(dg_medyan)
b_lo, b_hi = aralik(dgA[:, 1])
A = dict(n=len(dpi), kadin_boyu_ort=float(dpi.Height.mean()), kadin_boyu_ss=float(dpi.Height.std()),
         ust_silüet_payi=float((dpi.HEIGHTpref_CM == 185).mean()),
         ulke_n=dpi.Country.value_counts().to_dict(),
         a_165=float(tA[0]), egim=float(tA[1]), egim_ga=[float(b_lo), float(b_hi)], s=float(tA[-1]),
         ulke_etkisi=dict(zip(ULKELER, [float(-tA[2:5].sum())] + [float(x) for x in tA[2:5]])),
         medyan_160_5=float(medyan_tr), medyan_160_5_ga=[float(m_lo), float(m_hi)])
pay = {}
for ad, kadin in (("TR", TR_KADIN), ("IST", IST_KADIN)):
    for h in (173, 176, 178, 180, 183):
        v = turk_pay(tA, h, kadin)
        dg = np.array([turk_pay(t, h, kadin) for t in dgA])
        pay[f"{ad}_{h}"] = [float(v), *map(float, aralik(dg))]
A["tercihi_h_veya_alti"] = pay
ulke_pay = {}
for i, u in enumerate(ULKELER):
    t_u = tA.copy()
    t_u[0] = tA[0] + (A["ulke_etkisi"][u])
    ulke_pay[u] = {h: float(turk_pay(t_u, h)) for h in (176, 178)}
A["ulkeye_gore_TR_aktarim"] = ulke_pay
Xs, los, his, _ = pi_veri("ShortTerm")
tS = aralikli_fit(Xs, los, his)
A["kisa_sureli"] = dict(a_165=float(tS[0]), egim=float(tS[1]), s=float(tS[-1]),
                        TR_176=float(turk_pay(tS, 176)), TR_178=float(turk_pay(tS, 178)))
A["egri_TR"] = {int(h): float(turk_pay(tA, h)) for h in BOYLAR}
OZET["A_soylenen"] = A
test("H1", "Söylenen: 160,5 cm kadının medyan tercih ettiği partner boyu", yaz(medyan_tr, m_lo, m_hi),
     "< 180 ve GA üst < 182", medyan_tr < 180 and m_hi < 182)
test("H2", "Söylenen: kadın boyu → tercih edilen boy eğimi (cm/cm)", yaz(tA[1], b_lo, b_hi, 2), "GA alt > 0", b_lo > 0)

# A3: Stulp, Buunk ve Pollet 2013 parametreleri
STULP = dict(en_az=(3.72, 5.54), istenen=(13.45, 5.61), en_cok=(25.15, 8.13), kadin_ort=170.9)


def stulp_pay(h, tur, egim=1.0, kadin=TR_KADIN):
    f, s = STULP[tur]
    mu = STULP["kadin_ort"] + f + egim * (kadin[0] - STULP["kadin_ort"])
    return norm.cdf((h - mu) / np.sqrt(s ** 2 + (egim * kadin[1]) ** 2))


A3 = []
for h in BOYLAR:
    A3.append(dict(boy=int(h), en_az_karsilanir=stulp_pay(h, "en_az"), istenene_ulasir=stulp_pay(h, "istenen"),
                   en_az_karsilanir_egimA1=stulp_pay(h, "en_az", tA[1]), istenene_ulasir_egimA1=stulp_pay(h, "istenen", tA[1]),
                   en_az_IST=stulp_pay(h, "en_az", kadin=IST_KADIN), istenen_IST=stulp_pay(h, "istenen", kadin=IST_KADIN)))
A3 = pd.DataFrame(A3)
A3.to_csv(CIKTI / "A3_stulp_turk_aktarim.csv", index=False, float_format="%.3f")
OZET["A3_stulp"] = A3[A3.boy.isin([170, 173, 176, 178, 180, 183])].round(3).to_dict("records")

# K1
for h in (176, 178):
    v = pay[f"TR_{h}"][0]
    karar = ("çoğunun söylediği tercihi karşılıyor" if v >= 2 / 3 else "yarı yarıya" if v >= 1 / 3
             else "çoğunun söylediği tercihin altında")
    karar_kaydi(f"K1-{h}", f"Tercihi ≤ {h} cm olan Türk kadın payı (PI modeli)", yaz(100 * v, 100 * pay[f'TR_{h}'][1], 100 * pay[f'TR_{h}'][2]) + " %",
                f"{h} cm, Türk kadınlarının {karar}")

# ================================================================ B. SEÇİLEN
log("B1-B2: UvA seçim deneyi...")
u = pd.read_csv(VERI["UV"]["dosya"], sep=";", decimal=",", encoding="utf-8-sig")
ozellik = u[["Attractiveness", "Height", "Intelligence", "Bio", "Occupation"]].corr().abs().to_numpy()
r_max = ozellik[np.triu_indices(5, 1)].max()
test("T2", "UV rastgeleleştirme: profil özellikleri arası en büyük |r|", f"{r_max:.3f}", "< 0,05", r_max < 0.05)


def havuz_z(s):
    v = np.unique(s.to_numpy(float))
    return (s - v.mean()) / v.std(ddof=1)


u["y"] = u.Response * 100.0
for k, s in (("cek", "Attractiveness"), ("iq", "Intelligence"), ("bio", "Bio"), ("mes", "Occupation")):
    u[k] = havuz_z(u[s])
u["kendi"] = u["Height.in.cm"].astype(float)
u["gor"] = u.Height - u.kendi
DIGER = ["cek", "iq", "bio", "mes"]


def parca(x, dugum):
    x = np.asarray(x, float)
    return np.column_stack([x] + [np.maximum(x - k, 0) for k in dugum])


def kisi_ici(df, grup, y, X, B=2000):
    """Kişi ortalaması çıkarılmış en küçük kareler; kişi başına toplamlarla küme bootstrap."""
    g = df[grup].to_numpy()
    benz, idx = np.unique(g, return_inverse=True)
    Xd = pd.DataFrame(X).groupby(idx).transform("mean").to_numpy()
    Xc = X - Xd
    yc = df[y].to_numpy(float) - df.groupby(grup)[y].transform("mean").to_numpy()
    k = X.shape[1]
    xtx = np.zeros((len(benz), k, k))
    xty = np.zeros((len(benz), k))
    np.add.at(xtx, idx, Xc[:, :, None] * Xc[:, None, :])
    np.add.at(xty, idx, Xc * yc[:, None])
    b = np.linalg.solve(xtx.sum(0), xty.sum(0))
    ag = rng.multinomial(len(benz), np.full(len(benz), 1 / len(benz)), size=B).astype(float)
    dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty) for a in ag])
    return b, dg


DUG_M = [175, 180, 185]
XU = np.column_stack([parca(u.Height, DUG_M), u[DIGER].to_numpy(float)])
bU, dgU = kisi_ici(u, "Participants", "y", XU)


def fark_U(h1, h2, b, dug=DUG_M, nek=len(DIGER)):
    c = np.r_[(parca([h2], dug) - parca([h1], dug)).ravel(), np.zeros(nek)]
    return b @ c if b.ndim == 1 else b @ c


B1 = {}
for h1, h2 in ((176, 178), (176, 180), (176, 183), (176, 185), (172, 176), (170, 176)):
    v, dg = fark_U(h1, h2, bU), fark_U(h1, h2, dgU)
    B1[f"{h1}->{h2}"] = [float(v), *map(float, aralik(dg))]
B1["egri"] = {int(h): float(fark_U(176, h, bU)) for h in range(170, 190)}
B1["egri_ga"] = {int(h): list(map(float, aralik(fark_U(176, h, dgU)))) for h in range(170, 190)}
B1["taban_secilme_yp"] = float(u.y.mean())
B1["kadin"] = int(u.Participants.nunique())
B1["kadin_boyu"] = [float(u.groupby("Participants").kendi.first().mean()), float(u.groupby("Participants").kendi.first().std())]
d178 = B1["176->178"]
test("H3", "Seçilen (UV): 176 → 178 cm seçilme olasılığı farkı (yp)", yaz(*d178), "GA üst < 3 yp", d178[2] < 3)

DUG_G = [0, 10, 20]
XG = np.column_stack([parca(u.gor, DUG_G), u[DIGER].to_numpy(float)])
bG, dgG = kisi_ici(u, "Participants", "y", XG)
B2 = {}
for ad, kb in (("TR_160_5", TR_KADIN[0]), ("IST_164_3", IST_KADIN[0]), ("UV_ort", B1["kadin_boyu"][0])):
    v, dg = fark_U(176 - kb, 178 - kb, bG, DUG_G), fark_U(176 - kb, 178 - kb, dgG, DUG_G)
    v2, dg2 = fark_U(176 - kb, 180 - kb, bG, DUG_G), fark_U(176 - kb, 180 - kb, dgG, DUG_G)
    B2[ad] = {"176->178": [float(v), *map(float, aralik(dg))], "176->180": [float(v2), *map(float, aralik(dg2))]}
B2["kendinden_kisa_10cm_vs_esit"] = [float(fark_U(0, -10, bG, DUG_G)), *map(float, aralik(fark_U(0, -10, dgG, DUG_G)))]
OZET["B1_UV_mutlak"] = B1
OZET["B2_UV_goreli"] = B2

log("B3-B5: Sleiman seçim deneyi...")
s = pd.read_csv(SL_TEMIZ)
TASARIM = {   # 2.reshape.do: özellik = 1 olan görevler (alternatif 1, alternatif 2)
    "irk_beyaz": ([2, 3, 8, 10, 11, 13, 14, 15, 16], [3, 6, 9, 11, 12, 15, 16]),
    "parti_isci": ([1, 3, 4, 6, 10, 11, 13, 15], [1, 5, 6, 8, 10, 11, 13, 16]),
    "acik": ([1, 2, 6, 10, 11, 12, 15], [1, 3, 4, 8, 12, 14, 16]),
    "universite": ([3, 4, 6, 7, 14, 15, 16], [1, 3, 4, 6, 7, 9, 13, 14, 16]),
    "cekici": ([5, 6, 11, 13, 15], [1, 2, 3, 5, 6, 7, 9, 10, 12, 14, 15]),
    "uzun": ([1, 2, 3, 4, 8, 9, 10, 13, 15, 16], [1, 2, 3, 7, 10, 14]),
    "vejetaryen": ([4, 9, 10, 12, 14, 15, 16], [2, 3, 5, 6, 8, 10, 14, 15, 16]),
    "ilerici": ([1, 2, 3, 5, 6, 7, 14, 15, 16], [2, 5, 10, 11, 12, 14, 16]),
}
OZL = list(TASARIM)
satir = []
for _, r in s.iterrows():
    for t in range(1, 17):
        c = r[f"mset{t}"]
        if pd.isna(c):
            continue
        for alt in (1, 2):
            satir.append([r.kadin, r.height, t, alt, 100.0 * (c == alt)] +
                         [float(t in TASARIM[o][alt - 1]) for o in OZL])
sl = pd.DataFrame(satir, columns=["kadin", "kendi", "gorev", "alt", "y"] + OZL)


def kume_ols(df, terimler, B=2000):
    X = np.column_stack([np.ones(len(df)), df[terimler].to_numpy(float)])
    yv = df.y.to_numpy(float)
    benz, idx = np.unique(df.kadin.to_numpy(), return_inverse=True)
    k = X.shape[1]
    xtx = np.zeros((len(benz), k, k))
    xty = np.zeros((len(benz), k))
    np.add.at(xtx, idx, X[:, :, None] * X[:, None, :])
    np.add.at(xty, idx, X * yv[:, None])
    b = np.linalg.solve(xtx.sum(0), xty.sum(0))
    ag = rng.multinomial(len(benz), np.full(len(benz), 1 / len(benz)), size=B).astype(float)
    dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty) for a in ag])
    return b, dg, X


bS, dgS, XS = kume_ols(sl, OZL)
iu, ic, ie = 1 + OZL.index("uzun"), 1 + OZL.index("cekici"), 1 + OZL.index("universite")
ort_tahmin = XS.mean(0)
marj = {}
for v in (0, 1):
    xv = ort_tahmin.copy()
    xv[iu] = v
    marj[v] = float(xv @ bS / 100)
test("T1", "SL kodlama: kısa / uzun profil marjinal seçilme olasılığı (yayımlanan 0,382 / 0,435)",
     f"{marj[0]:.3f} / {marj[1]:.3f}", "ikisi de ±0,015", abs(marj[0] - 0.382) <= 0.015 and abs(marj[1] - 0.435) <= 0.015)
B3 = {o: [float(bS[1 + i]), *map(float, aralik(dgS[:, 1 + i]))] for i, o in enumerate(OZL)}
B3["kadin"] = int(sl.kadin.nunique())
B3["kadin_boyu"] = [float(s.height.mean()), float(s.height.std()), int(s.height.notna().sum())]
B3["marjinal_kisa_uzun"] = [marj[0], marj[1]]
fark_bc = dgS[:, iu] - dgS[:, ic]
B3["boy_eksi_cekicilik"] = [float(bS[iu] - bS[ic]), *map(float, aralik(fark_bc))]
OZET["B3_SL"] = B3
lo5, hi5 = aralik(fark_bc)
test("H5", "Seçilen (SL): boy etkisi − çekicilik etkisi (yp)", yaz(bS[iu] - bS[ic], lo5, hi5), "GA üst < 0", hi5 < 0)

B4 = {}
gruplar = {"<160": sl.kendi < 160, "160-169.9": sl.kendi.between(160, 169.999), ">=170": sl.kendi >= 170}
dg_grup = {}
for ad, m in gruplar.items():
    bg, dgg, _ = kume_ols(sl[m], OZL)
    B4[ad] = dict(kadin=int(sl[m].kadin.nunique()), uzun_etkisi=[float(bg[iu]), *map(float, aralik(dgg[:, iu]))])
    dg_grup[ad] = dgg[:, iu]
fark_g = dg_grup[">=170"] - dg_grup["<160"]
p_tek = float((fark_g <= 0).mean())
B4["fark_170ustu_eksi_160alti"] = [float(B4[">=170"]["uzun_etkisi"][0] - B4["<160"]["uzun_etkisi"][0]), *map(float, aralik(fark_g))]
B4["tek_yonlu_p"] = p_tek
OZET["B4_SL_kendi_boy"] = B4
test("H4", "Seçilen (SL): uzun profil avantajı, ≥170 cm kadınlar − <160 cm kadınlar (yp)",
     yaz(*B4["fark_170ustu_eksi_160alti"]) + f", tek yönlü p = {p_tek:.3f}", "fark > 0, p < 0,05",
     B4["fark_170ustu_eksi_160alti"][0] > 0 and p_tek < 0.05)
B5 = {"SL_2cm_dogrusal": [float(x * 2 / 10.2) for x in B3["uzun"]],
      "SL_2cm_<160_kadin": [float(x * 2 / 10.2) for x in B4["<160"]["uzun_etkisi"]]}
OZET["B5_aktarim"] = B5
karar_kaydi("K2", "Seçimde 176 → 178 farkı (UV, mutlak boy)", yaz(*d178) + " yp",
            "176 → 178 seçimde küçük fark" if d178[2] < 3 else f"176 → 178 seçimde fark edilir fark ({d178[0]:.1f} yp)")

# ================================================================ C. YAŞANAN (Brezilya POF)
log("C: Brezilya POF 2008-09...")
with zipfile.ZipFile(VERI["BRd"]["dosya"]) as z:
    sas = z.read("SAS/Leitura dos Microdados - SAS.txt").decode("latin-1")
blok = sas[sas.find("T_MORADOR_S"):sas.find("T_MORADOR_IMPUT_S")]
duzen = {ad: (int(p_) - 1, int(p_) - 1 + int(g), int(o) if o else 0)
         for p_, ad, g, o in re.findall(r"@(\d+)\s+(\w+)\s+\$?(\d+)\.(\d*)", blok)}
GEREK = ["COD_UF", "NUM_SEQ", "NUM_DV", "NUM_DOM", "NUM_UC", "COD_UPA", "PESO_FINAL", "COND_FAMILIA", "NUM_FAMILIA",
         "IDADE_ANOS", "V0405", "V0434", "ALTURA_IMPUTADA", "ANOS_ESTUDO"]
with zipfile.ZipFile(VERI["BR"]["dosya"]) as z:
    ad_m = [n for n in z.namelist() if n.endswith("T_MORADOR_S.txt")][0]
    ham = z.read(ad_m)
br = pd.read_fwf(io.BytesIO(ham), colspecs=[duzen[a][:2] for a in GEREK], names=GEREK, dtype=str)
del ham
for a in GEREK:
    ondalik = duzen[a][2]
    s_ = br[a].str.strip()
    v = pd.to_numeric(s_, errors="coerce")
    if ondalik:
        v = np.where(s_.str.contains(".", regex=False), v, v / 10 ** ondalik)
    br[a] = v
br["boy"] = br.V0434.where(br.V0434.between(120, 215))
br["aile"] = (br[["COD_UF", "NUM_SEQ", "NUM_DV", "NUM_DOM", "NUM_UC", "NUM_FAMILIA"]].astype("Int64").astype(str)
              .agg("-".join, axis=1))
es_var = br[br.COND_FAMILIA == 2].groupby("aile").size()
br["partnerli"] = ((br.COND_FAMILIA == 2) | ((br.COND_FAMILIA == 1) & br.aile.isin(es_var.index))).astype(float)
br["erkek"] = br.V0405 == 1
br["yas_grup"] = (br.IDADE_ANOS // 5) * 5
br["z"] = np.nan
for (e, g), d in br[br.boy.notna() & br.IDADE_ANOS.between(20, 64)].groupby(["erkek", "yas_grup"]):
    w = d.PESO_FINAL
    m = np.average(d.boy, weights=w)
    sd = np.sqrt(np.average((d.boy - m) ** 2, weights=w))
    br.loc[d.index, "z"] = (d.boy - m) / sd

# C1: çiftler
ref = br[br.COND_FAMILIA == 1]
es = br[br.COND_FAMILIA == 2]
cf = ref.merge(es, on="aile", suffixes=("_r", "_e"))
cf = cf[cf.V0405_r != cf.V0405_e]
cf["h_e"] = np.where(cf.V0405_r == 1, cf.boy_r, cf.boy_e)
cf["h_k"] = np.where(cf.V0405_r == 1, cf.boy_e, cf.boy_r)
cf["a_e"] = np.where(cf.V0405_r == 1, cf.IDADE_ANOS_r, cf.IDADE_ANOS_e)
cf["a_k"] = np.where(cf.V0405_r == 1, cf.IDADE_ANOS_e, cf.IDADE_ANOS_r)
cf = cf[(cf.a_e >= 20) & (cf.a_k >= 20)].dropna(subset=["h_e", "h_k"])
r_cift = float(np.corrcoef(cf.h_e, cf.h_k)[0, 1])
test("T3", "BR karşı cins çift sayısı ve eşler arası boy korelasyonu", f"n = {len(cf)}, r = {r_cift:.3f}",
     "n ≥ 25.000 ve 0,30 ≤ r ≤ 0,45", len(cf) >= 25000 and 0.30 <= r_cift <= 0.45)
gozlenen = float((cf.h_k > cf.h_e).mean())
he, hk = cf.h_e.to_numpy(), cf.h_k.to_numpy()
rast = np.array([(rng.permutation(hk) > he).mean() for _ in range(1000)])
C1 = dict(cift=len(cf), r=r_cift, fark_ort=float((cf.h_e - cf.h_k).mean()), fark_ss=float((cf.h_e - cf.h_k).std()),
          kadin_uzun_gozlenen=gozlenen, esit=float((cf.h_k == cf.h_e).mean()),
          kadin_uzun_rastgele=[float(rast.mean()), *map(float, aralik(rast))],
          erkek_ort=float(cf.h_e.mean()), kadin_ort=float(cf.h_k.mean()))
OZET["C1_ciftler"] = C1
test("H7", "Yaşanan: kadının daha uzun olduğu çift oranı, gözlenen vs rastgele eşleşme",
     f"%{100 * gozlenen:.2f} vs %{100 * rast.mean():.2f} [%{100 * np.percentile(rast, 2.5):.2f}, %{100 * np.percentile(rast, 97.5):.2f}]",
     "gözlenen < rastgele %2,5'lik dilim", gozlenen < np.percentile(rast, 2.5))

# C2: 25-44 yaş erkeklerde partnerle yaşama
e = br[br.erkek & br.IDADE_ANOS.between(25, 44)].copy()
C4 = dict(boy_eksik_partnerli=float(e[e.partnerli == 1].boy.isna().mean()),
          boy_eksik_partnersiz=float(e[e.partnerli == 0].boy.isna().mean()))
e = e[e.z.notna() & e.ANOS_ESTUDO.notna()].reset_index(drop=True)
DUG_Z = np.percentile(e.z, [5, 27.5, 50, 72.5, 95])


def rcs(x, k=DUG_Z):
    """Kısıtlı (doğal) kübik spline, Harrell: 5 düğüm → 4 terim."""
    x = np.asarray(x, float)
    s = (k[-1] - k[0]) ** 2
    pos = lambda v: np.maximum(v, 0) ** 3
    sut = [x]
    for j in range(len(k) - 2):
        sut.append((pos(x - k[j]) - pos(x - k[-2]) * (k[-1] - k[j]) / (k[-1] - k[-2])
                    + pos(x - k[-1]) * (k[-2] - k[j]) / (k[-1] - k[-2])) / s)
    return np.column_stack(sut)


yas_d = pd.get_dummies(e.yas_grup, prefix="y", drop_first=True).to_numpy(float)
uf_d = pd.get_dummies(e.COD_UF, prefix="uf", drop_first=True).to_numpy(float)


def tasarim(z, duzeltilmis):
    X = [np.ones(len(e)), rcs(z), yas_d]
    if duzeltilmis:
        X += [e.ANOS_ESTUDO.to_numpy(float)[:, None], uf_d]
    return np.column_stack(X)


def logit_irls(X, y, w, b=None, it=25):
    b = np.zeros(X.shape[1]) if b is None else b.copy()
    for _ in range(it):
        eta = np.clip(X @ b, -30, 30)
        pr = 1 / (1 + np.exp(-eta))
        W = w * pr * (1 - pr)
        H = X.T @ (X * W[:, None]) + 1e-8 * np.eye(X.shape[1])
        adim = np.linalg.solve(H, X.T @ (w * (y - pr)))
        b += adim
        if np.abs(adim).max() < 1e-8:
            break
    return b


y_e = e.partnerli.to_numpy()
w_e = (e.PESO_FINAL / e.PESO_FINAL.mean()).to_numpy()
Z_NOKTA = {"z=0 (medyan)": 0.0, "Türk 176 (z=0,189)": Z176, "Türk 178 (z=0,480)": Z178, "z=-1,28 (en kısa %10)": -1.2816,
           "z=+1,0": 1.0, "z=+1,5": 1.5}
Z_EGRI = np.linspace(-2.5, 2.5, 41)


def tahminler(b, X, w, dug):
    """Ortalama tahmin: herkesin boyu z'ye eşitlenir, diğer değişkenler olduğu gibi kalır."""
    geri = X[:, 5:] @ b[5:]
    out = {}
    for ad, zv in list(Z_NOKTA.items()) + [(f"egri_{i}", zv) for i, zv in enumerate(Z_EGRI)]:
        eta = b[0] + rcs([zv], dug)[0] @ b[1:5] + geri
        out[ad] = np.average(1 / (1 + np.exp(-np.clip(eta, -30, 30))), weights=w)
    return out


upa, upa_idx = np.unique(e.COD_UPA.to_numpy(), return_inverse=True)


def c2_model(X, y, w, upa_idx, n_upa, dug):
    b0 = logit_irls(X, y, w)
    t0 = tahminler(b0, X, w, dug)
    dg = []
    for _ in range(500):
        sayi = rng.multinomial(n_upa, np.full(n_upa, 1 / n_upa))[upa_idx]
        wb = w * sayi
        bb = logit_irls(X, y, wb, b0, it=8)
        dg.append(tahminler(bb, X, wb, dug))
    return t0, pd.DataFrame(dg)


C2 = {}
for duz in (False, True):
    t0, dg = c2_model(tasarim(e.z.to_numpy(), duz), y_e, w_e, upa_idx, len(upa), DUG_Z)
    ad = "duzeltilmis" if duz else "yas"
    res = {k: [float(100 * t0[k]), *map(float, 100 * aralik(dg[k]))] for k in Z_NOKTA}
    for k in Z_NOKTA:
        if k != "z=0 (medyan)":
            f = 100 * (dg[k] - dg["z=0 (medyan)"])
            res[f"fark: {k} − medyan"] = [float(100 * (t0[k] - t0["z=0 (medyan)"])), *map(float, aralik(f))]
    res["egri"] = [[float(zv), float(100 * t0[f"egri_{i}"]), *map(float, 100 * aralik(dg[f"egri_{i}"]))]
                   for i, zv in enumerate(Z_EGRI)]
    C2[ad] = res
C2["n_erkek"] = len(e)
C2["partnerli_orani"] = float(np.average(y_e, weights=w_e))
C2["br_erkek_boy_25_44"] = [float(np.average(e.boy, weights=w_e)), float(np.sqrt(np.average((e.boy - np.average(e.boy, weights=w_e)) ** 2, weights=w_e)))]
OZET["C2_partnerle_yasama"] = C2
OZET["C4_eksik_boy"] = C4
f176 = C2["yas"]["fark: Türk 176 (z=0,189) − medyan"]
f10 = C2["yas"]["fark: z=-1,28 (en kısa %10) − medyan"]
test("H6a", "Yaşanan (BR): partnerle yaşama, Türk-176 yüzdeliği − medyan (yp)", yaz(*f176), "GA alt > −2 yp", f176[1] > -2)
test("H6b", "Yaşanan (BR): partnerle yaşama, en kısa %10 − medyan (yp)", yaz(*f10), "GA üst < 0", f10[2] < 0)
karar_kaydi("K3", "Medyanın biraz üstündeki (Türk-176 yüzdeliği) erkeklerde partnerle yaşama cezası", yaz(*f176) + " yp",
            "medyanın biraz üstündeki erkekler için partnerle yaşamada ceza görülmedi" if f176[1] > -2 else "ceza görüldü")

# C3: partnerli erkeklerin eşi
erkek_ref = (cf.V0405_r == 1).to_numpy()
z_ref, z_es = cf.z_r.to_numpy(), cf.z_e.to_numpy()
cf["zE"] = np.where(erkek_ref, z_ref, z_es)
cf["zK"] = np.where(erkek_ref, z_es, z_ref)
cf["w"] = np.where(cf.V0405_r == 1, cf.PESO_FINAL_r, cf.PESO_FINAL_e)
c25 = cf[cf.a_e.between(25, 44)].dropna(subset=["zE", "zK"])
C3 = {}
for ad, z0 in (("medyan", 0.0), ("Türk 176", Z176), ("Türk 178", Z178), ("+1 SS", 1.0)):
    d = c25[(c25.zE - z0).abs() <= 0.3]
    C3[ad] = dict(n=len(d), es_z_ort=float(np.average(d.zK, weights=d.w)),
                  es_daha_uzun=float(np.average(d.h_k > d.h_e, weights=d.w)),
                  es_esit=float(np.average(d.h_k == d.h_e, weights=d.w)))
OZET["C3_es"] = C3
test("H8", "Yaşanan (BR): Türk-176/178 yüzdeliğinde eşin kocadan uzun olma olasılığı",
     f"%{100 * C3['Türk 176']['es_daha_uzun']:.1f} / %{100 * C3['Türk 178']['es_daha_uzun']:.1f}", "ikisi de < %5",
     C3["Türk 176"]["es_daha_uzun"] < 0.05 and C3["Türk 178"]["es_daha_uzun"] < 0.05)
OZET["C4_eksik_boy"]["duyarlilik_gerekli"] = abs(C4["boy_eksik_partnerli"] - C4["boy_eksik_partnersiz"]) > 0.05
if OZET["C4_eksik_boy"]["duyarlilik_gerekli"]:
    # Ön kayıt C4: ölçülmüş boy eksikse IBGE'nin atanmış boyu (ALTURA_IMPUTADA) kullanılarak C2 (yaş modeli) tekrarlanır.
    # (İlk çalıştırmada kod bu adımı yalnız bildiriyordu; Plandan sapmalar, madde 6.)
    log("C4: eksik boy farkı > 5 yp → atanmış boyla C2 tekrarı")
    br["boy_ta"] = br.boy.fillna(br.ALTURA_IMPUTADA.where(br.ALTURA_IMPUTADA.between(120, 215)))
    br["z_ta"] = np.nan
    for (er, g), d in br[br.boy_ta.notna() & br.IDADE_ANOS.between(20, 64)].groupby(["erkek", "yas_grup"]):
        m = np.average(d.boy_ta, weights=d.PESO_FINAL)
        br.loc[d.index, "z_ta"] = (d.boy_ta - m) / np.sqrt(np.average((d.boy_ta - m) ** 2, weights=d.PESO_FINAL))
    e = br[br.erkek & br.IDADE_ANOS.between(25, 44) & br.z_ta.notna() & br.ANOS_ESTUDO.notna()].reset_index(drop=True)
    yas_d = pd.get_dummies(e.yas_grup, prefix="y", drop_first=True).to_numpy(float)
    dug_ta = np.percentile(e.z_ta, [5, 27.5, 50, 72.5, 95])
    y_ta, w_ta = e.partnerli.to_numpy(), (e.PESO_FINAL / e.PESO_FINAL.mean()).to_numpy()
    upa_ta, upa_idx_ta = np.unique(e.COD_UPA.to_numpy(), return_inverse=True)
    X_ta = np.column_stack([np.ones(len(e)), rcs(e.z_ta.to_numpy(), dug_ta), yas_d])
    t0, dg = c2_model(X_ta, y_ta, w_ta, upa_idx_ta, len(upa_ta), dug_ta)
    ta = {"n_erkek": len(e), "atanmis_pay": float(br.loc[br.erkek & br.IDADE_ANOS.between(25, 44), "boy"].isna().mean())}
    for k in Z_NOKTA:
        if k != "z=0 (medyan)":
            ta[f"fark: {k} − medyan"] = [float(100 * (t0[k] - t0["z=0 (medyan)"])),
                                         *map(float, aralik(100 * (dg[k] - dg["z=0 (medyan)"])))]
    OZET["C4_eksik_boy"]["atanmis_boyla_C2"] = ta
    log("C4 atanmış boy: Türk-176 − medyan", yaz(*ta["fark: Türk 176 (z=0,189) − medyan"]),
        "; en kısa %10 − medyan", yaz(*ta["fark: z=-1,28 (en kısa %10) − medyan"]))

# Ön kayıt kuralı: teknik test geçmezse ilgili analizin hipotezleri doğrulayıcı sayılmaz (T1 → SL: H4, H5).
if [t for t in TESTLER if t["test"] == "T1"][0]["sonuc"] == "KALDI":
    for t in TESTLER:
        if t["test"] in ("H4", "H5"):
            t["sonuc"] = f"GEÇERSİZ (T1 kaldı; hesap {t['sonuc'].lower()})"

# K4: katmanlar arası çelişki
k1 = pay["TR_176"][0]
karar_kaydi("K4", "Söylenen ile seçilen/yaşanan uyumlu mu?",
            f"söylenen: tercihi ≤176 pay %{100 * k1:.0f}; seçilen 176→178 {d178[0]:.1f} yp; yaşanan Türk-176 − medyan {f176[0]:.1f} yp",
            "katmanlar farklı sonuç veriyor; ikisi de raporlanacak" if (k1 < 1 / 3) != (f176[1] <= -2) else "katmanlar aynı yönde")

# ================================================================ şekil
log("Şekil...")


def eksen(ax):
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(SOLUK)
    ax.tick_params(colors=MUR2, labelsize=8.5)
    ax.set_facecolor(YUZEY)
    ax.grid(axis="y", color=IZGARA, lw=0.8)


fig, axs = plt.subplots(1, 3, figsize=(14, 4.4), facecolor=YUZEY)
ax = axs[0]
hs = np.array(sorted(A["egri_TR"]))
ax.plot(hs, [100 * A["egri_TR"][h] for h in hs], color=MAVI, lw=2, label="Tercih ettiği boy ≤ bu boy (Pisanski)")
ax.plot(A3.boy, 100 * A3.en_az_karsilanir, color=TURUNCU, lw=2, ls="--", label="Söylediği en az sınır ≤ bu boy (Stulp)")
for h in (176, 178):
    ax.axvline(h, color=SOLUK, lw=1, ls=":")
ax.set_ylim(0, 100)
ax.set_title("Söylenen: Türk kadın dağılımına aktarım", color=MUR, loc="left", fontsize=10.5)
ax.set_xlabel("Erkeğin boyu (cm)", color=MUR2)
ax.set_ylabel("Kadınların yüzdesi", color=MUR2)
ax.legend(frameon=False, fontsize=8, loc="upper left")
eksen(ax)
ax = axs[1]
hs = np.arange(170, 190)
ax.fill_between(hs, [B1["egri_ga"][h][0] for h in hs], [B1["egri_ga"][h][1] for h in hs], color=MAVI, alpha=0.15, lw=0)
ax.plot(hs, [B1["egri"][h] for h in hs], color=MAVI, lw=2)
ax.axhline(0, color=SOLUK, lw=1)
for h in (176, 178):
    ax.axvline(h, color=SOLUK, lw=1, ls=":")
ax.set_title("Seçilen: 176 cm'ye göre seçilme farkı (UvA)", color=MUR, loc="left", fontsize=10.5)
ax.set_xlabel("Profildeki boy (cm)", color=MUR2)
ax.set_ylabel(f"Yüzde puan (taban %{B1['taban_secilme_yp']:.0f})", color=MUR2)
eksen(ax)
ax = axs[2]
eg = np.array(C2["yas"]["egri"])
ax.fill_between(eg[:, 0], eg[:, 2], eg[:, 3], color=MAVI, alpha=0.15, lw=0)
ax.plot(eg[:, 0], eg[:, 1], color=MAVI, lw=2)
for zv, et, hiza in ((Z176, "176", "right"), (Z178, "178", "left")):
    ax.axvline(zv, color=SOLUK, lw=1, ls=":")
    ax.text(zv, eg[:, 3].max(), f" Türk {et} ", color=MUR2, fontsize=8, va="top", ha=hiza)
ax.set_title("Yaşanan: partnerle yaşayan erkek oranı (Brezilya)", color=MUR, loc="left", fontsize=10.5)
ax.set_xlabel("Boy, yaş grubuna göre z-puanı", color=MUR2)
ax.set_ylabel("Yüzde (25-44 yaş erkek)", color=MUR2)
eksen(ax)
fig.tight_layout()
fig.savefig(CIKTI / "uc_katman.png", dpi=160)
plt.close(fig)

# ================================================================ çıktılar
pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET.update(testler=TESTLER, kararlar=KARARLAR, tohum=TOHUM, turk_referans=dict(kadin=TR_KADIN, erkek=TR_ERKEK,
            z176=Z176, z178=Z178))
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"Bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti; "
    f"{sum(t['sonuc'].startswith('GEÇERSİZ') for t in TESTLER)} geçersiz.")
