"""
Büyüme plağı dijital ikizi: tüm adımlar (PLAN.md). Tek komut:

    python calistir.py

Adımlar
  A  Tam kalibrasyon (Berkeley, boy + oturma boyu) + fiziksel tutarlılık kontrolleri
  B  5 katlı çapraz doğrulama: Ö1-Ö4
  C  Literatür senaryoları: Ö5a-f
  D  Türk nüfusuna uyarlama + 20.000'er kişilik sanal kohort: Ö6, Ö7
  E  Çalışma tasarımı (güç) simülasyonu
  F  Duyarlılık analizi
  G  Grafikler, test tablosu, ozet.json

Kalibrasyon sonuçları .onbellek/ altında saklanır (anahtar: model.py + veri.py içeriği);
kod değişmedikçe yeniden kullanılır. Sabit tohumlar: sonuçlar tekrar üretilebilir.
"""

import hashlib
import json
import pickle
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize

import model
from model import (BIREY, CINSIYETLER, Senaryo, bireysel_fit, fizik_kontrol, kalibre_et,
                   pb_boy, pb_fit, simule_et)
from olcum import PROTOKOLLER, VARSAYILAN, olc
from veri import YASLAR, berkeley, berkeley_matris, galton, turk_referans

KOK = Path(__file__).parent
CIKTI = KOK / "ciktilar"
ONB = KOK / ".onbellek"
CIKTI.mkdir(exist_ok=True)
ONB.mkdir(exist_ok=True)
OZET = {"testler": {}}
TESTLER = []

SURFACE, INK, INK2, GRID, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#c9c8c3"
SERI = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10.5,
    "axes.titlesize": 12, "axes.titleweight": "bold", "lines.linewidth": 2,
})
AD = {"erkek": "Erkek", "kiz": "Kız"}


def kaydet(fig, ad):
    fig.tight_layout()
    fig.savefig(CIKTI / ad, dpi=150)
    plt.close(fig)


def csv(ad, df):
    df.to_csv(CIKTI / ad, index=False, float_format="%.4f")


def kod_anahtari():
    h = hashlib.sha256()
    for f in ("model.py", "veri.py"):
        h.update((KOK / f).read_bytes())
    return h.hexdigest()[:16]


def onbellek(ad, fonk):
    yol = ONB / f"{ad}_{kod_anahtari()}.pkl"
    if yol.exists():
        return pickle.loads(yol.read_bytes())
    sonuc = fonk()
    yol.write_bytes(pickle.dumps(sonuc))
    return sonuc


def test_kaydet(kod, aciklama, olcut, deger, gecti, not_=""):
    TESTLER.append(dict(kod=kod, test=aciklama, olcut=olcut, deger=deger,
                        durum="GEÇTİ" if gecti else "KALDI", not_=not_))
    OZET["testler"][kod] = dict(deger=deger, gecti=bool(gecti))
    print(f"  {kod}: {'GEÇTİ' if gecti else 'KALDI'} | {deger}")


# ---------------------------------------------------------------------------
# A) Tam kalibrasyon
# ---------------------------------------------------------------------------

def a_kalibrasyon(d):
    print("A) Tam kalibrasyon...")
    mat = {c: berkeley_matris(d, c) for c in CINSIYETLER}
    veri = {c: (mat[c][1], mat[c][2]) for c in CINSIYETLER}
    kal, _ = onbellek("kalibrasyon_tam", lambda: kalibre_et(veri))

    satir, uyum = [], {}
    for c in CINSIYETLER:
        pop, ind = kal[c]
        B, G = veri[c]
        s = simule_et(ind, pop, B[:, 0], G[:, 0], t1=21.0, kayit_yaslari=YASLAR)
        m = ~np.isnan(B) & ~np.isnan(G)
        rb, rg = (s["bacak"].T - B)[m], (s["govde"].T - G)[m]
        rh = rb + rg
        # Kişi başı boy RMSE (9-21 yaş): mekanistik vs PB1
        kisi_m, kisi_pb = [], []
        for i, kid in enumerate(mat[c][0]):
            hm = s["boy"][:, i]
            gozlem = B[i] + G[i]
            ok = ~np.isnan(gozlem)
            kisi_m.append(np.sqrt(np.mean((hm[ok] - gozlem[ok]) ** 2)))
            g = d[(d.id == kid) & (d.yas >= 3)]
            p = pb_fit(g.yas, g.boy, c)
            kisi_pb.append(np.sqrt(np.mean((pb_boy(YASLAR[ok], *p) - gozlem[ok]) ** 2)))
        uyum[c] = dict(rmse_bacak=float(np.sqrt(np.mean(rb ** 2))), rmse_govde=float(np.sqrt(np.mean(rg ** 2))),
                       rmse_boy=float(np.sqrt(np.mean(rh ** 2))),
                       kisi_rmse_medyan_mekanistik=float(np.median(kisi_m)),
                       kisi_rmse_medyan_pb1=float(np.median(kisi_pb)),
                       parametre_sayisi_kisi_basi_mekanistik=4, parametre_sayisi_kisi_basi_pb1=5)
        fark = fizik_kontrol(ind, pop, B[:, 0], G[:, 0])
        uyum[c]["zaman_adimi_farki_cm"] = fark
        for k, v in pop.items():
            satir.append(dict(cinsiyet=c, parametre=k, deger=float(v)))
    csv("A_populasyon_parametreleri.csv", pd.DataFrame(satir))
    csv("A_uyum.csv", pd.DataFrame(uyum).T.reset_index().rename(columns={"index": "cinsiyet"}))
    bir = []
    for c in CINSIYETLER:
        pop, ind = kal[c]
        for i, kid in enumerate(mat[c][0]):
            bir.append(dict(cinsiyet=c, id=kid, **{k: float(ind[k][i]) for k in BIREY},
                            L0_bacak=float(veri[c][0][i, 0]), L0_govde=float(veri[c][1][i, 0])))
    csv("A_bireysel_parametreler.csv", pd.DataFrame(bir))
    OZET["A_uyum"] = uyum
    print("   uyum:", {c: round(uyum[c]["rmse_boy"], 3) for c in uyum}, "| S3 fiziksel kontroller geçti")
    return mat, veri, kal


