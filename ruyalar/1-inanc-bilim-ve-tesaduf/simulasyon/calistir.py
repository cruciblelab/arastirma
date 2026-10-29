"""
Rüyalar, sürüm 1: "rüyam çıktı" tesadüf simülasyonu (simulasyon/PLAN.md). Tek komut:

    python calistir.py

Rüyalar ve olaylar bağımsız üretilir (kehanet yok). Çıktılar O1-O5; testler T1-T4; karar kuralları K1-K5.
DreamBank analizinin çıktısı (../analiz/ciktilar/ozet.json) varsa, D4 oranı ek p_neg senaryosu olarak kullanılır.
"""

import itertools
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
TOHUM = 20261029
GUN = 365
M_HIT, M_MISS = 0.52, 0.215
TEMEL = dict(r=1.0, p_neg=0.33, p_e=0.10, W=7, s=1.0)
TESTLER, KARARLAR, OZET = [], [], {}
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK, IZGARA = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3", "#ecebe8"
MAVI, TURUNCU = "#2a78d6", "#eb6834"


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    print(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'}  ({deger})", flush=True)


def karar_kaydi(ad, soru, deger, karar):
    KARARLAR.append(dict(kural=ad, soru=soru, deger=deger, karar=karar))
    print(f"{ad}: {karar}  ({deger})", flush=True)


def pencere_toplam(x, W, ileri=False):
    """Her gün d için x'in d-W+1..d (geri) ya da d..d+W-1 (ileri) toplamı. x: (N, L)."""
    c = np.concatenate([np.zeros((x.shape[0], 1), dtype=np.int64), np.cumsum(x, axis=1, dtype=np.int64)], axis=1)
    L = x.shape[1]
    j = np.arange(L)
    if ileri:
        bas, son = j, np.minimum(j + W, L)
    else:
        bas, son = np.maximum(j - W + 1, 0), j + 1
    return c[:, son] - c[:, bas]


def simule(r, p_neg, p_e, W, s, N, rng, ek=False, parca=10_000):
    """Bir senaryoyu simüle eder (bellek için parça parça). Değerlendirme aralığı: [W, W+GUN) günleri/geceleri."""
    L = GUN + 2 * W
    a, b = W, W + GUN
    H_hepsi, toplam, dogrulanan, hat_d, hat_y = [], 0, 0, 0, 0
    t2 = [0, 0, 0, 0]  # olumsuz rüyayı izleyen günlerde olay sayısı, gün sayısı; tüm günlerde olay, gün
    kalan = N
    while kalan > 0:
        n = min(parca, kalan)
        kalan -= n
        ruya = rng.poisson(r * p_neg / 7, size=(n, L)).astype(np.int64)  # gece başına hatırlanan olumsuz rüya
        olay = (rng.random((n, L)) < p_e).astype(np.int64)  # gün başına belirgin olumsuz olay
        # O1: olay günü d; d-W+1..d gecelerindeki olumsuz rüyalardan en az biri eşleşip hatırlanırsa "rüyam çıktı"
        j = pencere_toplam(ruya, W)[:, a:b]
        p_bag = 1 - (1 - s * M_HIT) ** j
        cikti = (olay[:, a:b] == 1) & (rng.random(j.shape) < p_bag)
        H_hepsi.append(cikti.sum(axis=1))
        # O4/O5: gece n'deki her olumsuz rüya; n..n+W-1 günlerinde k olay; doğrulanma olasılığı 1-(1-s)^k
        k = pencere_toplam(olay, W, ileri=True)[:, a:b]
        c_n = ruya[:, a:b]
        dogru = rng.binomial(c_n, 1 - (1 - s) ** k)
        t_, d_ = int(c_n.sum()), int(dogru.sum())
        toplam += t_
        dogrulanan += d_
        hat_d += int(rng.binomial(d_, M_HIT))
        hat_y += int(rng.binomial(t_ - d_, M_MISS))
        if ek:
            ertesi = olay[:, a:b][c_n > 0]
            t2[0] += int(ertesi.sum()); t2[1] += int(ertesi.size)
            t2[2] += int(olay[:, a:b].sum()); t2[3] += int(olay[:, a:b].size)
    H = np.concatenate(H_hepsi)
    gercek = dogrulanan / toplam if toplam else np.nan
    algi = hat_d / (hat_d + hat_y) if (hat_d + hat_y) else np.nan
    sonuc = dict(r=r, p_neg=p_neg, p_e=p_e, W=W, s=s, N=N, O1=float(H.mean()), O2=float((H >= 1).mean()),
                 O3=float(1e6 * H.mean() / GUN), O4=gercek, O5=algi, ruya=toplam)
    if ek:
        sonuc["t2"] = (t2[0] / t2[1], t2[1], t2[2] / t2[3], t2[3])
    return sonuc


def analitik_O4(p_e, s, W):
    return 1 - (1 - p_e * s) ** W


def analitik_O5(c):
    return M_HIT * c / (M_HIT * c + M_MISS * (1 - c))


# ---------------------------------------------------------------- temel senaryo
temel = simule(**TEMEL, N=100_000, rng=np.random.default_rng(TOHUM), ek=True)
OZET["temel"] = {k: v for k, v in temel.items() if k != "t2"}
print("Temel:", OZET["temel"])

c0 = analitik_O4(TEMEL["p_e"], TEMEL["s"], TEMEL["W"])
test("T1", "Gerçek isabet oranı: simülasyon ile analitik farkı (temel)", f"{temel['O4']:.4f} - {c0:.4f} = "
     f"{temel['O4'] - c0:+.4f}", "|fark| < 0.005", abs(temel["O4"] - c0) < 0.005)

p1, n1, p0, n0 = temel["t2"]
fark = p1 - p0
se = np.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
lo, hi = fark - 1.96 * se, fark + 1.96 * se
test("T2", "Bağımsızlık: olumsuz rüyayı izleyen günde olay − rastgele günde olay", f"{fark:+.4f} [{lo:+.4f}, {hi:+.4f}]",
     "%95 aralık 0'ı içerir", lo <= 0 <= hi)

tekrar = simule(**TEMEL, N=100_000, rng=np.random.default_rng(TOHUM), ek=True)
ayni = all(tekrar[k] == temel[k] for k in ("O1", "O2", "O3", "O4", "O5", "ruya"))
test("T3", "Aynı tohumla tekrar çalıştırma", "birebir aynı" if ayni else "FARKLI", "birebir aynı", ayni)

s_pe0 = simule(**{**TEMEL, "p_e": 0.0}, N=5_000, rng=np.random.default_rng(TOHUM))
s_s0 = simule(**{**TEMEL, "s": 0.0}, N=5_000, rng=np.random.default_rng(TOHUM))
test("T4", "Uç durumlar: p_e = 0 ve s = 0 iken O1", f"{s_pe0['O1']}, {s_s0['O1']}", "ikisi de 0",
     s_pe0["O1"] == 0 and s_s0["O1"] == 0)

# ---------------------------------------------------------------- ızgara (192 senaryo, W = 7)
rng = np.random.default_rng(TOHUM + 1)
izgara = [simule(r, pn, pe, 7, s, 2_000, rng) for r, pn, pe, s in
          itertools.product([0.25, 1, 2, 5], [0.20, 0.33, 0.50, 0.72], [0.03, 0.10, 0.20, 0.40], [1.0, 0.3, 0.1])]
izg = pd.DataFrame(izgara)
izg.to_csv(CIKTI / "izgara.csv", index=False, float_format="%.4f")

# W taraması (temel senaryo)
rng = np.random.default_rng(TOHUM + 2)
pencere = pd.DataFrame([simule(**{**TEMEL, "W": W}, N=20_000, rng=rng) for W in (1, 3, 7, 14)])
pencere.to_csv(CIKTI / "pencere.csv", index=False, float_format="%.4f")

# Birebir yorum (s = 0.1) ve DreamBank tabanlı p_neg senaryoları
rng = np.random.default_rng(TOHUM + 3)
birebir = simule(**{**TEMEL, "s": 0.1}, N=100_000, rng=rng)
OZET["birebir_s01"] = birebir
db = KOK.parent / "analiz" / "ciktilar" / "ozet.json"
if db.exists():
    p_db = json.loads(db.read_text(encoding="utf-8"))["D4_p_neg"]
    OZET["dreambank"] = simule(**{**TEMEL, "p_neg": round(p_db, 4)}, N=100_000, rng=rng)
else:
    OZET["dreambank"] = "DreamBank çıktısı bulunamadı (önce ../analiz/calistir.py çalıştırılmalı)"

# ---------------------------------------------------------------- kararlar
t = OZET["temel"]
karar_kaydi("K1", "Temel senaryoda kehanet olmadan 'rüyam çıktı' yaygın mı?", f"P(yılda ≥1) = {t['O2']:.3f}",
            "insanların çoğu yılda en az bir kez yaşar" if t["O2"] >= 0.5 else "yaygın değil")
pay = float((izg.O2 >= 0.5).mean())
karar_kaydi("K2", "192 senaryonun yüzde kaçında P(yılda ≥1) ≥ 0.5?", f"%{pay * 100:.1f}",
            "ızgara özeti (ayrıntı izgara.csv)")
oran = t["O5"] / t["O4"]
karar_kaydi("K3", "Seçici hatırlama isabeti şişiriyor mu?", f"algılanan {t['O5']:.3f} / gerçek {t['O4']:.3f} = "
            f"{oran:.2f}", "evet, belirgin" if oran >= 1.5 else "sınırlı")
karar_kaydi("K4", "Milyon kişide günde kaç 'rüyam çıktı'?", f"{t['O3']:,.0f}",
            "her gün yüzlerce ya da daha fazla" if t["O3"] >= 100 else "günde 100'den az")
karar_kaydi("K5", "Birebir yorumda (s = 0.1) P(yılda ≥1)", f"{birebir['O2']:.3f} (s = 1: {t['O2']:.3f})",
            "raporlandı")
OZET["K2_parametreye_gore"] = {p: {str(k): float(v) for k, v in izg.groupby(p).O2.apply(lambda x: (x >= 0.5).mean())
                                   .items()} for p in ("r", "p_neg", "p_e", "s")}

# ---------------------------------------------------------------- grafik
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8), facecolor=YUZEY)
for ax in (ax1, ax2):
    ax.set_facecolor(YUZEY)
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(SOLUK)
    ax.tick_params(colors=MUR2)
    ax.grid(axis="y", color=IZGARA, lw=0.8)
    ax.set_axisbelow(True)
