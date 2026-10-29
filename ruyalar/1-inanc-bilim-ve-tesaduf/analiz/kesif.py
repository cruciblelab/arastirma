"""
ÖN KAYITSIZ KEŞİF (README "Bulgular", şeytanın avukatı itirazlarının kontrolü). calistir.py'den SONRA yazıldı.

    python kesif.py      (önce calistir.py çalışmış olmalı)

E6  "bit" kelimesi çıkarılınca ve hayvan ile saldırı kelimesi en fazla 8 kelime arayla geçmesi şartıyla hayvan saldırısı oranı
E7  Olumsuz içerik oranı rapor uzunluğuna göre (beşte birlik dilimler)
E8  Dizilerin eşit ağırlıklı ortalaması ve medyanı (tek kişilerin ağırlığını kaldırmak için); en büyük 5 dizinin payı
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
ozet = json.loads((CIKTI / "ozet.json").read_text(encoding="utf-8"))
L = ozet["kelime_listeleri"]


def desen(kelimeler):
    parca = [rf"{re.escape(k[:-1])}\w*" if k.endswith("*") else re.escape(k) for k in kelimeler]
    return re.compile(r"\b(?:" + "|".join(parca) + r")\b", re.IGNORECASE)


d = pd.read_csv(REPO / ".veri" / "ruya" / "dreambank_cortal.csv")
d = d.dropna(subset=["report"])
d = d[d.report.str.strip() != ""].drop_duplicates(subset=["report"]).reset_index(drop=True)
SONUC = {}

# E6
hayvan = desen(L["HAYVAN"])
saldiri_bitsiz = desen([k for k in L["SALDIRI"] if k != "bit"])


def yakin(t, en_fazla=8):
    kel = re.findall(r"\w+", t.lower())
    h = [i for i, w in enumerate(kel) if hayvan.fullmatch(w)]
    s = [i for i, w in enumerate(kel) if saldiri_bitsiz.fullmatch(w)]
    return any(abs(i - j) <= en_fazla for i in h for j in s)


d["HS_ham"] = d.report.apply(lambda t: bool(hayvan.search(t)) and bool(desen(L["SALDIRI"]).search(t)))
d["HS_bitsiz"] = d.report.apply(lambda t: bool(hayvan.search(t)) and bool(saldiri_bitsiz.search(t)))
d["HS_yakin"] = d.report.apply(yakin)
for k in ("HS_ham", "HS_bitsiz", "HS_yakin"):
    SONUC[f"E6_{k}"] = float(d[k].mean())
yalniz_bit = d.HS_ham & ~d.HS_bitsiz
SONUC["E6_yalniz_bit_payi"] = float(yalniz_bit.sum() / d.HS_ham.sum())
SONUC["E6_milyon_kisi_gecede_yakin"] = float(1e6 * (1 / 7) * d.HS_yakin.mean())

# E7
olumsuz = desen(L["OLAY"] + L["DUYGU"])
d["olumsuz"] = d.report.apply(lambda t: bool(olumsuz.search(t)))
d["uzunluk"] = d.report.str.split().str.len()
d["dilim"] = pd.qcut(d.uzunluk, 5, labels=False)
SONUC["E7_uzunluk_dilimleri"] = [dict(dilim=int(g), medyan_kelime=float(x.uzunluk.median()), olumsuz=float(x.olumsuz.mean()),
                                      hayvan_saldiri_yakin=float(x.HS_yakin.mean())) for g, x in d.groupby("dilim")]
SONUC["E7_medyan_kelime"] = float(d.uzunluk.median())

# E8
dizi = d.groupby("name").agg(n=("report", "size"), olumsuz=("olumsuz", "mean"), hs=("HS_yakin", "mean"))
SONUC["E8_dizi_esit_agirlik_olumsuz"] = float(dizi.olumsuz.mean())
SONUC["E8_dizi_medyan_olumsuz"] = float(dizi.olumsuz.median())
SONUC["E8_dizi_medyan_hs_yakin"] = float(dizi.hs.median())
SONUC["E8_en_buyuk_5_dizi_payi"] = float(dizi.n.nlargest(5).sum() / dizi.n.sum())

for k, v in SONUC.items():
    print(k, v)
(CIKTI / "kesif.json").write_text(json.dumps(SONUC, ensure_ascii=False, indent=1), encoding="utf-8")