# ---------------------------------------------------------------------------
# B) Çapraz doğrulama: Ö1-Ö4
# ---------------------------------------------------------------------------

def _boy(B, G, yas):
    j = int(np.where(np.isclose(YASLAR, yas))[0][0])
    return B[:, j] + G[:, j]


def b_capraz(d, mat, veri):
    print("B) 5 katlı çapraz doğrulama (uzun sürer)...")
    rng = np.random.default_rng(101)
    kat = {c: rng.permutation(len(mat[c][0])) % 5 for c in CINSIYETLER}
    tahmin = []
    kuyruk = []
    govde_satir = []
    son_olcum = d[d.yas > 18].groupby("id").agg(son_yas=("yas", "max"), son_boy=("boy", "last"))
    for k in range(5):
        egitim = {c: (veri[c][0][kat[c] != k], veri[c][1][kat[c] != k]) for c in CINSIYETLER}
        kal_k, _ = onbellek(f"kalibrasyon_kat{k}", lambda: kalibre_et(egitim))
        for c in CINSIYETLER:
            pop = kal_k[c][0]
            test = np.where(kat[c] == k)[0]
            ids = [mat[c][0][i] for i in test]
            B, G = veri[c][0][test], veri[c][1][test]
            Be, Ge = egitim[c]
            for kesme in (16.0, 17.0, 18.0):
                ind = onbellek(f"birey_kat{k}_{c}_{kesme}", lambda: bireysel_fit(B, G, pop, kesme, c))
                s = simule_et(ind, pop, B[:, 0], G[:, 0], t1=30.0)
                h = lambda a: s["boy"][int(round((a - 9.0) / 0.5))]
                if kesme < 18:
                    he = _boy(Be, Ge, kesme) - _boy(Be, Ge, kesme - 1)
                    re = _boy(Be, Ge, 18.0) - _boy(Be, Ge, kesme)
                    kat_kural = float(np.nansum(he * re) / np.nansum(he * he))
                    Hc, Hc1, H18 = _boy(B, G, kesme), _boy(B, G, kesme - 1), _boy(B, G, 18.0)
                    for i, kid in enumerate(ids):
                        g = d[(d.id == kid) & (d.yas >= 3) & (d.yas <= kesme + 1e-9)]
                        p = pb_fit(g.yas, g.boy, c)
                        for yontem, deger in (("K1 büyüme bitti", Hc[i]),
                                              ("K2 basit kural", Hc[i] + kat_kural * (Hc[i] - Hc1[i])),
                                              ("K3 PB1", float(pb_boy(18.0, *p))),
                                              ("M mekanistik", float(h(18.0)[i]))):
                            tahmin.append(dict(cinsiyet=c, id=kid, kesme=kesme, yontem=yontem,
                                               tahmin=float(deger), gercek=float(H18[i])))
                    if kesme == 16.0:
                        j16, j18 = 14, 18
                        for i, kid in enumerate(ids):
                            govde_satir.append(dict(
                                cinsiyet=c, id=kid,
                                tahmin_govde=float(s["govde"][j18, i] - s["govde"][j16, i]),
                                tahmin_boy=float(s["boy"][j18, i] - s["boy"][j16, i]),
                                gercek_govde=float(G[i, 18] - G[i, 14]),
                                gercek_boy=float(B[i, 18] + G[i, 18] - B[i, 14] - G[i, 14])))
                else:
                    H18 = _boy(B, G, 18.0)
                    for i, kid in enumerate(ids):
                        if kid in son_olcum.index:
                            sy, sb = son_olcum.loc[kid]
                            g = d[(d.id == kid) & (d.yas >= 3) & (d.yas <= 18.0)]
                            p = pb_fit(g.yas, g.boy, c)
                            kuyruk.append(dict(cinsiyet=c, id=kid, son_yas=sy,
                                               gozlenen=float(sb - H18[i]),
                                               mekanistik=float(h(sy)[i] - h(18.0)[i]),
                                               pb1=float(pb_boy(sy, *p) - pb_boy(18.0, *p))))
        print(f"   kat {k + 1}/5 tamam")
    t = pd.DataFrame(tahmin)
    t["mutlak_hata"] = (t.tahmin - t.gercek).abs()
    csv("B_capraz_tahminler.csv", t)
    ozet = t.groupby(["cinsiyet", "kesme", "yontem"]).mutlak_hata.agg(["count", "mean", "median"]).reset_index()
    csv("B_capraz_ozet.csv", ozet)
    ku = pd.DataFrame(kuyruk)
    csv("B_kuyruk.csv", ku)
    gv = pd.DataFrame(govde_satir)
    csv("B_govde_payi.csv", gv)

    for kod, kesme in (("Ö1", 16.0), ("Ö2", 17.0)):
        parcalar, gecti = [], True
        for c in CINSIYETLER:
            o = ozet[(ozet.cinsiyet == c) & (ozet.kesme == kesme)].set_index("yontem")["mean"]
            m, k2 = o["M mekanistik"], o["K2 basit kural"]
            gecti &= m <= k2 + 0.10
            parcalar.append(f"{c}: M {m:.2f}, K2 {k2:.2f}, K3 {o['K3 PB1']:.2f}, K1 {o['K1 büyüme bitti']:.2f}")
        test_kaydet(kod, f"Kesme {kesme:.0f} → 18 yaş boy tahmini (ortalama mutlak hata, cm)",
                    "M ≤ K2 + 0.10 (her iki cinsiyet)", " | ".join(parcalar), gecti)
    e = ku[ku.cinsiyet == "erkek"]
    fark = float(np.median(e.mekanistik) - np.median(e.gozlenen))
    test_kaydet("Ö3", f"18 sonrası kuyruk, erkek (n={len(e)})", "|medyan tahmin − medyan gözlem| ≤ 0.30",
                f"gözlenen medyan {np.median(e.gozlenen):.2f}, mekanistik {np.median(e.mekanistik):.2f}, "
                f"PB1 {np.median(e.pb1):.2f} cm (fark {fark:+.2f})", abs(fark) <= 0.30)
    ge = gv[gv.cinsiyet == "erkek"]
    pay_t = ge.tahmin_govde.sum() / ge.tahmin_boy.sum()
    pay_g = ge.gercek_govde.sum() / ge.gercek_boy.sum()
    test_kaydet("Ö4", "Erkek 16→18 büyümede gövde payı (kesme 16)", "|tahmin − gözlem| ≤ 0.15",
                f"gözlenen {pay_g:.2f}, tahmin {pay_t:.2f}", abs(pay_t - pay_g) <= 0.15)
    OZET["B"] = dict(ozet=ozet.to_dict("records"), govde_payi=dict(gozlenen=pay_g, tahmin=pay_t))
    return ozet


