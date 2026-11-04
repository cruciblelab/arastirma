"""
ÖN KAYITSIZ KEŞİF (şeytanın avukatı itirazlarının kontrolü). calistir.py'den SONRA yazıldı.

    python kesif.py      (önce calistir.py çalışmış olmalı; aynı .veri/ dosyalarını kullanır)

E1  ABD: doğum yerine göre (ABD doğumlu; ABD doğumlu beyaz) ≥5 − <1 farkı; gelir gruplarında yurt dışı doğumlu payı
E2  Eğitim eklenince gelir farkı (BR: ANOS_ESTUDO; ABD: DMDEDUC2)
E3  Brezilya: yalnız yaş düzeltmesi (ham farkı gizleyen kohort etkisi var mı?) ve doğum kohortlarına göre fark
E4  Brezilya: büyük bölgeler içinde üst − alt dilim
E5  Brezilya: log-gelir eğimi alt yarıda ve en üst %10'da (tepede yassılaşma)
E6  Brezilya: en zengin %1'de ölçülmüş boyu eksik olanlar ve beyan edilen boyları
E7  Brezilya: örtüşme — alt dilimden rastgele bir erkeğin üst dilimden rastgele bir erkekten uzun olma olasılığı
"""

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
CIKTI = KOK / "ciktilar"
rng = np.random.default_rng(20261105)
B = 500
SONUC = {}


def wols(X, y, w):
    Xw = X * w[:, None]
    return np.linalg.solve(X.T @ Xw + 1e-8 * np.eye(X.shape[1]), Xw.T @ y)


def boot_fark(d, kume, kur, B=B):
    """kur(d) → tek sayı; kümeye göre bootstrap GA."""
    v0 = kur(d)
    k, idx = np.unique(d[kume].to_numpy(), return_inverse=True)
    dg = []
    for _ in range(B):
        say = rng.multinomial(len(k), np.full(len(k), 1 / len(k)))[idx]
        dd = d.assign(w=d.w * say)
        dd = dd[dd.w > 0]
        dg.append(kur(dd))
    return [float(v0), *map(float, np.percentile(dg, [2.5, 97.5]))]


def fark_modeli(d, ust, alt, kontrol):
    """Ağırlıklı doğrusal model: boy ~ ust göstergesi + kontroller, yalnız ust ve alt gruplar."""
    dd = d[d.grup.isin([ust, alt])]
    X = np.column_stack([np.ones(len(dd)), (dd.grup == ust).astype(float)] +
                        ([pd.get_dummies(dd[c].astype(str), drop_first=True).to_numpy(float) for c in kontrol] if kontrol else []))
    return wols(X, dd.boy.to_numpy(), dd.w.to_numpy())[1]


