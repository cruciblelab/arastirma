"""
Kreatin, psikoloji ve çok tavuk: 17 yaşından sonra boy (PLAN.md). Tek komut:

    python calistir.py

Kendi modeli yoktur (PLAN S1). Şunları olduğu gibi kullanır:
  - boy-uzamasi-16-18-yas sürüm 3: büyüme plağı modeli (model.simule_et, Senaryo.N)
  - spor-egzersiz-ve-boy sürüm 1: sanal kohort (plak.kohort)
  - beslenme-uyku-ve-boy sürüm 1: enerji / vücut bileşimi modeli (fizyoloji.simule) ve USDA besin tablosu (besin)

Adımlar
  1  Kohort (erkek, 2000 kişi) ve referans boy eğrileri
  2  Senaryolar: kreatin (K), psikoloji (P), tavuk (T)
  3  Ön kayıtlı testler R1-R6
  4  Duyarlılık analizi, K1/K3 sınıflaması
  5  Sepet profilleri, grafik
Sabit tohum; tüm çıktılar ciktilar/ altında.
"""

import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
sys.path.append(str(REPO / "beslenme-uyku-ve-boy" / "1-fizyoloji-simulasyonu" / "simulasyon"))
sys.path.append(str(REPO / "spor-egzersiz-ve-boy" / "1-fizik-tabanli-simulasyon" / "simulasyon"))
sys.path.append(str(REPO / "boy-uzamasi-16-18-yas" / "3-mekanistik-simulasyon-ve-on-kayit" / "simulasyon"))

import plak                                   # noqa: E402  (spor araştırması: sanal kohort)
from model import DT, Senaryo, simule_et      # noqa: E402  (boy araştırması sürüm 3)

import besin                                  # noqa: E402  (beslenme-uyku: USDA tablosu)
import fizyoloji as fz                        # noqa: E402  (beslenme-uyku: enerji modeli)
from fizyoloji import Ayar, Durum             # noqa: E402

CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
TOHUM = 20261008
N_KOHORT = 2000
BAS = 17.0
IZGARA = np.round(np.arange(16.0, 25.0 + 1e-9, 0.02), 2)
OZET, TESTLER = {}, []
T_BAS = time.time()

# Yeni sepetler (PLAN 4.3). B1 beslenme-uyku araştırmasından aynen.
B1 = besin.SEPETLER["B1 Dengeli"]
SEPETLER = {
    "B1 Dengeli": B1,
    "T1 Çok tavuk, dengeli": {**B1, "tavuk": 400, "ekmek": 100, "bulgur": 100},
    "T2 Tavuk-pirinç, süt ürünü yok": dict(tavuk=500, pirinc=400, ekmek=150, zeytinyagi=30, domates=150,
                                          salatalik=100, elma=150),
}


def log(*a):
    print(f"[{time.time() - T_BAS:6.0f} sn]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'} ({deger})")


def sinif(cm):
    """PLAN K1."""
    a = abs(cm)
    return "fark edilir (≥ 0.5 cm)" if a >= 0.5 else "ölçülemeyecek kadar küçük (0.1-0.5 cm)" if a >= 0.1 \
        else "etki yok (< 0.1 cm)"


# ---------------------------------------------------------------------------
# 1. Besin tablosu ve kohort
# ---------------------------------------------------------------------------

TABLO, _ = besin.yiyecek_tablosu()
PROT_YOG = {s: besin.protein_yogunlugu(TABLO, g) for s, g in SEPETLER.items()}


class Kohort:
    """Erkek sanal kohort; beslenme-uyku araştırmasındaki Kohort sınıfının aynısı (yalnız erkek, BAS'tan bağımsız)."""

    def __init__(self):
        rng = np.random.default_rng(TOHUM)
        self.pop, self.ind, self.L0b, self.L0g = plak.kohort("erkek", N_KOHORT, rng)
        s = simule_et(self.ind, self.pop, self.L0b, self.L0g, t1=25.0, kayit_yaslari=IZGARA)
        self.H = s["boy"].T / 100.0                      # (n, len(IZGARA)) metre
        self.e_bmi = rng.standard_normal(N_KOHORT)
        self.z = rng.standard_normal(N_KOHORT)
        self.baslangic(21.0)

    def baslangic(self, bmi_medyan):
        self.BMI0 = np.clip(np.exp(np.log(bmi_medyan) + 0.13 * self.e_bmi), 16, 32)
        H0 = self.H[:, 0]
        self.W0 = self.BMI0 * H0 ** 2
        bf = np.clip(1.51 * self.BMI0 - 0.70 * 16 - 3.6 + 1.4, 5, 45)
        self.FM0 = self.W0 * bf / 100

    def H_fn(self):
        H, son = self.H, self.H.shape[1] - 1

        def f(yas):
            x = (yas - 16.0) / 0.02
            i = int(np.clip(np.floor(x), 0, son))
            if i >= son:
                return H[:, son]
            t = x - i
            return H[:, i] * (1 - t) + H[:, i + 1] * t
        return f

    def enerji(self, durum, ayar):
        return fz.simule("erkek", self.W0, self.FM0, self.H_fn(), self.z, PROT_YOG, durum, ayar)

    def boy(self, senaryo=None, dt=DT):
        return simule_et(self.ind, self.pop, self.L0b, self.L0g, t1=25.0, dt=dt, senaryo=senaryo,
                         kayit_yaslari=[18.0, 25.0])["boy"]


