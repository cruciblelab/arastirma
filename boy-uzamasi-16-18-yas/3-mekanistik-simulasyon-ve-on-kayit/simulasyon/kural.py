"""
Düzeltilmiş "geçen yıl kuralı" hesaplayıcısı (sürüm 3).

Sürüm 2'den farkı: kural yalnızca büyüme hızı YAVAŞLIYORSA uygulanır. Bunun için
yaklaşık birer yıl arayla 3 ölçüm gerekir. Hâlâ hızlanıyorsa kural kalan boyu ciddi
biçimde az tahmin eder (Berkeley: 13.6 cm'ye kadar; sanal kohort: medyan +2.3 cm).

Örnek:
    python kural.py --cinsiyet erkek --olcumler 15.0:168.0 16.0:171.5 17.0:173.0

Her ölçüm yaş:boy biçiminde (cm, sabah ölçümü).
Tıbbi değerlendirme değildir. Sağlıklı büyüme varsayar.
"""

import argparse

KATSAYI = {"erkek": 1.0, "kiz": 0.9}   # v2, Berkeley; v3 sanal kohortta yavaşlayanlarda 0.96 / 0.86
SAPMA = {"erkek": (-1.2, 0.8), "kiz": (-0.35, 0.55)}   # v2, 17 yaş artık %10-%90 (cm)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cinsiyet", choices=["erkek", "kiz"], required=True)
    ap.add_argument("--olcumler", nargs=3, required=True, metavar="YAS:BOY",
                    help="eskiden yeniye 3 ölçüm, aralarında ~12 ay")
    a = ap.parse_args()
    o = sorted(tuple(map(float, x.split(":"))) for x in a.olcumler)
    (y0, h0), (y1, h1), (y2, h2) = o
    d1, d2 = y1 - y0, y2 - y1
    if min(d1, d2) < 0.75:
        print(f"UYARI: ölçüm aralığı {min(d1, d2) * 12:.0f} ay. 9 aydan kısa aralıkta ölçüm hatası "
              "hızı ciddi bozar (sürüm 2, bölüm 4.4). Sonucu güvenilir sayma.")
    v_once = (h1 - h0) / d1
    v_son = (h2 - h1) / d2
    print(f"Önceki yıl: {v_once:.1f} cm/yıl   Son yıl: {v_son:.1f} cm/yıl")
    if v_son < 0:
        print("Son yıl negatif: büyüme yok ya da ölçüm hatası. Sabah, aynı aletle tekrar ölç.")
        return
    if v_son > v_once + 0.3:
        print("\nHIZ ARTIYOR: büyüme atağı bitmemiş olabilir. Kural bu durumda GEÇERSİZ;")
        print("önündeki boy, kuralın söylediğinden belirgin fazla olabilir.")
        print("Ergenlik geç kaldıysa bu önemli bir fırsat penceresi: çocuk endokrinoloğuna (18 yaştan önce).")
        return
    if abs(v_son - v_once) <= 0.3:
        print("Not: iki yıl neredeyse aynı. Ölçüm hatası sınırında; sonucu ihtiyatlı oku.")
    k = KATSAYI[a.cinsiyet]
    tahmin = k * v_son
    alt, ust = SAPMA[a.cinsiyet]
    print(f"\nKural: kalan boy ≈ {k} × {v_son:.1f} = ~{tahmin:.1f} cm "
          f"(tipik aralık {max(0, tahmin + alt):.1f} - {tahmin + ust:.1f} cm)")
    print("Bu tahmin optimal koşulları varsayar. Yaşam tarzı tavanı yükseltmez, sadece kaybı önler.")


if __name__ == "__main__":
    main()