alt = izg[(izg.r == 1) & (izg.p_neg == 0.33)]
for s, renk, ad in ((1.0, MAVI, "sembolik yorum (s = 1)"), (0.1, TURUNCU, "birebir yorum (s = 0.1)")):
    x = alt[alt.s == s].sort_values("p_e")
    ax1.plot(x.p_e, x.O2 * 100, "o-", color=renk, lw=2, ms=6, label=ad)
ax1.set_xlabel("Günlük belirgin olumsuz olay olasılığı", color=MUR2)
ax1.set_ylabel("Yılda en az bir 'rüyam çıktı' (%)", color=MUR2)
ax1.set_title("Kehanet yokken bile 'rüyam çıktı'", color=MUR, loc="left", fontsize=10.5)
ax1.set_ylim(0, 100)
ax1.legend(frameon=False, fontsize=8.5)
ax2.bar([0, 1], [t["O4"] * 100, t["O5"] * 100], color=[SOLUK, MAVI], width=0.55)
for i, v in enumerate([t["O4"], t["O5"]]):
    ax2.text(i, v * 100 + 1.5, f"%{v * 100:.0f}", ha="center", color=MUR)
ax2.set_xticks([0, 1], ["Gerçek isabet", "Hatırlanan isabet"], color=MUR)
ax2.set_ylabel("Olumsuz rüyaların 'doğru çıkma' oranı (%)", color=MUR2)
ax2.set_title("Seçici hatırlama isabeti şişiriyor", color=MUR, loc="left", fontsize=10.5)
ax2.set_ylim(0, 100)
fig.tight_layout()
fig.savefig(CIKTI / "tesaduf.png", dpi=160)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET.update(testler=TESTLER, kararlar=KARARLAR, tohum=TOHUM, parametreler=dict(TEMEL, m_hit=M_HIT, m_miss=M_MISS))
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(f"Bitti: {sum(x['sonuc'] == 'GEÇTİ' for x in TESTLER)}/{len(TESTLER)} test geçti.")
