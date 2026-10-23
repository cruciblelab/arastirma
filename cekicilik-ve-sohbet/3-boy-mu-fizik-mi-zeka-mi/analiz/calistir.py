"""
Çekicilik ve sohbet, sürüm 3: ortalama boydan sonra boy mu, fizik mi, zekâ mı (README "Yöntem" bölüm 2-4). Tek komut:

    python calistir.py

Veri (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  UvA  Witmer ve ark. 2025 seçim deneyi, kadın katılımcılar (OSF)
  MA   Mautz ve ark. 2013 ham puanlar (Aich ve ark. 2026, PLOS Biology ek dosyası S1)
  KO   Kordsmeyer ve ark. 2018 (Mendeley, CC BY 4.0)
Analizler U1-U4, M1-M3, G1-G2; teknik testler T1-T7; karar kuralları K1-K12. Çıktılar ciktilar/ altında.
"""

import hashlib
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
VERI_DIZIN = REPO / ".veri" / "cekicilik"
TOHUM = 20261023
BOOT = 2000
VERI = {
    "UvA": dict(url="https://osf.io/download/84abw/",
                sha256="e8de84b6255bd80252371b19b543e34107f4e862444f64587b22927e9a0c3205",
                dosya=VERI_DIZIN / "uva_conjoint_kadin.csv"),
    "MA": dict(url="https://journals.plos.org/plosbiology/article/file?type=supplementary&id=10.1371/journal.pbio.3003595.s003",
               sha256="f4e0e38b36dcc79af580a64c90aaca93e13b8649236beba2a9d2972aa6942925",
               dosya=VERI_DIZIN / "aich2026_s1.zip"),
    "KO": dict(url="https://data.mendeley.com/public-files/datasets/4bwxnwhwd3/files/"
                   "074a1f4d-f642-4986-889b-08785598b4e0/file_downloaded",
               sha256="7a8630b8f1c9fb01bcdc8473cd5cbf43afd0444b18066bbfad00bd2006e7d93a",
               dosya=VERI_DIZIN / "kordsmeyer2018.csv"),
}
TESTLER, KARARLAR, OZET, KATSAYI = [], [], {}, []
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK, IZGARA = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3", "#ecebe8"
MAVI = "#2a78d6"


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
        with urllib.request.urlopen(istek, timeout=180) as r:
            v["dosya"].write_bytes(r.read())
    return hashlib.sha256(v["dosya"].read_bytes()).hexdigest()


sha = {k: indir(v) for k, v in VERI.items()}
uyan = [k for k, v in VERI.items() if sha[k] == v["sha256"]]
test("T1", "Veri bütünlüğü: üç dosyanın SHA-256 özeti", ", ".join(f"{k} {'eşleşti' if k in uyan else 'UYUŞMADI'}" for k in VERI),
     "üçü de eşleşir", len(uyan) == 3)
rng = np.random.default_rng(TOHUM)


def aralik(dg):
    return np.percentile(dg, [2.5, 97.5], axis=0)


def boot_ag(n):
    return rng.multinomial(n, np.full(n, 1 / n), size=BOOT).astype(float)


# ---------------------------------------------------------------- kişi içi doğrusal model (ortak)

def kisi_ici(df, grup, y, terimler):
    """Kişi ortalaması çıkarılmış en küçük kareler; kişi başına X'X ve X'y (bootstrap için)."""
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
    ag = boot_ag(len(benzersiz))
    dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty) for a in ag])
    merkez = pd.Series(yv).groupby(idx).mean().abs().max()
    return dict(terimler=terimler, b=b, dg=dg, n=len(df), kisi=len(benzersiz), merkez=merkez)


def ols_boot(df, y, terimler):
    """Sabit terimli en küçük kareler; satırlar (kişiler) üzerinden bootstrap."""
    X = np.column_stack([np.ones(len(df)), df[terimler].to_numpy(float)])
    yv = df[y].to_numpy(float)
    xtx = X[:, :, None] * X[:, None, :]
    xty = X * yv[:, None]
    b = np.linalg.solve(xtx.sum(0), xty.sum(0))[1:]
    ag = boot_ag(len(df))
    dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty)[1:] for a in ag])
    return dict(terimler=terimler, b=b, dg=dg, n=len(df), kisi=len(df))


