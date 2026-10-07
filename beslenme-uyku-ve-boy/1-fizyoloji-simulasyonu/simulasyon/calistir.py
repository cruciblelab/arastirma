"""
Beslenme, iştah, vücut yağı, uyku ve boy simülasyonu (PLAN.md). Tek komut:

    python calistir.py

Adımlar
  0  USDA yiyecek tablosu ve sepet profilleri
  1  Sanal kohort (sürüm 3 modeli, Türk uyarlamalı) + 1. geçiş boy eğrileri
  2  Senaryolar S0-S9 (ana varsayımlar) → enerji/vücut bileşimi → N(t) → 2. geçiş boy
  3  Ön kayıtlı testler F1-F5
  4  Duyarlılık analizi ve K1/K2 sınıflaması
  5  Grafik
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
sys.path.append(str(REPO / "spor-egzersiz-ve-boy" / "1-fizik-tabanli-simulasyon" / "simulasyon"))
sys.path.append(str(REPO / "boy-uzamasi-16-18-yas" / "3-mekanistik-simulasyon-ve-on-kayit" / "simulasyon"))

import plak                                   # noqa: E402  (spor araştırması: sanal kohort)
from model import DT, Senaryo, simule_et      # noqa: E402  (boy araştırması sürüm 3: büyüme plağı)

import besin                                  # noqa: E402
import fizyoloji as fz                        # noqa: E402
from fizyoloji import Ayar, Durum             # noqa: E402

CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
TOHUM = 20261007
N_KOHORT = 2000
CINS = ("erkek", "kiz")
AD = {"erkek": "Erkek", "kiz": "Kız"}
IZGARA = np.round(np.arange(16.0, 25.0 + 1e-9, 0.02), 2)
OZET, TESTLER = {}, []
K4_MAX, K4_NOT = [0.0], []
T_BAS = time.time()

SPOR_SAAT = 2 * 6 / 7       # futbol 2 sa/gün, 6 gün/hafta
SENARYOLAR = {
    "S0 Referans": Durum(),
    "S1 Diyet -500 kcal": Durum(delta=-500),
    "S1b Sert diyet -1000 kcal": Durum(delta=-1000),
    "S2 Yoğun spor, telafisiz": Durum(spor_saat=SPOR_SAAT),
    "S2b Yoğun spor + diyet -500": Durum(spor_saat=SPOR_SAAT, delta=-500),
    "S3 Yüksek protein": Durum(sepet="B4 Yüksek protein"),
    "S4 Düşük protein": Durum(sepet="B3 Düşük protein"),
    "S5 Fast food +500 kcal": Durum(sepet="B2 Fast food", delta=500),
    "S6 Kısa uyku (6 sa)": Durum(uyku_kcal=385),
    "S7 Uyku bozukluğu": Durum(N_uyku=0.9),
    "S8 Spor + yeterli beslenme": Durum(spor_saat=SPOR_SAAT, spora_gore_yer=True),
    "S9 Etsiz": Durum(sepet="B5 Etsiz"),
}


def log(*a):
    print(f"[{time.time() - T_BAS:6.0f} sn]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'} ({deger})")


# ---------------------------------------------------------------------------
# 0. Besin katmanı
# ---------------------------------------------------------------------------

TABLO, EKSIK = besin.yiyecek_tablosu()
TABLO.to_csv(CIKTI / "yiyecekler_100g.csv", index_label="yiyecek", float_format="%.3f")
PROT_YOG = {s: besin.protein_yogunlugu(TABLO, g) for s, g in besin.SEPETLER.items()}
OZET["usda_eksik_kayitlar"] = EKSIK
OZET["protein_g_1000kcal"] = {s: round(1000 * v, 2) for s, v in PROT_YOG.items()}


# ---------------------------------------------------------------------------
# 1. Kohort
# ---------------------------------------------------------------------------

class Kohort:
    def __init__(self, cinsiyet):
        rng = np.random.default_rng(TOHUM + (0 if cinsiyet == "erkek" else 1))
        self.c = cinsiyet
        self.pop, self.ind, self.L0b, self.L0g = plak.kohort(cinsiyet, N_KOHORT, rng)
        s = simule_et(self.ind, self.pop, self.L0b, self.L0g, t1=25.0, kayit_yaslari=IZGARA)
        self.H = s["boy"].T / 100.0                  # (n, len(IZGARA)) metre
        self.e_bmi = rng.standard_normal(N_KOHORT)
        self.z = rng.standard_normal(N_KOHORT)
        self.baslangic(21.0)

    def baslangic(self, bmi_medyan):
        self.BMI0 = np.clip(np.exp(np.log(bmi_medyan) + 0.13 * self.e_bmi), 16, 32)
        H0 = self.H[:, 0]
        self.W0 = self.BMI0 * H0 ** 2
        bf = np.clip(1.51 * self.BMI0 - 0.70 * 16 - 3.6 * (self.c == "erkek") + 1.4, 5, 45)
        self.FM0 = self.W0 * bf / 100

    def H_fn(self, H=None):
        H = self.H if H is None else H
        son = H.shape[1] - 1

        def f(yas):
            x = (yas - 16.0) / 0.02
            i = int(np.clip(np.floor(x), 0, son))
            if i >= son:
                return H[:, son]
            t = x - i
            return H[:, i] * (1 - t) + H[:, i + 1] * t
        return f

    def enerji(self, durum, ayar, dt=1.0, H=None, **kw):
        return fz.simule(self.c, self.W0, self.FM0, self.H_fn(H), self.z, PROT_YOG, durum, ayar, dt=dt, **kw)

    def boy(self, N_ser, dt_gun=1.0, dt_rk=DT, kayit=(18.0, 25.0)):
        sen = Senaryo(N=fz.N_fonksiyonu(N_ser, 16.0, dt_gun))
        return simule_et(self.ind, self.pop, self.L0b, self.L0g, t1=25.0, dt=dt_rk, senaryo=sen,
                         kayit_yaslari=list(kayit))["boy"]


log("Kohort kuruluyor")
KOH = {c: Kohort(c) for c in CINS}
for c in CINS:
    k = KOH[c]
    OZET[f"kohort_{c}"] = dict(n=N_KOHORT, boy16_medyan_cm=float(np.median(k.H[:, 0]) * 100),
                               kalan_buyume_16_25_medyan_cm=float(np.median(k.H[:, -1] - k.H[:, 0]) * 100),
                               W16_medyan=float(np.median(k.W0)), BMI16_medyan=float(np.median(k.BMI0)),
                               BF16_medyan=float(np.median(100 * k.FM0 / k.W0)))

# Sepet profilleri: her cinsiyetin 16 yaş medyan referans alımında
sepet_satir = []
for c in CINS:
    k = KOH[c]
    W, H = float(np.median(k.W0)), float(np.median(k.H[:, 0]))
    kcal = fz.bmr(W, H, 16.0, c == "erkek") * 1.55
    for s, g in besin.SEPETLER.items():
        sepet_satir.append(dict(cinsiyet=c, sepet=s, **besin.sepet_profili(TABLO, g, kcal, c, W)))
pd.DataFrame(sepet_satir).to_csv(CIKTI / "sepet_profilleri.csv", index=False, float_format="%.2f")


# ---------------------------------------------------------------------------
# 2. Senaryolar
# ---------------------------------------------------------------------------

def kos(ayar, senaryolar=SENARYOLAR, bmi=21.0, ayrinti=False):
    """Her cinsiyet ve senaryo için 18 ve 25 yaş boy farkı (S0'a göre, aynı kişi)."""
    satirlar, ser = [], {}
    for c in CINS:
        k = KOH[c]
        k.baslangic(bmi)
        sonuc = {}
        for ad, d in {"S0 Referans": SENARYOLAR["S0 Referans"], **senaryolar}.items():
            try:
                e = k.enerji(d, ayar)
            except AssertionError as hata:
                # Sapma 4: iştah kapalıyken uzun süreli açık dokuyu tüketebilir. Yalnızca k = 0 varyantlarında
                # "sürdürülemez" diye kaydedilir; ana modelde bu assert durdurucu kalır.
                if "negatif doku" not in str(hata) or ayar.k_kayip > 0:
                    raise
                satirlar.append(dict(varyant=ayar.etiket, cinsiyet=c, senaryo=ad, surdurulemez=True))
                continue
            b = k.boy(e["N_ser"])
            assert np.all(e["F1"] < 1e-3), f"F1 enerji korunumu: {ad}"
            sonuc[ad] = (e, b)
        e0, b0 = sonuc["S0 Referans"]
        for ad, (e, b) in sonuc.items():
            d18, d25 = (b[0] - b0[0]), (b[1] - b0[1])
            # K4 (sapma 2-3): sayısal tolerans 1e-4 cm; yalnızca S0 tavandayken (N ≡ 1) assert edilir.
            # S0'ın kendisi kısıtlıysa (ör. doğrusal N_E) daha çok yiyen kişinin uzun çıkması varsayımın sonucudur.
            if np.all(e0["N_ser"] == 1.0):
                K4_MAX[0] = max(K4_MAX[0], float(d18.max()), float(d25.max()))
                assert np.all(d18 <= 1e-4) and np.all(d25 <= 1e-4), f"K4: {ad} referanstan uzun çıktı (hata)"
            else:
                K4_NOT.append(dict(varyant=ayar.etiket, cinsiyet=c, senaryo=ad,
                                   S0_kisitli_yuzde=100 * float(np.mean(e0["min_N"] < 0.999)),
                                   uzun_cikan_yuzde=100 * float(np.mean(d25 > 1e-4)), en_buyuk_pozitif_cm=float(d25.max())))
            a18, a18_0 = e["anlar"][18.0], e0["anlar"][18.0]
            satir = dict(varyant=ayar.etiket, cinsiyet=c, senaryo=ad,
                         dH18_medyan_cm=np.median(d18), dH18_p5_cm=np.percentile(d18, 5),
                         dH25_medyan_cm=np.median(d25), dH25_p5_cm=np.percentile(d25, 5),
                         dH25_p95_cm=np.percentile(d25, 95), dH25_ortalama_cm=d25.mean(),
                         etkilenen_yuzde=100 * np.mean(e["min_N"] < 0.999),
                         minN_medyan=np.median(e["min_N"]), surdurulemez=False,
                         BMI16_alti_18yas_yuzde=100 * np.mean(a18["BMI"] < 16), BMI18_min=a18["BMI"].min())
            if ayrinti:
                a17 = e["anlar"][17.0]
                satir.update(dW18_medyan_kg=np.median(a18["W"] - a18_0["W"]),
                             dFM18_medyan_kg=np.median(a18["FM"] - a18_0["FM"]),
                             BF18_medyan=np.median(a18["BF"]), dBF18_medyan=np.median(a18["BF"] - a18_0["BF"]),
                             BMI18_medyan=np.median(a18["BMI"]),
                             W25_fark_medyan_kg=np.median(e["anlar"][25.0]["W"] - e0["anlar"][25.0]["W"]),
                             EI17_medyan=np.median(a17["EI"]), TEE17_medyan=np.median(a17["TEE"]),
                             EA17_medyan=np.median(a17["EA"]), minEA_medyan=np.median(e["min_EA"]),
                             minEA_p5=np.percentile(e["min_EA"], 5),
                             protein17_gkg_medyan=np.median(a17["P_gkg"]),
                             yakalama_orani=(1 - np.median(d25) / np.median(d18)) if np.median(d18) < -1e-6 else np.nan,
                             F1_max=float(e["F1"].max()))
                ser[(c, ad)] = dict(yas=e["yas"].mean(0), W=e["W"].mean(0), N=e["N"].mean(0), EA=e["EA"].mean(0))
            satirlar.append(satir)
        k.baslangic(21.0)
    return pd.DataFrame(satirlar), ser


ANA = Ayar()
log("Ana senaryolar")
ana, SERI = kos(ANA, ayrinti=True)
ana.to_csv(CIKTI / "senaryolar_ana.csv", index=False, float_format="%.4f")
for _, r in ana.iterrows():
    log(f"  {r.cinsiyet:5s} {r.senaryo:30s} dH18 {r.dH18_medyan_cm:+.3f}  dH25 {r.dH25_medyan_cm:+.3f} cm  "
        f"dW18 {r.dW18_medyan_kg:+.1f} kg  BF18 {r.BF18_medyan:.1f}%  minEA {r.minEA_medyan:.1f}  "
        f"P {r.protein17_gkg_medyan:.2f} g/kg  etkilenen %{r.etkilenen_yuzde:.0f}")


# ---------------------------------------------------------------------------
# 3. Ön kayıtlı testler
# ---------------------------------------------------------------------------

# F1: ana koşudaki her senaryo ve kişi için kos() içinde assert edildi; en büyük değeri raporla
f1 = float(ana.F1_max.max())
test("F1", "Enerji korunumu (göreli hata, bütün senaryolar ve kişiler)", f"{f1:.2e}", "< 1e-3", f1 < 1e-3)

# F2: TEE ve IOM EER, 16 yaş medyan erkek
k = KOH["erkek"]
W, H = float(np.median(k.W0)), float(np.median(k.H[:, 0]))
tee = fz.bmr(W, H, 16.0, True) * 1.55
eer = 88.5 - 61.9 * 16 + 1.13 * (26.7 * W + 903 * H) + 25
OZET["F2"] = dict(W=W, H=H, TEE_model=tee, EER_IOM=eer, fark_yuzde=100 * (tee / eer - 1))
test("F2", "16 yaş medyan erkek: model TEE ve IOM EER (az aktif)", f"{tee:.0f} / {eer:.0f} kcal ({100 * (tee / eer - 1):+.1f}%)",
     "±%10", abs(tee / eer - 1) < 0.10)

# F3: Hall 2011 dinamiği (fazla kilolu yetişkin benzeri kişi, iştah kapalı, +100 kJ/gün)
e3 = fz.simule("erkek", np.array([90.0]), np.array([27.0]), lambda y: np.array([1.75]), np.zeros(1), PROT_YOG,
               Durum(delta=100 / 4.184, bas=25.0, bit=1e9), Ayar(k_kayip=0, k_artis=0),
               yas0=25.0, yas1=35.0, kayit_her=1)
dW = e3["W"][0] - 90.0
son = float(dW[-1])
yari = float(e3["yas"][0][np.argmax(dW >= 0.5 * son)] - 25.0)
OZET["F3"] = dict(artis_10yil_kg=son, yarilanma_yil=yari, artis_1yil_kg=float(dW[366]), artis_3yil_kg=float(dW[1096]))
test("F3a", "Hall 2011: +100 kJ/gün → 10 yılda kilo artışı", f"{son:.2f} kg", "0.8-1.25 kg", 0.8 <= son <= 1.25)
test("F3b", "Hall 2011: yarılanma süresi", f"{yari:.2f} yıl", "0.4-1.2 yıl", 0.4 <= yari <= 1.2)

# F4: yakınsama (S2b)
d2b = SENARYOLAR["S2b Yoğun spor + diyet -500"]
f4a, f4b, f4c = [], [], []
for c in CINS:
    k = KOH[c]
    e1 = k.enerji(d2b, ANA)
    eh = k.enerji(d2b, ANA, dt=0.5)
    f4a.append(float(np.max(np.abs(e1["anlar"][18.0]["W"] - eh["anlar"][18.0]["W"]))))
    b1 = k.boy(e1["N_ser"])
    b2 = k.boy(e1["N_ser"], dt_rk=DT / 2)
    f4b.append(float(np.max(np.abs(b1[1] - b2[1]))))
    # İkinci iterasyon: 2. geçişin boy eğrisiyle enerji modelini yeniden çöz
    H2 = simule_et(k.ind, k.pop, k.L0b, k.L0g, t1=25.0, kayit_yaslari=IZGARA,
                   senaryo=Senaryo(N=fz.N_fonksiyonu(e1["N_ser"], 16.0, 1.0)))["boy"].T / 100.0
    e2 = k.enerji(d2b, ANA, H=H2)
    b3 = k.boy(e2["N_ser"])
    f4c.append(float(np.max(np.abs(b3[1] - b1[1]))))
test("F4a", "Enerji modeli Δt 1 gün / 0.5 gün, 18 yaş kilo farkı (S2b, en büyük)", f"{max(f4a):.4f} kg", "< 0.05 kg", max(f4a) < 0.05)
test("F4b", "Büyüme RK2 Δt / Δt/2, son boy farkı (S2b, en büyük)", f"{max(f4b):.5f} cm", "< 0.01 cm", max(f4b) < 0.01)
test("F4c", "İkinci iterasyon, son boy farkı (S2b, en büyük)", f"{max(f4c):.5f} cm", "< 0.01 cm", max(f4c) < 0.01)

# F5: S0'da N ≡ 1 ve boy, sürüm 3'ün senaryosuz çıktısıyla aynı
f5 = []
for c in CINS:
    k = KOH[c]
    e0 = k.enerji(SENARYOLAR["S0 Referans"], ANA)
    assert np.all(e0["N_ser"] == 1.0), "F5: S0'da N ≡ 1 değil"
    b0 = k.boy(e0["N_ser"])
    bv3 = simule_et(k.ind, k.pop, k.L0b, k.L0g, t1=25.0, kayit_yaslari=[18.0, 25.0])["boy"]
    f5.append(float(np.max(np.abs(b0 - bv3))))
test("F5", "S0 (N ≡ 1) ve sürüm 3 senaryosuz çıktı", f"{max(f5):.1e} cm", "< 1e-9 cm", max(f5) < 1e-9)


# ---------------------------------------------------------------------------
# 4. Duyarlılık
# ---------------------------------------------------------------------------

def sinif(x):
    x = abs(x)
    return "fark edilir (≥0.5 cm)" if x >= 0.5 else ("ölçülemeyecek kadar küçük (0.1-0.5)" if x >= 0.1 else "yok (<0.1 cm)")


VARYANTLAR = [
    (replace(ANA, NE_bicim="dogrusal", etiket="N_E doğrusal"), None, 21.0),
    (replace(ANA, N_min=0.3, etiket="N_min 0.3"), None, 21.0),
    (replace(ANA, N_min=0.8, etiket="N_min 0.8"), None, 21.0),
    (replace(ANA, b=0.5, etiket="protein b 0.5"), None, 21.0),
    (replace(ANA, b=2.0, etiket="protein b 2"), None, 21.0),
    (replace(ANA, cv=0.08, etiket="protein CV 0.08"), None, 21.0),
    (replace(ANA, cv=0.16, etiket="protein CV 0.16"), None, 21.0),
    (replace(ANA, k_artis=0.0, etiket="iştah: artışta k=0"), None, 21.0),
    (replace(ANA, k_artis=0.0, k_kayip=0.0, etiket="iştah: k=0 (sabit alım)"), None, 21.0),
    (replace(ANA, PAL=1.40, etiket="PAL 1.40"), None, 21.0),
    (replace(ANA, PAL=1.70, etiket="PAL 1.70"), None, 21.0),
    (replace(ANA, etiket="BMI medyanı 18.5"), None, 18.5),
    (replace(ANA, etiket="BMI medyanı 25"), None, 25.0),
    (replace(ANA, etiket="S6 N_uyku 0.95"), {"S6 Kısa uyku (6 sa)": Durum(uyku_kcal=385, N_uyku=0.95)}, 21.0),
    (replace(ANA, etiket="S6 mekanik ek harcama"), {"S6 Kısa uyku (6 sa)": Durum(uyku_kcal=385, ek_harcama_saat=2.5)}, 21.0),
    (replace(ANA, etiket="S7 N_uyku 0.8"), {"S7 Uyku bozukluğu": Durum(N_uyku=0.8)}, 21.0),
    (replace(ANA, etiket="S7 N_uyku 0.95"), {"S7 Uyku bozukluğu": Durum(N_uyku=0.95)}, 21.0),
    (replace(ANA, NE_bicim="dogrusal", dogrusal_taban=0.3, N_min=0.3, b=2.0, k_kayip=0.0, k_artis=0.0,
             etiket="en kötümser kombinasyon"), None, 21.0),
]
tum = [ana.drop(columns=[c for c in ana.columns if c not in
                         ("varyant", "cinsiyet", "senaryo", "dH18_medyan_cm", "dH25_medyan_cm", "dH25_p5_cm",
                          "etkilenen_yuzde", "surdurulemez", "BMI16_alti_18yas_yuzde")])]
for ayar, ozel, bmi in VARYANTLAR:
    log("Duyarlılık:", ayar.etiket)
    df, _ = kos(ayar, senaryolar=ozel or SENARYOLAR, bmi=bmi)
    tum.append(df.reindex(columns=["varyant", "cinsiyet", "senaryo", "dH18_medyan_cm", "dH25_medyan_cm", "dH25_p5_cm",
                                   "etkilenen_yuzde", "surdurulemez", "BMI16_alti_18yas_yuzde"]))
duy = pd.concat(tum, ignore_index=True)
duy = duy[duy.senaryo != "S0 Referans"]
duy["sinif"] = np.where(duy.surdurulemez.astype(bool), "sürdürülemez (doku tükeniyor)",
                        duy.dH25_medyan_cm.map(lambda x: sinif(x) if pd.notna(x) else ""))
duy.to_csv(CIKTI / "duyarlilik.csv", index=False, float_format="%.4f")

k2 = []
for (c, s), g in duy.groupby(["cinsiyet", "senaryo"], sort=False):
    ana_s = g[g.varyant == "ana"].iloc[0]
    gg = g[~g.surdurulemez.astype(bool)]
    k2.append(dict(cinsiyet=c, senaryo=s, ana_dH25_cm=ana_s.dH25_medyan_cm, ana_sinif=ana_s.sinif,
                   en_kotu_dH25_cm=gg.dH25_medyan_cm.min(), en_kotu_varyant=gg.loc[gg.dH25_medyan_cm.idxmin(), "varyant"],
                   en_kotu_p5_cm=gg.dH25_p5_cm.min(),
                   siniflar=" | ".join(sorted(set(gg.sinif))),
                   K2="sağlam" if gg.sinif.nunique() == 1 else "varsayıma bağlı",
                   sinifi_degistiren=", ".join(gg[gg.sinif != ana_s.sinif].varyant),
                   surdurulemez_varyantlar=", ".join(g[g.surdurulemez.astype(bool)].varyant),
                   BMI16_alti_en_cok_yuzde=g.BMI16_alti_18yas_yuzde.max(),
                   BMI16_alti_varyant=(g.loc[g.BMI16_alti_18yas_yuzde.idxmax(), "varyant"]
                                       if g.BMI16_alti_18yas_yuzde.notna().any() else "")))
k2 = pd.DataFrame(k2)
k2.to_csv(CIKTI / "karar_K1_K2.csv", index=False, float_format="%.4f")
print(k2.to_string())

# Keşifsel (sonradan eklendi, sapma 4): kısıtlamayı kısmen sürdüren genç, zayıf iştah k = 25. K2'ye girmez.
log("Keşifsel: zayıf iştah k=25")
kes, _ = kos(replace(ANA, k_kayip=25.0, k_artis=25.0, etiket="keşifsel: zayıf iştah k=25"), ayrinti=True)
kes.to_csv(CIKTI / "kesifsel_zayif_istah.csv", index=False, float_format="%.4f")


# ---------------------------------------------------------------------------
# 5. Grafik
# ---------------------------------------------------------------------------

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
RENK = {"S1 Diyet -500 kcal": "#2a6fdb", "S1b Sert diyet -1000 kcal": "#16407f", "S2 Yoğun spor, telafisiz": "#e07b00",
        "S2b Yoğun spor + diyet -500": "#b3261e", "S5 Fast food +500 kcal": "#7b3fa0", "S6 Kısa uyku (6 sa)": "#2e8b57",
        "S8 Spor + yeterli beslenme": "#8a8a85"}
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE})
fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
for c, ls in (("erkek", "-"), ("kiz", "--")):
    s0 = SERI[(c, "S0 Referans")]
    for ad, renk in RENK.items():
        s = SERI[(c, ad)]
        ax[0].plot(s["yas"], s["W"] - s0["W"], ls, color=renk, lw=1.4, label=ad if c == "erkek" else None)
        ax[1].plot(s["yas"], s["N"], ls, color=renk, lw=1.4)
