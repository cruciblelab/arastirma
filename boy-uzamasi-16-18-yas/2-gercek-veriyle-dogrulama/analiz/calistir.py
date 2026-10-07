"""
v2 analizlerinin tamamı. Tek komut:

    python calistir.py

İlk çalıştırmada Berkeley verisini CRAN'dan indirir (SHA-256 doğrulamalı).
Tüm tablolar ve grafikler ciktilar/ altına, özet sayılar ciktilar/ozet.json'a yazılır.
Sabit tohum: aynı girdiyle her seferinde aynı sonuç.

Analizler
  A  PB1'i her bireye fit et, uyum kalitesi ve parametre dağılımı
  B  Ampirik kalan boy: 16->18, 17->18, 18 sonrası (model YOK, doğrudan veri)
  C  Hız kuralı: son 12 aydaki uzama, kalan boyu ne kadar iyi tahmin ediyor?
  D  Ölçüm hatası: hız hesabını ne kadar bozuyor?
  E  Kişisel tahmin aracının birini-dışarıda-bırak (LOO) doğrulaması
  F  Dinamik senaryolar, 66 gerçek erkek eğrisi üzerinde (kanıt seviyesi D)
"""

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from model import (DinamikAyar, Donem, Onsel, boy_par, hiz_par, pb_boy, pb_fit,
                   pb_hiz, phv, simule_et)
from veri import berkeley

CIKTI = Path(__file__).parent / "ciktilar"
CIKTI.mkdir(exist_ok=True)
RNG = np.random.default_rng(20261007)
OZET = {}

SURFACE, INK, INK2, GRID, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#c9c8c3"
SERI = ["#2a78d6", "#eb6834", "#1baf7a"]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10.5,
    "axes.titlesize": 12, "axes.titleweight": "bold", "lines.linewidth": 2,
})
CINS_AD = {"erkek": "Erkek", "kiz": "Kız"}


def kaydet(fig, ad):
    fig.tight_layout()
    fig.savefig(CIKTI / ad, dpi=150)
    plt.close(fig)


def csv_yaz(ad, df):
    df.to_csv(CIKTI / ad, index=False, float_format="%.3f", quoting=csv.QUOTE_MINIMAL)


def yuzdelik(x, q=(10, 50, 90)):
    return [float(v) for v in np.percentile(x, q)]


# ---------------------------------------------------------------------------
# A) PB1 fit
# ---------------------------------------------------------------------------

def a_fit(d):
    satir = []
    for (i, c), g in d.groupby(["id", "cinsiyet"]):
        p, rmse = pb_fit(g.yas, g.boy, c)
        pa, pv = phv(p)
        satir.append(dict(id=i, cinsiyet=c, h1=p[0], ht=p[1], s0=p[2], s1=p[3], th=p[4],
                          rmse=rmse, phv_yas=pa, phv_hiz=pv,
                          kuyruk18=float(p[0] - pb_boy(18.0, *p))))
    f = pd.DataFrame(satir)
    # Önsel için güvenilmez fitleri ayıkla: zirve hızı yaşı veri penceresinin dışında
    f["onsele_dahil"] = (f.phv_yas > 9.0) & (f.phv_yas < 17.0) & (f.rmse < 1.1)
    csv_yaz("A_pb1_parametreleri.csv", f)
    oz = {}
    for c, g in f.groupby("cinsiyet"):
        oz[c] = dict(n=int(len(g)), onsele_dahil=int(g.onsele_dahil.sum()),
                     rmse_medyan=float(g.rmse.median()), phv_yas_ort=float(g.phv_yas.mean()),
                     phv_yas_sd=float(g.phv_yas.std()), phv_hiz_ort=float(g.phv_hiz.mean()),
                     eriskin_ort=float(g.h1.mean()), eriskin_sd=float(g.h1.std()),
                     s1_ort=float(g.s1.mean()), theta_sd=float(g.th.std()))
    OZET["A_fit"] = oz
    return f


# ---------------------------------------------------------------------------
# B) Ampirik kalan boy (model yok)
# ---------------------------------------------------------------------------

