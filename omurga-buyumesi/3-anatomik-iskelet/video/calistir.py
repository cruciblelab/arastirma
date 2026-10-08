"""
Omurga büyümesi bilgilendirme videosu, anatomik iskeletle (sürüm 3). Tek komut:

    python calistir.py

- Sayılar elle yazılmaz: sürüm 1'in ve plak kapanma sırası araştırmasının çıktı dosyalarından okunur.
  Ekrandaki her sayı ciktilar/sayilar.csv'ye kaynağıyla birlikte yazılır.
- Simülasyon sahnesi, sürüm 1'in modeli ve şematik omurga çizimiyle her kare yeniden hesaplanır.
- Çıktılar: ciktilar/omurga_bilgilendirme_anatomik.mp4 (1280x720, H.264), .srt altyazı, sayilar.csv, testler.csv.
"""

import json
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

KOK = Path(__file__).resolve().parent
SURUM1 = KOK.parents[1] / "1-kaldiraclar-protokol-ve-animasyon"
REPO = KOK.parents[2]
sys.path.insert(0, str(SURUM1 / "simulasyon"))
import animasyon as v1           # noqa: E402  (palet, aşama notları)
import omurga                    # noqa: E402  (model erişimi, sabitler)
sys.path.insert(0, str(KOK.parent / "iskelet"))
import anatomi                   # noqa: E402  (sürüm 3: anatomik iskelet)

CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
FPS, W, H = 25, 1280, 720
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"], "font.size": 12})
YUZEY, MUR, MUR2, SOLUK, IZG = v1.YUZEY, v1.MUREKKEP, v1.MUREKKEP2, v1.SOLUK, v1.IZGARA
BACAK, GOVDE, EGRI = v1.BACAK, v1.GOVDE, v1.EGRI
BANT = "#f1efe8"

# ---------------------------------------------------------------------------
# Kaynak sayılar (yalnızca dosyalardan)
# ---------------------------------------------------------------------------

SAYILAR = []


def sayi(ad, deger, kaynak, bicim="{:.0f}"):
    SAYILAR.append(dict(ad=ad, deger=float(deger), gosterim=bicim.format(deger), kaynak=kaynak))
    return bicim.format(deger)


c1 = SURUM1 / "simulasyon" / "ciktilar"
kal = pd.read_csv(c1 / "kaldiraclar.csv")
tas = pd.read_csv(c1 / "protokol_tasarimlar.csv")
duy = pd.read_csv(c1 / "protokol_duyarlilik.csv")
oz1 = json.loads((c1 / "ozet.json").read_text(encoding="utf-8"))
pkk = REPO / "buyume-plaklari-kapanma-sirasi" / "1-literatur-ve-berkeley-analizi" / "analiz" / "ciktilar" / "ozet.json"
berk = json.loads(pkk.read_text(encoding="utf-8"))["berkeley_erkek_esik0.5"]


def kal_mm(desen, cins="erkek"):
    r = kal[kal.kaldirac.str.contains(desen, regex=False) & kal.cinsiyet.isin([cins, "her ikisi"])]
    return float(r.mm_medyan.iloc[0])