def sabit_N(deger, bas=BAS, bit=25.0):
    """Varsayımsal sınır senaryoları: bas-bit arasında sabit çarpan (PLAN 4.1, P4)."""
    return Senaryo(N=lambda t: deger if bas - 1e-9 <= t < bit else 1.0)


log("Kohort kuruluyor")
KOH = Kohort()
i17, i25 = int(round((17.0 - 16.0) / 0.02)), len(IZGARA) - 1
KALAN = (KOH.H[:, i25] - KOH.H[:, i17]) * 100                  # 17 → 25 yaş kalan büyüme, cm
REF = KOH.boy()                                                # (2, n): 18 ve 25 yaş
OZET["kohort"] = dict(n=N_KOHORT, boy17_medyan_cm=float(np.median(KOH.H[:, i17]) * 100),
                      kalan_17_25_cm=dict(medyan=float(np.median(KALAN)), p5=float(np.percentile(KALAN, 5)),
                                          p95=float(np.percentile(KALAN, 95)), en_cok=float(KALAN.max())),
                      W16_medyan=float(np.median(KOH.W0)))
log(f"17 → 25 kalan büyüme medyan {np.median(KALAN):.2f} cm")


# ---------------------------------------------------------------------------
# 2. Senaryolar
# ---------------------------------------------------------------------------

YIL = dict(bas=BAS, bit=18.0)                 # psikoloji: bir sınav yılı
ALISKANLIK = dict(bas=BAS, bit=25.0)          # kreatin ve tavuk: alışkanlık
ENERJI = {
    "P1 Stresle kısa uyku (6 sa)": Durum(uyku_kcal=385, **YIL),
    "P2 Stresle iştah kaybı (-300 kcal)": Durum(delta=-300, **YIL),
    "P3 Yeme bozukluğu düzeyinde kısıtlama (-1000 kcal)": Durum(delta=-1000, **YIL),
    "T1 Çok tavuk, dengeli": Durum(sepet="T1 Çok tavuk, dengeli", **ALISKANLIK),
    "T2 Tavuk-pirinç, süt ürünü yok": Durum(sepet="T2 Tavuk-pirinç, süt ürünü yok", **ALISKANLIK),
    "T3 Tavukla kilo verme (-500 kcal)": Durum(sepet="T2 Tavuk-pirinç, süt ürünü yok", delta=-500, **ALISKANLIK),
}
SINIR = {   # (çarpan, bitiş yaşı, etiket)
    "K1 Kreatin, kanıta göre (N = 1)": (1.00, 25.0, "D (kanıt boşluğu)"),
    "K2a Varsayımsal: kreatin plağı %5 hızlandırsaydı": (1.05, 25.0, "D, varsayımsal"),
    "K2b Varsayımsal: %10 hızlandırsaydı": (1.10, 25.0, "D, varsayımsal"),
    "K3 Varsayımsal: %5 yavaşlatsaydı (efsane)": (0.95, 25.0, "D, varsayımsal"),
    "P4 Varsayımsal: kortizol bir yıl %5 yavaşlatsaydı": (0.95, 18.0, "D, varsayımsal"),
}


def enerji_senaryosu(durum, ayar=Ayar()):
    e = KOH.enerji(durum, ayar)
    boy = KOH.boy(Senaryo(N=fz.N_fonksiyonu(e["N_ser"], 16.0, e["dt"])))
    return e, boy


