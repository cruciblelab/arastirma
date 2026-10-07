"""
Katman A: plak mekaniği (Hueter-Volkmann) + sürüm 3 büyüme plağı modeli.

Sürüm 3'ün denklemleri burada bölme bazında egzersiz çarpanı (M_bacak, M_govde)
alacak şekilde yeniden yazıldı. Parametreler sürüm 3'ün yayınlanmış çıktılarından
okunur (yeniden kalibrasyon yok). Çarpanlar 1 iken sürüm 3 modeliyle aynı sonucu
vermesi T7 testinde kontrol edilir.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

V3 = (Path(__file__).resolve().parents[3] / "boy-uzamasi-16-18-yas"
      / "3-mekanistik-simulasyon-ve-on-kayit" / "simulasyon")
T0, DT, KAPI = 9.0, 0.02, 0.15


def v3_parametreleri():
    pop_df = pd.read_csv(V3 / "ciktilar" / "A_populasyon_parametreleri.csv")
    bir = pd.read_csv(V3 / "ciktilar" / "A_bireysel_parametreler.csv")
    uy = json.loads((V3 / "ciktilar" / "ozet.json").read_text(encoding="utf-8"))["D_uyarlama"]
    pop = {c: dict(zip(g.parametre, g.deger)) for c, g in pop_df.groupby("cinsiyet")}
    return pop, bir, uy


def kohort(cinsiyet, n, rng):
    """Sürüm 3'teki gibi: bireysel parametrelerin çok değişkenli normali + Türk uyarlaması."""
    pop, bir, uy = v3_parametreleri()
    b = bir[bir.cinsiyet == cinsiyet]
    X = np.column_stack([np.log(b.Gb), np.log(b.Gg), b.Tp, np.log(b.Ap + 0.5),
                         np.log(b.L0_bacak), np.log(b.L0_govde)])
    Z = rng.multivariate_normal(X.mean(0), np.cov(X, rowvar=False), n)
    o, dTp = uy[cinsiyet]["olcek"], uy[cinsiyet]["dTp"]
    ind = dict(Gb=np.exp(Z[:, 0]) * o, Gg=np.exp(Z[:, 1]) * o, Tp=Z[:, 2] + dTp,
               Ap=np.clip(np.exp(Z[:, 3]) - 0.5, 0, None))
    return pop[cinsiyet], ind, np.exp(Z[:, 4]) * o, np.exp(Z[:, 5]) * o


def simule_et(ind, pop, L0b, L0g, program=None, t1=30.0, dt=DT, kayit=(30.0,), kontrol=False):
    """RK2. program: (t_bas, t_bit, M_bacak, M_govde) ya da None. Döndürür: dict(bacak, govde, boy) (len(kayit), n)."""
    Gb, Gg, Tp, Ap = (np.asarray(ind[k], float) for k in ("Gb", "Gg", "Tp", "Ap"))
    n = Gb.size
    adim = int(round((t1 - T0) / dt))
    hedef = {int(round((a - T0) / dt)): j for j, a in enumerate(kayit)}
    Lb, Lg = np.array(L0b, float), np.array(L0g, float)
    lSb, lSg = np.zeros(n), np.zeros(n)
    outb, outg = np.empty((len(kayit), n)), np.empty((len(kayit), n))
    sw = KAPI * pop["Sf"]

    def carpan(t):
        if program is None:
            return 1.0, 1.0
        a, b, mb, mg = program
        return (mb, mg) if a <= t < b else (1.0, 1.0)

    def hiz(t, lSb, lSg):
        E = expit((t - Tp) / pop["wE"])
        I = 1.0 + Ap * E
        Sb, Sg = np.exp(lSb), np.exp(lSg)
        mb, mg = carpan(t)
        vb = mb * Gb * I * Sb ** pop["gam"] * expit((Sb - pop["Sf"]) / sw)
        vg = mg * Gg * I ** pop["ag"] * Sg ** pop["gam"] * expit((Sg - pop["Sf"]) / sw)
        return vb, vg, -(pop["kb"] * vb / Gb + pop["eb"] * E), -(pop["kg"] * vg / Gg + pop["eg"] * E)

    for i in range(adim + 1):
        if i in hedef:
            outb[hedef[i]], outg[hedef[i]] = Lb, Lg
        if i == adim:
            break
        t = T0 + i * dt
        k1 = hiz(t, lSb, lSg)
        k2 = hiz(t + dt / 2, lSb + dt / 2 * k1[2], lSg + dt / 2 * k1[3])
        if kontrol:
            assert np.all(k2[0] >= 0) and np.all(k2[1] >= 0), "S3: negatif büyüme hızı"
        Lb, Lg = Lb + dt * k2[0], Lg + dt * k2[1]
        lSb, lSg = lSb + dt * k2[2], lSg + dt * k2[3]
    return dict(bacak=outb, govde=outg, boy=outb + outg)


# ---------------------------------------------------------------------------
# Göreli yükler ve programlar (PLAN 3.1)
# ---------------------------------------------------------------------------

# aktivite: (gövde L, bacak L)
YUK = {
    "uyku": (0.20, 0.0), "oturma": (0.92, 0.1), "ayakta": (1.15, 1.3),
    "kosu": (1.3, 3.0), "basketbol": (1.5, 3.5), "agirlik_set": (3.0, 3.0),
    "barfiks": (0.5, -0.15), "asilma": (-0.3, -0.15), "ters_asilma": (-0.6, -0.75),
    "sinav": (0.6, 0.3), "esneme": (0.3, 0.2), "asiri_yuk": (2.0, 3.5),
}

# program: [(aktivite, dakika/gün, gün/hafta)] — oturmanın yerine geçer
PROGRAMLAR = {
    "P1 Barfiks + asılma": [("barfiks", 5, 7), ("asilma", 5, 7)],
    "P2 Şınav": [("sinav", 10, 7)],
    "P3 Esneme": [("esneme", 20, 7)],
    "P4 Ters asılma": [("ters_asilma", 10, 7)],
    "P5 'Boy uzatma rutini'": [("barfiks", 5, 7), ("asilma", 5, 7), ("esneme", 20, 7), ("ters_asilma", 10, 7)],
    "P6 Koşu": [("kosu", 45, 5)],
    "P7 Basketbol": [("basketbol", 90, 4)],
    "P8 Ağırlık": [("agirlik_set", 15, 4), ("ayakta", 45, 4)],
    "P9 Aşırı yük": [("asiri_yuk", 180, 6)],
}

AYARLAR = {"üst sınır": (0.4, 1.0), "gerçekçi": (0.3, 0.5), "alt": (0.2, 0.25)}


def gunluk_fark(program, yuk=YUK):
    """D_j: günlük ortalama göreli yük farkı (oturmanın yerine geçen süre için)."""
    Dg = Db = 0.0
    for akt, dk, gun in program:
        saat = dk / 60 * gun / 7
        Dg += saat / 24 * (yuk[akt][0] - yuk["oturma"][0])
        Db += saat / 24 * (yuk[akt][1] - yuk["oturma"][1])
    return Db, Dg


def carpan(D, beta, eta):
    return 1 - beta * eta * D if D >= 0 else 1 + 0.5 * beta * eta * abs(D)
