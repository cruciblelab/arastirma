"""
Gelir ve boy, sürüm 1: gelir dilimlerinde ölçülmüş boy (ön kayıt: PLAN.md). Tek komut:

    python calistir.py

Veri (indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  BR  IBGE POF 2008-09 (Brezilya): ölçülmüş boy, hanenin kişi başı geliri
  US  NHANES 2017-Mart 2020 (ABD, CDC): ölçülmüş boy, aile gelir/yoksulluk oranı
Analizler A1-A4; teknik testler T1-T4; hipotezler H1-H6; karar kuralları K1-K3. Çıktılar ciktilar/ altında.
"""

import hashlib
import io
import json
import re
import time
import urllib.request
import zipfile
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
TOHUM = 20261104
BOOT = 1000
rng = np.random.default_rng(TOHUM)
POF = "https://ftp.ibge.gov.br/Orcamentos_Familiares/Pesquisa_de_Orcamentos_Familiares_2008_2009/Microdados/"
NH = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/"
VERI = {
    "BR": dict(url=POF + "Dados_20231009.zip", dosya=REPO / ".veri" / "boy-beklentisi" / "pof0809_dados.zip",
               sha256="cc2d5279dbdfd9276cde69066959b919e1a1ecaac4adf82582c6f177443ca265"),
    "BRd": dict(url=POF + "Programas_de_Leitura_20231009.zip", dosya=REPO / ".veri" / "boy-beklentisi" / "pof0809_leitura.zip",
                sha256="98d7eb83526801b356ebbd4074cb38976329e1023ed19bf84de3f2b8c5e6f2a5"),
    "US_demo": dict(url=NH + "P_DEMO.xpt", dosya=REPO / ".veri" / "gelir-boy" / "P_DEMO.xpt",
                    sha256="2e46c6c26bf77cd8989f64011ace12cbf42c0f3e03414eb59acc5328c8f87913"),
    "US_bmx": dict(url=NH + "P_BMX.xpt", dosya=REPO / ".veri" / "gelir-boy" / "P_BMX.xpt",
                   sha256="7038d0da3169420a4a3cbaec09ac586a701b38e1c7b925431b60e13ac24fed66"),
}
TESTLER, KARARLAR, OZET = [], [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK, IZGARA = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3", "#ecebe8"
ERKEK, KADIN = "#2a78d6", "#eb6834"


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
        with urllib.request.urlopen(istek, timeout=600) as r:
            v["dosya"].write_bytes(r.read())
    return hashlib.sha256(v["dosya"].read_bytes()).hexdigest()


def yaz(v, nd=1):
    return f"{v[0]:.{nd}f} [{v[1]:.{nd}f}, {v[2]:.{nd}f}]"


sha = {k: indir(v) for k, v in VERI.items()}
test("T1", "Veri bütünlüğü: dört dosyanın SHA-256 özeti", ", ".join(f"{k} {'eşleşti' if sha[k] == v['sha256'] else 'UYUŞMADI'}"
                                                                  for k, v in VERI.items()),
     "dördü de eşleşir", all(sha[k] == v["sha256"] for k, v in VERI.items()))


def agirlikli_yuzdelik(x, w):
    """Ağırlıklı yüzdelik sırası (0-1); eşit değerler aynı sırayı alır (orta nokta)."""
    s = pd.DataFrame({"x": x, "w": w}).groupby("x").w.sum().sort_index()
    ust = s.cumsum() / s.sum()
    orta = ust - s / (2 * s.sum())
    return pd.Series(x).map(orta).to_numpy()


def kume_ortalama(df, grup, kume):
    """Grup başına ağırlıklı ortalama boy + kümeye göre bootstrap (dağılım: BOOT × grup)."""
    gruplar = sorted(df[grup].unique())
    kum, kidx = np.unique(df[kume].to_numpy(), return_inverse=True)
    gidx = pd.Categorical(df[grup], categories=gruplar).codes
    sw = np.zeros((len(kum), len(gruplar)))
    swh = np.zeros((len(kum), len(gruplar)))
    np.add.at(sw, (kidx, gidx), df.w.to_numpy())
    np.add.at(swh, (kidx, gidx), (df.w * df.boy).to_numpy())
    ort = swh.sum(0) / sw.sum(0)
    say = rng.multinomial(len(kum), np.full(len(kum), 1 / len(kum)), size=BOOT).astype(float)
    dg = (say @ swh) / (say @ sw)
    return gruplar, ort, dg, sw.sum(0)


def kume_ols(X, y, w, kume):
    kum, kidx = np.unique(kume, return_inverse=True)
    k = X.shape[1]
    Xw = X * w[:, None]
    xtx = np.zeros((len(kum), k, k))
    xty = np.zeros((len(kum), k))
    for j in range(k):                     # bellek için sütun sütun
        np.add.at(xtx[:, j, :], kidx, Xw[:, j:j + 1] * X)
    np.add.at(xty, kidx, Xw * y[:, None])
    b = np.linalg.solve(xtx.sum(0), xty.sum(0))
    say = rng.multinomial(len(kum), np.full(len(kum), 1 / len(kum)), size=BOOT).astype(float)
    dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty) for a in say])
    return b, dg