def b_ampirik(d, f):
    w = d.pivot_table(index=["id", "cinsiyet"], columns="yas", values="boy").reset_index()
    satir, oz = [], {}
    for c in ("erkek", "kiz"):
        x = w[w.cinsiyet == c]
        oz[c] = {}
        for bas in (16.0, 16.5, 17.0, 17.5):
            g = (x[18.0] - x[bas]).dropna()
            p10, p50, p90 = yuzdelik(g)
            satir.append([c, f"{bas}->18", len(g), g.mean(), p10, p50, p90, g.max(), (g > 2).mean()])
            oz[c][f"{bas}->18"] = dict(n=int(len(g)), ort=float(g.mean()), p10=p10, medyan=p50, p90=p90,
                                       maks=float(g.max()), p_gt2=float((g > 2).mean()))
        # 18 sonrası: 18'den sonra en az bir ölçümü olanlar
        son = d[(d.cinsiyet == c) & (d.yas > 18)].groupby("id").agg(son_yas=("yas", "max"), son_boy=("boy", "last"))
        h18 = x.set_index("id")[18.0]
        son = son.join(h18.rename("h18"))
        g = (son.son_boy - son.h18).dropna()
        if len(g):
            p10, p50, p90 = yuzdelik(g)
            satir.append([c, f"18->son ölçüm (ort {son.son_yas.mean():.1f} yaş)", len(g), g.mean(), p10, p50, p90,
                          g.max(), (g > 2).mean()])
            oz[c]["18->son"] = dict(n=int(len(g)), son_yas_ort=float(son.son_yas.mean()), ort=float(g.mean()),
                                    medyan=p50, p90=p90, maks=float(g.max()))
            # PB1 kuyruğu ile karşılaştır (model 18 sonrasını eksik mi tahmin ediyor?)
            ff = f.set_index("id").loc[g.index]
            model_pencere = [float(pb_boy(sy, *ff.loc[i, ["h1", "ht", "s0", "s1", "th"]].values)
                                   - pb_boy(18.0, *ff.loc[i, ["h1", "ht", "s0", "s1", "th"]].values))
                             for i, sy in son.loc[g.index, "son_yas"].items()]
            oz[c]["18->son"]["pb1_ayni_pencere_medyan"] = float(np.median(model_pencere))
    tablo = pd.DataFrame(satir, columns=["cinsiyet", "aralik", "n", "ortalama_cm", "p10_cm", "medyan_cm",
                                         "p90_cm", "maks_cm", "P(>2cm)"])
    csv_yaz("B_ampirik_kalan_boy.csv", tablo)
    OZET["B_ampirik"] = oz

    # Grafik: 16 yaşından itibaren gerçek bireylerin uzaması
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, c in zip(axes, ("erkek", "kiz")):
        dd = d[(d.cinsiyet == c) & (d.yas >= 16)]
        h16 = dd[dd.yas == 16.0].set_index("id").boy
        for i, g in dd.groupby("id"):
            if i in h16.index:
                ax.plot(g.yas, g.boy - h16[i], color=SOLUK, lw=0.8, alpha=0.8)
        dd = dd[dd.id.isin(h16.index)].copy()
        dd["fark"] = dd.boy - dd.id.map(h16)
        med = dd.groupby("yas").fark.agg(["median", "count"])
        # Medyan yalnızca herkesin ölçüldüğü yaşlarda: 18 sonrası ölçülenler seçilmiş bir alt grup
        med = med[med["count"] >= 0.9 * len(h16)]
        ax.plot(med.index, med["median"], color=SERI[0], lw=2.5, label="medyan (herkes ölçülmüş)")
        ax.annotate(f"medyan {med['median'].iloc[-1]:.1f} cm", (med.index[-1], med["median"].iloc[-1]),
                    xytext=(6, -2), textcoords="offset points", color=INK2, fontsize=9)
        ax.set_title(f"{CINS_AD[c]}: 16 yaşından sonra gerçek uzama (n={len(h16)})")
        ax.set_xlabel("Yaş (18 sonrası yalnızca bir kısmı ölçülmüş)")
        ax.set_xlim(16, 21.6)
    axes[0].set_ylabel("16 yaşındaki boya göre artış (cm)")
    axes[0].legend(frameon=False, loc="upper left")
    kaydet(fig, "1_gercek_buyume_16dan_sonra.png")
    return w


