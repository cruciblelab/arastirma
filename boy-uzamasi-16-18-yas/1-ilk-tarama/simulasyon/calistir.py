"""
Tüm simülasyonları çalıştırır, grafikleri ve tabloları ciktilar/ altına yazar.

    python calistir.py

Sonuçlar sabit tohumla (seed) üretilir, tekrar çalıştırınca aynı sayılar çıkar.
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from model import (DinamikAyar, Donem, ortalama_birey, pb_boy, pb_hiz,
                   populasyon_ornekle, simule_et)

CIKTI = Path(__file__).parent / "ciktilar"
CIKTI.mkdir(exist_ok=True)
RNG = np.random.default_rng(20261007)

# Plak "fonksiyonel olarak açık" eşiği: o yaşta yıllık büyüme hızı en az bu kadar.
# Röntgende "açık" görünen plak 0.2 cm/yıl da büyüyor olabilir; bu ayrım önemli.
ACIK_ESIK = 0.5  # cm/yıl
SON_YAS = 25.0

# Görsel ayarlar (dataviz referans paleti, açık tema)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERI = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10.5,
    "axes.titlesize": 12, "axes.titleweight": "bold", "lines.linewidth": 2,
})


def kaydet(fig, ad):
    fig.tight_layout()
    fig.savefig(CIKTI / ad, dpi=150)
    plt.close(fig)


def csv_yaz(ad, basliklar, satirlar):
    with open(CIKTI / ad, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(basliklar)
        w.writerows(satirlar)


# ---------------------------------------------------------------------------
# 1) Popülasyon: 16/17/18 yaşında plak açıkken ne kadar boy kalıyor?
# ---------------------------------------------------------------------------

def populasyon_analizi(n=200_000):
    satirlar = []
    sonuc = {}
    for cins in ("erkek", "kiz"):
        par = populasyon_ornekle(cins, n, RNG)
        son = pb_boy(par, SON_YAS)
        for yas in (16, 17, 18):
            kalan = son - pb_boy(par, yas)
            hiz = pb_hiz(par, yas)
            acik = hiz >= ACIK_ESIK
            k_acik = kalan[acik]
            p10, p50, p90 = np.percentile(k_acik, [10, 50, 90]) if acik.any() else (0, 0, 0)
            p_gt2 = float(np.mean(k_acik > 2)) if acik.any() else 0.0
            p_gt5 = float(np.mean(k_acik > 5)) if acik.any() else 0.0
            satirlar.append([cins, yas, f"{acik.mean():.3f}", f"{np.median(kalan):.2f}",
                             f"{p10:.2f}", f"{p50:.2f}", f"{p90:.2f}", f"{p_gt2:.3f}", f"{p_gt5:.3f}"])
            sonuc[(cins, yas)] = (acik.mean(), p10, p50, p90, p_gt2, p_gt5)
    csv_yaz("1_populasyon_kalan_boy.csv",
            ["cinsiyet", "yas", "plagi_fonksiyonel_acik_orani", "herkes_icin_medyan_kalan_cm",
             "acik_olanlarda_p10_cm", "acik_olanlarda_medyan_cm", "acik_olanlarda_p90_cm",
             "acik_olanlarda_P(kalan>2cm)", "acik_olanlarda_P(kalan>5cm)"], satirlar)

    # Grafik: kalan boy vs olgunlaşma gecikmesi (asıl belirleyici)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    kaymalar = np.linspace(-1.5, 2.5, 161)
    for ax, cins, baslik in zip(axes, ("erkek", "kiz"), ("Erkek", "Kız")):
        for j, yas in enumerate((16, 17, 18)):
            kalan = [ortalama_birey(cins, k).boy(SON_YAS) - ortalama_birey(cins, k).boy(yas)
                     for k in kaymalar]
            ax.plot(kaymalar, kalan, color=SERI[j], label=f"{yas} yaşında")
            ax.annotate(f"{yas}", (kaymalar[-1], kalan[-1]), xytext=(4, 0),
                        textcoords="offset points", va="center", color=INK2, fontsize=9)
        ax.axvline(0, color=INK2, lw=1, ls=":")
        ax.text(0.05, 0.97 * ax.get_ylim()[1] if ax.get_ylim()[1] else 1, "ortalama\nolgunlaşma",
                color=INK2, fontsize=8.5, va="top")
        ax.set_title(f"{baslik}: kalan boy, olgunlaşma zamanına göre")
        ax.set_xlabel("Olgunlaşma gecikmesi (yıl, ~kemik yaşı geriliği)")
        ax.set_xlim(-1.5, 2.8)
    axes[0].set_ylabel("Kalan boy uzaması (cm)")
    axes[0].legend(frameon=False, loc="upper left", bbox_to_anchor=(0.0, 0.85))
    kaydet(fig, "1_kalan_boy_vs_olgunlasma.png")
    return sonuc


# ---------------------------------------------------------------------------
# 2) Senaryolar: 16 yaşında, geç olgunlaşan (plağı belirgin açık) bir erkek
# ---------------------------------------------------------------------------

SENARYOLAR = {
    "Optimal (genetik rota)": [],
    "Eksiklik 16-18, 18'de düzeltildi": [Donem(16, 18, m=0.85)],
    "Eksiklik 16-21, hiç düzeltilmedi": [Donem(16, 21, m=0.85)],
    "Anabolik/androjen 6 ay (16-16.5)": [Donem(16, 16.5, m=0.6, r=2.5)],
    # AI: kemik yaşı ilerleyişi %60, takvim büyüme hızı normalin %80i -> m = 0.8/0.6
    "Aromataz inhibitörü 16-18 (hekim)": [Donem(16, 18, m=0.8 / 0.6, r=0.6)],
}


def senaryo_analizi(theta_kayma=1.2):
    birey = ortalama_birey("erkek", theta_kayma)
    fig, ax = plt.subplots(figsize=(9, 5))
    satirlar = []
    opt_son = None
    for j, (ad, donemler) in enumerate(SENARYOLAR.items()):
        t, h, tau = simule_et(birey, donemler, 16.0)
        son = h[-1]
        if opt_son is None:
            opt_son = son
        satirlar.append([ad, f"{h[0]:.1f}", f"{son:.1f}", f"{son - opt_son:+.1f}", f"{tau[-1] - t[-1]:+.2f}"])
        ax.plot(t, h, color=SERI[j], label=f"{ad}: {son:.1f} cm ({son - opt_son:+.1f})")
    ax.set_xlim(16, 23)
    ax.set_xlabel("Yaş")
    ax.set_ylabel("Boy (cm)")
    ax.set_title("Geç olgunlaşan 16 yaş erkek: senaryolara göre boy (oyuncak model)")
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    kaydet(fig, "2_senaryolar_gec_olgunlasan_erkek.png")
    csv_yaz("2_senaryolar.csv", ["senaryo", "boy_16_cm", "son_boy_cm", "optimale_gore_fark_cm",
                                 "biyolojik_saat_farki_yil"], satirlar)
    return satirlar, birey


# ---------------------------------------------------------------------------
# 3) Eksiklik ne zaman düzeltilirse ne kadar kayıp kalır?
# ---------------------------------------------------------------------------

def duzeltme_zamani_analizi():
    duzeltme = np.round(np.arange(16.25, 21.01, 0.25), 2)
    kaymalar = {"Ortalama olgunlaşma": 0.0, "1 yıl geç": 1.0, "2 yıl geç": 2.0}
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    satirlar = []
    for j, (ad, k) in enumerate(kaymalar.items()):
        birey = ortalama_birey("erkek", k)
        _, h_opt, _ = simule_et(birey, [], 16.0)
        kayip = []
        for d in duzeltme:
            _, h, _ = simule_et(birey, [Donem(16, d, m=0.85)], 16.0)
            kayip.append(h_opt[-1] - h[-1])
            satirlar.append([ad, d, f"{kayip[-1]:.2f}"])
        ax.plot(duzeltme, kayip, color=SERI[j], label=ad)
    ax.set_xlabel("Eksikliğin düzeltildiği yaş (eksiklik 16'da başlıyor, büyüme verimi %85)")
    ax.set_ylabel("Kalıcı boy kaybı (cm)")
    ax.set_title("Erkek: geç düzeltilen eksiklik ne kadar boy götürür?")
    ax.legend(frameon=False, loc="upper left")
    kaydet(fig, "3_duzeltme_zamani_kayip.png")
    csv_yaz("3_duzeltme_zamani.csv", ["olgunlasma", "duzeltme_yasi", "kalici_kayip_cm"], satirlar)


# ---------------------------------------------------------------------------
# 4) Duyarlılık: varsayım parametreleri değişince sonuç ne kadar oynuyor?
# ---------------------------------------------------------------------------

def duyarlilik_analizi(theta_kayma=1.2):
    birey = ortalama_birey("erkek", theta_kayma)
    satirlar = []
    for alfa in (0.0, 0.25, 0.5, 0.75, 1.0):
        for k in (0.3, 1.0, 2.0):
            ayar = DinamikAyar(alfa=alfa, k=k)
            _, h_opt, _ = simule_et(birey, [], 16.0, ayar=ayar)
            _, h1, _ = simule_et(birey, [Donem(16, 18, m=0.85)], 16.0, ayar=ayar)
            _, h2, _ = simule_et(birey, [Donem(16, 21, m=0.85)], 16.0, ayar=ayar)
            satirlar.append([alfa, k, f"{h_opt[-1] - h1[-1]:.2f}", f"{h_opt[-1] - h2[-1]:.2f}"])
    csv_yaz("4_duyarlilik.csv", ["alfa", "k", "kayip_18de_duzeltilirse_cm", "kayip_hic_duzeltilmezse_cm"],
            satirlar)
    return satirlar


# ---------------------------------------------------------------------------
# 5) Aromataz inhibitörü: kazanç neye bağlı?
# AI kemik olgunlaşmasını yavaşlatır (r<1). Ama östrojen ergenlikteki GH/IGF-1
# artışına da katkı verdiği için takvim yaşına göre büyüme hızı da düşebilir.
# q = takvim büyüme hızı / normal hız. Modelde m = q / r.
# Net kazanç ancak q > r ise var: büyüme hızı, kemik yaşından DAHA AZ
# yavaşlamalı. RCT'lerde monoterapide kalıcı kazanç gösterilemedi; bu tablo
# kazancın neden bu orana bu kadar hassas olduğunu gösteriyor.
# ---------------------------------------------------------------------------

def aromataz_analizi():
    satirlar = []
    for kayma, ad in ((0.0, "ortalama"), (1.2, "gec")):
        birey = ortalama_birey("erkek", kayma)
        _, h_opt, _ = simule_et(birey, [], 16.0)
        for r in (0.5, 0.6, 0.75):
            for q in (0.5, 0.6, 0.7, 0.8, 0.9):
                _, h, _ = simule_et(birey, [Donem(16, 18, m=q / r, r=r)], 16.0)
                satirlar.append([ad, r, q, f"{h[-1] - h_opt[-1]:+.2f}"])
    csv_yaz("5_aromataz_duyarlilik.csv", ["olgunlasma", "r_kemik_yasi_hizi", "q_takvim_buyume_hizi_orani",
                                          "son_boy_farki_cm"], satirlar)
    return satirlar


if __name__ == "__main__":
    pop = populasyon_analizi()
    print("== Popülasyon (plağı fonksiyonel açık olanlarda kalan boy, cm) ==")
    for (c, y), (oran, p10, p50, p90, g2, g5) in pop.items():
        print(f"{c:5s} {y}: açık oranı {oran:5.1%} | p10 {p10:4.1f}  medyan {p50:4.1f}  p90 {p90:4.1f}"
              f" | P(>2cm) {g2:5.1%}  P(>5cm) {g5:5.1%}")
    sen, birey = senaryo_analizi()
    print("\n== Senaryolar (geç olgunlaşan erkek, 16 yaş) ==")
    print(f"16 yaş hızı: {float(birey.hiz(16)):.1f} cm/yıl")
    for s in sen:
        print("  ", " | ".join(map(str, s)))
    duzeltme_zamani_analizi()
    print("\n== Duyarlılık (alfa, k, kayıp-18'de düzeltilirse, kayıp-hiç) ==")
    for s in duyarlilik_analizi():
        print("  ", s)
    print("\n== Aromataz inhibitörü 16-18 (olgunlaşma, r, q, fark) ==")
    for s in aromataz_analizi():
        print("  ", s)
