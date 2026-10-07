"""
Enerji, iştah, vücut bileşimi ve büyüme çarpanı (PLAN 3.2-3.5). Vektörel: n kişi aynı anda.

    dE/dt  = EI − TEE                                     (kcal/gün, Euler, Δt = 1 gün)
    p      = 10.4 / (10.4 + FM)                           (Forbes/Hall: değişimin yağsız payı)
    ΔW     = ΔE / (p·ρL + (1 − p)·ρF),  ΔFFM = p·ΔW,  ΔFM = (1 − p)·ΔW
    EI     = EI_ref + Δ + k·(W_set − W)                   (iştah geri beslemesi)
    N      = min(N_E(EA), N_P) · N_uyku                    (büyüme çarpanı, ≤ 1)
"""

from dataclasses import dataclass, field

import numpy as np

RHO_F = 39.5e3 / 4.184      # kcal/kg, Hall 2008
RHO_L = 7.6e3 / 4.184       # kcal/kg, Hall 2008
FORBES = 10.4               # kg, Hall 2007/2008
GUN_YIL = 365.25
METY = dict(futbol=8.7, basketbol=7.5, kosu=9.8, sinav=4.1, el_agirlik=2.9, ders=1.4, uzanma=1.1)
EAR = dict(erkek=0.73, kiz=0.71)   # g/kg/gün, DRI 14-18


def bmr(W, H, yas, erkek):
    """Schofield (ağırlık + boy), kcal/gün. W kg, H m. 17.5-18.5 yaş arası iki denklem harmanlanır."""
    if erkek:
        genc, yet = 16.6 * W + 77 * H + 572, 15.4 * W - 27 * H + 717
    else:
        genc, yet = 7.4 * W + 482 * H + 217, 13.3 * W + 334 * H + 35
    a = float(np.clip(yas - 17.5, 0.0, 1.0))
    return (1 - a) * genc + a * yet


@dataclass
class Durum:
    """Bir senaryonun müdahale dönemindeki koşulları (PLAN 3.7). Dönem dışında herkes S0 koşulundadır."""
    sepet: str = "B1 Dengeli"
    delta: float = 0.0              # kcal/gün, kasıtlı alım değişikliği
    spor_saat: float = 0.0          # saat/gün (haftalık ortalama)
    mety: float = METY["futbol"]
    spora_gore_yer: bool = False    # True: EI_ref spor harcamasını içerir (S8)
    uyku_kcal: float = 0.0          # kısa uykuyla gelen ek alım
    N_uyku: float = 1.0
    ek_harcama_saat: float = 0.0    # S6 mekanik varyant: uyanık oturulan ek saat
    bas: float = 16.0
    bit: float = 18.0


@dataclass
class Ayar:
    """Varsayımlar (PLAN 5)."""
    NE_bicim: str = "esik"
    N_min: float = 0.5
    dogrusal_taban: float = 0.5
    b: float = 1.0
    cv: float = 0.12
    k_kayip: float = 100.0
    k_artis: float = 100.0
    PAL: float = 1.55
    etiket: str = "ana"
    ekstra: dict = field(default_factory=dict)


def N_E(EA, ayar):
    if ayar.NE_bicim == "esik":
        return np.clip(ayar.N_min + (1 - ayar.N_min) * (EA - 20.0) / 10.0, ayar.N_min, 1.0)
    t = ayar.dogrusal_taban
    return np.clip(t + (1 - t) * (EA - 10.0) / 35.0, t, 1.0)


def N_P(P, W, r, cinsiyet, ayar):
    oran = P / (EAR[cinsiyet] * W * r)
    return np.where(oran >= 1.0, 1.0, np.clip(1 - ayar.b * (1 - oran), 0.0, 1.0))


