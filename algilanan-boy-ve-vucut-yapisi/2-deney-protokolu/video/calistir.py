"""
Deney protokolü videosu: uygulayıcılar için adım adım anlatım. Tek komut (önce ../simulasyon/calistir.py):

    python calistir.py

- Sayılar elle yazılmaz: ../simulasyon/ciktilar/ dosyalarından okunur; ekrandaki her sayı ciktilar/sayilar.csv'de
  kaynağıyla birlikte listelenir.
- Çıktılar: ciktilar/deney_protokolu.mp4 (1280x720, H.264), .srt altyazı, sayilar.csv, testler.csv.
"""

import json
import subprocess
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Ellipse, FancyBboxPatch, Polygon, Rectangle
from scipy.stats import norm

KOK = Path(__file__).resolve().parent
SIM = KOK.parent / "simulasyon" / "ciktilar"
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
FPS, W, H = 25, 1280, 720
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"], "font.size": 12})
YUZEY, MUR, MUR2, SOLUK, IZG, BANT = "#fcfcfb", "#0b0b0b", "#52514e", "#c9c8c3", "#e4e3df", "#f1efe8"
YESIL, MAVI, TURUNCU, ZAYIF, KALIPLI = "#1baf7a", "#2a78d6", "#eb6834", "#9fb7d9", "#7fc9a6"

# ---------------------------------------------------------------------------
# Sayılar (yalnız dosyalardan)
# ---------------------------------------------------------------------------
SAYILAR = []


def sayi(ad, deger, kaynak, bicim="{:.0f}"):
    SAYILAR.append(dict(ad=ad, deger=float(deger), gosterim=bicim.format(deger), kaynak=kaynak))
    return bicim.format(deger)


oz = json.loads((SIM / "ozet.json").read_text(encoding="utf-8"))
guc = pd.read_csv(SIM / "guc.csv")
OS = "algilanan-boy/2/simulasyon/ciktilar/ozet.json"
on = oz["oneri"]
N = dict(N=sayi("Önerilen fotoğraflanan kişi", on["N"], OS), R=sayi("Önerilen değerlendirici", on["R"], OS),
         K=sayi("Değerlendirici başına çift", on["K"], OS),
         g2=sayi("Güç, etki 2 cm (%)", 100 * on["guc"]["2.0"], OS), g1=sayi("Güç, etki 1 cm (%)", 100 * on["guc"]["1.0"], OS),
         fp=sayi("Yanlış alarm, doğru analiz (%)", 100 * oz["D2_yanlis_alarm"], OS),
         fpn=sayi("Yanlış alarm, naif analiz (%)", 100 * oz["D5_naif_yanlis_alarm"], OS))
a = guc[(guc.secim == "amacli") & (guc.R == on["R"]) & (guc.pse2_gercek == 2.0)].sort_values("N")
r_ = guc[(guc.secim == "rastgele") & (guc.R == on["R"]) & (guc.pse2_gercek == 2.0)].sort_values("N")

# ---------------------------------------------------------------------------
# Çizim yardımcıları
# ---------------------------------------------------------------------------
fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=YUZEY)
BOLUM = ["Soru", "Fikir", "Kimler", "Etik", "Ölçüm", "Çekim", "Görseller", "Değerlendirme", "Analiz", "Kaç kişi",
         "Özet"]


def cerceve(bolum, baslik):
    fig.clf()
    fig.set_facecolor(YUZEY)
    ust = fig.add_axes([0, 0.9, 1, 0.1])
    ust.axis("off")
    ust.text(0.035, 0.42, baslik, fontsize=22, weight="bold", color=MUR, va="center")
    if bolum in BOLUM:
        i = BOLUM.index(bolum)
        for j in range(len(BOLUM)):
            ust.add_patch(Rectangle((0.66 + j * 0.028, 0.36), 0.021, 0.12, transform=ust.transAxes,
                                    fc=YESIL if j <= i else IZG, ec="none"))
    alt = fig.add_axes([0, 0, 1, 0.055])
    alt.axis("off")
    alt.add_patch(Rectangle((0, 0), 1, 1, transform=alt.transAxes, fc=BANT, ec="none"))
    alt.text(0.035, 0.45, "Deney protokolü · Tıbbi ya da hukuki tavsiye değildir · Çizimler şematiktir",
             fontsize=9.5, color=MUR2, va="center")
    alt.text(0.965, 0.45, "Crucible · arastirma · CC BY-NC 4.0", fontsize=9.5, color=MUR2, va="center", ha="right")


