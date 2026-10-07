"""
Kişisel kalan boy tahmini, v2.

v1'den farkı: önsel dağılım artık elle ayarlanmış değil; Berkeley verisindeki
133 gerçek bireye fit edilen büyüme eğrilerinden (ciktilar/A_pb1_parametreleri.csv)
geliyor. Erişkin boy ortalaması Türkiye referansına kaydırılıyor, eğri şekli ve
korelasyonlar gerçek veriden korunuyor. Araç gerçek veride birini-dışarıda-bırak
yöntemiyle doğrulandı (README, bölüm 4.5).

Örnek:
    python kisisel_tahmin.py --cinsiyet erkek --yas 16.5 --boy 171 \\
        --onceki-yas 15.5 --onceki-boy 167 --anne 162 --baba 178

En değerli girdi: en az 12 ay önceki bir boy ölçümü (--onceki-yas/--onceki-boy).

UYARI: Tıbbi değerlendirme değildir. Sağlıklı büyüme varsayar. Hastalık,
sendrom, ilaç ya da gecikmiş ergenlik varsa tahmin geçersizdir.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from model import TURK_ERISKIN, Onsel, boy_par, hiz_par

PARAM = Path(__file__).parent / "ciktilar" / "A_pb1_parametreleri.csv"
OLCUM_HATASI = 0.5        # cm, tek stadiometre ölçümü (bkz. D_olcum_hatasi_analitik.csv)
KEMIK_YASI_HATASI = 0.6   # yıl; okuyucular arası ~0.4 + bireysel sapma (varsayım)
HEDEF_BOY_SD = 5.0        # cm; anne-baba verildiğinde erişkin boy belirsizliği (varsayım)
REGRESYON = 0.72          # anne-baba ortalamasından topluma dönüş (varsayım, bkz. Hermanussen & Cole)
KURAL_KATSAYI = {"erkek": 1.0, "kiz": 0.9}   # C_hiz_kurali.csv, "sona kadar" katsayısı


def agirlikli_yuzdelik(x, w, q):
    i = np.argsort(x)
    cw = np.cumsum(w[i])
    cw /= cw[-1]
    return np.interp(np.asarray(q) / 100.0, cw, x[i])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cinsiyet", choices=["erkek", "kiz"], required=True)
    ap.add_argument("--yas", type=float, required=True)
    ap.add_argument("--boy", type=float, required=True, help="cm, sabah ölçümü")
    ap.add_argument("--onceki-yas", type=float)
    ap.add_argument("--onceki-boy", type=float)
    ap.add_argument("--anne", type=float)
    ap.add_argument("--baba", type=float)
    ap.add_argument("--kemik-yasi", type=float)
    ap.add_argument("--referans", choices=["turk", "berkeley"], default="turk",
                    help="anne-baba verilmezse erişkin boy ortalaması")
    ap.add_argument("--n", type=int, default=300_000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    if not 13 <= a.yas <= 19:
        print("Uyarı: araç 13-19 yaş için doğrulandı, bu yaşta sonuçlar güvenilmez.")

    f = pd.read_csv(PARAM)
    f = f[(f.cinsiyet == a.cinsiyet) & f.onsele_dahil]
    onsel = Onsel.parametrelerden(f[["h1", "ht", "s0", "s1", "th"]].values)
    rng = np.random.default_rng(a.seed)

    if a.anne is not None and a.baba is not None:
        tanner = (a.anne + a.baba + 13) / 2 if a.cinsiyet == "erkek" else (a.anne + a.baba - 13) / 2
        mu = TURK_ERISKIN[a.cinsiyet]
        hedef = mu + REGRESYON * (tanner - mu)
        par = onsel.ornekle(a.n, rng, h1_ort=hedef, h1_sd=HEDEF_BOY_SD)
        print(f"Anne-baba hedef boyu (Tanner): {tanner:.1f} cm, düzeltilmiş: {hedef:.1f} cm")
    elif a.referans == "turk":
        par = onsel.ornekle(a.n, rng, h1_ort=TURK_ERISKIN[a.cinsiyet])
    else:
        par = onsel.ornekle(a.n, rng)

    s = OLCUM_HATASI
    logw = -0.5 * ((boy_par(par, a.yas) - a.boy) / s) ** 2
    kural = None
    if a.onceki_yas is not None and a.onceki_boy is not None:
        dt = a.yas - a.onceki_yas
        artis = a.boy - a.onceki_boy
        logw += -0.5 * (((boy_par(par, a.yas) - boy_par(par, a.onceki_yas)) - artis) / (np.sqrt(2) * s)) ** 2
        print(f"Gözlenen hız: {artis / dt:.2f} cm/yıl ({dt * 12:.0f} ay arayla)")
        if dt < 0.75:
            print(f"  Dikkat: {dt * 12:.0f} ay kısa. Ölçüm hatası hızı ±{s * np.sqrt(2) / dt:.1f} cm/yıl oynatabilir.")
        kural = KURAL_KATSAYI[a.cinsiyet] * artis / dt
    if a.kemik_yasi is not None:
        by = a.yas - (par["th"] - onsel.ort[4])
        logw += -0.5 * ((by - a.kemik_yasi) / KEMIK_YASI_HATASI) ** 2

    w = np.exp(logw - logw.max())
    ess = w.sum() ** 2 / (w ** 2).sum()
    son = boy_par(par, 25.0)
    kalan = son - boy_par(par, a.yas)
    k10, k50, k90 = agirlikli_yuzdelik(kalan, w, [10, 50, 90])
    s10, s50, s90 = agirlikli_yuzdelik(son, w, [10, 50, 90])
    v50 = agirlikli_yuzdelik(hiz_par(par, a.yas), w, [50])[0]
    wn = w / w.sum()

    print("-" * 64)
    print(f"Tahmini şu anki hız: {v50:.1f} cm/yıl")
    print(f"Kalan boy (model):   medyan {k50:.1f} cm   %80 aralık {k10:.1f} - {k90:.1f}")
    print(f"Erişkin boy (model): medyan {s50:.1f} cm   %80 aralık {s10:.1f} - {s90:.1f}")
    print(f"P(kalan > 2 cm) = {np.sum(wn * (kalan > 2)):.0%}   P(kalan > 5 cm) = {np.sum(wn * (kalan > 5)):.0%}")
    if kural is not None:
        print(f"Basit kural (kalan ≈ {KURAL_KATSAYI[a.cinsiyet]} x son 1 yıl): ~{kural:.1f} cm")
    print(f"Etkin örnek: {ess:.0f}" + ("  (DÜŞÜK: girdiler çok uç, sonuca güvenme)" if ess < 200 else ""))
    print("-" * 64)
    print("Not: model 18 sonrası büyümeyi ~yarı yarıya eksik tahmin ediyor (README 4.2),")
    print("erkeklerde gerçek kalan boy buradaki medyandan ~0.5 cm fazla olabilir.")
    print("Bu tahmin optimal koşulları varsayar. Yaşam tarzı tavanı yükseltmez.")


if __name__ == "__main__":
    main()
