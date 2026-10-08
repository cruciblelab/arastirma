"""
Deney ön kaydının simülasyonu: güç analizi, analiz yönteminin doğrulanması, şablonlar (PLAN.md). Tek komut:

    python calistir.py

Adımlar
  1  ANSUR II referans değerleri (gerçek veri analizinde de kullanılır) → ciktilar/ansur_referans.json
  2  Güç ızgarası: N hedef × R değerlendirici × seçim × gerçek PSE₂ (hücre başına 300 sentetik deney)
  3  Önerilen tasarım (PLAN 5 kuralı) ve testler D1-D5
  4  Şablonlar ve örnek sentetik veri seti (../sablonlar/), grafikler
Sabit tohum; tüm çıktılar ciktilar/ altında.
"""

import os

for _d in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):   # paralel işlemler BLAS iş parçacıklarıyla
    os.environ.setdefault(_d, "1")                                          # çekişmesin (sonucu değil, hızı etkiler)
import itertools
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
import deney    # noqa: E402
import uretec   # noqa: E402

CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
SABLON = KOK.parent / "sablonlar"
SABLON.mkdir(exist_ok=True)
TOHUM = 20261009
K = 60
TEKRAR = 300
IZ_N, IZ_R, IZ_SEC, IZ_PSE = (10, 16, 20, 30, 40), (15, 30, 50), ("amacli", "rastgele"), (0.0, 1.0, 2.0, 3.0)
T0 = time.time()
TESTLER = []
A = uretec.ansur()
REF = A["ref"]
(CIKTI / "ansur_referans.json").write_text(json.dumps(REF, ensure_ascii=False, indent=1), encoding="utf-8")


def log(*a):
    print(f"[{time.time() - T0:6.0f} sn]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'} ({deger})")


def tek_deney(N, R, secim, pse2, tohum, tau=1.0, naif=False, B=2000):
    rng = np.random.default_rng(tohum)
    h = uretec.hedefler(N, secim, rng, A, tau=tau)
    t = deney.ciftler_uret(h, R, K, rng)
    y = uretec.yanitlar(h, t, pse2, rng)
    s = deney.analiz(h, y, ref=REF, B=B, rng=rng)
    out = dict(N=N, R=R, secim=secim, pse2_gercek=pse2, tau=tau, pse2=s["pse2"], lo=s["pse2_lo"], hi=s["pse2_hi"],
               b_lo=s["b_lo"], red=bool(s["pse2_lo"] > 0 or s["pse2_hi"] < 0),
               kapsar=bool(s["pse2_lo"] <= pse2 <= s["pse2_hi"]))
    if naif:
        z = deney.yapi_indeksi(h, REF)
        n_ = deney.naif_analiz(h, y, z)
        out.update(naif_red=bool(n_["pse2_lo"] > 0 or n_["pse2_hi"] < 0))
    return out


def _calis(args):
    return tek_deney(*args)


def paralel(isler):
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        return pd.DataFrame(list(ex.map(_calis, isler, chunksize=8)))