def maddeler(ax, liste, t, bas, fs=17, isaret=None):
    ax.axis("off")
    bb = ax.get_position()
    gen_px, yuk_px = bb.width * W, bb.height * H
    pt = 100 / 72
    karakter = max(18, int(gen_px * 0.9 / (fs * 0.54 * pt)))
    satir_h, bosluk = fs * 1.30 * pt / yuk_px, fs * 0.85 * pt / yuk_px
    y = 0.95
    for i, (m, b) in enumerate(zip(liste, bas)):
        if t < b:
            break
        al = min(1.0, (t - b) / 0.4)
        sat = textwrap.wrap(m, karakter)
        isr = (isaret[i] if isaret else "•")
        ax.text(0.0, y, isr, fontsize=fs, color=YESIL if isr == "•" else TURUNCU, alpha=al, va="top",
                transform=ax.transAxes, weight="bold")
        ax.text(0.045, y, "\n".join(sat), fontsize=fs, color=MUR, alpha=al, va="top", transform=ax.transAxes,
                linespacing=1.3)
        y -= len(sat) * satir_h + bosluk


def zamanla(liste, basla=0.6):
    out, t = [], basla
    for m in liste:
        out.append(t)
        t += float(np.clip(len(m) / 17.0, 2.2, 4.2))
    return out, t + 1.8


def kisi(ax, x0, boy, omuz, renk, bulanik=True, alpha=1.0):
    r = 11.5
    ax.add_patch(Ellipse((x0, boy - r), 2 * r * 0.8, 2 * r, fc=renk, ec="none", alpha=alpha))
    if bulanik:
        ax.add_patch(Ellipse((x0, boy - r), 2 * r * 0.62, 2 * r * 0.7, fc="#d9d7d2", ec="none", alpha=alpha))
    b = boy - 2 * r
    ax.add_patch(FancyBboxPatch((x0 - omuz / 2, b - 62), omuz, 60, boxstyle="round,pad=0,rounding_size=8", fc=renk,
                                ec="none", alpha=alpha))
    k = omuz * 0.62
    ax.fill([x0 - omuz / 2 + 2, x0 + omuz / 2 - 2, x0 + k / 2, x0 - k / 2], [b - 55, b - 55, b - 82, b - 82],
            color=renk, lw=0, alpha=alpha)
    for s in (-1, 1):
        ax.fill([x0 + s * 2, x0 + s * k / 2, x0 + s * k / 2 * 0.75, x0 + s * 3], [b - 80, b - 80, 0, 0], color=renk,
                lw=0, alpha=alpha)
        ax.fill([x0 + s * omuz / 2 - s, x0 + s * omuz / 2 + s * 8, x0 + s * omuz / 2 + s * 4, x0 + s * omuz / 2 - s * 6],
                [b - 4, b - 70, b - 72, b - 8], color=renk, lw=0, alpha=alpha)


def sahne_ekseni():
    ax = fig.add_axes([0.56, 0.08, 0.41, 0.8])
    ax.set_xlim(-60, 140)
    ax.set_ylim(-25, 225)
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


# ---------------------------------------------------------------------------
# Sahneler: her biri (bolum, baslik, maddeler, ciz(t)) döndürür
# ---------------------------------------------------------------------------
SAHNE = []


def sahne(f):
    SAHNE.append(f)
    return f


