"""
Belirsiz ölçümlerle kişisel büyüme tahmini (PLAN.md). Tek komut:

    python calistir.py

  1  Önsel: sürüm 3 sanal kohortu (N = 200 000)
  2  Doğrulama: Berkeley erkeklerinde aynı bilgi yapısı taklit edilir (T1-T4)
  3  Uydurma örnek kişi (ornek_girdi.json): sonsal, duyarlılık, T4-T5, grafik → ciktilar/
  4  .kisisel/girdi.json varsa: aynı analiz → .kisisel/ciktilar/ (repoya girmez)
"""

import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import vaka
from vaka import Ayar, Onsel, ozetle, sonsal, yuzdelik

import veri as v3veri   # noqa: E402  (boy araştırması sürüm 3: Berkeley verisi, vaka.py yolu ekledi)

KOK = Path(__file__).resolve().parent
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
OZEL = KOK / ".kisisel"
TOHUM = 20261007
N = 1_200_000   # sapma 2: ESS için 200 000 → 1 200 000
TESTLER, OZET = [], {}
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:5.0f} sn]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'} ({deger})")


log("Önsel kohort")
ONSEL = {"erkek": Onsel("erkek", N, TOHUM)}
OZET["onsel_erkek"] = dict(N=N, H25_ort=ONSEL["erkek"].mk, H25_sd=ONSEL["erkek"].sk)


# ---------------------------------------------------------------------------
# 2. Doğrulama: Berkeley
# ---------------------------------------------------------------------------

SABLON = [("o1", (14.10, 14.20), "bilinmiyor"), ("o2", (14.90, 15.15), "bilinmiyor"),
          ("isaret", (16.20, 16.45), "bilinmiyor"), ("simdi", (17.20, 17.20), "aksam")]


def berkeley_vakalari():
    d = v3veri.berkeley()
    d = d[d.cinsiyet == "erkek"]
    out = []
    for i, g in d.groupby("id"):
        g = g.sort_values("yas")
        # Sapma 1: bitiş noktası her kişinin son ölçüm yaşı (18-21); 21 yaşında ölçümü olan tek kişi vardı
        if g.yas.min() < 13.5 and g.yas.max() >= 18.0:
            out.append((i, g.yas.values, g.boy.values))
    return out


def sentetik_girdi(yas, boy, rng):
    """Berkeley kişisinin gerçek eğrisinden, PLAN 3.4'teki bilgi yapısıyla gürültülü girdi üretir."""
    H = lambda a: float(np.interp(a, yas, boy))
    r, olc = {}, []
    for ad, (lo, hi), saat in SABLON:
        a = rng.uniform(lo, hi)
        f = rng.uniform(*vaka.SAAT[saat])
        r[ad] = H(a) - vaka.D_GUNICI * f
        o = dict(ad=ad, yas=[lo, hi], saat=saat)
        if ad in ("o1", "o2"):
            o.update(deger=float(np.round(r[ad] + rng.normal(0, 1.0))), hata_sd=1.0, ayakkabi="yok")
        elif ad == "simdi":
            alt = float(np.floor(r[ad] + rng.normal(0, 0.7)))
            o.update(aralik=[alt, alt + 1.0], hata_sd=0.7)
        else:
            o["isaret"] = True
        olc.append(o)
    fark = r["isaret"] - r["simdi"] + rng.normal(0, 0.5)
    return dict(cinsiyet="erkek", simdiki_yas=17.20, olcumler=olc,
                farklar=[dict(a="isaret", b="simdi", deger=float(fark), sd=0.5)]), H


log("Berkeley doğrulaması")
on = ONSEL["erkek"]
rng = np.random.default_rng(TOHUM + 7)
simdi_onsel = on.boy(np.full(N, 17.20))
satir = []
for i, yas, boy in berkeley_vakalari():
    girdi, H = sentetik_girdi(yas, boy, rng)
    s = sonsal(on, girdi, Ayar(anne_baba=False), tohum=int(rng.integers(1e9)))
    w = s["w"]
    t_son = float(yas.max())
    H_son = on.boy(np.full(N, t_son))
    gercek_kalan, gercek_Hson = H(t_son) - H(17.20), H(t_son)
    k10, k50, k90 = yuzdelik(H_son - s["simdi"], w, [10, 50, 90])
    h10, h50, h90 = yuzdelik(H_son, w, [10, 50, 90])
    onsel_med = float(np.median(H_son - simdi_onsel))
    satir.append(dict(id=i, son_yas=t_son, gercek_kalan=gercek_kalan, kalan_p10=k10, kalan_medyan=k50, kalan_p90=k90,
                      gercek_Hson=gercek_Hson, Hson_p10=h10, Hson_medyan=h50, Hson_p90=h90, ESS=s["ess"],
                      kapsama_kalan=k10 <= gercek_kalan <= k90, kapsama_Hson=h10 <= gercek_Hson <= h90,
                      hata_sonsal=abs(k50 - gercek_kalan), hata_onsel=abs(onsel_med - gercek_kalan)))
