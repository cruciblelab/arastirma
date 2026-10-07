"""
Boy uzaması simülasyonu - çekirdek model.

İki katman var:

1) Preece-Baines Model 1 (PB1): Ergenlik büyüme eğrisi için literatürde en çok
   kullanılan parametrik model (Preece & Baines, 1978). Bir kişinin "genetik
   rotasını" (optimal koşullardaki boy eğrisini) temsil ediyor.

       h(t) = h1 - 2 (h1 - hθ) / (exp(s0 (t-θ)) + exp(s1 (t-θ)))

   h1  : erişkin boy (asimptot) -> genetik potansiyel
   θ   : zamanlama parametresi -> erken / geç olgunlaşma
   s0  : ergenlik öncesi hız sabiti
   s1  : ergenlik hız sabiti (büyük s1 = büyümenin keskin bitmesi)

2) Dinamik katman (bizim eklediğimiz, oyuncak model): Çevresel etkileri
   "biyolojik saat" (kemik yaşı) ve "büyüme verimi" olarak ayırıyor.

       dτ/dt = r(t)                         biyolojik saat ne hızla ilerliyor
       dh/dt = r(t) * v_PB(τ) * m(t)        normal büyüme
             + k * max(D, 0) * g(τ)         yakalama (catch-up) büyümesi

   r : olgunlaşma hızı. 1 = normal. <1 kemik yaşı yavaşlıyor (plak geç kapanır),
       >1 hızlanıyor (plak erken kapanır).
   m : büyüme verimi. 1 = optimal. <1 = eksiklik (enerji, protein, uyku, hastalık).
   D : kişinin kendi genetik rotasına göre açığı = h_PB(τ) - h
   g : yakalama kapasitesi, plak açıklığıyla orantılı = min(1, v_PB(τ)/v_ref)

   Biyolojik dayanak (niteliksel): kronik yetersiz beslenme / hastalıkta hem
   büyüme hem kemik olgunlaşması yavaşlar; sebep düzelince plak hâlâ açıksa
   yakalama büyümesi olur. Bu kısmın SAYISAL parametreleri (alfa, k, v_ref)
   literatürden ölçülmüş değerler DEĞİL, varsayımdır. Bu yüzden duyarlılık
   analizi ayrıca yapılıyor. Model mekanizmayı ve büyüklük sırasını gösterir,
   kesin cm vaat etmez.
"""

from dataclasses import dataclass, replace

import numpy as np

# ---------------------------------------------------------------------------
# Popülasyon parametreleri
# Kalibrasyon hedefi: Türk ve Avrupa referanslarındaki özet değerler
#   - erişkin boy ort. erkek ~176-177 cm, kız ~163 cm (Neyzi ve ark.)
#   - zirve büyüme hızı (PHV) yaşı erkek ~13.9, kız ~11.6
#   - PHV erkek ~9 cm/yıl, kız ~7.5-8 cm/yıl
# Bunlar bireysel veriye fit edilmiş değil, özet istatistiklere elle ayarlandı.
# ---------------------------------------------------------------------------

POP = {
    "erkek": dict(h1_ort=176.5, h1_sd=6.5, delta_ort=13.5, delta_sd=1.2,
                  s0_ort=0.10, s0_sd=0.01, s1_ort=1.20, s1_sd=0.12,
                  theta_ort=14.3, theta_sd=0.9),
    "kiz": dict(h1_ort=163.0, h1_sd=6.0, delta_ort=10.5, delta_sd=1.0,
                s0_ort=0.12, s0_sd=0.012, s1_ort=1.30, s1_sd=0.13,
                theta_ort=12.0, theta_sd=0.9),
}


@dataclass(frozen=True)
class PB1:
    h1: float
    ht: float
    s0: float
    s1: float
    theta: float

    def boy(self, t):
        u = np.asarray(t, dtype=float) - self.theta
        return self.h1 - 2.0 * (self.h1 - self.ht) / (np.exp(self.s0 * u) + np.exp(self.s1 * u))

    def hiz(self, t):
        u = np.asarray(t, dtype=float) - self.theta
        e0, e1 = np.exp(self.s0 * u), np.exp(self.s1 * u)
        return 2.0 * (self.h1 - self.ht) * (self.s0 * e0 + self.s1 * e1) / (e0 + e1) ** 2


