"""
ÖN KAYITSIZ KEŞİF (README "Bulgular" ve şeytanın avukatı itirazları). calistir.py'den SONRA yazıldı.

    python kesif.py      (önce calistir.py çalışmış olmalı; aynı .veri/ dosyalarını kullanır)

E1  Brezilya: partnerle yaşama ~ boy, eğitim katmanları içinde ve gelir eklenince (sosyoekonomik karıştırıcı mı?)
E2  Brezilya: yaş alt grupları (25-34 / 35-44)
E3  Sleiman: kadın boyuna göre uzun profil avantajı Türk kadın boy dağılımıyla ağırlıklandırılınca
E4  UvA: modelsiz kontrol — profil boy bantlarında ham seçilme oranı (kadın içi)
E5  Pisanski: kadının kendi boyuna göre tercihi ≤176 / ≤178 olma olasılığı (155-175 cm kadınlar)
"""

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
V = REPO / ".veri" / "boy-beklentisi"
ozet = json.loads((CIKTI / "ozet.json").read_text(encoding="utf-8"))
rng = np.random.default_rng(20261101)
SONUC = {}
TR_KADIN = (160.5, 6.62)
Z176 = ozet["turk_referans"]["z176"]

# ---------------------------------------------------------------- Brezilya verisi (calistir.py ile aynı tanımlar)
with zipfile.ZipFile(V / "pof0809_leitura.zip") as z:
    sas = z.read("SAS/Leitura dos Microdados - SAS.txt").decode("latin-1")
blok = sas[sas.find("T_MORADOR_S"):sas.find("T_MORADOR_IMPUT_S")]
duzen = {ad: (int(p) - 1, int(p) - 1 + int(g), int(o) if o else 0)
         for p, ad, g, o in re.findall(r"@(\d+)\s+(\w+)\s+\$?(\d+)\.(\d*)", blok)}
GEREK = ["COD_UF", "NUM_SEQ", "NUM_DV", "NUM_DOM", "NUM_UC", "COD_UPA", "PESO_FINAL", "COND_FAMILIA", "NUM_FAMILIA",
         "IDADE_ANOS", "V0405", "V0434", "ANOS_ESTUDO", "RENDA_PERCAPITA", "TIPO_SITUACAO_REG"]
with zipfile.ZipFile(V / "pof0809_dados.zip") as z:
    ham = z.read([n for n in z.namelist() if n.endswith("T_MORADOR_S.txt")][0])
br = pd.read_fwf(io.BytesIO(ham), colspecs=[duzen[a][:2] for a in GEREK], names=GEREK, dtype=str)
for a in GEREK:
    s = br[a].str.strip()
    v = pd.to_numeric(s, errors="coerce")
    if duzen[a][2]:
        v = np.where(s.str.contains(".", regex=False), v, v / 10 ** duzen[a][2])
    br[a] = v