bv = pd.DataFrame(satir)
bv.to_csv(CIKTI / "berkeley_dogrulama.csv", index=False, float_format="%.3f")
OZET["berkeley"] = dict(n=len(bv), gercek_kalan_medyan=float(bv.gercek_kalan.median()), son_yas_medyan=float(bv.son_yas.median()),
                        kapsama_kalan=float(bv.kapsama_kalan.mean()), kapsama_Hson=float(bv.kapsama_Hson.mean()),
                        MAE_sonsal=float(bv.hata_sonsal.mean()), MAE_onsel=float(bv.hata_onsel.mean()),
                        ESS_medyan=float(bv.ESS.median()), ESS_min=float(bv.ESS.min()))
# Sapma 3 (sonradan): T1 kaldığı için kalan büyüme aralığı Berkeley'deki gerçek hata dağılımıyla genişletilir
# (artık = gerçek − sonsal medyan; uyumlu tahmin / "conformal" yaklaşımı). Ufuk 17.2 → 18-21 yaş.
ARTIK = dict(zip(["p2.5", "p10", "p50", "p90", "p97.5"],
                 map(float, np.percentile(bv.gercek_kalan - bv.kalan_medyan, [2.5, 10, 50, 90, 97.5]))))
OZET["berkeley"]["artik_yuzdelikleri"] = ARTIK
b = OZET["berkeley"]
test("T1", f"Berkeley (n={b['n']}): kalan büyüme 17.2→son ölçüm (18-21 yaş) için %80 aralık kapsaması", f"{b['kapsama_kalan']:.2f}",
     "0.68-0.92", 0.68 <= b["kapsama_kalan"] <= 0.92)
test("T2", "Berkeley: son ölçüm yaşındaki boy için %80 aralık kapsaması", f"{b['kapsama_Hson']:.2f}", "0.68-0.92",
     0.68 <= b["kapsama_Hson"] <= 0.92)
test("T3", "Berkeley: kalan büyüme MAE, sonsal < önsel", f"{b['MAE_sonsal']:.2f} / {b['MAE_onsel']:.2f} cm",
     "sonsal < önsel", b["MAE_sonsal"] < b["MAE_onsel"])


# ---------------------------------------------------------------------------
# 3-4. Örnek kişi ve (varsa) gerçek kişi
# ---------------------------------------------------------------------------

VARYANTLAR = [Ayar(), Ayar(etiket="ayakkabı olabilir", ayakkabi=True), Ayar(etiket="D = 1.0 cm", D=1.0),
              Ayar(etiket="D = 2.0 cm", D=2.0), Ayar(etiket="işaret sabah çizildi", isaret_saat="sabah"),
              Ayar(etiket="işaret akşam çizildi", isaret_saat="aksam"), Ayar(etiket="hatalar 2 kat", hata_kat=2.0),
              Ayar(etiket="anne-baba yok", anne_baba=False), Ayar(etiket="yaş pencereleri ±0.1", yas_genislet=0.1)]