def satir(ad, grup, etiket, boy, ref=REF, ek=None):
    f18, f25 = boy[0] - ref[0], boy[1] - ref[1]
    d = dict(senaryo=ad, grup=grup, etiket=etiket,
             fark18_medyan=np.median(f18), fark18_p5=np.percentile(f18, 5), fark18_p95=np.percentile(f18, 95),
             fark25_medyan=np.median(f25), fark25_p5=np.percentile(f25, 5), fark25_p95=np.percentile(f25, 95),
             fark25_en_kotu=f25.min(), fark25_en_iyi=f25.max(), sinif=sinif(np.median(f25)))
    d.update(ek or {})
    return d, f25


SATIRLAR, FARK25 = [], {}
log("Referans enerji senaryosu (R0, B1)")
E0, B0 = enerji_senaryosu(Durum())
for ad, (c, bit, et) in SINIR.items():
    log(ad)
    d, f = satir(ad, "kreatin" if ad.startswith("K") else "psikoloji", et, KOH.boy(sabit_N(c, bit=bit)))
    SATIRLAR.append(d)
    FARK25[ad] = f
E = {}
for ad, durum in ENERJI.items():
    log(ad)
    e, b = enerji_senaryosu(durum)
    E[ad] = e
    a18 = e["anlar"][18.0]
    ek = dict(min_EA_medyan=float(np.median(e["min_EA"])), min_N_medyan=float(np.median(e["min_N"])),
              kilo_degisim18_medyan=float(np.median(a18["W"] - E0["anlar"][18.0]["W"])),
              protein_gkg18_medyan=float(np.median(a18["P_gkg"])), F1_max=float(e["F1"].max()))
    d, f = satir(ad, "psikoloji" if ad.startswith("P") else "tavuk", "D (enerji modeli)", b, ref=B0, ek=ek)
    SATIRLAR.append(d)
    FARK25[ad] = f
TAB = pd.DataFrame(SATIRLAR)
TAB.to_csv(CIKTI / "senaryolar.csv", index=False, float_format="%.4f")


# ---------------------------------------------------------------------------
# 3. Ön kayıtlı testler
# ---------------------------------------------------------------------------

# R1: sıfır kontrolü
yok = KOH.boy()
n1 = KOH.boy(Senaryo(N=lambda t: 1.0))
k1 = KOH.boy(sabit_N(1.0))
r1 = max(np.abs(n1 - yok).max(), np.abs(k1 - yok).max(), np.abs(B0 - yok).max())
test("R1", "Sıfır kontrolü: R0 (N ≡ 1, enerji modelli referans dahil) ve K1 = senaryosuz model",
     f"en büyük fark {r1:.1e} cm", "< 1e-9 cm", r1 < 1e-9)

# R2: enerji korunumu
f1 = max([E0["F1"].max()] + [e["F1"].max() for e in E.values()])
test("R2", "Enerji korunumu (enerji modelli bütün senaryolar)", f"en büyük göreli hata {f1:.1e}", "< %0.1", f1 < 1e-3)

# R3: tavan (N ≤ 1 senaryolarında kimse referanstan uzun değil)
tavan = {ad: float(FARK25[ad].max()) for ad in FARK25
         if ad in ENERJI or SINIR[ad][0] <= 1.0}
r3 = max(tavan.values())
assert r3 <= 1e-9, f"S5/R3: N ≤ 1 olan bir senaryo referanstan uzun çıktı: {tavan}"
test("R3", "Tavan: N ≤ 1 olan hiçbir senaryoda hiçbir kişi referanstan uzun değil", f"en büyük fark {r3:.1e} cm",
     "≤ 1e-9 cm", r3 <= 1e-9)

# R4: yön tutarlılığı
m = {ad: float(np.median(FARK25[ad])) for ad in SINIR}
sira = [m["K3 Varsayımsal: %5 yavaşlatsaydı (efsane)"], 0.0, m["K2a Varsayımsal: kreatin plağı %5 hızlandırsaydı"],
        m["K2b Varsayımsal: %10 hızlandırsaydı"]]
test("R4", "Yön: 25 yaş medyan fark sırası K3 < R0 < K2a < K2b", " < ".join(f"{v:+.3f}" for v in sira),
     "kesin artan", all(a < b for a, b in zip(sira, sira[1:])))

# R5: gözlemsel katsayının sağduyu kontrolü (Korovljev 2021: 0.1 g/gün başına +0.30 cm)
naif = 3.0 / 0.1 * 0.30
oran = float(np.mean(naif > KALAN))
test("R5", "Korovljev katsayısı nedensel okunursa (3 g/gün → +9 cm) 17 → 25 kalan büyüme payından büyük mü",
     f"kişilerin %{100 * oran:.1f}'inde 9 cm > kalan pay (medyan pay {np.median(KALAN):.2f} cm)", "≥ %95",
     oran >= 0.95)