@sahne
def giris():
    T = 6.0

    def ciz(t):
        cerceve("", "")
        ax = fig.add_axes([0.05, 0.15, 0.5, 0.7])
        ax.axis("off")
        ax.text(0, 0.75, "Kaslı vücut daha uzun\nmu görünür?", fontsize=34, weight="bold", color=MUR, va="top",
                linespacing=1.15)
        ax.text(0, 0.35, "Bir fotoğraf deneyi nasıl yapılır:\nuygulayıcılar için adım adım", fontsize=18, color=MUR2,
                va="top", alpha=min(1, t / 1.0))
        sx = sahne_ekseni()
        kisi(sx, 0, 176, 46, ZAYIF)
        kisi(sx, 80, 176, 54, KALIPLI)
        sx.axhline(0, color=MUR2, lw=1)
        sx.text(40, 205, "?", fontsize=40, ha="center", color=TURUNCU, alpha=min(1, max(0, t - 1.5)))
    return "", "", [], [], T, ciz


def madde_sahnesi(bolum, baslik, liste, sag=None, isaret=None, fs=17):
    bas, T = zamanla(liste)

    def ciz(t):
        cerceve(bolum, baslik)
        ax = fig.add_axes([0.04, 0.09, 0.5 if sag else 0.9, 0.78])
        maddeler(ax, liste, t, bas, fs=fs, isaret=isaret)
        if sag:
            sag(t, T)
    return bolum, baslik, liste, bas, T, ciz


@sahne
def soru():
    def sag(t, T):
        sx = sahne_ekseni()
        kisi(sx, 0, 176, 46, ZAYIF)
        kisi(sx, 80, 176, 54, KALIPLI)
        sx.axhline(0, color=MUR2, lw=1)
        if t > 3:
            sx.text(80, 196, "güç → büyük?", ha="center", fontsize=12, color=YESIL)
        if t > 6:
            sx.text(80, -18, "geniş → kısa?", ha="center", fontsize=12, color=TURUNCU)
    return madde_sahnesi("Soru", "Neden bir deney?", [
        "Aynı boyda kaslı ve zayıf iki kişiyi karşılaştıran bir çalışma bulunamadı.",
        "\"Güçlü görünen büyük görünür\" etkisi boyu 1-4 cm uzatıyor.",
        "Geometri ise tersine çekiyor: geniş vücut daha kısa görünüyor.",
        "Simülasyon net etkiyi ~1 cm buldu, ama yönü belirsiz. Cevap ancak ölçerek bulunur."], sag)


@sahne
def fikir():
    liste = ["Boyları ölçülmüş kişilerin fotoğrafları ikişer ikişer gösterilir.",
             "Tanımayan kişiler \"hangisi daha uzun?\" diye seçer.",
             "Gerçek fark bilindiği için cevapların kalıplının lehine kayıp kaymadığı ölçülür.",
             "Kayma, \"aynı boyda görünme\" noktası (PSE) olarak santimetreyle ifade edilir."]

    def sag(t, T):
        ax = fig.add_axes([0.6, 0.16, 0.36, 0.62])
        x = np.linspace(-8, 8, 200)
        ax.plot(x, norm.cdf(x / 3), color=SOLUK, lw=2.5, label="benzer yapı")
        k = min(1.0, max(0.0, (t - 6) / 3))
        pse = 2.0 * k
        ax.plot(x, norm.cdf((x + pse) / 3), color=YESIL, lw=2.5, label="kalıplı ↔ zayıf")
        ax.axhline(0.5, color=IZG, lw=1)
        if k > 0.05:
            ax.annotate("", (-pse, 0.5), (0, 0.5), arrowprops=dict(arrowstyle="->", color=TURUNCU, lw=2))
            ax.text(-pse / 2, 0.56, "PSE", ha="center", color=TURUNCU, fontsize=12)
        ax.set_xlabel("Gerçek boy farkı (cm)")
        ax.set_ylabel("\"Daha uzun\" seçilme olasılığı")
        ax.legend(frameon=False, fontsize=10, loc="upper left")
        ax.spines[["top", "right"]].set_visible(False)
    return madde_sahnesi("Fikir", "Deneyin fikri", liste, sag)


