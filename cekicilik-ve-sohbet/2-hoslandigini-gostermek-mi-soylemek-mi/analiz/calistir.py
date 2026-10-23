"""
Çekicilik ve sohbet, sürüm 2: hoşlandığını göstermek mi, söylemek mi (README "Ön kayıtlı analiz planı"). Tek komut:

    python calistir.py

Veri sürüm 1 ile aynı (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  D1  Fisman ve Iyengar hızlı tanışma deneyi (DataHub kopyası)
Analizler B1-B4; teknik testler T1-T5; karar kuralları K1-K4. Çıktılar ciktilar/ altında.
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
TOHUM = 20261023
BOOT = 2000
VERI = dict(url="https://datahub.io/core/speed-dating/r/speed-dating.csv",
            sha256="5f16a947d24289d548b89cb38878ca01e93ce01070ecb76f30b3a98d85bcdcbf",
            dosya=REPO / ".veri" / "yas" / "speed-dating.csv")
TESTLER, KARARLAR, OZET = [], [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3"
KADIN, ERKEK = "#eb6834", "#2a78d6"

OZELLIK = {"attractive_partner": "çekicilik", "sincere_partner": "samimiyet", "intelligence_partner": "zekâ",
           "funny_partner": "komiklik", "ambition_partner": "hırs", "shared_interests_partner": "ortak ilgi"}
KIMLIK = ["wave", "gender", "age", "race", "field", "attractive_important", "sincere_important", "intellicence_important",
          "funny_important", "ambtition_important", "shared_interests_important", "attractive", "sincere", "intelligence",
          "funny", "ambition", "sports", "tvsports", "exercise", "dining", "museums", "art", "hiking", "gaming", "clubbing",
          "reading", "tv", "theater", "movies", "concerts", "music", "shopping", "yoga", "expected_happy_with_sd_people"]
KARSI = ["wave", "karsi_cinsiyet", "age_o", "race_o", "pref_o_attractive", "pref_o_sincere", "pref_o_intelligence",
         "pref_o_funny", "pref_o_ambitious", "pref_o_shared_interests"]
AD = {"algilanan": "\"benden hoşlanıyor\" hissi", "karsi_ozgun": "karşısındaki onu özellikle seçti",
      "karsi_secici_olmayan": "karşısındaki herkese evet diyor"}
CINS = (("female", "kadın"), ("male", "erkek"))


def log(*a):
    print(f"[{time.time() - T0:6.1f} s]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'}  ({deger})")


def karar_kaydi(ad, soru, deger, karar):
    KARARLAR.append(dict(kural=ad, soru=soru, deger=deger, karar=karar))
    log(f"{ad}: {karar}  ({deger})")


def indir(v):
    if not v["dosya"].exists():
        v["dosya"].parent.mkdir(parents=True, exist_ok=True)
        istek = urllib.request.Request(v["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
        with urllib.request.urlopen(istek, timeout=180) as r:
            v["dosya"].write_bytes(r.read())
    return hashlib.sha256(v["dosya"].read_bytes()).hexdigest()


sha = indir(VERI)
test("T1", "Veri bütünlüğü: SHA-256 (sürüm 1 ile aynı)", "eşleşti" if sha == VERI["sha256"] else "UYUŞMADI",
     "eşleşir", sha == VERI["sha256"])
rng = np.random.default_rng(TOHUM)

s = pd.read_csv(VERI["dosya"], low_memory=False, na_values="?")
s["kisi"] = s.groupby(KIMLIK, dropna=False, sort=False).ngroup()
s["karsi_cinsiyet"] = s.gender.map({"female": "male", "male": "female"})
s["karsi"] = s.groupby(KARSI, dropna=False, sort=False).ngroup()

# T2: karşı taraf kimliği sayısı ~ karar veren sayısı (dalga ve cinsiyet bazında)
karar_veren = s.groupby(["wave", "gender"]).kisi.nunique()
karsi_say = s.groupby(["wave", "karsi_cinsiyet"]).karsi.nunique()
karsi_say.index = karsi_say.index.set_names(["wave", "gender"])
fark = (karsi_say.reindex(karar_veren.index, fill_value=0) - karar_veren).abs().sum()
test("T2", "Karşı taraf kimliği: |karşı kimlik sayısı − karar veren sayısı| toplamı / karar veren toplamı",
     f"{fark}/{karar_veren.sum()} = {fark / karar_veren.sum():.3f}", "< 0.05", fark / karar_veren.sum() < 0.05)

d = s.dropna(subset=["decision", "decision_o"]).copy()
d["evet"] = d.decision.astype(float)
d["karsi_evet"] = d.decision_o.astype(float)
karsi_n = d.groupby("karsi").karsi_evet.transform("size")
d["karsi_secici_olmayan"] = d.groupby("karsi").karsi_evet.transform("mean")
d["karsi_ozgun"] = d.karsi_evet - d.karsi_secici_olmayan
oran5 = (d.groupby("karsi").size() >= 5).mean()
test("T3", "Karşı tarafların 'evet' oranı en az 5 buluşmadan hesaplanan payı", f"{oran5:.3f}", ">= 0.90", oran5 >= 0.90)
d["algilanan"] = d.guess_prob_liked


def kisi_ici(dd, sutunlar):
    xc = dd[sutunlar] - dd.groupby("kisi")[sutunlar].transform("mean")
    xc = xc / xc.std()
    yc = dd.evet - dd.groupby("kisi").evet.transform("mean")
    benzersiz, idx = np.unique(dd.kisi.to_numpy(), return_inverse=True)
    X, y = xc.to_numpy(), yc.to_numpy()
    k = X.shape[1]
    xtx = np.zeros((len(benzersiz), k, k))
    xty = np.zeros((len(benzersiz), k))
    np.add.at(xtx, idx, X[:, :, None] * X[:, None, :])
    np.add.at(xty, idx, X * y[:, None])
    return dict(sutunlar=sutunlar, xtx=xtx, xty=xty, yc=yc, n=len(dd), kisi=len(benzersiz), idx=idx)


def coz(m, ag=None):
    if ag is None:
        return np.linalg.solve(m["xtx"].sum(0), m["xty"].sum(0))
    return np.linalg.solve(np.tensordot(ag, m["xtx"], 1), ag @ m["xty"])


def boot(m):
    n = m["xtx"].shape[0]
    ag = rng.multinomial(n, np.full(n, 1 / n), size=BOOT).astype(float)
    return np.array([coz(m, a) for a in ag])


def model(dd, sutunlar, etiket):
    dd = dd.dropna(subset=sutunlar)
    m = kisi_ici(dd, sutunlar)
    b, dg = coz(m) * 100, boot(m) * 100
    lo, hi = np.percentile(dg, [2.5, 97.5], axis=0)
    return pd.DataFrame(dict(model=etiket, terim=[OZELLIK.get(c, AD.get(c, c)) for c in sutunlar], puan=b, lo=lo, hi=hi,
                             n=m["n"], kisi=m["kisi"])), m, dd


X6 = list(OZELLIK)
tablolar = []
for cins, ad in CINS:
    dc = d[d.gender == cins]
    t1, m1, dd1 = model(dc, X6 + ["algilanan"], "B1")
    t2, _, _ = model(dc, X6 + ["karsi_ozgun", "karsi_secici_olmayan"], "B2")
    t3, _, _ = model(dc, ["karsi_ozgun", "karsi_secici_olmayan"], "B3")
    for t in (t1, t2, t3):
        t.insert(0, "karar_veren", ad)
        tablolar.append(t)
    if cins == "female":
        ort = m1["yc"].groupby(dd1.kisi.to_numpy()).mean().abs().max()
        test("T4", "Kişi içi merkezleme (B1, kadın)", f"{ort:.2e}", "< 1e-9", ort < 1e-9)
kat = pd.concat(tablolar, ignore_index=True)
kat.to_csv(CIKTI / "katsayilar.csv", index=False, float_format="%.2f")
OZET["katsayilar"] = kat.round(2).to_dict("records")

cek = kat[(kat.model == "B1") & (kat.terim == "çekicilik")]
test("T5", "Kodlama kontrolü: B1'de çekicilik katsayısı alt sınırı iki cinsiyette > 0",
     ", ".join(f"{r.karar_veren} {r.lo:.1f}" for r in cek.itertuples()), "ikisi de > 0", bool((cek.lo > 0).all()))


def yon(lo, hi, ust, alt):
    return ust if lo > 0 else (alt if hi < 0 else "belirgin fark yok")


for _, ad in CINS:
    k = kat[kat.karar_veren == ad].set_index(["model", "terim"])
    r = k.loc[("B1", AD["algilanan"])]
    karar_kaydi(f"K1 ({ad})", f"'Benden hoşlanıyor' hissi {ad} karar verenin evet'ini artırıyor mu?",
                f"{r.puan:.1f} [{r.lo:.1f}, {r.hi:.1f}]", "evet" if r.lo > 0 else "hayır")
    r = k.loc[("B2", AD["karsi_ozgun"])]
    karar_kaydi(f"K2 ({ad})", "Seçici ilgi karşılık görüyor mu?", f"{r.puan:.1f} [{r.lo:.1f}, {r.hi:.1f}]",
                yon(r.lo, r.hi, "evet", "tersine"))
    r = k.loc[("B2", AD["karsi_secici_olmayan"])]
    karar_kaydi(f"K3 ({ad})", "Herkese ilgi gösteren daha az mı ilgi görüyor?", f"{r.puan:.1f} [{r.lo:.1f}, {r.hi:.1f}]",
                "evet, ters tepiyor" if r.hi < 0 else ("tersine, daha çok ilgi görüyor" if r.lo > 0 else "belirgin fark yok"))

# B4: ilgiyi okuma doğruluğu (kişi içi korelasyon)
for cins, ad in CINS:
    dd = d[(d.gender == cins)].dropna(subset=["algilanan"])
    a = (dd.algilanan - dd.groupby("kisi").algilanan.transform("mean")).to_numpy()
    b = (dd.karsi_evet - dd.groupby("kisi").karsi_evet.transform("mean")).to_numpy()
    benzersiz, idx = np.unique(dd.kisi.to_numpy(), return_inverse=True)
    sab = np.zeros(len(benzersiz)); saa = np.zeros(len(benzersiz)); sbb = np.zeros(len(benzersiz))
    np.add.at(sab, idx, a * b); np.add.at(saa, idx, a * a); np.add.at(sbb, idx, b * b)
    r0 = sab.sum() / np.sqrt(saa.sum() * sbb.sum())
    n = len(benzersiz)
    ag = rng.multinomial(n, np.full(n, 1 / n), size=BOOT).astype(float)
    rb = (ag @ sab) / np.sqrt((ag @ saa) * (ag @ sbb))
    lo, hi = np.percentile(rb, [2.5, 97.5])
    OZET[f"B4_{ad}"] = dict(r=r0, lo=lo, hi=hi, n=len(dd), kisi=n)
    guc = "zayıf" if r0 < 0.3 else ("orta" if r0 <= 0.5 else "güçlü")
    karar_kaydi(f"K4 ({ad})", f"{ad} karar verenler karşısındakinin ilgisini doğru okuyor mu?",
                f"r = {r0:.2f} [{lo:.2f}, {hi:.2f}]", (f"okuyor, {guc}" if lo > 0 else "okumuyor"))

# Grafik: B1 ve B2'deki karşılık terimleri
fig, ax = plt.subplots(figsize=(8, 3.6), facecolor=YUZEY)
ax.set_facecolor(YUZEY)
terimler = [("B1", AD["algilanan"]), ("B2", AD["karsi_ozgun"]), ("B2", AD["karsi_secici_olmayan"])]
for j, (ad, renk, kay) in enumerate((("kadın", KADIN, 0.13), ("erkek", ERKEK, -0.13))):
    for i, (mo, te) in enumerate(terimler):
        r = kat[(kat.karar_veren == ad) & (kat.model == mo) & (kat.terim == te)].iloc[0]
        y = len(terimler) - 1 - i + kay
        ax.hlines(y, r.lo, r.hi, color=renk, lw=2)
        ax.plot(r.puan, y, "o", ms=8, color=renk, mec=YUZEY, mew=2, label=f"karar veren: {ad}" if i == 0 else None)
ax.axvline(0, color=SOLUK, lw=1)
ax.set_yticks(range(len(terimler)), [t for _, t in terimler][::-1], color=MUR)
ax.set_xlabel("\"Evet\" olasılığındaki değişim (puan, 1 SS; %95 aralık)", color=MUR2)
ax.set_title("Karşılıklılık: ilgi görmek \"evet\"i ne kadar değiştiriyor? (kişi içi)", color=MUR, loc="left")
for k in ("top", "right"):
    ax.spines[k].set_visible(False)
for k in ("left", "bottom"):
    ax.spines[k].set_color(SOLUK)
ax.tick_params(colors=MUR2)
ax.grid(axis="x", color="#ecebe8", lw=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="lower right")
fig.tight_layout()
fig.savefig(CIKTI / "karsiliklilik.png", dpi=160)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET.update(testler=TESTLER, kararlar=KARARLAR, tohum=TOHUM, bootstrap=BOOT)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"Bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti.")