br["boy"] = br.V0434.where(br.V0434.between(120, 215))
br["aile"] = br[["COD_UF", "NUM_SEQ", "NUM_DV", "NUM_DOM", "NUM_UC", "NUM_FAMILIA"]].astype("Int64").astype(str).agg("-".join, axis=1)
es_var = set(br.loc[br.COND_FAMILIA == 2, "aile"])
br["partnerli"] = ((br.COND_FAMILIA == 2) | ((br.COND_FAMILIA == 1) & br.aile.isin(es_var))).astype(float)
br["yas_grup"] = (br.IDADE_ANOS // 5) * 5
br["z"] = np.nan
for (e_, g), d in br[br.boy.notna() & br.IDADE_ANOS.between(20, 64)].groupby([br.V0405 == 1, "yas_grup"]):
    m = np.average(d.boy, weights=d.PESO_FINAL)
    br.loc[d.index, "z"] = (d.boy - m) / np.sqrt(np.average((d.boy - m) ** 2, weights=d.PESO_FINAL))
e = br[(br.V0405 == 1) & br.IDADE_ANOS.between(25, 44) & br.z.notna() & br.ANOS_ESTUDO.notna()].copy()
e["egitim"] = pd.cut(e.ANOS_ESTUDO, [-1, 7, 10, 30], labels=["0-7 yıl", "8-10 yıl", "11+ yıl"])
e["log_gelir"] = np.log1p(e.RENDA_PERCAPITA.clip(lower=0))
e["zband"] = pd.cut(e.z, [-9, -1.28, -0.5, 0.5, 1.0, 9], labels=["en kısa %10", "−1,28…−0,5", "−0,5…+0,5", "+0,5…+1", "+1 üstü"])


def wort(d, s):
    return float(np.average(d[s], weights=d.PESO_FINAL)) if len(d) else float("nan")


# E1: boy bantlarında partnerli oranı, eğitim katmanı içinde; boy-eğitim ve boy-gelir ilişkisi
SONUC["E1_boy_egitim_r"] = float(np.corrcoef(e.z, e.ANOS_ESTUDO)[0, 1])
SONUC["E1_boy_gelir_r"] = float(np.corrcoef(e.z, e.log_gelir)[0, 1])
SONUC["E1_egitim_partnerli"] = {str(k): wort(d, "partnerli") for k, d in e.groupby("egitim", observed=True)}
tab = {}
for k, d in e.groupby("egitim", observed=True):
    tab[str(k)] = {str(b): [wort(dd, "partnerli"), len(dd)] for b, dd in d.groupby("zband", observed=True)}
SONUC["E1_bant_x_egitim"] = tab


def dogrusal_olasilik(d, terimler):
    X = np.column_stack([np.ones(len(d))] + [d[t].to_numpy(float) for t in terimler])
    w = d.PESO_FINAL.to_numpy()
    b = np.linalg.solve(X.T @ (X * w[:, None]), X.T @ (w * d.partnerli.to_numpy()))
    return b


e["z_ust"] = np.maximum(e.z, 0)
e["z_alt"] = np.minimum(e.z, 0)
yas_d = pd.get_dummies(e.yas_grup, prefix="y", drop_first=True).astype(float)
uf_d = pd.get_dummies(e.COD_UF, prefix="uf", drop_first=True).astype(float)
e2 = pd.concat([e, yas_d, uf_d], axis=1)
kontrol = list(yas_d.columns)
modeller = {"yas": kontrol, "+egitim+eyalet": kontrol + ["ANOS_ESTUDO"] + list(uf_d.columns),
            "+egitim+eyalet+gelir": kontrol + ["ANOS_ESTUDO", "log_gelir"] + list(uf_d.columns)}
upa, idx = np.unique(e2.COD_UPA, return_inverse=True)
E1m = {}
for ad, kon in modeller.items():
    ter = ["z_alt", "z_ust"] + kon
    b0 = dogrusal_olasilik(e2, ter)
    dg = []
    for _ in range(300):
        say = rng.multinomial(len(upa), np.full(len(upa), 1 / len(upa)))[idx]
        dd = e2.assign(PESO_FINAL=e2.PESO_FINAL * say)
        dg.append(dogrusal_olasilik(dd, ter)[1:3])
    dg = 100 * np.array(dg)
    E1m[ad] = {"medyan_alti_egim_yp_per_SS": [100 * b0[1], *np.percentile(dg[:, 0], [2.5, 97.5])],
               "medyan_ustu_egim_yp_per_SS": [100 * b0[2], *np.percentile(dg[:, 1], [2.5, 97.5])]}
SONUC["E1_parcali_dogrusal"] = E1m

# E2: yaş alt grupları
SONUC["E2_yas_alt_grup"] = {ad: {str(b): wort(dd, "partnerli") for b, dd in d.groupby("zband", observed=True)}
                            for ad, d in (("25-34", e[e.IDADE_ANOS <= 34]), ("35-44", e[e.IDADE_ANOS >= 35]))}

# E3: Sleiman — Türk kadın dağılımıyla ağırlıklandırma
b4 = ozet["B4_SL_kendi_boy"]
p_alt = norm.cdf((160 - TR_KADIN[0]) / TR_KADIN[1])
p_ust = 1 - norm.cdf((170 - TR_KADIN[0]) / TR_KADIN[1])
agirlik = {"<160": p_alt, "160-169.9": 1 - p_alt - p_ust, ">=170": p_ust}
SONUC["E3_TR_agirlik"] = agirlik
SONUC["E3_TR_agirlikli_uzun_etkisi_yp"] = float(sum(agirlik[k] * b4[k]["uzun_etkisi"][0] for k in agirlik))
SONUC["E3_orneklem_uzun_etkisi_yp"] = ozet["B3_SL"]["uzun"][0]

# E4: UvA modelsiz kontrol
u = pd.read_csv(REPO / ".veri" / "cekicilik" / "uva_conjoint_kadin.csv", sep=";", decimal=",", encoding="utf-8-sig")
u["y"] = u.Response * 100
u["yc"] = u.y - u.groupby("Participants").y.transform("mean") + u.y.mean()
u["bant"] = pd.cut(u.Height, [169, 172, 175, 177, 179, 182, 185, 189],
                   labels=["170-172", "173-175", "176-177", "178-179", "180-182", "183-185", "186-189"])
kisiler = u.Participants.unique()
bant_ort = u.groupby("bant", observed=True).yc.mean()
dg = []
for _ in range(1000):
    sec = rng.choice(kisiler, len(kisiler))
    say = pd.Series(sec).value_counts()
    w = u.Participants.map(say).fillna(0)
    dg.append(u.assign(w=w).groupby("bant", observed=True).apply(lambda d: np.average(d.yc, weights=d.w) if d.w.sum() else np.nan,
                                                                  include_groups=False))
dg = pd.DataFrame(dg)
SONUC["E4_UV_bant_secilme_yp"] = {str(k): [float(bant_ort[k]), *map(float, np.nanpercentile(dg[k], [2.5, 97.5]))]
                                  for k in bant_ort.index}

# E5: Pisanski modeli — kadının boyuna göre
A = ozet["A_soylenen"]
a, b, s = A["a_165"], A["egim"], A["s"]
SONUC["E5_kadin_boyuna_gore"] = {int(kb): {"medyan_tercih": a + b * (kb - 165),
                                           "tercihi_<=176": float(norm.cdf((176 - a - b * (kb - 165)) / s)),
                                           "tercihi_<=178": float(norm.cdf((178 - a - b * (kb - 165)) / s))}
                                 for kb in (150, 155, 160, 165, 170, 175)}

for k, v in SONUC.items():
    print(k, json.dumps(v, ensure_ascii=False, default=float)[:600])
(CIKTI / "kesif.json").write_text(json.dumps(SONUC, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
