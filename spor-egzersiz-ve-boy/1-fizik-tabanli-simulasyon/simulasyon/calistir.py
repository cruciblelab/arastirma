"""
Egzersiz ve boy simülasyonu (PLAN.md). Tek komut:

    python calistir.py

Adımlar
  T7  Tutarlılık: sürüm 3 modeliyle eşdeğerlik + zaman adımı yakınsaması
  A   Plak mekaniği: P1-P9 programları (16-21 yaş), üç ayar; T5 karar kuralı; T4 jimnastik
  B   Disk sünmesi: kalibrasyon, T1-T3, "boy uzatma rutini" günü
  C   Duruş geometrisi: T6
  D   Seçilim
  E   Duyarlılık
Sabit tohumlar; tüm çıktılar ciktilar/ altında.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import disk
import durus
import plak

KOK = Path(__file__).parent
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
OZET, TESTLER = {}, []
CINS = ("erkek", "kiz")
AD = {"erkek": "Erkek", "kiz": "Kız"}
N_KOHORT = 5000

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERI = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10.5,
    "axes.titlesize": 12, "axes.titleweight": "bold", "lines.linewidth": 2,
})


def kaydet(fig, ad):
    fig.tight_layout()
    fig.savefig(CIKTI / ad, dpi=150)
    plt.close(fig)


def csv(ad, df):
    df.to_csv(CIKTI / ad, index=False, float_format="%.4f")


def test(kod, aciklama, olcut, deger, gecti, not_=""):
    TESTLER.append(dict(kod=kod, test=aciklama, olcut=olcut, deger=deger,
                        durum="GEÇTİ" if gecti else "KALDI", not_=not_))
    OZET.setdefault("testler", {})[kod] = dict(deger=deger, gecti=bool(gecti))
    print(f"  {kod}: {'GEÇTİ' if gecti else 'KALDI'} | {deger}")


# ---------------------------------------------------------------------------
# T7 tutarlılık
# ---------------------------------------------------------------------------

def t7():
    print("T7) Tutarlılık...")
    sys.path.insert(0, str(plak.V3))
    import model as v3model  # sürüm 3 modeli
    farklar, yak = [], []
    for c in CINS:
        pop, ind, b0, g0 = plak.kohort(c, 300, np.random.default_rng(1))
        a = plak.simule_et(ind, pop, b0, g0)["boy"][0]
        b = v3model.simule_et(ind, pop, b0, g0, t1=30.0, kayit_yaslari=[30.0])["boy"][0]
        farklar.append(float(np.max(np.abs(a - b))))
        p = (16.0, 21.0, 0.9, 1.05)
        d1 = plak.simule_et(ind, pop, b0, g0, program=p, kontrol=True)["boy"][0]
        d2 = plak.simule_et(ind, pop, b0, g0, program=p, dt=plak.DT / 2, kontrol=True)["boy"][0]
        yak.append(float(np.max(np.abs(d1 - d2))))
    test("T7", "Sürüm 3 modeliyle eşdeğerlik ve zaman adımı yakınsaması",
         "eşdeğerlik farkı < 0.01 cm ve yakınsama farkı < 0.05 cm",
         f"eşdeğerlik {max(farklar):.5f} cm, yakınsama {max(yak):.5f} cm",
         max(farklar) < 0.01 and max(yak) < 0.05)


# ---------------------------------------------------------------------------
# A) Plak mekaniği
# ---------------------------------------------------------------------------

def _etki(c, program_tanimi, beta, eta, bas, bit, yuk=None, n=N_KOHORT, tohum=10):
    pop, ind, b0, g0 = plak.kohort(c, n, np.random.default_rng(tohum + (0 if c == "erkek" else 1)))
    taban = plak.simule_et(ind, pop, b0, g0, kayit=(16.0, 30.0))
    Db, Dg = plak.gunluk_fark(program_tanimi, yuk or plak.YUK)
    mb, mg = plak.carpan(Db, beta, eta), plak.carpan(Dg, beta, eta)
    sonuc = plak.simule_et(ind, pop, b0, g0, program=(bas, bit, mb, mg), kayit=(16.0, 30.0))
    fark = sonuc["boy"][1] - taban["boy"][1]
    return fark, dict(Db=Db, Dg=Dg, Mb=mb, Mg=mg,
                      kalan_boy_16=float(np.median(taban["boy"][1] - taban["boy"][0])),
                      kalan_bacak_16=float(np.median(taban["bacak"][1] - taban["bacak"][0])),
                      kalan_govde_16=float(np.median(taban["govde"][1] - taban["govde"][0])))


def a_plak():
    print("A) Plak mekaniği...")
    sat = []
    for c in CINS:
        for ad, tanim in plak.PROGRAMLAR.items():
            for ayar, (beta, eta) in plak.AYARLAR.items():
                fark, bilgi = _etki(c, tanim, beta, eta, 16.0, 21.0)
                sat.append(dict(cinsiyet=c, program=ad, ayar=ayar, medyan_mm=10 * float(np.median(fark)),
                                p5_mm=10 * float(np.percentile(fark, 5)), p95_mm=10 * float(np.percentile(fark, 95)),
                                **bilgi))
    t = pd.DataFrame(sat)
    csv("A_plak_programlar.csv", t)
    OZET["A_plak"] = t.to_dict("records")
    ust = t[(t.ayar == "üst sınır") & (~t.program.str.startswith("P9"))]
    en = ust.loc[ust.medyan_mm.abs().idxmax()]
    test("T5", "Karar: üst sınır ayarında P1-P8, 16-21 yaş (16 hücre)", "tüm hücrelerde |medyan| < 2 mm (0.2 cm)",
         f"en büyük |medyan|: {en.medyan_mm:+.2f} mm ({en.cinsiyet}, {en.program})",
         bool((ust.medyan_mm.abs() < 2.0).all()))

    # T4 jimnastik profili 9-16
    sat4, gecti = [], True
    for c in CINS:
        for ayar, (beta, eta) in plak.AYARLAR.items():
            fark, bilgi = _etki(c, plak.PROGRAMLAR["P9 Aşırı yük"], beta, eta, 9.0, 16.0)
            sat4.append(dict(cinsiyet=c, ayar=ayar, medyan_cm=float(np.median(fark)),
                             p5_cm=float(np.percentile(fark, 5)), Mb=bilgi["Mb"], Mg=bilgi["Mg"]))
            if ayar == "gerçekçi":
                gecti &= float(np.median(fark)) > -1.0
    t4 = pd.DataFrame(sat4)
    csv("A_jimnastik_profili.csv", t4)
    OZET["A_jimnastik"] = t4.to_dict("records")
    g = t4[t4.ayar == "gerçekçi"].set_index("cinsiyet").medyan_cm
    u = t4[t4.ayar == "üst sınır"].set_index("cinsiyet").medyan_cm
    test("T4", "Jimnastik profili 9-16 yaş, gerçekçi ayar", "her iki cinsiyette medyan kayıp < 1.0 cm",
         f"gerçekçi: erkek {g['erkek']:+.2f}, kız {g['kiz']:+.2f} cm | üst sınır: erkek {u['erkek']:+.2f}, kız {u['kiz']:+.2f} cm",
         gecti)

    # Grafik
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    prog = list(plak.PROGRAMLAR)
    for ax, c in zip(axes, CINS):
        for j, ayar in enumerate(["üst sınır", "gerçekçi"]):
            x = t[(t.cinsiyet == c) & (t.ayar == ayar)].set_index("program").reindex(prog)
            y = np.arange(len(prog)) + (0.18 if j == 0 else -0.18)
            ax.errorbar(x.medyan_mm, y, xerr=[x.medyan_mm - x.p5_mm, x.p95_mm - x.medyan_mm], fmt="o",
                        color=SERI[j], ms=6, capsize=0, lw=1.5, label=f"{ayar} (medyan, %5-%95)")
        ax.axvline(0, color=INK2, lw=1)
        ax.axvspan(-2, 2, color=GRID, alpha=0.5, lw=0)
        ax.set_yticks(np.arange(len(prog)))
        ax.set_yticklabels(prog)
        ax.invert_yaxis()
        ax.set_xlabel("Nihai boya etki (mm), 16-21 yaş arası program")
        ax.set_title(f"{AD[c]}: plak mekaniği yoluyla kalıcı etki")
    axes[0].legend(frameon=False, loc="lower left", fontsize=9)
    axes[1].text(0.02, 0.02, "gri bant: ±2 mm (T5 eşiği)", transform=axes[1].transAxes, color=INK2, fontsize=8.5)
    kaydet(fig, "1_plak_programlar.png")
    return t


# ---------------------------------------------------------------------------
# B) Disk sünmesi
# ---------------------------------------------------------------------------

def b_disk(tau_c=1.5, tau_r=2.5, kaydet_grafik=True):
    k = disk.kalibre_k(tau_c, tau_r)
    y0, genlik = disk.periyodik_sabah(k, tau_c, tau_r)
    sonuc = dict(k=k, sabah=y0, genlik=genlik)
    # T1: uyanınca 1 saat ayakta, sonra 20 dk sırtüstü
    t, y = disk.entegre(y0, [(1.0, 0.50), (20 / 60, 0.10)], k, tau_c, tau_r)
    kayip = y0 - y[np.searchsorted(t, 1.0 - 1e-9)]
    geri = y[-1] - y[np.searchsorted(t, 1.0 - 1e-9)]
    sonuc["T1"] = geri / kayip
    # T2: normal günün 4. saatinde 15 dk traksiyon
    g = disk.gun_dilimleri()
    t, y = disk.entegre(y0, [(1.0, 0.50), (3.0, 0.46), (0.25, disk.BASINC["traksiyon"])], k, tau_c, tau_r)
    sonuc["T2"] = y[-1] - y[np.searchsorted(t, 4.0 - 1e-9)]
    # T3: günün 2. saatinde 33 dk koşu
    t, y = disk.entegre(y0, [(1.0, 0.50), (1.0, 0.46), (0.55, disk.BASINC["kosu"])], k, tau_c, tau_r)
    sonuc["T3"] = y[np.searchsorted(t, 2.0 - 1e-9)] - y[-1]
    # Boy uzatma rutini: günün 12. saatinde 40 dk (10 asılma, 10 ters asılma, 20 esneme-yerde)
    rutin = [(1.0, 0.50), (7.0, 0.46), (4.0, 0.59),
             (10 / 60, disk.BASINC["asilma"]), (10 / 60, disk.BASINC["ters_asilma"]), (20 / 60, 0.10),
             (16 - 12 - 40 / 60, 0.59), (8.0, 0.10)]
    normal = [(1.0, 0.50), (7.0, 0.46), (4.0, 0.59), (40 / 60, 0.46), (16 - 12 - 40 / 60, 0.59), (8.0, 0.10)]
    tr, yr = disk.entegre(y0, rutin, k, tau_c, tau_r)
    tn, yn = disk.entegre(y0, normal, k, tau_c, tau_r)
    def at(tt, yy, s):
        return yy[np.searchsorted(tt, s - 1e-9)]
    bitis = 12 + 40 / 60
    sonuc["rutin_hemen"] = at(tr, yr, bitis) - at(tn, yn, bitis)
    sonuc["rutin_1saat"] = at(tr, yr, bitis + 1) - at(tn, yn, bitis + 1)
    sonuc["rutin_2saat"] = at(tr, yr, bitis + 2) - at(tn, yn, bitis + 2)
    sonuc["rutin_ertesi_sabah"] = yr[-1] - yn[-1]
    if kaydet_grafik:
        fig, ax = plt.subplots(figsize=(10, 4.6))
        ax.plot(tn, yn, color=SERI[0], label="normal gün")
        ax.plot(tr, yr, color=SERI[1], label="12. saatte 40 dk 'boy uzatma rutini'")
        ax.axvspan(12, bitis, color=GRID, alpha=0.6, lw=0)
        ax.annotate(f"rutin bitince +{sonuc['rutin_hemen']:.1f} mm\n2 saat sonra +{sonuc['rutin_2saat']:.1f} mm\n"
                    f"ertesi sabah {sonuc['rutin_ertesi_sabah']:+.2f} mm", (bitis, at(tr, yr, bitis)),
                    xytext=(25, 20), textcoords="offset points", color=INK2, fontsize=9)
        ax.set_xticks(range(0, 25, 2))
        ax.set_xticklabels([f"{h}" for h in range(0, 25, 2)])
        ax.set_xlabel("Uyanıştan beri saat (16-24: uyku)")
        ax.set_ylabel("Omurga boyu, sabaha göre (mm)")
        ax.set_title("Disk sünmesi: asılma ve esnemenin etkisi geçici (model, kalibre: günlük 14.4 mm)")
        ax.legend(frameon=False, loc="lower left")
        kaydet(fig, "2_disk_gunluk.png")
    return sonuc


def b_testler():
    print("B) Disk sünmesi...")
    s = b_disk()
    OZET["B_disk"] = s
    test("T1", "Disk: 1 saat ayakta sonrası 20 dk sırtüstü geri kazanım", "< kaybın %30'u",
         f"%{100 * s['T1']:.0f} (k = {s['k']:.1f} mm/MPa)", s["T1"] < 0.30)
    test("T2", "Disk: 15 dk traksiyon (0.03 MPa) kazancı", "1-8 mm (literatür 3.2-5.4)",
         f"{s['T2']:.2f} mm", 1 <= s["T2"] <= 8)
    test("T3", "Disk: 33 dk koşuda kısalma", "1-6 mm (literatür 3.25)", f"{s['T3']:.2f} mm", 1 <= s["T3"] <= 6)
    print(f"   rutin: hemen +{s['rutin_hemen']:.2f}, 1 saat +{s['rutin_1saat']:.2f}, 2 saat +{s['rutin_2saat']:.2f}, "
          f"ertesi sabah {s['rutin_ertesi_sabah']:+.3f} mm")


# ---------------------------------------------------------------------------
# C) Duruş
# ---------------------------------------------------------------------------

def c_durus(L_oran=durus.L_T_ORAN, kayit=True):
    rng = np.random.default_rng(30)
    n = 100_000
    teta = rng.normal(*durus.KIFOZ_ERKEK_16, n)
    teta = np.clip(teta, 5, None)
    boy = rng.normal(176.0, 6.24, n)
    sat = []
    for ad, oran in durus.DUZELME.items():
        g = durus.kazanc(boy, teta, oran, L_oran)
        kif = teta >= 45
        sat.append(dict(duzelme=ad, herkes_medyan_cm=float(np.median(g)), kifotik_medyan_cm=float(np.median(g[kif])),
                        kifotik_p95_cm=float(np.percentile(g[kif], 95)), kifotik_oran=float(kif.mean())))
    for ek in (10, 20):
        g = durus.dikey(L_oran * boy, teta + ek) - durus.dikey(L_oran * boy, teta)
        sat.append(dict(duzelme=f"kambur duruş: +{ek}° (görünür boy)", herkes_medyan_cm=float(np.median(g)),
                        kifotik_medyan_cm=np.nan, kifotik_p95_cm=np.nan, kifotik_oran=np.nan))
    t = pd.DataFrame(sat)
    if kayit:
        csv("C_durus.csv", t)
        OZET["C_durus"] = t.to_dict("records")
        r = t.set_index("duzelme")
        kap = r.loc["kapsamlı program (−%26)"]
        test("T6", "Karar: kifotik gençlerde (θ ≥ 45°) kapsamlı programın ölçülen boya katkısı",
             "medyan < 1.0 cm ise 'duruşla 1-2 cm' ifadesi ölçülen boy için desteklenmiyor",
             f"medyan {kap.kifotik_medyan_cm:.2f} cm (%95'lik {kap.kifotik_p95_cm:.2f}); herkes için {kap.herkes_medyan_cm:.2f} cm",
             kap.kifotik_medyan_cm < 1.0)
        # Grafik
        th = np.linspace(20, 70, 200)
        fig, ax = plt.subplots(figsize=(8.5, 4.6))
        for j, (ad, oran) in enumerate(durus.DUZELME.items()):
            ax.plot(th, 10 * durus.kazanc(176.0, th, oran, L_oran), color=SERI[j], label=ad)
        ax.axvspan(durus.KIFOZ_ERKEK_16[0] - durus.KIFOZ_ERKEK_16[1], durus.KIFOZ_ERKEK_16[0] + durus.KIFOZ_ERKEK_16[1],
                   color=GRID, alpha=0.6, lw=0)
        ax.text(durus.KIFOZ_ERKEK_16[0], ax.get_ylim()[1] * 0.92 if ax.get_ylim()[1] > 0 else 1, "16 yaş\nort ± SD",
                ha="center", color=INK2, fontsize=8.5, va="top")
        ax.axvline(45, color=INK2, lw=1, ls=":")
        ax.set_xlabel("Başlangıç kifoz açısı (derece)")
        ax.set_ylabel("Ölçülen boya katkı (mm)")
        ax.set_title("Duruş düzeltmesinin geometrik etkisi (176 cm, L_T = 0.16 × boy)")
        ax.legend(frameon=False, loc="upper left")
        kaydet(fig, "3_durus_geometrisi.png")
    return t


# ---------------------------------------------------------------------------
# D) Seçilim
# ---------------------------------------------------------------------------

def d_secilim():
    mu, sd = 176.0, 6.24
    sat = []
    for p in (0.10, 0.05, 0.01):
        z = stats.norm.ppf(1 - p)
        ort = mu + sd * stats.norm.pdf(z) / p
        sat.append(dict(en_uzun_yuzde=100 * p, esik_cm=mu + sd * z, secilenlerin_ortalamasi_cm=ort, fark_cm=ort - mu))
    t = pd.DataFrame(sat)
    csv("D_secilim.csv", t)
    OZET["D_secilim"] = t.to_dict("records")


# ---------------------------------------------------------------------------
# E) Duyarlılık
# ---------------------------------------------------------------------------

def e_duyarlilik():
    print("E) Duyarlılık...")
    sat = []
    prog = {k: v for k, v in plak.PROGRAMLAR.items() if not k.startswith("P9")}
    def en_buyuk(beta, eta, yuk=None):
        m = []
        for ad, tanim in prog.items():
            f, _ = _etki("erkek", tanim, beta, eta, 16.0, 21.0, yuk=yuk, n=2000)
            m.append((abs(10 * np.median(f)), ad, 10 * np.median(f)))
        return max(m)
    for ad, beta, eta, yuk in (("taban (üst sınır)", 0.4, 1.0, None), ("β = 0.2", 0.2, 1.0, None),
                               ("η = 0.5", 0.4, 0.5, None), ("η = 0.25", 0.4, 0.25, None),
                               ("koşu/basketbol bacak L = 5", 0.4, 1.0, {**plak.YUK, "kosu": (1.3, 5.0), "basketbol": (1.5, 5.0)}),
                               ("koşu/basketbol bacak L = 2", 0.4, 1.0, {**plak.YUK, "kosu": (1.3, 2.0), "basketbol": (1.5, 2.0)})):
        _, prog_ad, deger = en_buyuk(beta, eta, yuk)
        sat.append(dict(katman="A plak", degisiklik=ad, cikti="T5 en büyük |medyan| (erkek, mm)", deger=deger, not_=prog_ad))
    for tc, tr in ((0.5, 2.5), (3.0, 2.5), (1.5, 1.0), (1.5, 4.0)):
        s = b_disk(tc, tr, kaydet_grafik=False)
        sat.append(dict(katman="B disk", degisiklik=f"τ_c={tc}, τ_r={tr}", cikti="T1 / T2 mm / T3 mm / rutin ertesi sabah mm",
                        deger=np.nan, not_=f"%{100 * s['T1']:.0f} / {s['T2']:.2f} / {s['T3']:.2f} / {s['rutin_ertesi_sabah']:+.3f}"))
    for L in (0.14, 0.18):
        t = c_durus(L, kayit=False).set_index("duzelme")
        sat.append(dict(katman="C duruş", degisiklik=f"L_T = {L} × boy", cikti="T6 kifotik medyan (cm)",
                        deger=float(t.loc["kapsamlı program (−%26)", "kifotik_medyan_cm"]), not_=""))
    t = pd.DataFrame(sat)
    csv("E_duyarlilik.csv", t)
    OZET["E_duyarlilik"] = t.to_dict("records")
    print(t.to_string(index=False))


if __name__ == "__main__":
    t7()
    a_plak()
    b_testler()
    c_durus()
    d_secilim()
    e_duyarlilik()
    pd.DataFrame(TESTLER).to_csv(CIKTI / "on_kayitli_testler.csv", index=False)
    with open(CIKTI / "ozet.json", "w", encoding="utf-8") as fh:
        json.dump(OZET, fh, ensure_ascii=False, indent=1, default=float)
    print("\nÖN KAYITLI TESTLER")
    for t in TESTLER:
        print(f"  {t['kod']:<4} {t['durum']:<6} {t['deger']}")