for a in ax[:2]:
    a.axvspan(16, 18, color=GRID, alpha=0.6, lw=0)
    a.set_xlim(16, 21)
    a.set_xlabel("Yaş")
ax[0].set_ylabel("Kilo farkı, S0'a göre (kg, ortalama)")
ax[0].set_title("Vücut ağırlığı (düz: erkek, kesikli: kız)")
ax[1].set_ylabel("Büyüme çarpanı N (ortalama)")
ax[1].set_title("Plak çıktısına uygulanan çarpan")
ax[0].legend(fontsize=7, frameon=False)
sen = [s for s in SENARYOLAR if s != "S0 Referans"]
y = np.arange(len(sen))
for j, (c, renk) in enumerate((("erkek", "#2a6fdb"), ("kiz", "#e07b00"))):
    v = ana.set_index(["cinsiyet", "senaryo"]).loc[c].loc[sen, "dH25_medyan_cm"].values * 10
    ax[2].barh(y + (j - 0.5) * 0.38, v, 0.38, color=renk, label=AD[c])
ax[2].set_yticks(y, sen, fontsize=7.5)
ax[2].invert_yaxis()
ax[2].axvline(-1, color=INK2, lw=0.8, ls=":")
ax[2].set_xlabel("Son boy farkı, 25 yaş (mm, medyan)")
ax[2].set_title("Son boya etki (ana varsayımlar)")
ax[2].legend(frameon=False, fontsize=8)
fig.tight_layout()
fig.savefig(CIKTI / "senaryolar.png", dpi=150)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
OZET["testler"] = TESTLER
OZET["K4_en_buyuk_pozitif_fark_cm"] = K4_MAX[0]
pd.DataFrame(K4_NOT).to_csv(CIKTI / "K4_S0_kisitli_varyantlar.csv", index=False, float_format="%.4f")
OZET["sure_sn"] = round(time.time() - T_BAS)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
log("Bitti")