def kaydet(m, etiket, veri, birim, olcek=None):
    olcek = olcek or {}
    lo, hi = aralik(m["dg"])
    for i, t in enumerate(m["terimler"]):
        c = olcek.get(t, 1.0)
        KATSAYI.append(dict(veri=veri, model=etiket, terim=t, deger=m["b"][i] * c, lo=lo[i] * c, hi=hi[i] * c,
                            birim=birim.get(t, ""), n=m["n"], kisi=m["kisi"]))


def bilesim(m, agirlik):
    """Katsayıların doğrusal birleşimi: nokta tahmini ve bootstrap aralığı."""
    w = np.array([agirlik.get(t, 0.0) for t in m["terimler"]])
    nokta, dg = m["b"] @ w, m["dg"] @ w
    lo, hi = aralik(dg)
    return nokta, lo, hi


def yaz(n, lo, hi, nd=2):
    return f"{n:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]"


# ---------------------------------------------------------------- UvA: veri
u = pd.read_csv(VERI["UvA"]["dosya"], sep=";", decimal=",", encoding="utf-8-sig")
satir_kisi = u.groupby("Participants").size()
set_secim = u.groupby(["Participants", "Block"]).Response.sum()
test("T2", "UvA yapısı: kadın sayısı × satır; 3'lü sette en fazla 1 seçim",
     f"{u.Participants.nunique()} kadın, satır/kadın {satir_kisi.min()}-{satir_kisi.max()}, set başına en fazla {set_secim.max()} seçim",
     "224 × 36; en fazla 1", u.Participants.nunique() == 224 and (satir_kisi == 36).all() and set_secim.max() <= 1)
ozellik = u[["Attractiveness", "Height", "Intelligence", "Bio", "Occupation"]].corr().abs().to_numpy()
r_max = ozellik[np.triu_indices(5, 1)].max()
test("T3", "UvA rastgeleleştirme: profil özellikleri arası |r| en büyüğü", f"{r_max:.3f}", "< 0.05", r_max < 0.05)


def havuz_z(s):
    v = np.unique(s.to_numpy(float))
    return (s - v.mean()) / v.std(ddof=1)


u["secildi"] = u.Response * 100.0
u["cek"], u["bio"], u["mes"] = havuz_z(u.Attractiveness), havuz_z(u.Bio), havuz_z(u.Occupation)
u["cek_alt"], u["cek_ust"] = np.minimum(u.cek, 0), np.maximum(u.cek, 0)
u["boy_alt"], u["boy_ust"] = np.minimum(u.Height - 180, 0), np.maximum(u.Height - 180, 0)
u["iq_alt"], u["iq_ust"] = np.minimum(u.Intelligence - 100, 0), np.maximum(u.Intelligence - 100, 0)
u["boy5"] = (u.Height - 180) / 5
u["iq15"] = (u.Intelligence - 100) / 15
kendi = u.groupby("Participants")["Height.in.cm"].first()
u["kendi5"] = (u["Height.in.cm"] - kendi.mean()) / 5
u["boy5_x_kendi5"] = u.boy5 * u.kendi5
u["boy5_x_cek"] = u.boy5 * u.cek
u["iq15_x_cek"] = u.iq15 * u.cek
OZET["UvA"] = dict(kadin=int(u.Participants.nunique()), karar=len(u), secilme_orani=float(u.Response.mean()),
                   kadin_boyu_ort=float(kendi.mean()), kadin_boyu_ss=float(kendi.std()),
                   cekicilik_havuz_ss=float(np.unique(u.Attractiveness).std(ddof=1)))

U1 = ["cek_alt", "cek_ust", "boy_alt", "boy_ust", "iq_alt", "iq_ust", "bio", "mes"]
U2 = ["cek", "boy5", "iq15", "bio", "mes", "boy5_x_kendi5"]
U3 = ["cek", "boy5", "iq15", "bio", "mes", "boy5_x_cek", "iq15_x_cek"]
BIRIM_U = {"cek_alt": "yp / 1 SS (ortalamanın altı)", "cek_ust": "yp / 1 SS (ortalamanın üstü)",
           "boy_alt": "yp / 5 cm (180 altı)", "boy_ust": "yp / 5 cm (180 üstü)",
           "iq_alt": "yp / 15 IQ (100 altı)", "iq_ust": "yp / 15 IQ (100 üstü)",
           "cek": "yp / 1 SS", "boy5": "yp / 5 cm", "iq15": "yp / 15 IQ", "bio": "yp / 1 SS", "mes": "yp / 1 SS",
           "boy5_x_kendi5": "yp / 5 cm boy, kadın 5 cm uzunken", "boy5_x_cek": "yp / 5 cm boy, 1 SS çekicilikte",
           "iq15_x_cek": "yp / 15 IQ, 1 SS çekicilikte"}