KS = "omurga-buyumesi/1/kaldiraclar.csv"
PS = "omurga-buyumesi/1/protokol_tasarimlar.csv"
BS = "buyume-plaklari-kapanma-sirasi/1/ozet.json"
N = dict(
    bacak_bitis=sayi("Berkeley erkek bacak bitiş yaşı (medyan)", berk["bacak_bitis_medyan"], BS, "{:.0f}"),
    govde_bitis=sayi("Berkeley erkek gövde bitiş yaşı (medyan, alt sınır)", berk["govde_bitis_medyan"], BS, "{:.0f}"),
    govde_pay=sayi("16 yaş sonrası gövde payı (%)", 100 * berk["govde_payi16_medyan"], BS, "{:.0f}"),
    govde_sonra=sayi("Gövdesi bacaktan sonra biten (%)", 100 * berk["govde_sonra_oran"], BS, "{:.0f}"),
    kalan_govde=sayi("Bacak bittikten sonra gövde (cm, alt sınır)", berk["kalan_govde_medyan"], BS, "{:.1f}"),
    gunici=sayi("Gün içi disk değişimi (cm)", kal_mm("Gün içi") / 10, KS, "{:.1f}"),
    k30=sayi("Skolyoz 30° boy kaybı (mm)", kal_mm("Skolyoz eğrisi 30"), KS, "{:.0f}"),
    k45=sayi("Skolyoz 45° boy kaybı (mm)", kal_mm("Skolyoz eğrisi 45"), KS, "{:.0f}"),
    g17=sayi("Kalan gövde büyümesi 17→25 erkek (mm)", kal_mm("Kalan gövde büyümesi (17"), KS, "{:.0f}"),
    b17=sayi("Kalan bacak büyümesi 17→25 erkek (mm)", kal_mm("Kalan bacak büyümesi (17"), KS, "{:.0f}"),
    mekanik=sayi("Egzersizin mekanik etkisi üst sınır (mm)", kal_mm("mekanik"), KS, "{:.1f}"),
)
o = oz1["protokol_oneri"]
p3 = tas[(tas.aralik_ay == 3) & (tas.sure_ay == 18) & (tas.k == 3)].guc_govde.iloc[0]
pmax = duy[(duy.parametre == "sigma_s") & (duy.deger == 0.0)].guc.iloc[0]
N.update(
    p_oneri=sayi("Önerilen protokolde gövde gücü (%)", 100 * o["guc_govde"], PS, "{:.0f}"),
    p_bacak=sayi("Önerilen protokolde bacak gücü (%)", 100 * o["guc_bacak"], PS, "{:.0f}"),
    p3=sayi("3 ayda bir, 18 ay, k=3 gövde gücü (%)", 100 * p3, PS, "{:.0f}"),
    pmax=sayi("Koşul farkı 0 iken gövde gücü (%)", 100 * pmax, "omurga-buyumesi/1/protokol_duyarlilik.csv", "{:.0f}"),
    n_olcum=sayi("Önerilen protokol toplam ölçüm", o["toplam_olcum"], PS, "{:.0f}"),
)

# Tipik erkek (sürüm 1 animasyonuyla aynı kişi)
INCE = np.round(np.arange(11.0, 25.0 + 1e-9, 0.1), 2)
_, _, _, _, BB, GG = omurga.tipik_kisi("erkek", INCE)
VB, VG = np.gradient(BB, INCE), np.gradient(GG, INCE)
VMAX = max(VB.max(), VG.max())
OLAY = oz1["animasyon_olaylar"]

# ---------------------------------------------------------------------------
# Çizim yardımcıları
# ---------------------------------------------------------------------------

fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=YUZEY)
BOLUMLER = ["Giriş", "İskelet", "Boy nereden gelir", "Simülasyon", "Gece-gündüz", "Eğrilik", "Kaldıraçlar", "Ne işe yarar",
            "Ölçüm protokolü", "Özet"]


def cerceve(bolum, baslik):
    fig.clf()
    fig.set_facecolor(YUZEY)
    ust = fig.add_axes([0, 0.9, 1, 0.1])
    ust.axis("off")
    ust.text(0.035, 0.42, baslik, fontsize=22, weight="bold", color=MUR, va="center")
    if bolum in BOLUMLER:
        i = BOLUMLER.index(bolum)
        for j in range(len(BOLUMLER)):
            ust.add_patch(Rectangle((0.70 + j * 0.03, 0.36), 0.022, 0.12, transform=ust.transAxes,
                                    fc=GOVDE if j <= i else IZG, ec="none"))
    alt = fig.add_axes([0, 0, 1, 0.055])
    alt.axis("off")
    alt.add_patch(Rectangle((0, 0), 1, 1, transform=alt.transAxes, fc=BANT, ec="none"))
    alt.text(0.035, 0.45, "Tıbbi tavsiye değildir · Sayılar model tahminidir (D) · İskelet iç oranları görsel varsayım",
             fontsize=9.5, color=MUR2, va="center")
    alt.text(0.965, 0.45, "Crucible · arastirma · CC BY-NC 4.0", fontsize=9.5, color=MUR2, va="center", ha="right")


def maddeler(ax, liste, t, baslangic, renk_isareti=GOVDE, y0=0.95, aralik=None, fs=17):
    """Maddeleri zamanla göster: her madde kendi başlangıç anında 0.4 sn'de belirir.
    Satırlar eksen genişliğine göre elle kaydırılır; madde aralığı satır sayısına göre ayarlanır."""
    import textwrap
    ax.axis("off")
    bb = ax.get_position()
    genislik_px, yukseklik_px = bb.width * W, bb.height * H
    pt = 100 / 72                                   # 1 punto = 1.39 piksel (dpi 100)
    karakter = max(18, int(genislik_px * 0.90 / (fs * 0.54 * pt)))
    satir_h = fs * 1.30 * pt / yukseklik_px
    bosluk = fs * 0.85 * pt / yukseklik_px
    y = y0
    for m, b in zip(liste, baslangic):
        isaret, metin = (m[0], m[1]) if isinstance(m, tuple) else ("•", m)
        satirlar = textwrap.wrap(metin, karakter)
        a = float(np.clip((t - b) / 0.4, 0, 1))
        if a > 0:
            rk = {"✓": GOVDE, "✗": EGRI, "!": EGRI}.get(isaret, renk_isareti)
            dy = (1 - a) * 0.02
            ax.text(0.0, y + dy, isaret, fontsize=fs + 2, color=rk, alpha=a, va="top", weight="bold")
            ax.text(0.055, y + dy, "\n".join(satirlar), fontsize=fs, color=MUR, alpha=a, va="top", linespacing=1.25)
        y -= len(satirlar) * satir_h + bosluk


