"""
Deneyin kendisi: çift üretimi ve ön kayıtlı iki aşamalı analiz (PLAN 2.4-2.5).

Bu modül gerçek deney verisinde de aynen kullanılır (analiz_et.py). Sentetik veri üreteci ayrı bir modüldedir
(uretec.py) ve buraya bağımlı değildir.

Veri biçimi
  hedefler: id, boy_cm, omuz_cm, kilo_kg            (bir satır = fotoğraflanan bir kişi)
  yanitlar: degerlendirici, sol, sag, secilen        (secilen = "daha uzun" diye seçilen hedefin id'si)
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import log_ndtr
from scipy.stats import norm


# ---------------------------------------------------------------------------
# Yapı indeksi (sürüm 1 ile aynı tanım; birim: ANSUR II popülasyon SD'si)
# ---------------------------------------------------------------------------

def yapi_indeksi(h, ref):
    """Omuz ve kilonun boya göre artıkları, ANSUR referans SD'leriyle ölçeklenir. ref: ansur_referans.json içeriği."""
    boy = h.boy_cm.to_numpy(float)

    def artik(y):
        b = np.polyfit(boy, y, 1)
        return y - np.polyval(b, boy)

    eo = artik(h.omuz_cm.to_numpy(float)) / ref["omuz_artik_sd_cm"]
    ek = artik(h.kilo_kg.to_numpy(float)) / ref["kilo_artik_sd_kg"]
    return (eo + ek) / 2 / ref["ortalama_sd"]


# ---------------------------------------------------------------------------
# Çift üretimi (PLAN 2.4): boy farkı ≤ max_fark; gösterilme dengesi için açgözlü seçim
# ---------------------------------------------------------------------------

def ciftler_uret(h, R, K, rng, max_fark=6.0, en_az=None):
    ids = h.id.to_numpy()
    boy = dict(zip(ids, h.boy_cm.to_numpy(float)))
    tum = [(a, b, abs(boy[a] - boy[b])) for i, a in enumerate(ids) for b in ids[i + 1:]]
    uygun = [(a, b) for a, b, f in tum if f <= max_fark]
    en_az = en_az or K
    if len(uygun) < en_az:                                     # yetmezse en yakın farklar
        uygun = [(a, b) for a, b, _ in sorted(tum, key=lambda x: x[2])[:max(en_az, len(uygun))]]
    konum = {k: i for i, k in enumerate(ids)}
    pa = np.array([konum[a] for a, _ in uygun])
    pb = np.array([konum[b] for _, b in uygun])
    sayac = np.zeros(len(ids))
    kk = min(K, len(uygun))
    sol, sag = np.empty(R * kk, int), np.empty(R * kk, int)
    j = 0
    for r in range(R):
        gosterildi = np.zeros(len(uygun), bool)
        for _ in range(kk):
            puan = sayac[pa] + sayac[pb] + rng.random(len(uygun)) * 0.5   # en az gösterilen hedefler öne
            puan[gosterildi] = np.inf
            i = int(np.argmin(puan))
            gosterildi[i] = True
            sayac[pa[i]] += 1
            sayac[pb[i]] += 1
            sol[j], sag[j] = (pa[i], pb[i]) if rng.random() < 0.5 else (pb[i], pa[i])
            j += 1
    return pd.DataFrame(dict(degerlendirici=np.repeat(np.arange(R), kk), sira=np.tile(np.arange(kk), R),
                             sol=ids[sol], sag=ids[sag]))


# ---------------------------------------------------------------------------
# Aşama 1: Thurstone probit ölçeği; Aşama 2: hedef düzeyinde regresyon
# ---------------------------------------------------------------------------

