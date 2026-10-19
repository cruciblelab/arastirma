"""
Çekicilik ve sohbet, sürüm 1: hızlı tanışma analizi (README "Ön kayıtlı analiz planı"). Tek komut:

    python calistir.py

Veri yaş-farkı araştırmasıyla aynı (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  D1  Fisman ve Iyengar hızlı tanışma deneyi (DataHub kopyası)
  D2  Walter ve ark. 2020, 45 ülke açık verisi (OSF gb5cn)
Analizler A1-A6; teknik testler T1-T5; karar kuralları K1-K6. Çıktılar ciktilar/ altında.
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

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
TOHUM = 20261019
BOOT = 2000
VERI = {
    "hizli": dict(url="https://datahub.io/core/speed-dating/r/speed-dating.csv",
                  sha256="5f16a947d24289d548b89cb38878ca01e93ce01070ecb76f30b3a98d85bcdcbf",
                  dosya=REPO / ".veri" / "yas" / "speed-dating.csv"),
    "walter": dict(url="https://osf.io/download/5fmyu/",
                   sha256="0509eb7bbaae75c08533d19e1e6fa3a343a4775d825d644068be63824dff5933",
                   dosya=REPO / ".veri" / "yas" / "walter2020_45ulke.csv"),
}
TESTLER, KARARLAR, OZET = [], [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3"
KADIN, ERKEK = "#eb6834", "#2a78d6"

OZELLIK = {"attractive_partner": "çekicilik", "sincere_partner": "samimiyet", "intelligence_partner": "zekâ",
           "funny_partner": "komiklik", "ambition_partner": "hırs", "shared_interests_partner": "ortak ilgi"}
ONEM = {"attractive_partner": "attractive_important", "funny_partner": "funny_important",
        "intelligence_partner": "intellicence_important"}
KIMLIK = ["wave", "gender", "age", "race", "field", "attractive_important", "sincere_important", "intellicence_important",
          "funny_important", "ambtition_important", "shared_interests_important", "attractive", "sincere", "intelligence",
          "funny", "ambition", "sports", "tvsports", "exercise", "dining", "museums", "art", "hiking", "gaming", "clubbing",
          "reading", "tv", "theater", "movies", "concerts", "music", "shopping", "yoga", "expected_happy_with_sd_people"]


def log(*a):
    print(f"[{time.time() - T0:6.1f} s]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'}  ({deger})")


def karar_kaydi(ad, soru, deger, karar):
    KARARLAR.append(dict(kural=ad, soru=soru, deger=deger, karar=karar))
    log(f"{ad}: {karar}  ({deger})")


def yon(lo, hi, ust="evet", alt="tersine"):
    return ust if lo > 0 else (alt if hi < 0 else "belirgin fark yok")


def indir(v):
    if not v["dosya"].exists():
        v["dosya"].parent.mkdir(parents=True, exist_ok=True)
        istek = urllib.request.Request(v["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
        with urllib.request.urlopen(istek, timeout=180) as r:
            v["dosya"].write_bytes(r.read())
    return hashlib.sha256(v["dosya"].read_bytes()).hexdigest()


def aralik(dagilim):
    return np.percentile(dagilim, [2.5, 97.5], axis=0)


sha = {k: indir(v) for k, v in VERI.items()}
test("T1", "Veri bütünlüğü: iki dosyanın SHA-256 özeti (yaş-farkı araştırmasıyla aynı)",
     ", ".join(f"{k}: {'eşleşti' if sha[k] == v['sha256'] else 'UYUŞMADI'}" for k, v in VERI.items()),
     "ikisi de eşleşir", all(sha[k] == v["sha256"] for k, v in VERI.items()))
rng = np.random.default_rng(TOHUM)

# ---------------------------------------------------------------------------
# D1: hızlı tanışma. Kişi kimliği yaş-farkı araştırmasındaki gibi kurulur.
# ---------------------------------------------------------------------------
s = pd.read_csv(VERI["hizli"]["dosya"], low_memory=False, na_values="?")
s["kisi"] = s.groupby(KIMLIK, dropna=False, sort=False).ngroup()
say = s.groupby("gender").kisi.nunique().to_dict()
test("T2", "Kişi sayısı yaş-farkı sürüm 1 ile aynı", f"kadın {say.get('female')}, erkek {say.get('male')}",
     "kadın 269, erkek 274", say.get("female") == 269 and say.get("male") == 274)

X6 = list(OZELLIK)
d = s.dropna(subset=X6 + ["decision"]).copy()
d["evet"] = d.decision.astype(float)


def merkezle(dd, sutunlar):
    return dd[sutunlar] - dd.groupby("kisi")[sutunlar].transform("mean")


def kisi_ici(dd, sutunlar, ek=None):
    """Kişi içi merkezlenmiş ve kişi içi SS'ye bölünmüş yordayıcılar, merkezlenmiş karar; kişi bazında X'X ve X'y."""
    xc = merkezle(dd, sutunlar)
    olcek = xc.std()
    xc = xc / olcek
    if ek is not None:
        xc = pd.concat([xc, ek(xc)], axis=1)
    yc = dd.evet - dd.groupby("kisi").evet.transform("mean")
    kisiler = dd.kisi.to_numpy()
    benzersiz, idx = np.unique(kisiler, return_inverse=True)
    X, y = xc.to_numpy(), yc.to_numpy()
    k = X.shape[1]
    xtx = np.zeros((len(benzersiz), k, k))
    xty = np.zeros((len(benzersiz), k))
    np.add.at(xtx, idx, X[:, :, None] * X[:, None, :])
    np.add.at(xty, idx, X * y[:, None])
    return dict(sutunlar=list(xc.columns), xtx=xtx, xty=xty, yc=yc, n=len(dd), kisi=len(benzersiz))