def ga(x):
    return list(map(float, np.percentile(x, [2.5, 97.5])))


# ================================================================ BR
log("BR: POF okunuyor...")
with zipfile.ZipFile(VERI["BRd"]["dosya"]) as z:
    sas = z.read("SAS/Leitura dos Microdados - SAS.txt").decode("latin-1")
blok = sas[sas.find("T_MORADOR_S"):sas.find("T_MORADOR_IMPUT_S")]
duzen = {ad: (int(p) - 1, int(p) - 1 + int(g), int(o) if o else 0)
         for p, ad, g, o in re.findall(r"@(\d+)\s+(\w+)\s+\$?(\d+)\.(\d*)", blok)}
GEREK = ["COD_UF", "COD_UPA", "PESO_FINAL", "IDADE_ANOS", "V0405", "V0434", "V0406", "V0429", "TIPO_SITUACAO_REG",
         "RENDA_PERCAPITA"]
with zipfile.ZipFile(VERI["BR"]["dosya"]) as z:
    ham = z.read([n for n in z.namelist() if n.endswith("T_MORADOR_S.txt")][0])
br = pd.read_fwf(io.BytesIO(ham), colspecs=[duzen[a][:2] for a in GEREK], names=GEREK, dtype=str)
del ham
for a in GEREK:
    s = br[a].str.strip()
    v = pd.to_numeric(s, errors="coerce")
    if duzen[a][2]:
        v = np.where(s.str.contains(".", regex=False), v, v / 10 ** duzen[a][2])
    br[a] = v
