"""
Notlu animasyon (PLAN 3.3). Şematik omurga + bacak (ölçekli değil), hız eğrileri ve uzama sütunları (model).
Sahne 1: yaş 13 → 22. Sahne 2: gece-gündüz disk değişimi. Sahne 3: 30° skolyozun ölçülen boya etkisi.
"""

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

import omurga

# Referans palet (dataviz): yüzey, mürekkep, kategorik 1-3
YUZEY, MUREKKEP, MUREKKEP2, SOLUK, IZGARA = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3", "#e4e3df"
BACAK, GOVDE, EGRI = "#2a78d6", "#1baf7a", "#eb6834"
DISK = "#e8d9b0"


def _karisim(renk, oran):
    """Plak rengi: oran = aktivite (0 kapalı → 1 en hızlı); kapalıda soluk gri."""
    a = np.array(matplotlib.colors.to_rgb(renk))
    g = np.array(matplotlib.colors.to_rgb(SOLUK))
    return tuple(g + (a - g) * float(np.clip(oran, 0, 1)))


def notlar(yas, vb, vg, olaylar):
    if yas < olaylar["tepe"] + 0.3:
        return ("Ergenlik atağı: bacak ve gövde birlikte hızla uzuyor.",
                "Bacak plakları (diz çevresi) ve omur plakları aynı anda aktif.")
    if yas < olaylar["bacak_bitis"]:
        return ("Bacak yavaşlıyor, gövde hâlâ hızlı.",
                "Önce bacaklar biter: diz plakları kapanmaya yaklaşıyor.")
    if yas < olaylar["govde_yavas"]:
        return ("Bacak büyümesi neredeyse bitti, omurga devam ediyor.",
                "Bu dönemde boy artışının çoğu gövdeden (omurga ve leğen) gelir.")
    if yas < olaylar["govde_bitis"]:
        return ("Gövde de yavaşlıyor: yılda 1 cm'den az.",
                "Berkeley'de erkeklerde bacak bittikten sonra gövde ≥ 3.4 cm uzadı (medyan).")
    return ("Büyüme bitti.",
            "Bundan sonra 'uzama' sanılanlar: duruş (2-4 mm) ve gün içi disk değişimi (14 mm, geçici).")


def ciz_omurga(ax, aktivite_g, aktivite_b, disk_ezilme=0.0, cobb=0.0):
    """Şematik omurga (24 omur) + leğen + bacak. disk_ezilme 0-1, cobb derece (yanal S eğrisi)."""
    ax.clear()
    ax.set_xlim(-3, 3)
    ax.set_ylim(-0.5, 25.5)
    ax.axis("off")
    n = 24
    omur_h, disk_h0 = 0.42, 0.16
    disk_h = disk_h0 * (1 - 0.45 * disk_ezilme)
    toplam = n * omur_h + (n - 1) * disk_h
    y0 = 9.0
    plak_renk = _karisim(GOVDE, aktivite_g)
    # yanal eğrilik: x(s) = A·sin(2πs) (S eğrisi), A Cobb'a orantılı (şematik)
    A = 0.75 * cobb / 30.0   # şematik genlik (30°'de 0.75 birim)
    y = y0
    for i in range(n):
        s = (i + 0.5) / n
        x = A * np.sin(2 * np.pi * s)
        w = 1.0 + 0.35 * (1 - i / n)
        ax.add_patch(FancyBboxPatch((x - w / 2, y), w, omur_h, boxstyle="round,pad=0,rounding_size=0.06",
                                    fc="#f4f1ea", ec=MUREKKEP2, lw=0.8))
        ax.add_patch(Rectangle((x - w / 2, y), w, 0.08, fc=plak_renk, ec="none"))
        ax.add_patch(Rectangle((x - w / 2, y + omur_h - 0.08), w, 0.08, fc=plak_renk, ec="none"))
        y += omur_h
        if i < n - 1:
            ax.add_patch(Rectangle((x - w * 0.42, y), w * 0.84, disk_h, fc=DISK, ec="none"))
            y += disk_h
    # kafa
    ax.add_patch(plt.Circle((0, y + 0.9), 0.85, fc="#f4f1ea", ec=MUREKKEP2, lw=0.8))
    # leğen
    ax.add_patch(FancyBboxPatch((-1.6, y0 - 1.2), 3.2, 1.1, boxstyle="round,pad=0,rounding_size=0.4",
                                fc="#f4f1ea", ec=MUREKKEP2, lw=0.8))
    # bacaklar: uyluk + diz plakları + kaval
    bplak = _karisim(BACAK, aktivite_b)
    for xs in (-0.75, 0.75):
        ax.add_patch(Rectangle((xs - 0.22, 4.3), 0.44, 3.4, fc="#f4f1ea", ec=MUREKKEP2, lw=0.8))
        ax.add_patch(Rectangle((xs - 0.24, 4.15), 0.48, 0.12, fc=bplak, ec="none"))
        ax.add_patch(Rectangle((xs - 0.24, 3.85), 0.48, 0.12, fc=bplak, ec="none"))
        ax.add_patch(Rectangle((xs - 0.2, 0.3), 0.4, 3.45, fc="#f4f1ea", ec=MUREKKEP2, lw=0.8))
    ax.text(-2.95, 4.0, "diz\nplakları", fontsize=7.5, color=MUREKKEP2, va="center")
    ax.text(-2.95, 13.5, "omur\nplakları", fontsize=7.5, color=MUREKKEP2, va="center")
    ax.text(2.0, 24.6, "renkli = aktif\ngri = kapanmış", fontsize=7, color=MUREKKEP2, va="top")
    ax.text(0, -0.45, "Şematik, ölçekli değil", fontsize=7, color=MUREKKEP2, ha="center", style="italic")
    return toplam