OLCEK_U = {"boy_alt": 5, "boy_ust": 5, "iq_alt": 15, "iq_ust": 15}

log("UvA modelleri (kişi içi)...")
mU = {ad: kisi_ici(u, "Participants", "secildi", t) for ad, t in (("U1", U1), ("U2", U2), ("U3", U3))}
for ad, m in mU.items():
    kaydet(m, ad, "UvA", BIRIM_U, OLCEK_U)

# ---------------------------------------------------------------- UvA: koşullu logit (U4, ölçek denetimi)
secim_setleri = set_secim[set_secim == 1].index
us = u.set_index(["Participants", "Block"]).loc[secim_setleri].reset_index().sort_values(["Participants", "Block", "Profile"])
B = len(secim_setleri)
assert (us.groupby(["Participants", "Block"]).size() == 3).all()
secilen = us.Response.to_numpy().reshape(B, 3).argmax(1)
set_kisi = us.Participants.to_numpy()[::3]
kisi_benzersiz, set_idx = np.unique(set_kisi, return_inverse=True)


def clogit(X, w, b0=None):
    k = X.shape[2]
    b = np.zeros(k) if b0 is None else b0.copy()
    sec = X[np.arange(len(X)), secilen]
    for _ in range(100):
        v = X @ b
        v -= v.max(1, keepdims=True)
        p = np.exp(v)
        p /= p.sum(1, keepdims=True)
        xbar = np.einsum("bj,bjk->bk", p, X)
        g = (w[:, None] * (sec - xbar)).sum(0)
        dx = X - xbar[:, None, :]
        H = np.einsum("b,bj,bjk,bjl->kl", w, p, dx, dx)
        adim = np.linalg.solve(H, g)
        b = b + adim
        if np.abs(adim).max() < 1e-12:
            break
    v = X @ b
    v -= v.max(1, keepdims=True)
    p = np.exp(v)
    p /= p.sum(1, keepdims=True)
    g = (w[:, None] * (sec - np.einsum("bj,bjk->bk", p, X))).sum(0)
    return b, np.linalg.norm(g)


log("U4: koşullu logit ve bootstrap...")
mL, grad = {}, {}
for ad, terimler in (("U1", U1), ("U2", U2), ("U3", U3)):
    X = us[terimler].to_numpy(float).reshape(B, 3, len(terimler))
    b, grad[ad] = clogit(X, np.ones(B))
    ag = boot_ag(len(kisi_benzersiz))
    dg = np.array([clogit(X, a[set_idx], b)[0] for a in ag])
    mL[ad] = dict(terimler=terimler, b=b, dg=dg, n=B, kisi=len(kisi_benzersiz))
    kaydet(mL[ad], f"U4-{ad}", "UvA", {t: "log-odds " + BIRIM_U[t][3:] for t in terimler}, OLCEK_U)
gmax = max(grad.values())
test("T7", "U4 koşullu logit yakınsadı: gradyan normu (en büyük)", f"{gmax:.1e}", "< 1e-6", gmax < 1e-6)

# ---------------------------------------------------------------- MA: veri
with zipfile.ZipFile(VERI["MA"]["dosya"]) as z:
    ad_xlsx = [n for n in z.namelist() if n.endswith("HumanStudyData.xlsx")][0]
    ma = pd.read_excel(io.BytesIO(z.read(ad_xlsx)), sheet_name="inperson_female_attractiveness")
satir_ma = ma.groupby("participant").size()
ko = pd.read_csv(VERI["KO"]["dosya"], sep=";", decimal=",", encoding="utf-8-sig")
test("T6", "MA: kadın × puan, figür boyu düzeyi; KO: satır sayısı ve boy aralığı",
     f"MA {ma.participant.nunique()} × {satir_ma.min()}-{satir_ma.max()}, {ma.figheight.nunique()} düzey; "
     f"KO {len(ko)} satır, boy {ko.height.min():.1f}-{ko.height.max():.1f}",
     "105 × 49, 7 düzey; 164 satır, 150-210 cm",
     ma.participant.nunique() == 105 and (satir_ma == 49).all() and ma.figheight.nunique() == 7
     and len(ko) == 164 and ko.height.between(150, 210).all())