@sahne
def kimler():
    return madde_sahnesi("Kimler", "Kimler katılır?", [
        f"En az {N['N']} fotoğraflanan erkek: yarısı belirgin zayıf, yarısı belirgin kalıplı.",
        "Boyları birbirine yakın olsun (ör. 170-182 cm); çok farklı boylar bilgi vermez.",
        f"En az {N['R']} değerlendirici: fotoğraftakileri tanımayan, 16 yaş ve üstü.",
        f"Her değerlendirici {N['K']} çift görür; yaklaşık 6-8 dakika."])


@sahne
def etik():
    return madde_sahnesi("Etik", "Etik ve gizlilik", [
        "Herkesten yazılı onam; 18 yaş altında ayrıca veli onamı.",
        "İsteyen istediği an çekilir; verisi silinir.",
        "Yüzler bulanıklaştırılır, adlar yerine kod kullanılır.",
        "Fotoğraflar paylaşılmaz, internete yüklenmez; analiz bitince silinir.",
        "Kimseye bedeniyle ilgili kişisel sonuç söylenmez; yalnız toplu sonuç paylaşılır."])


@sahne
def olcum():
    return madde_sahnesi("Ölçüm", "Ölçüm", [
        "Boy: ayakkabısız, duvarda, başın üstüne dik kitap; 3 ölçümün ortalaması.",
        "Herkes aynı gün, aynı saat aralığında ölçülür; boy gün içinde 1-2 cm değişir.",
        "Kilo: hep aynı tartı.",
        "Omuz genişliği: fotoğraftan, cetvelle ölçeklenerek; dokunmadan."])


@sahne
def cekim():
    def sag(t, T):
        ax = fig.add_axes([0.53, 0.12, 0.45, 0.7])
        kisi(ax, 20, 176, 50, ZAYIF, bulanik=False)
        ax.add_patch(Rectangle((48, 0), 3, 100, fc="#e8c547", ec="none"))
        ax.plot([300, 300], [0, 100], color=MUR, lw=2)
        ax.add_patch(Polygon([(290, 100), (310, 100), (300, 112)], fc=MUR))
        ax.add_patch(Rectangle((292, 106), 16, 10, fc=MUR))
        if t > 2:
            ax.annotate("", (20, -14), (300, -14), arrowprops=dict(arrowstyle="<->", color=MUR2))
            ax.text(160, -32, "3 m", ha="center", fontsize=13, color=MUR2)
        if t > 4:
            ax.text(318, 55, "100 cm", fontsize=13, color=MUR2, va="center")
        ax.axhline(0, color=MUR2, lw=1)
        ax.set_xlim(-30, 380)
        ax.set_ylim(-45, 230)
        ax.set_aspect("equal")
        ax.axis("off")
    return madde_sahnesi("Çekim", "Fotoğraf çekimi", [
        "Tripod: kişiden 3 m uzakta, yerden 100 cm yükseklikte; her çekimde aynı yer.",
        "Düz arka plan: kapı, çizgi, eşya yok.",
        "Aynı tip düz tişört, koyu alt, ayakkabısız.",
        "Ayak hizasında 1 m'lik cetvel; ölçekleme için."], sag)


@sahne
def gorsel():
    def sag(t, T):
        sx = sahne_ekseni()
        kisi(sx, 0, 177, 46, ZAYIF)
        kisi(sx, 80, 175, 54, KALIPLI)
        sx.axhline(0, color=MUR2, lw=1.5)
        if t > 3:
            sx.text(40, -18, "aynı zemin çizgisi, aynı ölçek", ha="center", fontsize=12, color=MUR2)
    return madde_sahnesi("Görseller", "Görselleri hazırlama", [
        "Bütün fotoğraflar aynı piksel/cm oranına getirilir: gerçek fark görüntüde korunur.",
        "Yüzler bulanıklaştırılır.",
        "İki kişi yan yana, ayaklar aynı zemin çizgisinde.",
        "Hazır kod, her değerlendiriciye dengeli bir çift listesi üretir."], sag)


