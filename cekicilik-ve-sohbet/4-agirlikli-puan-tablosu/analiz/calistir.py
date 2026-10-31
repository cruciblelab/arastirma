"""
Çekicilik ve sohbet, sürüm 4: ağırlıklı puan tablosu (ön kayıt: PLAN.md). Tek komut:

    python calistir.py

Veri (önceki sürümlerle aynı dosyalar; yoksa indirilir, SHA-256 doğrulanır; repoya girmez, .veri/ altında tutulur)
  HT  Fisman ve Iyengar hızlı tanışma (datahub)            — sürüm 1
  WA  Walter ve ark. 2020, 45 ülke (OSF)                    — sürüm 1
  UV  Witmer ve ark. 2025, seçim deneyi (OSF 84abw)         — sürüm 3
  SL  Sleiman, Melios ve Dolan 2025 (Dataverse G1H0UA, CC0) — kadınların-boy-beklentisi, sürüm 1
      (IP/konum içeren ham dosya tutulmaz; yoksa önce o araştırmanın calistir.py'si çalıştırılmalı)
Testler T1-T4, H1-H3; karar kuralları K1-K3. Çıktılar ciktilar/ altında.
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
TOHUM = 20261031
BOOT = 2000
rng = np.random.default_rng(TOHUM)
VERI = {
    "HT": dict(url="https://datahub.io/core/speed-dating/r/speed-dating.csv",
               sha256="5f16a947d24289d548b89cb38878ca01e93ce01070ecb76f30b3a98d85bcdcbf",
               dosya=REPO / ".veri" / "yas" / "speed-dating.csv"),
    "WA": dict(url="https://osf.io/download/5fmyu/",
               sha256="0509eb7bbaae75c08533d19e1e6fa3a343a4775d825d644068be63824dff5933",
               dosya=REPO / ".veri" / "yas" / "walter2020_45ulke.csv"),
    "UV": dict(url="https://osf.io/download/84abw/",
               sha256="e8de84b6255bd80252371b19b543e34107f4e862444f64587b22927e9a0c3205",
               dosya=REPO / ".veri" / "cekicilik" / "uva_conjoint_kadin.csv"),
}
SL_TEMIZ = REPO / ".veri" / "boy-beklentisi" / "sleiman_kadin_temiz.csv"
SL_SHA = "2c30c10ff321b903c015952b41c27d5d17e063a51307736b139fd752e8e48f65"
TESTLER, KARARLAR, OZET = [], [], {}
T0 = time.time()
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2, SOLUK, IZGARA = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3", "#ecebe8"
MAVI = "#2a78d6"


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


def aralik(x):
    return np.percentile(x, [2.5, 97.5], axis=0)


def kisi_ici(grup, X, y):
    """Kişi ortalaması çıkarılmış en küçük kareler + kişiye göre küme bootstrap. Katsayılar ve bootstrap dağılımı."""
    benz, idx = np.unique(grup, return_inverse=True)
    Xc = X - pd.DataFrame(X).groupby(idx).transform("mean").to_numpy()
    yc = y - pd.Series(y).groupby(idx).transform("mean").to_numpy()
    k = X.shape[1]
    xtx = np.zeros((len(benz), k, k))
    xty = np.zeros((len(benz), k))
    np.add.at(xtx, idx, Xc[:, :, None] * Xc[:, None, :])
    np.add.at(xty, idx, Xc * yc[:, None])
    b = np.linalg.solve(xtx.sum(0), xty.sum(0))
    ag = rng.multinomial(len(benz), np.full(len(benz), 1 / len(benz)), size=BOOT).astype(float)
    dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty) for a in ag])
    return b, dg, len(benz)


def puanla(b, dg):
    """Pozitif etkilerin toplamı 100 olacak şekilde puan; bootstrap'te aynı kural."""
    pos = np.clip(b, 0, None)
    pos_d = np.clip(dg, 0, None)
    p = 100 * pos / pos.sum()
    pd_ = 100 * pos_d / pos_d.sum(1, keepdims=True)
    return p, pd_


sha = {k: indir(v) for k, v in VERI.items()}
sha["SL"] = (SL_TEMIZ.parent / "sleiman_ham_sha256.txt").read_text().strip() if SL_TEMIZ.exists() else "yok"
uyan = [k for k in VERI if sha[k] == VERI[k]["sha256"]] + (["SL"] if sha["SL"] == SL_SHA else [])
test("T1", "Veri bütünlüğü: dört kaynağın SHA-256 özeti", ", ".join(f"{k} {'eşleşti' if k in uyan else 'UYUŞMADI'}"
                                                                  for k in ("HT", "WA", "UV", "SL")),
     "dördü de eşleşir", len(uyan) == 4)