# ---------------------------------------------------------------------------
# C) Literatür senaryoları: Ö5
# ---------------------------------------------------------------------------

def _medyan_birey(kal, veri, c, Tp_kayma=0.0):
    pop, ind = kal[c]
    m = {k: np.array([np.median(ind[k])]) for k in BIREY}
    m["Tp"] = m["Tp"] + Tp_kayma
    return pop, m, np.array([np.median(veri[c][0][:, 0])]), np.array([np.median(veri[c][1][:, 0])])


def _son(pop, ind, L0b, L0g, sen=None, yaslar=(30.0,)):
    return simule_et(ind, pop, L0b, L0g, t1=30.0, senaryo=sen, kayit_yaslari=list(yaslar))["boy"]


def aralik(a, b, deger, disari=1.0):
    return lambda t: deger if a <= t < b else disari


def c_senaryolar(kal, veri):
    print("C) Literatür senaryoları...")
    sonuc = {}
    pop, ind, L0b, L0g = _medyan_birey(kal, veri, "erkek")
    # Ö5a östrojen yokluğu
    yas = (24.5, 25.5, 28.0, 30.0)
    norm = _son(pop, ind, L0b, L0g, yaslar=yas)[:, 0]
    yok = _son(pop, ind, L0b, L0g, Senaryo(a_rom=lambda t: 0.0), yas)[:, 0]
    popE, indE = kal["erkek"]
    hepsi28 = _son(popE, indE, veri["erkek"][0][:, 0], veri["erkek"][1][:, 0], yaslar=(28.0,))[0]
    esik = hepsi28.mean() + 2 * hepsi28.std()
    v25 = yok[1] - yok[0]
    test_kaydet("Ö5a", "Östrojen yokluğu (medyan erkek)", "25 yaşta hız ≥ 0.5 cm/yıl ve 28 yaşta boy ≥ ort + 2SD",
                f"hız {v25:.2f} cm/yıl, 28 yaş {yok[2]:.1f} cm (eşik {esik:.1f}, normal {norm[2]:.1f})",
                v25 >= 0.5 and yok[2] >= esik)
    sonuc["Ö5a"] = dict(v25=v25, h28=yok[2], esik=esik, normal28=norm[2])
    # Ö5b/c yakalama
    kayip = {}
    for c in CINSIYETLER:
        p_, i_, b_, g_ = _medyan_birey(kal, veri, c)
        for ad, (a, b) in (("cocukluk", (9, 11)), ("ergenlik", (13, 15))):
            yy = (float(b), 30.0)
            n0 = _son(p_, i_, b_, g_, yaslar=yy)[:, 0]
            n1 = _son(p_, i_, b_, g_, Senaryo(N=aralik(a, b, 0.6)), yy)[:, 0]
            kayip[(c, ad)] = (n0[0] - n1[0], n0[1] - n1[1])
    kb, kc = kayip[("erkek", "cocukluk")], kayip[("erkek", "ergenlik")]
    test_kaydet("Ö5b", "Yakalama: çocuklukta eksiklik (erkek, N=0.6, 9-11 yaş)", "nihai kayıp ≤ 11 yaş kaybının %25'i",
                f"11 yaşta kayıp {kb[0]:.2f}, nihai kayıp {kb[1]:.2f} cm (%{100 * kb[1] / kb[0]:.0f}); "
                f"kız: {kayip[('kiz', 'cocukluk')][0]:.2f} → {kayip[('kiz', 'cocukluk')][1]:.2f}",
                kb[1] <= 0.25 * kb[0])
    test_kaydet("Ö5c", "Aynı eksiklik ergenlikte (erkek, 13-15 yaş)", "nihai kayıp ≥ 2 × Ö5b nihai kaybı",
                f"15 yaşta kayıp {kc[0]:.2f}, nihai kayıp {kc[1]:.2f} cm (Ö5b: {kb[1]:.2f}, oran {kc[1] / max(kb[1], 1e-9):.1f}x)",
                kc[1] >= 2 * kb[1])
    sonuc["Ö5bc"] = {f"{c}_{a}": v for (c, a), v in kayip.items()}
    # Ö5d/e aromataz inhibitörü
    pg, ig, bg, gg = _medyan_birey(kal, veri, "erkek", Tp_kayma=2.0)
    taban = _son(pg, ig, bg, gg)[0, 0]
    ai = _son(pg, ig, bg, gg, Senaryo(a_rom=aralik(15.2, 16.2, 0.2)))[0, 0]
    test_kaydet("Ö5d", "Aromataz inhibitörü, geç olgunlaşan erkek (15.2-16.2 yaş)", "kazanç +0.5 ile +8 cm arası",
                f"kazanç {ai - taban:+.2f} cm", 0.5 <= ai - taban <= 8)
    t0 = _son(pop, ind, L0b, L0g)[0, 0]
    t1 = _son(pop, ind, L0b, L0g, Senaryo(a_rom=aralik(9, 11, 0.2)))[0, 0]
    test_kaydet("Ö5e", "Ergenlik öncesi aromataz inhibitörü (9-11 yaş)", "|kazanç| < 0.5 cm",
                f"kazanç {t1 - t0:+.2f} cm", abs(t1 - t0) < 0.5)
    sonuc["Ö5de"] = dict(gec_kazanc=ai - taban, erken_kazanc=t1 - t0)
    # Ö5f dış steroid, 66 gerçek eğri
    B, G = veri["erkek"]
    yy = (15.5, 16.5, 30.0)
    n0 = _son(popE, indE, B[:, 0], G[:, 0], yaslar=yy)
    n1 = _son(popE, indE, B[:, 0], G[:, 0], Senaryo(dE=aralik(16, 16.5, 0.5, 0.0)), yy)
    hiz = n0[1] - n0[0]
    secili = hiz > 1.0
    dus = np.mean((n1[2] - n0[2])[secili] < 0)
    test_kaydet("Ö5f", f"Dış steroid 16-16.5 yaş (hızı > 1 cm/yıl olan {secili.sum()} erkek)",
                "≥ %95'inde nihai boy düşer",
                f"%{100 * dus:.0f} düştü; medyan etki {np.median((n1[2] - n0[2])[secili]):+.2f} cm", dus >= 0.95)
    sonuc["Ö5f"] = dict(oran=dus, medyan=float(np.median((n1[2] - n0[2])[secili])))
    OZET["C"] = sonuc

    # Grafik: medyan erkek senaryoları
    yaslar = np.round(np.arange(9, 30.01, 0.25), 2)
    fig, ax = plt.subplots(figsize=(9, 5))
    eğriler = [("Normal", None, ind), ("Östrojen yok (Ö5a)", Senaryo(a_rom=lambda t: 0.0), ind),
               ("Eksiklik 13-15 yaş (Ö5c)", Senaryo(N=aralik(13, 15, 0.6)), ind),
               ("Steroid 16-16.5 yaş", Senaryo(dE=aralik(16, 16.5, 0.5, 0.0)), ind)]
    for j, (ad, sen, ii) in enumerate(eğriler):
        h = simule_et(ii, pop, L0b, L0g, t1=30.0, senaryo=sen, kayit_yaslari=yaslar)["boy"][:, 0]
        ax.plot(yaslar, h, color=SERI[j], label=ad)
    ax.set_xlim(9, 30)
    ax.set_xlabel("Yaş")
    ax.set_ylabel("Boy (cm)")
    ax.set_title("Medyan erkek: mekanistik senaryolar (model, kanıt seviyesi D)")
    ax.legend(frameon=False, loc="lower right")
    kaydet(fig, "4_senaryolar_medyan_erkek.png")