@sahne
def degerlendirme():
    liste = ["Yönerge aynen okunur: \"Hangisi daha uzun? İlk izleniminiz yeterli.\"",
             "Değerlendirici hipotezi bilmez; amaç sonra anlatılır.",
             "Görevden SONRA: yaş ve \"Bedenimden memnunum\" (1-7).",
             "Fotoğraftakilerden birini tanıyorsa oturum analiz dışı kalır."]

    def sag(t, T):
        sx = sahne_ekseni()
        i = int(t // 2.2) % 4
        rng = np.random.default_rng(i)
        b1, b2 = 172 + rng.integers(0, 8), 172 + rng.integers(0, 8)
        o1, o2 = (46, 54) if i % 2 == 0 else (54, 46)
        kisi(sx, 0, b1, o1, ZAYIF if o1 < 50 else KALIPLI)
        kisi(sx, 80, b2, o2, ZAYIF if o2 < 50 else KALIPLI)
        sx.axhline(0, color=MUR2, lw=1)
        sx.text(40, 205, "Hangisi daha uzun?", ha="center", fontsize=14, color=MUR)
        sec = 0 if (i % 3 == 0) else 80
        if (t % 2.2) > 1.2:
            sx.add_patch(Rectangle((sec - 32, -6), 64, 196, fc="none", ec=TURUNCU, lw=2.5))
    return madde_sahnesi("Değerlendirme", "Değerlendirme oturumu", liste, sag)


@sahne
def analiz():
    liste = ["Tekrar birimi fotoğraflanan kişidir; değerlendiricilerin cevapları bağımsız değildir.",
             "Aşama 1: her kişinin \"algılanan boy\" puanı. Aşama 2: bu puanın gerçek boy ve yapıyla ilişkisi.",
             f"Simülasyonda etki yokken yanlış analiz %{N['fpn']}, doğru analiz %{N['fp']} oranında \"var\" dedi.",
             "Hazır kod tek komutla analiz eder; karar kuralları önceden yazıldı."]

    def sag(t, T):
        ax = fig.add_axes([0.62, 0.2, 0.33, 0.55])
        k = min(1.0, max(0.0, (t - 8) / 2))
        ax.bar([0, 1], [float(N["fpn"]) * k, float(N["fp"]) * k], color=[TURUNCU, YESIL], width=0.6)
        ax.axhline(5, color=MUR2, lw=1, ls="--")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["yanlış analiz", "doğru analiz"])
        ax.set_ylabel("Etki yokken \"var\" deme (%)")
        ax.set_ylim(0, max(float(N["fpn"]) * 1.2, 15))
        ax.spines[["top", "right"]].set_visible(False)
    return madde_sahnesi("Analiz", "Analiz", liste, sag, fs=16)


@sahne
def kac_kisi():
    liste = [f"Önerilen: {N['N']} fotoğraflanan kişi, {N['R']} değerlendirici.",
             f"Gerçek etki 2 cm ise yakalama olasılığı %{N['g2']}; 1 cm ise %{N['g1']}.",
             "Gücü asıl belirleyen fotoğraflanan kişi sayısı.",
             "Yarı zayıf, yarı kalıplı seçmek, rastgele seçmekten çok daha güçlü."]

    def sag(t, T):
        ax = fig.add_axes([0.6, 0.18, 0.36, 0.6])
        k = min(1.0, max(0.0, (t - 1) / 3))
        ax.plot(a.N, a.guc * 100 * k, "-o", color=YESIL, lw=2.5, label="amaçlı seçim")
        ax.plot(r_.N, r_.guc * 100 * k, ":", color=SOLUK, lw=2.5, label="rastgele seçim")
        ax.axhline(80, color=TURUNCU, lw=1, ls="--")
        ax.set_ylim(0, 100)
        ax.set_xlabel("Fotoğraflanan kişi")
        ax.set_ylabel("Güç (%), etki 2 cm")
        ax.legend(frameon=False, fontsize=10, loc="lower right")
        ax.spines[["top", "right"]].set_visible(False)
    return madde_sahnesi("Kaç kişi", "Kaç kişi gerekiyor?", liste, sag)


