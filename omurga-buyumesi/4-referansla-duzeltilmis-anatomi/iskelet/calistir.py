"""
Anatomik iskelet: statik görseller ve geometri testleri. Tek komut:

    python calistir.py

Çıktılar (ciktilar/):
  anatomi_karti.png      etiketli yan görünüm (22 yaş, tipik erkek)
  iskelet_buyume.png     13 / 16 / 22 yaş yan yana: bacak önce durur, gövde devam eder
  on_gorunum_skolyoz.png ön görünüm, 0° ve 30° Cobb
  karsilastirma_gogus.png  sürüm 3 / sürüm 4 / referans (Gray's Anatomy 1918, kamu malı) göğüs kafesi
  once_sonra.png         sürüm 3 ve sürüm 4 iskeleti yan yana
  testler.csv            geometri testleri (I1-I3 sürüm 3'ten, I4-I8 sürüm 4'te yeni)

Referans görseller ilk çalıştırmada Wikimedia Commons'tan indirilir, SHA-256 ile doğrulanır (referans.py).
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOK = Path(__file__).resolve().parent
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK.parents[1] / "1-kaldiraclar-protokol-ve-animasyon" / "simulasyon"))
import anatomi          # noqa: E402
import omurga           # noqa: E402
import referans         # noqa: E402
import importlib.util   # noqa: E402

_spec = importlib.util.spec_from_file_location("anatomi_v3", KOK.parents[1] / "3-anatomik-iskelet" / "iskelet" / "anatomi.py")
anatomi_v3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anatomi_v3)

CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})
YUZEY, MUR, MUR2 = "#fcfcfb", "#0b0b0b", "#52514e"
BACAK, GOVDE = "#2a78d6", "#1baf7a"
TEST = []

yaslar = [13.0, 16.0, 22.0]
_, _, _, _, B, G = omurga.tipik_kisi("erkek", yaslar)

# Anatomi kartı
fig, ax = plt.subplots(figsize=(9, 10), facecolor=YUZEY)
geo = anatomi.yan(ax, B[-1], G[-1], plak_govde=0.7, plak_bacak=0.7, etiket=True)
ax.set_xlim(-80, 80)
ax.set_ylim(-3, 190)
ax.axis("off")
ax.set_title("İskeletin neresi büyür? (yan görünüm, tipik erkek, 22 yaş)", fontsize=13, color=MUR, loc="left")
ax.text(-80, -2, "Boy, bacak ve oturma boyu: sürüm 3 büyüme modeli. İç oranlar görsel varsayımdır (oranlar.md). "
        "Tıbbi tavsiye değildir.", fontsize=8, color=MUR2)
fig.tight_layout()
fig.savefig(CIKTI / "anatomi_karti.png", dpi=150)
lim = ax.dataLim.bounds
plt.close(fig)
TEST.append(dict(test="I1", aciklama="Anatomi kartı: iskeletin tepesi = model boyu", deger=f"{lim[1] + lim[3]:.2f} / {B[-1] + G[-1]:.2f} cm",
                 olcut="göreli fark < %0.2", sonuc="GEÇTİ" if abs(lim[1] + lim[3] - B[-1] - G[-1]) / (B[-1] + G[-1]) < 0.002 else "KALDI"))
TEST.append(dict(test="I2", aciklama="Omur sayıları", deger=str(geo["sayim"]), olcut="C7, T12, L5",
                 sonuc="GEÇTİ" if geo["sayim"] == {"C": 7, "T": 12, "L": 5} else "KALDI"))

# Büyüme karşılaştırması
fig, axs = plt.subplots(1, 3, figsize=(13, 7.5), facecolor=YUZEY, sharey=True)
for ax, a, b, g in zip(axs, yaslar, B, G):
    aktif = {13.0: (1.0, 1.0), 16.0: (0.9, 0.15), 22.0: (0.05, 0.0)}[a]
    anatomi.yan(ax, b, g, plak_govde=aktif[0], plak_bacak=aktif[1])
    ax.axhline(b, color=BACAK, lw=0.9, ls=":")
    ax.axhline(b + g, color=MUR2, lw=0.9, ls=":")
    ax.text(-62, b + 1.5, f"bacak {b:.1f}", fontsize=10, color=BACAK)
    ax.text(-62, b + g + 1.5, f"boy {b + g:.1f}", fontsize=10, color=MUR2)
    ax.set_xlim(-65, 60)
    ax.set_ylim(-3, 190)
    ax.axis("off")
    ax.set_title(f"{a:.0f} yaş · oturma boyu {g:.1f} cm", fontsize=12, color=MUR)
fig.suptitle("Tipik erkek (model): 16 yaşından sonra bacak neredeyse durur, gövde uzamaya devam eder", fontsize=13,
             color=MUR, x=0.02, ha="left")
fig.text(0.02, 0.015, f"16 → 22 yaş: bacak +{(B[2] - B[1]):.1f} cm, gövde +{(G[2] - G[1]):.1f} cm. Renkli plak = aktif, gri = kapanmış. "
         "İç oranlar görsel varsayım. Tıbbi tavsiye değildir.", fontsize=9, color=MUR2)
fig.tight_layout(rect=(0, 0.03, 1, 0.95))
fig.savefig(CIKTI / "iskelet_buyume.png", dpi=150)
plt.close(fig)
TEST.append(dict(test="I3", aciklama="16 → 22 yaş: gövde artışı > bacak artışı (model, iskelet aynı değerlerle çiziliyor)",
                 deger=f"gövde {G[2] - G[1]:.2f}, bacak {B[2] - B[1]:.2f} cm", olcut="gövde > bacak",
                 sonuc="GEÇTİ" if (G[2] - G[1]) > (B[2] - B[1]) else "KALDI"))

# Ön görünüm, skolyoz
fig, axs = plt.subplots(1, 2, figsize=(9, 7.5), facecolor=YUZEY, sharey=True)
for ax, c in zip(axs, (0, 30)):
    anatomi.on(ax, B[-1], G[-1], cobb=c, plak_govde=0.05)
    ax.set_xlim(-60, 60)
    ax.set_ylim(-3, 190)
    ax.axis("off")
    kay = omurga.stokes_kayip_mm(c) if c >= 10 else 0
    ax.set_title(f"Cobb {c}° · ölçülen boy kaybı ~{kay:.0f} mm (Stokes 2008)", fontsize=11, color=MUR)
fig.text(0.02, 0.015, "Eğriliğin genliği şematiktir; kayıp değeri Stokes 2008 formülünden. Tıbbi tavsiye değildir.",
         fontsize=8.5, color=MUR2)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(CIKTI / "on_gorunum_skolyoz.png", dpi=150)
plt.close(fig)

# --- Sürüm 4 göğüs kafesi testleri (README "Tuhaflık kontrol tablosu"; kodla birlikte yazıldı, ön kayıtlı değil) ---
gg = geo["gogus"]
TEST.append(dict(test="I4", aciklama="Kaburga sayısı ve bağlantılar: 12 kaburga; 1-7 göğüs kemiğine, 8-10 kavse, 11-12 serbest",
                 deger=f"{gg['kaburga']} kaburga; {gg['kikirdak_sternum']} sternal, {gg['kavis']} kavis, "
                       f"{gg['kaburga'] - gg['kikirdak_sternum'] - gg['kavis']} serbest", olcut="12; 7 / 3 / 2",
                 sonuc="GEÇTİ" if (gg["kaburga"], gg["kikirdak_sternum"], gg["kavis"]) == (12, 7, 3) else "KALDI"))
d = gg["dusus"]
egim_ok = all(v > 1.0 for v in d.values()) and max(d, key=d.get) in range(4, 10) and d[1] < d[6] and d[12] < d[6]
TEST.append(dict(test="I5", aciklama="Kaburga eğimi: her kaburganın ön ucu kendi omurundan aşağıda; en çok orta kaburgalar iner",
                 deger="omur seviyesi: " + ", ".join(f"{i}:{d[i]:.1f}" for i in (1, 4, 7, 10, 12)),
                 olcut="hepsi > 1; en büyük 4-9 arası; 1 ve 12 < 6", sonuc="GEÇTİ" if egim_ok else "KALDI"))
y_sap, y_han = gg["sternum"]
T2, T3, T9 = gg["seviye"][2], gg["seviye"][3], gg["seviye"][9]
TEST.append(dict(test="I6", aciklama="Göğüs kemiği seviyesi: üst ucu T2-T3 arası, alt ucu T9'un altında",
                 deger=f"üst {y_sap:.1f} (T2 {T2:.1f}, T3 {T3:.1f}); alt {y_han:.1f} (T9 {T9:.1f})",
                 olcut="T3 ≤ üst ≤ T2; alt < T9", sonuc="GEÇTİ" if (T3 <= y_sap <= T2 and y_han < T9) else "KALDI"))
TEST.append(dict(test="I7", aciklama="Köprücük kafesin tepesinde: en alçak noktası göğüs kemiği sapının üst ucunun üstünde",
                 deger=f"köprücük alt {gg['kopru_alt']:.1f}, sap üstü {y_sap:.1f} cm", olcut="köprücük ≥ sap üstü",
                 sonuc="GEÇTİ" if gg["kopru_alt"] >= y_sap else "KALDI"))

# Önce / sonra / referans: göğüs kafesi
fig, axs = plt.subplots(1, 3, figsize=(15, 7.2), facecolor=YUZEY, gridspec_kw=dict(width_ratios=[1, 1, 0.9]))
b, g = B[-1], G[-1]
for ax, mod, baslik in ((axs[0], anatomi_v3, "Sürüm 3 (önce)"), (axs[1], anatomi, "Sürüm 4 (sonra)")):
    mod.yan(ax, b, g, plak_govde=0.7, plak_bacak=0.7, kollar=False)
    ax.set_xlim(-0.33 * g, 0.27 * g)
    ax.set_ylim(b + 0.30 * g, b + 0.80 * g)
    ax.axis("off")
    ax.set_title(baslik, fontsize=12, color=MUR, loc="left")
ref = plt.imread(referans.indir("gray966"))
axs[2].imshow(ref)
axs[2].axis("off")
axs[2].set_title("Referans: Gray's Anatomy (1918), Fig. 966", fontsize=12, color=MUR, loc="left")
fig.text(0.01, 0.035, "Sürüm 3'teki tuhaflıklar: kaburgalar yatay ve tarak gibi; 10 kaburga; hepsi aynı uzunlukta; göğüs kemiği kopuk bir çubuk; "
         "kıkırdak ve kaburga kavsi yok; köprücük göğüs ortasında.", fontsize=9, color=MUR2)
fig.text(0.01, 0.012, "Sürüm 4: 12 kaburga, öne doğru aşağı eğimli; 1-7 kıkırdakla göğüs kemiğine, 8-10 kaburga kavsine; 11-12 serbest; "
         "üç parçalı göğüs kemiği; köprücük kafesin tepesinde. Referans görsel kamu malıdır (Wikimedia Commons).",
         fontsize=9, color=MUR2)
fig.tight_layout(rect=(0, 0.05, 1, 0.96))
fig.savefig(CIKTI / "karsilastirma_gogus.png", dpi=150)
plt.close(fig)

# Önce / sonra: tüm iskelet
fig, axs = plt.subplots(1, 2, figsize=(10, 9), facecolor=YUZEY, sharey=True)
for ax, mod, baslik in ((axs[0], anatomi_v3, "Sürüm 3 (önce)"), (axs[1], anatomi, "Sürüm 4 (sonra)")):
    mod.yan(ax, b, g, plak_govde=0.7, plak_bacak=0.7)
    ax.set_xlim(-60, 60)
    ax.set_ylim(-3, 190)
    ax.axis("off")
    ax.set_title(baslik, fontsize=12, color=MUR, loc="left")
fig.text(0.01, 0.012, "Sürüm 4'te ayrıca: bel eğrisi yumuşatıldı, diskler komşu omurları birleştiriyor, diz ve sakrum şekli düzeltildi, "
         "kol omurgayı örtmeyen kontur. Tıbbi tavsiye değildir.", fontsize=8.5, color=MUR2)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(CIKTI / "once_sonra.png", dpi=150)
plt.close(fig)

pd.DataFrame(TEST).to_csv(CIKTI / "testler.csv", index=False)
print(pd.DataFrame(TEST).to_string(index=False))
