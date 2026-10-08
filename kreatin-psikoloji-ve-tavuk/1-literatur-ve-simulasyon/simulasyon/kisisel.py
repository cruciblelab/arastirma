"""
Kişisel uyarlama: kreatin, psikoloji ve tavuk senaryolarını bir kişinin kendi büyüme sonsalı üzerinde çalıştırır.

    python kisisel.py                  # .kisisel/girdi.json varsa onu, yoksa uydurma örnek kişiyi kullanır
    python kisisel.py yol/girdi.json

Kişisel veri ve sonuçlar YALNIZ .kisisel/ klasörüne yazılır (.gitignore'da; repoya girmez).
Uydurma örnek kişinin sonuçları ciktilar/kisisel_ornek/ altına yazılır.

Yöntem
  1  Kişisel büyüme analizi sürüm 1'in sonsalı (vaka.Onsel + vaka.sonsal, aynı tohum ve N): ölçümlerle uyumlu
     sanal kişiler ve ağırlıkları.
  2  Ağırlıklara göre M kişi yeniden örneklenir; aynı tohumla kohort parametreleri yeniden üretilip bu kişiler
     16-25 yaş ızgarasında yeniden simüle edilir (tutarlılık kontrolü: 25 yaş boyu sonsaldakiyle aynı).
  3  Ana çalışmadaki senaryolar (calistir.py) kişinin bugünkü yaşından başlatılır. Kilo bilinmediği için
     enerji senaryolarında ana çalışmadaki BMI dağılımı kullanılır (varsayım).
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
REPO = KOK.parents[2]
VAKA = REPO / "kisisel-buyume-analizi" / "1-belirsiz-olcumlerle-tahmin" / "simulasyon"
sys.path.append(str(VAKA))
sys.path.append(str(REPO / "beslenme-uyku-ve-boy" / "1-fizyoloji-simulasyonu" / "simulasyon"))

import vaka                                   # noqa: E402  (kişisel analiz sürüm 1; model yollarını ekler)
import plak                                   # noqa: E402
from model import DT, Senaryo, simule_et      # noqa: E402
import besin                                  # noqa: E402
import fizyoloji as fz                        # noqa: E402
from fizyoloji import Ayar, Durum             # noqa: E402

TOHUM_V1, N_V1 = 20261007, 1_200_000          # kişisel analiz sürüm 1 ile aynı (sapma 2)
M = 2000
IZGARA = np.round(np.arange(16.0, 25.0 + 1e-9, 0.02), 2)

yol = Path(sys.argv[1]) if len(sys.argv) > 1 else VAKA / ".kisisel" / "girdi.json"
if yol.exists():
    girdi, CIKTI = json.loads(yol.read_text(encoding="utf-8")), KOK / ".kisisel"
else:
    girdi, CIKTI = json.loads((VAKA / "ornek_girdi.json").read_text(encoding="utf-8")), KOK / "ciktilar" / "kisisel_ornek"
CIKTI.mkdir(parents=True, exist_ok=True)
# İsteğe bağlı profil (kilo, öğün sepetleri, anne-baba boyu aralığı). Gerçek kişininki .kisisel/profil.json'da kalır.
PROFIL_YOL = KOK / ".kisisel" / "profil.json" if CIKTI.name == ".kisisel" else KOK / "ornek_profil.json"
PROFIL = json.loads(PROFIL_YOL.read_text(encoding="utf-8")) if PROFIL_YOL.exists() else {}
c = girdi["cinsiyet"]
BAS = round(round(girdi["simdiki_yas"] / 0.02) * 0.02, 2)      # model ızgarasına (0.02) yuvarlanmış bugünkü yaş
assert 16.0 <= BAS < 25.0
print(f"Girdi: {'kişisel (.kisisel)' if CIKTI.name == '.kisisel' else 'uydurma örnek'}; başlangıç yaşı {BAS}")

# 1. Sonsal
on = vaka.Onsel(c, N_V1, TOHUM_V1)
s = vaka.sonsal(on, girdi, vaka.Ayar(), tohum=TOHUM_V1)
print(f"ESS {s['ess']:.0f}")
AB = []                                        # anne-baba boyu belirsizliği: kalan büyüme ne kadar değişiyor?
if PROFIL.get("anne_aralik") and PROFIL.get("baba_aralik"):
    for a_ in (PROFIL["anne_aralik"][0], np.mean(PROFIL["anne_aralik"]), PROFIL["anne_aralik"][1]):
        for b_ in (PROFIL["baba_aralik"][0], np.mean(PROFIL["baba_aralik"]), PROFIL["baba_aralik"][1]):
            s2 = vaka.sonsal(on, {**girdi, "anne": float(a_), "baba": float(b_)}, vaka.Ayar(), tohum=TOHUM_V1)
            q = vaka.yuzdelik(s2["kalan"], s2["w"], [10, 50, 90])
            AB.append(dict(anne=float(a_), baba=float(b_), kalan_p10=q[0], kalan_medyan=q[1], kalan_p90=q[2],
                           H25_medyan=float(vaka.yuzdelik(s2["H25"], s2["w"], [50])[0])))
    pd.DataFrame(AB).to_csv(CIKTI / "kisisel_anne_baba.csv", index=False, float_format="%.3f")

# 2. Yeniden örnekleme ve yeniden simülasyon
rng = np.random.default_rng(TOHUM_V1 + 99)
idx = np.sort(rng.choice(N_V1, size=M, replace=True, p=s["w"]))
pop, ind, L0b, L0g = plak.kohort(c, N_V1, np.random.default_rng(TOHUM_V1))
ind = {k: v[idx] for k, v in ind.items()}
L0b, L0g = L0b[idx], L0g[idx]
del on
H = simule_et(ind, pop, L0b, L0g, t1=25.0, kayit_yaslari=IZGARA)["boy"].T / 100.0
H25_sonsal = s["H25"][idx]
tutarlilik = float(np.abs(H[:, -1] * 100 - H25_sonsal).max())
assert tutarlilik < 0.01, f"yeniden simülasyon sonsalla uyuşmuyor: {tutarlilik}"
i0 = int(round((BAS - 16.0) / 0.02))
KALAN = (H[:, -1] - H[:, i0]) * 100


def boy(senaryo=None):
    return simule_et(ind, pop, L0b, L0g, t1=25.0, dt=DT, senaryo=senaryo, kayit_yaslari=[25.0])["boy"][0]


def sabit_N(deger, bas=BAS, bit=25.0):
    return Senaryo(N=lambda t: deger if bas - 1e-9 <= t < bit else 1.0)


REF = boy()
SATIR = []


def ekle(ad, etiket, b, ref=REF):
    f = b - ref
    SATIR.append(dict(senaryo=ad, etiket=etiket, medyan=np.median(f), p5=np.percentile(f, 5),
                      p95=np.percentile(f, 95), en_iyi=f.max(), en_kotu=f.min()))


bir_yil = min(BAS + 1.0, 25.0)
for ad, (k, bit) in {"K2a Varsayımsal: kreatin plağı %5 hızlandırsaydı": (1.05, 25.0),
                     "K2b Varsayımsal: %10 hızlandırsaydı": (1.10, 25.0),
                     "K3 Varsayımsal: %5 yavaşlatsaydı (efsane)": (0.95, 25.0),
                     "P4 Varsayımsal: kortizol bir yıl %5 yavaşlatsaydı": (0.95, bir_yil),
                     "X1 Tavan: bir yıl boyunca yarı hız": (0.5, bir_yil)}.items():
    ekle(ad, "D, varsayımsal", boy(sabit_N(k, bit=bit)))

# Enerji senaryoları (kilo bilinmiyor: ana çalışmadaki BMI dağılımı, medyan 21)
SEPET = {"B1 Dengeli": besin.SEPETLER["B1 Dengeli"],
         "T2 Tavuk-pirinç, süt ürünü yok": dict(tavuk=500, pirinc=400, ekmek=150, zeytinyagi=30, domates=150,
                                               salatalik=100, elma=150)}
TABLO, _ = besin.yiyecek_tablosu()
if PROFIL.get("ek_yiyecekler"):                # USDA SR Legacy'den ek kayıtlar (aynı dosya, aynı SHA-256)
    import io
    import zipfile
    zf = zipfile.ZipFile(besin._indir())
    fn = pd.read_csv(io.BytesIO(zf.read(besin.ALT + "food_nutrient.csv")), usecols=["fdc_id", "nutrient_id", "amount"])
    ids = list(PROFIL["ek_yiyecekler"].values())
    fn = fn[fn.fdc_id.isin(ids) & fn.nutrient_id.isin(list(besin.BESINLER))]
    ek = fn.pivot_table(index="fdc_id", columns="nutrient_id", values="amount", aggfunc="first")
    ek = ek.reindex(index=ids, columns=list(besin.BESINLER)).fillna(0.0).rename(columns=besin.BESINLER)
    ek.index = list(PROFIL["ek_yiyecekler"])
    ek.insert(0, "fdc_id", ids)
    TABLO = pd.concat([TABLO, ek])
    assert (TABLO.kcal > 0).all()
for k, v in PROFIL.get("sepetler", {}).items():
    SEPET[f"Kendi sepetin ({k})"] = v
PY = {k: besin.protein_yogunlugu(TABLO, v) for k, v in SEPET.items()}
r2 = np.random.default_rng(TOHUM_V1 + 7)
bmi = np.clip(np.exp(np.log(21.0) + 0.13 * r2.standard_normal(M)), 16, 32)
if PROFIL.get("kilo"):                         # bugünkü kilo verilmişse: 16 yaşa aynı BMI ile geri ölçeklenir
    bmi = PROFIL["kilo"] / H[:, i0] ** 2
W0 = bmi * H[:, 0] ** 2
FM0 = W0 * np.clip(1.51 * bmi - 0.70 * 16 - 3.6 * (c == "erkek") + 1.4, 5, 45) / 100
z = r2.standard_normal(M)


def H_fn(yas):
    x = (yas - 16.0) / 0.02
    i = int(np.clip(np.floor(x), 0, len(IZGARA) - 1))
    if i >= len(IZGARA) - 1:
        return H[:, -1]
    t = x - i
    return H[:, i] * (1 - t) + H[:, i + 1] * t


def enerji(durum):
    e = fz.simule(c, W0, FM0, H_fn, z, PY, durum, Ayar())
    assert e["F1"].max() < 1e-3
    return boy(Senaryo(N=fz.N_fonksiyonu(e["N_ser"], 16.0, e["dt"])))


B0 = enerji(Durum())
for ad, d in {"P1 Stresle kısa uyku (6 sa), bir yıl": Durum(uyku_kcal=385, bas=BAS, bit=bir_yil),
              "P2 Stresle iştah kaybı (-300 kcal), bir yıl": Durum(delta=-300, bas=BAS, bit=bir_yil),
              "P3 Sert kısıtlama (-1000 kcal), bir yıl": Durum(delta=-1000, bas=BAS, bit=bir_yil),
              "T2 Tavuk-pirinç, süt ürünü yok": Durum(sepet="T2 Tavuk-pirinç, süt ürünü yok", bas=BAS),
              "T3 Tavukla kilo verme (-500 kcal)": Durum(sepet="T2 Tavuk-pirinç, süt ürünü yok", delta=-500,
                                                         bas=BAS)}.items():
    ekle(ad, "D (enerji modeli)", enerji(d), ref=B0)

# Kendi sepetin: gerçek alım (ölçeklenmeden) ve bir yıl boyunca bu alım
BES = []
if PROFIL.get("sepetler"):
    PAL = PROFIL.get("pal", 1.55)
    e0 = fz.simule(c, W0, FM0, H_fn, z, PY, Durum(), Ayar(PAL=PAL))
    j = int(np.argmin(np.abs(e0["yas"][0] - BAS)))
    EI_ref = float(np.median(e0["EI"][:, j]))
    W_simdi, FM_simdi = e0["W"][:, j], e0["FM"][:, j]
    FFM = float(np.median(W_simdi - FM_simdi))
    b0p = boy(Senaryo(N=fz.N_fonksiyonu(e0["N_ser"], 16.0, e0["dt"])))
    for k, sep in PROFIL["sepetler"].items():
        ad = f"Kendi sepetin ({k})"
        kcal = float(besin.sepet_icerigi(TABLO, sep).kcal)
        prof = besin.sepet_profili(TABLO, sep, kcal, c, float(np.median(W_simdi)))
        e = fz.simule(c, W0, FM0, H_fn, z, PY, Durum(sepet=ad, delta=kcal - EI_ref, bas=BAS, bit=bir_yil), Ayar(PAL=PAL))
        assert e["F1"].max() < 1e-3
        b = boy(Senaryo(N=fz.N_fonksiyonu(e["N_ser"], 16.0, e["dt"])))
        j1 = int(np.argmin(np.abs(e["yas"][0] - bir_yil)))
        # İştah düzeltmesi olmadan, bu alım bir yıl sabit kalsaydı: çarpan bugünkü enerji uygunluğundan (üst sınır)
        N_sabit = float(fz.N_E(kcal / FFM, Ayar()))
        b_sabit = boy(sabit_N(N_sabit, bit=bir_yil)) if N_sabit < 1 else REF
        BES.append(dict(sepet=k, kcal=kcal, ihtiyac_kcal=EI_ref, acik_kcal=kcal - EI_ref, EA_simdi=kcal / FFM,
                        esik_kcal_EA30=30 * FFM, min_EA_yil=float(np.median(e["min_EA"])),
                        kilo_degisim_1yil=float(np.median(e["W"][:, j1] - e0["W"][:, j1])),
                        boy_fark25_medyan=float(np.median(b - b0p)), boy_fark25_p5=float(np.percentile(b - b0p, 5)),
                        N_sabit_alim=N_sabit, boy_fark25_sabit_alim=float(np.median(b_sabit - REF)),
                        **{kk: prof[kk] for kk in ("protein_g", "protein_g_kg", "enerji_protein_yuzde",
                                                     "kalsiyum_mg", "kalsiyum_rda_yuzde", "demir_mg",
                                                     "demir_rda_yuzde", "cinko_rda_yuzde", "d_vitamini_ug",
                                                     "d_rda_yuzde", "lif_g")}))
    pd.DataFrame(BES).to_csv(CIKTI / "kisisel_beslenme.csv", index=False, float_format="%.2f")

TAB = pd.DataFrame(SATIR)
TAB.to_csv(CIKTI / "kisisel_senaryolar.csv", index=False, float_format="%.4f")
ozet = dict(baslangic_yasi=BAS, ESS=s["ess"], M=M, tutarlilik_cm=tutarlilik,
            kalan_cm={k: float(np.percentile(KALAN, q)) for k, q in (("p5", 5), ("p10", 10), ("medyan", 50),
                                                                     ("p90", 90), ("p95", 95))},
            P_kalan_en_az={str(e): float(np.mean(KALAN >= e)) for e in (0.5, 1, 2, 3)},
            korovljev_naif_cm=9.0, P_naif_kalandan_buyuk=float(np.mean(9.0 > KALAN)),
            kilo_profilden=bool(PROFIL.get("kilo")), anne_baba=AB, beslenme=BES)
(CIKTI / "kisisel_ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")

fig, ax = plt.subplots(figsize=(9, 5), facecolor="#fcfcfb")
t = TAB.iloc[::-1].reset_index(drop=True)
for i, r in t.iterrows():
    ax.barh(i, r.medyan, color="#c9c8c3" if "varsayımsal" in r.etiket else "#2a78d6", height=0.6)
    ax.plot([r.p5, r.p95], [i, i], color="#0b0b0b", lw=1)
ax.set_yticks(range(len(t)))
ax.set_yticklabels(t.senaryo, fontsize=8.5)
ax.axvline(0, color="#0b0b0b", lw=0.8)
for x in (-0.5, -0.1, 0.1, 0.5):
    ax.axvline(x, color="#e4e3df", lw=1, ls="--", zorder=0)
ax.set_xlabel("25 yaşta boy farkı (cm; çubuk medyan, çizgi %5-%95)")
ax.set_title(f"Kişisel sonsal üzerinde senaryolar (başlangıç {BAS} yaş; kalan pay medyan "
             f"{np.median(KALAN):.1f} cm)", loc="left", fontsize=10.5)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(CIKTI / "kisisel_senaryolar.png", dpi=150)
print(json.dumps(ozet, ensure_ascii=False, indent=1))
print(TAB.round(3).to_string(index=False))
if BES:
    print(pd.DataFrame(BES).round(2).T.to_string())