ma["puan"] = ma.rating.astype(float)
ma["fh"] = ma.figheight.astype(float)
ma["fh_alt"], ma["fh_ust"] = np.minimum(ma.fh, 0), np.maximum(ma.fh, 0)
ma["fh2"] = ma.fh ** 2
puanlayan = ma.groupby("participant").height.first()
ma["kendi5"] = (ma.height - puanlayan.mean()) / 5
ma["fh_x_kendi5"] = ma.fh * ma.kendi5
ma["fh_x_sekil"] = ma.fh * ma.zShape
OZET["MA"] = dict(kadin=int(ma.participant.nunique()), puan=len(ma), puanlayan_boyu_ort=float(puanlayan.mean()),
                  puanlayan_boyu_ss=float(puanlayan.std()))
M1 = ["zShape", "qshape", "zpenis", "qpenis", "fh_alt", "fh_ust"]
M2 = ["zShape", "qshape", "zpenis", "qpenis", "fh", "fh2", "fh_x_kendi5"]
M3 = M2 + ["fh_x_sekil"]
BIRIM_M = {"zShape": "puan / 1 SS omuz-kalça", "qshape": "puan (kare terim)", "zpenis": "puan / 1 SS",
           "qpenis": "puan (kare terim)", "fh_alt": "puan / 1 nüfus SS boy (ortalamanın altı)",
           "fh_ust": "puan / 1 nüfus SS boy (ortalamanın üstü)", "fh": "puan / 1 nüfus SS boy", "fh2": "puan (kare terim)",
           "fh_x_kendi5": "puan / 1 SS boy, puanlayan 5 cm uzunken", "fh_x_sekil": "puan / 1 SS boy, 1 SS omuz-kalçada"}
log("MA modelleri (kişi içi)...")
mM = {ad: kisi_ici(ma, "participant", "puan", t) for ad, t in (("M1", M1), ("M2", M2), ("M3", M3))}
for ad, m in mM.items():
    kaydet(m, ad, "MA", BIRIM_M)

merkez = max(mU["U1"]["merkez"], mM["M1"]["merkez"])
test("T4", "Kişi içi merkezleme (U1 ve M1)", f"{merkez:.2e}", "< 1e-9", merkez < 1e-9)


def katsayi(m, t):
    i = m["terimler"].index(t)
    lo, hi = aralik(m["dg"][:, i])
    return m["b"][i], lo, hi


c_lo = katsayi(mU["U2"], "cek")[1]
s_lo = katsayi(mM["M2"], "zShape")[1]
test("T5", "Kodlama kontrolü: UvA çekicilik (U2) ve MA omuz-kalça (M2) doğrusal katsayısı alt sınırı",
     f"UvA {c_lo:.2f}, MA {s_lo:.2f}", "ikisi de > 0", c_lo > 0 and s_lo > 0)

# ---------------------------------------------------------------- KO: G1, G2 (keşif)
G = ["height", "facial.attract", "bodily.attract", "physicalstrength_mean", "AgeT1"]
g = ko.dropna(subset=G + ["SOIbehaviour", "relationship.status"]).copy()
zad = {"height": "z_boy", "facial.attract": "z_yuz", "bodily.attract": "z_beden", "physicalstrength_mean": "z_kuvvet",
       "AgeT1": "z_yas"}
for c, z in zad.items():
    g[z] = (g[c] - g[c].mean()) / g[c].std()
g["z_soi"] = (g.SOIbehaviour - g.SOIbehaviour.mean()) / g.SOIbehaviour.std()
g["iliskide"] = g["relationship.status"].astype(float) * 100
GZ = list(zad.values())
log("KO modelleri...")
mG = {"G1": ols_boot(g, "z_soi", GZ), "G2": ols_boot(g, "iliskide", GZ)}
kaydet(mG["G1"], "G1", "KO", {z: "SS (SOI-R davranış) / 1 SS" for z in GZ})
kaydet(mG["G2"], "G2", "KO", {z: "yp (ilişkide olma) / 1 SS" for z in GZ})
OZET["KO"] = dict(n=len(g), iliskide_orani=float(g["relationship.status"].mean()), boy_ort=float(g.height.mean()),
                  boy_ss=float(g.height.std()))

