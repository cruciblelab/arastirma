"""
Parametrik anatomik iskelet (yan ve ön görünüm), matplotlib ile vektörel çizim.

Ölçülü kısım (model): boy H = bacak B + oturma boyu S. İskelet her yaşta bu üç değere göre ölçeklenir:
    zemin → iskial yumru = B (oturma yüzeyi), iskial yumru → kafa tepesi = S.
Görsel varsayım: iskelet içi oranlar (bkz. oranlar.md). Birimler cm; yan görünümde +x = ön (yüz sağa bakar).

Döndürülen geometri sözlüğü testlerde kullanılır (tepe, iskial seviye, omur sayıları, plak konumları).
"""

import numpy as np
import matplotlib
from matplotlib.patches import Circle, Ellipse, PathPatch, Polygon
from matplotlib.path import Path
from scipy.interpolate import splev, splprep

KEMIK, KEMIK_KENAR, KEMIK_GOLGE = "#efe8d8", "#6b6556", "#ddd3bd"
DISK_RENK = "#d9c48f"
SOLUK = "#c9c8c3"

# --- Görsel varsayımlar (oranlar.md) -------------------------------------------------------------
# Gövde (S) içi seviyeler, oturma yüzeyinden itibaren S'nin kesri
S1_UST, L1_UST, T1_UST, C1_UST = 0.17, 0.36, 0.66, 0.79
# Bacak (B) içi seviyeler, zeminden itibaren B'nin kesri
DIZ, AYAK_BILEGI = 0.585, 0.085
KALCA_EKLEMI_S = 0.085            # kalça eklemi, iskial seviyenin üstünde (S'nin kesri)
# Omur göreli birim boyları (gövde + disk), üstten alta
SEVIYELER = ([("C", i, 1.00 + 0.02 * i) for i in range(1, 8)] +
             [("T", i, 1.22 + 0.035 * i) for i in range(1, 13)] +
             [("L", i, 1.95 + 0.07 * i) for i in range(1, 6)])
DISK_PAYI = {"C": 0.24, "T": 0.20, "L": 0.30}       # birim boyun disk payı
DERINLIK = {"C": 0.022, "T": 0.032, "L": 0.050}      # omur gövdesi ön-arka derinliği (S kesri), seviye içinde artar


def _renk(aktivite, tam):
    a = np.array(matplotlib.colors.to_rgb(tam))
    g = np.array(matplotlib.colors.to_rgb(SOLUK))
    return tuple(g + (a - g) * float(np.clip(aktivite, 0, 1)))


def _yumusak(noktalar, kapali=True, n=200):
    p = np.asarray(noktalar, float)
    if kapali:
        p = np.vstack([p, p[:1]])
    tck, _ = splprep([p[:, 0], p[:, 1]], s=0, per=1 if kapali else 0, k=3)
    x, y = splev(np.linspace(0, 1, n), tck)
    return np.column_stack([x, y])


def _sekil(ax, noktalar, fc=KEMIK, ec=KEMIK_KENAR, lw=0.9, z=2, alpha=1.0, kapali=True):
    xy = _yumusak(noktalar, kapali)
    if kapali:
        ax.add_patch(Polygon(xy, closed=True, fc=fc, ec=ec, lw=lw, zorder=z, alpha=alpha, joinstyle="round"))
    else:
        ax.plot(xy[:, 0], xy[:, 1], color=ec, lw=lw, zorder=z, alpha=alpha, solid_capstyle="round")
    return xy


