"""
Omurga uzaması: kaldıraçlar, ölçüm protokolü, notlu animasyon (PLAN.md). Tek komut:

    python calistir.py

  A  Kaldıraç tablosu (mm): kalan gövde büyümesi (model), eğrilik (Stokes 2008), duruş, mekanik, gün içi
  B  Ev ölçüm protokolü güç simülasyonu (oturma boyu ve bacak)
  C  Notlu animasyon (MP4 + GIF)
  T1-T5 ön kayıtlı testler. Çıktılar ciktilar/ altında.
"""

import json
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import animasyon
import omurga

KOK = Path(__file__).resolve().parent
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
REPO = KOK.parents[2]
TESTLER, OZET = [], {}
T0 = time.time()
YUZEY, MUREKKEP, MUREKKEP2, SOLUK, IZGARA = animasyon.YUZEY, animasyon.MUREKKEP, animasyon.MUREKKEP2, animasyon.SOLUK, animasyon.IZGARA


def log(*a):
    print(f"[{time.time() - T0:5.0f} sn]", *a, flush=True)


def test(ad, aciklama, deger, olcut, gecti):
    TESTLER.append(dict(test=ad, aciklama=aciklama, deger=deger, olcut=olcut, sonuc="GEÇTİ" if gecti else "KALDI"))
    log(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'} ({deger})")


def stil(ax):
    ax.set_facecolor(YUZEY)
    ax.grid(color=IZGARA, lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(SOLUK)
    ax.tick_params(colors=MUREKKEP2)


# ---------------------------------------------------------------------------
# A. Kaldıraçlar
# ---------------------------------------------------------------------------

log("A: kaldıraçlar")
yaslar = [16.0, 17.0, 25.0]
satir = []
for c in ("erkek", "kiz"):
    B, G = omurga.kohort_egrileri(c, 5000, yaslar)
    for i, bas in enumerate((16.0, 17.0)):
        dg, db = (G[2] - G[i]) * 10, (B[2] - B[i]) * 10
        satir.append(dict(cinsiyet=c, kaldirac=f"Kalan gövde büyümesi ({bas:.0f} → 25 yaş)", tur="kalıcı büyüme",
                          mm_medyan=np.median(dg), mm_p10=np.percentile(dg, 10), mm_p90=np.percentile(dg, 90),
                          kaynak="Sürüm 3 modeli (D)"))
        satir.append(dict(cinsiyet=c, kaldirac=f"Kalan bacak büyümesi ({bas:.0f} → 25 yaş)", tur="kalıcı büyüme",
                          mm_medyan=np.median(db), mm_p10=np.percentile(db, 10), mm_p90=np.percentile(db, 90),
                          kaynak="Sürüm 3 modeli (D)"))
for cobb in (10, 20, 30, 45):
    satir.append(dict(cinsiyet="her ikisi", kaldirac=f"Skolyoz eğrisi {cobb}° (Cobb): ölçülen boy kaybı", tur="ölçülen boy kaybı",
                      mm_medyan=float(omurga.stokes_kayip_mm(cobb)), mm_p10=np.nan, mm_p90=np.nan, kaynak="Stokes 2008 (C)"))
satir += [
    dict(cinsiyet="her ikisi", kaldirac="Duruş (kambur ↔ dik)", tur="ölçülen boy (geri dönüşlü)",
         mm_medyan=np.mean(omurga.DURUS_MM), mm_p10=omurga.DURUS_MM[0], mm_p90=omurga.DURUS_MM[1],
         kaynak="Spor ve boy sürüm 1, bölüm 4.4 (D)"),
    dict(cinsiyet="her ikisi", kaldirac="Egzersizin plağa mekanik etkisi (üst sınır)", tur="kalıcı büyüme",
         mm_medyan=omurga.MEKANIK_UST_MM, mm_p10=0.0, mm_p90=omurga.MEKANIK_UST_MM, kaynak="Spor ve boy sürüm 1 (D)"),
    dict(cinsiyet="her ikisi", kaldirac="Gün içi disk değişimi (sabah → akşam)", tur="geçici",
         mm_medyan=omurga.GUNICI_MM, mm_p10=np.nan, mm_p90=np.nan, kaynak="Spor ve boy sürüm 1 (C)"),
]
kal = pd.DataFrame(satir)
kal.to_csv(CIKTI / "kaldiraclar.csv", index=False, float_format="%.2f")
print(kal.round(2).to_string(index=False))

d30, d40 = omurga.stokes_kayip_mm(30), omurga.stokes_kayip_mm(40)
test("T2", "Stokes formülü: Cobb 30 → 40° kayıp farkı (kaynak örneği ~6.7 mm)", f"{d40 - d30:.2f} mm", "|Δ − 6.7| < 0.3",
     abs(d40 - d30 - 6.7) < 0.3)

# Kaldıraç grafiği (erkek, 17 → 25)
e = kal[(kal.cinsiyet.isin(["erkek", "her ikisi"])) & ~kal.kaldirac.str.contains("16 →")]
e = e[~e.kaldirac.str.contains("Skolyoz eğrisi (?:10|20)°")].copy()
renk = {"kalıcı büyüme": animasyon.GOVDE, "ölçülen boy kaybı": animasyon.EGRI, "ölçülen boy (geri dönüşlü)": SOLUK,
        "geçici": SOLUK}
e = e.sort_values("mm_medyan")
fig, ax = plt.subplots(figsize=(10, 4.6), facecolor=YUZEY)
y = np.arange(len(e))
for yi, (_, r) in zip(y, e.iterrows()):
    ax.barh(yi, r.mm_medyan, color=renk[r.tur], height=0.62, hatch="///" if r.tur == "geçici" else None,
            edgecolor=YUZEY if r.tur != "geçici" else MUREKKEP2, lw=0.6)
    if not np.isnan(r.mm_p10) and r.mm_p90 > r.mm_p10:
        ax.plot([r.mm_p10, r.mm_p90], [yi, yi], color=MUREKKEP, lw=1.2)
    ax.text(max(r.mm_medyan, r.mm_p90 if not np.isnan(r.mm_p90) else 0) + 0.6, yi, f"{r.mm_medyan:.1f} mm · {r.tur}",
            va="center", fontsize=8.5, color=MUREKKEP2)
ax.set_yticks(y, e.kaldirac, fontsize=8.5, color=MUREKKEP)
ax.set_xlabel("Ölçülen boya etkisi (mm)", color=MUREKKEP2)
ax.set_xlim(0, e.mm_p90.fillna(e.mm_medyan).max() * 1.45)
ax.set_title("Omurga tarafındaki kaldıraçlar (erkek, 17 yaştan sonra). Çizgi: %10-90 ya da kaynak aralığı",
             fontsize=10, color=MUREKKEP, loc="left")
stil(ax)
fig.tight_layout()
fig.savefig(CIKTI / "kaldiraclar.png", dpi=150)
plt.close(fig)


# ---------------------------------------------------------------------------
# B. Ölçüm protokolü
# ---------------------------------------------------------------------------

log("B: protokol")
ANA = dict(v_g=0.6, v_b=0.3, sigma_o=0.5, sigma_s=0.3)
tas = []
for aralik in (1, 2, 3, 6):
    for sure in (6, 12, 18):
        for k in (1, 3, 5):
            g = omurga.protokol_gucu(ANA["v_g"], aralik, sure, k, ANA["sigma_o"], ANA["sigma_s"])
            b = omurga.protokol_gucu(ANA["v_b"], aralik, sure, k, ANA["sigma_o"], ANA["sigma_s"], iki_olcum=True)
            tas.append(dict(aralik_ay=aralik, sure_ay=sure, k=k, n_seans=g["n_seans"], toplam_olcum=g["n_seans"] * k,
                            guc_govde=g["guc"], ci90_govde=g["ci90_genislik"], guc_bacak=b["guc"], ci90_bacak=b["ci90_genislik"]))
tas = pd.DataFrame(tas).dropna(subset=["guc_govde"])
tas.to_csv(CIKTI / "protokol_tasarimlar.csv", index=False, float_format="%.3f")
uygun = tas[tas.guc_govde >= 0.80].sort_values(["toplam_olcum", "sure_ay", "aralik_ay"])
oneri = uygun.iloc[0].to_dict() if len(uygun) else None
OZET["protokol_oneri"] = oneri
log("öneri:", oneri)

# Duyarlılık: önerilen tasarımda parametreler birer birer
duy = []
if oneri:
    a, s_, k = int(oneri["aralik_ay"]), int(oneri["sure_ay"]), int(oneri["k"])
    for ad, deg in [("v_g", 0.3), ("v_g", 1.0), ("sigma_o", 0.3), ("sigma_o", 0.8), ("sigma_s", 0.0), ("sigma_s", 0.5)]:
        p = dict(ANA)
        p[ad] = deg
        g = omurga.protokol_gucu(p["v_g"], a, s_, k, p["sigma_o"], p["sigma_s"])
        duy.append(dict(hedef="gövde", parametre=ad, deger=deg, guc=g["guc"]))
    for vb in (0.1, 0.3, 0.5):
        for sure in (12, 18):
            b = omurga.protokol_gucu(vb, a, sure, k, ANA["sigma_o"], ANA["sigma_s"], iki_olcum=True)
            duy.append(dict(hedef="bacak", parametre=f"v_b (süre {sure} ay)", deger=vb, guc=b["guc"]))
pd.DataFrame(duy).to_csv(CIKTI / "protokol_duyarlilik.csv", index=False, float_format="%.3f")

# T3: v = 0'da yanlış pozitif oranı (ana tasarım)
if oneri:
    fp = omurga.protokol_gucu(0.0, a, s_, k, ANA["sigma_o"], ANA["sigma_s"])["guc"]
    test("T3", "Protokol testi: büyüme yokken (v = 0) yanlış pozitif oranı", f"{fp:.3f}", "0.04-0.06", 0.04 <= fp <= 0.06)
    g1 = omurga.protokol_gucu(ANA["v_g"], a, s_, k, ANA["sigma_o"], ANA["sigma_s"], tohum=1)["guc"]
    g2 = omurga.protokol_gucu(ANA["v_g"], a, s_, k, ANA["sigma_o"], ANA["sigma_s"], tohum=2)["guc"]
    test("T4", "Monte Carlo kararlılığı: önerilen tasarımda iki tohumla güç farkı", f"{abs(g1 - g2):.4f}", "< 0.02",
         abs(g1 - g2) < 0.02)

# Protokol grafiği: süreye göre güç; çizgiler = ölçüm sıklığı (seans başına 3 tekrar); gövde ve bacak yan yana
fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), facecolor=YUZEY, sharey=True)
renkler = {1: animasyon.BACAK, 2: animasyon.EGRI, 3: animasyon.GOVDE}
etiket = {1: "her ay", 2: "2 ayda bir", 3: "3 ayda bir"}
for ax, hedef, baslik in ((axs[0], "guc_govde", f"Gövde (oturma boyu), {ANA['v_g']} cm/yıl"),
                          (axs[1], "guc_bacak", f"Bacak (boy − oturma boyu), {ANA['v_b']} cm/yıl")):
    for aralik in (1, 2, 3):
        t = tas[(tas.aralik_ay == aralik) & (tas.k == 3)].sort_values("sure_ay")
        ax.plot(t.sure_ay, t[hedef], "-o", color=renkler[aralik], lw=2, ms=8, mec=YUZEY, mew=2, label=etiket[aralik])
    ax.axhline(0.8, color=MUREKKEP2, lw=0.8, ls=":")
    ax.text(6.1, 0.82, "hedef güç 0.80", fontsize=8, color=MUREKKEP2)
    ax.set_title(baslik, fontsize=10, color=MUREKKEP, loc="left")
    ax.set_xlabel("Toplam süre (ay); her seansta 3 ölçüm, ortalaması", color=MUREKKEP2)
    ax.set_xticks([6, 12, 18])
    ax.set_xlim(5, 19)
    ax.set_ylim(0, 1.02)
    stil(ax)