br = br[br.IDADE_ANOS.between(25, 59) & br.V0434.between(130, 215) & br.RENDA_PERCAPITA.notna()].copy()
br = br[~((br.V0405 == 2) & (br.V0406 == 1))]          # hamile kadınlar dışarıda
br["boy"], br["w"] = br.V0434, br.PESO_FINAL
br["yas_g"] = (br.IDADE_ANOS // 5) * 5
OZET["BR_V0406_dagilim"] = br.V0406.value_counts(dropna=False).head(5).to_dict()
n_br = {c: int((br.V0405 == c).sum()) for c in (1, 2)}
test("T2", "BR örneklemi (25-59 yaş, ölçülmüş boy + gelir)", f"erkek {n_br[1]}, kadın {n_br[2]}", "her biri ≥ 20.000",
     min(n_br.values()) >= 20000)

BR = {}
for c, ad in ((1, "erkek"), (2, "kadin")):
    d = br[br.V0405 == c].copy()
    d["yuzdelik"] = agirlikli_yuzdelik(d.RENDA_PERCAPITA.to_numpy(), d.w.to_numpy())
    d["dilim"] = np.clip(np.ceil(d.yuzdelik * 10), 1, 10).astype(int)
    d["grup"] = np.where(d.yuzdelik > 0.99, 11, d.dilim)          # 11 = en zengin %1, 10 = 90-99. yüzdelik
    g, ort, dg, sw = kume_ortalama(d, "grup", "COD_UPA")
    i = {gg: k for k, gg in enumerate(g)}
    ust_dilim = (ort[i[10]] * sw[i[10]] + ort[i[11]] * sw[i[11]]) / (sw[i[10]] + sw[i[11]])
    dg_ust = (dg[:, i[10]] * sw[i[10]] + dg[:, i[11]] * sw[i[11]]) / (sw[i[10]] + sw[i[11]])
    ortanca = (ort[i[5]] * sw[i[5]] + ort[i[6]] * sw[i[6]]) / (sw[i[5]] + sw[i[6]])
    dg_ort = (dg[:, i[5]] * sw[i[5]] + dg[:, i[6]] * sw[i[6]]) / (sw[i[5]] + sw[i[6]])
    ham_f = {"ust_eksi_alt": [ust_dilim - ort[i[1]], *ga(dg_ust - dg[:, i[1]])],
             "ust_eksi_ortanca": [ust_dilim - ortanca, *ga(dg_ust - dg_ort)],
             "yuzde1_eksi_ust_dilim_kalani": [ort[i[11]] - ort[i[10]], *ga(dg[:, i[11]] - dg[:, i[10]])],
             "yuzde1_eksi_ortanca": [ort[i[11]] - ortanca, *ga(dg[:, i[11]] - dg_ort)]}
    # A3: düzeltilmiş (yaş + eyalet + kent/kır + ırk/renk)
    gd = pd.get_dummies(d.grup, prefix="g").drop(columns="g_1").astype(float)
    kon = pd.concat([pd.get_dummies(d.yas_g, prefix="y", drop_first=True), pd.get_dummies(d.COD_UF, prefix="uf", drop_first=True),
                     pd.get_dummies(d.TIPO_SITUACAO_REG, prefix="k", drop_first=True),
                     pd.get_dummies(d.V0429.fillna(9), prefix="r", drop_first=True)], axis=1).astype(float)
    X = np.column_stack([np.ones(len(d)), gd.to_numpy(), kon.to_numpy()])
    b, bdg = kume_ols(X, d.boy.to_numpy(), d.w.to_numpy(), d.COD_UPA.to_numpy())
    col = {c_: k + 1 for k, c_ in enumerate(gd.columns)}
    coef = lambda bb, gg: 0.0 if gg == 1 else bb[..., col[f"g_{gg}"]]
    p10, p11 = sw[i[10]] / (sw[i[10]] + sw[i[11]]), sw[i[11]] / (sw[i[10]] + sw[i[11]])
    p5, p6 = sw[i[5]] / (sw[i[5]] + sw[i[6]]), sw[i[6]] / (sw[i[5]] + sw[i[6]])
    ust_b = lambda bb: p10 * coef(bb, 10) + p11 * coef(bb, 11)
    ort_b = lambda bb: p5 * coef(bb, 5) + p6 * coef(bb, 6)
    duz_f = {"ust_eksi_alt": [float(ust_b(b)), *ga(ust_b(bdg))],
             "ust_eksi_ortanca": [float(ust_b(b) - ort_b(b)), *ga(ust_b(bdg) - ort_b(bdg))],
             "yuzde1_eksi_ust_dilim_kalani": [float(coef(b, 11) - coef(b, 10)), *ga(coef(bdg, 11) - coef(bdg, 10))]}
    # A4: eğim (10 yüzdelik puanı başına cm)
    egim = {}
    for et, K in (("ham", np.column_stack([np.ones(len(d)), d.yuzdelik * 10, pd.get_dummies(d.yas_g, drop_first=True).astype(float)])),
                  ("duzeltilmis", np.column_stack([np.ones(len(d)), d.yuzdelik * 10, kon.to_numpy()]))):
        bb, dd = kume_ols(K, d.boy.to_numpy(), d.w.to_numpy(), d.COD_UPA.to_numpy())
        egim[et] = [float(bb[1]), *ga(dd[:, 1])]
    BR[ad] = dict(n=len(d), dilim_ort={int(gg): [float(ort[i[gg]]), *ga(dg[:, i[gg]])] for gg in g},
                  ust_dilim_ort=float(ust_dilim), ortanca_ort=float(ortanca),
                  ham=ham_f, duzeltilmis=duz_f, egim_10_yuzdelik=egim,
                  gelir_esikleri_R=dict(zip(["%10", "%50", "%90", "%99"],
                                            [float(np.interp(q, np.sort(d.yuzdelik), np.sort(d.RENDA_PERCAPITA))) for q in (.1, .5, .9, .99)])))
    log(f"BR {ad}: üst−alt ham {yaz(ham_f['ust_eksi_alt'])}, düzeltilmiş {yaz(duz_f['ust_eksi_alt'])}")
OZET["BR"] = BR

# ================================================================ US
log("US: NHANES okunuyor...")
dm = pd.read_sas(VERI["US_demo"]["dosya"], format="xport")
bx = pd.read_sas(VERI["US_bmx"]["dosya"], format="xport")
us = dm.merge(bx[["SEQN", "BMXHT"]], on="SEQN")
us = us[us.RIDAGEYR.between(25, 59) & us.BMXHT.between(130, 215) & us.INDFMPIR.notna() & (us.WTMECPRP > 0)].copy()
us = us[~((us.RIAGENDR == 2) & (us.RIDEXPRG == 1))]
us["boy"], us["w"] = us.BMXHT, us.WTMECPRP
us["kume"] = us.SDMVSTRA.astype(int).astype(str) + "-" + us.SDMVPSU.astype(int).astype(str)
us["yas_g"] = (us.RIDAGEYR // 5) * 5
us["pir"] = us.INDFMPIR.round(2)
us["grup"] = pd.cut(us.pir, [-1, 0.999, 1.999, 2.999, 3.999, 4.999, 9], labels=[1, 2, 3, 4, 5, 6]).astype(int)
GRUP_US = {1: "<1", 2: "1-2", 3: "2-3", 4: "3-4", 5: "4-5", 6: "≥5"}
n_us = {c: int((us.RIAGENDR == c).sum()) for c in (1, 2)}
test("T3", "US örneklemi (25-59 yaş, ölçülmüş boy + gelir oranı)", f"erkek {n_us[1]}, kadın {n_us[2]}", "her biri ≥ 1.500",
     min(n_us.values()) >= 1500)
US = {}
for c, ad in ((1, "erkek"), (2, "kadin")):
    d = us[us.RIAGENDR == c].copy()
    g, ort, dg, sw = kume_ortalama(d, "grup", "kume")
    i = {gg: k for k, gg in enumerate(g)}
    ham_f = {"ust_eksi_alt": [ort[i[6]] - ort[i[1]], *ga(dg[:, i[6]] - dg[:, i[1]])],
             "ust_eksi_orta": [ort[i[6]] - ort[i[3]], *ga(dg[:, i[6]] - dg[:, i[3]])]}
    gd = pd.get_dummies(d.grup, prefix="g").drop(columns="g_1").astype(float)
    kon = pd.concat([pd.get_dummies(d.yas_g, prefix="y", drop_first=True), pd.get_dummies(d.RIDRETH3, prefix="e", drop_first=True),
                     pd.get_dummies(d.DMDBORN4.where(d.DMDBORN4.isin([1, 2]), 9), prefix="d", drop_first=True)], axis=1).astype(float)
    X = np.column_stack([np.ones(len(d)), gd.to_numpy(), kon.to_numpy()])
    b, bdg = kume_ols(X, d.boy.to_numpy(), d.w.to_numpy(), d.kume.to_numpy())
    col = {c_: k + 1 for k, c_ in enumerate(gd.columns)}
    duz_f = {"ust_eksi_alt": [float(b[col["g_6"]]), *ga(bdg[:, col["g_6"]])],
             "ust_eksi_orta": [float(b[col["g_6"]] - b[col["g_3"]]), *ga(bdg[:, col["g_6"]] - bdg[:, col["g_3"]])]}
    US[ad] = dict(n=len(d), ort=float(np.average(d.boy, weights=d.w)),
                  grup_ort={GRUP_US[gg]: [float(ort[i[gg]]), *ga(dg[:, i[gg]])] for gg in g},
                  grup_pay={GRUP_US[gg]: float(sw[i[gg]] / sw.sum()) for gg in g}, ham=ham_f, duzeltilmis=duz_f)
    log(f"US {ad}: ≥5 − <1 ham {yaz(ham_f['ust_eksi_alt'])}, düzeltilmiş {yaz(duz_f['ust_eksi_alt'])}")
OZET["US"] = US
test("T4", "US ağırlıklı ortalama erkek boyu", f"{US['erkek']['ort']:.1f} cm", "172-178", 172 <= US["erkek"]["ort"] <= 178)

# ================================================================ hipotezler ve kararlar
be, ue = BR["erkek"], US["erkek"]
test("H1", "BR erkek: en üst − en alt gelir dilimi (ham, cm)", yaz(be["ham"]["ust_eksi_alt"]), "≥ 3 ve GA alt > 0",
     be["ham"]["ust_eksi_alt"][0] >= 3 and be["ham"]["ust_eksi_alt"][1] > 0)
test("H2", "BR erkek: düzeltilmiş fark < ham ve > 0", f"ham {be['ham']['ust_eksi_alt'][0]:.1f}, düzeltilmiş {yaz(be['duzeltilmis']['ust_eksi_alt'])}",
     "düzeltilmiş < ham, GA alt > 0", be["duzeltilmis"]["ust_eksi_alt"][0] < be["ham"]["ust_eksi_alt"][0] and be["duzeltilmis"]["ust_eksi_alt"][1] > 0)
test("H3", "US erkek: ≥5 − <1 (ham, cm)", yaz(ue["ham"]["ust_eksi_alt"]), "GA alt > 0", ue["ham"]["ust_eksi_alt"][1] > 0)
test("H4", "US erkek: ≥5 − <1, ırk/köken + doğum yeri düzeltmeli", yaz(ue["duzeltilmis"]["ust_eksi_alt"]), "GA alt > 0",
     ue["duzeltilmis"]["ust_eksi_alt"][1] > 0)
test("H5", "Kadınlarda gradyan (en üst − en alt, ham): BR; US", f"BR {yaz(BR['kadin']['ham']['ust_eksi_alt'])}; US {yaz(US['kadin']['ham']['ust_eksi_alt'])}",
     "ikisinde de GA alt > 0", BR["kadin"]["ham"]["ust_eksi_alt"][1] > 0 and US["kadin"]["ham"]["ust_eksi_alt"][1] > 0)
p1 = be["ham"]["yuzde1_eksi_ust_dilim_kalani"]
test("H6", "BR erkek: en zengin %1 − üst dilimin geri kalanı (ham, cm)", yaz(p1), "GA üst < 2", p1[2] < 2)
f = be["duzeltilmis"]["ust_eksi_ortanca"][0]
karar_kaydi("K1", "BR erkek: en üst dilim − ortanca (düzeltilmiş)", yaz(be["duzeltilmis"]["ust_eksi_ortanca"]),
            "zenginler ortalamadan biraz uzun" if f < 2 else "belirgin uzun" if f <= 4 else "çok uzun")
for ulke, R in (("BR", BR), ("US", US)):
    for ad in ("erkek", "kadin"):
        h, dz = R[ad]["ham"]["ust_eksi_alt"][0], R[ad]["duzeltilmis"]["ust_eksi_alt"][0]
        karar_kaydi("K2", f"{ulke} {ad}: farkın bileşimle açıklanan payı", f"ham {h:.1f}, düzeltilmiş {dz:.1f} cm",
                    f"%{100 * (1 - dz / h):.0f} bileşimden" if h > 0 else "ham fark yok")

# ================================================================ şekil
log("Şekil...")
fig, axs = plt.subplots(1, 2, figsize=(13, 4.6), facecolor=YUZEY)
for ad, renk, et in (("erkek", ERKEK, "Erkek"), ("kadin", KADIN, "Kadın")):
    dd = BR[ad]["dilim_ort"]
    xs = list(range(1, 12))
    y = [dd[k][0] for k in xs]
    axs[0].errorbar(xs, y, yerr=[[dd[k][0] - dd[k][1] for k in xs], [dd[k][2] - dd[k][0] for k in xs]], color=renk, marker="o",
                    ms=4, lw=1.6, capsize=2, label=et)
    gu = US[ad]["grup_ort"]
    ks = list(gu)
    axs[1].errorbar(range(len(ks)), [gu[k][0] for k in ks], yerr=[[gu[k][0] - gu[k][1] for k in ks], [gu[k][2] - gu[k][0] for k in ks]],
                    color=renk, marker="o", ms=4, lw=1.6, capsize=2, label=et)
axs[0].set_xticks(range(1, 12), [f"{k}." for k in range(1, 10)] + ["10.\n(%90-99)", "en zengin\n%1"], fontsize=8)
axs[0].set_title("Brezilya 2008-09: hanenin kişi başı gelir dilimi", color=MUR, loc="left", fontsize=10.5)
axs[1].set_xticks(range(6), list(GRUP_US.values()), fontsize=8.5)
axs[1].set_title("ABD 2017-20: ailenin gelir / yoksulluk sınırı oranı", color=MUR, loc="left", fontsize=10.5)
for ax in axs:
    ax.set_facecolor(YUZEY)
    ax.set_ylabel("Ölçülmüş ortalama boy (cm), 25-59 yaş", color=MUR2, fontsize=9)
    ax.grid(axis="y", color=IZGARA, lw=0.8)
    for k in ("top", "right"):
        ax.spines[k].set_visible(False)
    for k in ("left", "bottom"):
        ax.spines[k].set_color(SOLUK)
    ax.tick_params(colors=MUR2)
    ax.legend(frameon=False, fontsize=8.5)
fig.tight_layout()
fig.savefig(CIKTI / "gelir_ve_boy.png", dpi=160)
plt.close(fig)

# ================================================================ çıktılar
pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET.update(testler=TESTLER, kararlar=KARARLAR, tohum=TOHUM, bootstrap=BOOT)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"Bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti.")