KAYNAK = {}

# ---------------------------------------------------------------- HT: hızlı tanışma, kadın kararları
log("HT...")
OZ_HT = {"attractive_partner": "Görünüş (yüz/fotoğraf)", "sincere_partner": "Kişilik: samimiyet / hoşgörü",
         "intelligence_partner": "Zekâ", "funny_partner": "Mizah / eğlence", "ambition_partner": "Eğitim / meslek / hırs",
         "shared_interests_partner": "Ortak ilgi / uyum"}
KIMLIK = ["wave", "gender", "age", "race", "field", "attractive_important", "sincere_important", "intellicence_important",
          "funny_important", "ambtition_important", "shared_interests_important", "attractive", "sincere", "intelligence",
          "funny", "ambition", "sports", "tvsports", "exercise", "dining", "museums", "art", "hiking", "gaming", "clubbing",
          "reading", "tv", "theater", "movies", "concerts", "music", "shopping", "yoga", "expected_happy_with_sd_people"]
s = pd.read_csv(VERI["HT"]["dosya"], low_memory=False, na_values="?")
s["kisi"] = s.groupby(KIMLIK, dropna=False, sort=False).ngroup()
d = s[s.gender == "female"].dropna(subset=list(OZ_HT) + ["decision"]).copy()
X = d[list(OZ_HT)].to_numpy(float)
Xc = X - d.groupby("kisi")[list(OZ_HT)].transform("mean").to_numpy()
X = X / Xc.std(0)                         # kadın içi 1 SS (sürüm 1 ile aynı ölçek)
b, dg, n = kisi_ici(d.kisi.to_numpy(), X, 100 * d.decision.astype(float).to_numpy())
KAYNAK["HT"] = dict(ad="Hızlı tanışma (canlı, ABD)", ozellik=list(OZ_HT.values()), b=b, dg=dg, kadin=n, karar=len(d),
                    birim="kadın içi 1 SS algı farkı")
i_cek = list(OZ_HT).index("attractive_partner")
test("T2", "HT kadın çekicilik etkisi sürüm 1'i tekrar ediyor (yp / 1 SS)", f"{b[i_cek]:.2f}", "12,9 ± 0,3",
     abs(b[i_cek] - 12.9) <= 0.3)

# ---------------------------------------------------------------- UV: profil seçimi
log("UV...")
u = pd.read_csv(VERI["UV"]["dosya"], sep=";", decimal=",", encoding="utf-8-sig")


def havuz_z(sr):
    v = np.unique(sr.to_numpy(float))
    return (sr - v.mean()) / v.std(ddof=1)


OZ_UV = {"cek": "Görünüş (yüz/fotoğraf)", "boy": "Boy", "iq": "Zekâ", "mes": "Eğitim / meslek / hırs",
         "bio": "Kendini anlatma (profil yazısı)"}
u["cek"], u["bio"], u["mes"] = havuz_z(u.Attractiveness), havuz_z(u.Bio), havuz_z(u.Occupation)
u["boy"] = u.Height / 7.0
u["iq"] = u.Intelligence / 15.0
b, dg, n = kisi_ici(u.Participants.to_numpy(), u[list(OZ_UV)].to_numpy(float), 100 * u.Response.to_numpy(float))
KAYNAK["UV"] = dict(ad="Profil seçimi (Almanya)", ozellik=list(OZ_UV.values()), b=b, dg=dg, kadin=n, karar=len(u),
                    birim="1 SS (boy 7 cm, IQ 15)")
test("T3", "UV boy etkisi sürüm 3'ü tekrar ediyor (yp / 7 cm)", f"{b[1]:.2f}", "1,2 ± 0,3", abs(b[1] - 1.2) <= 0.3)

