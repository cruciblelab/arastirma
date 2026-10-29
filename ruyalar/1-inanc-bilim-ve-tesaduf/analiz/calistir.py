"""
Rüyalar, sürüm 1: DreamBank içerik sayımı (README "DreamBank içerik analizi (ön kayıt)"). Tek komut:

    python calistir.py

Veri (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur):
  DreamBank (Domhoff ve Schneider; CC BY-NC-SA 4.0), Cortal'ın Hugging Face kopyası gustavecortal/DreamBank-annotated
Ölçüler D1-D4; teknik testler T5-T7; karar kuralı K6. Kesinlik kontrolü örnekleri .veri/ altına yazılır (metinler repoya girmez).
"""

import hashlib
import json
import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
VERI_DIZIN = REPO / ".veri" / "ruya"
TOHUM = 20261029
VERI = dict(url="https://huggingface.co/datasets/gustavecortal/DreamBank-annotated/resolve/main/train.csv",
            sha256="aacabafe17adf3d407482630e60502dc9216d766c42c167f849afde91c1e7447",
            dosya=VERI_DIZIN / "dreambank_cortal.csv")
TESTLER, KARARLAR, OZET = [], [], {}

LISTE = {
    "OLAY": ["die", "dies", "died", "dying", "dead", "death", "kill*", "accident*", "crash*", "fell", "fall", "falling",
             "injur*", "hurt*", "bleed*", "blood*", "sick*", "hospital*", "lost", "lose", "losing", "fail*", "broke",
             "broken", "fire", "burn*", "drown*", "attack*", "chase*", "chasing", "fight*", "fought", "stab*", "shot",
             "shoot*", "bite", "bit", "bites", "biting", "bitten"],
    "DUYGU": ["afraid", "scared", "fear*", "terrif*", "panic*", "anxious", "anxiety", "worr*", "scream*", "cry", "cried",
              "crying", "upset", "angry", "anger", "sad", "sadness"],
    "HAYVAN": ["animal*", "cat", "cats", "kitten*", "dog", "dogs", "puppy", "puppies", "horse*", "bird*", "snake*",
               "spider*", "rat", "rats", "mouse", "mice", "lion*", "tiger*", "wolf", "wolves", "shark*", "bee", "bees",
               "monkey*", "cow", "cows", "pig", "pigs", "insect*", "bug", "bugs"],
    "SALDIRI": ["bite", "bit", "bites", "biting", "bitten", "scratch*", "attack*", "claw*", "sting*", "stung"],
    "KEDI": ["cat", "cats", "kitten*"],
    "ISIRMA": ["bite", "bit", "bites", "biting", "bitten"],
}


def desen(kelimeler):
    parca = [rf"{re.escape(k[:-1])}\w*" if k.endswith("*") else re.escape(k) for k in kelimeler]
    return re.compile(r"\b(?:" + "|".join(parca) + r")\b", re.IGNORECASE)


