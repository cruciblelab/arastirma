"""
Parametrik anatomik iskelet (yan ve ön görünüm), matplotlib ile vektörel çizim.
Sürüm 4: göğüs kafesi, diz ve sakrum Gray's Anatomy (1918, kamu malı) referanslarıyla karşılaştırılarak düzeltildi.

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
KOL_KONTUR = "#a9a399"
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
                + 0.028 * S * np.exp(-((u - 0.26) / 0.085) ** 2)     # bel lordozu (öne; sürüm 4: daha yayvan)
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
        # femur kondili: önde dar (trochlea), arkada yuvarlak çıkıntı (referans: yan görünüm)
        kond = [(x_diz - 0.018 * S, y_diz + 0.075 * B), (x_diz + 0.020 * S, y_diz + 0.075 * B),
                (x_diz + 0.030 * S, y_diz + 0.030 * B), (x_diz + 0.022 * S, y_diz + 0.006 * B),
                (x_diz - 0.010 * S, y_diz + 0.002 * B), (x_diz - 0.040 * S, y_diz + 0.014 * B),
                (x_diz - 0.042 * S, y_diz + 0.038 * B)]
        _sekil(ax, kond, z=z + 0.1, alpha=alpha)
        # kaval kemiği (tibia) + kamış kemiği (fibula)
        _cubuk(ax, (x_diz - 0.035 * S, y_diz - 0.02 * B), (x_bilek - 0.03 * S, y_bilek + 0.02 * B),
               0.014 * S, 0.012 * S, z=z - 0.2, alpha=alpha * 0.9)
        _cubuk(ax, (x_diz, y_diz - 0.035 * B), (x_bilek, y_bilek + 0.03 * B), 0.030 * S, 0.026 * S, z=z, alpha=alpha,
               egrilik=-0.004 * S)
        # tibia başı: düz eklem yüzü (plato), aşağı doğru daralır, önde tüberozite (yuvarlatmasız çokgen)
        ax.add_patch(Polygon([(x_diz - 0.040 * S, y_diz - 0.003 * B), (x_diz + 0.030 * S, y_diz - 0.003 * B),
                              (x_diz + 0.032 * S, y_diz - 0.020 * B), (x_diz + 0.030 * S, y_diz - 0.045 * B),
                              (x_diz + 0.020 * S, y_diz - 0.075 * B), (x_diz - 0.012 * S, y_diz - 0.085 * B),
                              (x_diz - 0.032 * S, y_diz - 0.040 * B), (x_diz - 0.042 * S, y_diz - 0.015 * B)],
                             closed=True, fc=KEMIK, ec=KEMIK_KENAR, lw=0.9, zorder=z + 0.1, alpha=alpha, joinstyle="round"))
        # diz kapağı
        if z > 2:
            geo["diz_kapagi"] = (x_diz + 0.048 * S, y_diz + 0.030 * B)
        ax.add_patch(Ellipse((x_diz + 0.040 * S, y_diz + 0.030 * B), 0.020 * S, 0.040 * S, angle=-8, fc=KEMIK,
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
    xs1 = eks(y_s1)
    _sekil(ax, [(xs1 - 0.028 * S, y_s1 + 0.004 * S), (xs1 + 0.028 * S, y_s1 - 0.002 * S),        # S1 üst yüzü (promontoryum)
                (xs1 + 0.004 * S, B + 0.11 * S), (xs1 - 0.022 * S, B + 0.065 * S),             # ön iç bükey yüz
                (xs1 - 0.030 * S, B + 0.035 * S), (xs1 - 0.045 * S, B + 0.040 * S),            # kuyruk sokumu
                (xs1 - 0.060 * S, B + 0.080 * S), (xs1 - 0.058 * S, B + 0.125 * S)], z=2.2)
    geo["iskial"] = B - 0.002 * S

    # --- Omurga: C1 üstten L5 alta ---
    y_ust, y_alt = B + C1_UST * S, y_s1
    sirt, kose = {}, []
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
        # disk: bu gövdenin üst yüzünden bir üstteki gövdenin alt yüzüne (eğrilikte boşluk kalmasın); çizim döngüden sonra
        dn = matplotlib.transforms.Affine2D().rotate_deg_around(xc, yc, egim)
        kose.append(dict(k=dn.transform([(xc - der / 2, y0), (xc + der / 2, y0), (xc - der / 2, y0 + govde_h),
                                         (xc + der / 2, y0 + govde_h)]), disk=disk, bos=h_birim - govde_h - disk))
        # arka elemanlar: pedikül + diken çıkıntısı (bölgeye göre yön ve uzunluk)
        uz = {"C": 0.022, "T": 0.034, "L": 0.026}[bolge] * S * (1.6 if (bolge, i) == ("C", 7) else 1.0)
        aci = {"C": -10, "T": -38, "L": -5}[bolge]
        kok = np.array([xc - der / 2 + 0.003 * S, yc + 0.1 * govde_h])          # gövdenin altına girer: kopuk görünmez
        uc = kok + uz * np.array([-np.cos(np.radians(aci)), np.sin(np.radians(aci))])
        ax.add_patch(Polygon([kok + [0, govde_h * 0.35], kok - [0, govde_h * 0.35], uc - [0, 0.003 * S],
                              uc + [0, 0.003 * S]], closed=True, fc=KEMIK, ec=KEMIK_KENAR, lw=0.7, zorder=3.6, transform=tr))
        geo["sayim"][bolge] += 1
        if bolge == "T":
            sirt[i] = dict(xc=xc, yc=yc, der=der, ust=y0 + govde_h, alt=y0)
    for ust, alt in zip(kose[:-1], kose[1:]):
        if alt["disk"] <= 0:
            continue
        f = alt["disk"] / (alt["disk"] + alt["bos"])                     # ezilmede disk incelir, boşluk kalır
        a_sol, a_sag = alt["k"][2], alt["k"][3]
        u_sol, u_sag = a_sol + f * (ust["k"][0] - a_sol), a_sag + f * (ust["k"][1] - a_sag)
        ic = lambda p, q: (p + 0.04 * (q - p), q + 0.04 * (p - q))
        (a_sol, a_sag), (u_sol, u_sag) = ic(a_sol, a_sag), ic(u_sol, u_sag)
        ax.add_patch(Polygon([a_sol, a_sag, u_sag, u_sol], closed=True, fc=DISK_RENK, ec="none", zorder=3.8))
    geo["omur_ust"] = y_ust
    geo["gogus"] = gogus_kafesi(ax, sirt, S)

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

    # --- Kol (soluk, gövdenin arkasında; omuz göğüs kafesi fonksiyonundan) ---
    if kollar:
        omuz = geo["gogus"]["omuz"]
        dirsek = (omuz[0] - 0.01 * S, omuz[1] - 0.205 * H)
        bilek = (dirsek[0] + 0.035 * S, dirsek[1] - 0.15 * H)
        # kol yakın tarafta ama omurga ve kaburgalar görünsün diye yalnız kontur ("hayalet") olarak çizilir
        hk = dict(fc="none", ec=KOL_KONTUR, z=4.6)
        ax.add_patch(Circle(omuz, 0.022 * S, fc="none", ec=KOL_KONTUR, lw=0.8, zorder=4.6))
        _cubuk(ax, omuz, dirsek, 0.024 * S, 0.026 * S, **hk)
        _cubuk(ax, dirsek, bilek, 0.020 * S, 0.022 * S, **hk)
        for k in range(4):
            ax.plot([bilek[0] - 0.008 * S + k * 0.006 * S, bilek[0] - 0.006 * S + k * 0.008 * S],
                    [bilek[1] - 0.01 * S, bilek[1] - 0.075 * S - 0.006 * S * (k in (1, 2))],
                    color=KOL_KONTUR, lw=1.2, zorder=4.6, solid_capstyle="round")

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
    e("Omur sonlanma plakları\n(omurganın büyüme bölgesi)", (eks(B + 0.30 * S) + 0.02 * S, B + 0.30 * S), sag, B + 0.43 * S)
    e("Diskler (gün içinde\nsıkışır, gece kabarır)", (eks(B + 0.22 * S) + 0.01 * S, B + 0.215 * S), sag, B + 0.26 * S)
    g = geo["gogus"]
    e("Göğüs kemiği", g["st_orta"], sag, B + 0.73 * S)
    e("Kaburgalar (12 çift)", g["kaburga_orta"], sag, B + 0.63 * S)
    e("Kaburga kıkırdakları", g["kikirdak_orta"], sag, B + 0.53 * S)
    e("Sakrum ve leğen", (-0.03 * S, B + 0.15 * S), sol, B + 0.14 * S, "right")
    e("Uyluk kemiği (femur)", (0.0, 0.80 * B), sag, 0.82 * B)
    e("Diz plakları (bacağın\nbüyüme bölgesi)", (0.03 * S, geo["plaklar"]["femur_alt"]), sag, 0.66 * B)
    e("Diz kapağı", geo["diz_kapagi"], sag, 0.54 * B)
    e("Kaval ve kamış kemiği", (0.0, 0.35 * B), sag, 0.33 * B)
    e("Ayak", (0.08 * S, 0.02 * B), sag, 0.06 * B)


KIKIRDAK, KIKIRDAK_KENAR = "#dfe3df", "#8a918c"
GOGUS_BOSLUK = "#e2ddd6"                                                 # kemikten koyu: kaburga araları görünür


def _bant(ax, xy, w0, w1, fc=KEMIK, ec=KEMIK_KENAR, z=3.4, alpha=1.0, lw=0.7):
    """Bir eğri boyunca kalınlığı w0'dan w1'e değişen bant (kaburga, kıkırdak)."""
    xy = np.asarray(xy, float)
    d = np.gradient(xy, axis=0)
    n = np.column_stack([-d[:, 1], d[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    w = np.linspace(w0, w1, len(xy))[:, None] / 2
    ax.add_patch(Polygon(np.vstack([xy + w * n, (xy - w * n)[::-1]]), closed=True, fc=fc, ec=ec, lw=lw, zorder=z,
                         alpha=alpha, joinstyle="round"))


def _egri(noktalar, n=60, k=3):
    p = np.asarray(noktalar, float)
    tck, _ = splprep([p[:, 0], p[:, 1]], s=0, k=min(k, len(p) - 1))
    return np.column_stack(splev(np.linspace(0, 1, n), tck))


def _bezier(p0, c, p1, n=20):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * np.asarray(p0) + 2 * (1 - t) * t * np.asarray(c) + t ** 2 * np.asarray(p1)


# Kaburga ön (kemik) ucunun, kendi omurunun kaç sırt omuru aşağısında olduğu (yan görünüm; Gray's 1918 Fig. 966 ile
# karşılaştırılarak seçildi, görsel varsayım). 1. kaburga kısa ve dik, orta kaburgalar en çok iner, 11-12 kısa.
KABURGA_DUSUS = {1: 1.6, 2: 2.8, 3: 3.3, 4: 3.6, 5: 3.8, 6: 4.0, 7: 4.0, 8: 3.8, 9: 3.4, 10: 3.0, 11: 2.6, 12: 1.8}


def gogus_kafesi(ax, sirt, S):
    """Yan görünüm göğüs kafesi (referans: Gray's Anatomy 1918, Fig. 115 ve 966; kamu malı).

    Her kaburga yan izdüşümde: omurdan arkaya (kaburga açısı), sonra aşağı-öne uzun bir yay, ön kemik ucu kendi
    omurunun KABURGA_DUSUS[i] omur aşağısında. 1-7 kıkırdakla göğüs kemiğine yukarı kıvrılarak bağlanır (gerçek
    kaburga), 8-10 üstteki kıkırdağa (kaburga kavsi), 11-12 serbest (yüzen). Omurga konunun odağı olduğu için
    kaburgalar omurganın arkasında çizilir (çizim tercihi; gerçekte yakın taraf kaburgalar omurgayı örter).
    """
    T = {i: sirt[i] for i in range(1, 13)}
    u = (T[1]["yc"] - T[12]["yc"]) / 11                                  # bir sırt omuru seviyesi (cm)
    on_yuz = lambda i: T[i]["xc"] + T[i]["der"] / 2
    arka_yuz = lambda i: T[i]["xc"] - T[i]["der"] / 2
    seviye = lambda d: T[1]["yc"] - (d - 1) * u                          # d. sırt omurunun yüksekliği (kesirli)
    # göğüs kemiği: sap üstü T2-T3, sternal açı T4-T5, gövde altı T9, hançer çıkıntısı ~T10-T11
    y_sap, y_aci, y_govde_alt = T[2]["alt"], T[4]["alt"], T[9]["yc"]
    y_hancer = y_govde_alt - 0.035 * S
    x_sap, x_alt = on_yuz(2) + 0.080 * S, on_yuz(9) + 0.140 * S
    x_st = lambda y: x_sap + (x_alt - x_sap) * (y_sap - y) / (y_sap - y_govde_alt)
    y_eklem = {1: y_sap - 0.012 * S, 2: y_aci}
    for i in range(3, 8):
        y_eklem[i] = y_aci - (i - 2) / 5 * (y_aci - y_govde_alt)
    ucl, aci, kik = {}, {}, {}
    for i in range(1, 13):
        y_v = T[i]["yc"]
        boyun = (arka_yuz(i) - 0.012 * S, y_v - 0.002 * S)
        a = (arka_yuz(i) - (0.018 + 0.016 * np.sin(np.pi * i / 12)) * S, y_v - 0.012 * S)
        y_e = seviye(i + KABURGA_DUSUS[i])
        if i <= 7:
            x_e = x_st(y_e) - (0.015 if i == 1 else 0.028 + 0.002 * i) * S          # sternuma paralel hat
        elif i <= 10:
            x_e = x_st(y_govde_alt) - (0.030 + 0.022 * (i - 7)) * S
        else:
            x_e = on_yuz(i) + (0.055 if i == 11 else 0.025) * S
        e = (x_e, y_e)
        kiris = np.subtract(e, a)
        orta = (a[0] + 0.5 * kiris[0], a[1] + 0.5 * kiris[1] - (0.002 + 0.004 * np.sin(np.pi * i / 13)) * S)
        yol = _egri([boyun, a, orta, e], n=70)
        w = (0.009 + 0.006 * np.sin(np.pi * i / 13)) * S * (0.7 if i in (1, 12) else 1.0)
        _bant(ax, yol, w * 0.55, w, z=3.0 + 0.01 * i)
        ucl[i], aci[i] = e, a
        if i == 6:
            yol6 = yol
        if i <= 7:                                                       # kıkırdak: önce öne, sonra yukarı-öne
            hedef = (x_st(y_eklem[i]) - 0.004 * S, y_eklem[i])
            kontrol = (hedef[0] - 0.25 * (hedef[0] - x_e), y_e)
            kik[i] = _bezier(e, kontrol, hedef)
            _bant(ax, kik[i], w * 0.75, w * 0.6, fc=KIKIRDAK, ec=KIKIRDAK_KENAR, z=3.2, lw=0.6)
    for i in (8, 9, 10):                                                 # kaburga kavsi
        hedef = kik[i - 1][int(0.55 * len(kik[i - 1]))]
        kik[i] = _bezier(ucl[i], (hedef[0] - 0.2 * (hedef[0] - ucl[i][0]), ucl[i][1] + 0.3 * (hedef[1] - ucl[i][1])), hedef)
        _bant(ax, kik[i], 0.009 * S, 0.008 * S, fc=KIKIRDAK, ec=KIKIRDAK_KENAR, z=3.19 - 0.01 * i, lw=0.6)
    # göğüs kemiği: sap (geniş, kısa), gövde (uzun), hançer çıkıntısı (kıkırdak)
    k = 0.017 * S
    dorgen = lambda y0, y1, k0, k1: [(x_st(y0) - k0 / 2, y0), (x_st(y0) + k0 / 2, y0),
                                     (x_st(y1) + k1 / 2, y1), (x_st(y1) - k1 / 2, y1)]
    for parca in (dorgen(y_sap + 0.004 * S, y_aci + 0.002 * S, 1.35 * k, 1.05 * k),     # sap (manubrium)
                  dorgen(y_aci - 0.002 * S, y_govde_alt, 1.0 * k, 1.05 * k)):           # gövde
        ax.add_patch(Polygon(parca, closed=True, fc=KEMIK, ec=KEMIK_KENAR, lw=0.8, zorder=3.7, joinstyle="round"))
    ax.add_patch(Polygon([(x_st(y_govde_alt) - 0.35 * k, y_govde_alt - 0.002 * S),
                          (x_st(y_govde_alt) + 0.4 * k, y_govde_alt - 0.002 * S),
                          (x_st(y_govde_alt) + 0.006 * S, y_hancer)], closed=True, fc=KIKIRDAK, ec=KIKIRDAK_KENAR,
                         lw=0.7, zorder=3.7))
    # göğüs hacmi (soluk dolgu): arka açılar, alt kaburga uçları, kaburga kavsi, göğüs kemiği
    zarf = ([(x_sap - 0.4 * k, y_sap + 0.004 * S), (arka_yuz(1) - 0.01 * S, T[1]["ust"])] +
            [aci[i] for i in range(1, 13)] + [ucl[12], ucl[11], ucl[10]] +
            [tuple(p) for p in kik[10][::4]] + [tuple(p) for p in kik[9][-6::3]] + [tuple(p) for p in kik[8][-6::3]] +
            [tuple(p) for p in kik[7][::-4]] + [(x_st(y_govde_alt), y_govde_alt)])
    ax.add_patch(Polygon(zarf, closed=True, fc=GOGUS_BOSLUK, ec="none", zorder=1.2))     # kaburga araları seçilsin
    # kürek kemiği (arkada, kaburga 2-7 seviyesi; yandan dar görünür) ve köprücük (göğüs kemiği sapından omuza)
    omuz = (on_yuz(2) + 0.005 * S, T[2]["yc"])
    akromiyon = (omuz[0] + 0.004 * S, omuz[1] + 0.030 * S)
    kurek = [akromiyon, (aci[2][0] + 0.006 * S, T[1]["yc"]), (aci[4][0] - 0.004 * S, T[4]["yc"]),
             (aci[7][0] + 0.010 * S, T[7]["yc"] - 0.006 * S), (omuz[0] - 0.040 * S, T[4]["yc"]),
             (omuz[0] - 0.010 * S, omuz[1] - 0.012 * S)]
    _sekil(ax, kurek, fc=KEMIK_GOLGE, z=3.25, alpha=0.55)
    kopru = _egri([(x_sap - 0.3 * k, y_sap + 0.006 * S), ((x_sap + akromiyon[0]) / 2 + 0.006 * S, y_sap + 0.016 * S),
                   akromiyon], n=30, k=2)
    _bant(ax, kopru, 0.013 * S, 0.011 * S, z=3.75)
    return dict(kaburga=len(ucl), kikirdak_sternum=sum(1 for i in kik if i <= 7), kavis=sum(1 for i in kik if i > 7),
                omuz=omuz, sternum=(y_sap, y_hancer), uclar=ucl,
                st_orta=(x_st((y_aci + y_govde_alt) / 2) + 0.6 * k, (y_aci + y_govde_alt) / 2),
                kaburga_orta=tuple(yol6[len(yol6) * 2 // 3]), kikirdak_orta=tuple(kik[6][len(kik[6]) // 2]),
                seviye={i: T[i]["yc"] for i in T}, kopru_alt=float(kopru[:, 1].min()),
                dusus={i: (T[i]["yc"] - ucl[i][1]) / u for i in ucl})


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