def grafik(on, s, girdi, yol, baslik):
    w = s["w"]
    yas = np.array(vaka.KAYIT)
    sec = yas >= 13.0
    Hq = np.array([yuzdelik(on.H[:, j].astype(float), w, [2.5, 10, 50, 90, 97.5]) for j in np.where(sec)[0]])
    x = yas[sec]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.fill_between(x, Hq[:, 0], Hq[:, 4], color="#2a78d6", alpha=0.15, lw=0, label="%95 aralık")
    ax.fill_between(x, Hq[:, 1], Hq[:, 3], color="#2a78d6", alpha=0.30, lw=0, label="%80 aralık")
    ax.plot(x, Hq[:, 2], color="#2a78d6", lw=1.8, label="medyan (sabah boyu)")
    for o in girdi["olcumler"]:
        xm = np.mean(o["yas"])
        if "deger" in o:
            ax.errorbar(xm, o["deger"], xerr=(o["yas"][1] - o["yas"][0]) / 2, yerr=o.get("hata_sd", 1), fmt="o",
                        color="#eb6834", ms=5, capsize=3)
        elif "aralik" in o:
            ax.errorbar(xm, np.mean(o["aralik"]), yerr=0.5, fmt="s", color="#eb6834", ms=5, capsize=3)
    ax.set_xlabel("Yaş")
    ax.set_ylabel("Boy (cm)")
    ax.set_title(baslik)
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(yol, dpi=150)
    plt.close(fig)


def analiz(girdi, hedef, baslik, kararlilik=False):
    c = girdi["cinsiyet"]
    if c not in ONSEL:
        ONSEL[c] = Onsel(c, N, TOHUM)
    on = ONSEL[c]
    sonuc = {"girdi": girdi, "varyantlar": {}}
    for ayar in VARYANTLAR:
        s = sonsal(on, girdi, ayar, tohum=TOHUM)
        sonuc["varyantlar"][ayar.etiket] = ozetle(s)
        if ayar.etiket == "ana":
            ana = s
    m = sonuc["varyantlar"]["ana"]
    sonuc["kalibre_sapma3"] = {
        "not": "Sonradan eklendi (PLAN sapma 3). Sonsal medyan + Berkeley artık yüzdelikleri; ufuk ~1-4 yıl.",
        "kalan": {q: m["kalan"]["medyan"] + ARTIK[q] for q in ("p2.5", "p10", "p90", "p97.5")} | {"medyan": m["kalan"]["medyan"]},
        "H25": {q: m["H25"]["medyan"] + ARTIK[q] for q in ("p2.5", "p10", "p90", "p97.5")} | {"medyan": m["H25"]["medyan"]}}
    grafik(on, ana, girdi, hedef / "buyume_egrisi.png", baslik)
    if kararlilik:
        on2 = Onsel(c, N, TOHUM + 1)
        s2 = sonsal(on2, girdi, Ayar(), tohum=TOHUM + 1)
        sonuc["kararlilik_ikinci_tohum"] = ozetle(s2)
    (hedef / "sonuc.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    tablo = pd.DataFrame([{"varyant": k, "ESS": v["ESS"], **{f"{a}_{q}": v[a][q] for a in ("simdi", "son_yil", "kalan", "H25", "tepe_yasi")
                                                            for q in ("p10", "medyan", "p90")},
                           "P_kalan_1cm": v["P_kalan_en_az_1cm"], "P_kalan_2cm": v["P_kalan_en_az_2cm"]}
                          for k, v in sonuc["varyantlar"].items()])
    tablo.to_csv(hedef / "varyantlar.csv", index=False, float_format="%.3f")
    return sonuc


log("Örnek kişi (uydurma)")
ornek = json.loads((KOK / "ornek_girdi.json").read_text(encoding="utf-8"))
so = analiz(ornek, CIKTI, "Uydurma örnek kişi: sonsal büyüme eğrisi", kararlilik=True)
ana = so["varyantlar"]["ana"]
fark = abs(ana["kalan"]["medyan"] - so["kararlilik_ikinci_tohum"]["kalan"]["medyan"])
ess_ok = ana["ESS"] >= 200 and b["ESS_medyan"] >= 200
test("T4", "ESS: örnek kişi ve Berkeley medyanı", f"{ana['ESS']:.0f} / {b['ESS_medyan']:.0f}", "≥ 200", ess_ok)
test("T5", "Örnek kişi: iki tohumla kalan büyüme medyanı farkı", f"{fark:.3f} cm", "< 0.1 cm", fark < 0.1)

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
OZET["testler"] = TESTLER
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")

if (OZEL / "girdi.json").exists():
    log("Kişisel vaka (.kisisel/, repoya girmez)")
    (OZEL / "ciktilar").mkdir(exist_ok=True)
    kg = json.loads((OZEL / "girdi.json").read_text(encoding="utf-8"))
    analiz(kg, OZEL / "ciktilar", "Kişisel vaka: sonsal büyüme eğrisi")
log("Bitti")