OZET["R5"] = dict(naif_cm=naif, oran=oran)

# R6: sayısal yakınsama
c = SINIR["K2b Varsayımsal: %10 hızlandırsaydı"][0]
r6 = float(np.abs(KOH.boy(sabit_N(c), dt=DT) - KOH.boy(sabit_N(c), dt=DT / 2))[1].max())
test("R6", "Sayısal yakınsama (K2b, RK2 Δt ve Δt/2, 25 yaş boy)", f"en büyük fark {r6:.1e} cm", "< 0.01 cm", r6 < 0.01)


# ---------------------------------------------------------------------------
# 4. Duyarlılık analizi (PLAN 6)
# ---------------------------------------------------------------------------

DUY = []


def duy(ad, varyant, boy, ref):
    f = boy[1] - ref[1]
    DUY.append(dict(senaryo=ad, varyant=varyant, fark25_medyan=np.median(f), fark25_p5=np.percentile(f, 5),
                    fark25_p95=np.percentile(f, 95), sinif=sinif(np.median(f))))


KISIT = ["P2 Stresle iştah kaybı (-300 kcal)", "P3 Yeme bozukluğu düzeyinde kısıtlama (-1000 kcal)",
         "T3 Tavukla kilo verme (-500 kcal)"]
for ad in ENERJI:
    duy(ad, "ana", KOH.boy(Senaryo(N=fz.N_fonksiyonu(E[ad]["N_ser"], 16.0, 1.0))), B0)
AYARLAR = {"N_min 0.3": Ayar(N_min=0.3), "N_min 0.8": Ayar(N_min=0.8), "N_E doğrusal": Ayar(NE_bicim="dogrusal")}
for v, ayar in AYARLAR.items():
    log(f"Duyarlılık: {v}")
    _, b0 = enerji_senaryosu(Durum(), ayar)
    for ad in KISIT:
        duy(ad, v, enerji_senaryosu(ENERJI[ad], ayar)[1], b0)
log("Duyarlılık: iştah k = 0 / 0")
ayar = Ayar(k_kayip=0.0, k_artis=0.0)
_, b0 = enerji_senaryosu(Durum(), ayar)
for ad in ENERJI:
    duy(ad, "iştah k 0/0", enerji_senaryosu(ENERJI[ad], ayar)[1], b0)
duy("P1 Stresle kısa uyku (6 sa)", "N_uyku 0.95",
    enerji_senaryosu(replace(ENERJI["P1 Stresle kısa uyku (6 sa)"], N_uyku=0.95))[1], B0)
duy("P2 Stresle iştah kaybı (-300 kcal)", "iştah kaybı -500",
    enerji_senaryosu(replace(ENERJI["P2 Stresle iştah kaybı (-300 kcal)"], delta=-500))[1], B0)
for bmi in (18.5, 25.0):
    log(f"Duyarlılık: BMI {bmi}")
    KOH.baslangic(bmi)
    _, b0 = enerji_senaryosu(Durum())
    for ad in KISIT:
        duy(ad, f"BMI {bmi}", enerji_senaryosu(ENERJI[ad])[1], b0)
KOH.baslangic(21.0)
log("Duyarlılık: müdahale 16 yaşında başlasaydı")
duy("K2b Varsayımsal: %10 hızlandırsaydı", "16.0'da başlasaydı", KOH.boy(sabit_N(1.10, bas=16.0)), REF)
duy("P3 Yeme bozukluğu düzeyinde kısıtlama (-1000 kcal)", "16.0-17.0 arasında olsaydı",
    enerji_senaryosu(replace(ENERJI["P3 Yeme bozukluğu düzeyinde kısıtlama (-1000 kcal)"], bas=16.0, bit=17.0))[1], B0)
DTAB = pd.DataFrame(DUY)
DTAB.to_csv(CIKTI / "duyarlilik.csv", index=False, float_format="%.4f")

K3 = []
for ad, g in DTAB.groupby("senaryo", sort=False):
    s = g.sinif.unique()
    K3.append(dict(senaryo=ad, siniflar=" | ".join(s), karar="sağlam" if len(s) == 1 else "varsayıma bağlı",
                   aralik_cm=f"{g.fark25_medyan.min():+.3f} … {g.fark25_medyan.max():+.3f}"))
pd.DataFrame(K3).to_csv(CIKTI / "karar_K3.csv", index=False)


# ---------------------------------------------------------------------------
# 4b. Keşifsel (ön kayıtlı DEĞİL; PLAN 7, sapma 1): gerçek yeme bozukluğu düzeyi ve en kötü durum tavanı
# ---------------------------------------------------------------------------