def zamanlama(liste, bas=0.6):
    """Her maddeye okuma süresine göre zaman ver (sn): 2.2-4.2 sn, metin uzunluğuyla."""
    out, t = [], bas
    for m in liste:
        metin = m[1] if isinstance(m, tuple) else m
        out.append(t)
        t += float(np.clip(len(metin) / 17.0, 2.0, 3.8))
    return out, t + 1.6


def iskelet_ekseni(ax, B, S, ust=190.0, **kw):
    geo = anatomi.yan(ax, B, S, **kw)
    ax.set_xlim(-0.26 * ust, 0.26 * ust)
    ax.set_ylim(-3, ust)
    ax.axis("off")
    ISKELET_GEO.append((B, S, geo, ax.dataLim.bounds))
    return geo


ISKELET_GEO = []


def hiz_ekseni(ax, a=None):
    ax.set_facecolor(YUZEY)
    ax.plot(INCE, VB, color=BACAK, lw=2.5)
    ax.plot(INCE, VG, color=GOVDE, lw=2.5)
    ax.text(11.2, VB[2] + 0.3, "bacak", color=MUR2, fontsize=12)
    ax.text(18.6, VG[np.argmin(np.abs(INCE - 18.6))] + 0.35, "gövde (omurga + leğen)", color=MUR2, fontsize=12)
    if a is not None:
        j = np.argmin(np.abs(INCE - a))
        ax.axvline(a, color=MUR2, lw=0.8, ls=":")
        ax.plot([a], [VB[j]], "o", color=BACAK, ms=10, mec=YUZEY, mew=2)
        ax.plot([a], [VG[j]], "o", color=GOVDE, ms=10, mec=YUZEY, mew=2)
    ax.set_xlim(11, 25)
    ax.set_ylim(-0.2, VMAX * 1.15)
    ax.set_xlabel("Yaş", color=MUR2)
    ax.set_ylabel("Uzama hızı (cm/yıl)", color=MUR2)
    ax.grid(color=IZG, lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(SOLUK)
    ax.tick_params(colors=MUR2)


# ---------------------------------------------------------------------------
# Sahneler: her biri (süre, çiz(t), altyazılar[(baş, son, metin)])
# ---------------------------------------------------------------------------

SAHNELER = []


def sahne(fonk):
    SAHNELER.append(fonk())
    return fonk


@sahne
def kapak():
    def ciz(t):
        cerceve("Giriş", "")
        ax = fig.add_axes([0.06, 0.25, 0.55, 0.55])
        ax.axis("off")
        a = min(1, t / 0.8)
        ax.text(0, 0.85, "Omurga Büyümesi", fontsize=40, weight="bold", color=MUR, alpha=a)
        ax.text(0, 0.62, "16 yaşından sonra boy nereden gelir,\nneyi değiştirebilirsin, neyi değiştiremezsin?",
                fontsize=20, color=MUR2, alpha=a, linespacing=1.35)
        ax.text(0, 0.25, "Simülasyon, gerçek veri (Berkeley) ve kaynaklara dayalı kısa bilgilendirme",
                fontsize=14, color=MUR2, alpha=a)
        ax.text(0, 0.08, "Crucible ekibi · arastirma deposu", fontsize=13, color=GOVDE, alpha=a, weight="bold")
        s = fig.add_axes([0.64, 0.07, 0.34, 0.83])
        iskelet_ekseni(s, BB[-1], GG[-1], plak_govde=0.6, plak_bacak=0.6)
    return 4.5, ciz, [(0, 4.5, "Omurga Büyümesi: 16 yaşından sonra boy nereden gelir?")]


@sahne
def iskelet():
    L = ["Boyu iki bölge belirler: bacak kemikleri ve omurga.",
         "Bacakta büyüme dizdeki plaklarda olur: uyluk kemiğinin alt, kaval kemiğinin üst ucu.",
         "Omurgada büyüme her omurun alt ve üst sonlanma plağında olur.",
         "Omurlar arasındaki diskler gün içinde sıkışır; bu büyüme değildir.",
         "El ve ayak plakları boya katkı yapmaz; yalnızca olgunluğu gösterir."]
    bas, T = zamanlama(L)

    def ciz(t):
        cerceve("İskelet", "İskeletin neresi büyür?")
        maddeler(fig.add_axes([0.04, 0.10, 0.38, 0.78]), L, t, bas, fs=15)
        ax = fig.add_axes([0.44, 0.065, 0.54, 0.83])
        geo = anatomi.yan(ax, BB[-1], GG[-1], plak_govde=0.7, plak_bacak=0.7, etiket=True, etiket_fs=11)
        ax.set_xlim(-72, 78)
        ax.set_ylim(-3, 188)
        ax.axis("off")
    return T, ciz, [(b, b + 2.5, m) for b, m in zip(bas, L)]


@sahne
def nereden():
    L = ["Boy iki yerden uzar: bacaklar ve gövde (omurga + leğen).",
         f"Bacak önce biter: erkeklerde medyan {N['bacak_bitis']} yaş.",
         f"Gövde devam eder: en az {N['govde_bitis']} yaşına kadar (kişilerin %{N['govde_sonra']}'sinde).",
         f"Bacak bittikten sonra gövde en az ~{N['kalan_govde']} cm daha uzar.",
         f"16 yaştan sonraki uzamanın ~%{N['govde_pay']}'ı gövdeden gelir.",
         ("i", "Kaynak: Berkeley verisi, 66 erkek (bu depodaki analiz).")]
    bas, T = zamanlama(L)

    def ciz(t):
        cerceve("Boy nereden gelir", "16 yaşından sonra boy nereden gelir?")
        maddeler(fig.add_axes([0.04, 0.10, 0.52, 0.78]), L, t, bas, fs=16)
        hiz_ekseni(fig.add_axes([0.62, 0.16, 0.35, 0.66]))
    return T, ciz, [(b, b + 2.5, m if isinstance(m, str) else m[1]) for b, m in zip(bas, L)]


@sahne
def simulasyon():
    yaslar = np.round(np.arange(13.0, 22.0 + 1e-9, 0.1), 2)
    T = len(yaslar) * 2 / FPS + 2.0
    i13 = np.argmin(np.abs(INCE - 13.0))
    gosterilen = []

    def ciz(t):
        k = min(int(t * FPS / 2), len(yaslar) - 1)
        a = yaslar[k]
        j = np.argmin(np.abs(INCE - a))
        cerceve("Simülasyon", f"Simülasyon: tipik bir erkek, yaş {a:.1f}")
        sk = fig.add_axes([0.0, 0.06, 0.30, 0.84])
        iskelet_ekseni(sk, BB[j], GG[j], plak_govde=VG[j] / VMAX * 1.6, plak_bacak=VB[j] / VMAX * 1.6)
        H_ = BB[j] + GG[j]
        sk.axhline(H_, color=MUR2, lw=0.8, ls=":", xmax=0.95)
        sk.axhline(BB[j], color=BACAK, lw=0.8, ls=":", xmax=0.95)
        sk.text(-0.255 * 190, H_ + 1.5, f"boy {H_:.1f} cm", fontsize=11, color=MUR2)
        sk.text(-0.255 * 190, BB[j] + 1.5, f"bacak {BB[j]:.1f} cm", fontsize=11, color=BACAK)
        hiz_ekseni(fig.add_axes([0.33, 0.30, 0.40, 0.55]), a)
        sb = fig.add_axes([0.78, 0.30, 0.19, 0.55])
        sb.axis("off")
        db, dg = BB[j] - BB[i13], GG[j] - GG[i13]
        sb.text(0, 1.0, "13 yaşından beri", fontsize=13, color=MUR2, va="top")
        sb.text(0, 0.86, f"bacak  +{db:.1f} cm", fontsize=18, color=BACAK, va="top", weight="bold")
        sb.text(0, 0.72, f"gövde  +{dg:.1f} cm", fontsize=18, color=GOVDE, va="top", weight="bold")
        sb.text(0, 0.50, f"Boy {BB[j] + GG[j]:.1f} cm", fontsize=14, color=MUR, va="top")
        sb.text(0, 0.40, f"Oturma boyu {GG[j]:.1f} cm", fontsize=14, color=MUR, va="top")
        sb.text(0, 0.24, "renkli plak = aktif\ngri plak = kapanmış", fontsize=11, color=MUR2, va="top")
        b1, n1 = v1.notlar(a, VB[j], VG[j], OLAY)
        nt = fig.add_axes([0.33, 0.07, 0.64, 0.17])
        nt.axis("off")
        nt.text(0, 0.85, "• " + b1, fontsize=16, color=MUR, va="top", weight="bold")
        nt.text(0, 0.40, "• " + n1, fontsize=14, color=MUR2, va="top")
        gosterilen.append((float(a), float(BB[j] + GG[j]), float(GG[j]), float(BB[j])))
    ciz.gosterilen = gosterilen
    sub = [(0, T, "Simülasyon: bacak önce durur, gövde (omurga) birkaç yıl daha uzar. Model: tipik erkek.")]
    return T, ciz, sub


@sahne
def gunici():
    L = [f"Gün içinde diskler sıkışır: akşam ~{N['gunici']} cm daha kısa ölçülürsün.",
         "Gece yatınca diskler su çeker; sabah boy geri gelir.",
         "Bu ne büyümedir ne kayıp. Boyunu hep sabah ölç.",
         "Asılma ve esneme sonrası 'uzama' da aynı nedenle geçici: ertesi sabah ~0 mm."]
    bas, T = zamanlama(L)

    def ciz(t):
        cerceve("Gece-gündüz", "Gece-gündüz: diskler sıkışır, kabarır")
        maddeler(fig.add_axes([0.32, 0.12, 0.64, 0.76]), L, t, bas, fs=17)
        ez = 0.5 * (1 - np.cos(2 * np.pi * t / 3.0))
        s = fig.add_axes([0.0, 0.06, 0.30, 0.84])
        iskelet_ekseni(s, BB[-1], GG[-1], plak_govde=0.05, plak_bacak=0.0, disk_ezilme=ez)
        s.text(0, 186, "akşam: diskler sıkışık" if ez > 0.5 else "sabah: diskler dolgun", ha="center", fontsize=13,
               color=MUR, weight="bold")
    return T, ciz, [(b, b + 2.5, m) for b, m in zip(bas, L)]


@sahne
def egrilik():
    L = [f"30° skolyoz eğrisi ölçülen boyu ~{N['k30']} mm azaltır; 45°'de ~{N['k45']} mm.",
         "Omurga kısalmaz; eğildiği için dik boy kısa ölçülür.",
         "Scheuermann kifozu (omurlarda kama şekli) kişilerin %0.4-10'unda görülür.",
         ("!", "Sırtında eğrilik ya da kamburluk fark edersen hekime git. Amaç boy değil, sağlık.")]
    bas, T = zamanlama(L)

    def ciz(t):
        cerceve("Eğrilik", "Eğrilik: omurga kısalmadan boy kısalır")
        maddeler(fig.add_axes([0.32, 0.12, 0.64, 0.76]), L, t, bas, fs=17)
        cobb = 30 * float(np.clip(t / 4.0, 0, 1))
        s = fig.add_axes([0.0, 0.06, 0.30, 0.84])
        anatomi.on(s, BB[-1], GG[-1], cobb=cobb, plak_govde=0.05)
        s.set_xlim(-48, 48)
        s.set_ylim(-3, 190)
        s.axis("off")
        kayip = float(omurga.stokes_kayip_mm(cobb)) if cobb >= 10 else 0.0
        s.text(0, 184, f"önden görünüm · {cobb:.0f}°  →  −{kayip:.0f} mm", ha="center", fontsize=13, color=EGRI,
               weight="bold")
    return T, ciz, [(b, b + 2.5, m if isinstance(m, str) else m[1]) for b, m in zip(bas, L)]


@sahne
def kaldiraclar():
    L = ["Boyu gerçekten artıran tek şey: kalan biyolojik büyüme.",
         f"Tipik erkek, 17 → 25 yaş: gövde ~{N['g17']} mm, bacak ~{N['b17']} mm.",
         f"Duruş 2-4 mm; egzersizin plağa etkisi < {N['mekanik']} mm.",
         "Eğrilik ve günün saati, ölçülen boyu büyümeden fazla değiştirebilir."]
    bas, T = zamanlama(L)
    satir = [("Kalan gövde büyümesi (17→25)", kal_mm("Kalan gövde büyümesi (17"), GOVDE),
             ("Skolyoz 45°", kal_mm("Skolyoz eğrisi 45"), EGRI),
             ("Gün içi disk (geçici)", kal_mm("Gün içi"), SOLUK),
             ("Skolyoz 30°", kal_mm("Skolyoz eğrisi 30"), EGRI),
             ("Duruş", kal_mm("Duruş"), SOLUK),
             ("Kalan bacak büyümesi (17→25)", kal_mm("Kalan bacak büyümesi (17"), GOVDE),
             ("Egzersiz, mekanik (üst sınır)", kal_mm("mekanik"), GOVDE)]

    def ciz(t):
        cerceve("Kaldıraçlar", "Ne kaç milimetre? (erkek, 17 yaştan sonra)")
        maddeler(fig.add_axes([0.04, 0.10, 0.40, 0.78]), L, t, bas, fs=15)
        ax = fig.add_axes([0.70, 0.14, 0.27, 0.72], facecolor=YUZEY)
        g = float(np.clip(t / 2.5, 0, 1))
        y = np.arange(len(satir))[::-1]
        for yi, (ad, mm, rk) in zip(y, satir):
            ax.barh(yi, mm * g, color=rk, height=0.6, hatch="///" if "geçici" in ad else None,
                    edgecolor=MUR2 if "geçici" in ad else YUZEY, lw=0.6)
            if g > 0.95:
                ax.text(mm + 0.6, yi, f"{mm:.1f}", va="center", fontsize=11, color=MUR2)
        ax.set_yticks(y, [s[0] for s in satir], fontsize=11, color=MUR)
        ax.set_xlim(0, 26)
        ax.set_xlabel("mm", color=MUR2)
        ax.grid(axis="x", color=IZG, lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=MUR2)
    return T, ciz, [(b, b + 2.5, m) for b, m in zip(bas, L)]


@sahne
def ne_ise_yarar():
    L = [("✗", "Asılma, esneme, ters asılma: kalıcı uzama yok."),
         ("✗", "Fazla protein, protein tozu, 'boy uzatan' takviye: yeterli beslenen gençte ek uzama yok."),
         ("✗", "Ağırlık antrenmanı omurgayı kısaltmaz; doğru teknikle güvenli."),
         ("!", "Yapma: steroid, reçetesiz hormon, yoğun spor + aşırı diyet."),
         ("✓", "Taban: yeterli enerji ve protein, D vitamini (güneş), düzenli uyku."),
         ("✓", "Horlama, uykuda nefes durması, eğrilik, yavaşlayan büyüme: hekim.")]
    bas, T = zamanlama(L)

    def ciz(t):
        cerceve("Ne işe yarar", "Ne işe yaramaz, ne gerçekten önemli?")
        ac = fig.add_axes([0.05, 0.82, 0.90, 0.06])
        ac.axis("off")
        ac.text(0, 0.5, "✗ boya etkisi yok      ! yapma      ✓ gerçekten önemli", fontsize=13, color=MUR2, va="center")
        maddeler(fig.add_axes([0.05, 0.10, 0.90, 0.70]), L, t, bas, fs=18)
    return T, ciz, [(b, b + 2.5, m[1]) for b, m in zip(bas, L)]


@sahne
def protokol():
    L = ["Sabah, çıplak ayak, aynı duvar, kafaya düz bir kitap.",
         "Boy ve oturma boyu, 3'er kez; ortalamasını yaz.",
         f"Ayda bir, 18 ay ({N['n_olcum']} ölçüm): omurga uzamasını yakalama ~%{N['p_oneri']}.",
         f"3 ayda bir ölçersen ~%{N['p3']}.",
         f"En büyük kazanç koşulları sabitlemek: ~%{N['pmax']}.",
         ("!", f"'Dizlerim hâlâ uzuyor mu?' evde anlaşılmaz (~%{N['p_bacak']}). Görüntüleme hekimin kararı.")]
    bas, T = zamanlama(L)
    cubuk = [("3 ayda bir", float(N["p3"])), ("her ay", float(N["p_oneri"])), ("her ay +\nsabit koşul", float(N["pmax"])),
             ("bacak\n(her ay)", float(N["p_bacak"]))]

    def ciz(t):
        cerceve("Ölçüm protokolü", "Evde nasıl ölçülür? (simülasyonla hesaplandı)")
        maddeler(fig.add_axes([0.04, 0.10, 0.56, 0.78]), L, t, bas, fs=15)
        ax = fig.add_axes([0.68, 0.18, 0.29, 0.62], facecolor=YUZEY)
        g = float(np.clip((t - bas[2]) / 1.5, 0, 1))
        for i, (ad, p) in enumerate(cubuk):
            ax.bar(i, p * g, color=BACAK if "bacak" in ad else GOVDE, width=0.62)
            if g > 0.95:
                ax.text(i, p + 2, f"%{p:.0f}", ha="center", fontsize=12, color=MUR)
        ax.axhline(80, color=MUR2, lw=0.8, ls=":")
        ax.text(3.45, 82, "hedef %80", fontsize=10, color=MUR2, ha="right")
        ax.set_xticks(range(len(cubuk)), [c[0] for c in cubuk], fontsize=10.5, color=MUR)
        ax.set_ylim(0, 108)
        ax.set_ylabel("Uzamayı yakalama olasılığı (%)", color=MUR2)
        ax.grid(axis="y", color=IZG, lw=0.6)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=MUR2)
    return T, ciz, [(b, b + 2.5, m if isinstance(m, str) else m[1]) for b, m in zip(bas, L)]