# ---------------------------------------------------------------- karar kuralları
m1, l1 = mU["U1"], mL["U1"]


def yon3(lo, hi, ust, alt, yok):
    return ust if lo > 0 else (alt if hi < 0 else yok)


n, lo, hi = bilesim(m1, {"cek_ust": 1, "boy_ust": -5})
karar_kaydi("K1", "Ortalamanın üstünde +1 SS çekicilik mi, +5 cm boy mu? (yp farkı)", yaz(n, lo, hi, 1),
            yon3(lo, hi, "çekicilik", "boy", "ayırt edilemiyor"))
n, lo, hi = bilesim(m1, {"iq_ust": 15, "boy_ust": -5})
karar_kaydi("K2", "Ortalamanın üstünde +15 IQ mı, +5 cm boy mu? (yp farkı)", yaz(n, lo, hi, 1),
            yon3(lo, hi, "IQ", "boy", "ayırt edilemiyor"))

KURAL_U = {}  # K11 için: kural -> (UvA modeli, ağırlıklar, karar)
n, lo, hi = bilesim(m1, {"boy_alt": 5, "boy_ust": -5})
k3 = yon3(lo, hi, "azalıyor", "artıyor", "fark gösterilemedi")
ust_b = katsayi(m1, "boy_ust")
ek = " · 180 cm üstünde belirgin etki yok" if ust_b[1] <= 0 <= ust_b[2] else ""
karar_kaydi("K3", "Boyun getirisi 180 cm üstünde azalıyor mu? (alt − üst eğim, yp / 5 cm)",
            f"{yaz(n, lo, hi, 2)}; üst eğim {yaz(ust_b[0] * 5, ust_b[1] * 5, ust_b[2] * 5, 2)}", k3 + ek)
KURAL_U["K3"] = ("U1", {"boy_alt": 5, "boy_ust": -5}, k3)

n, lo, hi = bilesim(m1, {"iq_alt": 15, "iq_ust": -15})
k4 = yon3(lo, hi, "azalıyor", "artıyor", "fark gösterilemedi")
ust_i = katsayi(m1, "iq_ust")
ek = " · 100 üstünde belirgin etki yok" if ust_i[1] <= 0 <= ust_i[2] else ""
karar_kaydi("K4", "IQ'nun getirisi 100'ün üstünde azalıyor mu? (alt − üst eğim, yp / 15 IQ)",
            f"{yaz(n, lo, hi, 2)}; üst eğim {yaz(ust_i[0] * 15, ust_i[1] * 15, ust_i[2] * 15, 2)}", k4 + ek)
KURAL_U["K4"] = ("U1", {"iq_alt": 15, "iq_ust": -15}, k4)

n, lo, hi = bilesim(m1, {"cek_ust": 1, "cek_alt": -1})
k5 = yon3(lo, hi, "üstte daha dik", "üstte azalıyor", "fark gösterilemedi")
karar_kaydi("K5", "Çekiciliğin getirisi ortalamanın üstünde değişiyor mu? (üst − alt eğim, yp / 1 SS)", yaz(n, lo, hi, 2), k5)
KURAL_U["K5"] = ("U1", {"cek_ust": 1, "cek_alt": -1}, k5)

n, lo, hi = katsayi(mU["U2"], "boy5_x_kendi5")
k6 = yon3(lo, hi, "evet", "tersine", "gösterilemedi")
karar_kaydi("K6", "Uzun kadınlar boya daha çok mu önem veriyor? (UvA; boy × kendi boyu)", yaz(n, lo, hi, 2), k6)
KURAL_U["K6"] = ("U2", {"boy5_x_kendi5": 1}, k6)

n, lo, hi = katsayi(mM["M2"], "fh_x_kendi5")
k7 = yon3(lo, hi, "evet", "tersine", "gösterilemedi")
karar_kaydi("K7", "K6 bağımsız veride (MA) tekrarlanıyor mu? (boy × puanlayanın boyu)", yaz(n, lo, hi, 3),
            k7 + (" · tekrarlandı" if k6 == "evet" and k7 == "evet" else ""))