if __name__ == "__main__":
    # 2. Güç ızgarası
    log("Güç ızgarası")
    isler = []
    for c, (N, R, sec, p) in enumerate(itertools.product(IZ_N, IZ_R, IZ_SEC, IZ_PSE)):
        isler += [(N, R, sec, p, TOHUM + 100_000 * c + k) for k in range(TEKRAR)]
    G = paralel(isler)
    GUC = G.groupby(["secim", "N", "R", "pse2_gercek"]).agg(guc=("red", "mean"), kapsama=("kapsar", "mean"),
                                                            ort_tahmin=("pse2", "mean"),
                                                            medyan_genislik=("hi", "median")).reset_index()
    gen = G.assign(g=G.hi - G.lo).groupby(["secim", "N", "R", "pse2_gercek"]).g.median().reset_index(drop=True)
    GUC["medyan_aralik_genisligi"] = gen.values
    GUC = GUC.drop(columns="medyan_genislik")
    GUC.to_csv(CIKTI / "guc.csv", index=False, float_format="%.3f")

    # 3. Önerilen tasarım (PLAN 5)
    a2 = GUC[(GUC.secim == "amacli") & (GUC.pse2_gercek == 2.0)]
    uygun_N = [n for n in IZ_N if (a2[a2.N == n].guc >= 0.8).any()]
    if uygun_N:
        N_on = min(uygun_N)
        R_on = int(a2[(a2.N == N_on) & (a2.guc >= 0.8)].R.min())
    else:
        N_on, R_on = max(IZ_N), max(IZ_R)
    oneri = dict(N=N_on, R=R_on, K=K, secim="amacli", bulundu=bool(uygun_N),
                 guc={str(p): float(GUC[(GUC.secim == "amacli") & (GUC.N == N_on) & (GUC.R == R_on) &
                                       (GUC.pse2_gercek == p)].guc.iloc[0]) for p in IZ_PSE})
    log("Öneri:", oneri)

    # D1 yansızlık
    d1 = paralel([(40, 200, "amacli", 2.0, TOHUM + 7_000_000 + k) for k in range(100)])
    m1 = float(d1.pse2.mean())
    test("D1", "Yansızlık: N = 40, R = 200, gerçek PSE₂ = 2 cm; 100 tekrarın ortalama tahmini",
         f"{m1:.3f} cm (SD {d1.pse2.std():.3f})", "2 ± 0.2 cm", abs(m1 - 2) <= 0.2)

    # D2 yanlış alarm, D5 naif analiz
    d2 = paralel([(N_on, R_on, "amacli", 0.0, TOHUM + 8_000_000 + k, 1.0, True) for k in range(500)])
    fp, fp_naif = float(d2.red.mean()), float(d2.naif_red.mean())
    test("D2", f"Yanlış alarm: önerilen tasarım (N = {N_on}, R = {R_on}), gerçek PSE₂ = 0, 500 tekrar",
         f"%{100 * fp:.1f}", "%2.5 - %8", 0.025 <= fp <= 0.08)

    # D3 kapsama
    d3 = paralel([(N_on, R_on, "amacli", 2.0, TOHUM + 9_000_000 + k) for k in range(500)])
    kap = float(d3.kapsar.mean())
    test("D3", f"Kapsama: önerilen tasarım, gerçek PSE₂ = 2 cm, 500 tekrar", f"%{100 * kap:.1f}", "%90 - %98",
         0.90 <= kap <= 0.98)

    # D4 tasarım dengesi
    rng = np.random.default_rng(TOHUM + 4)
    h4 = uretec.hedefler(N_on, "amacli", rng, A)
    t4 = deney.ciftler_uret(h4, 30, K, rng)
    say = pd.concat([t4.sol, t4.sag]).value_counts().reindex(h4.id, fill_value=0)
    oran_ms = float(say.max() / max(say.min(), 1))
    sol_pay = float(np.mean([s < g for s, g in zip(t4.sol, t4.sag)]))       # alfabetik küçük olan solda mı
    test("D4", "Tasarım dengesi: gösterilme en çok/en az oranı; sol-sağ dengesi (R = 30)",
         f"oran {oran_ms:.2f} (en az {say.min()}, en çok {say.max()}); solda %{100 * sol_pay:.1f}",
         "≤ 1.5; %50 ± 3", oran_ms <= 1.5 and abs(sol_pay - 0.5) <= 0.03)

    test("D5", "Gösterim: yanıtları bağımsız sayan naif analizin yanlış alarm oranı (D2 ile aynı veriler)",
         f"%{100 * fp_naif:.1f} (iki aşamalı analizde %{100 * fp:.1f})", "raporlanır (geçme ölçütü değil)", True)

    # Duyarlılık: τ (hedefe özgü görünüş farkı)
    log("Duyarlılık: τ")
    duy = []
    for tau in (0.5, 2.0):
        for p in (0.0, 2.0):
            d = paralel([(N_on, R_on, "amacli", p, TOHUM + 11_000_000 + int(tau * 10) * 1000 + int(p) * 100_000 + k, tau)
                         for k in range(300)])
            duy.append(dict(tau=tau, pse2_gercek=p, guc_ya_da_yanlis_alarm=float(d.red.mean()),
                            kapsama=float(d.kapsar.mean())))
    pd.DataFrame(duy).to_csv(CIKTI / "duyarlilik_tau.csv", index=False, float_format="%.3f")

    # 4. Şablonlar ve örnek veri
    pd.DataFrame(columns=["id", "boy_cm", "omuz_cm", "kilo_kg", "sac_yuksekligi_cm", "not"]).to_csv(
        SABLON / "hedefler_sablon.csv", index=False)
    pd.DataFrame(columns=["degerlendirici", "sira", "sol", "sag", "secilen"]).to_csv(
        SABLON / "yanitlar_sablon.csv", index=False)
    pd.DataFrame(columns=["degerlendirici", "yas", "beden_memnuniyeti_1_7", "hedefleri_taniyor_mu"]).to_csv(
        SABLON / "degerlendiriciler_sablon.csv", index=False)
    rng = np.random.default_rng(TOHUM + 99)
    ho = uretec.hedefler(N_on, "amacli", rng, A)
    to = deney.ciftler_uret(ho, R_on, K, rng)
    yo = uretec.yanitlar(ho, to, 2.0, rng)
    ho.drop(columns=["z_gercek", "t"]).to_csv(SABLON / "ornek_hedefler_SENTETIK.csv", index=False)
    yo.to_csv(SABLON / "ornek_yanitlar_SENTETIK.csv", index=False)
    so = deney.analiz(ho.drop(columns=["z_gercek", "t"]), yo, ref=REF, rng=np.random.default_rng(1))
    ornek = dict(pse2_gercek=2.0, pse2=so["pse2"], aralik=[so["pse2_lo"], so["pse2_hi"]], b=so["b"],
                 b_aralik=[so["b_lo"], so["b_hi"]])

    # Grafikler
    plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
    renk = {15: "#c9c8c3", 30: "#2a78d6", 50: "#0b0b0b"}
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.2), facecolor="#fcfcfb", sharey=True)
    for ax, p in zip(axs, (1.0, 2.0, 3.0)):
        for R in IZ_R:
            for sec, ls in (("amacli", "-"), ("rastgele", ":")):
                g = GUC[(GUC.secim == sec) & (GUC.R == R) & (GUC.pse2_gercek == p)]
                ax.plot(g.N, g.guc, ls, marker="o" if sec == "amacli" else None, color=renk[R], lw=1.8, ms=4,
                        label=f"{R} değerlendirici, {'amaçlı' if sec == 'amacli' else 'rastgele'} seçim")
        ax.axhline(0.8, color="#eb6834", lw=1, ls="--")
        ax.set_title(f"Gerçek etki: {p:.0f} cm", loc="left", fontsize=11)
        ax.set_xlabel("Fotoğraflanan kişi sayısı")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.3)
    axs[0].set_ylabel("Güç (etkiyi yakalama olasılığı)")
    axs[2].legend(frameon=False, fontsize=7.5, loc="lower right")
    fig.suptitle("Kaç kişi gerekiyor? (her nokta 300 sentetik deney; kesikli çizgi %80)", x=0.01, ha="left", fontsize=12)
    fig.tight_layout()
    fig.savefig(CIKTI / "guc.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.6), facecolor="#fcfcfb")
    zz = so["z"]
    sc = ax.scatter(ho.boy_cm, so["s"], c=zz, cmap="coolwarm", vmin=-2, vmax=2, s=45, edgecolor="#0b0b0b", lw=0.4)
    plt.colorbar(sc, ax=ax, label="Yapı indeksi (SD)")
    ax.set_xlabel("Ölçülen boy (cm)")
    ax.set_ylabel("Algılanan boy ölçeği (aşama 1)")
    ax.set_title(f"Örnek sentetik deney: gerçek etki 2 cm → tahmin {so['pse2']:.1f} cm "
                 f"({so['pse2_lo']:.1f} … {so['pse2_hi']:.1f})", loc="left", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(CIKTI / "ornek_analiz.png", dpi=150)
    plt.close(fig)

    pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
    (CIKTI / "ozet.json").write_text(json.dumps(dict(oneri=oneri, D1_ortalama=m1, D2_yanlis_alarm=fp,
                                                     D5_naif_yanlis_alarm=fp_naif, D3_kapsama=kap, ornek=ornek,
                                                     sure_sn=round(time.time() - T0)),
                                                ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(GUC[(GUC.secim == "amacli")].pivot_table(index=["pse2_gercek", "N"], columns="R", values="guc").round(2))
    print(json.dumps(oneri, ensure_ascii=False))
    print(pd.DataFrame(TESTLER)[["test", "deger", "sonuc"]].to_string(index=False))
