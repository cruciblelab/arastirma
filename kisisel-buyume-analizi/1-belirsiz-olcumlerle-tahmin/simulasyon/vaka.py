"""
Belirsiz ölçümlerden kişisel büyüme sonsalı (PLAN 3). Önem örneklemesi.

    r_i = H(a_i) − D·f_i + s_i            okuma (gerçek sabah boyu − gün içi kısalma + ayakkabı)
    y_i ~ N(r_i, σ_i² + w_i²/12)          bildirilen değer (tek değer ya da w genişliğinde aralık)
    r_a − r_b ~ N(fark, σ_eş²)            "şimdi akşam ölçünce işaretle aynı" türü fark gözlemi
    önsel: sürüm 3 sanal kohortu; anne-baba varsa erişkin boy N(μ_h, SD_h²)'ye yeniden ağırlıklandırılır
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import norm

REPO = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO / "spor-egzersiz-ve-boy" / "1-fizik-tabanli-simulasyon" / "simulasyon"))
sys.path.append(str(REPO / "boy-uzamasi-16-18-yas" / "3-mekanistik-simulasyon-ve-on-kayit" / "simulasyon"))

import plak                        # noqa: E402
from model import simule_et        # noqa: E402

D_GUNICI = 1.44                    # cm, spor araştırması sürüm 1 (gün içi boy farkı)
GALTON = {"erkek": (0.746, 5.83), "kiz": (0.687, 5.13)}   # sürüm 3, Ek_galton (eğim, artık SD)
IZGARA = np.round(np.arange(11.0, 21.0 + 1e-9, 0.05), 2)   # sapma 1: 21 yaşa kadar (Berkeley son ölçüm yaşları)
KAYIT = list(IZGARA) + [25.0]
SAAT = {"sabah": (0.0, 0.3), "aksam": (0.7, 1.0), "bilinmiyor": (0.0, 1.0)}


@dataclass
class Ayar:
    etiket: str = "ana"
    ayakkabi: bool = False          # True: ayakkabısı bilinmeyen ölçümlere U(0, 2.5) cm
    D: float = D_GUNICI
    isaret_saat: str = None         # None: girdideki gibi; "sabah"/"aksam": işaret ölçümüne zorla
    hata_kat: float = 1.0
    anne_baba: bool = True
    yas_genislet: float = 0.0


class Onsel:
    """N sanal kişinin 11-21 yaş (0.05 adım) ve 25 yaş sabah boyları (float32)."""

    def __init__(self, cinsiyet, N, tohum, parca=50_000):
        rng = np.random.default_rng(tohum)
        pop, ind, L0b, L0g = plak.kohort(cinsiyet, N, rng)
        self.c, self.N = cinsiyet, N
        self.H = np.empty((N, len(KAYIT)), np.float32)
        for a in range(0, N, parca):
            b = min(a + parca, N)
            alt = {k: v[a:b] for k, v in ind.items()}
            s = simule_et(alt, pop, L0b[a:b], L0g[a:b], t1=25.0, kayit_yaslari=KAYIT)
            self.H[a:b] = s["boy"].T
        self.H21, self.H25 = self.H[:, len(IZGARA) - 1].astype(float), self.H[:, -1].astype(float)
        self.mk, self.sk = float(self.H25.mean()), float(self.H25.std())
        hiz = np.diff(self.H[:, :len(IZGARA)], axis=1)
        orta = (IZGARA[:-1] + IZGARA[1:]) / 2
        sec = orta <= 17.5
        self.tepe_yasi = orta[sec][np.argmax(hiz[:, sec], axis=1)]

    def boy(self, yas):
        """Her kişi için kendi yaşında (n,) boy; 11-21 arasında doğrusal aradeğer."""
        x = (np.asarray(yas, float) - IZGARA[0]) / 0.05
        i = np.clip(np.floor(x).astype(int), 0, len(IZGARA) - 2)
        f = x - i
        n = np.arange(self.N)
        return self.H[n, i] * (1 - f) + self.H[n, i + 1] * f


def sonsal(onsel, girdi, ayar=Ayar(), tohum=1):
    """Ağırlıklar ve türetilmiş büyüklükler. girdi: dict (ornek_girdi.json biçimi)."""
    rng = np.random.default_rng(tohum)
    N = onsel.N
    logw = np.zeros(N)
    if ayar.anne_baba and girdi.get("anne") and girdi.get("baba"):
        egim, sd = GALTON[onsel.c]
        oab = (girdi["baba"] + girdi["anne"] + (13 if onsel.c == "erkek" else -13)) / 2
        mu = onsel.mk + egim * (oab - onsel.mk)
        logw += norm.logpdf(onsel.H25, mu, sd) - norm.logpdf(onsel.H25, onsel.mk, onsel.sk)
    r = {}
    for o in girdi["olcumler"]:
        lo, hi = o["yas"]
        a = rng.uniform(lo - ayar.yas_genislet, hi + ayar.yas_genislet, N)
        saat = ayar.isaret_saat if (o.get("isaret") and ayar.isaret_saat) else o.get("saat", "bilinmiyor")
        f = rng.uniform(*SAAT[saat], N)
        s = rng.uniform(0, 2.5, N) if (ayar.ayakkabi and o.get("ayakkabi") == "bilinmiyor") else 0.0
        r[o["ad"]] = onsel.boy(a) - ayar.D * f + s
        if "deger" in o or "aralik" in o:
            sd = o.get("hata_sd", 1.0) * ayar.hata_kat
            if "aralik" in o:
                y, var = np.mean(o["aralik"]), sd ** 2 + (o["aralik"][1] - o["aralik"][0]) ** 2 / 12
            else:
                y, var = o["deger"], sd ** 2
            logw += norm.logpdf(y, r[o["ad"]], np.sqrt(var))
    for fk in girdi.get("farklar", []):
        logw += norm.logpdf(r[fk["a"]] - r[fk["b"]], fk.get("deger", 0.0), fk.get("sd", 0.5) * ayar.hata_kat)
    w = np.exp(logw - logw.max())
    w /= w.sum()
    t = girdi["simdiki_yas"]
    simdi = onsel.boy(np.full(N, t))
    return dict(w=w, ess=float(1 / np.sum(w ** 2)), simdi=simdi,
                son_yil=simdi - onsel.boy(np.full(N, t - 1.0)),
                kalan=onsel.H25 - simdi, H25=onsel.H25, H21=onsel.H21, kalan21=onsel.H21 - simdi,
                tepe_yasi=onsel.tepe_yasi)


def yuzdelik(x, w, q):
    i = np.argsort(x)
    cw = np.cumsum(w[i])
    cw /= cw[-1]
    return np.interp(np.asarray(q) / 100.0, cw, x[i])


def ozetle(s):
    w = s["w"]
    out = {"ESS": s["ess"]}
    for k in ("simdi", "son_yil", "kalan", "H25", "tepe_yasi"):
        q = yuzdelik(s[k], w, [2.5, 10, 50, 90, 97.5])
        out[k] = dict(zip(["p2.5", "p10", "medyan", "p90", "p97.5"], map(float, q)))
    for e in (0.5, 1, 2, 3):
        out[f"P_kalan_en_az_{e}cm"] = float(np.sum(w[s["kalan"] >= e]))
    return out
