"""
v2 model katmanı.

1) Preece-Baines Model 1 (PB1), artık her bireye GERÇEK veriden fit ediliyor
   (v1'de parametreler elle ayarlanmıştı).

       h(t) = h1 - 2 (h1 - hθ) / (exp(s0 (t-θ)) + exp(s1 (t-θ)))

2) Ampirik önsel: Berkeley bireylerine fit edilen parametrelerin ortak dağılımı
   (çok değişkenli normal, korelasyonlar dahil). Kişisel tahmin bunu kullanır.

3) Dinamik katman (v1'den aynen, KANIT SEVİYESİ D = model/varsayım):
       dτ/dt = r        biyolojik saat (kemik yaşı) hızı
       dh/dt = r·m·v_PB(τ) + k·max(D,0)·g(τ)
   r: olgunlaşma hızı, m: biyolojik saat başına büyüme verimi,
   D: kişinin kendi rotasına göre açığı, g: plak açıklığı (yakalama kapasitesi).
   Takvim yaşına göre büyüme hızı oranı q = r·m.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import curve_fit

# Türkiye referans erişkin boyu (18 yaş ortalaması; Neyzi ve ark. çalışmaları,
# 2009 İstanbul verisi: erkek ~177, kız ~163). Kişisel tahminde Berkeley
# önselinin ortalaması buraya kaydırılır, kovaryans korunur.
TURK_ERISKIN = {"erkek": 177.0, "kiz": 163.0}


def pb_boy(t, h1, ht, s0, s1, th):
    u = np.asarray(t, dtype=float) - th
    return h1 - 2.0 * (h1 - ht) / (np.exp(s0 * u) + np.exp(s1 * u))


def pb_hiz(t, h1, ht, s0, s1, th):
    u = np.asarray(t, dtype=float) - th
    e0, e1 = np.exp(s0 * u), np.exp(s1 * u)
    return 2.0 * (h1 - ht) * (s0 * e0 + s1 * e1) / (e0 + e1) ** 2


def pb_fit(yas, boy, cinsiyet):
    """Tek bireye PB1 fit. 3 yaş öncesi kullanılmaz (PB1 bebeklikte geçersiz)."""
    yas, boy = np.asarray(yas), np.asarray(boy)
    m = yas >= 3
    yas, boy = yas[m], boy[m]
    p0 = [boy.max() + 1, boy.max() - 12, 0.1, 1.2, 14.0 if cinsiyet == "erkek" else 12.0]
    p, _ = curve_fit(pb_boy, yas, boy, p0=p0, maxfev=20000,
                     bounds=([100, 80, 0.01, 0.3, 8], [220, 210, 0.5, 5, 20]))
    rmse = float(np.sqrt(np.mean((boy - pb_boy(yas, *p)) ** 2)))
    return p, rmse


def phv(p, t0=8.0, t1=20.0):
    t = np.linspace(t0, t1, 2401)
    v = pb_hiz(t, *p)
    i = int(np.argmax(v))
    return float(t[i]), float(v[i])


# ---------------------------------------------------------------------------
# Ampirik önsel: dönüştürülmüş uzayda çok değişkenli normal
#   x = (h1, delta = h1 - ht, log s0, log s1, θ)
# ---------------------------------------------------------------------------

def _donustur(P):
    P = np.atleast_2d(P)
    return np.column_stack([P[:, 0], P[:, 0] - P[:, 1], np.log(P[:, 2]), np.log(P[:, 3]), P[:, 4]])


def _geri(X):
    h1 = X[:, 0]
    return dict(h1=h1, ht=h1 - np.clip(X[:, 1], 3, None), s0=np.exp(X[:, 2]),
                s1=np.exp(X[:, 3]), th=X[:, 4])


@dataclass
class Onsel:
    ort: np.ndarray
    kov: np.ndarray

    @classmethod
    def parametrelerden(cls, P):
        X = _donustur(P)
        return cls(X.mean(axis=0), np.cov(X, rowvar=False))

    def ornekle(self, n, rng, h1_ort=None, h1_sd=None):
        ort, kov = self.ort.copy(), self.kov.copy()
        if h1_ort is not None:
            ort[0] = h1_ort
        if h1_sd is not None:
            # h1'in varyansını değiştir, diğerleriyle korelasyonu koru
            olcek = h1_sd / np.sqrt(kov[0, 0])
            kov[0, :] *= olcek
            kov[:, 0] *= olcek
        X = rng.multivariate_normal(ort, kov, n)
        return _geri(X)


def boy_par(par, t):
    return pb_boy(t, par["h1"], par["ht"], par["s0"], par["s1"], par["th"])


def hiz_par(par, t):
    return pb_hiz(t, par["h1"], par["ht"], par["s0"], par["s1"], par["th"])


# ---------------------------------------------------------------------------
# Dinamik katman
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Donem:
    bas: float
    bit: float
    m: float = 1.0
    r: float | None = None


@dataclass(frozen=True)
class DinamikAyar:
    alfa: float = 0.5
    k: float = 1.0
    v_ref: float = 3.0
    dt: float = 0.01


def simule_et(p, donemler, bas_yas, bit_yas=25.0, ayar=DinamikAyar()):
    """p: PB1 parametreleri (h1, ht, s0, s1, th). Son boyu döndürür."""
    n = int(round((bit_yas - bas_yas) / ayar.dt))
    h = float(pb_boy(bas_yas, *p))
    tau = bas_yas
    for i in range(n):
        t = bas_yas + i * ayar.dt
        m, r = 1.0, 1.0
        for d in donemler:
            if d.bas <= t < d.bit:
                m = d.m
                r = d.r if d.r is not None else 1.0 - ayar.alfa * (1.0 - d.m)
        v = float(pb_hiz(tau, *p))
        acik = max(float(pb_boy(tau, *p)) - h, 0.0)
        yakalama = ayar.k * acik * min(1.0, v / ayar.v_ref) if m >= 1.0 else 0.0
        h += ayar.dt * (r * m * v + yakalama)
        tau += ayar.dt * r
    return h