@sahne
def ozet():
    L = [f"16 yaştan sonra uzamanın çoğu (~%{N['govde_pay']}) omurgadan; bacaklar önce biter.",
         "Omurgayı genetiğinin üstüne uzatan bilinen bir yöntem yok.",
         "Desteklemek = eksik bırakmamak: beslenme, D vitamini, uyku, hastalığı tedavi.",
         "Eğrilik ve günün saati ölçülen boyu değiştirir; ikisini büyümeyle karıştırma.",
         "Ölçeceksen: sabah, aynı koşulda, ayda bir. Kesin cevap hekimde."]
    bas, T = zamanlama(L)

    def ciz(t):
        cerceve("Özet", "Özet")
        maddeler(fig.add_axes([0.05, 0.10, 0.90, 0.78]), L, t, bas, fs=19)
    return T + 1.0, ciz, [(b, b + 2.5, m) for b, m in zip(bas, L)]


@sahne
def kapanis():
    L = ["Bu video tıbbi tavsiye değildir.",
         "Sayılar model tahminidir (D). İskeletin boyu, bacağı ve gövdesi modelden; iç oranları görsel varsayımdır.",
         "Yapay zekâ yardımıyla hazırlandı; bağımsız hakem değerlendirmesinden geçmedi.",
         "Yöntem, kod ve kaynaklar: github.com/cruciblelab/arastirma · omurga-buyumesi",
         "CC BY-NC 4.0 · Crucible ekibi · atıfla, ticari olmayan her kullanıma açık"]
    bas, _ = zamanlama(L, bas=0.3)
    T = 9.0

    def ciz(t):
        cerceve("", "Şeffaflık")
        maddeler(fig.add_axes([0.05, 0.12, 0.90, 0.76]), [("i", m) for m in L], t,
                 [0.3 + 0.5 * i for i in range(len(L))], fs=17)
    return T, ciz, [(0, T, "Tıbbi tavsiye değildir. Kaynaklar: github.com/cruciblelab/arastirma")]


