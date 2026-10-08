"""
Kaslı vücut daha uzun mu görünür? Gerçek boy → görünür boy → algılanan boy (PLAN.md). Tek komut:

    python calistir.py

Adımlar
  1  ANSUR II (17-24 yaş erkek) indir, SHA-256 doğrula; yapı ve genişlik indeksleri; Türk boy ölçeklemesi
  2  Eşit boy testi: katman katman (K0 gürültü, K1 fiziksel, K2 algı, K3 kişisel) olasılık ve PSE
  3  Bir haftalık gözlem: yanlılıklı ve yanlılıksız gözlemci, hatırlama yanlılığı
  4  Ön kayıtlı testler A1-A5, duyarlılık analizi, karar kuralları K1-K4
  5  Grafikler
Sabit tohum; tüm çıktılar ciktilar/ altında.
"""

import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Ellipse, FancyBboxPatch

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
TOHUM = 20261008
R = 4000                       # Monte Carlo tekrarı
CIFT = 2000                    # eşit boy testinde tekrar başına çift
TR_ORT, TR_SD = 175.8, 6.3     # NCD-RisC 2020 (18 yaş, 2019) ve Günöz 2014 SD
EGILME_CM = 1.3                # Prushansky 2013: gevşek → dik, erkek
ANSUR = dict(url="https://tools.openlab.psu.edu/publicData/ANSUR_II_MALE_Public.csv",
             sha256="0547aea0170e5293de519389981135e75803f02e6d40c77ace740decc0caac64",
             dosya=REPO / ".veri" / "ansur2" / "ANSUR_II_MALE_Public.csv")
