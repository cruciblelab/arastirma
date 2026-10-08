"""
Gerçek deney için araç. İki komut:

    python analiz_et.py tasarim hedefler.csv R [K] [cikti.csv]
        Değerlendirici başına K (varsayılan 60) çiftlik, dengeli ve sol-sağ rastgele bir gösterim listesi üretir.

    python analiz_et.py analiz hedefler.csv yanitlar.csv
        Ön kayıtlı iki aşamalı analiz (PLAN 2.5): PSE₂, %95 aralık, kontrol (b > 0) ve karar (PLAN K1-K3).

Dosya biçimleri: ../sablonlar/*_sablon.csv. Kişisel veri içeren dosyalar repoya konmaz; .kisisel/ altında tutulmalıdır.
Önce `python calistir.py` çalıştırılmış olmalıdır (ciktilar/ansur_referans.json).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
import deney  # noqa: E402

TOHUM = 20261009


def sinif(cm):
    a = abs(cm)
    return "ihmal edilebilir (< 0.5 cm)" if a < 0.5 else "küçük (0.5-2 cm)" if a < 2 else "belirgin (≥ 2 cm)"


def main(argv):
    if len(argv) >= 3 and argv[0] == "tasarim":
        h = pd.read_csv(argv[1])
        R = int(argv[2])
        K = int(argv[3]) if len(argv) > 3 else 60
        out = Path(argv[4]) if len(argv) > 4 else Path("tasarim.csv")
        t = deney.ciftler_uret(h, R, K, np.random.default_rng(TOHUM))
        t.to_csv(out, index=False)
        print(f"{len(t)} satır yazıldı: {out}")
        return
    if len(argv) == 3 and argv[0] == "analiz":
        ref = json.loads((KOK / "ciktilar" / "ansur_referans.json").read_text(encoding="utf-8"))
        h, y = pd.read_csv(argv[1]), pd.read_csv(argv[2])
        s = deney.analiz(h, y, ref=ref, rng=np.random.default_rng(TOHUM))
        print(f"Hedef: {len(h)}, yanıt: {len(y)}, değerlendirici: {y.degerlendirici.nunique()}")
        print(f"Kontrol (gerçek boyun algıya etkisi b): {s['b']:.3f} ({s['b_lo']:.3f} … {s['b_hi']:.3f})")
        if s["b_lo"] <= 0:
            print("K1: kontrol başarısız; uyaranlar boy farkını göstermiyor. Sonuç yorumlanmaz.")
            return
        print(f"PSE₂ = {s['pse2']:+.2f} cm (%95: {s['pse2_lo']:+.2f} … {s['pse2_hi']:+.2f})")
        if s["pse2_lo"] > 0:
            k = "kalıplı vücut aynı boyda daha uzun algılanıyor"
        elif s["pse2_hi"] < 0:
            k = "kalıplı vücut aynı boyda daha kısa algılanıyor"
        else:
            k = "bu örneklemle fark gösterilemedi (yokluğu kanıtlamaz)"
        print(f"K2: {k}. K3: {sinif(s['pse2'])}.")
        return
    print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