# ---------------------------------------------------------------- SL: ikili profil seçimi
log("SL...")
sl_w = pd.read_csv(SL_TEMIZ)
TASARIM = {   # 2.reshape.do: özellik = 1 olan görevler (alternatif 1, alternatif 2)
    "cekici": ([5, 6, 11, 13, 15], [1, 2, 3, 5, 6, 7, 9, 10, 12, 14, 15]),
    "uzun": ([1, 2, 3, 4, 8, 9, 10, 13, 15, 16], [1, 2, 3, 7, 10, 14]),
    "universite": ([3, 4, 6, 7, 14, 15, 16], [1, 3, 4, 6, 7, 9, 13, 14, 16]),
    "acik": ([1, 2, 6, 10, 11, 12, 15], [1, 3, 4, 8, 12, 14, 16]),
    "parti_isci": ([1, 3, 4, 6, 10, 11, 13, 15], [1, 5, 6, 8, 10, 11, 13, 16]),
    "ilerici": ([1, 2, 3, 5, 6, 7, 14, 15, 16], [2, 5, 10, 11, 12, 14, 16]),
    "irk_beyaz": ([2, 3, 8, 10, 11, 13, 14, 15, 16], [3, 6, 9, 11, 12, 15, 16]),
    "vejetaryen": ([4, 9, 10, 12, 14, 15, 16], [2, 3, 5, 6, 8, 10, 14, 15, 16]),
}
OZ_SL = {"cekici": "Görünüş (yüz/fotoğraf)", "uzun": "Boy", "universite": "Eğitim / meslek / hırs",
         "acik": "Kişilik: samimiyet / hoşgörü", "parti_isci": "Siyasi değerler (İngiltere'ye özgü)",
         "ilerici": "Siyasi değerler (İngiltere'ye özgü)", "irk_beyaz": "Diğer (ırk)", "vejetaryen": "Diğer (beslenme)"}
satir = []
for _, r in sl_w.iterrows():
    for t in range(1, 17):
        c = r[f"mset{t}"]
        if pd.isna(c):
            continue
        for alt in (1, 2):
            satir.append([r.kadin, 100.0 * (c == alt)] + [float(t in TASARIM[o][alt - 1]) for o in TASARIM])
