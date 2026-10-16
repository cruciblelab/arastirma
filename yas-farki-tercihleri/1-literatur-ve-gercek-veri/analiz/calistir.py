"""
Yaş farkı tercihleri: gerçek veri analizi (README "Ön kayıtlı analiz planı"). Tek komut:

    python calistir.py

Veri (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  D1  Walter ve ark. 2020, 45 ülke açık verisi (OSF gb5cn)
  D2  Fisman ve Iyengar hızlı tanışma deneyi (DataHub kopyası)
Analizler A1-A5 (D1), B1-B2 (D2); testler T1-T6; karar kuralları K1-K3. Çıktılar ciktilar/ altında.
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


def ort_ga(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    t = stats.t.ppf(0.975, len(x) - 1)
    return dict(n=int(len(x)), ort=float(m), lo=float(m - t * se), hi=float(m + t * se), medyan=float(np.median(x)))


def egim(x, y):
    r = stats.linregress(x, y)
    t = stats.t.ppf(0.975, len(x) - 2)
    return dict(egim=float(r.slope), lo=float(r.slope - t * r.stderr), hi=float(r.slope + t * r.stderr), n=int(len(x)))


sha = {k: indir(v) for k, v in VERI.items()}
test("T1", "Veri bütünlüğü: iki dosyanın SHA-256 özeti",
     ", ".join(f"{k}: {'eşleşti' if sha[k] == v['sha256'] else 'UYUŞMADI'}" for k, v in VERI.items()),
     "ikisi de eşleşir", all(sha[k] == v["sha256"] for k, v in VERI.items()))

# ---------------------------------------------------------------------------
# D1: 45 ülke (A1-A5)
# ---------------------------------------------------------------------------
w = pd.read_csv(VERI["walter"]["dosya"], low_memory=False, encoding="latin-1")
fiz = w.groupby("sex").ideal_physatt.mean()
ERKEK_KOD = int(fiz.idxmax())                           # README: erkek = fiziksel çekicilik tercihi yüksek grup
w["cins"] = np.where(w.sex == ERKEK_KOD, "erkek", "kadın")
w["fark"] = w.mate_age - w.age                          # partner − kendi (yıl)
OZET["cinsiyet_kodu"] = dict(erkek=ERKEK_KOD, fiziksel_cekicilik_ort={str(k): float(v) for k, v in fiz.items()})


def d1_analiz(d, etiket):
    out = {}
    out["A1_genel"] = {c: ort_ga(d.loc[d.cins == c, "fark"]) for c in ("kadın", "erkek")}
    tr = d[d.country == "Turkey"]
    a2 = {}
    for c in ("kadın", "erkek"):
        x = tr.loc[tr.cins == c, "fark"].to_numpy(float)
        a2[c] = ort_ga(x) | {
            "partner_5ten_fazla_buyuk_%": float(100 * np.mean(x > 5)), "partner_10dan_fazla_buyuk_%": float(100 * np.mean(x > 10)),
            "partner_5ten_fazla_kucuk_%": float(100 * np.mean(x < -5)), "partner_10dan_fazla_kucuk_%": float(100 * np.mean(x < -10)),
            "yas_esit_pm1_%": float(100 * np.mean(np.abs(x) <= 1)), "yas_ort": float(tr.loc[tr.cins == c, "age"].mean())}
        gr = {}
        for ad, (lo, hi) in {"18-24": (18, 24), "25-34": (25, 34), "35+": (35, 200)}.items():
            sec = tr[(tr.cins == c) & (tr.age >= lo) & (tr.age <= hi)]
            gr[ad] = ort_ga(sec.fark) if len(sec) >= 5 else dict(n=int(len(sec)))
        a2[c]["yas_gruplari"] = gr
    out["A2_turkiye"] = a2
    ulke = []
    for u, g in d.groupby("country"):
        mk, me = g.loc[g.cins == "kadın", "fark"], g.loc[g.cins == "erkek", "fark"]
        if len(mk) >= 10 and len(me) >= 10:
            ulke.append(dict(ulke=u, n=len(g), kadin=mk.mean(), erkek=me.mean(), fark_erkek_eksi_kadin=me.mean() - mk.mean()))
    ulke = pd.DataFrame(ulke).sort_values("fark_erkek_eksi_kadin").reset_index(drop=True)
    tr_sira = int(ulke.index[ulke.ulke == "Turkey"][0]) + 1
    out["A3_ulke"] = dict(ulke_sayisi=len(ulke), turkiye_sira_en_buyuk_farktan=tr_sira,
                          turkiye_fark=float(ulke.loc[ulke.ulke == "Turkey", "fark_erkek_eksi_kadin"].iloc[0]),
                          ulkeler_medyan_fark=float(ulke.fark_erkek_eksi_kadin.median()))
    a4 = {}
    for kapsam, dd in (("genel", d), ("turkiye", tr)):
        a4[kapsam] = {c: egim(dd.loc[dd.cins == c, "age"].to_numpy(float), dd.loc[dd.cins == c, "fark"].to_numpy(float))
                      for c in ("kadın", "erkek")}
    out["A4_yas_egimi"] = a4
    return out, ulke, tr


d_tum = w[w.mate_age.notna()].copy()
ana, ulke, tr = d1_analiz(d_tum, "tum")
d_10 = d_tum[d_tum.mate_age > 10].copy()
duy, _, _ = d1_analiz(d_10, "10dan_buyuk")
OZET["D1_ana"], OZET["D1_A5_duyarlilik_partner_yasi_10dan_buyuk"] = ana, duy
ulke.to_csv(CIKTI / "ulkeler.csv", index=False, float_format="%.3f")
a1 = ana["A1_genel"]
test("T2", "Replikasyon (Walter 2020): yaş farkı ortalaması kadın +2.43, erkek −2.26; n = 8920",
     f"kadın {a1['kadın']['ort']:+.2f}, erkek {a1['erkek']['ort']:+.2f}; n = {a1['kadın']['n'] + a1['erkek']['n']}",
     "±0.05 ve n = 8920", abs(a1["kadın"]["ort"] - 2.43) <= 0.05 and abs(a1["erkek"]["ort"] + 2.26) <= 0.05
     and a1["kadın"]["n"] + a1["erkek"]["n"] == 8920)

# ---------------------------------------------------------------------------
# D2: hızlı tanışma (B1-B2)
# ---------------------------------------------------------------------------
s = pd.read_csv(VERI["hizli"]["dosya"], low_memory=False)
test("T3", "Hızlı tanışma verisi: satır sayısı ve cinsiyet değerleri", f"{len(s)} satır; {sorted(s.gender.unique())}",
     "8378; ['female', 'male']", len(s) == 8378 and sorted(s.gender.unique()) == ["female", "male"])

# Sapma (README): dosyada kişi kimliği yok. Kişi, buluşmadan buluşmaya değişmeyen kendi beyanlarından yeniden kurulur.
KIMLIK = ["wave", "gender", "age", "race", "field", "attractive_important", "sincere_important", "intellicence_important",
          "funny_important", "ambtition_important", "shared_interests_important", "attractive", "sincere", "intelligence",
          "funny", "ambition", "sports", "tvsports", "exercise", "dining", "museums", "art", "hiking", "gaming", "clubbing",
          "reading", "tv", "theater", "movies", "concerts", "music", "shopping", "yoga", "expected_happy_with_sd_people"]
s["kisi"] = s[KIMLIK].astype(str).agg("|".join, axis=1).factorize()[0]
say = s.groupby("kisi").size()
kisi_grup = s.groupby("kisi")[["wave", "gender"]].first()
modal = say.groupby([kisi_grup.wave, kisi_grup.gender]).agg(lambda v: v.mode().iloc[0])
beklenen = np.array([modal.loc[(kisi_grup.loc[k, "wave"], kisi_grup.loc[k, "gender"])] for k in say.index])
uyum = float(np.mean(say.to_numpy() == beklenen))
karsi = s.groupby(["wave", "gender"]).size()
test("T6", "Sapma testi: yeniden kurulan kişilerin satır sayısı, dalgadaki karşı cinsten kişi sayısıyla uyumlu (mod)",
     f"{len(say)} kişi; %{100 * uyum:.1f} kişide satır sayısı = dalga-cinsiyet modu", "≥ %90", uyum >= 0.90)

h = s.dropna(subset=["age", "age_o", "decision"]).copy()
h["fark"] = h.age_o - h.age
h["evet"] = h.decision.astype(float)
h["sapma"] = h.evet - h.groupby("kisi").evet.transform("mean")
max_sapma_ort = float(h.groupby("kisi").sapma.mean().abs().max())
test("T4", "Kişi içi merkezleme: her kişinin ortalama sapması 0", f"en büyük |ortalama| = {max_sapma_ort:.1e}", "< 1e-9",
     max_sapma_ort < 1e-9)
SINIR = [(-99, -4, "≤ −4"), (-3, -2, "−3…−2"), (-1, 1, "−1…+1"), (2, 3, "+2…+3"), (4, 99, "≥ +4")]
b1 = []
for c in ("female", "male"):
    for lo, hi, ad in SINIR:
        sec = h[(h.gender == c) & (h.fark >= lo) & (h.fark <= hi)]
        b1.append(dict(cinsiyet="kadın" if c == "female" else "erkek", partner_fark=ad, n=len(sec),
                       evet_orani=float(sec.evet.mean()), kisi_ici_sapma=float(sec.sapma.mean())))
b1 = pd.DataFrame(b1)
b1.to_csv(CIKTI / "hizli_tanisma_evet_oranlari.csv", index=False, float_format="%.4f")


def b2_egim(dd):
    """Kişi içi doğrusal model: sapma ~ büyük + küçük (yıl); kişi sabit etkisi merkezlemeyle."""
    buyuk = np.clip(dd.fark.to_numpy(float), 0, None)
    kucuk = np.clip(-dd.fark.to_numpy(float), 0, None)
    X = np.column_stack([buyuk, kucuk])
    X = X - pd.DataFrame(X).groupby(dd.kisi.to_numpy()).transform("mean").to_numpy()
    b, *_ = np.linalg.lstsq(X, dd.sapma.to_numpy(float), rcond=None)
    return b


rng = np.random.default_rng(TOHUM)
b2 = {}
for c in ("female", "male"):
    dd = h[h.gender == c].reset_index(drop=True)
    tah = b2_egim(dd)
    kisiler = dd.kisi.unique()
    gruplar = {k: g.index.to_numpy() for k, g in dd.groupby("kisi")}
    boot = []
    for _ in range(1000):
        sec = rng.choice(kisiler, len(kisiler))
        idx = np.concatenate([gruplar[k] for k in sec])
        bd = dd.loc[idx].copy()
        bd["kisi"] = np.repeat(np.arange(len(sec)), [len(gruplar[k]) for k in sec])
        boot.append(b2_egim(bd))
    boot = np.array(boot)
    b2["kadın" if c == "female" else "erkek"] = dict(
        partner_buyuk_yil_basina=float(tah[0]), buyuk_lo=float(np.percentile(boot[:, 0], 2.5)),
        buyuk_hi=float(np.percentile(boot[:, 0], 97.5)), buyuk_se=float(boot[:, 0].std()),
        partner_kucuk_yil_basina=float(tah[1]), kucuk_lo=float(np.percentile(boot[:, 1], 2.5)),
        kucuk_hi=float(np.percentile(boot[:, 1], 97.5)), kucuk_se=float(boot[:, 1].std()),
        kisi=int(len(kisiler)), bulusma=int(len(dd)), yas_ort=float(dd.age.mean()))
OZET["D2_B2"] = b2
max_se = max(max(v["buyuk_se"], v["kucuk_se"]) for v in b2.values())
test("T5", "B2 eğimlerinin bootstrap standart hatası", f"en büyük SE = {max_se:.4f}", "< 0.01", max_se < 0.01)

# ---------------------------------------------------------------------------
# Karar kuralları
# ---------------------------------------------------------------------------
a2 = ana["A2_turkiye"]
k1 = a2["kadın"]["lo"] > 0 and a2["erkek"]["hi"] < 0
a3 = ana["A3_ulke"]
k2 = a3["turkiye_fark"] < a3["ulkeler_medyan_fark"]      # fark negatif: daha negatif = daha büyük cinsiyet farkı
k3 = {c: ("etkiliyor" if (v["buyuk_lo"] > 0 or v["buyuk_hi"] < 0 or v["kucuk_lo"] > 0 or v["kucuk_hi"] < 0) else "etkilemiyor")
      for c, v in b2.items()}
OZET["karar"] = dict(
    K1=("evet" if k1 else "hayır") + f" (kadın {a2['kadın']['ort']:+.2f} [{a2['kadın']['lo']:+.2f}, {a2['kadın']['hi']:+.2f}]; "
                                    f"erkek {a2['erkek']['ort']:+.2f} [{a2['erkek']['lo']:+.2f}, {a2['erkek']['hi']:+.2f}])",
    K2=("evet" if k2 else "hayır") + f" (Türkiye {a3['turkiye_fark']:+.2f} yıl; ülke ortancası {a3['ulkeler_medyan_fark']:+.2f}; "
                                    f"{a3['ulke_sayisi']} ülke içinde en büyük farktan {a3['turkiye_sira_en_buyuk_farktan']}. sırada)",
    K3=k3)
for k, v in OZET["karar"].items():
    log(k, v)

# ---------------------------------------------------------------------------
# Grafikler
# ---------------------------------------------------------------------------
fig, axs = plt.subplots(1, 3, figsize=(15, 4.6), facecolor=YUZEY)
ax = axs[0]
bins = np.arange(-15.5, 16.5, 1)
for c, rk in (("kadın", KADIN), ("erkek", ERKEK)):
    x = tr.loc[tr.cins == c, "fark"].clip(-15, 15)
    ax.hist(x, bins=bins, color=rk, alpha=0.55, label=f"{c} (n = {len(x)}; ort. {x.mean():+.1f})", edgecolor=YUZEY, lw=0.6)
ax.axvline(0, color=MUR2, lw=1)
ax.set_xlabel("Partnerin yaşı − kendi yaşı (yıl; ±15'te kırpıldı)")
ax.set_ylabel("Kişi sayısı")
ax.set_title("Türkiye: gerçek partnerle yaş farkı", loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=9)

ax = axs[1]
for c, rk in (("kadın", KADIN), ("erkek", ERKEK)):
    g = d_tum[d_tum.cins == c]
    gr = g.groupby(pd.cut(g.age, [17, 24, 29, 34, 39, 49, 59, 100])).fark.mean()
    orta = [21, 27, 32, 37, 44, 54, 65]
    ax.plot(orta, gr.to_numpy(), "o-", color=rk, lw=2, ms=6, label=c)
ax.axhline(0, color=MUR2, lw=1)
ax.set_xlabel("Katılımcının yaşı")
ax.set_ylabel("Partner − kendi (yıl, ortalama)")
ax.set_title("45 ülke: yaş ilerledikçe fark", loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=9)

ax = axs[2]
x = np.arange(len(SINIR))
for i, (c, rk) in enumerate((("kadın", KADIN), ("erkek", ERKEK))):
    v = b1[b1.cinsiyet == c]
    ax.bar(x + (i - 0.5) * 0.38, v.evet_orani * 100, width=0.36, color=rk, label=c, edgecolor=YUZEY)
ax.set_xticks(x)
ax.set_xticklabels([a for _, _, a in SINIR])
ax.set_xlabel("Partner − kendi (yıl)")
ax.set_ylabel("\"Evet\" oranı (%)")
ax.set_title("Hızlı tanışma: partnerin yaşına göre \"evet\"", loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=9)
for a in axs:
    a.set_facecolor(YUZEY)
    a.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(CIKTI / "yas_farki.png", dpi=150)
plt.close(fig)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti")