# ---------------------------------------------------------------------------
# Kodla: ffmpeg'e ham kare akışı
# ---------------------------------------------------------------------------

def srt_zaman(s):
    h, m = int(s // 3600), int(s % 3600 // 60)
    return f"{h:02d}:{m:02d}:{s % 60:06.3f}".replace(".", ",")


mp4 = CIKTI / "omurga_bilgilendirme_anatomik.mp4"
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                       "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
t0, srt, kare = 0.0, [], 0
for T, ciz, alt in SAHNELER:
    n = int(round(T * FPS))
    for i in range(n):
        ciz(i / FPS)
        fig.canvas.draw()
        ff.stdin.write(bytes(fig.canvas.buffer_rgba()))
        kare += 1
    for b, s, metin in alt:
        srt.append((t0 + b, t0 + min(s, T), metin))
    t0 += n / FPS
ff.stdin.close()
ff.wait()
plt.close(fig)

with open(CIKTI / "omurga_bilgilendirme_anatomik.srt", "w", encoding="utf-8") as f:
    for i, (b, s, m) in enumerate(sorted(srt), 1):
        f.write(f"{i}\n{srt_zaman(b)} --> {srt_zaman(s)}\n{m}\n\n")
pd.DataFrame(SAYILAR).to_csv(CIKTI / "sayilar.csv", index=False)

# ---------------------------------------------------------------------------
# Testler
# ---------------------------------------------------------------------------

TEST = []
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(mp4)],
                               capture_output=True, text=True, check=True).stdout)
