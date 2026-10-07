"""
Katman B: omurga disklerinin viskoelastik sünmesi (geçici boy değişimi).

    dy/dt = (y_denge(P) − y) / τ,   τ = τ_c (sıkışırken) ya da τ_r (açılırken)
    y_denge(P) = −k · (P − 0.10)    P: bel diski basıncı (MPa, Wilke 1999)

y: sabah referansına göre omurga boyu değişimi (mm). Tamamen geri dönüşlü:
kalıcı bir durum değişkeni yok. Boy yalnızca o anki ve yakın geçmişteki yüke bağlı.
"""

import numpy as np
from scipy.optimize import brentq

P_UZANMA = 0.10
# Wilke 1999 (ölçülmüş) + asılma/traksiyon (varsayım)
BASINC = dict(uyku=0.10, oturma=0.46, ayakta=0.50, yuruyus=0.59, kosu=0.65,
              asilma=0.05, traksiyon=0.03, ters_asilma=0.0)

# Uygulama ayrıntısı 4: kalibrasyon günü (saat aralığı, basınç)
NORMAL_GUN = [(0, 1, 0.50), (1, 8, 0.46), (8, 16, 0.59), (16, 24, 0.10)]
GUNLUK_HEDEF_MM = 14.4


def entegre(y0, dilimler, k, tau_c, tau_r, dt_saat=1 / 60):
    """dilimler: [(süre_saat, P)]. Analitik üstel çözüm (her adımda sabit P). Zaman ve y dizileri döndürür."""
    t, y = [0.0], [y0]
    for sure, P in dilimler:
        adim = max(1, int(round(sure / dt_saat)))
        h = sure / adim
        ye = -k * (P - P_UZANMA)
        for _ in range(adim):
            tau = tau_c if ye < y[-1] else tau_r
            y.append(ye + (y[-1] - ye) * np.exp(-h / tau))
            t.append(t[-1] + h)
    return np.array(t), np.array(y)


def gun_dilimleri(gun=NORMAL_GUN):
    return [(b - a, P) for a, b, P in gun]


def periyodik_sabah(k, tau_c, tau_r, gun_sayisi=10):
    """10 günlük ısınma sonrası sabah değeri ve günlük genlik."""
    y = 0.0
    for _ in range(gun_sayisi):
        t, yy = entegre(y, gun_dilimleri(), k, tau_c, tau_r)
        y = yy[-1]
    t, yy = entegre(y, gun_dilimleri(), k, tau_c, tau_r)
    aksam = yy[np.searchsorted(t, 16.0 - 1e-9)]
    return y, y - aksam


def kalibre_k(tau_c, tau_r):
    """Günlük sabah-akşam farkı 14.4 mm olacak k (mm/MPa)."""
    return brentq(lambda k: periyodik_sabah(k, tau_c, tau_r)[1] - GUNLUK_HEDEF_MM, 1, 500)