n, lo, hi = katsayi(mU["U3"], "boy5_x_cek")
k8 = yon3(lo, hi, "çarpımsal: çekicilikle birlikte artıyor", "telafi edici", "toplanıyor (etkileşim yok)")
karar_kaydi("K8", "Boy × çekicilik (UvA)", yaz(n, lo, hi, 2), k8)
KURAL_U["K8"] = ("U3", {"boy5_x_cek": 1}, k8)

n, lo, hi = katsayi(mU["U3"], "iq15_x_cek")
k9 = yon3(lo, hi, "çarpımsal: çekicilikle birlikte artıyor", "telafi edici", "toplanıyor (etkileşim yok)")
karar_kaydi("K9", "IQ × çekicilik (UvA)", yaz(n, lo, hi, 2), k9)
KURAL_U["K9"] = ("U3", {"iq15_x_cek": 1}, k9)

n, lo, hi = katsayi(mM["M3"], "fh_x_sekil")
k10 = yon3(lo, hi, "çarpımsal: çekicilikle birlikte artıyor", "telafi edici", "toplanıyor (etkileşim yok)")
karar_kaydi("K10", "Boy × omuz-kalça (MA)", yaz(n, lo, hi, 3), k10)

BOS = {"fark gösterilemedi", "gösterilemedi", "toplanıyor (etkileşim yok)"}
for kural, (mod, agirlik, karar) in KURAL_U.items():
    if karar in BOS:
        karar_kaydi(f"K11 ({kural})", f"{kural} ölçek denetimi", "—", "uygulanmaz (boş karar)")
        continue
    nu = bilesim(mU[mod], agirlik)[0]
    nl, lo, hi = bilesim(mL[mod], agirlik)
    ayni = np.sign(nl) == np.sign(nu) and (lo > 0 or hi < 0)
    karar_kaydi(f"K11 ({kural})", f"{kural} kararı koşullu logitte de aynı mı?", f"log-odds {yaz(nl, lo, hi, 3)}",
                "sağlam" if ayni else "ölçeğe bağlı")
for kural, karar in (("K7", k7), ("K10", k10)):
    karar_kaydi(f"K11 ({kural})", f"{kural} ölçek denetimi", "—",
                "uygulanmaz (MA puan ölçeği; koşullu logit karşılığı yok)" if karar not in BOS else "uygulanmaz (boş karar)")

for ad in ("G1", "G2"):
    m = mG[ad]
    parca = []
    for t in GZ:
        n, lo, hi = katsayi(m, t)
        parca.append(f"{t} {yaz(n, lo, hi, 2)}" + ("*" if lo > 0 or hi < 0 else ""))
    for ad2, agirlik in (("yüz − boy", {"z_yuz": 1, "z_boy": -1}), ("beden − boy", {"z_beden": 1, "z_boy": -1})):
        n, lo, hi = bilesim(m, agirlik)
        parca.append(f"{ad2} {yaz(n, lo, hi, 2)}" + ("*" if lo > 0 or hi < 0 else ""))
    karar_kaydi(f"K12 ({ad})", "SOI-R davranış (SS)" if ad == "G1" else "İlişkide olma (yp)", "; ".join(parca),
                "keşif: * = aralık 0'ı dışlıyor")

# ---------------------------------------------------------------- senaryo (U1'den, betimsel)
senaryo = []
for etiket, agirlik in (("+5 cm boy (180 → 185)", {"boy_ust": 5}), ("+1 SS fotoğraf çekiciliği", {"cek_ust": 1}),
                        ("+15 IQ (100 → 115)", {"iq_ust": 15}), ("+1 SS biyografi", {"bio": 1}),
                        ("+1 SS meslek prestiji", {"mes": 1})):
    n, lo, hi = bilesim(m1, agirlik)
    senaryo.append(dict(degisiklik=etiket, yp=n, lo=lo, hi=hi))
senaryo = pd.DataFrame(senaryo)
senaryo.to_csv(CIKTI / "senaryo.csv", index=False, float_format="%.2f")
OZET["senaryo"] = senaryo.round(2).to_dict("records")
log("Senaryo:\n" + senaryo.round(2).to_string(index=False))

# ---------------------------------------------------------------- grafikler