def _cubuk(ax, p0, p1, w0, w1, fc=KEMIK, ec=KEMIK_KENAR, z=2, alpha=1.0, egrilik=0.0):
    """İki uç arasında hafif eğri, uçlara doğru genişleyen uzun kemik gövdesi."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    t = np.linspace(0, 1, 30)
    d = p1 - p0
    nrm = np.array([-d[1], d[0]]) / np.linalg.norm(d)
    merkez = p0[None, :] + t[:, None] * d[None, :] + (egrilik * np.sin(np.pi * t))[:, None] * nrm[None, :]
    w = w0 + (w1 - w0) * t
    w = w * (1 + 0.25 * (np.abs(t - 0.5) * 2) ** 3)          # uçlarda (metafiz) genişleme
    sol = merkez + (w / 2)[:, None] * nrm[None, :]
    sag = merkez - (w / 2)[:, None] * nrm[None, :]
    ax.add_patch(Polygon(np.vstack([sol, sag[::-1]]), closed=True, fc=fc, ec=ec, lw=0.9, zorder=z, alpha=alpha,
                         joinstyle="round"))
    return merkez


def _plak_cizgisi(ax, merkez, yon, genislik, renk, z=5, kalinlik=2.6):
    yon = np.asarray(yon, float) / np.linalg.norm(yon)
    a, b = np.asarray(merkez) - yon * genislik / 2, np.asarray(merkez) + yon * genislik / 2
    ax.plot([a[0], b[0]], [a[1], b[1]], color=renk, lw=kalinlik, zorder=z, solid_capstyle="round")


# -------------------------------------------------------------------------------------------------
# Yan görünüm
# -------------------------------------------------------------------------------------------------

def omurga_ekseni(B, S, x_sakrum):
    """Yan görünüm omurga orta hattı x(y): bel lordozu, sırt kifozu, boyun lordozu (görsel varsayım)."""
    def x(y):
        u = (np.asarray(y) - B) / S
        return (x_sakrum + 0.010 * S * (u - S1_UST) / (C1_UST - S1_UST)
                + 0.040 * S * np.exp(-((u - 0.26) / 0.07) ** 2)      # bel lordozu (öne)
                - 0.050 * S * np.exp(-((u - 0.52) / 0.10) ** 2)      # sırt kifozu (arkaya)
                + 0.030 * S * np.exp(-((u - 0.73) / 0.04) ** 2))     # boyun lordozu (öne)
    return x


def yan(ax, B, S, plak_govde=0.0, plak_bacak=0.0, disk_ezilme=0.0, kollar=True, etiket=False, etiket_fs=9):
    """Yan görünüm iskelet. plak_*: 0 (kapalı) - 1 (en aktif). Döndürür: geometri sözlüğü."""
    H = B + S
    geo = dict(H=H, B=B, S=S, sayim={"C": 0, "T": 0, "L": 0}, plaklar={})
    gr, br = _renk(plak_govde, "#1baf7a"), _renk(plak_bacak, "#2a78d6")
    y_kalca = B + KALCA_EKLEMI_S * S
    x_kalca = 0.0
    x_sak = -0.055 * S
    eks = omurga_ekseni(B, S, x_sak)

    # --- Bacak (uzak bacak soluk, yakın bacak önde) ---
    for ofs, alpha, z in ((0.012 * S, 0.45, 1), (0.0, 1.0, 3)):
        y_diz, y_bilek = DIZ * B, AYAK_BILEGI * B
        x_diz, x_bilek = 0.010 * S + ofs, -0.005 * S + ofs
        # uyluk kemiği (femur): baş + boyun + gövde + kondiller
        bas = (x_kalca + ofs, y_kalca)
        trokanter = (x_kalca - 0.045 * S + ofs, y_kalca - 0.012 * S)
        _cubuk(ax, (x_kalca - 0.02 * S + ofs, y_kalca - 0.03 * S), (x_diz - 0.004 * S, y_diz + 0.055 * B),
               0.030 * S, 0.034 * S, z=z, alpha=alpha, egrilik=0.012 * S)
        _sekil(ax, [(bas[0] - 0.01 * S, bas[1] - 0.018 * S), trokanter, (trokanter[0] + 0.004 * S, trokanter[1] + 0.022 * S),
                    (bas[0] + 0.012 * S, bas[1] + 0.012 * S), (bas[0] + 0.024 * S, bas[1] - 0.004 * S),
                    (bas[0] + 0.005 * S, bas[1] - 0.04 * S), (bas[0] - 0.03 * S, bas[1] - 0.045 * S)], z=z, alpha=alpha)
        ax.add_patch(Circle(bas, 0.024 * S, fc=KEMIK, ec=KEMIK_KENAR, lw=0.9, zorder=z + 0.1, alpha=alpha))
        kond = [(x_diz - 0.045 * S, y_diz + 0.045 * B), (x_diz + 0.035 * S, y_diz + 0.05 * B),
                (x_diz + 0.045 * S, y_diz + 0.012 * B), (x_diz + 0.02 * S, y_diz + 0.002 * B),
                (x_diz - 0.035 * S, y_diz + 0.004 * B), (x_diz - 0.055 * S, y_diz + 0.02 * B)]
        _sekil(ax, kond, z=z + 0.1, alpha=alpha)
        # kaval kemiği (tibia) + kamış kemiği (fibula)
        _cubuk(ax, (x_diz - 0.035 * S, y_diz - 0.02 * B), (x_bilek - 0.03 * S, y_bilek + 0.02 * B),
               0.014 * S, 0.012 * S, z=z - 0.2, alpha=alpha * 0.9)
        _cubuk(ax, (x_diz, y_diz - 0.035 * B), (x_bilek, y_bilek + 0.03 * B), 0.030 * S, 0.026 * S, z=z, alpha=alpha,
               egrilik=-0.004 * S)
        _sekil(ax, [(x_diz - 0.045 * S, y_diz - 0.004 * B), (x_diz + 0.04 * S, y_diz - 0.002 * B),
                    (x_diz + 0.046 * S, y_diz - 0.03 * B), (x_diz + 0.024 * S, y_diz - 0.07 * B),   # tibial çıkıntı
                    (x_diz - 0.02 * S, y_diz - 0.07 * B), (x_diz - 0.05 * S, y_diz - 0.03 * B)], z=z + 0.1, alpha=alpha)
        # diz kapağı
        ax.add_patch(Ellipse((x_diz + 0.058 * S, y_diz + 0.012 * B), 0.022 * S, 0.042 * S, angle=-8, fc=KEMIK,
                             ec=KEMIK_KENAR, lw=0.9, zorder=z + 0.2, alpha=alpha))
        # ayak: talus, kalkaneus, metatarslar
        _sekil(ax, [(x_bilek - 0.03 * S, y_bilek + 0.01 * B), (x_bilek + 0.03 * S, y_bilek + 0.012 * B),
                    (x_bilek + 0.16 * S, 0.012 * B), (x_bilek + 0.20 * S, 0.002 * B), (x_bilek + 0.10 * S, 0.0),
                    (x_bilek - 0.03 * S, 0.0), (x_bilek - 0.075 * S, 0.012 * B), (x_bilek - 0.06 * S, y_bilek - 0.02 * B)],
               z=z, alpha=alpha)
        if alpha == 1.0:
            # büyüme plakları: femur alt ucu, tibia üst ucu, tibia alt ucu
            y_fp, y_tp, y_ta = y_diz + 0.042 * B, y_diz - 0.028 * B, y_bilek + 0.04 * B
            _plak_cizgisi(ax, (x_diz - 0.004 * S, y_fp), (1, 0.05), 0.085 * S, br, z=z + 0.3)
            _plak_cizgisi(ax, (x_diz - 0.002 * S, y_tp), (1, -0.03), 0.08 * S, br, z=z + 0.3)
            _plak_cizgisi(ax, (x_bilek, y_ta), (1, 0), 0.032 * S, br, z=z + 0.3, kalinlik=2.0)
            geo["plaklar"].update(femur_alt=y_fp, tibia_ust=y_tp, tibia_alt=y_ta, diz=y_diz)

    # --- Leğen (yan görünüm) ve sakrum ---
    _sekil(ax, [(x_kalca - 0.105 * S, B + 0.215 * S), (x_kalca - 0.02 * S, B + 0.235 * S),
                (x_kalca + 0.075 * S, B + 0.185 * S), (x_kalca + 0.06 * S, B + 0.125 * S),     # ön üst diken
                (x_kalca + 0.035 * S, B + 0.09 * S), (x_kalca + 0.075 * S, B + 0.045 * S),     # pubis
                (x_kalca + 0.03 * S, B + 0.02 * S), (x_kalca - 0.035 * S, B - 0.002 * S),     # iskial yumru
                (x_kalca - 0.06 * S, B + 0.05 * S), (x_kalca - 0.095 * S, B + 0.13 * S)], fc=KEMIK_GOLGE, z=1.5)
    ax.add_patch(Circle((x_kalca, y_kalca), 0.03 * S, fc="none", ec=KEMIK_KENAR, lw=0.8, zorder=1.6))
    ax.add_patch(Circle((x_kalca + 0.02 * S, B + 0.06 * S), 0.012 * S, fc=KEMIK, ec=KEMIK_KENAR, lw=0.6, zorder=1.6))
    y_s1 = B + S1_UST * S
    _sekil(ax, [(eks(y_s1) - 0.03 * S, y_s1 + 0.005 * S), (eks(y_s1) + 0.025 * S, y_s1),
                (eks(y_s1) - 0.03 * S, B + 0.06 * S), (eks(y_s1) - 0.06 * S, B + 0.035 * S),
                (eks(y_s1) - 0.055 * S, B + 0.10 * S)], z=2.2)
    geo["iskial"] = B - 0.002 * S

    # göğüs kafesi hacmi (soluk dolgu, kaburgaların arkasında)
    _sekil(ax, [(eks(B + 0.64 * S) - 0.02 * S, B + 0.645 * S), (x_kalca + 0.13 * S, B + 0.64 * S),
                (x_kalca + 0.19 * S, B + 0.55 * S), (x_kalca + 0.18 * S, B + 0.42 * S),
                (x_kalca + 0.10 * S, B + 0.36 * S), (eks(B + 0.40 * S) - 0.05 * S, B + 0.40 * S),
                (eks(B + 0.52 * S) - 0.075 * S, B + 0.52 * S)], fc="#f4efe4", ec="none", z=1.2)
    # --- Omurga: C1 üstten L5 alta ---
    y_ust, y_alt = B + C1_UST * S, y_s1
    birim = np.array([u for _, _, u in SEVIYELER])
    sinir = y_ust - np.concatenate([[0], np.cumsum(birim)]) / birim.sum() * (y_ust - y_alt)
    for (bolge, i, u), ya, yb in zip(SEVIYELER, sinir[:-1], sinir[1:]):
        h_birim = ya - yb
        disk = h_birim * DISK_PAYI[bolge] * (1 - 0.35 * disk_ezilme)
        govde_h = h_birim * (1 - DISK_PAYI[bolge])
        y0 = yb + (h_birim - govde_h - disk)          # alttaki disk + gövde; disk gövdenin üstünde
        yc = y0 + govde_h / 2
        xc = eks(yc)
        egim = np.degrees(np.arctan2(eks(yc + 0.5) - eks(yc - 0.5), 1.0))
        der = DERINLIK[bolge] * S * (0.85 + 0.15 * i / (12 if bolge == "T" else 7 if bolge == "C" else 5))
        tr = matplotlib.transforms.Affine2D().rotate_deg_around(xc, yc, egim) + ax.transData
        govde = matplotlib.patches.FancyBboxPatch((xc - der / 2, y0), der, govde_h,
                                                  boxstyle=f"round,pad=0,rounding_size={min(der, govde_h) * 0.25}",
                                                  fc=KEMIK, ec=KEMIK_KENAR, lw=0.8, zorder=4, transform=tr)
        ax.add_patch(govde)
        for yy in (y0 + 0.0, y0 + govde_h):                       # sonlanma plakları
            ax.add_patch(matplotlib.patches.Rectangle((xc - der / 2, yy - 0.0012 * S), der, 0.0024 * S, fc=gr,
                                                      ec="none", zorder=4.5, transform=tr))
        if disk > 0:
            ax.add_patch(matplotlib.patches.Rectangle((xc - der * 0.46, y0 + govde_h), der * 0.92, disk, fc=DISK_RENK,
                                                      ec="none", zorder=3.8, transform=tr))
        # arka elemanlar: pedikül + diken çıkıntısı (bölgeye göre yön ve uzunluk)
        uz = {"C": 0.022, "T": 0.034, "L": 0.026}[bolge] * S * (1.6 if (bolge, i) == ("C", 7) else 1.0)
        aci = {"C": -10, "T": -38, "L": -5}[bolge]
        kok = np.array([xc - der / 2 - 0.004 * S, yc + 0.1 * govde_h])
        uc = kok + uz * np.array([-np.cos(np.radians(aci)), np.sin(np.radians(aci))])
        ax.add_patch(Polygon([kok + [0, govde_h * 0.35], kok - [0, govde_h * 0.35], uc - [0, 0.003 * S],
                              uc + [0, 0.003 * S]], closed=True, fc=KEMIK, ec=KEMIK_KENAR, lw=0.7, zorder=3.6, transform=tr))
        geo["sayim"][bolge] += 1
        if bolge == "T" and i <= 10:                               # kaburga: önce geriye, sonra aşağı-öne
            p0 = np.array([xc - der / 2, yc])
            p3 = np.array([x_kalca + (0.150 + 0.004 * i) * S, yc - (0.03 + 0.010 * i) * S])
            p1 = p0 + np.array([-0.06 * S, 0.01 * S])
            p2 = p3 + np.array([0.0, 0.07 * S])
            tt = np.linspace(0, 1, 40)[:, None]
            bez = (1 - tt) ** 3 * p0 + 3 * (1 - tt) ** 2 * tt * p1 + 3 * (1 - tt) * tt ** 2 * p2 + tt ** 3 * p3
            ax.plot(bez[:, 0], bez[:, 1], color=KEMIK_KENAR, lw=2.4, alpha=0.6, zorder=3.4, solid_capstyle="round")
            ax.plot(bez[:, 0], bez[:, 1], color=KEMIK, lw=1.3, zorder=3.45, solid_capstyle="round")
    geo["omur_ust"] = y_ust
    # göğüs kemiği
    ax.add_patch(Polygon([(x_kalca + 0.150 * S, B + 0.645 * S), (x_kalca + 0.170 * S, B + 0.645 * S),
                          (x_kalca + 0.188 * S, B + 0.47 * S), (x_kalca + 0.172 * S, B + 0.46 * S)],
                         closed=True, fc=KEMIK, ec=KEMIK_KENAR, lw=0.8, zorder=3.5))

    # --- Kafatası (yan) ---
    tepe = B + S
    xk = eks(y_ust) + 0.03 * S
    kr = 0.105 * S
    S_ = S
    S = S * 1.12                                                     # kafatası ölçeği (görsel)
    _sekil(ax, [(xk - 0.095 * S, tepe - 0.10 * S), (xk - 0.07 * S, tepe - 0.025 * S), (xk + 0.0, tepe),
                (xk + 0.075 * S, tepe - 0.03 * S), (xk + 0.10 * S, tepe - 0.085 * S),
                (xk + 0.105 * S, tepe - 0.12 * S),                                              # alın-göz
                (xk + 0.118 * S, tepe - 0.15 * S), (xk + 0.10 * S, tepe - 0.175 * S),           # burun-çene
                (xk + 0.085 * S, tepe - 0.205 * S), (xk + 0.035 * S, tepe - 0.215 * S),         # çene
                (xk + 0.005 * S, tepe - 0.17 * S), (xk - 0.035 * S, tepe - 0.155 * S),
                (xk - 0.085 * S, tepe - 0.14 * S)], z=4)
    ax.add_patch(Ellipse((xk + 0.07 * S, tepe - 0.105 * S), 0.035 * S, 0.03 * S, fc=KEMIK_GOLGE, ec=KEMIK_KENAR, lw=0.7,
                         zorder=4.2))                                                                        # göz çukuru
    ax.plot([xk + 0.005 * S, xk + 0.03 * S, xk + 0.085 * S], [tepe - 0.17 * S, tepe - 0.185 * S, tepe - 0.19 * S],
            color=KEMIK_KENAR, lw=0.7, zorder=4.2)                                                         # alt çene hattı
    ax.add_patch(Ellipse((xk - 0.01 * S, tepe - 0.13 * S), 0.016 * S, 0.02 * S, fc=KEMIK_GOLGE, ec=KEMIK_KENAR, lw=0.6,
                         zorder=4.2))                                                                        # kulak deliği
    S = S_
    geo["tepe"] = tepe
    _ = kr

    # --- Kol (soluk, gövdenin arkasında) ---
    if kollar:
        omuz = (eks(B + 0.62 * S) + 0.05 * S, B + 0.615 * S)
        dirsek = (omuz[0] - 0.015 * S, omuz[1] - 0.205 * H)
        bilek = (dirsek[0] + 0.035 * S, dirsek[1] - 0.15 * H)
        _cubuk(ax, omuz, dirsek, 0.026 * S, 0.028 * S, z=1.0, alpha=0.45)
        _cubuk(ax, dirsek, bilek, 0.020 * S, 0.022 * S, z=1.0, alpha=0.45)
        for k in range(4):                                       # el: avuç + parmaklar
            ax.plot([bilek[0] - 0.008 * S + k * 0.006 * S, bilek[0] - 0.006 * S + k * 0.008 * S],
                    [bilek[1] - 0.01 * S, bilek[1] - 0.075 * S - 0.006 * S * (k in (1, 2))],
                    color=KEMIK_KENAR, lw=1.6, alpha=0.45, zorder=1.0, solid_capstyle="round")
        ax.add_patch(Ellipse((omuz[0] - 0.045 * S, omuz[1] - 0.06 * S), 0.05 * S, 0.14 * S, angle=8, fc=KEMIK_GOLGE,
                             ec=KEMIK_KENAR, lw=0.6, zorder=1.1, alpha=0.5))                                    # kürek kemiği
        ax.plot([omuz[0], omuz[0] + 0.13 * S], [omuz[1] + 0.01 * S, omuz[1] + 0.02 * S], color=KEMIK_KENAR, lw=2.2,
                alpha=0.6, zorder=3.3, solid_capstyle="round")                                                # köprücük

    if etiket:
        etiketle(ax, B, S, eks, geo, fs=etiket_fs)
    ax.set_aspect("equal")
    return geo


def etiketle(ax, B, S, eks, geo, fs=9):
    H = B + S
    sag = 0.32 * S
    sol = -0.36 * S
    ok = dict(arrowstyle="-", color="#52514e", lw=0.6)

    def e(metin, xy, x_metin, y_metin, ha="left"):
        ax.annotate(metin, xy=xy, xytext=(x_metin, y_metin), fontsize=fs, color="#0b0b0b", ha=ha, va="center",
                    arrowprops=ok, zorder=10)
    e("Kafatası", (eks(B + 0.9 * S) + 0.05 * S, B + 0.95 * S), sag, B + 0.97 * S)
    e("Boyun omurları (C1-C7)", (eks(B + 0.72 * S), B + 0.72 * S), sol, B + 0.80 * S, "right")
    e("Sırt omurları (T1-T12)", (eks(B + 0.52 * S), B + 0.52 * S), sol, B + 0.60 * S, "right")
    e("Bel omurları (L1-L5)", (eks(B + 0.27 * S), B + 0.27 * S), sol, B + 0.36 * S, "right")
    e("Omur sonlanma plakları\n(omurganın büyüme bölgesi)", (eks(B + 0.30 * S) + 0.02 * S, B + 0.30 * S), sag, B + 0.42 * S)
    e("Diskler (gün içinde\nsıkışır, gece kabarır)", (eks(B + 0.22 * S) + 0.01 * S, B + 0.215 * S), sag, B + 0.26 * S)
    e("Kaburgalar", (0.10 * S, B + 0.52 * S), sag, B + 0.58 * S)
    e("Sakrum ve leğen", (-0.03 * S, B + 0.15 * S), sol, B + 0.14 * S, "right")
    e("Uyluk kemiği (femur)", (0.0, 0.80 * B), sag, 0.82 * B)
    e("Diz plakları (bacağın\nbüyüme bölgesi)", (0.03 * S, geo["plaklar"]["femur_alt"]), sag, 0.66 * B)
    e("Diz kapağı", (0.07 * S, DIZ * B + 0.012 * B), sag, 0.54 * B)
    e("Kaval ve kamış kemiği", (0.0, 0.35 * B), sag, 0.33 * B)
    e("Ayak", (0.08 * S, 0.02 * B), sag, 0.06 * B)


# -------------------------------------------------------------------------------------------------
# Ön görünüm (omurga ve gövde; skolyoz sahnesi için)
# -------------------------------------------------------------------------------------------------

def on(ax, B, S, cobb=0.0, plak_govde=0.0, plak_bacak=0.0):
    """Ön görünüm: kafatası, omurga (yanal S eğrisi = Cobb, şematik genlik), göğüs kafesi, leğen, bacaklar."""
    H = B + S
    gr, br = _renk(plak_govde, "#1baf7a"), _renk(plak_bacak, "#2a78d6")
    A = 0.045 * S * cobb / 30.0
    y_alt, y_ust = B + S1_UST * S, B + C1_UST * S

    def x(y):
        u = (y - y_alt) / (y_ust - y_alt)
        return A * np.sin(2 * np.pi * u)
    # bacaklar
    for s in (-1, 1):
        y_diz, y_bilek = DIZ * B, AYAK_BILEGI * B
        _cubuk(ax, (s * 0.09 * S, B + 0.07 * S), (s * 0.05 * S, y_diz + 0.04 * B), 0.03 * S, 0.034 * S)
        _cubuk(ax, (s * 0.05 * S, y_diz - 0.03 * B), (s * 0.055 * S, y_bilek + 0.03 * B), 0.028 * S, 0.024 * S)
        ax.add_patch(Ellipse((s * 0.05 * S, y_diz + 0.01 * B), 0.08 * S, 0.06 * B, fc=KEMIK, ec=KEMIK_KENAR, lw=0.8, zorder=2.5))
        _plak_cizgisi(ax, (s * 0.05 * S, y_diz + 0.042 * B), (1, 0), 0.075 * S, br)
        _plak_cizgisi(ax, (s * 0.05 * S, y_diz - 0.028 * B), (1, 0), 0.07 * S, br)
        _sekil(ax, [(s * 0.04 * S, y_bilek), (s * 0.075 * S, y_bilek), (s * 0.09 * S, 0.0), (s * 0.03 * S, 0.0)])
    # leğen (kelebek)
    _sekil(ax, [(-0.16 * S, B + 0.22 * S), (-0.05 * S, B + 0.17 * S), (0.05 * S, B + 0.17 * S), (0.16 * S, B + 0.22 * S),
                (0.14 * S, B + 0.10 * S), (0.05 * S, B + 0.0), (-0.05 * S, B + 0.0), (-0.14 * S, B + 0.10 * S)],
           fc="#e6dcc6", z=1.8)
    # göğüs kafesi
    for i in range(10):
        yy = B + (0.64 - 0.028 * i) * S
        g = (0.09 + 0.006 * i) * S
        ax.add_patch(matplotlib.patches.Arc((x(yy), yy - 0.02 * S), 2 * g, 0.09 * S, theta1=200, theta2=340,
                                            color=KEMIK_KENAR, lw=1.3, alpha=0.6, zorder=2))
    # omurga
    birim = np.array([u for _, _, u in SEVIYELER])
    sinir = y_ust - np.concatenate([[0], np.cumsum(birim)]) / birim.sum() * (y_ust - y_alt)
    for (bolge, i, u), ya, yb in zip(SEVIYELER, sinir[:-1], sinir[1:]):
        h = (ya - yb) * (1 - DISK_PAYI[bolge])
        w = {"C": 0.035, "T": 0.045, "L": 0.06}[bolge] * S
        yc = yb + (ya - yb) / 2
        aci = np.degrees(np.arctan2(x(yc + 0.5) - x(yc - 0.5), 1.0))
        tr = matplotlib.transforms.Affine2D().rotate_deg_around(x(yc), yc, -aci) + ax.transData
        ax.add_patch(matplotlib.patches.FancyBboxPatch((x(yc) - w / 2, yc - h / 2), w, h,
                                                       boxstyle=f"round,pad=0,rounding_size={h * 0.25}",
                                                       fc=KEMIK, ec=KEMIK_KENAR, lw=0.8, zorder=3, transform=tr))
        for yy in (yc - h / 2, yc + h / 2):
            ax.add_patch(matplotlib.patches.Rectangle((x(yc) - w / 2, yy - 0.0012 * S), w, 0.0024 * S, fc=gr, ec="none",
                                                      zorder=3.5, transform=tr))
    # sakrum + kafatası
    _sekil(ax, [(-0.04 * S, y_alt), (0.04 * S, y_alt), (0.0, B + 0.07 * S)], z=2.4)
    ax.add_patch(Ellipse((x(y_ust), B + 0.89 * S), 0.17 * S, 0.21 * S, fc=KEMIK, ec=KEMIK_KENAR, lw=0.9, zorder=3))
    for s in (-1, 1):
        ax.add_patch(Ellipse((x(y_ust) + s * 0.035 * S, B + 0.90 * S), 0.04 * S, 0.035 * S, fc=KEMIK_GOLGE,
                             ec=KEMIK_KENAR, lw=0.6, zorder=3.2))
    ax.set_aspect("equal")
    return dict(H=H, genlik=A)