def ortalama_birey(cinsiyet: str, theta_kayma: float = 0.0, h1: float | None = None) -> PB1:
    p = POP[cinsiyet]
    h1 = p["h1_ort"] if h1 is None else h1
    return PB1(h1=h1, ht=h1 - p["delta_ort"], s0=p["s0_ort"], s1=p["s1_ort"],
               theta=p["theta_ort"] + theta_kayma)


def populasyon_ornekle(cinsiyet: str, n: int, rng: np.random.Generator,
                       h1_ort: float | None = None, h1_sd: float | None = None):
    """Vektörel parametre dizileri döndürür (her biri n uzunlukta)."""
    p = POP[cinsiyet]
    h1 = rng.normal(p["h1_ort"] if h1_ort is None else h1_ort,
                    p["h1_sd"] if h1_sd is None else h1_sd, n)
    delta = np.clip(rng.normal(p["delta_ort"], p["delta_sd"], n), 5, None)
    s0 = np.clip(rng.normal(p["s0_ort"], p["s0_sd"], n), 0.05, None)
    s1 = np.clip(rng.normal(p["s1_ort"], p["s1_sd"], n), 0.6, None)
    theta = rng.normal(p["theta_ort"], p["theta_sd"], n)
    return dict(h1=h1, ht=h1 - delta, s0=s0, s1=s1, theta=theta)


def pb_boy(par, t):
    u = t - par["theta"]
    return par["h1"] - 2.0 * (par["h1"] - par["ht"]) / (np.exp(par["s0"] * u) + np.exp(par["s1"] * u))


def pb_hiz(par, t):
    u = t - par["theta"]
    e0, e1 = np.exp(par["s0"] * u), np.exp(par["s1"] * u)
    return 2.0 * (par["h1"] - par["ht"]) * (par["s0"] * e0 + par["s1"] * e1) / (e0 + e1) ** 2


# ---------------------------------------------------------------------------
# Dinamik katman
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Donem:
    """[bas, bit) yaş aralığında geçerli olan bir müdahale/koşul."""
    bas: float
    bit: float
    m: float = 1.0          # büyüme verimi
    r: float | None = None  # olgunlaşma hızı; None ise m'den türetilir
    ad: str = ""


@dataclass(frozen=True)
class DinamikAyar:
    alfa: float = 0.5   # eksikliğin olgunlaşmayı ne kadar yavaşlattığı (0: hiç, 1: büyümeyle aynı oranda)
    k: float = 1.0      # yakalama hızı (1/yıl)
    v_ref: float = 3.0  # bu hızın üzerindeyken yakalama kapasitesi tam (cm/yıl)
    dt: float = 0.005


def simule_et(birey: PB1, donemler: list[Donem], bas_yas: float, bit_yas: float = 23.0,
              ayar: DinamikAyar = DinamikAyar()):
    """bas_yas'ta kişi tam kendi genetik rotasında başlar. Zaman serisi döndürür."""
    n = int(round((bit_yas - bas_yas) / ayar.dt)) + 1
    t = np.linspace(bas_yas, bit_yas, n)
    h = np.empty(n)
    tau = np.empty(n)
    h[0] = birey.boy(bas_yas)
    tau[0] = bas_yas
    for i in range(1, n):
        ti = t[i - 1]
        m, r = 1.0, 1.0
        for d in donemler:
            if d.bas <= ti < d.bit:
                m = d.m
                r = d.r if d.r is not None else 1.0 - ayar.alfa * (1.0 - d.m)
        v_pb = float(birey.hiz(tau[i - 1]))
        acik = max(float(birey.boy(tau[i - 1])) - h[i - 1], 0.0)
        g = min(1.0, v_pb / ayar.v_ref)
        yakalama = ayar.k * acik * g if m >= 1.0 else 0.0
        h[i] = h[i - 1] + ayar.dt * (r * v_pb * m + yakalama)
        tau[i] = tau[i - 1] + ayar.dt * r
    return t, h, tau


def senaryo_degistir(d: Donem, **kw) -> Donem:
    return replace(d, **kw)