def coz(m, agirlik=None):
    if agirlik is None:
        return np.linalg.solve(m["xtx"].sum(0), m["xty"].sum(0))
    return np.linalg.solve(np.tensordot(agirlik, m["xtx"], 1), agirlik @ m["xty"])


def boot(m):
    n = m["xtx"].shape[0]
    ag = rng.multinomial(n, np.full(n, 1 / n), size=BOOT).astype(float)
    return np.array([coz(m, a) for a in ag])


# A1 ve A2: iki cinsiyet, 6 yordayıcı
MOD, DAG = {}, {}
for cins in ("female", "male"):
    dd = d[d.gender == cins]
    MOD[cins] = kisi_ici(dd, X6)
    DAG[cins] = boot(MOD[cins])
    if cins == "female":
        ortlar = MOD[cins]["yc"].groupby(dd.kisi).mean().abs().max()
        test("T4", "Kişi içi merkezleme: merkezlenmiş kararın kişi ortalamalarının mutlak en büyüğü", f"{ortlar:.2e}",
             "< 1e-9", ortlar < 1e-9)

satirlar = []
for cins, ad in (("female", "kadın"), ("male", "erkek")):
    b = coz(MOD[cins]) * 100
    lo, hi = aralik(DAG[cins] * 100)
    for i, c in enumerate(X6):
        satirlar.append(dict(karar_veren=ad, ozellik=OZELLIK[c], puan=b[i], lo=lo[i], hi=hi[i],
                             n_degerlendirme=MOD[cins]["n"], n_kisi=MOD[cins]["kisi"]))
kat = pd.DataFrame(satirlar)
fark_dag = (DAG["male"] - DAG["female"]) * 100
fark_b = (coz(MOD["male"]) - coz(MOD["female"])) * 100
flo, fhi = aralik(fark_dag)
farklar = pd.DataFrame(dict(ozellik=[OZELLIK[c] for c in X6], erkek_eksi_kadin=fark_b, lo=flo, hi=fhi))
kat.to_csv(CIKTI / "katsayilar.csv", index=False, float_format="%.2f")
farklar.to_csv(CIKTI / "farklar_erkek_eksi_kadin.csv", index=False, float_format="%.2f")
OZET["A1_A2"] = dict(kat=kat.round(2).to_dict("records"), fark=farklar.round(2).to_dict("records"))

cek = kat[kat.ozellik == "çekicilik"]
test("T3", "Çekicilik katsayısının %95 aralık alt sınırı iki cinsiyette de > 0",
     ", ".join(f"{r.karar_veren} {r.lo:.1f}" for r in cek.itertuples()), "ikisi de > 0", bool((cek.lo > 0).all()))

kad = kat[kat.karar_veren == "kadın"].set_index("ozellik")
k1 = (kad.puan.idxmax() == "çekicilik") and kad.loc["komiklik", "lo"] > 0 and kad.loc["ortak ilgi", "lo"] > 0
karar_kaydi("K1", "Kadınlarda en büyük katsayı çekicilik; komiklik ve ortak ilgi pozitif mi? (kör değil)",
            "; ".join(f"{o} {r.puan:.1f} [{r.lo:.1f}, {r.hi:.1f}]" for o, r in kad.iterrows()), "evet" if k1 else "hayır")
