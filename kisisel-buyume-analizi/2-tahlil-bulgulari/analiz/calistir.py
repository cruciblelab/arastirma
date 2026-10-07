"""
Seçilmiş tahlil değerlerinin değerlendirmesi (sürüm 2). Tek komut:

    python calistir.py

Girdi: tahlil_secilmis.csv (veri sahibinin isteğiyle yayınlanan, kimliksizleştirilmiş seçilmiş değerler).
Çıktı: ciktilar/tahlil_degerlendirme.csv, ciktilar/ozet.json

Her değer iki ölçüte göre işaretlenir:
  1) Laboratuvarın kendi referans aralığı (raporda yazan).
  2) Varsa yayınlanmış eşik: D vitamini ≥ 20 ng/mL (IOM 2011); ferritin < 15 µg/L, 10-19 yaş, iltihap
     yokken demir eksikliği (DSÖ 2020; iltihap varsa < 70). İltihap durumu aynı tahlildeki CRP'den okunur.
Yorum tıbbi tavsiye değildir; karar hekime aittir.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).parent
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)

t = pd.read_csv(KOK / "tahlil_secilmis.csv")


def lab_durum(r):
    if pd.notna(r.lab_alt) and r.deger < r.lab_alt:
        return "laboratuvar aralığının altında"
    if pd.notna(r.lab_ust) and r.deger > r.lab_ust:
        return "laboratuvar aralığının üstünde"
    if pd.isna(r.lab_alt) and pd.isna(r.lab_ust):
        return "laboratuvar aralık vermemiş"
    return "laboratuvar aralığında"


t["lab_durum"] = t.apply(lab_durum, axis=1)
t["yayinlanmis_esik"] = ""
t["esige_gore"] = ""

crp = t[(t.test == "CRP")].set_index("yas").deger
for i, r in t.iterrows():
    if r.test == "25-OH D vitamini":
        t.loc[i, "yayinlanmis_esik"] = "≥ 20 ng/mL nüfusun %97.5'inin ihtiyacını karşılar (IOM 2011)"
        t.loc[i, "esige_gore"] = "eşiğin altında" if r.deger < 20 else "eşikte ya da üstünde"
    if r.test == "Ferritin":
        iltihap = r.yas in crp.index and crp[r.yas] > 5
        esik = 70 if iltihap else 15
        t.loc[i, "yayinlanmis_esik"] = f"< {esik} µg/L demir eksikliği (DSÖ 2020, 10-19 yaş, {'iltihap var' if iltihap else 'iltihap yok, CRP normal'})"
        t.loc[i, "esige_gore"] = "eksiklik eşiğinin altında" if r.deger < esik else "eksiklik eşiğinin üstünde (sınırda)"

fe = t[(t.test == "Demir")].set_index("yas").deger
tibc = t[(t.test.str.startswith("Demir bağlama"))].set_index("yas").deger
tsat = {float(y): round(100 * fe[y] / tibc[y], 1) for y in fe.index if y in tibc.index}

t.to_csv(CIKTI / "tahlil_degerlendirme.csv", index=False)
ozet = dict(
    n_deger=int(len(t)),
    lab_disi=t[t.lab_durum.str.contains("altında|üstünde")][["yas", "test", "deger", "birim", "lab_durum"]].to_dict("records"),
    esik_karsilastirma=t[t.esige_gore != ""][["yas", "test", "deger", "esige_gore"]].to_dict("records"),
    transferrin_doygunlugu_yuzde=tsat,
    hemoglobin_seyri=t[t.test == "Hemoglobin"][["yas", "deger"]].to_dict("records"),
)
(CIKTI / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print(t[["yas", "test", "deger", "birim", "lab_durum", "esige_gore"]].to_string(index=False))
print("transferrin doygunluğu %:", tsat)
