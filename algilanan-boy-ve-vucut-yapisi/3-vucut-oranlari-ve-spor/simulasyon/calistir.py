"""
Omuz, göğüs, bel oranları ve spor: görünüşe etkisi (PLAN.md). Tek komut:

    python calistir.py

Adımlar
  1  ANSUR II (17-24 yaş erkek) indir, SHA-256 doğrula; V1-V6 gerçek veri analizi
  2  Senaryolar S0-S4 (12 ay), Monte Carlo: ölçüler, yüzdelikler, algılanan boy
  3  Ön kayıtlı testler B1-B6, karar kuralları K1-K4
  4  Duyarlılık D1-D5
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
from matplotlib.patches import Ellipse, Polygon
from scipy import stats

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
TOHUM = 20261009
R = 4000
DIK_DURUS_CM = 1.3             # Prushansky 2013 (sürüm 1): gevşek → dik, erkek, gerçek boy
ANSUR = dict(url="https://tools.openlab.psu.edu/publicData/ANSUR_II_MALE_Public.csv",
             sha256="0547aea0170e5293de519389981135e75803f02e6d40c77ace740decc0caac64",
             dosya=REPO / ".veri" / "ansur2" / "ANSUR_II_MALE_Public.csv")
TESTLER, OZET = [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3"
MAVI, YESIL, TURUNCU = "#2a78d6", "#1baf7a", "#eb6834"


def log(*a):
    print(f"[{time.time() - T0:6.1f} s]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'}  ({deger})")


# ---------------------------------------------------------------------------
# 1. Gerçek veri (V1-V6)
# ---------------------------------------------------------------------------
if not ANSUR["dosya"].exists():
    ANSUR["dosya"].parent.mkdir(parents=True, exist_ok=True)
    istek = urllib.request.Request(ANSUR["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
    with urllib.request.urlopen(istek, timeout=120) as r:
        ANSUR["dosya"].write_bytes(r.read())
ozet_sha = hashlib.sha256(ANSUR["dosya"].read_bytes()).hexdigest()
d = pd.read_csv(ANSUR["dosya"], encoding="latin-1")
g = d[(d.Age >= 17) & (d.Age <= 24)].reset_index(drop=True)
test("B1", "Veri bütünlüğü: ANSUR II SHA-256 ve 17-24 yaş erkek sayısı",
     f"SHA {'eşleşti' if ozet_sha == ANSUR['sha256'] else 'UYUŞMADI'}; n = {len(g)}", "eşleşir; n = 1358",
     ozet_sha == ANSUR["sha256"] and len(g) == 1358)

cm = lambda s: g[s].to_numpy(float) / 10                            # mm → cm
M = dict(boy=cm("stature"), biak=cm("biacromialbreadth"), bidelt=cm("bideltoidbreadth"),
         gogus=cm("chestcircumference"), omuz_c=cm("shouldercircumference"), pazi=cm("bicepscircumferenceflexed"),
         onkol=cm("forearmcircumferenceflexed"), bel=cm("waistcircumference"), bel_en=cm("waistbreadth"),
         kalca_en=cm("hipbreadth"), kilo=g.weightkg.to_numpy(float) / 10, yas=g.Age.to_numpy(float))
N = len(g)


def ols(y, X):
    """Sabit terimli en küçük kareler. Döner: katsayılar, artık, R²."""
    A = np.column_stack([np.ones(len(y))] + list(X))
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    e = y - A @ b
    return b, e, 1 - e.var() / y.var()


def z(x):
    return (x - x.mean()) / x.std()


# V1: iskelet payı
_, _, r2_iskelet = ols(M["bidelt"], [M["boy"], M["biak"]])
# V2: yağ ve kas indeksleri
z_yag = z(ols(M["bel"], [M["boy"], M["biak"]])[1])
kas_bilesen = [z(ols(M[k], [M["boy"], M["biak"], M["bel"]])[1]) for k in ("gogus", "omuz_c", "pazi", "onkol")]
z_kas = z(np.mean(kas_bilesen, axis=0))
_, _, r2_tum = ols(M["bidelt"], [M["boy"], M["biak"], z_kas, z_yag])
r_kas_yag = float(np.corrcoef(z_kas, z_yag)[0, 1])
test("B2", "İndeks yapısı: ortalama 0, SD 1, kas ve yağ indeksleri ilişkisiz",
     f"ortalamalar {z_kas.mean():.1e}, {z_yag.mean():.1e}; SD {z_kas.std():.12f}, {z_yag.std():.12f}; r = {r_kas_yag:.4f}",
     "|ort| < 1e-9; SD = 1 ± 1e-9; |r| < 0.05",
     abs(z_kas.mean()) < 1e-9 and abs(z_yag.mean()) < 1e-9 and abs(z_kas.std() - 1) < 1e-9
     and abs(z_yag.std() - 1) < 1e-9 and abs(r_kas_yag) < 0.05)

# V3: oranlar
WCR = M["bel"] / M["gogus"]
SWR = M["omuz_c"] / M["bel"]
# V4: aynı iskelet
boy_med, biak_med = np.median(M["boy"]), np.median(M["biak"])
ayni = (np.abs(M["boy"] - boy_med) <= 2) & (np.abs(M["biak"] - biak_med) <= 1)
# V5: yaş eğimi
yas_reg = stats.linregress(M["yas"], M["biak"])
t975 = stats.t.ppf(0.975, N - 2)
# V6: eşleme katsayıları
OLCULER = ("gogus", "omuz_c", "bidelt", "bel", "bel_en", "kalca_en", "kilo", "pazi")
KAT = {}
for k in OLCULER:
    b, _, r2 = ols(M[k], [M["boy"], M["biak"], z_kas, z_yag])
    KAT[k] = dict(sabit=b[0], boy=b[1], biak=b[2], kas=b[3], yag=b[4], r2=r2)
# Önden genişlik indeksi (Beck 2013 yanılgısı için)
e_bd = ols(M["bidelt"], [M["boy"]])[1]
e_be = ols(M["bel_en"], [M["boy"]])[1]
gen_ham = (e_bd / e_bd.std() + e_be / e_be.std()) / 2
GEN_SD = gen_ham.std()

OZET["veri"] = dict(
    n=N,
    V1=dict(r2_bideltoid_iskelet=r2_iskelet, r2_bideltoid_iskelet_kas_yag=r2_tum,
            ort_cm=dict(biakromiyal=float(M["biak"].mean()), bideltoid=float(M["bidelt"].mean()),
                        yumusak_doku_fark=float((M["bidelt"] - M["biak"]).mean()))),
    V2=dict(r_kas_yag=r_kas_yag),
    V3=dict(WCR=dict(p5=float(np.percentile(WCR, 5)), p50=float(np.median(WCR)), p95=float(np.percentile(WCR, 95))),
            SWR=dict(p5=float(np.percentile(SWR, 5)), p50=float(np.median(SWR)), p95=float(np.percentile(SWR, 95)))),
    V4=dict(n=int(ayni.sum()), WCR_p5=float(np.percentile(WCR[ayni], 5)), WCR_p95=float(np.percentile(WCR[ayni], 95)),
            bideltoid_p5=float(np.percentile(M["bidelt"][ayni], 5)), bideltoid_p95=float(np.percentile(M["bidelt"][ayni], 95)),
            gogus_p5=float(np.percentile(M["gogus"][ayni], 5)), gogus_p95=float(np.percentile(M["gogus"][ayni], 95))),
    V5=dict(egim_cm_yil=yas_reg.slope, lo=yas_reg.slope - t975 * yas_reg.stderr, hi=yas_reg.slope + t975 * yas_reg.stderr,
            ort_17_18=float(M["biak"][M["yas"] <= 18].mean()), ort_23_24=float(M["biak"][M["yas"] >= 23].mean()),
            n_17_18=int((M["yas"] <= 18).sum()), n_23_24=int((M["yas"] >= 23).sum())),
    V6={k: {kk: float(vv) for kk, vv in v.items()} for k, v in KAT.items()},
)
log("V1 R² iskelet", round(r2_iskelet, 3), "· V5 eğim", round(yas_reg.slope, 3), "cm/yıl")


# ---------------------------------------------------------------------------
# 2. Model ve senaryolar
# ---------------------------------------------------------------------------
@dataclass
class Ayar:
    etiket: str = "ana"
    gogus: tuple = (0.0, 0.0)        # cm, kas ekseni boyunca göğüs çevresi artışı
    yag: tuple = (0.0, 0.0)          # kg yağ değişimi
    b_guc: tuple = (0.0, 2.0)        # cm / SD kas indeksi
    b_en: tuple = (-1.0, 0.0)        # cm / SD önden genişlik
    bidelt_carpan: float = 1.0       # D3: antrenmanın omuz genişliğine etkisi
    kas0: float = -1.0               # başlangıç kas indeksi (zayıf yapılı)


SENARYO = {
    "S0 hiçbir şey": Ayar(),
    "S1 antrenman": Ayar(gogus=(3.0, 8.0), yag=(-1.0, 1.0)),
    "S2 antrenman + yağ kaybı": Ayar(gogus=(3.0, 8.0), yag=(-3.0, -1.0)),
    "S3 antrenmansız kilo alma": Ayar(yag=(2.0, 5.0)),
    "S4 yalnız yağ kaybı": Ayar(yag=(-3.0, -1.0)),
}


def cek(rng, aralik, n):
    lo, hi = aralik
    return np.full(n, lo) if lo == hi else rng.uniform(lo, hi, n)


def profil(kas, yag):
    """Medyan boy ve iskelet genişliğinde, verilen indekslerle tipik ölçüler (V6 katsayıları)."""
    return {k: v["sabit"] + v["boy"] * boy_med + v["biak"] * biak_med + v["kas"] * kas + v["yag"] * yag
            for k, v in KAT.items()}


def degisim(dkas, dyag, a):
    """İndeks değişimlerini ölçü değişimlerine çevirir."""
    out = {k: v["kas"] * dkas + v["yag"] * dyag for k, v in KAT.items()}
    out["bidelt"] = KAT["bidelt"]["kas"] * dkas * a.bidelt_carpan + KAT["bidelt"]["yag"] * dyag
    return out


def gen_degisim(dm):
    return ((dm["bidelt"] / e_bd.std() + dm["bel_en"] / e_be.std()) / 2) / GEN_SD


def v_sirasi(wcr):
    """Akranların yüzde kaçının bel/göğüs oranı daha yüksek (yani daha az V)."""
    return 100.0 * np.mean(WCR[None, :] > np.atleast_1d(wcr)[:, None], axis=1)


def kas_yuzdelik(k):
    return 100.0 * np.mean(z_kas[None, :] < np.atleast_1d(k)[:, None], axis=1)


def calistir(a, tohum=TOHUM, n=R):
    rng = np.random.default_rng(tohum)
    dgogus, dyag_kg = cek(rng, a.gogus, n), cek(rng, a.yag, n)
    b_guc, b_en = cek(rng, a.b_guc, n), cek(rng, a.b_en, n)
    dkas = dgogus / KAT["gogus"]["kas"]
    dyag = dyag_kg / KAT["kilo"]["yag"]
    p0 = profil(a.kas0, 0.0)
    dm = degisim(dkas, dyag, a)
    dgen = gen_degisim(dm)
    dA = b_guc * dkas + b_en * dgen
    wcr0 = p0["bel"] / p0["gogus"]
    wcr1 = (p0["bel"] + dm["bel"]) / (p0["gogus"] + dm["gogus"])
    v0, v1 = v_sirasi(wcr0)[0], v_sirasi(wcr1)
    k0, k1 = kas_yuzdelik(a.kas0)[0], kas_yuzdelik(a.kas0 + dkas)
    return pd.DataFrame(dict(dgogus_girdi=dgogus, dyag_kg=dyag_kg, b_guc=b_guc, b_en=b_en, dkas=dkas, dyag=dyag,
                             dgen=dgen, dA=dA, wcr0=wcr0, wcr1=wcr1, v0=v0, v1=v1, dv=v1 - v0, k0=k0, k1=k1, dk=k1 - k0,
                             **{f"d_{k}": dm[k] for k in ("gogus", "omuz_c", "bidelt", "bel", "bel_en", "kilo", "pazi")}))


def q(x):
    x = np.asarray(x, float)
    return dict(medyan=float(np.median(x)), p5=float(np.percentile(x, 5)), p95=float(np.percentile(x, 95)))


SONUC, sat = {}, []
for ad, a in SENARYO.items():
    df = calistir(replace(a, etiket=ad))
    SONUC[ad] = df
    satir = dict(senaryo=ad)
    for k in ("dA", "dv", "dk", "d_gogus", "d_omuz_c", "d_bidelt", "d_bel", "d_kilo", "d_pazi", "wcr1", "v1", "k1"):
        for kk, vv in q(df[k]).items():
            satir[f"{k}_{kk}"] = vv
    satir["v0"], satir["k0"], satir["wcr0"] = float(df.v0.iloc[0]), float(df.k0.iloc[0]), float(df.wcr0.iloc[0])
    sat.append(satir)
    log(ad, "ΔA medyan", round(satir["dA_medyan"], 2), "cm · V sırası", round(satir["v0"]), "→", round(satir["v1_medyan"]))
senaryo_tablo = pd.DataFrame(sat)
senaryo_tablo.to_csv(CIKTI / "senaryolar.csv", index=False, float_format="%.4f")
p0 = profil(-1.0, 0.0)
OZET["baslangic_profili"] = {k: float(v) for k, v in p0.items()} | dict(boy=float(boy_med), biak=float(biak_med))


# ---------------------------------------------------------------------------
# 3. Testler ve karar kuralları
# ---------------------------------------------------------------------------
s1 = SONUC["S1 antrenman"]
fark = float(np.max(np.abs(KAT["gogus"]["kas"] * s1.dkas + KAT["gogus"]["yag"] * 0 - s1.dgogus_girdi)))
test("B3", "Eşleme: kas ekseni boyunca uygulanan göğüs artışı geri hesaplanınca aynı çıkar",
     f"en büyük fark {fark:.1e} cm", "< 1e-9 cm", fark < 1e-9)

s0 = SONUC["S0 hiçbir şey"]
test("B4", "Sıfır senaryosu: ΔA = 0 ve yüzdelikler değişmez",
     f"max |ΔA| = {np.abs(s0.dA).max():.1e}; max |ΔV| = {np.abs(s0.dv).max():.1e}; max |Δkas%| = {np.abs(s0.dk).max():.1e}",
     "hepsi 0", np.abs(s0.dA).max() == 0 and np.abs(s0.dv).max() == 0 and np.abs(s0.dk).max() == 0)

wcrs, dAs = [], []
for kg in (1, 2, 3, 4, 5):
    dfk = calistir(Ayar(yag=(kg, kg), b_guc=(1.0, 1.0), b_en=(-0.5, -0.5)), n=5)
    wcrs.append(float(dfk.wcr1.iloc[0]))
    dAs.append(float(dfk.dA.iloc[0]))
mono = all(np.diff(wcrs) > 0) and all(np.diff(dAs) < 0)
test("B5", "Yön: yağ arttıkça bel/göğüs oranı yükselir, algılanan boy azalır (1-5 kg)",
     "WCR " + ", ".join(f"{w:.4f}" for w in wcrs) + " · ΔA " + ", ".join(f"{x:+.3f}" for x in dAs),
     "kesin monoton", mono)

s2 = SONUC["S2 antrenman + yağ kaybı"]
rng_b = np.random.default_rng(TOHUM + 1)
boot = [np.median(rng_b.choice(s2.dA.to_numpy(), len(s2))) for _ in range(1000)]
se = float(np.std(boot))
test("B6", "Monte Carlo hatası: S2'de ΔA medyanının bootstrap SE'si", f"SE = {se:.4f} cm", "< 0.02 cm", se < 0.02)

S2 = senaryo_tablo.set_index("senaryo").loc["S2 antrenman + yağ kaybı"]
dv_med = S2["dv_medyan"]
K1 = "belirgin" if dv_med >= 15 else "orta" if dv_med >= 5 else "küçük"
dA_med, dA_lo, dA_hi = S2["dA_medyan"], S2["dA_p5"], S2["dA_p95"]
K2_yon = "biraz daha uzun gösterir" if dA_lo > 0 else "yönü belirsiz"
K2_buyukluk = "küçük" if dA_med < 1 else "orta" if dA_med <= 2 else "büyük"
K3 = "çoğu iskelet" if r2_iskelet > 0.5 else "karışık" if r2_iskelet >= 0.3 else "çoğu yumuşak doku"
V5 = OZET["veri"]["V5"]
K4 = "kesitsel veride büyüme görülüyor" if V5["lo"] > 0 else "kesitsel veride büyüme görülmüyor"
OZET["karar"] = dict(K1=f"{K1} (V sırası iyileşmesi medyan {dv_med:.1f} puan)",
                     K2=f"{K2_yon}; {K2_buyukluk} (medyan {dA_med:+.2f} cm; %5-%95 {dA_lo:+.2f} … {dA_hi:+.2f})",
                     K3=f"{K3} (R² = {r2_iskelet:.3f})",
                     K4=f"{K4} ({V5['egim_cm_yil']:+.3f} cm/yıl; %95 {V5['lo']:+.3f} … {V5['hi']:+.3f})")
for k, v in OZET["karar"].items():
    log(k, v)


# ---------------------------------------------------------------------------
# 4. Duyarlılık (S2)
# ---------------------------------------------------------------------------
ana = SENARYO["S2 antrenman + yağ kaybı"]
VARYANT = {
    "ana": ana,
    "D1 güç etkisi güçlü": replace(ana, b_guc=(1.0, 3.0)),
    "D2 genişlik yanılgısı güçlü": replace(ana, b_en=(-2.0, -1.0)),
    "D3 omuz daha az genişler": replace(ana, bidelt_carpan=0.5),
    "D4 başlangıç ortalama yapılı": replace(ana, kas0=0.0),
    "D5 göğüs artışı düşük": replace(ana, gogus=(1.0, 3.0)),
}
dsat = []
for ad, a in VARYANT.items():
    df = calistir(a)
    dsat.append(dict(varyant=ad, **{f"dA_{k}": v for k, v in q(df.dA).items()}, **{f"dv_{k}": v for k, v in q(df.dv).items()},
                     v0=float(df.v0.iloc[0])))
duy = pd.DataFrame(dsat)
duy.to_csv(CIKTI / "duyarlilik.csv", index=False, float_format="%.4f")
log("duyarlılık:\n" + duy.round(2).to_string(index=False))


# ---------------------------------------------------------------------------
# 5. Grafikler
# ---------------------------------------------------------------------------
def siluet(ax, x0, olc, boy, renk, dolu, etiket):
    """Basit önden siluet: omuz = bideltoid, bel = bel genişliği, kalça = kalça genişliği (cm)."""
    s = boy / 175.0
    bas_r = 9.5 * s
    y_omuz, y_bel, y_kalca, y_bacak = boy - 26 * s, boy - 62 * s, boy - 80 * s, 0
    om, be, ka = olc["bidelt"] / 2, olc["bel_en"] / 2, olc["kalca_en"] / 2
    govde = [(x0 - om, y_omuz), (x0 + om, y_omuz), (x0 + be, y_bel), (x0 + ka, y_kalca), (x0 + ka * 0.85, y_bacak),
             (x0 + 3, y_bacak), (x0, y_kalca - 8 * s), (x0 - 3, y_bacak), (x0 - ka * 0.85, y_bacak), (x0 - ka, y_kalca),
             (x0 - be, y_bel)]
    kw = dict(facecolor=renk if dolu else "none", edgecolor=renk, lw=1.6, alpha=0.9 if dolu else 1.0)
    ax.add_patch(Polygon(govde, closed=True, **kw))
    ax.add_patch(Polygon([(x0 - 6 * s, y_omuz), (x0 + 6 * s, y_omuz), (x0 + 5 * s, y_omuz + 7 * s), (x0 - 5 * s, y_omuz + 7 * s)], **kw))
    ax.add_patch(Ellipse((x0, y_omuz + 7 * s + bas_r), 2 * bas_r * 0.8, 2 * bas_r, **kw))
    if etiket:
        ax.text(x0, -12, etiket, ha="center", va="top", fontsize=9.5, color=MUR)


fig, axs = plt.subplots(1, 2, figsize=(12.5, 5.6), facecolor=YUZEY, gridspec_kw=dict(width_ratios=[1.05, 1]))
ax = axs[0]
ax.set_facecolor(YUZEY)
kutu = [("Başlangıç\n(zayıf yapılı)", 0.0, 0.0, SOLUK), ("S2: 12 ay antrenman\n+ hafif yağ kaybı", None, None, YESIL),
        ("S3: antrenmansız\nkilo alma", None, None, TURUNCU)]
for i, (et, dk_, dy_, renk) in enumerate(kutu):
    x0 = 30 + i * 60
    siluet(ax, x0, p0, boy_med, SOLUK, i == 0, None)
    if i > 0:
        df = SONUC["S2 antrenman + yağ kaybı" if i == 1 else "S3 antrenmansız kilo alma"]
        med = {k: p0[k] + float(np.median(df[f"d_{k}"])) if f"d_{k}" in df else p0[k] for k in p0}
        siluet(ax, x0, med, boy_med, renk, False, None)
        dd = {k: float(np.median(df[f"d_{k}"])) for k in ("bidelt", "bel", "gogus")}
        ax.text(x0, -12, f"{et}\nomuz {dd['bidelt']:+.1f} · göğüs {dd['gogus']:+.1f}\nbel {dd['bel']:+.1f} cm",
                ha="center", va="top", fontsize=9, color=MUR)
    else:
        ax.text(x0, -12, f"{et}\nomuz {p0['bidelt']:.0f} · bel {p0['bel_en']:.0f} cm\n(önden genişlik)",
                ha="center", va="top", fontsize=9, color=MUR)
ax.set_xlim(0, 180)
ax.set_ylim(-48, boy_med + 8)
ax.set_aspect("equal")
ax.axis("off")
ax.set_title("Aynı iskelet, 12 ay sonra (medyan; gri dolu = başlangıç, çizgi = sonrası)", fontsize=10.5, loc="left", color=MUR)

ax = axs[1]
ax.set_facecolor(YUZEY)
sira = ["S1 antrenman", "S2 antrenman + yağ kaybı", "S4 yalnız yağ kaybı", "S3 antrenmansız kilo alma"]
renkler = [MAVI, YESIL, MUR2, TURUNCU]
for i, (ad, rk) in enumerate(zip(sira, renkler)):
    r_ = senaryo_tablo.set_index("senaryo").loc[ad]
    y = len(sira) - 1 - i
    ax.plot([r_["dA_p5"], r_["dA_p95"]], [y, y], color=rk, lw=2.5, solid_capstyle="round")
    ax.plot(r_["dA_medyan"], y, "o", color=rk, ms=9, mec=YUZEY, mew=2)
    ax.text(r_["dA_p95"] + 0.12, y, f"{r_['dA_medyan']:+.1f} cm", va="center", fontsize=9.5, color=MUR)
ax.plot([DIK_DURUS_CM, DIK_DURUS_CM], [-0.6, len(sira) - 0.4], color=MUR2, lw=1, ls="--")
ax.text(DIK_DURUS_CM, len(sira) - 0.35, "dik duruş\n(+1.3 cm, gerçek)", ha="center", va="bottom", fontsize=8.5, color=MUR2)
ax.axvline(0, color=SOLUK, lw=1)
ax.set_yticks(range(len(sira)))
ax.set_yticklabels([s.split(" ", 1)[1] for s in sira[::-1]], fontsize=9.5)
ax.set_xlabel("Algılanan boy değişimi (cm; nokta medyan, çizgi %5-%95)", fontsize=9.5)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.set_ylim(-0.6, len(sira) + 0.6)
ax.set_title("Modelde algılanan boya etkisi (12 ay)", fontsize=10.5, loc="left", color=MUR)
fig.tight_layout()
fig.savefig(CIKTI / "siluet_ve_boy.png", dpi=150)
plt.close(fig)

fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor=YUZEY)
ax.set_facecolor(YUZEY)
for i, (ad, rk) in enumerate(zip(sira, renkler)):
    r_ = senaryo_tablo.set_index("senaryo").loc[ad]
    y = len(sira) - 1 - i
    ax.plot([r_["v0"], r_["v1_medyan"]], [y, y], color=rk, lw=2)
    ax.plot(r_["v0"], y, "o", color=SOLUK, ms=8, mec=YUZEY, mew=1.5)
    ax.plot(r_["v1_medyan"], y, "o", color=rk, ms=9, mec=YUZEY, mew=1.5)
    ax.text(max(r_["v0"], r_["v1_medyan"]) + 2, y, f"{r_['v0']:.0f} → {r_['v1_medyan']:.0f}", va="center", fontsize=9.5, color=MUR)
ax.set_yticks(range(len(sira)))
ax.set_yticklabels([s.split(" ", 1)[1] for s in sira[::-1]], fontsize=9.5)
ax.set_xlim(0, 100)
ax.set_xlabel("V sırası: akranların yüzde kaçından daha V (bel/göğüs oranı daha düşük)", fontsize=9.5)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.set_title("Akranlar arasında V oranı sırası: başlangıç (gri) → 12 ay sonra (medyan)", fontsize=10.5, loc="left", color=MUR)
fig.tight_layout()
fig.savefig(CIKTI / "v_sirasi.png", dpi=150)
plt.close(fig)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti")