def olcek(y, ia, ib, n, ridge=1e-3):
    """P(A seçilir) = Φ(s_A − s_B). y: 1 = sol (A) seçildi. Küçük ridge yalnız tam ayrışmaya karşı. Ortalama 0."""
    def f(s):
        d = s[ia] - s[ib]
        sgn = 2 * y - 1
        z = sgn * d
        ll = log_ndtr(z)
        g_d = sgn * np.exp(norm.logpdf(z) - ll)
        g = np.bincount(ia, g_d, n) - np.bincount(ib, g_d, n)
        return -ll.sum() + ridge * s @ s, -g + 2 * ridge * s
    s = minimize(f, np.zeros(n), jac=True, method="L-BFGS-B").x
    return s - s.mean()


def asama2(s, boy, z):
    X = np.column_stack([np.ones_like(boy), boy, z])
    coef = np.linalg.lstsq(X, s, rcond=None)[0]
    return coef[1], coef[2]


def analiz(h, y_df, ref=None, z=None, B=2000, rng=None):
    """Ön kayıtlı analiz. Döner: PSE₂ (cm), %95 aralık, b ve aralığı, aşama-1 ölçeği."""
    rng = rng or np.random.default_rng(0)
    z = yapi_indeksi(h, ref) if z is None else np.asarray(z, float)
    idx = {k: i for i, k in enumerate(h.id.to_numpy())}
    ia = y_df.sol.map(idx).to_numpy()
    ib = y_df.sag.map(idx).to_numpy()
    y = (y_df.secilen.to_numpy() == y_df.sol.to_numpy()).astype(float)
    s = olcek(y, ia, ib, len(h))
    boy = h.boy_cm.to_numpy(float)
    b, c = asama2(s, boy, z)
    n = len(h)
    sec = rng.integers(0, n, (B, n))                              # hedefler üzerinden bootstrap
    X = np.stack([np.ones((B, n)), boy[sec], z[sec]], axis=2)
    XtX = np.einsum("bni,bnj->bij", X, X)
    Xty = np.einsum("bni,bn->bi", X, s[sec])
    ok = np.linalg.matrix_rank(XtX) == 3
    coef = np.linalg.solve(XtX[ok], Xty[ok][..., None])[..., 0]
    pse_b = 2 * coef[:, 2] / coef[:, 1]
    return dict(pse2=2 * c / b, pse2_lo=float(np.percentile(pse_b, 2.5)), pse2_hi=float(np.percentile(pse_b, 97.5)),
                b=b, b_lo=float(np.percentile(coef[:, 1], 2.5)), b_hi=float(np.percentile(coef[:, 1], 97.5)),
                s=s, z=z)


def naif_analiz(h, y_df, z):
    """D5 gösterimi: yanıtları bağımsız sayan, yanıt düzeyinde probit (ΔH, Δz) ve delta yöntemiyle Wald aralığı."""
    idx = {k: i for i, k in enumerate(h.id.to_numpy())}
    ia, ib = y_df.sol.map(idx).to_numpy(), y_df.sag.map(idx).to_numpy()
    y = (y_df.secilen.to_numpy() == y_df.sol.to_numpy()).astype(float)
    boy = h.boy_cm.to_numpy(float)
    X = np.column_stack([boy[ia] - boy[ib], z[ia] - z[ib]])

    def f(w):
        sgn = 2 * y - 1
        q = sgn * (X @ w)
        ll = log_ndtr(q)
        g = (sgn * np.exp(norm.logpdf(q) - ll))[:, None] * X
        return -ll.sum(), -g.sum(0)
    w = minimize(f, np.array([0.3, 0.0]), jac=True, method="L-BFGS-B").x
    q = X @ w
    lam = np.exp(norm.logpdf(q) - log_ndtr(q))
    lam2 = np.exp(norm.logpdf(q) - log_ndtr(-q))
    wgt = lam * lam2                                              # beklenen bilgi (probit)
    V = np.linalg.inv((X * wgt[:, None]).T @ X)
    pse = 2 * w[1] / w[0]
    gr = np.array([-2 * w[1] / w[0] ** 2, 2 / w[0]])
    se = float(np.sqrt(gr @ V @ gr))
    return dict(pse2=pse, pse2_lo=pse - 1.96 * se, pse2_hi=pse + 1.96 * se)