# ---------------------------------------------------------------------------
# C) Hız kuralı
# ---------------------------------------------------------------------------

def c_hiz_kurali(d, w, f):
    kuyruk = f.set_index("id").kuyruk18
    satir, oz = [], {}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, c in zip(axes, ("erkek", "kiz")):
        x = w[w.cinsiyet == c].set_index("id")
        oz[c] = {}
        for j, a in enumerate((16.0, 17.0)):
            kazanc = x[a] - x[a - 1]
            kalan18 = x[18.0] - x[a]
            kalan_son = kalan18 + kuyruk.loc[x.index]
            ok = kazanc.notna() & kalan18.notna()
            g, k18, ks = kazanc[ok].values, kalan18[ok].values, kalan_son[ok].values
            kat18 = float((g * k18).sum() / (g * g).sum())
            kat = float((g * ks).sum() / (g * g).sum())
            art = ks - kat * g
            r = float(np.corrcoef(g, ks)[0, 1])
            mae_kural = float(np.mean(np.abs(art)))
            mae_medyan = float(np.mean(np.abs(ks - np.median(ks))))
            a10, a90 = yuzdelik(art, (10, 90))
            satir.append([c, a, int(ok.sum()), kat18, kat, r, mae_kural, mae_medyan, a10, a90])
            oz[c][str(a)] = dict(n=int(ok.sum()), katsayi_18e=kat18, katsayi_sona=kat, r=r,
                                 mae_kural=mae_kural, mae_herkese_medyan=mae_medyan, artik_p10=a10, artik_p90=a90)
            ax.scatter(g, ks, s=26, color=SERI[j], edgecolor=SURFACE, linewidth=0.8, label=f"{int(a)} yaşında", zorder=3)
        lim = max(ax.get_xlim()[1], ax.get_ylim()[1])
        ax.plot([0, lim], [0, lim], color=INK2, lw=1, ls="--")
        ax.text(lim * 0.62, lim * 0.55, "kalan = geçen yıl", color=INK2, fontsize=9, rotation=0)
        ax.set_xlim(-0.5, lim)
        ax.set_ylim(-0.5, lim)
        ax.set_title(f"{CINS_AD[c]}: geçen yıl uzama vs kalan boy")
        ax.set_xlabel("Son 12 ayda uzama (cm)")
        ax.set_ylabel("Sonrasında kalan boy (cm)")
        ax.legend(frameon=False, loc="upper left")
    kaydet(fig, "2_hiz_kurali.png")

    # Modelsiz kontrol: 18'den sonra da ölçülmüş erkeklerde kalan = son ölçüm - h(a)
    sat2 = []
    d_er = d[d.cinsiyet == "erkek"].groupby("id").agg(son_yas=("yas", "max"), son_boy=("boy", "last"))
    xe = w[w.cinsiyet == "erkek"].set_index("id")
    for min_yas in (19.0, 19.5):
        ids = d_er[d_er.son_yas >= min_yas].index
        for a in (16.0, 17.0):
            g = (xe.loc[ids, a] - xe.loc[ids, a - 1]).values
            k = (d_er.loc[ids, "son_boy"] - xe.loc[ids, a]).values
            kat = float((g * k).sum() / (g * g).sum())
            r = float(np.corrcoef(g, k)[0, 1])
            sat2.append(["erkek", min_yas, a, len(ids), kat, r])
            oz["erkek"][f"modelsiz_son>={min_yas}_yas{a}"] = dict(n=len(ids), katsayi=kat, r=r)
    csv_yaz("C_hiz_kurali_modelsiz.csv", pd.DataFrame(sat2, columns=[
        "cinsiyet", "son_olcum_en_az_yas", "yas", "n", "katsayi_son_olcume_kadar", "korelasyon_r"]))
    csv_yaz("C_hiz_kurali.csv", pd.DataFrame(satir, columns=[
        "cinsiyet", "yas", "n", "katsayi_18e_kadar", "katsayi_sona_kadar", "korelasyon_r",
        "ortalama_mutlak_hata_kural_cm", "ortalama_mutlak_hata_herkese_medyan_cm", "artik_p10_cm", "artik_p90_cm"]))
    OZET["C_hiz_kurali"] = oz