def eksen(ax):
    ax.set_facecolor(YUZEY)
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(SOLUK)
    ax.tick_params(colors=MUR2)
    ax.set_axisbelow(True)


fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=YUZEY)
eksen(ax)
s = senaryo.iloc[::-1].reset_index(drop=True)
for i, r in s.iterrows():
    ax.hlines(i, r.lo, r.hi, color=MAVI, lw=2)
    ax.plot(r.yp, i, "o", ms=8, color=MAVI, mec=YUZEY, mew=2)
    ax.text(max(r.hi, 0) + 0.4, i, f"{r.yp:+.1f}", va="center", color=MUR, fontsize=9)
ax.axvline(0, color=SOLUK, lw=1)
ax.set_yticks(range(len(s)), s.degisiklik, color=MUR)
ax.set_xlabel("Seçilme olasılığındaki değişim (yüzde puan; %95 aralık)", color=MUR2)
ax.set_title("180 cm, ortalama görünüşlü, IQ 100 bir profilde tek bir değişiklik ne kazandırıyor?", color=MUR,
             loc="left", fontsize=10.5)
ax.grid(axis="x", color=IZGARA, lw=0.8)
fig.tight_layout()
fig.savefig(CIKTI / "ortalamanin_ustunde.png", dpi=160)
plt.close(fig)

# Eğriler: kişi içi tahmin (parçalı, U1) ve ham ortalamalar (her değer için, kişi içi)
fig, axs = plt.subplots(1, 3, figsize=(10, 3.6), facecolor=YUZEY, sharey=True)
yc = u.secildi - u.groupby("Participants").secildi.transform("mean")
for ax, (baslik, x_ham, alt, ust, kirilma, xlab) in zip(axs, (
        ("Boy", u.Height, "boy_alt", "boy_ust", 180, "Profildeki boy (cm)"),
        ("Fotoğraf çekiciliği", u.cek, "cek_alt", "cek_ust", 0, "Çekicilik (havuz SS'si)"),
        ("IQ", u.Intelligence, "iq_alt", "iq_ust", 100, "Profildeki IQ"))):
    eksen(ax)
    ia, iu = m1["terimler"].index(alt), m1["terimler"].index(ust)
    xs = np.linspace(x_ham.min(), x_ham.max(), 60)
    f = np.minimum(xs - kirilma, 0)[:, None] * m1["dg"][:, ia] + np.maximum(xs - kirilma, 0)[:, None] * m1["dg"][:, iu]
    f0 = np.minimum(xs - kirilma, 0) * m1["b"][ia] + np.maximum(xs - kirilma, 0) * m1["b"][iu]
    lo, hi = np.percentile(f, [2.5, 97.5], axis=1)
    ax.fill_between(xs, lo, hi, color=MAVI, alpha=0.15, lw=0)
    ax.plot(xs, f0, color=MAVI, lw=2)
    ort = (np.minimum(x_ham - kirilma, 0) * m1["b"][ia] + np.maximum(x_ham - kirilma, 0) * m1["b"][iu]).mean()
    noktalar = yc.groupby(x_ham.round(3)).mean() + ort
    ax.plot(noktalar.index, noktalar.values, "o", ms=4, color=MUR2, alpha=0.6)
    ax.axhline(0, color=SOLUK, lw=1)
    ax.axvline(kirilma, color=SOLUK, lw=1, ls=":")
    ax.set_title(baslik, color=MUR, loc="left", fontsize=10.5)
    ax.set_xlabel(xlab, color=MUR2)
    ax.grid(axis="y", color=IZGARA, lw=0.8)
axs[0].set_ylabel("Seçilme olasılığı farkı (yp)\nortalama noktaya göre", color=MUR2)
fig.suptitle("Aynı kadınların seçimleri: çizgi = parçalı model (%95 bant), noktalar = her değerin ham ortalaması",
             color=MUR2, fontsize=9, x=0.01, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(CIKTI / "egriler.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- çıktılar
kat = pd.DataFrame(KATSAYI)
kat.to_csv(CIKTI / "katsayilar.csv", index=False, float_format="%.3f")
pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET.update(katsayilar=kat.round(3).to_dict("records"), testler=TESTLER, kararlar=KARARLAR, tohum=TOHUM, bootstrap=BOOT)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"Bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti.")
