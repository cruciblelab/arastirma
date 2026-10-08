"""
Anatomik iskelet: statik görseller ve geometri testleri. Tek komut:

    python calistir.py

Çıktılar (ciktilar/):
  anatomi_karti.png      etiketli yan görünüm (22 yaş, tipik erkek)
  iskelet_buyume.png     13 / 16 / 22 yaş yan yana: bacak önce durur, gövde devam eder
  on_gorunum_skolyoz.png ön görünüm, 0° ve 30° Cobb
  testler.csv            geometri testleri
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

pd.DataFrame(TEST).to_csv(CIKTI / "testler.csv", index=False)
print(pd.DataFrame(TEST).to_string(index=False))
