"""
Kişisel kalan boy tahmini (Bayesçi, Monte Carlo).

Popülasyondan 400 bin "sanal genç" üretir, her birinin büyüme eğrisi farklı
(erişkin boy, olgunlaşma zamanı, eğri şekli). Sonra elindeki ölçümlere en çok
uyanları ağırlıklandırır:

  - şimdiki boy (zorunlu)
  - anne-baba boyu (isteğe bağlı) -> erişkin boy önsel dağılımını daraltır
  - kemik yaşı (isteğe bağlı, el-bilek röntgeni) -> olgunlaşma zamanını daraltır
  - önceki bir boy ölçümü (isteğe bağlı) -> büyüme hızı, EN GÜÇLÜ bilgi

Örnek:
    python kisisel_tahmin.py --cinsiyet erkek --yas 16.5 --boy 171 \\
        --anne 162 --baba 178 --onceki-yas 15.9 --onceki-boy 168.2

UYARI: Bu bir tıbbi değerlendirme değildir. Model sağlıklı büyüme varsayar;
altta yatan hastalık (çölyak, hipotiroidi, GH eksikliği, Turner vb.) varsa
tahmin geçersizdir. Kemik yaşı ve büyüme hızı ölçümü için çocuk endokrinoloğu.
"""

import argparse

import numpy as np

from model import POP, pb_boy, pb_hiz, populasyon_ornekle

SON_YAS = 25.0
OLCUM_HATASI = 0.5      # cm, stadiometre ile tek ölçüm (sabah, aynı cihaz) varsayımı
KEMIK_YASI_HATASI = 0.6  # yıl, Greulich-Pyle okuma belirsizliği + bireysel sapma
HEDEF_BOY_SD = 5.0       # cm, düzeltilmiş hedef boy etrafında belirsizlik
REGRESYON = 0.72         # anne-baba ortalamasından topluma dönüş (ortalamaya regresyon)


def hedef_boy(cinsiyet, anne, baba):
    """Tanner hedef boyu + ortalamaya regresyon düzeltmesi."""
    tanner = (anne + baba + 13) / 2 if cinsiyet == "erkek" else (anne + baba - 13) / 2
    mu = POP[cinsiyet]["h1_ort"]
    return tanner, mu + REGRESYON * (tanner - mu)


def agirlikli_yuzdelik(x, w, q):
    i = np.argsort(x)
    cw = np.cumsum(w[i])
    cw /= cw[-1]
    return np.interp(np.asarray(q) / 100.0, cw, x[i])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cinsiyet", choices=["erkek", "kiz"], required=True)
    ap.add_argument("--yas", type=float, required=True)
    ap.add_argument("--boy", type=float, required=True, help="cm, sabah ölçümü tercih")
    ap.add_argument("--anne", type=float)
    ap.add_argument("--baba", type=float)
    ap.add_argument("--kemik-yasi", type=float)
    ap.add_argument("--onceki-yas", type=float)
    ap.add_argument("--onceki-boy", type=float)
    ap.add_argument("--n", type=int, default=400_000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    p = POP[a.cinsiyet]

    if a.anne is not None and a.baba is not None:
        tanner, th = hedef_boy(a.cinsiyet, a.anne, a.baba)
        par = populasyon_ornekle(a.cinsiyet, a.n, rng, h1_ort=th, h1_sd=HEDEF_BOY_SD)
        print(f"Tanner hedef boy: {tanner:.1f} cm (klasik ±8.5 cm aralık: {tanner - 8.5:.0f}-{tanner + 8.5:.0f})")
        print(f"Regresyon düzeltmeli hedef: {th:.1f} cm (bunu kullanıyoruz)")
    else:
        par = populasyon_ornekle(a.cinsiyet, a.n, rng)

    s = OLCUM_HATASI
    logw = -0.5 * ((pb_boy(par, a.yas) - a.boy) / s) ** 2

    if a.kemik_yasi is not None:
        # Biyolojik yaş ~ takvim yaşı - (bireyin θ'sı - popülasyon θ'sı)
        by = a.yas - (par["theta"] - p["theta_ort"])
        logw += -0.5 * ((by - a.kemik_yasi) / KEMIK_YASI_HATASI) ** 2

    if a.onceki_yas is not None and a.onceki_boy is not None:
        artis_model = pb_boy(par, a.yas) - pb_boy(par, a.onceki_yas)
        artis_gozlem = a.boy - a.onceki_boy
        logw += -0.5 * ((artis_model - artis_gozlem) / (np.sqrt(2) * s)) ** 2
        aralik = a.yas - a.onceki_yas
        print(f"Gözlenen hız: {artis_gozlem / aralik:.2f} cm/yıl ({aralik * 12:.0f} ay)")
        if aralik < 0.5:
            print("  Not: 6 aydan kısa aralıkta ölçüm hatası hızı ciddi bozar.")

    w = np.exp(logw - logw.max())
    ess = w.sum() ** 2 / (w ** 2).sum()

    son = pb_boy(par, SON_YAS)
    kalan = son - pb_boy(par, a.yas)
    hiz = pb_hiz(par, a.yas)
    q = agirlikli_yuzdelik(kalan, w, [10, 50, 90])
    qs = agirlikli_yuzdelik(son, w, [10, 50, 90])
    qh = agirlikli_yuzdelik(hiz, w, [50])
    wn = w / w.sum()

    print("-" * 60)
    print(f"Tahmini şu anki büyüme hızı (medyan): {qh[0]:.2f} cm/yıl")
    print(f"Kalan boy:  medyan {q[1]:.1f} cm   (%80 aralık {q[0]:.1f} - {q[2]:.1f})")
    print(f"Erişkin boy: medyan {qs[1]:.1f} cm (%80 aralık {qs[0]:.1f} - {qs[2]:.1f})")
    print(f"P(kalan > 2 cm) = {np.sum(wn * (kalan > 2)):.0%}   P(kalan > 5 cm) = {np.sum(wn * (kalan > 5)):.0%}")
    print(f"Etkin örnek sayısı: {ess:.0f}" + ("  (DÜŞÜK - girdiler popülasyona göre çok uç, sonuca güvenme)"
                                             if ess < 200 else ""))
    print("-" * 60)
    print("Bu, optimal koşullarda genetik rotanın tahminidir. Yaşam tarzı bunu")
    print("AŞMAZ; eksiklik varsa bu rotanın altında kalınır.")


if __name__ == "__main__":
    main()