# ---------------------------------------------------------------------------
# D) Türk uyarlaması + sanal kohort: Ö6, Ö7
# ---------------------------------------------------------------------------

def _dagilim(kal, veri, c):
    pop, ind = kal[c]
    X = np.column_stack([np.log(ind["Gb"]), np.log(ind["Gg"]), ind["Tp"], np.log(ind["Ap"] + 0.5),
                         np.log(veri[c][0][:, 0]), np.log(veri[c][1][:, 0])])
    return X.mean(0), np.cov(X, rowvar=False)


def _ornekle(mu, kov, n, rng, dTp=0.0, olcek=1.0):
    X = rng.multivariate_normal(mu, kov, n)
    ind = dict(Gb=np.exp(X[:, 0]) * olcek, Gg=np.exp(X[:, 1]) * olcek, Tp=X[:, 2] + dTp,
               Ap=np.clip(np.exp(X[:, 3]) - 0.5, 0, None))
    return ind, np.exp(X[:, 4]) * olcek, np.exp(X[:, 5]) * olcek


def d_kohort(kal, veri):
    print("D) Türk uyarlaması ve sanal kohort...")
    ref = turk_referans()
    kohort, uyarlama = {}, {}
    ince = np.round(np.arange(9.0, 30.0001, 0.1), 2)
    for ci, c in enumerate(CINSIYETLER):
        pop = kal[c][0]
        mu, kov = _dagilim(kal, veri, c)
        r = ref[(ref.cinsiyet == c) & (ref.yas >= 9) & (ref.yas <= 18)]
        hedef_yas, hedef = r.yas.values, r.ortalama.values
        Z = np.random.default_rng(200 + ci)

        sabit = Z.standard_normal((4000, len(mu)))
        L = np.linalg.cholesky(kov + 1e-12 * np.eye(len(mu)))

        def uret(dTp, olcek, z):
            X = mu + z @ L.T
            ind = dict(Gb=np.exp(X[:, 0]) * olcek, Gg=np.exp(X[:, 1]) * olcek, Tp=X[:, 2] + dTp,
                       Ap=np.clip(np.exp(X[:, 3]) - 0.5, 0, None))
            return ind, np.exp(X[:, 4]) * olcek, np.exp(X[:, 5]) * olcek

        def amac(p):
            ind, b0, g0 = uret(p[0], np.exp(p[1]), sabit)
            h = simule_et(ind, pop, b0, g0, t1=18.0, kayit_yaslari=hedef_yas)["boy"].mean(1)
            return np.sqrt(np.mean((h - hedef) ** 2))

        o = minimize(amac, x0=[0.0, 0.0], method="Nelder-Mead", options=dict(xatol=1e-3, fatol=1e-4, maxiter=300))
        dTp, olcek = float(o.x[0]), float(np.exp(o.x[1]))
        rmse = float(o.fun)
        uyarlama[c] = dict(dTp=dTp, olcek=olcek, rmse=rmse)
        test_kaydet(f"Kalibrasyon-TR-{c}", f"Türk ortalama boy eğrisine uyum, {c} (9-18 yaş)", "RMSE ≤ 0.7 cm",
                    f"RMSE {rmse:.2f} cm, ΔT_p {dTp:+.2f} yıl, ölçek {olcek:.3f}", rmse <= 0.7,
                    "Kalibrasyon kabul ölçütü (doğrulama testi değil)")
        # 20.000 kişilik kohort (parçalar halinde)
        rng = np.random.default_rng(300 + ci)
        Hs = []
        for _ in range(4):
            z = rng.standard_normal((5000, len(mu)))
            ind, b0, g0 = uret(dTp, olcek, z)
            Hs.append(simule_et(ind, pop, b0, g0, t1=30.0, kayit_yaslari=ince)["boy"].astype(np.float32))
        kohort[c] = np.concatenate(Hs, axis=1)
    OZET["D_uyarlama"] = uyarlama
    return kohort, ince