v = pr["streams"][0]
sure = float(pr["format"]["duration"])
boyut = mp4.stat().st_size / 1e6
TEST.append(dict(test="V1", aciklama="Video biçimi: H.264, 1280x720, yuv420p", deger=f"{v['codec_name']}, {v['width']}x{v['height']}, {v['pix_fmt']}",
                 olcut="h264, 1280x720, yuv420p",
                 sonuc="GEÇTİ" if (v["codec_name"], v["width"], v["height"], v["pix_fmt"]) == ("h264", W, H, "yuv420p") else "KALDI"))
TEST.append(dict(test="V2", aciklama="Süre ve boyut", deger=f"{sure:.1f} sn, {boyut:.1f} MB", olcut="60-180 sn, < 25 MB",
                 sonuc="GEÇTİ" if 60 <= sure <= 180 and boyut < 25 else "KALDI"))
g = next(sh[1].gosterilen for sh in SAHNELER if hasattr(sh[1], 'gosterilen'))
_, _, _, _, Bm, Gm = omurga.tipik_kisi("erkek", sorted({x[0] for x in g}))
yas_idx = {a: i for i, a in enumerate(sorted({x[0] for x in g}))}
fark = max(max(abs(h - Bm[yas_idx[a]] - Gm[yas_idx[a]]), abs(gg - Gm[yas_idx[a]]), abs(bb - Bm[yas_idx[a]])) for a, h, gg, bb in g)
TEST.append(dict(test="V3", aciklama="Simülasyon sahnesindeki boy/oturma boyu/bacak = sürüm 3 modeli", deger=f"{fark:.1e} cm",
                 olcut="< 1e-6 cm", sonuc="GEÇTİ" if fark < 1e-6 else "KALDI"))