# ---------------------------------------------------------------------------
# D) Ölçüm hatası
# ---------------------------------------------------------------------------

def d_olcum(d, f):
    satir = []
    sigmalar = {"dikkatli (sabah, stadiometre, 3 ölçüm ort.)": 0.3,
                "tek ölçüm, stadiometre": 0.5,
                "saat kontrolsüz / duvara işaret": 0.65}
    for ad, s in sigmalar.items():
        for ay in (3, 6, 12):
            satir.append([ad, s, ay, s * np.sqrt(2) / (ay / 12)])
    t1 = pd.DataFrame(satir, columns=["olcum_kosulu", "tek_olcum_hatasi_sd_cm", "aralik_ay", "hiz_hatasi_sd_cm_yil"])
    csv_yaz("D_olcum_hatasi_analitik.csv", t1)

    # Gerçek veride 6 aylık negatif "büyüme" oranı (16-18 yaş)
    oz = {}
    for c in ("erkek", "kiz"):
        w = d[d.cinsiyet == c].pivot_table(index="id", columns="yas", values="boy")
        inc = np.concatenate([(w[a] - w[a - 0.5]).dropna().values for a in np.arange(16.5, 18.01, 0.5)])
        oz[c] = dict(alti_aylik_artis_n=int(len(inc)), negatif_oran=float(np.mean(inc < 0)))

    # Gerçek eğrilerde karar hatası: 17 yaşında "hâlâ ≥1 cm/yıl büyüyor mu?"
    karar = []
    for c in ("erkek", "kiz"):
        ff = f[f.cinsiyet == c]
        P = ff[["h1", "ht", "s0", "s1", "th"]].values
        for ad, s in sigmalar.items():
            for ay in (6, 12):
                dt = ay / 12
                yanlis = []
                for p in P:
                    gercek = (pb_boy(17.0, *p) - pb_boy(17.0 - dt, *p)) / dt >= 1.0
                    olc = (pb_boy(17.0, *p) - pb_boy(17.0 - dt, *p) + RNG.normal(0, s, 2000)
                           - RNG.normal(0, s, 2000)) / dt >= 1.0
                    yanlis.append(np.mean(olc != gercek))
                karar.append([c, ad, ay, float(np.mean(yanlis))])
    t2 = pd.DataFrame(karar, columns=["cinsiyet", "olcum_kosulu", "aralik_ay", "yanlis_karar_orani"])
    csv_yaz("D_karar_hatasi_17yas.csv", t2)
    oz["karar"] = {f"{r.cinsiyet}|{r.olcum_kosulu}|{r.aralik_ay}": r.yanlis_karar_orani for r in t2.itertuples()}
    OZET["D_olcum"] = oz


# ---------------------------------------------------------------------------
# E) Kişisel tahmin aracının LOO doğrulaması
# ---------------------------------------------------------------------------

def tahmin_h18(onsel, a, h_a, h_once, n, rng, sigma=0.5):
    """Önsel + ölçümler -> h(18) için ağırlıklı örnekler (posterior predictive)."""
    par = onsel.ornekle(n, rng)
    logw = -0.5 * ((boy_par(par, a) - h_a) / sigma) ** 2
    if h_once is not None:
        logw += -0.5 * (((boy_par(par, a) - boy_par(par, a - 1)) - (h_a - h_once)) / (np.sqrt(2) * sigma)) ** 2
    w = np.exp(logw - logw.max())
    tahmin = boy_par(par, 18.0) + rng.normal(0, sigma, n)
    return tahmin, w