def _H(kohort, ince, c, yas):
    """Kohort boyu, herhangi bir yaşta (doğrusal ara değerleme). yas: skaler ya da (n,)."""
    H = kohort[c]
    yas = np.broadcast_to(np.asarray(yas, float), (H.shape[1],))
    j = np.clip(((yas - 9.0) / 0.1).astype(int), 0, len(ince) - 2)
    w = (yas - ince[j]) / 0.1
    kol = np.arange(H.shape[1])
    return (1 - w) * H[j, kol] + w * H[j + 1, kol]


def d_testler(kohort, ince):
    sat, gecti_a, gecti_b, deger_a, deger_b = [], True, True, [], []
    kural_k = {"erkek": 1.0, "kiz": 0.9}
    for c in CINSIYETLER:
        for a in (16.0, 17.0):
            h0, h1, h2 = _H(kohort, ince, c, a - 2), _H(kohort, ince, c, a - 1), _H(kohort, ince, c, a)
            son = _H(kohort, ince, c, 30.0)
            g, gp, r = h2 - h1, h1 - h0, son - h2
            yav = g < gp
            k_yav = float(np.sum(g[yav] * r[yav]) / np.sum(g[yav] ** 2))
            k_hep = float(np.sum(g * r) / np.sum(g * g))
            hiz_n = int((~yav).sum())
            hata_hiz = float(np.median(r[~yav] - kural_k[c] * g[~yav])) if hiz_n else np.nan
            sat.append(dict(cinsiyet=c, yas=a, n_yavaslayan=int(yav.sum()), n_hizlanan=hiz_n,
                            katsayi_yavaslayan=k_yav, katsayi_hepsi=k_hep,
                            r_yavaslayan=float(np.corrcoef(g[yav], r[yav])[0, 1]),
                            hizlananlarda_kural_hatasi_medyan=hata_hiz,
                            kalan_medyan=float(np.median(r))))
            gecti_a &= 0.7 <= k_yav <= 1.3
            deger_a.append(f"{c} {a:.0f}: {k_yav:.2f}")
            if hiz_n >= 30:
                gecti_b &= hata_hiz > 0.5
                deger_b.append(f"{c} {a:.0f}: {hata_hiz:+.2f} (n={hiz_n})")
            else:
                deger_b.append(f"{c} {a:.0f}: değerlendirilemedi (n={hiz_n})")
    t = pd.DataFrame(sat)
    csv("D_kural_sanal_kohort.csv", t)
    test_kaydet("Ö6a", "Kural katsayısı, yavaşlayanlar, sanal Türk kohortu (gerçek boy)", "her hücrede [0.7, 1.3]",
                ", ".join(deger_a), gecti_a)
    test_kaydet("Ö6b", "Hâlâ hızlananlarda kural hatası medyanı (gerçek − tahmin)", "> +0.5 cm (n ≥ 30 hücrelerde)",
                ", ".join(deger_b), gecti_b)
    OZET["D_kural"] = t.to_dict("records")

    # Ö7: sanal kızlarda 6 aylık negatif artış oranı
    rng = np.random.default_rng(400)
    yaslar = [16.0, 16.5, 17.0, 17.5, 18.0]
    gercek = np.stack([_H(kohort, ince, "kiz", a) for a in yaslar])
    oran = {}
    for p in PROTOKOLLER:
        olculen = olc(gercek, rng, p)
        oran[p] = float(np.mean(np.diff(olculen, axis=0) < 0))
    test_kaydet("Ö7", "Sanal kızlarda 16.5-18 yaş 6 aylık negatif artış oranı (Berkeley: %14)",
                "en az bir protokolde %7-%25", ", ".join(f"{p} %{100 * v:.0f}" for p, v in oran.items()),
                any(0.07 <= v <= 0.25 for v in oran.values()))
    OZET["D_negatif_oran"] = oran

    # Grafik: kural, sanal erkekler 16 yaş
    rng = np.random.default_rng(5)
    c, a = "erkek", 16.0
    h0, h1, h2, son = (_H(kohort, ince, c, x) for x in (a - 2, a - 1, a, 30.0))
    g, gp, r = h2 - h1, h1 - h0, son - h2
    sec = rng.choice(len(g), 2500, replace=False)
    yav = (g < gp)[sec]
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    ax.scatter(g[sec][yav], r[sec][yav], s=7, color=SERI[0], alpha=0.5, label="yavaşlıyor (son yıl < önceki yıl)", lw=0)
    ax.scatter(g[sec][~yav], r[sec][~yav], s=9, color=SERI[1], alpha=0.8, label="hâlâ hızlanıyor", lw=0)
    lim = float(np.percentile(np.concatenate([g, r]), 99.5))
    ax.plot([0, lim], [0, lim], color=INK2, lw=1, ls="--")
    ax.text(lim * 0.68, lim * 0.6, "kalan = geçen yıl", color=INK2, fontsize=9)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim * 1.3)
    ax.set_xlabel("Son 12 ayda uzama (cm, gerçek boy)")
    ax.set_ylabel("16 yaşından sonra kalan boy (cm)")
    ax.set_title("Sanal Türk erkekleri, 16 yaş (model, kanıt seviyesi D)")
    ax.legend(frameon=False, loc="upper left", markerscale=2.5)
    kaydet(fig, "3_kural_sanal_kohort.png")