# ---------------------------------------------------------------- ABD
dm = pd.read_sas(REPO / ".veri" / "gelir-boy" / "P_DEMO.xpt", format="xport")
bx = pd.read_sas(REPO / ".veri" / "gelir-boy" / "P_BMX.xpt", format="xport")
us = dm.merge(bx[["SEQN", "BMXHT"]], on="SEQN")
us = us[us.RIDAGEYR.between(25, 59) & us.BMXHT.between(130, 215) & us.INDFMPIR.notna() & (us.WTMECPRP > 1e-6)].copy()
us = us[~((us.RIAGENDR == 2) & (us.RIDEXPRG == 1))]
us["boy"], us["w"] = us.BMXHT, us.WTMECPRP
us["kume"] = us.SDMVSTRA.astype(int).astype(str) + "-" + us.SDMVPSU.astype(int).astype(str)
us["yas_g"] = (us.RIDAGEYR // 5) * 5
us["grup"] = pd.cut(us.INDFMPIR.round(2), [-1, 0.999, 1.999, 2.999, 3.999, 4.999, 9], labels=[1, 2, 3, 4, 5, 6]).astype(int)
us["egitim"] = us.DMDEDUC2.where(us.DMDEDUC2.between(1, 5), 9)
E1, E2us = {}, {}
for c, ad in ((1, "erkek"), (2, "kadin")):
    d = us[us.RIAGENDR == c]
    E1[ad] = {
        "yurt_disi_dogumlu_payi_<1": float(np.average(d[d.grup == 1].DMDBORN4 == 2, weights=d[d.grup == 1].w)),
        "yurt_disi_dogumlu_payi_>=5": float(np.average(d[d.grup == 6].DMDBORN4 == 2, weights=d[d.grup == 6].w)),
        "ABD_dogumlu": boot_fark(d[d.DMDBORN4 == 1], "kume", lambda x: fark_modeli(x, 6, 1, ["yas_g"])),
        "ABD_dogumlu_beyaz": boot_fark(d[(d.DMDBORN4 == 1) & (d.RIDRETH3 == 3)], "kume", lambda x: fark_modeli(x, 6, 1, ["yas_g"])),
        "yurt_disi_dogumlu": boot_fark(d[d.DMDBORN4 == 2], "kume", lambda x: fark_modeli(x, 6, 1, ["yas_g"])),
    }
    E2us[ad] = {"irk+dogum_yeri": boot_fark(d, "kume", lambda x: fark_modeli(x, 6, 1, ["yas_g", "RIDRETH3", "DMDBORN4"])),
                "irk+dogum_yeri+egitim": boot_fark(d, "kume", lambda x: fark_modeli(x, 6, 1, ["yas_g", "RIDRETH3", "DMDBORN4", "egitim"]))}
SONUC["E1_ABD_dogum_yeri"] = E1

# ---------------------------------------------------------------- Brezilya
V = REPO / ".veri" / "boy-beklentisi"
with zipfile.ZipFile(V / "pof0809_leitura.zip") as z:
    sas = z.read("SAS/Leitura dos Microdados - SAS.txt").decode("latin-1")
blok = sas[sas.find("T_MORADOR_S"):sas.find("T_MORADOR_IMPUT_S")]
duzen = {a: (int(p) - 1, int(p) - 1 + int(g), int(o) if o else 0) for p, a, g, o in re.findall(r"@(\d+)\s+(\w+)\s+\$?(\d+)\.(\d*)", blok)}
G = ["COD_UF", "COD_UPA", "PESO_FINAL", "IDADE_ANOS", "V0405", "V0434", "V0406", "V0429", "TIPO_SITUACAO_REG", "RENDA_PERCAPITA",
     "ANOS_ESTUDO", "ALTURA_REFERIDA"]
with zipfile.ZipFile(V / "pof0809_dados.zip") as z:
    ham = z.read([n for n in z.namelist() if n.endswith("T_MORADOR_S.txt")][0])
br = pd.read_fwf(io.BytesIO(ham), colspecs=[duzen[a][:2] for a in G], names=G, dtype=str)
for a in G:
    s = br[a].str.strip()
    v = pd.to_numeric(s, errors="coerce")
    if duzen[a][2]:
        v = np.where(s.str.contains(".", regex=False), v, v / 10 ** duzen[a][2])
    br[a] = v
br = br[br.IDADE_ANOS.between(25, 59) & br.RENDA_PERCAPITA.notna() & ~((br.V0405 == 2) & (br.V0406 == 1))].copy()
br["w"] = br.PESO_FINAL
br["yas_g"] = (br.IDADE_ANOS // 5) * 5
br["bolge"] = (br.COD_UF // 10).astype(int)      # 1 Kuzey, 2 Kuzeydoğu, 3 Güneydoğu, 4 Güney, 5 Orta-Batı
BOLGE = {1: "Kuzey", 2: "Kuzeydoğu", 3: "Güneydoğu", 4: "Güney", 5: "Orta-Batı"}
br["egitim"] = br.ANOS_ESTUDO.fillna(-1).clip(upper=16)


def yuzdelik(x, w):
    s = pd.DataFrame({"x": x, "w": w}).groupby("x").w.sum().sort_index()
    return pd.Series(x).map(s.cumsum() / s.sum() - s / (2 * s.sum())).to_numpy()


E2br, E3, E4, E5, E6, E7 = {}, {}, {}, {}, {}, {}
for c, ad in ((1, "erkek"), (2, "kadin")):
    d = br[br.V0405 == c].copy()
    d["yuzdelik"] = yuzdelik(d.RENDA_PERCAPITA.to_numpy(), d.w.to_numpy())   # yüzdelik, eksik boylular dahil hesaplanır
    d["grup"] = np.clip(np.ceil(d.yuzdelik * 10), 1, 10).astype(int)
    # E6: en zengin %1'de eksik ölçülmüş boy
    t1 = d[d.yuzdelik > 0.99]
    E6[ad] = {"eksik_payi": float(np.average(t1.V0434.between(130, 215) == False, weights=t1.w)),
              "beyan_eksikler": float(t1[~t1.V0434.between(130, 215)].ALTURA_REFERIDA.where(lambda x: x.between(130, 215)).mean()),
              "beyan_olculenler": float(t1[t1.V0434.between(130, 215)].ALTURA_REFERIDA.where(lambda x: x.between(130, 215)).mean())}
    # Yüzdelikler calistir.py'deki gibi yalnız ölçülmüş boylular arasında yeniden hesaplanır
    d = d[d.V0434.between(130, 215)].copy()
    d["boy"] = d.V0434
    d["yuzdelik"] = yuzdelik(d.RENDA_PERCAPITA.to_numpy(), d.w.to_numpy())
    d["grup"] = np.clip(np.ceil(d.yuzdelik * 10), 1, 10).astype(int)
    E2br[ad] = {"yas+eyalet+kent+irk": boot_fark(d, "COD_UPA", lambda x: fark_modeli(x, 10, 1, ["yas_g", "COD_UF", "TIPO_SITUACAO_REG", "V0429"])),
                "yas+eyalet+kent+irk+egitim": boot_fark(d, "COD_UPA", lambda x: fark_modeli(x, 10, 1, ["yas_g", "COD_UF", "TIPO_SITUACAO_REG", "V0429", "egitim"]))}
    E3[ad] = {"yalniz_yas": boot_fark(d, "COD_UPA", lambda x: fark_modeli(x, 10, 1, ["yas_g"])),
              "kohort_1949_63": float(fark_modeli(d[d.IDADE_ANOS >= 45], 10, 1, ["yas_g"])),
              "kohort_1974_84": float(fark_modeli(d[d.IDADE_ANOS <= 34], 10, 1, ["yas_g"]))}
    E4[ad] = {BOLGE[b]: float(fark_modeli(d[d.bolge == b], 10, 1, ["yas_g"])) for b in BOLGE}
    lg = np.log(d.RENDA_PERCAPITA.clip(lower=1))
    for et, m in (("alt_yari", d.yuzdelik <= 0.5), ("en_ust_%10", d.yuzdelik > 0.9)):
        X = np.column_stack([np.ones(m.sum()), lg[m], pd.get_dummies(d[m].yas_g, drop_first=True).to_numpy(float)])
        E5.setdefault(ad, {})[et + "_cm_per_log"] = float(wols(X, d[m].boy.to_numpy(), d[m].w.to_numpy())[1])
    a, u = d[d.grup == 1], d[d.grup == 10]
    ia = rng.choice(len(a), 200000, p=a.w / a.w.sum())
    iu = rng.choice(len(u), 200000, p=u.w / u.w.sum())
    E7[ad] = float((a.boy.to_numpy()[ia] > u.boy.to_numpy()[iu]).mean())
SONUC["E2_egitim"] = {"BR": E2br, "ABD": E2us}
SONUC["E3_yas_ve_kohort"] = E3
SONUC["E4_bolge_ici"] = E4
SONUC["E5_log_gelir_egimi"] = E5
SONUC["E6_yuzde1_eksik_boy"] = E6
SONUC["E7_ortusme"] = E7

for k, v in SONUC.items():
    print(k, json.dumps(v, ensure_ascii=False, default=float)[:700])
(CIKTI / "kesif.json").write_text(json.dumps(SONUC, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