sl = pd.DataFrame(satir, columns=["kadin", "y"] + list(TASARIM))
Xs = sl[list(TASARIM)].to_numpy(float)
Xs[:, 1] *= 10.2 / 7.0                    # boy: 10,2 cm → 7 cm başına (doğrusal kabul)
Xs1 = np.column_stack([np.ones(len(sl)), Xs])
benz, idx = np.unique(sl.kadin, return_inverse=True)
xtx = np.zeros((len(benz), 9, 9))
xty = np.zeros((len(benz), 9))
np.add.at(xtx, idx, Xs1[:, :, None] * Xs1[:, None, :])
np.add.at(xty, idx, Xs1 * sl.y.to_numpy()[:, None])
b = np.linalg.solve(xtx.sum(0), xty.sum(0))[1:]
ag = rng.multinomial(len(benz), np.full(len(benz), 1 / len(benz)), size=BOOT).astype(float)
dg = np.array([np.linalg.solve(np.tensordot(a, xtx, 1), a @ xty)[1:] for a in ag])
KAYNAK["SL"] = dict(ad="İkili profil seçimi (İngiltere)", ozellik=[OZ_SL[o] for o in TASARIM], ham=list(TASARIM), b=b, dg=dg,
                    kadin=len(benz), karar=len(sl) // 2, birim="ikili özellik (boy 7 cm'ye ölçekli)")

# ---------------------------------------------------------------- puanlar ve ortak kategoriler
tablo = []
for k, v in KAYNAK.items():
    p, pdg = puanla(v["b"], v["dg"])
    plo, phi = aralik(pdg)
    blo, bhi = aralik(v["dg"])
    for i, oz in enumerate(v["ozellik"]):
        tablo.append(dict(kaynak=k, ozellik=oz, ham=(v.get("ham") or [None] * len(v["ozellik"]))[i],
                          etki_yp=v["b"][i], etki_lo=blo[i], etki_hi=bhi[i], puan=p[i], puan_lo=plo[i], puan_hi=phi[i]))
    v["puan"], v["puan_dg"] = p, pdg
tablo = pd.DataFrame(tablo)
# Siyasi değerler (SL'de iki özellik) kategori içinde toplanır
kat = tablo.groupby(["kaynak", "ozellik"], sort=False).agg(puan=("puan", "sum"), etki_yp=("etki_yp", "sum")).reset_index()
genel = kat.groupby("ozellik").agg(genel_puan=("puan", "mean"), kaynak_sayisi=("kaynak", "nunique"),
                                   kaynaklar=("kaynak", lambda x: ", ".join(x))).reset_index()
genis = kat.pivot(index="ozellik", columns="kaynak", values="puan").reindex(columns=["HT", "UV", "SL"])
genel = genel.merge(genis, left_on="ozellik", right_index=True).sort_values("genel_puan", ascending=False)
DEGISIR = {
    "Görünüş (yüz/fotoğraf)": (2, "Yüz yapısı değişmez; bakım, cilt, saç, kilo/yağ oranı, kıyafet ve fotoğraf kalitesi değişir"),
    "Boy": (0, "Büyüme bittikten sonra değişmez; duruş yalnız birkaç mm"),
    "Zekâ": (1, "Zekâ büyük ölçüde sabit; algılanan zekâ sohbet ve bilgiyle kısmen değişir"),
    "Eğitim / meslek / hırs": (2, "Yıllar içinde değişir: eğitim, iş, hedefler"),
    "Kişilik: samimiyet / hoşgörü": (3, "Davranışla hemen gösterilir: dürüstlük, saygı, ilgi"),
    "Mizah / eğlence": (2, "Kısmen öğrenilir; rahatlık ve ortam etkili"),
    "Ortak ilgi / uyum": (3, "Algılanan ortak ilgi, soru sorma ve dinlemeyle artar (sürüm 1-2)"),
    "Kendini anlatma (profil yazısı)": (3, "Yazı ve anlatım hemen düzeltilebilir"),
    "Siyasi değerler (İngiltere'ye özgü)": (None, "Türkiye'ye aktarılamaz; değer uyumu"),
}
genel["degistirilebilirlik_0_3"] = genel.ozellik.map(lambda o: DEGISIR.get(o, (None, ""))[0])
genel["degistirilebilirlik_gerekce"] = genel.ozellik.map(lambda o: DEGISIR.get(o, (None, ""))[1])


def sinif(p):
    return "en büyük ağırlık" if p >= 25 else "büyük" if p >= 12 else "orta" if p >= 6 else "küçük"


genel["sinif"] = [sinif(p) + (" (tek kaynak)" if n == 1 else "") for p, n in zip(genel.genel_puan, genel.kaynak_sayisi)]
for _, r in genel.iterrows():
    karar_kaydi("K1/K2", f"{r.ozellik}: genel davranış puanı", f"{r.genel_puan:.1f} ({r.kaynaklar})", r.sinif)
tablo.to_csv(CIKTI / "ozellik_puanlari.csv", index=False, float_format="%.2f")
genel.to_csv(CIKTI / "puan_tablosu.csv", index=False, float_format="%.1f")
negatif = tablo[tablo.etki_yp < 0]
OZET["negatif_etkiler"] = negatif[["kaynak", "ozellik", "ham", "etki_yp", "etki_lo", "etki_hi"]].round(2).to_dict("records")

# H1: HT ve UV'de görünüş birinci
birinci = {k: tablo[tablo.kaynak == k].sort_values("puan", ascending=False).ozellik.iloc[0] for k in ("HT", "UV", "SL")}
test("H1", "HT ve UV'de en yüksek puanlı özellik görünüş (kör değil)", f"HT: {birinci['HT']}; UV: {birinci['UV']}; SL: {birinci['SL']}",
     "HT ve UV'de birinci", birinci["HT"].startswith("Görünüş") and birinci["UV"].startswith("Görünüş"))
# H2: boy < görünüş (UV, SL)
h2 = {}
for k, ib, ic in (("UV", 1, 0), ("SL", 1, 0)):
    f = KAYNAK[k]["puan_dg"][:, ib] - KAYNAK[k]["puan_dg"][:, ic]
    h2[k] = [float(KAYNAK[k]["puan"][ib] - KAYNAK[k]["puan"][ic]), *map(float, aralik(f))]
test("H2", "Boy puanı − görünüş puanı (UV; SL)", f"UV {h2['UV'][0]:.1f} [{h2['UV'][1]:.1f}, {h2['UV'][2]:.1f}]; "
     f"SL {h2['SL'][0]:.1f} [{h2['SL'][1]:.1f}, {h2['SL'][2]:.1f}]", "ikisinde de GA üst < 0", h2["UV"][2] < 0 and h2["SL"][2] < 0)
# H3: HT ortak ilgi > zekâ
i_oi, i_z = list(OZ_HT).index("shared_interests_partner"), list(OZ_HT).index("intelligence_partner")
f = KAYNAK["HT"]["dg"][:, i_oi] - KAYNAK["HT"]["dg"][:, i_z]
h3 = [float(KAYNAK["HT"]["b"][i_oi] - KAYNAK["HT"]["b"][i_z]), *map(float, aralik(f))]
test("H3", "HT: ortak ilgi − zekâ etkisi (yp, kör değil)", f"{h3[0]:.1f} [{h3[1]:.1f}, {h3[2]:.1f}]", "GA alt > 0", h3[1] > 0)

# ---------------------------------------------------------------- WA: söylenen, Türk kadınları
log("WA...")
w = pd.read_csv(VERI["WA"]["dosya"], encoding_errors="ignore", low_memory=False)
IDEAL = {"ideal_kindness": "İyi kalplilik", "ideal_intelligence": "Zekâ", "ideal_health": "Sağlık",
         "ideal_physatt": "Fiziksel çekicilik", "ideal_resources": "Kaynak (maddi imkân)"}
wk = w[w.sex == 0].dropna(subset=list(IDEAL))
tr = wk[wk.country == "Turkey"]
test("T4", "WA Türk kadın sayısı (5 maddenin hepsi dolu)", f"{len(tr)}", "≥ 500", len(tr) >= 500)


def ipsatif(df):
    return df[list(IDEAL)].sub(df[list(IDEAL)].mean(1), axis=0)


WA = pd.DataFrame({"TR_ort_1_7": tr[list(IDEAL)].mean(), "TR_goreli": ipsatif(tr).mean(),
                   "45ulke_ort_1_7": wk[list(IDEAL)].mean(), "45ulke_goreli": ipsatif(wk).mean()}).rename(index=IDEAL)
dg_tr = []
for _ in range(BOOT):
    i = rng.integers(0, len(tr), len(tr))
    dg_tr.append(ipsatif(tr.iloc[i]).mean().to_numpy())
lo, hi = aralik(np.array(dg_tr))
WA["TR_goreli_lo"], WA["TR_goreli_hi"] = lo, hi
WA["TR_sira"] = WA.TR_goreli.rank(ascending=False).astype(int)
WA["45ulke_sira"] = WA["45ulke_goreli"].rank(ascending=False).astype(int)
WA = WA.sort_values("TR_goreli", ascending=False)
WA.to_csv(CIKTI / "turk_kadinlar_soylenen.csv", float_format="%.2f")
OZET["WA"] = dict(tr_kadin=len(tr), kadin_45=len(wk), tablo=WA.round(3).reset_index(names="ozellik").to_dict("records"))
karar_kaydi("K3", "Türk kadınlarının söylediği sıralama ile davranış sıralaması",
            "söylenen: " + " > ".join(WA.index) + " | davranış: " + " > ".join(genel.ozellik.head(4)),
            "farklı; ikisi de yazılır" if not WA.index[0].startswith("Fiziksel") else "aynı yönde")

# ---------------------------------------------------------------- şekil
log("Şekil...")
g = genel[~genel.ozellik.str.startswith("Diğer")].iloc[::-1]
fig, ax = plt.subplots(figsize=(9.5, 5.2), facecolor=YUZEY)
ax.set_facecolor(YUZEY)
ax.barh(g.ozellik, g.genel_puan, color=MAVI, height=0.62)
sembol = {"HT": "o", "UV": "s", "SL": "^"}
for k, m in sembol.items():
    ax.scatter(g[k], g.ozellik, marker=m, s=34, color=MUR2, zorder=3, label={"HT": "Hızlı tanışma", "UV": "Profil (Almanya)",
                                                                              "SL": "İkili profil (İngiltere)"}[k])
for y_, (p, n) in enumerate(zip(g.genel_puan, g.kaynak_sayisi)):
    ax.text(p + 0.8, y_, f"{p:.0f}" + ("" if n > 1 else " *"), va="center", fontsize=9, color=MUR)
for k in ("top", "right"):
    ax.spines[k].set_visible(False)
for k in ("left", "bottom"):
    ax.spines[k].set_color(SOLUK)
ax.tick_params(colors=MUR2, labelsize=9)
ax.grid(axis="x", color=IZGARA, lw=0.8)
ax.set_axisbelow(True)
ax.set_xlabel("Puan (her kaynakta pozitif etkiler toplamı 100); çubuk = kaynakların ortalaması", color=MUR2, fontsize=9)
ax.set_title("Kadınların gerçek kararlarında özelliklerin ağırlığı  (* tek kaynak)", color=MUR, loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(CIKTI / "puan_tablosu.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- çıktılar
OZET["kaynaklar"] = {k: dict(ad=v["ad"], kadin=v["kadin"], karar=v["karar"], birim=v["birim"]) for k, v in KAYNAK.items()}
OZET["puan_tablosu"] = genel.round(2).to_dict("records")
OZET["ozellik_puanlari"] = tablo.round(2).to_dict("records")
OZET["H2"], OZET["H3"] = h2, h3
pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
pd.DataFrame(KARARLAR).to_csv(CIKTI / "kararlar.csv", index=False)
OZET.update(testler=TESTLER, kararlar=KARARLAR, tohum=TOHUM, bootstrap=BOOT)
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log(f"Bitti: {sum(t['sonuc'] == 'GEÇTİ' for t in TESTLER)}/{len(TESTLER)} test geçti.")