# ---------------------------------------------------------------------------
# E) Çalışma tasarımı
# ---------------------------------------------------------------------------

TASARIMLAR = {"uzun": (15.5, 16.5, 20.0), "kisa": (16.0, 17.0, 19.0)}


def _calisma(kohort, ince, c, tasarim, protokol, n, k_alt, rng, ayar=None, tekrar=300):
    lo, hi, bitis = TASARIMLAR[tasarim]
    N = kohort[c].shape[1]
    # Kohortun gerçek katsayısı (bu tasarımın yaş dağılımıyla)
    b_all = np.random.default_rng(7).uniform(lo, hi, N)
    g_all = _H(kohort, ince, c, b_all + 1) - _H(kohort, ince, c, b_all)
    r_all = _H(kohort, ince, c, bitis) - _H(kohort, ince, c, b_all + 1)
    k_pop = float(np.sum(g_all * r_all) / np.sum(g_all ** 2))
    f = 1.0 if k_alt is None else k_alt / k_pop
    basari, khat, genislik, mae = [], [], [], []
    for _ in range(tekrar):
        idx = rng.integers(0, N, n)
        b = rng.uniform(lo, hi, n)
        tam = rng.random(n) < 0.9 ** (bitis - b)
        idx, b = idx[tam], b[tam]
        if len(idx) < 5:
            basari.append(False)
            continue
        Hb = kohort[c][:, idx]
        sub = {c: Hb}
        h_b, h_a, h_s = (_H(sub, ince, c, x) for x in (b, b + 1, bitis))
        h_s = h_a + f * (h_s - h_a)
        m_b, m_a, m_s = (olc(x, rng, protokol, ayar) for x in (h_b, h_a, h_s))
        g, r = m_a - m_b, m_s - m_a
        k = float(np.sum(g * r) / np.sum(g * g))
        art = r - k * g
        se = np.sqrt(np.sum(art ** 2) / (len(g) - 1) / np.sum(g * g))
        tq = stats.t.ppf(0.975, len(g) - 1)
        alt, ust = k - tq * se, k + tq * se
        m = float(np.mean(np.abs(art)))
        basari.append(alt >= 0.7 and ust <= 1.3 and m < 1.0)
        khat.append(k)
        genislik.append(ust - alt)
        mae.append(m)
    return dict(basari=float(np.mean(basari)), k_medyan=float(np.median(khat)) if khat else np.nan,
                ga_genislik_medyan=float(np.median(genislik)) if genislik else np.nan,
                mae_medyan=float(np.median(mae)) if mae else np.nan, k_pop=k_pop)


