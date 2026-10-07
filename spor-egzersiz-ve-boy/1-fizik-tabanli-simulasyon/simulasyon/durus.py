"""
Katman C: duruş geometrisi.

Göğüs omurgası, merkez açısı θ (kifoz açısı) olan bir çember yayı. Yay boyu L_T sabit
(kemik boyu değişmiyor); dikey yüksekliği:

    h(θ) = L_T · sinc(θ/2),   sinc(x) = sin(x)/x

Kifoz azalınca yay düzleşir ve dikey yükseklik artar. Ölçülen boydaki değişim:

    ΔH = L_T · [sinc(θ_son/2) − sinc(θ_ilk/2)]
"""

import numpy as np

L_T_ORAN = 0.16          # varsayım: göğüs omurgası yay boyu / boy
KIFOZ_ERKEK_16 = (36.5, 7.85)   # derece, ölçülmüş (esnek cetvel)
DUZELME = {"sadece sırt egzersizi (−%13)": 0.13, "kapsamlı program (−%26)": 0.26}   # RCT, ölçülmüş


def sinc(x):
    x = np.asarray(x, float)
    return np.where(np.abs(x) < 1e-12, 1.0, np.sin(x) / np.where(x == 0, 1, x))


def dikey(L, teta_derece):
    return L * sinc(np.radians(teta_derece) / 2)


def kazanc(boy_cm, teta_ilk, oran, L_oran=L_T_ORAN):
    L = L_oran * np.asarray(boy_cm, float)
    teta_son = np.asarray(teta_ilk) * (1 - oran)
    return dikey(L, teta_son) - dikey(L, teta_ilk)
