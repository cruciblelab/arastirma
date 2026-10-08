"""
Ortak hesaplar (PLAN 3.1-3.2): sürüm 3 modelinden gövde/bacak eğrileri, Stokes 2008 eğrilik kaybı,
ölçüm protokolü güç simülasyonu.
"""

import sys
from pathlib import Path

import numpy as np
from scipy import stats

REPO = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO / "spor-egzersiz-ve-boy" / "1-fizik-tabanli-simulasyon" / "simulasyon"))
sys.path.append(str(REPO / "boy-uzamasi-16-18-yas" / "3-mekanistik-simulasyon-ve-on-kayit" / "simulasyon"))

import plak                    # noqa: E402
from model import simule_et    # noqa: E402

TOHUM = 20261008
GUNICI_MM = 14.4               # spor araştırması sürüm 1 (gün içi boy farkı)
DURUS_MM = (2.0, 4.0)          # spor araştırması sürüm 1, bölüm 4.4
MEKANIK_UST_MM = 0.5           # spor araştırması sürüm 1 (egzersizin üst sınırı)


def stokes_kayip_mm(cobb):
    """Stokes 2008: skolyozda boy kaybı (mm) = 1.0 + 0.066·Cobb + 0.0084·Cobb²."""
    cobb = np.asarray(cobb, float)
    return 1.0 + 0.066 * cobb + 0.0084 * cobb ** 2


def kohort_egrileri(cinsiyet, n, yaslar, tohum=TOHUM):
    pop, ind, L0b, L0g = plak.kohort(cinsiyet, n, np.random.default_rng(tohum))
    s = simule_et(ind, pop, L0b, L0g, t1=float(max(yaslar)), kayit_yaslari=list(yaslar))
    return s["bacak"], s["govde"]


def tipik_kisi(cinsiyet, yaslar, n=5000, tohum=TOHUM):
    """Bireysel parametrelerin medyanıyla 'tipik' kişi. Döndürür: (ind, pop, L0b, L0g, bacak, govde)."""
    pop, ind, L0b, L0g = plak.kohort(cinsiyet, n, np.random.default_rng(tohum))
    ind1 = {k: np.array([np.median(v)]) for k, v in ind.items()}
    b0, g0 = np.array([np.median(L0b)]), np.array([np.median(L0g)])
    s = simule_et(ind1, pop, b0, g0, t1=float(max(yaslar)), kayit_yaslari=list(yaslar))
    return ind1, pop, b0, g0, s["bacak"][:, 0], s["govde"][:, 0]


def protokol_gucu(v, aralik_ay, sure_ay, k, sigma_o, sigma_s, iki_olcum=False, n_mc=20_000, tohum=TOHUM, alfa=0.05):
    """Seans ortalamalarına doğru oturtup tek yönlü eğim testi. iki_olcum: bacak = boy − oturma boyu (iki hata)."""
    t = np.arange(0, sure_ay + 1e-9, aralik_ay) / 12.0
    n = t.size
    if n < 3:
        return dict(n_seans=n, guc=np.nan, ci90_genislik=np.nan)
    var = sigma_s ** 2 + sigma_o ** 2 / k
    if iki_olcum:
        var *= 2
    rng = np.random.default_rng(tohum)
    y = v * t[None, :] + rng.normal(0, np.sqrt(var), (n_mc, n))
    tc = t - t.mean()
    sxx = (tc ** 2).sum()
    b = (y - y.mean(1, keepdims=True)) @ tc / sxx
    res = y - y.mean(1, keepdims=True) - b[:, None] * tc[None, :]
    se = np.sqrt((res ** 2).sum(1) / (n - 2) / sxx)
    tkrit = stats.t.ppf(1 - alfa, n - 2)
    t90 = stats.t.ppf(0.95, n - 2)
    return dict(n_seans=n, guc=float(np.mean(b / se > tkrit)), ci90_genislik=float(np.median(2 * t90 * se)))