fr = farklar.set_index("ozellik")
r = fr.loc["çekicilik"]
karar_kaydi("K2", "Erkekler görünüşe kadınlardan daha mı çok ağırlık veriyor? (erkek − kadın)",
            f"{r.erkek_eksi_kadin:.1f} [{r.lo:.1f}, {r.hi:.1f}]", yon(r.lo, r.hi))
for kod, oz in (("K3", "komiklik"), ("K3b", "zekâ")):
    r = fr.loc[oz]
    karar_kaydi(kod, f"Kadınlar {oz} özelliğine erkeklerden daha mı çok ağırlık veriyor? (kadın − erkek)",
                f"{-r.erkek_eksi_kadin:.1f} [{-r.hi:.1f}, {-r.lo:.1f}]", yon(-r.hi, -r.lo))

# A3: söylenen önem × gerçek puan (kadınlar)
kd = d[d.gender == "female"].copy()
kisi_onem = kd.groupby("kisi").agg(wave=("wave", "first"), **{v: (v, "first") for v in ONEM.values()})
for v in ONEM.values():
    kisi_onem[v + "_z"] = kisi_onem.groupby("wave")[v].transform(lambda x: (x - x.mean()) / x.std(ddof=0))
kd = kd.join(kisi_onem[[v + "_z" for v in ONEM.values()]], on="kisi")
kd = kd.dropna(subset=[v + "_z" for v in ONEM.values()])


def etkilesim(xc):
    return pd.DataFrame({f"{OZELLIK[c]} × önem": xc[c] * kd.loc[xc.index, ONEM[c] + "_z"] for c in ONEM})


m3 = kisi_ici(kd, X6, ek=etkilesim)
b3, d3 = coz(m3) * 100, boot(m3) * 100
lo3, hi3 = aralik(d3)
a3 = pd.DataFrame(dict(terim=m3["sutunlar"], puan=b3, lo=lo3, hi=hi3))
a3.to_csv(CIKTI / "soylenen_ve_gercek.csv", index=False, float_format="%.2f")
OZET["A3"] = dict(n=m3["n"], kisi=m3["kisi"], terimler=a3.round(2).to_dict("records"))
etk = a3[a3.terim.str.contains("×")]
ongormuyor = int(((etk.lo <= 0) & (etk.hi >= 0)).sum())
for t in etk.itertuples():
    karar_kaydi("K4", f"Söylenen önem gerçek kararı öngörüyor mu? ({t.terim})", f"{t.puan:.1f} [{t.lo:.1f}, {t.hi:.1f}]",
                "öngörüyor" if t.lo > 0 else ("öngörmüyor" if t.hi >= 0 else "tersine"))
karar_kaydi("K4 genel", "En az 2 etkileşim 'öngörmüyor' mu?", f"{ongormuyor}/3",
            "söylenen ve gerçek tercih örtüşmüyor" if ongormuyor >= 2 else "söylenen tercih kararı kısmen öngörüyor")

# A4: nesnel hobi benzerliği ve algılanan ortak ilgi (kadınlar, aynı satırlar)
k4 = d[(d.gender == "female")].dropna(subset=["interests_correlate"]).copy()
m_nes = kisi_ici(k4, ["interests_correlate"])
m_alg = kisi_ici(k4, ["shared_interests_partner"])
n4 = m_nes["xtx"].shape[0]
ag = rng.multinomial(n4, np.full(n4, 1 / n4), size=BOOT).astype(float)
b_nes = np.array([coz(m_nes, a)[0] for a in ag]) * 100
b_alg = np.array([coz(m_alg, a)[0] for a in ag]) * 100
nes, alg = coz(m_nes)[0] * 100, coz(m_alg)[0] * 100
(nlo, nhi), (alo, ahi), (flo4, fhi4) = aralik(b_nes), aralik(b_alg), aralik(b_alg - b_nes)
OZET["A4"] = dict(n=m_nes["n"], kisi=m_nes["kisi"], nesnel=[nes, nlo, nhi], algilanan=[alg, alo, ahi],
                  fark=[alg - nes, flo4, fhi4])
