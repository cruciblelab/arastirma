"""
ÖN KAYITSIZ KEŞİF (README "Bulgular", şeytanın avukatı itirazlarının kontrolü). calistir.py'den SONRA yazıldı.

    python kesif.py

E1  Rüya hatırlama kişiden kişiye değişirse (üçte biri hiç hatırlamıyor) "yılda ≥1" oranı ne olur?
E2  Belirgin olay olasılığı da kişiden kişiye değişirse?
E3  Yalnızca ağır olaylar (ölüm, kaza, ağır hastalık) sayılırsa (p_e = 0.01 ve 0.003)?
E4  Seçici hatırlamanın senaryodan bağımsız ölçüsü: odds oranı; ve s = 0.3, 0.1 için algılanan/gerçek oranı
E5  Rüya başına sayım (aynı rüya birden çok olaya bağlanmasın)
"""

import json
from pathlib import Path

import numpy as np

KOK = Path(__file__).resolve().parent
CIKTI = KOK / "ciktilar"
GUN, M_HIT, M_MISS = 365, 0.52, 0.215
rng = np.random.default_rng(20261030)
SONUC = {}


def pencere_toplam(x, W, ileri=False):
    c = np.concatenate([np.zeros((x.shape[0], 1), dtype=np.int64), np.cumsum(x, axis=1, dtype=np.int64)], axis=1)
    L = x.shape[1]
    j = np.arange(L)
    bas, son = (j, np.minimum(j + W, L)) if ileri else (np.maximum(j - W + 1, 0), j + 1)
    return c[:, son] - c[:, bas]


def simule(r_kisi, p_neg, pe_kisi, W, s):
    """r_kisi, pe_kisi: kişi başına değerler (N,). Olay başına ve rüya başına 'rüyam çıktı' sayısı."""
    N, L = len(r_kisi), GUN + 2 * W
    a, b = W, W + GUN
    ruya = rng.poisson((r_kisi * p_neg / 7)[:, None], size=(N, L)).astype(np.int64)
    olay = (rng.random((N, L)) < pe_kisi[:, None]).astype(np.int64)
    j = pencere_toplam(ruya, W)[:, a:b]
    H = ((olay[:, a:b] == 1) & (rng.random(j.shape) < 1 - (1 - s * M_HIT) ** j)).sum(axis=1)
    k = pencere_toplam(olay, W, ileri=True)[:, a:b]
    dogru = rng.binomial(ruya[:, a:b], 1 - (1 - s) ** k)
    H_ruya = rng.binomial(dogru, M_HIT).sum(axis=1)  # rüya başına: doğrulanmış ve hatırlanmış olumsuz rüya
    return dict(O1_olay=float(H.mean()), O2_olay=float((H >= 1).mean()), O1_ruya=float(H_ruya.mean()),
                O2_ruya=float((H_ruya >= 1).mean()))


N = 20_000
sabit_r, sabit_pe = np.full(N, 1.0), np.full(N, 0.10)
# E1: %31 hiç hatırlamıyor; kalanlarda üstel (gamma, şekil 1) dağılım; ortalama 1 rüya/hafta korunur
hatirlar = rng.random(N) >= 0.31
het_r = np.where(hatirlar, rng.gamma(1.0, 1.0 / 0.69, N), 0.0)
# E2: p_e kişiden kişiye Beta(2, 18) (ortalama 0.10)
het_pe = rng.beta(2, 18, N)
for s in (1.0, 0.3, 0.1):
    SONUC[f"E0_homojen_s{s}"] = simule(sabit_r, 0.33, sabit_pe, 7, s)
    SONUC[f"E1_r_heterojen_s{s}"] = simule(het_r, 0.33, sabit_pe, 7, s)
    SONUC[f"E2_r_ve_pe_heterojen_s{s}"] = simule(het_r, 0.33, het_pe, 7, s)
for pe in (0.01, 0.003):
    for s in (1.0, 0.1):
        SONUC[f"E3_pe{pe}_s{s}"] = simule(sabit_r, 0.33, np.full(N, pe), 7, s)

# E4: analitik (W = 7, p_e = 0.10): algılanan / gerçek ve odds oranı
for s in (1.0, 0.3, 0.1):
    c = 1 - (1 - 0.10 * s) ** 7
    algi = M_HIT * c / (M_HIT * c + M_MISS * (1 - c))
    SONUC[f"E4_s{s}"] = dict(gercek=c, algilanan=algi, oran=algi / c,
                             odds_orani=(algi / (1 - algi)) / (c / (1 - c)))

for k, v in SONUC.items():
    print(k, {a: round(b, 3) for a, b in v.items()})
(CIKTI / "kesif.json").write_text(json.dumps(SONUC, ensure_ascii=False, indent=1), encoding="utf-8")