TESTLER, OZET = [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3"
RENK = {"K1 fiziksel": "#2a78d6", "K2 algı (herkes)": "#1baf7a", "K3 kişisel": "#eb6834"}


def log(*a):
    print(f"[{time.time() - T0:6.0f} sn]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'} ({deger})")


def sinif(cm):
    """PLAN K1."""
    a = abs(cm)
    return "ihmal edilebilir (< 0.5 cm)" if a < 0.5 else "küçük ama yan yana fark edilebilir (0.5-2 cm)" if a < 2 \
        else "belirgin (≥ 2 cm)"


# ---------------------------------------------------------------------------
# 1. Veri
# ---------------------------------------------------------------------------

if not ANSUR["dosya"].exists():
    ANSUR["dosya"].parent.mkdir(parents=True, exist_ok=True)
    istek = urllib.request.Request(ANSUR["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
    with urllib.request.urlopen(istek, timeout=120) as r:
        ANSUR["dosya"].write_bytes(r.read())
ozet = hashlib.sha256(ANSUR["dosya"].read_bytes()).hexdigest()
d = pd.read_csv(ANSUR["dosya"], encoding="latin-1")
g = d[d.Age <= 24].copy()
r_biak = float(np.corrcoef(g.stature, g.biacromialbreadth)[0, 1])
test("A1", "Veri bütünlüğü: ANSUR II SHA-256, 17-24 yaş erkek sayısı, r(boy, biakromiyal)",
     f"SHA {'eşleşti' if ozet == ANSUR['sha256'] else 'UYUŞMADI'}; n = {len(g)}; r = {r_biak:.4f}",
     "eşleşir; n = 1358; r = 0.508 ± 0.005", ozet == ANSUR["sha256"] and len(g) == 1358 and abs(r_biak - 0.508) <= 0.005)


def artik(y, x):
    b = np.polyfit(x, y, 1)
    e = y - np.polyval(b, x)
    return (e - e.mean()) / e.std()


boy_mm = g.stature.to_numpy(float)
z_boy = (boy_mm - boy_mm.mean()) / boy_mm.std()
z_en = artik(g.bideltoidbreadth.to_numpy(float), boy_mm)
z_kilo = artik(g.weightkg.to_numpy(float) / 10, boy_mm)
z_yapi = (z_en + z_kilo) / 2
z_yapi = (z_yapi - z_yapi.mean()) / z_yapi.std()
H_TR = TR_ORT + TR_SD * z_boy
OZET["kohort"] = dict(n=len(g), r_boy_biakromiyal=r_biak, r_yapi_en=float(np.corrcoef(z_yapi, z_en)[0, 1]),
                      r_yapi_boy=float(np.corrcoef(z_yapi, z_boy)[0, 1]),
                      bideltoid_artik_sd_mm=float(np.std(g.bideltoidbreadth - np.polyval(
                          np.polyfit(boy_mm, g.bideltoidbreadth, 1), boy_mm))),
                      kilo_artik_sd_kg=float(np.std(g.weightkg / 10 - np.polyval(
                          np.polyfit(boy_mm, g.weightkg / 10, 1), boy_mm))))


# ---------------------------------------------------------------------------
# 2. Model
# ---------------------------------------------------------------------------

@dataclass
class Ayar:
    """Parametre aralıkları (PLAN 4, 6). Her tekrarda aralıktan çekilir."""
    etiket: str = "ana"
    kappa: tuple = (0.0, 0.0)          # kaslının daha dik durması
    sac: tuple = (0.0, 3.0)            # cm
    ayakkabi_sd: float = 0.8           # cm
    b_guc: tuple = (0.0, 2.0)          # cm / SD yapı
    b_en: tuple = (-1.0, 0.0)          # cm / SD genişlik
    delta: tuple = (0.0, 2.4)          # cm, kişisel katman
    s_yan: tuple = (2.0, 4.0)          # cm
    s_ayri: tuple = (5.0, 9.0)         # cm
    karsilasma: int = 100
    m: tuple = (1.0, 2.0)              # hatırlama çarpanı
    katman: int = 3                    # 0: gürültü, 1: +fiziksel, 2: +algı, 3: +kişisel


def cek(rng, aralik):
    lo, hi = aralik
    return lo if lo == hi else rng.uniform(lo, hi)


def parametreler(rng, a):
    return dict(kappa=cek(rng, a.kappa), b_guc=cek(rng, a.b_guc), b_en=cek(rng, a.b_en), delta=cek(rng, a.delta),
                s_yan=cek(rng, a.s_yan), s_ayri=cek(rng, a.s_ayri), m=cek(rng, a.m))


def gorunur(rng, H, zy, p, a, n):
    """Fiziksel katman: ayakkabı + saç − eğilme. katman < 1 ise yalnız gerçek boy."""
    if a.katman < 1:
        return np.broadcast_to(H, (n,)).astype(float)
    ayak = 2.5 + rng.normal(0, a.ayakkabi_sd, n)
    sac = rng.uniform(*a.sac, n) if a.sac[1] > a.sac[0] else np.full(n, a.sac[0])
    e = np.clip(rng.beta(2, 2, n) - p["kappa"] * zy, 0, 1)
    return H + ayak + sac - EGILME_CM * e


def algi(G, zy, ze, iri, p, a):
    """Algı katmanı (K2) ve kişisel katman (K3; yalnız gözlemcinin kendinden iri bulduğu hedefe)."""
    A = G + (p["b_guc"] * zy + p["b_en"] * ze if a.katman >= 2 else 0.0)
    return A + (p["delta"] * iri if a.katman >= 3 else 0.0)


def esit_boy(rng, a, p, n=CIFT, durum="yan", kisisel=False):
    """Gerçek boyları eşit iki kişi: kaslı (+1, +1) ve zayıf (−1, −1). Döner: P(kaslı daha uzun), ortalama fark."""
    H = TR_ORT
    Gk, Gz = gorunur(rng, H, +1.0, p, a, n), gorunur(rng, H, -1.0, p, a, n)
    Ak = algi(Gk, +1.0, +1.0, 1.0 if kisisel else 0.0, p, a)     # kişisel: gözlemci zayıf olanın kendisi
    Az = algi(Gz, -1.0, -1.0, 0.0, p, a)
    s = p["s_yan"] if durum == "yan" else p["s_ayri"]
    D = Ak - Az + rng.normal(0, s, n)
    return float(np.mean(D > 0)), float(np.mean(Ak - Az))


def hafta(rng, a, p):
    """Zayıf (−1, −1), ortalama boylu gözlemci; a.karsilasma akran. Döner: olay sayıları ve kaslı payları."""
    n = a.karsilasma
    i = rng.integers(0, len(H_TR), n)
    H, zy, ze = H_TR[i], z_yapi[i], z_en[i]
    Ho = np.full(n, TR_ORT)
    Gh, Go = gorunur(rng, H, zy, p, a, n), gorunur(rng, Ho, np.full(n, -1.0), p, a, n)
    Ah = algi(Gh, zy, ze, (zy > -1.0).astype(float), p, a)
    Ao = algi(Go, -1.0, -1.0, 0.0, p, a)
    s = np.where(rng.random(n) < 0.5, p["s_yan"], p["s_ayri"])
    uzun_gorundu = Ah - Ao + rng.normal(0, s) > 0
    olay = uzun_gorundu & (H <= Ho)
    kasli = zy > 0.5
    hatir = rng.random(n) < np.where(kasli, min(1.0, 0.5 * p["m"]), 0.5)
    h = olay & hatir
    return dict(olay=int(olay.sum()), olay_kasli=int((olay & kasli).sum()), hatir=int(h.sum()),
                hatir_kasli=int((h & kasli).sum()), kasli_pay_akran=float(kasli.mean()))


def calistir(a, tohum=TOHUM, R_=R):
    rng = np.random.default_rng(tohum)
    sat = []
    for _ in range(R_):
        p = parametreler(rng, a)
        py, ort = esit_boy(rng, a, p, durum="yan")
        pa, _ = esit_boy(rng, a, p, durum="ayri")
        pk, ortk = esit_boy(rng, a, p, durum="yan", kisisel=True)
        hf = hafta(rng, a, p)
        sat.append(dict(**p, P_yan=py, P_ayri=pa, P_kisisel_yan=pk, PSE=ort, PSE_kisisel=ortk, **hf))
    return pd.DataFrame(sat)


def q(x):
    x = np.asarray(x, float)
    return dict(medyan=float(np.median(x)), p5=float(np.percentile(x, 5)), p95=float(np.percentile(x, 95)))


# ---------------------------------------------------------------------------
# 3. Ana analiz: katman katman
# ---------------------------------------------------------------------------

ANA = Ayar()
KATMAN = {}
for k, ad in enumerate(["K0 yalnız gürültü", "K1 + fiziksel", "K2 + algı", "K3 + kişisel"]):
    log(ad)
    KATMAN[ad] = calistir(replace(ANA, katman=k))

# PSE katkıları: her katmanın PSE'si bir öncekinden farkı (aynı tohum → aynı parametre çekilişleri)
pse = {ad: KATMAN[ad]["PSE_kisisel"].to_numpy() for ad in KATMAN}
katki = {"K1 fiziksel": pse["K1 + fiziksel"] - pse["K0 yalnız gürültü"],
         "K2 algı (herkes)": pse["K2 + algı"] - pse["K1 + fiziksel"],
         "K3 kişisel": pse["K3 + kişisel"] - pse["K2 + algı"]}
KATKI = pd.DataFrame([dict(katman=k, **q(v), sinif=sinif(np.median(v)),
                           sifir_icinde=bool(np.percentile(v, 5) <= 0 <= np.percentile(v, 95))) for k, v in katki.items()]
                     + [dict(katman="TOPLAM (kişisel PSE)", **q(pse["K3 + kişisel"]),
                             sinif=sinif(np.median(pse["K3 + kişisel"])), sifir_icinde=False)])
KATKI.to_csv(CIKTI / "pse_katkilari.csv", index=False, float_format="%.3f")

OLAS = []
for ad, t in KATMAN.items():
    OLAS.append(dict(katman=ad, **{f"P_yan_{k}": v for k, v in q(t.P_yan).items()},
                     **{f"P_ayri_{k}": v for k, v in q(t.P_ayri).items()},
                     **{f"P_kisisel_yan_{k}": v for k, v in q(t.P_kisisel_yan).items()},
                     **{f"PSE_tarafsiz_{k}": v for k, v in q(t.PSE).items()}))
pd.DataFrame(OLAS).to_csv(CIKTI / "esit_boy_olasiliklari.csv", index=False, float_format="%.4f")

HAF = []
for ad in ("K1 + fiziksel", "K3 + kişisel"):
    t = KATMAN[ad]
    pay_olay = (t.olay_kasli / t.olay.replace(0, np.nan)).to_numpy()
    pay_hatir = (t.hatir_kasli / t.hatir.replace(0, np.nan)).to_numpy()
    HAF.append(dict(gozlemci="algı yanlılığı yok (gürültü + fiziksel; hatırlama yanlılığı açık)" if ad.startswith("K1")
                    else "algı + kişisel yanlılık (tüm katmanlar; hatırlama yanlılığı açık)",
                    olay_hafta=q(t.olay)["medyan"], olay_p5=q(t.olay)["p5"], olay_p95=q(t.olay)["p95"],
                    kasli_pay_akranlarda=float(t.kasli_pay_akran.mean()),
                    kasli_pay_olaylarda=float(np.nanmedian(pay_olay)),
                    kasli_pay_hatirlananlarda=float(np.nanmedian(pay_hatir))))
pd.DataFrame(HAF).to_csv(CIKTI / "haftalik_gozlem.csv", index=False, float_format="%.3f")


# ---------------------------------------------------------------------------
# 4. Testler
# ---------------------------------------------------------------------------

# A2: sıfır kontrolü (bütün etkiler 0)
sifir = replace(ANA, kappa=(0, 0), sac=(0, 0), ayakkabi_sd=0.0, b_guc=(0, 0), b_en=(0, 0), delta=(0, 0), katman=3)
t0 = calistir(sifir, R_=500)
p0, pse0 = float(t0.P_yan.mean()), float(t0.PSE_kisisel.abs().max())
test("A2", "Sıfır kontrolü: bütün etkiler 0 iken eşit boyda 'kaslı daha uzun' olasılığı ve PSE",
     f"P = {p0:.4f}; |PSE| en çok {pse0:.4f} cm", "P = 0.50 ± 0.01; PSE = 0 ± 0.05", abs(p0 - 0.5) <= 0.01 and pse0 <= 0.05)

# A3: yön tutarlılığı (diğer parametreler sabit, ortak rastgele sayılar)
def P_sabit(**kw):
    a = replace(ANA, katman=2, delta=(0, 0), **{k: (v, v) for k, v in kw.items()})
    return float(calistir(a, tohum=TOHUM + 5, R_=300).P_yan.mean())


seri_g = [P_sabit(b_guc=v, b_en=-0.5) for v in (0.0, 0.5, 1.0, 1.5, 2.0)]
seri_e = [P_sabit(b_guc=1.0, b_en=v) for v in (0.0, -0.5, -1.0, -1.5)]
test("A3", "Yön: β_güç arttıkça olasılık artar; β_en negatifleştikçe azalır",
     "β_güç: " + " < ".join(f"{v:.3f}" for v in seri_g) + " | β_en: " + " > ".join(f"{v:.3f}" for v in seri_e),
     "kesin monoton", all(a < b for a, b in zip(seri_g, seri_g[1:])) and all(a > b for a, b in zip(seri_e, seri_e[1:])))

# A4: toplanabilirlik
top = sum(katki.values()) + pse["K0 yalnız gürültü"]
fark = float(np.abs(top - pse["K3 + kişisel"]).max())
# Bağımsız kontrol: beklenen değerden analitik PSE (kaslı +1/+1, zayıf −1/−1)
t3 = KATMAN["K3 + kişisel"]
analitik = 2 * t3.b_guc + 2 * t3.b_en + t3.delta + EGILME_CM * 2 * t3.kappa   # κ: kırpma ihmal
fark2 = float(np.median(np.abs(analitik - t3.PSE_kisisel)))
test("A4", "Toplanabilirlik: katman katkılarının toplamı = tüm katmanlar açıkken PSE (ve analitik beklenen değer)",
     f"en büyük fark {fark:.2e} cm; analitikle medyan fark {fark2:.3f} cm", "< 0.1 cm", fark < 0.1 and fark2 < 0.1)

# A5: Monte Carlo yakınsaması
se = float(t3.P_kisisel_yan.std() / np.sqrt(len(t3)))
test("A5", "Monte Carlo standart hatası (kişisel, yan yana olasılığın ortalaması)", f"SE = {se:.5f}", "< 0.005", se < 0.005)


# ---------------------------------------------------------------------------
# 5. Duyarlılık (PLAN 6) ve karar kuralları
# ---------------------------------------------------------------------------

VARY = {"κ U(0, 0.15)": dict(kappa=(0.0, 0.15)), "saç eşit (0)": dict(sac=(0.0, 0.0)),
        "β_güç U(0, 1)": dict(b_guc=(0.0, 1.0)), "β_güç U(1, 3)": dict(b_guc=(1.0, 3.0)),
        "β_en 0": dict(b_en=(0.0, 0.0)), "β_en U(−2, −1)": dict(b_en=(-2.0, -1.0)),
        "karşılaşma 30": dict(karsilasma=30), "karşılaşma 300": dict(karsilasma=300),
        "hatırlama m = 1": dict(m=(1.0, 1.0)), "hatırlama m U(2, 3)": dict(m=(2.0, 3.0))}
DUY = []
for v, kw in {"ana": {}, **VARY}.items():
    log(f"Duyarlılık: {v}")
    a = replace(ANA, **kw)
    t = {k: calistir(replace(a, katman=k), R_=1500) for k in (1, 2, 3)}
    k2 = t[2].PSE_kisisel - t[1].PSE_kisisel
    k3 = t[3].PSE_kisisel - t[2].PSE_kisisel
    k1 = t[1].PSE_kisisel - calistir(replace(a, katman=0), R_=1500).PSE_kisisel
    pay = (t[3].hatir_kasli / t[3].hatir.replace(0, np.nan))
    DUY.append(dict(varyant=v, K1_medyan=np.median(k1), K2_medyan=np.median(k2), K2_p5=np.percentile(k2, 5),
                    K2_p95=np.percentile(k2, 95), K3_medyan=np.median(k3), K3_p5=np.percentile(k3, 5),
                    K3_p95=np.percentile(k3, 95), toplam_medyan=np.median(t[3].PSE_kisisel),
                    P_kisisel_yan=np.median(t[3].P_kisisel_yan), olay_hafta=np.median(t[3].olay),
                    kasli_pay_hatirlanan=np.nanmedian(pay)))
DTAB = pd.DataFrame(DUY)
DTAB.to_csv(CIKTI / "duyarlilik.csv", index=False, float_format="%.3f")

k2v, k3v = katki["K2 algı (herkes)"], katki["K3 kişisel"]
k2_sifir = np.percentile(k2v, 5) <= 0 <= np.percentile(k2v, 95)
K3_karar = ("evet, herkes için geçerli bir eğilim" if np.median(k2v) >= 0.5 and not k2_sifir
            else "bilinmiyor, deney gerekli")
a2, a3 = (np.percentile(k2v, 5), np.percentile(k2v, 95)), (np.percentile(k3v, 5), np.percentile(k3v, 95))
ortusme = not (a3[0] > a2[1] or a2[0] > a3[1])
K4_karar = ("ikisi karışık" if ortusme else "gözlem büyük ölçüde gözlemciye özgü" if np.median(k3v) > np.median(k2v)
            else "büyük ölçüde herkes için geçerli")
OZET["karar"] = dict(K3_herkes_gorur_mu=K3_karar, K4_kisisel_mi=K4_karar,
                     K2_siniflari_duyarlilikta=sorted({sinif(v) for v in DTAB.K2_medyan}),
                     K3_siniflari_duyarlilikta=sorted({sinif(v) for v in DTAB.K3_medyan}))
OZET["katkilar"] = {k: q(v) for k, v in katki.items()}
OZET["olasiliklar"] = {ad: dict(P_yan=q(t.P_yan), P_ayri=q(t.P_ayri), P_kisisel_yan=q(t.P_kisisel_yan))
                       for ad, t in KATMAN.items()}


# ---------------------------------------------------------------------------
# 6. Grafikler
# ---------------------------------------------------------------------------

def siluet(ax, x0, boy, omuz, renk, etiket):
    """Basit insan silueti: baş, gövde (omuz genişliği değişken), bacaklar. Birim cm."""
    bas_r = 11.5
    ax.add_patch(Ellipse((x0, boy - bas_r), 2 * bas_r * 0.8, 2 * bas_r, fc=renk, ec="none"))
    boyun = boy - 2 * bas_r
    ax.add_patch(FancyBboxPatch((x0 - omuz / 2, boyun - 62), omuz, 60, boxstyle="round,pad=0,rounding_size=8",
                                fc=renk, ec="none"))
    kalca = omuz * 0.62
    ax.fill([x0 - omuz / 2 + 2, x0 + omuz / 2 - 2, x0 + kalca / 2, x0 - kalca / 2],
            [boyun - 55, boyun - 55, boyun - 82, boyun - 82], color=renk, lw=0)
    for s in (-1, 1):
        ax.fill([x0 + s * 2, x0 + s * kalca / 2, x0 + s * kalca / 2 * 0.75, x0 + s * 3],
                [boyun - 80, boyun - 80, 0, 0], color=renk, lw=0)
        ax.fill([x0 + s * omuz / 2 - s * 1, x0 + s * omuz / 2 + s * 8 * omuz / 46, x0 + s * omuz / 2 + s * 4,
                 x0 + s * omuz / 2 - s * 6], [boyun - 4, boyun - 70, boyun - 72, boyun - 8], color=renk, lw=0)
    ax.text(x0, -12, etiket, ha="center", va="top", fontsize=10, color=MUR)


fig, ax = plt.subplots(figsize=(7, 6.2), facecolor=YUZEY)
OMUZ_ORT = float(g.bideltoidbreadth.mean()) / 10                  # cm, ANSUR 17-24
OMUZ_SD = OZET["kohort"]["bideltoid_artik_sd_mm"] / 10              # boy sabitken
siluet(ax, 0, TR_ORT, OMUZ_ORT - OMUZ_SD, "#9fb7d9", f"zayıf yapılı\n(omuz {OMUZ_ORT - OMUZ_SD:.0f} cm, −1 SD)")
siluet(ax, 75, TR_ORT, OMUZ_ORT + OMUZ_SD, "#7fc9a6", f"kaslı, kalıplı\n(omuz {OMUZ_ORT + OMUZ_SD:.0f} cm, +1 SD)")
ax.axhline(TR_ORT, color=MUR2, lw=1, ls="--")
ax.text(118, TR_ORT + 2, f"ikisi de {TR_ORT:.0f} cm", ha="right", fontsize=10, color=MUR2)
ax.set_xlim(-45, 120)
ax.set_ylim(-35, 195)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Aynı gerçek boy, farklı yapı: hangisi daha uzun görünüyor?", loc="left", fontsize=12, color=MUR)
fig.text(0.02, 0.02, f"Omuz (bideltoid) genişliği: ANSUR II 17-24 yaş erkek, boy sabitken ±1 SD "
         f"(fark {2 * OMUZ_SD:.1f} cm).\nSiluetin geri kalanı şematik. Tıbbi tavsiye değildir.", fontsize=8, color=MUR2)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(CIKTI / "ayni_boy_farkli_yapi.png", dpi=150)
plt.close(fig)

fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), facecolor=YUZEY, gridspec_kw=dict(width_ratios=[1.25, 1]))
ax = axs[0]
sat = KATKI.iloc[:3]
for i, r in sat.iterrows():
    ax.barh(i, r.medyan, color=RENK[r.katman], height=0.55)
    ax.plot([r.p5, r.p95], [i, i], color=MUR, lw=1.2)
    ax.text(max(r.p95, r.medyan) + 0.12, i, f"{r.medyan:+.1f} cm ({r.p5:+.1f} … {r.p95:+.1f})", va="center",
            fontsize=9, color=MUR2)
ax.set_yticks(range(3))
ax.set_yticklabels(sat.katman, fontsize=10)
ax.invert_yaxis()
ax.axvline(0, color=MUR, lw=0.8)
for x in (0.5, 2.0):
    ax.axvline(x, color="#e4e3df", lw=1, ls="--", zorder=0)
ax.set_xlabel("Kaslı akranı 'aynı boyda' gösteren fark (cm; çubuk medyan, çizgi %5-%95)")
ax.set_title("Farkın kaynakları (zayıf gözlemci, kaslı akran)", loc="left", fontsize=11)
ax.spines[["top", "right"]].set_visible(False)
ax.set_xlim(min(-1.5, sat.p5.min() - 0.3), sat.p95.max() + 3.2)
ax = axs[1]
hf = pd.DataFrame(HAF)
x = np.arange(3)
vals = [hf.kasli_pay_akranlarda.iloc[1], hf.kasli_pay_olaylarda.iloc[1], hf.kasli_pay_hatirlananlarda.iloc[1]]
vals0 = [hf.kasli_pay_akranlarda.iloc[0], hf.kasli_pay_olaylarda.iloc[0], hf.kasli_pay_hatirlananlarda.iloc[0]]
ax.bar(x - 0.18, vals0, width=0.36, color=SOLUK, label="algı yanlılığı yok")
ax.bar(x + 0.18, vals, width=0.36, color="#eb6834", label="algı + kişisel yanlılık")
for xi, v0, v in zip(x, vals0, vals):
    ax.text(xi - 0.18, v0 + 0.01, f"%{100 * v0:.0f}", ha="center", fontsize=9, color=MUR2)
    ax.text(xi + 0.18, v + 0.01, f"%{100 * v:.0f}", ha="center", fontsize=9, color=MUR2)
ax.set_xticks(x)
ax.set_xticklabels(["akranlar\narasında", "'benden kısa ama\nuzun göründü'", "...ve hatırlanan"], fontsize=9)
ax.set_ylabel("Kaslıların payı")
ax.set_ylim(0, 1)
ax.legend(frameon=False, fontsize=8, loc="upper left")
ax.set_title("Bir haftalık gözlem (iki grupta da hatırlama yanlılığı açık)", loc="left", fontsize=10.5)
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, "Model: gerçek boy → görünür boy (ayakkabı, saç, duruş) → algılanan boy. Merkezi algı etkileri "
         "doğrudan ölçülmedi; aralıklar literatürden çıkarım. Tıbbi tavsiye değildir.", fontsize=8, color=MUR2)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(CIKTI / "katkilar_ve_hafta.png", dpi=150)
plt.close(fig)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
OZET["sure_sn"] = round(time.time() - T0)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(KATKI.to_string(index=False))
print(pd.DataFrame(OLAS)[["katman", "P_yan_medyan", "P_ayri_medyan", "P_kisisel_yan_medyan", "P_kisisel_yan_p5",
                          "P_kisisel_yan_p95"]].round(3).to_string(index=False))
print(pd.DataFrame(HAF).round(3).to_string(index=False))
print(DTAB.round(2).to_string(index=False))
print(json.dumps(OZET["karar"], ensure_ascii=False, indent=1))
print(pd.DataFrame(TESTLER)[["test", "deger", "sonuc"]].to_string(index=False))