DESEN = {ad: desen(k) for ad, k in LISTE.items()}


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    print(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'}  ({deger})", flush=True)


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    m = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return m - h, m + h


def indir(v):
    if not v["dosya"].exists():
        v["dosya"].parent.mkdir(parents=True, exist_ok=True)
        istek = urllib.request.Request(v["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
        with urllib.request.urlopen(istek, timeout=300) as r:
            v["dosya"].write_bytes(r.read())
    return hashlib.sha256(v["dosya"].read_bytes()).hexdigest()


sha = indir(VERI)
test("T5", "Veri bütünlüğü: SHA-256", "eşleşti" if sha == VERI["sha256"] else "UYUŞMADI", "eşleşir", sha == VERI["sha256"])

# T7: düzenli ifade kontrolü (sabit örnek cümleler)
ornek = {
    "the cat bit my hand": {"HAYVAN": True, "SALDIRI": True, "KEDI": True, "ISIRMA": True},
    "I caught a bus": {"HAYVAN": False, "SALDIRI": False, "OLAY": False, "DUYGU": False},
    "bitter coffee": {"SALDIRI": False, "ISIRMA": False},
}
hatali = [(c, ad) for c, beklenen in ornek.items() for ad, b in beklenen.items() if bool(DESEN[ad].search(c)) != b]
test("T7", "Düzenli ifade kontrolü (sabit örnek cümleler)", "hata yok" if not hatali else str(hatali), "hata yok",
     not hatali)

d = pd.read_csv(VERI["dosya"])
n_ham = len(d)
d = d.dropna(subset=["report"])
d = d[d.report.str.strip() != ""]
d = d.drop_duplicates(subset=["report"]).reset_index(drop=True)
test("T6", "Temizlikten sonra rapor sayısı (boş ve birebir tekrarlar atıldı)", f"{n_ham} → {len(d)}", ">= 27000",
     len(d) >= 27000)

for ad, p in DESEN.items():
    d[ad] = d.report.apply(lambda t, p=p: bool(p.search(t)))
d["OLAY_YA_DA_DUYGU"] = d.OLAY | d.DUYGU
d["HAYVAN_VE_SALDIRI"] = d.HAYVAN & d.SALDIRI
d["KEDI_VE_ISIRMA"] = d.KEDI & d.ISIRMA

OLCU = ["OLAY", "DUYGU", "OLAY_YA_DA_DUYGU", "HAYVAN", "HAYVAN_VE_SALDIRI", "KEDI_VE_ISIRMA"]
gruplar = {
    "Tümü": d,
    "Hall ve Van de Castle normları": d[d.name.isin(["Hall/VdC Norms: Male", "Hall/VdC Norms: Female"])],
    "Kadın rüyacılar": d[d.gender == "F"],
    "Erkek rüyacılar": d[d.gender == "M"],
}
satir = []
for g, dd in gruplar.items():
    for o in OLCU:
        k, n = int(dd[o].sum()), len(dd)
        lo, hi = wilson(k, n)
        satir.append(dict(grup=g, olcu=o, rapor=n, sayi=k, oran=k / n, lo=lo, hi=hi))
oran = pd.DataFrame(satir)
oran.to_csv(CIKTI / "oranlar.csv", index=False, float_format="%.4f")
print(oran.round(4).to_string(index=False))

# D3: uzun dizilerde kişi bazında dağılım
uzun = d.groupby("name").filter(lambda x: len(x) >= 200)
kisi = uzun.groupby("name").agg(rapor=("report", "size"), olay_ya_da_duygu=("OLAY_YA_DA_DUYGU", "mean"),
                                hayvan=("HAYVAN", "mean"), hayvan_ve_saldiri=("HAYVAN_VE_SALDIRI", "mean"))
kisi.to_csv(CIKTI / "uzun_diziler.csv", float_format="%.4f")
OZET["D3"] = dict(dizi=int(len(kisi)), medyan=float(kisi.olay_ya_da_duygu.median()),
                  en_dusuk=float(kisi.olay_ya_da_duygu.min()), en_yuksek=float(kisi.olay_ya_da_duygu.max()))

tum = oran[oran.grup == "Tümü"].set_index("olcu")
OZET["D1"] = {o: dict(oran=float(tum.loc[o, "oran"]), lo=float(tum.loc[o, "lo"]), hi=float(tum.loc[o, "hi"]))
              for o in OLCU}
OZET["D4_p_neg"] = float(tum.loc["OLAY_YA_DA_DUYGU", "oran"])
OZET["rapor"] = int(len(d))

# K6: hayvan saldırısı rüyası nadir mi? Milyon kişide gecede (haftada 1 hatırlanan rüya varsayımı)
hs = float(tum.loc["HAYVAN_VE_SALDIRI", "oran"])
milyon = 1e6 * (1 / 7) * hs
karar = "nadir (%5'in altında)" if hs < 0.05 else "nadir değil (%5 ve üstü)"
KARARLAR.append(dict(kural="K6", soru="Hayvan ve saldırı birlikte geçen rüya nadir mi?",
                     deger=f"%{hs * 100:.2f}; milyon kişide gecede ~{milyon:,.0f} hatırlanan rapor", karar=karar))
print("K6:", karar, f"%{hs * 100:.2f}", f"milyonda gecede ~{milyon:,.0f}")

# Kesinlik kontrolü örnekleri (metinler repoya girmez)
rng = np.random.default_rng(TOHUM)
orn = []
for o in ("OLAY_YA_DA_DUYGU", "HAYVAN_VE_SALDIRI"):
    idx = d.index[d[o]].to_numpy()
    sec = rng.choice(idx, size=min(30, len(idx)), replace=False)
    for i in sec:
        orn.append(dict(liste=o, id=d.loc[i, "id"], dizi=d.loc[i, "name"], rapor=d.loc[i, "report"]))
pd.DataFrame(orn).to_csv(VERI_DIZIN / "kesinlik_ornekleri.csv", index=False)
pd.DataFrame(orn)[["liste", "id", "dizi"]].to_csv(CIKTI / "kesinlik_ornek_kimlikleri.csv", index=False)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET.update(testler=TESTLER, kararlar=KARARLAR, tohum=TOHUM, kelime_listeleri=LISTE)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti.")