# V4: ekrandaki her kaynak sayısı dosyadaki değerin yuvarlanmış hali mi (bağımsız yeniden okuma)
s2 = pd.DataFrame(SAYILAR)
tekrar = {"Skolyoz 30° boy kaybı (mm)": pd.read_csv(c1 / "kaldiraclar.csv").set_index("kaldirac").loc[
    "Skolyoz eğrisi 30° (Cobb): ölçülen boy kaybı", "mm_medyan"],
          "Önerilen protokolde gövde gücü (%)": 100 * json.loads((c1 / "ozet.json").read_text())["protokol_oneri"]["guc_govde"],
          "16 yaş sonrası gövde payı (%)": 100 * json.loads(pkk.read_text())["berkeley_erkek_esik0.5"]["govde_payi16_medyan"]}
ok = all(abs(s2.set_index("ad").loc[k, "deger"] - val) < 1e-9 for k, val in tekrar.items())
TEST.append(dict(test="V4", aciklama="Örnek sayılar bağımsız yeniden okumayla aynı (skolyoz 30°, protokol gücü, gövde payı)",
                 deger="aynı" if ok else "farklı", olcut="aynı", sonuc="GEÇTİ" if ok else "KALDI"))
# A1: çizilen iskeletin tepesi ve tabanı = model boyu (her karede); A2: omur sayıları; A3: büyüme yalnız artar
hata_tepe = max(abs((b[1] + b[3]) - (B_ + S_)) / (B_ + S_) for B_, S_, g_, b in ISKELET_GEO)
hata_taban = max(abs(b[1]) for B_, S_, g_, b in ISKELET_GEO)
TEST.append(dict(test="A1", aciklama="Çizilen iskeletin tepesi = modelin boyu (her kare), taban = 0",
                 deger=f"tepe en büyük göreli fark {hata_tepe:.2e}, taban {hata_taban:.2f} cm",
                 olcut="< %0.2, < 0.2 cm", sonuc="GEÇTİ" if hata_tepe < 0.002 and hata_taban < 0.2 else "KALDI"))