@sahne
def ozet():
    return madde_sahnesi("Özet", "Özet", [
        "Ölç, standart çek, yüzleri bulanıklaştır, tanımayanlara sor, hazır kodla analiz et.",
        "Sonuç ne çıkarsa çıksın yayımlanır; yalnız toplu ve kimliksiz.",
        "Ayrıntılar, formlar ve şablonlar: deney protokolü PDF'i ve depodaki kod.",
        "Bu deney, \"kalıplı biri gerçekten daha uzun mu görünüyor?\" sorusuna ilk doğrudan cevabı verebilir."])


# ---------------------------------------------------------------------------
# Kayıt
# ---------------------------------------------------------------------------
SAHNELER = [f() for f in SAHNE]
toplam = sum(s[4] for s in SAHNELER)
mp4 = CIKTI / "deney_protokolu.mp4"
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
                       "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
SRT, t0, kare = [], 0.0, 0
for bolum, baslik, liste, bas, T, ciz in SAHNELER:
    n = int(round(T * FPS))
    for i in range(n):
        ciz(i / FPS)
        fig.canvas.draw()
        ff.stdin.write(np.asarray(fig.canvas.buffer_rgba()).tobytes())
        kare += 1
    for j, (m, b) in enumerate(zip(liste, bas)):
        son = bas[j + 1] if j + 1 < len(bas) else T
        SRT.append((t0 + b, t0 + son, m))
    t0 += T
ff.stdin.close()
ff.wait()


def zm(s):
    h, r = divmod(s, 3600)
    m, r = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(r):02d},{int((r % 1) * 1000):03d}"


with open(CIKTI / "deney_protokolu.srt", "w", encoding="utf-8") as f:
    for i, (a_, b_, m) in enumerate(SRT, 1):
        f.write(f"{i}\n{zm(a_)} --> {zm(b_)}\n{m}\n\n")
pd.DataFrame(SAYILAR).to_csv(CIKTI / "sayilar.csv", index=False)

# Testler
TEST = []
pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                     "stream=codec_name,width,height,pix_fmt:format=duration,size", "-of", "json", str(mp4)],
                    capture_output=True, text=True)
j = json.loads(pr.stdout)
s0 = j["streams"][0]
sure, boyut = float(j["format"]["duration"]), float(j["format"]["size"]) / 1e6
TEST.append(dict(test="V1", aciklama="Biçim: H.264, 1280x720, yuv420p", deger=f"{s0['codec_name']}, {s0['width']}x"
                 f"{s0['height']}, {s0['pix_fmt']}", olcut="h264, 1280x720, yuv420p",
                 sonuc="GEÇTİ" if (s0["codec_name"], s0["width"], s0["height"], s0["pix_fmt"]) ==
                 ("h264", 1280, 720, "yuv420p") else "KALDI"))
TEST.append(dict(test="V2", aciklama="Süre ve boyut", deger=f"{sure:.1f} sn, {boyut:.1f} MB", olcut="90-240 sn, < 25 MB",
                 sonuc="GEÇTİ" if 90 <= sure <= 240 and boyut < 25 else "KALDI"))
oz2 = json.loads((SIM / "ozet.json").read_text(encoding="utf-8"))
kontrol = {"Önerilen fotoğraflanan kişi": oz2["oneri"]["N"], "Önerilen değerlendirici": oz2["oneri"]["R"],
           "Güç, etki 2 cm (%)": 100 * oz2["oneri"]["guc"]["2.0"],
           "Yanlış alarm, doğru analiz (%)": 100 * oz2["D2_yanlis_alarm"]}
ok = all(abs(next(s["deger"] for s in SAYILAR if s["ad"] == k) - v) < 1e-9 for k, v in kontrol.items())
TEST.append(dict(test="V3", aciklama="Ekrandaki sayılar kaynak dosyadan bağımsız yeniden okumayla aynı",
                 deger="aynı" if ok else "farklı", olcut="aynı", sonuc="GEÇTİ" if ok else "KALDI"))
pd.DataFrame(TEST).to_csv(CIKTI / "testler.csv", index=False)
print(f"{kare} kare, {sure:.1f} sn, {boyut:.1f} MB")
print(pd.DataFrame(TEST)[["test", "deger", "sonuc"]].to_string(index=False))