axs[0].set_ylabel("Uzamayı yakalama olasılığı (güç)", color=MUREKKEP2)
axs[0].legend(frameon=False, fontsize=8.5, loc="upper left", bbox_to_anchor=(0.0, 0.78), title="Ölçüm sıklığı",
              title_fontsize=8.5)
fig.tight_layout()
fig.savefig(CIKTI / "protokol_guc.png", dpi=150)
plt.close(fig)


# ---------------------------------------------------------------------------
# C. Animasyon
# ---------------------------------------------------------------------------

log("C: animasyon")
mp4, gif = CIKTI / "omurga_animasyon.mp4", CIKTI / "omurga_animasyon.gif"
an = animasyon.uret(mp4, gif)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
                "fps=10,scale=840:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                str(gif)], check=True)
OZET["animasyon_olaylar"] = an["olaylar"]
# T1: gösterilen sayılar = model (aynı tipik kişi, aynı yaşlar, bağımsız çağrı)
g_yas = [x[0] for x in an["gosterilen"]]
_, _, _, _, Bm, Gm = omurga.tipik_kisi("erkek", g_yas)
fark = max(max(abs(h - (Bm[i] + Gm[i])), abs(gg - Gm[i]), abs(bb - Bm[i]))
           for i, (_, h, gg, bb) in enumerate(an["gosterilen"]))
test("T1", "Animasyondaki boy/oturma boyu/bacak = sürüm 3 modeli (aynı kişi ve yaşlar)", f"{fark:.2e} cm", "< 1e-6",
     fark < 1e-6)
boyut = gif.stat().st_size / 1e6
test("T5", "Animasyon dosyası (GIF boyutu, kare sayısı)", f"{boyut:.2f} MB, {an['kare']} kare", "< 5 MB, ≥ 60 kare",
     boyut < 5 and an["kare"] >= 60)
OZET["animasyon"] = dict(kare=an["kare"], gif_mb=boyut, mp4_mb=mp4.stat().st_size / 1e6)

# Animasyonun 4 karelik özeti (README'de statik önizleme için)
tip = pd.DataFrame(an["gosterilen"], columns=["yas", "boy", "oturma_boyu", "bacak"])
tip.to_csv(CIKTI / "animasyon_tipik_erkek.csv", index=False, float_format="%.3f")

pd.DataFrame(TESTLER).to_csv(CIKTI / "testler.csv", index=False)
OZET["testler"] = TESTLER
(CIKTI / "ozet.json").write_text(json.dumps(OZET, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
log("Bitti")