KES = []
# Enerji modeliyle ağır kısıtlama (-1500 / -2000 kcal, iştah sinyali kapalı) denendi: bir yıllık sabit açık, metabolik
# uyum modellenmediği için zayıf kişilerde yağ kütlesini sıfırın altına indiriyor (S5 assert). Model yeme bozukluğunu
# temsil edemiyor; yerine modelin izin verdiği en kötü durum (N = N_min = 0.5) tavan olarak hesaplanır.
for ad, (c, bas, bit) in {"X1 Tavan: bir yıl boyunca N = 0.5 (17-18)": (0.5, 17.0, 18.0),
                           "X2 Karşılaştırma: aynı tavan 14-15 yaşta": (0.5, 14.0, 15.0)}.items():
    log(ad)
    d, _ = satir(ad, "keşifsel", "D, keşifsel", KOH.boy(sabit_N(c, bas=bas, bit=bit)))
    KES.append(d)
pd.DataFrame(KES).to_csv(CIKTI / "kesifsel.csv", index=False, float_format="%.4f")


# ---------------------------------------------------------------------------
# 5. Sepet profilleri ve grafik
# ---------------------------------------------------------------------------

EI17 = float(np.median(E0["anlar"][17.0]["EI"]))
W17 = float(np.median(E0["anlar"][17.0]["W"]))
PROF = pd.DataFrame({s: besin.sepet_profili(TABLO, g, EI17, "erkek", W17) for s, g in SEPETLER.items()}).T
PROF.to_csv(CIKTI / "sepet_profilleri.csv", float_format="%.2f", index_label="sepet")
OZET["sepet_hedef"] = dict(kcal=EI17, kilo=W17)

fig, ax = plt.subplots(figsize=(10, 6.2), facecolor="#fcfcfb")
renk = {"D (kanıt boşluğu)": "#52514e", "D, varsayımsal": "#c9c8c3", "D (enerji modeli)": "#2a78d6"}
sirali = TAB.iloc[::-1].reset_index(drop=True)
for i, r in sirali.iterrows():
    ax.barh(i, r.fark25_medyan, color=renk[r.etiket], height=0.6)
    ax.plot([r.fark25_p5, r.fark25_p95], [i, i], color="#0b0b0b", lw=1)
    ax.text(0.62, i, f"{r.fark25_medyan:+.2f} cm", va="center", ha="right", fontsize=8.5, color="#52514e")
ax.set_yticks(range(len(sirali)))
ax.set_yticklabels(sirali.senaryo, fontsize=9)
for x in (-0.5, -0.1, 0.1, 0.5):
    ax.axvline(x, color="#e4e3df", lw=1, ls="--", zorder=0)
ax.axvline(0, color="#0b0b0b", lw=0.8)
ax.set_xlabel("25 yaşta boy farkı, referansa göre (cm; çubuk medyan, çizgi %5-%95)")
ax.set_title("17 yaşından sonra: kreatin, psikoloji, tavuk (tipik erkek, model)", loc="left", fontsize=12)
from matplotlib.patches import Patch  # noqa: E402
ax.legend(handles=[Patch(color=c, label=e) for e, c in renk.items()], frameon=False, fontsize=8, loc="lower left")
ax.set_xlim(-0.6, 0.65)
ax.spines[["top", "right"]].set_visible(False)
fig.text(0.01, 0.01, "Kesik çizgiler: ±0.1 ve ±0.5 cm karar eşikleri. Gri = kanıtı olmayan varsayımsal sınır. "
         "Tıbbi tavsiye değildir.", fontsize=8, color="#52514e")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(CIKTI / "senaryolar.png", dpi=150)
plt.close(fig)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
OZET["sure_sn"] = round(time.time() - T_BAS)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(TAB[["senaryo", "fark18_medyan", "fark25_medyan", "fark25_p5", "fark25_p95", "sinif"]].to_string(index=False))
print(pd.DataFrame(K3).to_string(index=False))
print(PROF[["protein_g_kg", "enerji_protein_yuzde", "kalsiyum_rda_yuzde", "d_rda_yuzde", "demir_rda_yuzde",
            "cinko_rda_yuzde"]].round(1).to_string())
print(pd.DataFrame(TESTLER)[["test", "deger", "sonuc"]].to_string(index=False))
print(pd.DataFrame(KES)[["senaryo", "fark18_medyan", "fark25_medyan", "fark25_p5", "fark25_p95"]].to_string(index=False))
