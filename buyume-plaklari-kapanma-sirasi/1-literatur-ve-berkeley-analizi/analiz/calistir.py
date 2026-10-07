"""
Bacak ve gövde büyümesinin bitiş sırası (on-kayit.md). Tek komut:

    python calistir.py

Veri: Berkeley (sitar), boy araştırması sürüm 3'ün veri.py modülüyle indirilir ve SHA-256 ile doğrulanır.
Karşılaştırma: sürüm 3 büyüme modeli (D). Çıktılar ciktilar/ altında.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
V3 = REPO / "boy-uzamasi-16-18-yas" / "3-mekanistik-simulasyon-ve-on-kayit" / "simulasyon"
sys.path.append(str(V3))
sys.path.append(str(REPO / "spor-egzersiz-ve-boy" / "1-fizik-tabanli-simulasyon" / "simulasyon"))
import veri            # noqa: E402
import plak            # noqa: E402
from model import simule_et  # noqa: E402

CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
ESIKLER = (0.3, 0.5, 1.0)
OZET = {}


def bitis(yas, L, esik):
    """Son ölçüme kadar kalan büyümenin ilk kez ≤ esik olduğu yaş."""
    kalan = L[-1] - L
    return float(yas[np.argmax(kalan <= esik)])


def kisi_olcutleri(yas, B, G, esik=0.5):
    H = B + G
    b_bit, g_bit = bitis(yas, B, esik), bitis(yas, G, esik)
    once = yas <= yas[-1] - 0.9
    g_son_yil = float(G[-1] - G[once][-1]) if once.any() else np.nan
    h16, g16 = np.interp(16.0, yas, H), np.interp(16.0, yas, G)
    dH16, dG16 = float(H[-1] - h16), float(G[-1] - g16)
    return dict(son_yas=float(yas[-1]), bacak_bitis=b_bit, govde_bitis=g_bit,
                govde_sonra=g_bit > b_bit, kalan_govde_bacak_bitince=float(G[-1] - np.interp(b_bit, yas, G)),
                govde_son_yil=g_son_yil, govde_sansurlu=bool(g_son_yil > 0.5) if not np.isnan(g_son_yil) else False,
                dH16=dH16, dG16=dG16, dB16=dH16 - dG16)


# ---------------------------------------------------------------------------
# Berkeley (V)
# ---------------------------------------------------------------------------

d = veri.berkeley().dropna(subset=["govde"])
satir = []
for (i, c), g in d.groupby(["id", "cinsiyet"]):
    g = g.sort_values("yas")
    if g.yas.min() >= 13.0 or g.yas.max() < 18.0:
        continue
    yas, B, G = g.yas.values, g.bacak.values, g.govde.values
    for e in ESIKLER:
        satir.append(dict(id=i, cinsiyet=c, esik=e, **kisi_olcutleri(yas, B, G, e)))
k = pd.DataFrame(satir)
k.to_csv(CIKTI / "berkeley_kisiler.csv", index=False, float_format="%.3f")


def ozetle(t):
    pay = t[t.dH16 >= 0.5]
    return dict(n=int(len(t)), son_yas_medyan=float(t.son_yas.median()),
                bacak_bitis_medyan=float(t.bacak_bitis.median()),
                bacak_bitis_p25_p75=[float(t.bacak_bitis.quantile(.25)), float(t.bacak_bitis.quantile(.75))],
                govde_bitis_medyan=float(t.govde_bitis.median()),
                govde_bitis_p25_p75=[float(t.govde_bitis.quantile(.25)), float(t.govde_bitis.quantile(.75))],
                govde_sonra_oran=float(t.govde_sonra.mean()),
                kalan_govde_medyan=float(t.kalan_govde_bacak_bitince.median()),
                kalan_govde_p25_p75=[float(t.kalan_govde_bacak_bitince.quantile(.25)),
                                     float(t.kalan_govde_bacak_bitince.quantile(.75))],
                kalan_govde_p90=float(t.kalan_govde_bacak_bitince.quantile(.9)),
                govde_sansurlu_oran=float(t.govde_sansurlu.mean()),
                dH16_medyan=float(t.dH16.median()), dG16_medyan=float(t.dG16.median()), dB16_medyan=float(t.dB16.median()),
                govde_payi16_medyan=float((pay.dG16 / pay.dH16).median()) if len(pay) else np.nan,
                govde_payi16_n=int(len(pay)), govde_payi16_birlesik=float(t.dG16.sum() / t.dH16.sum()))


for e in ESIKLER:
    for c in ("erkek", "kiz"):
        OZET[f"berkeley_{c}_esik{e}"] = ozetle(k[(k.cinsiyet == c) & (k.esik == e)])

hip = []
for c in ("erkek", "kiz"):
    for e in ESIKLER:
        o = OZET[f"berkeley_{c}_esik{e}"]
        hip.append(dict(cinsiyet=c, esik=e, H1_govde_sonra_oran=o["govde_sonra_oran"],
                        H1_destek=o["govde_sonra_oran"] >= 0.60,
                        H2_kalan_govde_medyan=o["kalan_govde_medyan"],
                        H2_destek=(o["kalan_govde_medyan"] >= 0.5) if c == "erkek" else None,
                        H3_govde_payi_medyan=o["govde_payi16_medyan"], H3_n=o["govde_payi16_n"],
                        H3_destek=(o["govde_payi16_medyan"] > 0.5) if c == "erkek" else None))
pd.DataFrame(hip).to_csv(CIKTI / "hipotezler.csv", index=False, float_format="%.3f")


# ---------------------------------------------------------------------------
# Sürüm 3 modeli (D)
# ---------------------------------------------------------------------------

YAS = np.round(np.arange(9.0, 30.0 + 1e-9, 0.5), 2)
for c in ("erkek", "kiz"):
    pop, ind, L0b, L0g = plak.kohort(c, 5000, np.random.default_rng(20261007))
    s = simule_et(ind, pop, L0b, L0g, t1=30.0, kayit_yaslari=YAS)
    for kes, etiket in ((30.0, "30"), (19.0, "19")):
        m = YAS <= kes
        rows = [kisi_olcutleri(YAS[m], s["bacak"][m, j], s["govde"][m, j], 0.5) for j in range(5000)]
        OZET[f"model_{c}_son{etiket}"] = ozetle(pd.DataFrame(rows))


# ---------------------------------------------------------------------------
# Grafik
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(1, 3, figsize=(14, 4.3))
for c, renk in (("erkek", "#2a78d6"), ("kiz", "#eb6834")):
    t = k[(k.cinsiyet == c) & (k.esik == 0.5)]
    j = np.random.default_rng(1).uniform(-0.12, 0.12, (2, len(t)))
    ax[0].scatter(t.bacak_bitis + j[0], t.govde_bitis + j[1], s=14, alpha=0.7, color=renk,
                  label=f"{'Erkek' if c == 'erkek' else 'Kız'} (n={len(t)})")
    # ortalama yıllık hız (yarım yıllık farklar)
    x = d[d.cinsiyet == c].sort_values(["id", "yas"])
    x = x.assign(vb=x.groupby("id").bacak.diff() / x.groupby("id").yas.diff(),
                 vg=x.groupby("id").govde.diff() / x.groupby("id").yas.diff())
    hv = x[(x.yas >= 10) & (x.yas <= 20)].groupby("yas")[["vb", "vg"]].mean()
    a = ax[1] if c == "erkek" else ax[2]
    a.plot(hv.index, hv.vb, color="#2a78d6", lw=2, label="bacak")
    a.plot(hv.index, hv.vg, color="#1baf7a", lw=2, label="gövde (oturma boyu)")
    a.axhline(0, color="#999", lw=0.8)
    a.set_title(f"{'Erkek' if c == 'erkek' else 'Kız'}: ortalama yıllık uzama (Berkeley)")
    a.set_xlabel("Yaş")
    a.set_ylabel("cm/yıl")
    a.legend(frameon=False)
    a.grid(alpha=0.3)
lim = [12, 21.5]
ax[0].plot(lim, lim, color="#999", lw=1, ls="--")
ax[0].set_xlim(lim)
ax[0].set_ylim(lim)
ax[0].set_xlabel("Bacak büyümesinin bitiş yaşı")
ax[0].set_ylabel("Gövde büyümesinin bitiş yaşı")
ax[0].set_title("Çizginin üstü: gövde bacaktan sonra bitiyor")
ax[0].legend(frameon=False, fontsize=8)
ax[0].grid(alpha=0.3)
fig.tight_layout()
fig.savefig(CIKTI / "bitis_sirasi.png", dpi=150)

(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(pd.DataFrame(hip).to_string(index=False))
for kk in ("berkeley_erkek_esik0.5", "berkeley_kiz_esik0.5", "model_erkek_son30", "model_erkek_son19", "model_kiz_son30"):
    print(kk, json.dumps(OZET[kk], ensure_ascii=False))