def e_tasarim(kohort, ince):
    print("E) Çalışma tasarımı simülasyonu...")
    rng = np.random.default_rng(500)
    sat = []
    for c in CINSIYETLER:
        for tasarim in TASARIMLAR:
            for p in PROTOKOLLER:
                for n in (30, 60, 100, 200):
                    for gercek_ad, k_alt in (("kural doğru", None), ("gerçek k=0.5", 0.5), ("gerçek k=1.6", 1.6)):
                        r = _calisma(kohort, ince, c, tasarim, p, n, k_alt, rng)
                        sat.append(dict(cinsiyet=c, tasarim=tasarim, protokol=p, n=n, senaryo=gercek_ad, **r))
    t = pd.DataFrame(sat)
    csv("E_calisma_tasarimi.csv", t)
    OZET["E_tasarim"] = t.to_dict("records")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, c in zip(axes, CINSIYETLER):
        for j, p in enumerate(PROTOKOLLER):
            x = t[(t.cinsiyet == c) & (t.tasarim == "uzun") & (t.protokol == p) & (t.senaryo == "kural doğru")]
            ax.plot(x.n, x.basari, color=SERI[j], marker="o", ms=5, label=f"{p}: {PROTOKOLLER[p]['ad']}")
        y = t[(t.cinsiyet == c) & (t.tasarim == "uzun") & (t.protokol == "P1") & (t.senaryo != "kural doğru")]
        yp = y.groupby("n").basari.max()
        ax.plot(yp.index, yp.values, color=INK2, ls=":", lw=1.5, label="P1, kural yanlışken (yanlış pozitif)")
        ax.set_title(f"{AD[c]}: uzun tasarım (15.5-16.5 → 20 yaş)")
        ax.set_xlabel("Katılımcı sayısı (başlangıçta)")
        ax.set_ylim(-0.03, 1.03)
    axes[0].set_ylabel("Çalışmanın 'başarılı' çıkma olasılığı")
    axes[0].legend(frameon=False, loc="center right", fontsize=8.5)
    kaydet(fig, "5_calisma_tasarimi_guc.png")
    return t


# ---------------------------------------------------------------------------
# F) Duyarlılık
# ---------------------------------------------------------------------------

def f_duyarlilik(kal, veri, kohort, ince):
    print("F) Duyarlılık analizi...")
    sat = []
    rng0 = np.random.default_rng(600)
    yaslar = [16.0, 16.5, 17.0, 17.5, 18.0]
    gercek_kiz = np.stack([_H(kohort, ince, "kiz", a) for a in yaslar])
    for ad, aralik_ in (("D_max", (1.0, 2.0)), ("tau_c", (0.5, 4.0)), ("e_okuma", (0.2, 0.6)), ("b_gozlemci", (0.0, 0.5))):
        for deger in aralik_:
            ayar = {ad: deger}
            rng = np.random.default_rng(601)
            neg = {p: float(np.mean(np.diff(olc(gercek_kiz, rng, p, ayar), axis=0) < 0)) for p in PROTOKOLLER}
            g1 = _calisma(kohort, ince, "erkek", "uzun", "P1", 100, None, np.random.default_rng(602), ayar, tekrar=200)
            g2 = _calisma(kohort, ince, "erkek", "uzun", "P2", 100, None, np.random.default_rng(603), ayar, tekrar=200)
            sat.append(dict(parametre=ad, deger=deger, negatif_P1=neg["P1"], negatif_P2=neg["P2"], negatif_P3=neg["P3"],
                            guc_erkek_n100_P1=g1["basari"], guc_erkek_n100_P2=g2["basari"], katsayi_Ö6a_erkek16=np.nan))
    # Kaynaşma kapısı genişliği: gerçek boyları değiştirir, Ö6a katsayısını yeniden hesapla
    eski = model.KAPI
    try:
        pop = kal["erkek"][0]
        mu, kov = _dagilim(kal, veri, "erkek")
        uy = OZET["D_uyarlama"]["erkek"]
        for kapi in (0.05, 0.30):
            model.KAPI = kapi
            ind, b0, g0 = _ornekle(mu, kov, 5000, np.random.default_rng(610), uy["dTp"], uy["olcek"])
            H = simule_et(ind, pop, b0, g0, t1=30.0, kayit_yaslari=[14.0, 15.0, 16.0, 30.0])["boy"]
            g, gp, r = H[2] - H[1], H[1] - H[0], H[3] - H[2]
            yav = g < gp
            sat.append(dict(parametre="kaynasma_kapisi", deger=kapi, negatif_P1=np.nan, negatif_P2=np.nan,
                            negatif_P3=np.nan, guc_erkek_n100_P1=np.nan, guc_erkek_n100_P2=np.nan,
                            katsayi_Ö6a_erkek16=float(np.sum(g[yav] * r[yav]) / np.sum(g[yav] ** 2))))
    finally:
        model.KAPI = eski
    t = pd.DataFrame(sat)
    csv("F_duyarlilik.csv", t)
    OZET["F_duyarlilik"] = t.to_dict("records")