def uret(yol_mp4, yol_gif, cinsiyet="erkek", fps=10):
    yas = np.round(np.arange(13.0, 22.0 + 1e-9, 0.1), 2)
    ince = np.round(np.arange(11.0, 25.0 + 1e-9, 0.1), 2)   # 0.02 adımının katı (model kayıt yaşları yuvarlar)
    _, _, _, _, B, G = omurga.tipik_kisi(cinsiyet, ince)
    vb, vg = np.gradient(B, ince), np.gradient(G, ince)
    i13 = np.argmin(np.abs(ince - 13.0))
    vmax = max(vb.max(), vg.max())
    tepe = float(ince[np.argmax(vb + vg)])
    olaylar = dict(tepe=tepe,
                   bacak_bitis=float(ince[(ince > tepe) & (vb < 0.3)][0]),
                   govde_yavas=float(ince[(ince > tepe) & (vg < 1.0)][0]),
                   govde_bitis=float(ince[(ince > tepe) & (vg < 0.1)][0]))
    gosterilen = []

    fig = plt.figure(figsize=(12, 6.75), dpi=100, facecolor=YUZEY)
    ax_s = fig.add_axes([0.01, 0.17, 0.25, 0.80])
    ax_b = fig.add_axes([0.32, 0.30, 0.13, 0.58], facecolor=YUZEY)
    ax_v = fig.add_axes([0.53, 0.30, 0.44, 0.58], facecolor=YUZEY)
    ax_t = fig.add_axes([0.0, 0.0, 1.0, 0.17])
    ax_t.axis("off")

    def hiz_paneli(a):
        ax_v.clear()
        ax_v.set_facecolor(YUZEY)
        ax_v.plot(ince, vb, color=BACAK, lw=2)
        ax_v.plot(ince, vg, color=GOVDE, lw=2)
        ax_v.text(11.2, vb[np.argmin(np.abs(ince - 11.2))] + 0.25, "bacak", color=MUREKKEP2, fontsize=9)
        ax_v.text(19.2, vg[np.argmin(np.abs(ince - 19.2))] + 0.25, "gövde (oturma boyu)", color=MUREKKEP2, fontsize=9)
        j = np.argmin(np.abs(ince - a))
        ax_v.axvline(a, color=MUREKKEP2, lw=0.8, ls=":")
        ax_v.plot([a], [vb[j]], "o", color=BACAK, ms=8, mec=YUZEY, mew=2)
        ax_v.plot([a], [vg[j]], "o", color=GOVDE, ms=8, mec=YUZEY, mew=2)
        ax_v.set_xlim(11, 25)
        ax_v.set_ylim(-0.2, vmax * 1.12)
        ax_v.set_xlabel("Yaş", color=MUREKKEP2)
        ax_v.set_ylabel("Uzama hızı (cm/yıl)", color=MUREKKEP2)
        ax_v.set_title("Model: tipik erkek (sürüm 3, Türk uyarlamalı)", fontsize=10, color=MUREKKEP, loc="left")
        ax_v.grid(color=IZGARA, lw=0.6)
        for sp in ("top", "right"):
            ax_v.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax_v.spines[sp].set_color(SOLUK)
        ax_v.tick_params(colors=MUREKKEP2)
        return j

    def sutun_paneli(j):
        ax_b.clear()
        ax_b.set_facecolor(YUZEY)
        db, dg = B[j] - B[i13], G[j] - G[i13]
        ax_b.bar([0], [db], color=BACAK, width=0.6)
        ax_b.bar([0], [dg], bottom=[db], color=GOVDE, width=0.6)
        yb = max(db / 2, 1.2)
        yg = max(db + dg / 2, yb + 2.6)          # etiketler üst üste binmesin
        ax_b.text(0.38, yb, f"bacak\n+{db:.1f} cm", va="center", fontsize=9, color=MUREKKEP)
        ax_b.text(0.38, yg, f"gövde\n+{dg:.1f} cm", va="center", fontsize=9, color=MUREKKEP)
        ax_b.set_xlim(-0.5, 1.4)
        ax_b.set_ylim(0, (B[-1] - B[i13] + G[-1] - G[i13]) * 1.08)
        ax_b.set_title("13 yaşından beri\nuzama (model)", fontsize=10, color=MUREKKEP, loc="left")
        ax_b.set_xticks([])
        ax_b.tick_params(colors=MUREKKEP2)
        for sp in ("top", "right", "bottom"):
            ax_b.spines[sp].set_visible(False)
        ax_b.spines["left"].set_color(SOLUK)
        ax_b.set_ylabel("cm", color=MUREKKEP2)
        return db, dg

    def alt_yazi(baslik, not_, sayilar):
        ax_t.clear()
        ax_t.axis("off")
        ax_t.add_patch(Rectangle((0, 0), 1, 1, transform=ax_t.transAxes, fc="#f1efe8", ec="none"))
        ax_t.text(0.02, 0.70, baslik, fontsize=13, color=MUREKKEP, weight="bold", transform=ax_t.transAxes)
        ax_t.text(0.02, 0.38, not_, fontsize=10.5, color=MUREKKEP2, transform=ax_t.transAxes)
        ax_t.text(0.02, 0.10, sayilar, fontsize=9.5, color=MUREKKEP2, transform=ax_t.transAxes, family="monospace")
        ax_t.text(0.98, 0.10, "Tıbbi tavsiye değildir · Crucible / arastirma · CC BY-NC 4.0", fontsize=8,
                  color=MUREKKEP2, ha="right", transform=ax_t.transAxes)

    kareler = []
    for a in yas:
        kareler.append(("buyume", float(a)))
    for f in np.concatenate([np.linspace(0, 1, 12), np.linspace(1, 0, 12)]):
        kareler.append(("gunici", float(f)))
    for c in np.concatenate([np.linspace(0, 30, 14), np.full(10, 30.0)]):
        kareler.append(("egri", float(c)))

    from matplotlib.animation import FFMpegWriter
    yazici = FFMpegWriter(fps=fps, bitrate=1800)
    j_son = len(ince) - 1
    with yazici.saving(fig, str(yol_mp4), dpi=100):
        for tur, deger in kareler:
            if tur == "buyume":
                a = deger
                j = hiz_paneli(a)
                ciz_omurga(ax_s, vg[j] / vmax * 1.6, vb[j] / vmax * 1.6)
                db, dg = sutun_paneli(j)
                b1, n1 = notlar(a, vb[j], vg[j], olaylar)
                H = B[j] + G[j]
                gosterilen.append((a, float(H), float(G[j]), float(B[j])))
                alt_yazi(f"Yaş {a:.1f} · {b1}", n1,
                         f"Boy {H:6.1f} cm   Oturma boyu {G[j]:5.1f} cm   Bacak {B[j]:5.1f} cm   "
                         f"Hız: bacak {vb[j]:.2f}, gövde {vg[j]:.2f} cm/yıl")
            elif tur == "gunici":
                j = hiz_paneli(22.0)
                ciz_omurga(ax_s, vg[j] / vmax * 1.6, vb[j] / vmax * 1.6, disk_ezilme=deger)
                sutun_paneli(j)
                alt_yazi("Gece-gündüz: diskler gün içinde sıkışır, gece kabarır",
                         f"Sabahtan akşama ölçülen boy ≈ {omurga.GUNICI_MM * deger / 10:.2f} cm kısalır "
                         f"(en fazla {omurga.GUNICI_MM / 10:.2f} cm). Bu büyüme ya da kayıp değildir; ertesi sabah geri gelir.",
                         "Kaynak: spor ve boy araştırması sürüm 1 (gün içi farkı 14.4 mm). Ölçümü hep sabah yap.")
            else:
                j = hiz_paneli(22.0)
                ciz_omurga(ax_s, vg[j] / vmax * 1.6, vb[j] / vmax * 1.6, cobb=deger)
                sutun_paneli(j)
                kayip = float(omurga.stokes_kayip_mm(deger)) if deger >= 10 else 0.0
                alt_yazi(f"Eğrilik: {deger:.0f}° skolyoz eğrisi (Cobb açısı)",
                         f"Omurganın uzunluğu aynı kalır, ama dik ölçülen boy kısalır: ≈ {kayip:.1f} mm (Stokes 2008; 10°'nin altı gösterilmedi).",
                         "Eğrilik ve kambur duruş tanı/tedavi gerektirebilir: karar hekimin. Şekildeki eğrilik şematiktir.")
            yazici.grab_frame()
    plt.close(fig)
    return dict(kare=len(kareler), olaylar=olaylar, gosterilen=gosterilen, ince=ince, B=B, G=G)
