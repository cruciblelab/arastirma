"""
ÖN KAYITSIZ KEŞİF (README "Bulgular" ve şeytanın avukatı itirazları). calistir.py'den SONRA yazıldı.

    python kesif.py      (önce calistir.py çalışmış olmalı; aynı .veri/ dosyalarını kullanır)

E1  Brezilya: partnerle yaşama ~ boy, eğitim katmanları içinde ve gelir eklenince (sosyoekonomik karıştırıcı mı?)
E2  Brezilya: yaş alt grupları (25-34 / 35-44)
E3  Sleiman: kadın boyuna göre uzun profil avantajı Türk kadın boy dağılımıyla ağırlıklandırılınca
E4  UvA: modelsiz kontrol — profil boy bantlarında ham seçilme oranı (kadın içi)
E5  Pisanski: kadının kendi boyuna göre tercihi ≤176 / ≤178 olma olasılığı (155-175 cm kadınlar)
Şeytanın avukatı itirazlarının kontrolü (faz 3 sonrası eklendi):
E6  Brezilya: asıl karşılaştırma 176 → daha uzun (178, 183) — 25-44 ve 35-44 yaş
E7  UvA: basit doğrusal model (yp/cm) ve kadının boyuna göre alt gruplar
E8  Pisanski: silüet sınırları ±1 cm kaydırılınca (176 ile 178 arasındaki tek sınır 177,5)
E9  Brezilya H7: rastgele eşleşme eyalet × kent/kır × yaş × eğitim katmanları içinde
E10 Stulp aktarımı: kendi boy ile fark arasındaki r = −0,49 ile tutarlı eğim
Not: E1'deki "+gelir" modeli yorumlanamaz; kişi başı hane geliri partnerli olmanın sonucudur (eş, çocuk).
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


# ---------------------------------------------------------------- E6: 176 → daha uzun (Brezilya)
TR_ERKEK = (174.7, 6.88)
Z = {h: (h - TR_ERKEK[0]) / TR_ERKEK[1] for h in (176, 178, 183)}


def rcs(x, k):
    x = np.asarray(x, float)
    s = (k[-1] - k[0]) ** 2
    pos = lambda v: np.maximum(v, 0) ** 3
    sut = [x]
    for j in range(len(k) - 2):
        sut.append((pos(x - k[j]) - pos(x - k[-2]) * (k[-1] - k[j]) / (k[-1] - k[-2])
                    + pos(x - k[-1]) * (k[-2] - k[j]) / (k[-1] - k[-2])) / s)
    return np.column_stack(sut)


def logit(X, y, w, b=None, it=25):
    b = np.zeros(X.shape[1]) if b is None else b.copy()
    for _ in range(it):
        pr = 1 / (1 + np.exp(-np.clip(X @ b, -30, 30)))
        adim = np.linalg.solve(X.T @ (X * (w * pr * (1 - pr))[:, None]) + 1e-8 * np.eye(X.shape[1]), X.T @ (w * (y - pr)))
        b += adim
        if np.abs(adim).max() < 1e-8:
            break
    return b


def fark_176(d, B=300):
    dug = np.percentile(d.z, [5, 27.5, 50, 72.5, 95])
    yd = pd.get_dummies(d.yas_grup, drop_first=True).to_numpy(float)
    X = np.column_stack([np.ones(len(d)), rcs(d.z, dug), yd])
    y, w = d.partnerli.to_numpy(), (d.PESO_FINAL / d.PESO_FINAL.mean()).to_numpy()

    def tah(b, w):
        geri = X[:, 5:] @ b[5:]
        p = {h: np.average(1 / (1 + np.exp(-(b[0] + rcs([zv], dug)[0] @ b[1:5] + geri))), weights=w) for h, zv in Z.items()}
        return {"178-176": 100 * (p[178] - p[176]), "183-176": 100 * (p[183] - p[176])}
    b0 = logit(X, y, w)
    t0 = tah(b0, w)
    up, ix = np.unique(d.COD_UPA, return_inverse=True)
    dg = []
    for _ in range(B):
        wb = w * rng.multinomial(len(up), np.full(len(up), 1 / len(up)))[ix]
        dg.append(tah(logit(X, y, wb, b0, it=8), wb))
    dg = pd.DataFrame(dg)
    return {k: [float(t0[k]), *map(float, np.percentile(dg[k], [2.5, 97.5]))] for k in t0}


SONUC["E6_176dan_uzuna"] = {"25-44": fark_176(e), "35-44": fark_176(e[e.IDADE_ANOS >= 35].reset_index(drop=True))}

# ---------------------------------------------------------------- E7: UvA doğrusal ve alt gruplar
u["kendi"] = u["Height.in.cm"].astype(float)
for k_, s_ in (("cek", "Attractiveness"), ("iq", "Intelligence"), ("bio", "Bio"), ("mes", "Occupation")):
    v_ = np.unique(u[s_].to_numpy(float))
    u[k_] = (u[s_] - v_.mean()) / v_.std(ddof=1)


def uv_egim(d, B=1000):
    X = d[["Height", "cek", "iq", "bio", "mes"]].to_numpy(float)
    benz, idx = np.unique(d.Participants, return_inverse=True)
    Xc = X - pd.DataFrame(X).groupby(idx).transform("mean").to_numpy()
    yc = d.y.to_numpy() - d.groupby("Participants").y.transform("mean").to_numpy()
    xtx = np.zeros((len(benz), 5, 5))
    xty = np.zeros((len(benz), 5))
    np.add.at(xtx, idx, Xc[:, :, None] * Xc[:, None, :])
    np.add.at(xty, idx, Xc * yc[:, None])
    b = np.linalg.solve(xtx.sum(0), xty.sum(0))[0]
    ag = rng.multinomial(len(benz), np.full(len(benz), 1 / len(benz)), size=B).astype(float)
    dg = np.array([np.linalg.solve(np.tensordot(a_, xtx, 1), a_ @ xty)[0] for a_ in ag])
    return {"kadin": len(benz), "yp_per_cm": [float(b), *map(float, np.percentile(dg, [2.5, 97.5]))],
            "2cm_yp": [float(2 * b), *map(float, 2 * np.percentile(dg, [2.5, 97.5]))]}


SONUC["E7_UV_dogrusal"] = {"tumu": uv_egim(u), "kadin<=163": uv_egim(u[u.kendi <= 163]),
                           "kadin164-169": uv_egim(u[u.kendi.between(164, 169)]), "kadin>=170": uv_egim(u[u.kendi >= 170])}

# ---------------------------------------------------------------- E8: Pisanski sınır kaydırma
from scipy.optimize import minimize

pi = pd.read_excel(V / "pisanski2022.xlsx")
pi["Height"] = pd.to_numeric(pi.Height, errors="coerce")
pi["HEIGHTpref_CM"] = pd.to_numeric(pi.HEIGHTpref_CM, errors="coerce")
pi = pi[(pi.Sex == "Female") & pi.Preferredsex_selfreport.isin(["PrefersOppositeSex", "FePrefersOppositeSex"])
        & (pi.Relationship_context == "LongTerm")].dropna(subset=["Height", "HEIGHTpref_CM"])
pi = pi[pi.Height.between(130, 210)].drop_duplicates("ID_NUMBER")
G = np.array([165, 170, 175, 180, 185.0])


def sil(g, k):
    return (-np.inf if g == 165 else g - 2.5 + k), (np.inf if g == 185 else g + 2.5 + k)


def ara(v, k):
    if v in G:
        return sil(v, k)
    if v % 5 == 2.5 and 165 < v < 185:
        return sil(v - 2.5, k)[0], sil(v + 2.5, k)[1]
    return sil(G[np.abs(G - v).argmin()], k)


UL = ["Canada", "Cuba", "Norway", "USA"]
Xp = np.column_stack([np.ones(len(pi)), pi.Height - 165] +
                     [(pi.Country == c).astype(float) - (pi.Country == UL[0]).astype(float) for c in UL[1:]])
E8 = {}
for kay in (-1.0, 0.0, 1.0):
    lo, hi = map(np.array, zip(*pi.HEIGHTpref_CM.map(lambda v: ara(v, kay))))
    nll = lambda t: -np.log(np.clip(norm.cdf((hi - Xp @ t[:-1]) / np.exp(t[-1])) - norm.cdf((lo - Xp @ t[:-1]) / np.exp(t[-1])),
                                    1e-300, None)).sum()
    r = minimize(nll, np.r_[178, 0.3, 0, 0, 0, np.log(5)], method="BFGS")
    a, b, s = r.x[0], r.x[1], np.exp(r.x[-1])
    sd = np.sqrt(s ** 2 + (b * TR_KADIN[1]) ** 2)
    mu = a + b * (TR_KADIN[0] - 165)
    E8[f"{kay:+.0f} cm"] = {h: float(norm.cdf((h - mu) / sd)) for h in (174.7, 176, 178, 180)}
SONUC["E8_PI_sinir_kaydirma"] = E8

# ---------------------------------------------------------------- E9: H7 katmanlı rastgele eşleşme
ref, es = br[br.COND_FAMILIA == 1], br[br.COND_FAMILIA == 2]
cf = ref.merge(es, on="aile", suffixes=("_r", "_e"))
cf = cf[cf.V0405_r != cf.V0405_e]
er = (cf.V0405_r == 1).to_numpy()
for v_ in ("boy", "IDADE_ANOS", "ANOS_ESTUDO"):
    cf[v_ + "_E"] = np.where(er, cf[v_ + "_r"], cf[v_ + "_e"])
    cf[v_ + "_K"] = np.where(er, cf[v_ + "_e"], cf[v_ + "_r"])
cf = cf[(cf.IDADE_ANOS_E >= 20) & (cf.IDADE_ANOS_K >= 20)].dropna(subset=["boy_E", "boy_K"]).reset_index(drop=True)
cf["katman"] = (cf.COD_UF_r.astype(str) + "-" + cf.TIPO_SITUACAO_REG_r.astype(str) + "-" + (cf.IDADE_ANOS_E // 10).astype(str)
                + "-" + pd.cut(cf.ANOS_ESTUDO_E.fillna(-1), [-2, -0.5, 7, 10, 30], labels=False).astype(str))
he, hk = cf.boy_E.to_numpy(), cf.boy_K.to_numpy()
gr = list(cf.groupby("katman").indices.values())
sonuc = []
for _ in range(300):
    hk2 = hk.copy()
    for ix in gr:
        hk2[ix] = hk[rng.permutation(ix)]
    sonuc.append((hk2 > he).mean())
SONUC["E9_H7_katmanli"] = {"gozlenen": float((hk > he).mean()),
                           "katmanli_rastgele": [float(np.mean(sonuc)), *map(float, np.percentile(sonuc, [2.5, 97.5]))],
                           "katman_sayisi": len(gr)}

# ---------------------------------------------------------------- E10: Stulp aktarımı, r = −0,49 ile tutarlı eğim
E10 = {}
for tur, (f, sd_f) in (("en_az", (3.72, 5.54)), ("istenen", (13.45, 5.61))):
    for r_ in (-0.49, 0.0):
        egim = 1 + r_ * sd_f / 5.9          # Stulp kadınlarının boy SS'si raporlanmadı; 5,9 cm varsayıldı
        art = sd_f * np.sqrt(1 - r_ ** 2)
        mu = 170.9 + f + egim * (TR_KADIN[0] - 170.9)
        sd = np.sqrt(art ** 2 + (egim * TR_KADIN[1]) ** 2)
        E10[f"{tur}_r={r_}"] = {"egim": float(egim), 176: float(norm.cdf((176 - mu) / sd)), 178: float(norm.cdf((178 - mu) / sd))}
SONUC["E10_stulp_tutarli"] = E10

for k, v in SONUC.items():
    print(k, json.dumps(v, ensure_ascii=False, default=float)[:600])
(CIKTI / "kesif.json").write_text(json.dumps(SONUC, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