k5 = ((nlo <= 0 <= nhi) or nes < alg / 2) and flo4 > 0
karar_kaydi("K5", "Ortak ilgi sohbette mi oluşuyor? (nesnel benzerlik / algılanan ortak ilgi)",
            f"nesnel {nes:.1f} [{nlo:.1f}, {nhi:.1f}]; algılanan {alg:.1f} [{alo:.1f}, {ahi:.1f}]; fark {alg - nes:.1f} [{flo4:.1f}, {fhi4:.1f}]",
            "kâğıt üzerindeki benzerlik az etkili, ortak ilgi sohbette algılanıyor" if k5 else "hayır")

# ---------------------------------------------------------------------------
# D2: 45 ülke (A5, A6)
# ---------------------------------------------------------------------------
w = pd.read_csv(VERI["walter"]["dosya"], encoding_errors="ignore")
IDEAL = {"ideal_kindness": "iyi kalplilik", "ideal_intelligence": "zekâ", "ideal_health": "sağlık",
         "ideal_physatt": "fiziksel çekicilik", "ideal_resources": "kaynak"}
kaynak = w.groupby("sex").ideal_resources.mean()
test("T5", "D2: ülke sayısı ve cinsiyet kodu (sex=0 kadın: kaynak ortalaması daha yüksek)",
     f"{w.country.nunique()} ülke; kaynak ort. sex0 {kaynak[0]:.2f}, sex1 {kaynak[1]:.2f}",
     "45 ülke ve sex0 > sex1", w.country.nunique() == 45 and kaynak[0] > kaynak[1])
ulke = {}
for sx, ad in ((0, "kadın"), (1, "erkek")):
    u = w[w.sex == sx].groupby("country")[list(IDEAL)].mean().rename(columns=IDEAL)
    u["birinci"] = u[list(IDEAL.values())].idxmax(axis=1)
    u.round(2).to_csv(CIKTI / f"ulkeler_{'kadin' if sx == 0 else 'erkek'}.csv")
    ulke[ad] = u
    OZET[f"A{5 if sx == 0 else 6}"] = dict(birinci_sayilari=u.birinci.value_counts().to_dict(),
                                          turkiye=u.loc["Turkey", list(IDEAL.values())].round(2).to_dict(),
                                          turkiye_birinci=u.loc["Turkey", "birinci"],
                                          iyi_kalplilik_cekicilikten_yuksek=int((u["iyi kalplilik"] > u["fiziksel çekicilik"]).sum()))
ik = OZET["A5"]["birinci_sayilari"].get("iyi kalplilik", 0)
karar_kaydi("K6", "45 ülkede kadınlar en çok iyi kalpliliği mi önemsiyor? (kör değil)", f"{ik}/45 ülkede birinci",
            "evet" if ik >= 25 else "hayır")

# ---------------------------------------------------------------------------
# Grafik: kişi içi katsayılar, kadın ve erkek karar verenler
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=YUZEY)
ax.set_facecolor(YUZEY)
sira = kat[kat.karar_veren == "kadın"].sort_values("puan").ozellik.tolist()
for j, (ad, renk, kay) in enumerate((("kadın", KADIN, 0.14), ("erkek", ERKEK, -0.14))):
    kk = kat[kat.karar_veren == ad].set_index("ozellik").loc[sira]
    yy = np.arange(len(sira)) + kay
    ax.hlines(yy, kk.lo, kk.hi, color=renk, lw=2)
    ax.plot(kk.puan, yy, "o", ms=8, color=renk, mec=YUZEY, mew=2, label=f"karar veren: {ad}")
ax.axvline(0, color=SOLUK, lw=1)
ax.set_yticks(range(len(sira)), sira, color=MUR)
ax.set_xlabel("\"Evet\" olasılığındaki değişim (puan, özellik 1 SS yüksek bulunduğunda; %95 aralık)", color=MUR2)
ax.set_title("Hızlı tanışmada \"evet\" kararını ne belirliyor? (kişi içi)", color=MUR, loc="left")
for k in ("top", "right"):
    ax.spines[k].set_visible(False)
for k in ("left", "bottom"):
    ax.spines[k].set_color(SOLUK)
ax.tick_params(colors=MUR2)
ax.grid(axis="x", color="#ecebe8", lw=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="lower right")
fig.tight_layout()
fig.savefig(CIKTI / "evet_kararini_belirleyenler.png", dpi=160)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET["testler"] = TESTLER
OZET["kararlar"] = KARARLAR
OZET["tohum"], OZET["bootstrap"] = TOHUM, BOOT
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
gecen = sum(t["sonuc"] == "GEÇTİ" for t in TESTLER)
log(f"Bitti: {gecen}/{len(TESTLER)} test geçti.")