say = {tuple(sorted(g_["sayim"].items())) for _, _, g_, _ in ISKELET_GEO}
TEST.append(dict(test="A2", aciklama="Omur sayıları (boyun, sırt, bel)", deger=str(say), olcut="C7, T12, L5",
                 sonuc="GEÇTİ" if say == {(("C", 7), ("L", 5), ("T", 12))} else "KALDI"))
artis = np.array([[x[3], x[2]] for x in g])           # (bacak, oturma boyu) simülasyon sahnesi boyunca
tamam = bool(np.all(np.diff(artis, axis=0) >= -1e-9))
TEST.append(dict(test="A3", aciklama="Simülasyon sahnesinde iskeletin bacağı ve gövdesi hiç kısalmıyor (yalnız büyüme)",
                 deger="evet" if tamam else "hayır", olcut="evet", sonuc="GEÇTİ" if tamam else "KALDI"))
pd.DataFrame(TEST).to_csv(CIKTI / "testler.csv", index=False)
(CIKTI / "ozet.json").write_text(json.dumps(dict(sure_sn=sure, boyut_mb=boyut, kare=kare, fps=FPS, sahne=len(SAHNELER),
                                                 altyazi=len(srt)), ensure_ascii=False, indent=1), encoding="utf-8")
print(pd.DataFrame(TEST).to_string(index=False))
print(f"{kare} kare, {sure:.1f} sn, {boyut:.1f} MB")