def agirlikli_yuzdelik(x, w, q):
    i = np.argsort(x)
    cw = np.cumsum(w[i])
    cw /= cw[-1]
    return np.interp(np.asarray(q) / 100.0, cw, x[i])


def e_loo(w, f, n=40_000):
    sonuc = []
    for c in ("erkek", "kiz"):
        x = w[w.cinsiyet == c].set_index("id")
        ff = f[f.cinsiyet == c].set_index("id")
        for i in x.index:
            digerleri = ff.drop(index=i)
            digerleri = digerleri[digerleri.onsele_dahil]
            onsel = Onsel.parametrelerden(digerleri[["h1", "ht", "s0", "s1", "th"]].values)
            for a in (16.0, 17.0):
                h_a, h_once, h18 = x.loc[i, a], x.loc[i, a - 1], x.loc[i, 18.0]
                if np.isnan([h_a, h_once, h18]).any():
                    continue
                # Kural katsayısı da LOO: diğerlerinden
                xo = x.drop(index=i)
                g = (xo[a] - xo[a - 1]).values
                k = (xo[18.0] - xo[a]).values
                ok = ~np.isnan(g) & ~np.isnan(k)
                kat = (g[ok] * k[ok]).sum() / (g[ok] ** 2).sum()
                kural = h_a + kat * (h_a - h_once)
                for ad, once in (("sadece_boy", None), ("boy+hiz", h_once)):
                    t, wt = tahmin_h18(onsel, a, h_a, once, n, RNG)
                    p10, p50, p90 = agirlikli_yuzdelik(t, wt, [10, 50, 90])
                    sonuc.append(dict(cinsiyet=c, id=i, yas=a, yontem=ad, gercek=h18, tahmin=p50,
                                      p10=p10, p90=p90, kapsadi=float(p10 <= h18 <= p90)))
                sonuc.append(dict(cinsiyet=c, id=i, yas=a, yontem="basit_kural", gercek=h18, tahmin=kural,
                                  p10=np.nan, p90=np.nan, kapsadi=np.nan))
                sonuc.append(dict(cinsiyet=c, id=i, yas=a, yontem="buyume_bitti_varsay", gercek=h18, tahmin=h_a,
                                  p10=np.nan, p90=np.nan, kapsadi=np.nan))
    s = pd.DataFrame(sonuc)
    s["mutlak_hata"] = (s.tahmin - s.gercek).abs()
    ozet = s.groupby(["cinsiyet", "yas", "yontem"]).agg(
        n=("id", "count"), ort_mutlak_hata_cm=("mutlak_hata", "mean"),
        p90_mutlak_hata_cm=("mutlak_hata", lambda v: np.percentile(v, 90)),
        yuzde80_araligi_kapsama=("kapsadi", "mean")).reset_index()
    csv_yaz("E_loo_dogrulama.csv", ozet)
    OZET["E_loo"] = {f"{r.cinsiyet}|{r.yas}|{r.yontem}": dict(mae=r.ort_mutlak_hata_cm, kapsama=r.yuzde80_araligi_kapsama)
                     for r in ozet.itertuples()}


# ---------------------------------------------------------------------------
# F) Dinamik senaryolar, gerçek erkek eğrileri (KANIT SEVİYESİ D)
# ---------------------------------------------------------------------------

SENARYOLAR = {
    "Eksiklik 16-18 (%15), 18'de düzeltildi": [Donem(16, 18, m=0.85)],
    "Anabolik/androjen 6 ay (16-16.5)": [Donem(16, 16.5, m=0.6, r=2.5)],
    "Aromataz inh. 16-18 (r=0.6, q=0.8)": [Donem(16, 18, m=0.8 / 0.6, r=0.6)],
}


