"""
Ölçüm fiziği (PLAN bölüm 3.4).

    ölçülen = gerçek − D_max·(1 − exp(−τ/τ_c)) + e_okuma + b_gözlemci, 0.1 cm'ye yuvarlanır

D_max: gün içi omurga disk sıkışmasının üst sınırı (ölçülmüş: ort. 14.4 mm).
τ:     uyanıştan beri geçen saat. Sabah protokolünde 0-2, rastgele protokolde 1-13.
τ_c, e_okuma, b_gözlemci: varsayım (duyarlılık analizi calistir.py'de).
"""

import numpy as np

VARSAYILAN = dict(D_max=1.44, tau_c=1.5, e_okuma=0.3, b_gozlemci=0.3)

PROTOKOLLER = {
    "P1": dict(ad="Sabah, aynı gözlemci, 3 okuma ortalaması", sabah=True, okuma=3, farkli_gozlemci=False),
    "P2": dict(ad="Rastgele saat, aynı gözlemci, tek okuma", sabah=False, okuma=1, farkli_gozlemci=False),
    "P3": dict(ad="Rastgele saat, farklı gözlemciler, tek okuma", sabah=False, okuma=1, farkli_gozlemci=True),
}


def olc(gercek, rng, protokol, ayar=None):
    """gercek: herhangi bir şekilde gerçek boy dizisi. Her eleman ayrı bir ölçüm ziyaretidir."""
    a = {**VARSAYILAN, **(ayar or {})}
    p = PROTOKOLLER[protokol]
    gercek = np.asarray(gercek, float)
    tau = rng.uniform(0, 2, gercek.shape) if p["sabah"] else rng.uniform(1, 13, gercek.shape)
    sikisma = a["D_max"] * (1 - np.exp(-tau / a["tau_c"]))
    hata = rng.normal(0, a["e_okuma"] / np.sqrt(p["okuma"]), gercek.shape)
    sapma = rng.normal(0, a["b_gozlemci"], gercek.shape) if p["farkli_gozlemci"] else 0.0
    return np.round((gercek - sikisma + hata + sapma) * 10) / 10
