"""
Yaş farkı tercihleri, sürüm 2: kadının büyük olduğu çiftler ve eğitim (README "Ön kayıtlı analiz planı"). Tek komut:

    python calistir.py

Veri sürüm 1 ile aynı (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  D1  Walter ve ark. 2020, 45 ülke açık verisi (OSF gb5cn); yalnız partner yaşı > 10
  D2  Fisman ve Iyengar hızlı tanışma deneyi (DataHub kopyası); yüksek eğitimli örneklem
Analizler C1-C6; testler T1-T5; karar kuralları K1-K4. Çıktılar ciktilar/ altında.
"""

import hashlib
import json
import time
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
TOHUM = 20261016
BOOT = 2000
VERI = {
    "walter": dict(url="https://osf.io/download/5fmyu/",
                   sha256="0509eb7bbaae75c08533d19e1e6fa3a343a4775d825d644068be63824dff5933",
                   dosya=REPO / ".veri" / "yas" / "walter2020_45ulke.csv"),
    "hizli": dict(url="https://datahub.io/core/speed-dating/r/speed-dating.csv",
                  sha256="5f16a947d24289d548b89cb38878ca01e93ce01070ecb76f30b3a98d85bcdcbf",
                  dosya=REPO / ".veri" / "yas" / "speed-dating.csv"),
}
TESTLER, OZET = [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3"
KADIN, ERKEK = "#eb6834", "#2a78d6"


def log(*a):
    print(f"[{time.time() - T0:6.1f} s]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'}  ({deger})")


def indir(v):
    if not v["dosya"].exists():
        v["dosya"].parent.mkdir(parents=True, exist_ok=True)
        istek = urllib.request.Request(v["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
        with urllib.request.urlopen(istek, timeout=180) as r:
            v["dosya"].write_bytes(r.read())
    return hashlib.sha256(v["dosya"].read_bytes()).hexdigest()


def karar(lo, hi, alt="evet", ust="tersine, daha çok"):
    return alt if hi < 0 else (ust if lo > 0 else "belirgin fark yok")


sha = {k: indir(v) for k, v in VERI.items()}
test("T1", "Veri bütünlüğü: iki dosyanın SHA-256 özeti (sürüm 1 ile aynı)",
     ", ".join(f"{k}: {'eşleşti' if sha[k] == v['sha256'] else 'UYUŞMADI'}" for k, v in VERI.items()),
     "ikisi de eşleşir", all(sha[k] == v["sha256"] for k, v in VERI.items()))
rng = np.random.default_rng(TOHUM)

# ---------------------------------------------------------------------------
# D2: hızlı tanışma (C1-C4). Kişi kimliği sürüm 1'deki gibi yeniden kurulur.
# ---------------------------------------------------------------------------
s = pd.read_csv(VERI["hizli"]["dosya"], low_memory=False)
KIMLIK = ["wave", "gender", "age", "race", "field", "attractive_important", "sincere_important", "intellicence_important",
          "funny_important", "ambtition_important", "shared_interests_important", "attractive", "sincere", "intelligence",
          "funny", "ambition", "sports", "tvsports", "exercise", "dining", "museums", "art", "hiking", "gaming", "clubbing",
          "reading", "tv", "theater", "movies", "concerts", "music", "shopping", "yoga", "expected_happy_with_sd_people"]
s["kisi"] = s.groupby(KIMLIK, dropna=False, sort=False).ngroup()
h = s.dropna(subset=["age", "age_o", "decision"]).copy()
h["fark"] = h.age_o - h.age
h["evet"] = h.decision.astype(float)
h["sapma"] = h.evet - h.groupby("kisi").evet.transform("mean")
h["eslesme"] = h["match"].astype(float)

BOLME = {"küçük 3-4": (-4, -3), "yaşıt ±1": (-1, 1), "büyük 3-4": (3, 4)}


def bolme(dd, ad):
    lo, hi = BOLME[ad]
    return (dd.fark >= lo) & (dd.fark <= hi)


ref_k = h[(h.gender == "female") & bolme(h, "yaşıt ±1")]
test("T2", "Sürüm 1 ile tutarlılık: kadınlarda yaşıt bölmesinin \"evet\" oranı", f"{ref_k.evet.mean():.4f}",
     "0.3738 ± 0.0001", abs(ref_k.evet.mean() - 0.3738) <= 0.0001)


def fark_boot(dd, sutun, hedef, ref="yaşıt ±1"):
    """Hedef bölmenin ortalaması − referans bölmenin ortalaması (yüzde puan); kişiler üzerinden bootstrap."""
    dd = dd[bolme(dd, hedef) | bolme(dd, ref)].copy()
    dd["hedef"] = bolme(dd, hedef)
    ozet_k = dd.groupby(["kisi", "hedef"])[sutun].agg(["sum", "count"]).unstack(fill_value=0)
    top_h, say_h = ozet_k[("sum", True)].to_numpy(), ozet_k[("count", True)].to_numpy()
    top_r, say_r = ozet_k[("sum", False)].to_numpy(), ozet_k[("count", False)].to_numpy()

    def f(i):
        return 100 * (top_h[i].sum() / say_h[i].sum() - top_r[i].sum() / say_r[i].sum())

    n = len(ozet_k)
    tah = f(np.arange(n))
    boot = np.array([f(rng.integers(0, n, n)) for _ in range(BOOT)])
    return dict(fark_puan=float(tah), lo=float(np.percentile(boot, 2.5)), hi=float(np.percentile(boot, 97.5)),
                se=float(boot.std()), n_hedef=int(say_h.sum()), n_ref=int(say_r.sum()), kisi=int(n),
                oran_hedef=float(dd.loc[dd.hedef, sutun].mean()), oran_ref=float(dd.loc[~dd.hedef, sutun].mean()))


CINS = {"kadın": "female", "erkek": "male"}
c12, c3 = {}, {}
for c, kod in CINS.items():
    dd = h[h.gender == kod]
    c12[c] = {f"partner {b}": fark_boot(dd, "sapma", b) for b in ("küçük 3-4", "büyük 3-4")}
    kisi_yas = dd.groupby("kisi").age.first()
    med = float(kisi_yas.median())
    genc = set(kisi_yas.index[kisi_yas < med])
    c3[c] = {"ortanca_yas": med}
    for grup, sec in (("ortancanın altı", dd.kisi.isin(genc)), ("ortanca ve üstü", ~dd.kisi.isin(genc))):
        d3 = dd[sec]
        c3[c][grup] = {f"partner {b}": fark_boot(d3, "sapma", b) for b in ("küçük 3-4", "büyük 3-4")}
        c3[c][grup]["yas_ort"] = float(d3.groupby("kisi").age.first().mean())
OZET["C1_C2"], OZET["C3_yasa_gore"] = c12, c3

kadin_bakis = h[h.gender == "female"]
# Kadının bakışında partner küçük = kadın büyük
c4 = {"kadın 3-4 büyük": fark_boot(kadin_bakis, "eslesme", "küçük 3-4"),
      "erkek 3-4 büyük": fark_boot(kadin_bakis, "eslesme", "büyük 3-4")}
OZET["C4_eslesme"] = c4

# Keşif (ön kayıtta yok, sonuçlar görüldükten sonra eklendi): yıl yıl "evet" oranı ve kişi içi sapma, −8…+8
kesif = (h[h.fark.between(-8, 8)].assign(cinsiyet=lambda x: x.gender.map({"female": "kadın", "male": "erkek"}))
         .groupby(["cinsiyet", "fark"]).agg(n=("evet", "size"), evet_orani=("evet", "mean"), kisi_ici_sapma=("sapma", "mean"))
         .reset_index())
kesif.to_csv(CIKTI / "kesif_yil_yil.csv", index=False, float_format="%.4f")
OZET["ham_evet_oranlari"] = {c: {b: float(h[(h.gender == kod) & bolme(h, b)].evet.mean()) for b in BOLME}
                             for c, kod in CINS.items()}

min_n = min(min(v["n_hedef"], v["n_ref"]) for c in c12.values() for v in c.values())
test("T3", "C1 ve C2'deki her bölmede buluşma sayısı", f"en küçük = {min_n}", "≥ 150", min_n >= 150)
max_se = max(v["se"] for c in c12.values() for v in c.values())
test("T4", "C1 ve C2 farklarının bootstrap standart hatası", f"en büyük SE = {max_se:.2f} puan", "< 3 puan", max_se < 3)

# ---------------------------------------------------------------------------
# D1: 45 ülke (C5-C6), partner yaşı > 10
# ---------------------------------------------------------------------------
w = pd.read_csv(VERI["walter"]["dosya"], low_memory=False, encoding="latin-1")
fiz = w.groupby("sex").ideal_physatt.mean()
ERKEK_KOD = int(fiz.idxmax())                           # sürüm 1: erkek = fiziksel çekicilik tercihi yüksek grup
w["cins"] = np.where(w.sex == ERKEK_KOD, "erkek", "kadın")
d = w[w.mate_age.notna() & (w.mate_age > 10)].copy()
d["fark"] = d.mate_age - d.age

ulke = []
for u, g in d.groupby("country"):
    k, e = g[g.cins == "kadın"], g[g.cins == "erkek"]
    if len(k) >= 10 and len(e) >= 10:
        ulke.append(dict(ulke=u, kadin_n=len(k), kadin_buyuk3_pay=100 * float((k.fark <= -3).mean()),
                         cinsiyet_farki=float(e.fark.mean() - k.fark.mean()),
                         gggi=float(g.gggi.iloc[0]), gdp_percap=float(g.gdp_percap.iloc[0])))
ulke = pd.DataFrame(ulke).sort_values("kadin_buyuk3_pay", ascending=False).reset_index(drop=True)
ulke.to_csv(CIKTI / "ulkeler_kadin_buyuk.csv", index=False, float_format="%.3f")
u_ok = ulke.dropna(subset=["gggi"])
test("T5", "C5'te ülke sayısı (cinsiyet eşitliği endeksi dolu)", f"{len(u_ok)} ülke", "≥ 35", len(u_ok) >= 35)


def spear(x, y):
    r = stats.spearmanr(x, y, nan_policy="omit")
    return dict(rho=float(r.statistic), p=float(r.pvalue), n=int(pd.concat([x, y], axis=1).dropna().shape[0]))


tr_i = ulke.index[ulke.ulke == "Turkey"][0]
OZET["C5_ulke"] = dict(
    ulke_sayisi=len(ulke),
    kadin_buyuk3_pay_ortanca=float(ulke.kadin_buyuk3_pay.median()),
    kadin_buyuk3_pay_en_dusuk=ulke.iloc[-1][["ulke", "kadin_buyuk3_pay"]].to_dict(),
    kadin_buyuk3_pay_en_yuksek=ulke.iloc[0][["ulke", "kadin_buyuk3_pay"]].to_dict(),
    turkiye_pay=float(ulke.loc[tr_i, "kadin_buyuk3_pay"]), turkiye_sira_en_yuksekten=int(tr_i) + 1,
    rho_pay_gggi=spear(ulke.kadin_buyuk3_pay, ulke.gggi), rho_pay_gdp=spear(ulke.kadin_buyuk3_pay, ulke.gdp_percap),
    rho_cinsiyet_farki_gggi=spear(ulke.cinsiyet_farki, ulke.gggi))

c6 = {}
for kapsam, dd in (("genel", d), ("turkiye", d[d.country == "Turkey"])):
    k = dd[dd.cins == "kadın"]
    c6[kapsam] = {}
    for ad, (lo, hi) in {"18-24": (18, 24), "25-34": (25, 34), "35+": (35, 200)}.items():
        sec = k[(k.age >= lo) & (k.age <= hi)]
        c6[kapsam][ad] = dict(n=int(len(sec)), kadin_buyuk3_pay=float(100 * (sec.fark <= -3).mean()) if len(sec) else None,
                              erkek_buyuk3_pay=float(100 * (sec.fark >= 3).mean()) if len(sec) else None)
OZET["C6_yas_grubu"] = c6

# ---------------------------------------------------------------------------
# Karar kuralları
# ---------------------------------------------------------------------------
r = OZET["C5_ulke"]["rho_pay_gggi"]
OZET["karar"] = dict(
    K1=karar(c12["kadın"]["partner küçük 3-4"]["lo"], c12["kadın"]["partner küçük 3-4"]["hi"]),
    K2=karar(c12["erkek"]["partner büyük 3-4"]["lo"], c12["erkek"]["partner büyük 3-4"]["hi"]),
    K3=karar(c4["kadın 3-4 büyük"]["lo"], c4["kadın 3-4 büyük"]["hi"]),
    K4=("evet" if r["rho"] > 0 and r["p"] < 0.05 else "hayır") + f" (rho = {r['rho']:+.2f}, p = {r['p']:.3f}, {r['n']} ülke)")
for k, v in OZET["karar"].items():
    log(k, v)

# ---------------------------------------------------------------------------
# Grafik
# ---------------------------------------------------------------------------
fig, axs = plt.subplots(1, 3, figsize=(15, 4.8), facecolor=YUZEY)
ax = axs[0]
satirlar = [("Kadın → 3-4 yaş küçük erkek", c12["kadın"]["partner küçük 3-4"], KADIN),
            ("Kadın → 3-4 yaş büyük erkek", c12["kadın"]["partner büyük 3-4"], KADIN),
            ("Erkek → 3-4 yaş büyük kadın", c12["erkek"]["partner büyük 3-4"], ERKEK),
            ("Erkek → 3-4 yaş küçük kadın", c12["erkek"]["partner küçük 3-4"], ERKEK)]
for i, (ad, v, rk) in enumerate(satirlar):
    y = len(satirlar) - 1 - i
    ax.plot([v["lo"], v["hi"]], [y, y], color=rk, lw=2)
    ax.plot(v["fark_puan"], y, "o", color=rk, ms=8, mec=YUZEY, mew=2)
    ax.text(v["hi"] + 0.6, y, f"{v['fark_puan']:+.1f}", va="center", fontsize=9, color=MUR2)
ax.set_yticks(range(len(satirlar)))
ax.set_yticklabels([s_[0] for s_ in satirlar][::-1], fontsize=9)
ax.axvline(0, color=MUR2, lw=1)
ax.set_xlabel("\"Evet\" farkı, yaşıta göre (yüzde puan; %95 aralık)")
ax.set_title("Hızlı tanışma (yüksek eğitimli örneklem):\nyaşıta göre \"evet\" farkı", loc="left", fontsize=11)

ax = axs[1]
etiket = ["Kadın 3-4\nyaş büyük", "Yaşıt\n(±1)", "Erkek 3-4\nyaş büyük"]
deger = [c4["kadın 3-4 büyük"]["oran_hedef"], c4["kadın 3-4 büyük"]["oran_ref"], c4["erkek 3-4 büyük"]["oran_hedef"]]
nler = [c4["kadın 3-4 büyük"]["n_hedef"], c4["kadın 3-4 büyük"]["n_ref"], c4["erkek 3-4 büyük"]["n_hedef"]]
ax.bar(range(3), [100 * x for x in deger], color=[KADIN, SOLUK, ERKEK], width=0.6, edgecolor=YUZEY)
for i, (x, n) in enumerate(zip(deger, nler)):
    ax.text(i, 100 * x + 0.4, f"%{100 * x:.1f}\n(n = {n})", ha="center", va="bottom", fontsize=9, color=MUR2)
ax.set_xticks(range(3))
ax.set_xticklabels(etiket)
ax.set_ylabel("Karşılıklı eşleşme oranı (%)")
ax.set_ylim(0, 100 * max(deger) * 1.35)
ax.set_title("Hızlı tanışma: iki tarafın da \"evet\" dediği\nbuluşmaların payı", loc="left", fontsize=11)

ax = axs[2]
ax.scatter(u_ok.gggi, u_ok.kadin_buyuk3_pay, s=28, color=SOLUK, edgecolor=MUR2, lw=0.6)
tr_r = ulke.loc[tr_i]
ax.scatter([tr_r.gggi], [tr_r.kadin_buyuk3_pay], s=60, color=KADIN, edgecolor=MUR, lw=0.8, zorder=3)
ax.annotate("Türkiye", (tr_r.gggi, tr_r.kadin_buyuk3_pay), xytext=(6, 6), textcoords="offset points", fontsize=9)
ax.set_xlabel("Küresel Cinsiyet Eşitliği Endeksi (ülke)")
ax.set_ylabel("Partneri en az 3 yaş küçük kadınlar (%)")
ax.set_title(f"{len(u_ok)} ülke: kadının en az 3 yaş büyük olduğu\nçiftlerin payı (rho = {r['rho']:+.2f}, p = {r['p']:.2f})",
             loc="left", fontsize=11)
for a in axs:
    a.set_facecolor(YUZEY)
    a.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(CIKTI / "kadinin_buyuk_oldugu_ciftler.png", dpi=150)
plt.close(fig)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti")
