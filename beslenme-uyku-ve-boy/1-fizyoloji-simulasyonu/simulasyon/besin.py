"""
Besin katmanı (PLAN 3.1): USDA FoodData Central SR Legacy'den yiyeceklerin 100 g başına
besin vektörleri ve diyet sepetleri. Ham veri repoya konmaz (.veri/ önbelleği), SHA-256 ile doğrulanır.
"""

import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ONBELLEK = Path(__file__).parent / ".veri"
USDA = dict(
    url="https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip",
    sha256="b80817294b8850530aaedf2e515c02593b1824f763a0ff356e5c2081643e6fd0",
    dosya="FoodData_Central_sr_legacy_food_csv_2018-04.zip")
ALT = "FoodData_Central_sr_legacy_food_csv_2018-04/"

BESINLER = {1008: "kcal", 1003: "protein_g", 1004: "yag_g", 1258: "doymus_yag_g", 1005: "karbonhidrat_g",
            1079: "lif_g", 1087: "kalsiyum_mg", 1089: "demir_mg", 1095: "cinko_mg", 1114: "d_vitamini_ug"}

YIYECEKLER = {
    "kiyma": 171797, "tavuk": 171477, "yumurta": 171287, "sut": 171265, "yogurt": 171284,
    "beyaz_peynir": 173420, "somon": 175168, "hamsi": 174182, "tereyagi": 173410,
    "mercimek": 172421, "nohut": 173757, "kuru_fasulye": 175203, "ekmek": 172686, "pirinc": 168878,
    "bulgur": 170287, "makarna": 169737, "patates": 170438, "domates": 170457, "ispanak": 168462,
    "elma": 171688, "muz": 173944, "salatalik": 168409, "portakal": 169097, "zeytinyagi": 171413,
    "ceviz": 170187, "kola": 174852, "seker": 169655, "hamburger": 170694, "cips": 169677,
}

_B1 = dict(ekmek=200, bulgur=150, pirinc=100, patates=150, mercimek=150, nohut=100, tavuk=80, yumurta=50,
           sut=250, yogurt=200, beyaz_peynir=40, domates=150, salatalik=100, ispanak=80, elma=150,
           portakal=150, muz=100, zeytinyagi=30, ceviz=20, seker=20)
SEPETLER = {
    "B1 Dengeli": _B1,
    "B2 Fast food": dict(hamburger=300, cips=100, kola=660, ekmek=100, pirinc=150, tavuk=50, sut=100,
                         tereyagi=15, seker=30, elma=100, domates=50),
    "B3 Düşük protein": dict(ekmek=200, pirinc=250, patates=300, seker=70, zeytinyagi=60, domates=200,
                             salatalik=150, elma=200, muz=150, kola=500, portakal=150),
    "B4 Yüksek protein": {**_B1, "tavuk": 250, "yumurta": 100, "sut": 400, "yogurt": 300, "ekmek": 100,
                          "seker": 0, "zeytinyagi": 20},
    "B5 Etsiz": {**_B1, "tavuk": 0, "mercimek": 250, "nohut": 150, "yumurta": 100},
}

# DRI 14-18 yaş (RDA); PLAN 3.5d
RDA = {"erkek": dict(kalsiyum_mg=1300, demir_mg=11, cinko_mg=11, d_vitamini_ug=15),
       "kiz": dict(kalsiyum_mg=1300, demir_mg=15, cinko_mg=9, d_vitamini_ug=15)}


def _indir() -> Path:
    ONBELLEK.mkdir(exist_ok=True)
    hedef = ONBELLEK / USDA["dosya"]
    if not hedef.exists():
        istek = urllib.request.Request(USDA["url"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(istek, timeout=300) as r:
            hedef.write_bytes(r.read())
    ozet = hashlib.sha256(hedef.read_bytes()).hexdigest()
    if ozet != USDA["sha256"]:
        hedef.unlink()
        raise RuntimeError(f"USDA: SHA-256 uyuşmuyor ({ozet}); dosya silindi.")
    return hedef


def yiyecek_tablosu():
    """Seçilen yiyeceklerin 100 g başına besin değerleri (satır: yiyecek). Eksik kayıt sayısını da döndürür."""
    z = zipfile.ZipFile(_indir())
    food = pd.read_csv(io.BytesIO(z.read(ALT + "food.csv")), usecols=["fdc_id", "description"])
    fn = pd.read_csv(io.BytesIO(z.read(ALT + "food_nutrient.csv")), usecols=["fdc_id", "nutrient_id", "amount"])
    ids = list(YIYECEKLER.values())
    fn = fn[fn.fdc_id.isin(ids) & fn.nutrient_id.isin(list(BESINLER))]
    t = fn.pivot_table(index="fdc_id", columns="nutrient_id", values="amount", aggfunc="first")
    t = t.reindex(index=ids, columns=list(BESINLER))
    eksik = {BESINLER[c]: [k for k, i in YIYECEKLER.items() if pd.isna(t.loc[i, c])] for c in t.columns}
    t = t.fillna(0.0).rename(columns=BESINLER)       # PLAN sapma (d): eksik kayıt = 0
    t.index = list(YIYECEKLER)
    t.insert(0, "fdc_id", ids)
    t.insert(1, "usda_aciklama", food.set_index("fdc_id").loc[ids, "description"].values)
    assert (t.kcal > 0).all(), "enerjisi sıfır yiyecek: yanlış fdc_id?"
    return t, {k: v for k, v in eksik.items() if v}


def sepet_icerigi(tablo, sepet):
    """Sepetin günlük besin içeriği (ölçeklenmemiş)."""
    g = pd.Series(sepet, dtype=float)
    return (tablo.loc[g.index, list(BESINLER.values())].mul(g / 100.0, axis=0)).sum()


def sepet_profili(tablo, sepet, kcal_hedef, cinsiyet, kilo):
    """Sepet, kcal_hedef'e orantılı ölçeklenmiş haliyle: makro yüzdeleri ve RDA yüzdeleri."""
    ham = sepet_icerigi(tablo, sepet)
    s = ham * (kcal_hedef / ham.kcal)
    p = dict(kcal=s.kcal, protein_g=s.protein_g, protein_g_kg=s.protein_g / kilo,
             protein_g_1000kcal=1000 * ham.protein_g / ham.kcal,
             enerji_protein_yuzde=100 * 4 * s.protein_g / s.kcal, enerji_yag_yuzde=100 * 9 * s.yag_g / s.kcal,
             enerji_doymus_yag_yuzde=100 * 9 * s.doymus_yag_g / s.kcal,
             enerji_karbonhidrat_yuzde=100 * 4 * s.karbonhidrat_g / s.kcal, lif_g=s.lif_g)
    for k, v in RDA[cinsiyet].items():
        p[k] = s[k]
        p[k.split("_")[0] + "_rda_yuzde"] = 100 * s[k] / v
    return p


def protein_yogunlugu(tablo, sepet):
    """g protein / kcal (sepet ölçeklendiğinde sabit)."""
    ham = sepet_icerigi(tablo, sepet)
    return float(ham.protein_g / ham.kcal)