# ---------------------------------------------------------------------------
# Ek: Galton ile hedef boy varsayımı (v2 aracındaki 0.72 ve SD 5.0)
# ---------------------------------------------------------------------------

def ek_galton():
    g = galton()
    sat = []
    for c, isaret in (("erkek", 13), ("kiz", -13)):
        x = g[g.cinsiyet == c]
        t = (x.baba + x.anne + isaret) / 2
        tm = t - t.mean()
        egim = float((tm * (x.boy - x.boy.mean())).sum() / (tm ** 2).sum())
        art = x.boy - (x.boy.mean() + egim * tm)
        sat.append(dict(cinsiyet=c, n=len(x), egim=egim, artik_sd=float(art.std()),
                        korelasyon=float(np.corrcoef(t, x.boy)[0, 1])))
    t = pd.DataFrame(sat)
    csv("Ek_galton_hedef_boy.csv", t)
    OZET["Ek_galton"] = t.to_dict("records")


# ---------------------------------------------------------------------------

def grafik_uyum(d, mat, veri, kal):
    pop, ind = kal["erkek"]
    B, G = veri["erkek"]
    sira = np.argsort(ind["Tp"])
    secim = sira[[3, len(sira) // 3, 2 * len(sira) // 3, len(sira) - 4]]
    yas = np.round(np.arange(9, 25.01, 0.25), 2)
    s = simule_et(ind, pop, B[:, 0], G[:, 0], t1=25.0, kayit_yaslari=yas)
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.8), sharey=True)
    for ax, i in zip(axes, secim):
        ax.plot(yas, s["boy"][:, i], color=SERI[0], label="model: boy")
        ax.plot(yas, s["govde"][:, i] + 80, color=SERI[1], label="model: gövde (+80)")
        ok = ~np.isnan(B[i])
        ax.scatter(YASLAR[ok], (B[i] + G[i])[ok], s=10, color=INK2, zorder=3, label="ölçüm")
        ax.scatter(YASLAR[ok], G[i][ok] + 80, s=10, color=INK2, marker="x", zorder=3)
        ax.set_title(f"Kişi {mat['erkek'][0][i]} (T_p {ind['Tp'][i]:.1f})", fontsize=10.5)
        ax.set_xlabel("Yaş")
    axes[0].set_ylabel("cm")
    axes[0].legend(frameon=False, fontsize=8.5, loc="lower right")
    kaydet(fig, "1_kalibrasyon_ornekleri.png")


def grafik_capraz(ozet):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    yontemler = ["K1 büyüme bitti", "K2 basit kural", "K3 PB1", "M mekanistik"]
    for ax, c in zip(axes, CINSIYETLER):
        for j, kesme in enumerate((16.0, 17.0)):
            o = ozet[(ozet.cinsiyet == c) & (ozet.kesme == kesme)].set_index("yontem").reindex(yontemler)
            y = np.arange(len(yontemler)) + (j - 0.5) * 0.25
            ax.barh(y, o["mean"], height=0.23, color=SERI[j], label=f"kesme {kesme:.0f}")
            for yy, v in zip(y, o["mean"]):
                ax.text(v + 0.03, yy, f"{v:.2f}", va="center", fontsize=8.5, color=INK2)
        ax.set_yticks(np.arange(len(yontemler)))
        ax.set_yticklabels(yontemler)
        ax.set_title(f"{AD[c]}: 18 yaş boyu tahmini, örneklem dışı")
        ax.set_xlabel("Ortalama mutlak hata (cm)")
    axes[0].legend(frameon=False, loc="lower right")
    kaydet(fig, "2_capraz_dogrulama.png")


if __name__ == "__main__":
    d = berkeley()
    mat, veri, kal = a_kalibrasyon(d)
    grafik_uyum(d, mat, veri, kal)
    ozet = b_capraz(d, mat, veri)
    grafik_capraz(ozet)
    c_senaryolar(kal, veri)
    kohort, ince = d_kohort(kal, veri)
    d_testler(kohort, ince)
    e_tasarim(kohort, ince)
    f_duyarlilik(kal, veri, kohort, ince)
    ek_galton()
    pd.DataFrame(TESTLER).to_csv(CIKTI / "on_kayitli_testler.csv", index=False)
    with open(CIKTI / "ozet.json", "w", encoding="utf-8") as fh:
        json.dump(OZET, fh, ensure_ascii=False, indent=1, default=float)
    print("\nÖN KAYITLI TESTLER")
    for t in TESTLER:
        print(f"  {t['kod']:<20} {t['durum']:<6} {t['deger']}")