def f_senaryolar(f):
    ff = f[(f.cinsiyet == "erkek") & f.onsele_dahil]
    satir = []
    for i, row in ff.iterrows():
        p = tuple(row[["h1", "ht", "s0", "s1", "th"]].values)
        taban = simule_et(p, [], 16.0)
        v16 = float(pb_hiz(16.0, *p))
        for ad, dn in SENARYOLAR.items():
            satir.append(dict(id=row.id, hiz16=v16, senaryo=ad, fark=simule_et(p, dn, 16.0) - taban))
    s = pd.DataFrame(satir)
    ozet = s.groupby("senaryo").fark.describe(percentiles=[0.1, 0.5, 0.9]).reset_index()
    csv_yaz("F_senaryolar_gercek_egriler.csv", ozet)
    OZET["F_senaryolar"] = {r["senaryo"]: dict(p10=r["10%"], medyan=r["50%"], p90=r["90%"], n=int(r["count"]))
                            for _, r in ozet.iterrows()}

    fig, ax = plt.subplots(figsize=(9, 4.8))
    for j, (ad, g) in enumerate(s.groupby("senaryo", sort=False)):
        ax.scatter(g.hiz16, g.fark, s=24, color=SERI[j], edgecolor=SURFACE, linewidth=0.8, label=ad, zorder=3)
    ax.axhline(0, color=INK2, lw=1)
    ax.set_xlabel("16 yaşındaki büyüme hızı (cm/yıl, kişinin kendi eğrisinden)")
    ax.set_ylabel("Nihai boya etkisi (cm)")
    ax.set_title(f"66 gerçek erkek eğrisinde senaryo etkisi (model, kanıt seviyesi D)")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    kaydet(fig, "3_senaryo_etkisi_gercek_egriler.png")

    # Aromataz duyarlılığı: r (kemik yaşı hızı) x q (takvim büyüme hızı oranı)
    sat = []
    hizli = ff[ff.apply(lambda r: pb_hiz(16.0, r.h1, r.ht, r.s0, r.s1, r.th) >= 3.0, axis=1)]
    for grup, G in (("tum_erkekler", ff), ("16da_hizi_3ten_buyuk", hizli)):
        for r in (0.5, 0.6, 0.75):
            for q in (0.6, 0.7, 0.8, 0.9):
                fark = [simule_et(tuple(x[["h1", "ht", "s0", "s1", "th"]].values), [Donem(16, 18, m=q / r, r=r)], 16.0)
                        - simule_et(tuple(x[["h1", "ht", "s0", "s1", "th"]].values), [], 16.0)
                        for _, x in G.iterrows()]
                sat.append([grup, len(G), r, q, float(np.median(fark)), float(np.percentile(fark, 90))])
    csv_yaz("F_aromataz_duyarlilik.csv", pd.DataFrame(sat, columns=[
        "grup", "n", "r_kemik_yasi_hizi", "q_buyume_hizi_orani", "medyan_fark_cm", "p90_fark_cm"]))

    # Eksiklik senaryosunun varsayım duyarlılığı
    sat = []
    for alfa in (0.0, 0.5, 1.0):
        for k in (0.3, 1.0, 2.0):
            ay = DinamikAyar(alfa=alfa, k=k)
            fark = [simule_et(tuple(x[["h1", "ht", "s0", "s1", "th"]].values), [Donem(16, 18, m=0.85)], 16.0, ayar=ay)
                    - simule_et(tuple(x[["h1", "ht", "s0", "s1", "th"]].values), [], 16.0, ayar=ay)
                    for _, x in ff.iterrows()]
            sat.append([alfa, k, float(np.median(fark)), float(np.percentile(fark, 10))])
    csv_yaz("F_eksiklik_duyarlilik.csv", pd.DataFrame(sat, columns=["alfa", "k", "medyan_fark_cm", "p10_fark_cm"]))


if __name__ == "__main__":
    d = berkeley()
    f = a_fit(d)
    w = b_ampirik(d, f)
    c_hiz_kurali(d, w, f)
    d_olcum(d, f)
    e_loo(w, f)
    f_senaryolar(f)
    with open(CIKTI / "ozet.json", "w", encoding="utf-8") as fh:
        json.dump(OZET, fh, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(OZET, ensure_ascii=False, indent=1, default=lambda v: round(float(v), 3)))