def simule(cinsiyet, W0, FM0, H_fn, z, prot_yog, durum, ayar, yas0=16.0, yas1=25.0, dt=1.0,
           kayit_her=30, anlik=(17.0, 18.0, 21.0, 25.0)):
    """Günlük adımlı enerji/vücut bileşimi modeli.

    H_fn(yas) -> (n,) boy (m). prot_yog: {sepet: g protein/kcal}. z: protein ihtiyacı için N(0,1) çekilişi.
    Döndürür: seyrek zaman serileri (her kayit_her günde bir), 'anlik' yaşlardaki durum (ilk yas ≥ hedef adım),
    müdahale dönemindeki en düşük EA ve N, günlük N serisi ve F1 için enerji defteri.
    """
    erkek = cinsiyet == "erkek"
    n = W0.size
    adim = int(round((yas1 - yas0) * GUN_YIL / dt))
    r = np.clip(1 + ayar.cv * z, 0.5, 1.5)
    H0 = H_fn(yas0)
    W, FM = W0.astype(float).copy(), FM0.astype(float).copy()
    FFM = W - FM
    defter = np.zeros(n)                  # Σ (EI − TEE)·Δt
    mutlak = np.zeros(n)
    kayit = {k: [] for k in ("yas", "W", "FM", "EI", "TEE", "EA", "N", "NE", "NP", "P_gkg", "buyume_kcal")}
    N_ser = np.empty((n, adim + 1))
    anlar, min_EA, min_N = {}, np.full(n, np.inf), np.ones(n)
    for i in range(adim + 1):
        yas = yas0 + i * dt / GUN_YIL
        aktif = durum.bas <= yas < durum.bit
        d = durum if aktif else Durum()
        H = H_fn(yas)
        W_set = W0 * (H / H0) ** 2
        dWset = (W0 * (H_fn(min(yas + dt / GUN_YIL, yas1)) / H0) ** 2 - W_set) / dt  # kg/gün
        p = FORBES / (FORBES + FM)
        rho = p * RHO_L + (1 - p) * RHO_F
        buyume = np.maximum(dWset, 0.0) * rho
        B = bmr(W, H, yas, erkek)
        B_set = bmr(W_set, H, yas, erkek)
        eee_net = (d.mety - METY["ders"]) * B / 24 * d.spor_saat
        eee_brut = d.mety * B / 24 * d.spor_saat
        ek = (METY["ders"] - METY["uzanma"]) * B / 24 * d.ek_harcama_saat
        TEE = B * ayar.PAL + eee_net + ek
        EI_ref = B_set * ayar.PAL + buyume
        if d.spora_gore_yer:
            EI_ref = EI_ref + (d.mety - METY["ders"]) * B_set / 24 * d.spor_saat
        fark = W_set - W
        istah = np.where(fark > 0, ayar.k_kayip * fark, ayar.k_artis * fark)
        EI = np.maximum(EI_ref + d.delta + d.uyku_kcal + istah, 0.0)
        EA = (EI - eee_brut) / FFM
        P = prot_yog[d.sepet] * EI
        ne, npr = N_E(EA, ayar), N_P(P, W, r, cinsiyet, ayar)
        N = np.minimum(ne, npr) * d.N_uyku
        assert np.all((N >= 0) & (N <= 1)), "S3: çarpan [0,1] dışında"
        N_ser[:, i] = N
        if aktif:
            min_EA, min_N = np.minimum(min_EA, EA), np.minimum(min_N, N)
        for a in anlik:
            if a not in anlar and (yas >= a - 1e-9 or i == adim):
                anlar[a] = dict(W=W.copy(), FM=FM.copy(), BF=100 * FM / W, BMI=W / H ** 2, EI=EI.copy(),
                                TEE=np.asarray(TEE, float).copy(), EA=EA.copy(), P_gkg=P / W)
        if i % kayit_her == 0:
            for k, v in (("yas", np.full(n, yas)), ("W", W), ("FM", FM), ("EI", EI), ("TEE", TEE), ("EA", EA),
                         ("N", N), ("NE", ne), ("NP", npr), ("P_gkg", P / W), ("buyume_kcal", buyume)):
                kayit[k].append(np.array(v, float))
        if i == adim:
            break
        dE = (EI - TEE) * dt
        defter += dE
        mutlak += np.abs(dE)
        dW = dE / rho
        FFM = FFM + p * dW
        FM = FM + (1 - p) * dW
        W = FM + FFM
        assert np.all(FM > 0) and np.all(FFM > 0), "S3: negatif doku kütlesi"
    depo = RHO_F * (FM - FM0) + RHO_L * (FFM - (W0 - FM0))
    F1 = np.abs(defter - depo) / np.maximum(mutlak, 1.0)
    out = {k: np.array(v).T for k, v in kayit.items()}
    out.update(N_ser=N_ser, dt=dt, yas0=yas0, F1=F1, anlar=anlar, min_EA=min_EA, min_N=min_N)
    return out


def N_fonksiyonu(N_ser, yas0, dt):
    """Günlük N serisini sürüm 3 modelinin Senaryo.N(t) arayüzüne çevirir (doğrusal aradeğer)."""
    son = N_ser.shape[1] - 1

    def N(t):
        if t < yas0:
            return 1.0
        x = (t - yas0) * GUN_YIL / dt
        i = min(int(np.floor(x)), son)
        if i >= son:
            return N_ser[:, son]
        f = x - i
        return N_ser[:, i] * (1 - f) + N_ser[:, i + 1] * f
    return N
