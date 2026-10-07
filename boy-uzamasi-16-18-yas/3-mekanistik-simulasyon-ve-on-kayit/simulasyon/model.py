"""
Büyüme plağı dijital ikizi: model çekirdeği. Denklemler ve gerekçeleri PLAN.md bölüm 3'te.

    E   = a_rom(t) · σ((t − T_p)/w_E) + ΔE(t)                    östrojen etkisi
    I   = 1 + A_p · E                                            GH/IGF-1 ekseni
    v_j = G_j · I^α_j · N(t) · S_j^γ · Φ(S_j)                     plak çıktısı (cm/yıl)
    dS_j/dt = −S_j · [κ_j · v_j/G_j + ε_j · E]                   öncü hücre stoku tükenmesi
    Φ(S) = σ((S − S_f)/(0.15·S_f))                                kaynaşma kapısı
    H = L_bacak + L_govde

Stok güncellemesi üstel adımla yapılır (S·exp(−Δt·oran)); böylece S hiçbir zaman
artmaz ve sıfırın altına inmez (fiziksel tutarlılık, PLAN S3).
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
from scipy.special import expit

T0 = 9.0
DT = 0.02
KAPI = 0.15
ORTAK = ["kb", "kg", "gam", "Sf"]          # hücre düzeyi, cinsiyetler ortak
CINS = ["wE", "eb", "eg", "ag"]            # hormon ortamı, cinsiyete özgü
BIREY = ["Gb", "Gg", "Tp", "Ap"]
CINSIYETLER = ("erkek", "kiz")


@dataclass
class Senaryo:
    """Zamana bağlı müdahaleler. Fonksiyonlar t (yaş) alır, skaler ya da (n,) dizi döndürür."""
    N: callable = None       # beslenme/hastalık çarpanı (1 = normal)
    a_rom: callable = None   # aromatizasyon çarpanı (1 = normal, 0 = östrojen yok)
    dE: callable = None      # dışarıdan eklenen steroid etkisi

    def degerler(self, t):
        return (1.0 if self.N is None else self.N(t),
                1.0 if self.a_rom is None else self.a_rom(t),
                0.0 if self.dE is None else self.dE(t))


def simule_et(ind, pop, L0b, L0g, t1=30.0, dt=DT, senaryo=None, kayit_yaslari=None, kontrol=False):
    """Vektörel (n kişi) simülasyon. kayit_yaslari'ndaki boyları döndürür.

    Döndürür: dict(yas, bacak, govde, boy) — her biri (len(kayit_yaslari), n).
    kontrol=True ise S3 fiziksel tutarlılık kontrollerini uygular.
    """
    Gb, Gg, Tp, Ap = (np.asarray(ind[k], float) for k in BIREY)
    n = Gb.size
    adim = int(round((t1 - T0) / dt))
    if kayit_yaslari is None:
        kayit_yaslari = np.round(np.arange(T0, t1 + 1e-9, 0.5), 3)
    kayit_idx = np.round((np.asarray(kayit_yaslari) - T0) / dt).astype(int)
    if kayit_idx.max() > adim or kayit_idx.min() < 0:
        raise ValueError("kayıt yaşı simülasyon aralığı dışında")
    kayit_hedef = {int(i): j for j, i in enumerate(kayit_idx)}
    Lb = np.array(L0b, float, copy=True)
    Lg = np.array(L0g, float, copy=True)
    Sb, Sg = np.ones(n), np.ones(n)
    outb = np.empty((len(kayit_idx), n))
    outg = np.empty((len(kayit_idx), n))
    sw = KAPI * pop["Sf"]
    sen = senaryo or Senaryo()
    for i in range(adim + 1):
        if i in kayit_hedef:
            outb[kayit_hedef[i]] = Lb
            outg[kayit_hedef[i]] = Lg
        if i == adim:
            break
        t = T0 + i * dt
        N, a_rom, dE = sen.degerler(t)
        E = a_rom * expit((t - Tp) / pop["wE"]) + dE
        I = 1.0 + Ap * E
        vb = Gb * I * N * Sb ** pop["gam"] * expit((Sb - pop["Sf"]) / sw)
        vg = Gg * I ** pop["ag"] * N * Sg ** pop["gam"] * expit((Sg - pop["Sf"]) / sw)
        Sb_yeni = Sb * np.exp(-dt * (pop["kb"] * vb / Gb + pop["eb"] * E))
        Sg_yeni = Sg * np.exp(-dt * (pop["kg"] * vg / Gg + pop["eg"] * E))
        if kontrol:
            assert np.all(vb >= 0) and np.all(vg >= 0), "S3: negatif büyüme hızı"
            assert np.all(Sb_yeni <= Sb + 1e-12) and np.all(Sg_yeni <= Sg + 1e-12), "S3: hücre stoku arttı"
            assert np.all(Sb_yeni > 0) and np.all(Sg_yeni > 0), "S3: stok sıfırın altına indi"
        Sb, Sg = Sb_yeni, Sg_yeni
        Lb = Lb + dt * vb
        Lg = Lg + dt * vg
    boy = outb + outg
    if kontrol:
        assert np.allclose(boy, outb + outg), "S3: korunum (boy = bacak + gövde)"
    return dict(yas=np.asarray(kayit_yaslari), bacak=outb, govde=outg, boy=boy)


def fizik_kontrol(ind, pop, L0b, L0g):
    """S3: işaret/korunum kontrolleri + zaman adımı yakınsaması (Δt ve Δt/2)."""
    a = simule_et(ind, pop, L0b, L0g, kayit_yaslari=[30.0], kontrol=True)["boy"][0]
    b = simule_et(ind, pop, L0b, L0g, dt=DT / 2, kayit_yaslari=[30.0], kontrol=True)["boy"][0]
    fark = float(np.max(np.abs(a - b)))
    assert fark < 0.05, f"S3: zaman adımı yakınsaması sağlanmadı ({fark:.3f} cm)"
    return fark


# ---------------------------------------------------------------------------
# Kalibrasyon
# ---------------------------------------------------------------------------

BASLANGIC_ORTAK = dict(kb=0.1, kg=0.1, gam=1.5, Sf=0.01)
BASLANGIC_CINS = {"erkek": dict(wE=0.55, eb=1.4, eg=0.6, ag=1.4),
                  "kiz": dict(wE=0.55, eb=0.64, eg=0.36, ag=2.0)}
BASLANGIC_BIREY = {"erkek": dict(Gb=3.6, Gg=2.0, Tp=13.6, Ap=4.0),
                   "kiz": dict(Gb=3.5, Gg=1.8, Tp=11.8, Ap=1.6)}
SINIR_ORTAK = dict(kb=(0, 3), kg=(0, 3), gam=(0.3, 6), Sf=(0.0005, 0.5))
SINIR_CINS = dict(wE=(0.2, 3), eb=(0, 5), eg=(0, 5), ag=(0.2, 4))
SINIR_BIREY = dict(Gb=(0.3, 12), Gg=(0.3, 12), Tp=(8, 18), Ap=(0, 12))


def _kayit_yaslari():
    from veri import YASLAR
    return YASLAR


def _maske(B, G, kesme=None):
    from veri import YASLAR
    m = ~np.isnan(B) & ~np.isnan(G)
    if kesme is not None:
        m &= (YASLAR <= kesme + 1e-9)[None, :]
    return m


def kalibre_et(veri, max_nfev=500):
    """veri: {cinsiyet: (B, G)} (bireyler x YASLAR). Ortak + cinsiyet + bireysel parametreleri birlikte fit eder."""
    yaslar = _kayit_yaslari()
    n = {c: veri[c][0].shape[0] for c in CINSIYETLER}
    maske = {c: _maske(*veri[c]) for c in CINSIYETLER}
    adlar = ORTAK + [f"{k}_{c}" for c in CINSIYETLER for k in CINS]
    npop = len(adlar)
    ofset = {"erkek": npop, "kiz": npop + 4 * n["erkek"]}

    def coz(p):
        P = dict(zip(adlar, p[:npop]))
        sonuc = {}
        for c in CINSIYETLER:
            q = p[ofset[c]:ofset[c] + 4 * n[c]].reshape(4, n[c])
            pop = {**{k: P[k] for k in ORTAK}, **{k: P[f"{k}_{c}"] for k in CINS}}
            sonuc[c] = (pop, dict(zip(BIREY, q)))
        return sonuc

    def artik(p):
        out = []
        for c, (pop, ind) in coz(p).items():
            B, G = veri[c]
            s = simule_et(ind, pop, B[:, 0], G[:, 0], t1=float(yaslar[-1]), kayit_yaslari=yaslar)
            out += [(s["bacak"].T - B)[maske[c]], (s["govde"].T - G)[maske[c]]]
        return np.concatenate(out)

    p0 = [BASLANGIC_ORTAK[k] for k in ORTAK] + [BASLANGIC_CINS[c][k] for c in CINSIYETLER for k in CINS]
    alt = [SINIR_ORTAK[k][0] for k in ORTAK] + [SINIR_CINS[k][0] for c in CINSIYETLER for k in CINS]
    ust = [SINIR_ORTAK[k][1] for k in ORTAK] + [SINIR_CINS[k][1] for c in CINSIYETLER for k in CINS]
    for c in CINSIYETLER:
        for k in BIREY:
            p0 += [BASLANGIC_BIREY[c][k]] * n[c]
            alt += [SINIR_BIREY[k][0]] * n[c]
            ust += [SINIR_BIREY[k][1]] * n[c]
    p0, alt, ust = map(np.array, (p0, alt, ust))

    # Seyrek Jacobian: her artık yalnızca kendi bireyinin ve ilgili popülasyon parametrelerinin fonksiyonu
    m = {c: int(maske[c].sum()) for c in CINSIYETLER}
    J = lil_matrix((2 * (m["erkek"] + m["kiz"]), len(p0)), dtype=int)
    satir0 = {"erkek": 0, "kiz": 2 * m["erkek"]}
    J[:, :len(ORTAK)] = 1
    for ci, c in enumerate(CINSIYETLER):
        cs = len(ORTAK) + ci * len(CINS)
        J[satir0[c]:satir0[c] + 2 * m[c], cs:cs + len(CINS)] = 1
        bireyler = np.where(maske[c])[0]
        for k, r in enumerate(bireyler):
            for q in range(4):
                col = ofset[c] + q * n[c] + r
                J[satir0[c] + k, col] = 1
                J[satir0[c] + m[c] + k, col] = 1
    sonuc = least_squares(artik, p0, bounds=(alt, ust), jac_sparsity=J, x_scale="jac", max_nfev=max_nfev)
    return coz(sonuc.x), sonuc


def bireysel_fit(B, G, pop, kesme, cinsiyet, max_nfev=300):
    """Popülasyon parametreleri sabitken bireysel parametreleri yalnızca kesme yaşına kadarki veriyle fit eder."""
    yaslar = _kayit_yaslari()
    n = B.shape[0]
    maske = _maske(B, G, kesme)
    son_yas = float(yaslar[yaslar <= kesme + 1e-9][-1])
    kayit = yaslar[yaslar <= son_yas + 1e-9]
    Bm, Gm, mm = B[:, :len(kayit)], G[:, :len(kayit)], maske[:, :len(kayit)]

    def artik(p):
        ind = dict(zip(BIREY, p.reshape(4, n)))
        s = simule_et(ind, pop, B[:, 0], G[:, 0], t1=son_yas, kayit_yaslari=kayit)
        return np.concatenate([(s["bacak"].T - Bm)[mm], (s["govde"].T - Gm)[mm]])

    p0 = np.concatenate([np.full(n, BASLANGIC_BIREY[cinsiyet][k]) for k in BIREY])
    alt = np.concatenate([np.full(n, SINIR_BIREY[k][0]) for k in BIREY])
    ust = np.concatenate([np.full(n, SINIR_BIREY[k][1]) for k in BIREY])
    m = int(mm.sum())
    J = lil_matrix((2 * m, 4 * n), dtype=int)
    for k, r in enumerate(np.where(mm)[0]):
        for q in range(4):
            J[k, q * n + r] = 1
            J[m + k, q * n + r] = 1
    s = least_squares(artik, p0, bounds=(alt, ust), jac_sparsity=J, x_scale="jac", max_nfev=max_nfev)
    return dict(zip(BIREY, s.x.reshape(4, n)))


# ---------------------------------------------------------------------------
# PB1 karşılaştırıcısı (v2 ile aynı)
# ---------------------------------------------------------------------------

def pb_boy(t, h1, ht, s0, s1, th):
    u = np.asarray(t, float) - th
    return h1 - 2.0 * (h1 - ht) / (np.exp(s0 * u) + np.exp(s1 * u))


def pb_fit(yas, boy, cinsiyet):
    from scipy.optimize import curve_fit
    yas, boy = np.asarray(yas), np.asarray(boy)
    p0 = [boy.max() + 1, boy.max() - 12, 0.1, 1.2, 14.0 if cinsiyet == "erkek" else 12.0]
    p, _ = curve_fit(pb_boy, yas, boy, p0=p0, maxfev=20000,
                     bounds=([100, 80, 0.01, 0.3, 8], [230, 220, 0.5, 5, 20]))
    return p
