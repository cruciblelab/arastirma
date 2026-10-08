"""
Deney protokolü PDF'i. Tek komut (önce ../simulasyon/calistir.py çalışmış olmalı):

    python uret.py

Çıktı: ciktilar/deney_protokolu.pdf (A4). Sayılar elle yazılmaz: güç analizi ve öneri ../simulasyon/ciktilar/'dan okunur.
"""

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Ellipse, FancyBboxPatch, Polygon, Rectangle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

KOK = Path(__file__).resolve().parent
SIM = KOK.parent / "simulasyon" / "ciktilar"
CIKTI = KOK / "ciktilar"
SEKIL = CIKTI / "sekiller"
SEKIL.mkdir(parents=True, exist_ok=True)
FONT = "/usr/share/fonts/truetype/crosextra/Carlito-{}.ttf"
pdfmetrics.registerFont(TTFont("G", FONT.format("Regular")))
pdfmetrics.registerFont(TTFont("GB", FONT.format("Bold")))
pdfmetrics.registerFont(TTFont("GI", FONT.format("Italic")))
pdfmetrics.registerFontFamily("G", normal="G", bold="GB", italic="GI", boldItalic="GB")
MUR, MUR2, SOLUK, YESIL, MAVI, TURUNCU = "#0b0b0b", "#52514e", "#c9c8c3", "#1baf7a", "#2a78d6", "#eb6834"
plt.rcParams.update({"font.family": ["Inter", "DejaVu Sans"]})

oz = json.loads((SIM / "ozet.json").read_text(encoding="utf-8"))
guc = pd.read_csv(SIM / "guc.csv")
testler = pd.read_csv(SIM / "testler.csv")
on = oz["oneri"]
N_ON, R_ON, K = on["N"], on["R"], on["K"]
G2 = 100 * on["guc"]["2.0"]
G1 = 100 * on["guc"]["1.0"]
G3 = 100 * on["guc"]["3.0"]
FP = 100 * oz["D2_yanlis_alarm"]
FP_NAIF = 100 * oz["D5_naif_yanlis_alarm"]
# Pratik öneri (keşifsel; PLAN 7 sapma 2): τ = 2 cm'de de güç ≥ %80 olan en küçük N, R = 30
kt = pd.read_csv(SIM / "kesifsel_tau.csv")
_k2 = kt[(kt.pse2_gercek == 2.0) & (kt.guc_ya_da_yanlis_alarm >= 0.8)]
N_PR = int(_k2.N.min()) if len(_k2) else int(kt.N.max())
R_PR = int(kt.R.iloc[0])
_g = guc[(guc.secim == "amacli") & (guc.N == N_PR) & (guc.R == R_PR)].set_index("pse2_gercek").guc
PR1, PR2 = 100 * _g[1.0], 100 * _g[2.0]
PR2_TAU = 100 * float(kt[(kt.N == N_PR) & (kt.pse2_gercek == 2.0)].guc_ya_da_yanlis_alarm.iloc[0])
ON2_TAU = 100 * float(kt[(kt.N == N_ON) & (kt.pse2_gercek == 2.0)].guc_ya_da_yanlis_alarm.iloc[0])

# ---------------------------------------------------------------------------
# Şekiller
# ---------------------------------------------------------------------------


def kisi(ax, x0, boy, omuz, renk, yuz_bulanik=True):
    r = 11.5
    ax.add_patch(Ellipse((x0, boy - r), 2 * r * 0.8, 2 * r, fc=renk, ec="none"))
    if yuz_bulanik:
        ax.add_patch(Ellipse((x0, boy - r), 2 * r * 0.62, 2 * r * 0.7, fc="#d9d7d2", ec="none", alpha=0.95))
    b = boy - 2 * r
    ax.add_patch(FancyBboxPatch((x0 - omuz / 2, b - 62), omuz, 60, boxstyle="round,pad=0,rounding_size=8", fc=renk,
                                ec="none"))
    k = omuz * 0.62
    ax.fill([x0 - omuz / 2 + 2, x0 + omuz / 2 - 2, x0 + k / 2, x0 - k / 2], [b - 55, b - 55, b - 82, b - 82],
            color=renk, lw=0)
    for s in (-1, 1):
        ax.fill([x0 + s * 2, x0 + s * k / 2, x0 + s * k / 2 * 0.75, x0 + s * 3], [b - 80, b - 80, 0, 0], color=renk, lw=0)
        ax.fill([x0 + s * omuz / 2 - s, x0 + s * omuz / 2 + s * 8, x0 + s * omuz / 2 + s * 4, x0 + s * omuz / 2 - s * 6],
                [b - 4, b - 70, b - 72, b - 8], color=renk, lw=0)


def sekil_kurulum():
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.8), facecolor="white", gridspec_kw=dict(width_ratios=[1.6, 1]))
    ax = axs[0]
    ax.add_patch(Rectangle((-40, 0), 30, 230, fc="#f1efe8", ec=SOLUK))
    ax.text(-25, 235, "düz arka plan", ha="center", fontsize=8, color=MUR2)
    kisi(ax, 20, 176, 50, "#9fb7d9", yuz_bulanik=False)
    ax.add_patch(Rectangle((48, 0), 3, 100, fc="#e8c547", ec="none"))
    ax.text(55, 50, "1 m cetvel\n(ayak hizasında)", fontsize=8, color=MUR2, va="center")
    ax.plot([300, 300], [0, 100], color=MUR, lw=2)
    ax.add_patch(Polygon([(290, 100), (310, 100), (300, 112)], fc=MUR))
    ax.add_patch(Rectangle((292, 106), 16, 10, fc=MUR))
    ax.plot([300, 20], [111, 111], color=MAVI, lw=1, ls="--")
    ax.annotate("", (20, -12), (300, -12), arrowprops=dict(arrowstyle="<->", color=MUR2))
    ax.text(160, -24, "3 m (her kişi için aynı)", ha="center", fontsize=9, color=MUR2)
    ax.annotate("", (318, 0), (318, 106), arrowprops=dict(arrowstyle="<->", color=MUR2))
    ax.text(322, 53, "kamera\n100 cm", fontsize=9, color=MUR2, va="center")
    ax.axhline(0, color=MUR2, lw=1)
    ax.set_xlim(-45, 360)
    ax.set_ylim(-30, 245)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Yandan görünüş: kurulum", loc="left", fontsize=11)
    ax = axs[1]
    ax.add_patch(Rectangle((0, 0), 100, 100, fc="white", ec=MUR2))
    for x, t in ((50, "zemin işareti\n(ayak ucu)"),):
        ax.plot([35, 65], [20, 20], color=TURUNCU, lw=3)
        ax.text(50, 12, t, ha="center", va="top", fontsize=8, color=MUR2)
    ax.text(50, 92, "Yasaklar", ha="center", fontsize=10, weight="bold", color=MUR)
    for i, t in enumerate(["kapı, çerçeve, çizgili duvar", "arkada eşya ya da insan", "ayakkabı, şapka, bol giysi",
                           "geniş açı / yakın çekim", "yüzü bulanıklaştırmadan paylaşmak"]):
        ax.text(8, 80 - i * 10, "× " + t, fontsize=8.5, color=MUR2)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(SEKIL / "kurulum.png", dpi=200)
    plt.close(fig)


def sekil_cift():
    fig, ax = plt.subplots(figsize=(5.2, 4.2), facecolor="white")
    kisi(ax, 0, 177, 46, "#9fb7d9")
    kisi(ax, 70, 175, 54, "#7fc9a6")
    ax.axhline(0, color=MUR2, lw=1)
    ax.text(0, -10, "A", ha="center", fontsize=14, weight="bold")
    ax.text(70, -10, "B", ha="center", fontsize=14, weight="bold")
    ax.text(35, 205, "Hangisi daha uzun?", ha="center", fontsize=12, color=MUR)
    ax.set_xlim(-40, 110)
    ax.set_ylim(-20, 215)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(SEKIL / "cift.png", dpi=200)
    plt.close(fig)


sekil_kurulum()
sekil_cift()

# ---------------------------------------------------------------------------
# Biçemler
# ---------------------------------------------------------------------------

st = dict(
    baslik=ParagraphStyle("baslik", fontName="GB", fontSize=24, leading=29, textColor=MUR, spaceAfter=8),
    alt=ParagraphStyle("alt", fontName="G", fontSize=13, leading=17, textColor=MUR2, spaceAfter=14),
    h1=ParagraphStyle("h1", fontName="GB", fontSize=16, leading=20, textColor=MUR, spaceBefore=6, spaceAfter=8),
    h2=ParagraphStyle("h2", fontName="GB", fontSize=12.5, leading=16, textColor=MUR, spaceBefore=8, spaceAfter=4),
    p=ParagraphStyle("p", fontName="G", fontSize=10.5, leading=14.2, textColor=MUR, spaceAfter=5, alignment=TA_LEFT),
    kucuk=ParagraphStyle("k", fontName="G", fontSize=8.8, leading=11.5, textColor=MUR2, spaceAfter=4),
    kutu=ParagraphStyle("kutu", fontName="G", fontSize=10.5, leading=14.2, textColor=MUR),
    hucre=ParagraphStyle("hucre", fontName="G", fontSize=9.2, leading=11.8, textColor=MUR),
    hucreb=ParagraphStyle("hucreb", fontName="GB", fontSize=9.2, leading=11.8, textColor=MUR),
    soz=ParagraphStyle("soz", fontName="GI", fontSize=10.5, leading=14.5, textColor=MUR, leftIndent=12, rightIndent=12,
                       spaceAfter=6, backColor=colors.HexColor("#f1efe8"), borderPadding=8),
)


def P(t, s="p"):
    return Paragraph(t, st[s])


def liste(maddeler, numarali=False):
    return ListFlowable([ListItem(P(m), leftIndent=14, value=i + 1 if numarali else None)
                         for i, m in enumerate(maddeler)],
                        bulletType="1" if numarali else "bullet", start="1" if numarali else None,
                        bulletFontName="G", bulletFontSize=9.5, leftIndent=14, bulletColor=MUR2)


def tablo(satirlar, gen, baslik=True, zemin="#f1efe8", satir_h=None):
    veri = [[P(str(h), "hucreb" if (baslik and i == 0) else "hucre") for h in r] for i, r in enumerate(satirlar)]
    yuk = None if satir_h is None else [None] + [satir_h * cm] * (len(satirlar) - 1)
    t = Table(veri, colWidths=[g * cm for g in gen], repeatRows=1 if baslik else 0, rowHeights=yuk)
    stil = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(SOLUK)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if baslik:
        stil.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(zemin)))
    t.setStyle(TableStyle(stil))
    return t


def kutu(icerik, renk="#eaf6f0"):
    t = Table([[icerik]], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(renk)),
                           ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(YESIL)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def bos_satirlar(n, sutun):
    return [["" for _ in sutun] for _ in range(n)]


# ---------------------------------------------------------------------------
# İçerik
# ---------------------------------------------------------------------------

S = []
S += [Spacer(1, 2.5 * cm), P("Kaslı Vücut Daha Uzun mu Görünür?", "baslik"),
      P("Fotoğraf deneyi protokolü · uygulayıcılar için adım adım rehber", "alt"),
      Image(str(SEKIL / "cift.png"), width=9 * cm, height=7.3 * cm), Spacer(1, 0.8 * cm),
      P(f"Sürüm 2 · {date(2026, 10, 8).strftime('%d.%m.%Y')} · arastirma deposu, "
        "<i>algilanan-boy-ve-vucut-yapisi</i>", "kucuk"),
      P("Lisans: CC BY-NC 4.0 (atıf vererek, ticari olmayan amaçla kullanılabilir ve değiştirilebilir). "
        "Bu belge tıbbi ya da hukuki tavsiye değildir.", "kucuk"),
      PageBreak()]

S += [P("Bir sayfada deney", "h1"),
      kutu(P(f"<b>Soru:</b> Gerçek boyları aynı iki kişiden kaslı, kalıplı olan daha uzun mu görünür?<br/>"
             f"<b>Yöntem:</b> Boyları ölçülmüş erkeklerin standart fotoğrafları ikişer ikişer gösterilir. Onları "
             f"tanımayan değerlendiriciler \"hangisi daha uzun?\" diye seçer. Gerçek boy farkı bilindiği için "
             f"seçimlerin kalıplı olanın lehine kayıp kaymadığı ölçülür.<br/>"
             f"<b>Önerilen:</b> <b>{N_PR} fotoğraflanan kişi</b> (yarısı zayıf, yarısı kalıplı; boyları birbirine yakın) "
             f"ve <b>{R_PR} değerlendirici</b>. Değerlendirici başına {K} çift, ~6-8 dakika. Bu tasarım gerçek 2 cm'lik "
             f"etkiyi %{PR2:.0f}, 1 cm'lik etkiyi %{PR1:.0f} olasılıkla yakalar; kişiler arası görünüş farkı büyük olsa "
             f"bile 2 cm için %{PR2_TAU:.0f}.<br/>"
             f"<b>Asgari:</b> Önceden yazılan kurala göre en küçük tasarım {N_ON} kişi ve {R_ON} değerlendirici "
             f"(2 cm için %{G2:.0f}). Ama görünüş farkı büyükse gücü %{ON2_TAU:.0f}'e düşer; bu yüzden önerilmez.<br/>"
             f"<b>Yanlış alarm:</b> Gerçek etki yokken \"var\" deme olasılığı ~%{FP:.0f}.", "kutu")),
      Spacer(1, 10),
      P("Akış", "h2"),
      liste(["Hazırlık: onam formları, malzeme, çekim yeri (bölüm 3-4).",
             "Ölçüm günü: her kişinin boyu, kilosu ölçülür ve standart fotoğrafı çekilir (bölüm 5-6).",
             "Görsellerin hazırlanması: aynı ölçek, aynı zemin çizgisi, yüzler bulanık (bölüm 7).",
             "Değerlendirme oturumları: tanımayan kişiler çiftleri değerlendirir (bölüm 8).",
             "Analiz: hazır kodla iki aşamalı analiz; karar kuralları önceden sabit (bölüm 9).",
             "Paylaşım: yalnız kimliksiz, toplu sonuçlar. Fotoğraflar silinir (bölüm 3)."], numarali=True),
      Spacer(1, 8),
      P("Benzetme", "h2"),
      P("Bir terazi düşünün. Kefelerde iki kişinin gerçek boyu var ve biz bunları santimetresine kadar biliyoruz. "
        "Değerlendiricilere \"hangisi ağır basıyor?\" diye soruyoruz. Gerçek fark sabitken cevaplar sistematik olarak "
        "kalıplının tarafına kayıyorsa, terazinin bir de \"göz\" eli var demektir. Bu deney o elin kaç santimetre "
        "ittiğini ölçer."),
      PageBreak()]

S += [P("1. Neden bu deney?", "h1"),
      P("Bu deponun sürüm 1 araştırması, aynı boyda kaslı ve zayıf iki kişiyi karşılaştırıp algılanan boyu ölçen bir "
        "çalışma bulamadı. Var olan kanıtlar iki zıt yöne çekiyor:"),
      liste(["<b>Güç = büyüklük:</b> Güçlü ya da tehditkâr görünen kişi 1-4 cm daha uzun tahmin ediliyor "
             "(Fessler ve ark. 2012; Marsh ve ark. 2009). Kaslılık da bir güç ipucu.",
             "<b>Geometri:</b> Aynı boyda daha geniş vücut daha kısa görünüyor (Beck ve ark. 2013: yargıların %71'i).",
             "<b>Gözlemcinin hali:</b> Kendini güçsüz hisseden, karşısındakini daha büyük görüyor "
             "(Duguid & Goncalo 2012; Fessler & Holbrook 2013)."]),
      P("Sürüm 1'in simülasyonu bu etkilerin toplamını ~+1 cm civarında, ama yönü belirsiz buldu. Soru ancak doğrudan "
        "bir ölçümle çözülebilir."),
      P("2. Hipotezler (önceden sabit)", "h1"),
      tablo([["", "Hipotez", "Nasıl test edilir"],
             ["H1 (birincil)", "Gerçek boy farkı sabitken yapısı daha kalıplı olan daha uzun algılanır.",
              "PSE₂ ≠ 0. PSE₂: yapı farkı 2 SD olan iki kişiden kalıplının \"aynı boyda\" görünmesi için kaç cm kısa "
              "olabileceği. %95 aralık 0'ı içermiyorsa H1 kabul edilir."],
             ["H2 (ikincil)", "Bedeninden memnun olmayan değerlendiricilerde etki daha büyüktür.",
              "Değerlendirici başına PSE₂ ile beden memnuniyeti puanının ilişkisi."],
             ["H3 (keşifsel)", "Fotoğraflar tek tek gösterilip cm tahmini istendiğinde de aynı kayma vardır.",
              "Tahmin − gerçek boy ile yapı indeksinin ilişkisi."]], [2.4, 6.0, 8.0]),
      Spacer(1, 6),
      P("Ön kayıt: hipotezler, analiz ve karar kuralları deney yapılmadan önce yazıldı ve depoya kaydedildi "
        "(simulasyon/PLAN.md). Sonuç ne çıkarsa çıksın yayımlanır.", "kucuk"),
      PageBreak()]

S += [P("3. Etik ve gizlilik", "h1"),
      kutu(P("<b>Kural:</b> Bu deneyde kimse incitilmemeli. Kimsenin bedeni hakkında kişisel sonuç bildirilmez, "
             "sıralama yapılmaz, fotoğraflar yayımlanmaz.", "kutu"), "#fdeee6"),
      Spacer(1, 8),
      liste(["<b>Onam:</b> Her fotoğraflanan kişiye ve her değerlendiriciye deneyin amacı anlatılır, yazılı onam alınır "
             "(ek A, B). İstediği an, gerekçe göstermeden çekilebilir; verisi silinir.",
             "<b>18 yaş altı:</b> Katılımcının kendi onamına ek olarak <b>veli onamı</b> zorunludur (ek B). Okulda "
             "yapılacaksa okul yönetiminin izni alınır.",
             "<b>Kişisel veri:</b> Fotoğraf, boy ve kilo kişisel veridir. Türkiye'de 6698 sayılı Kişisel Verilerin "
             "Korunması Kanunu (KVKK) geçerlidir. Veriler yalnız bu amaçla toplanır, en az veri ilkesi uygulanır.",
             "<b>Kimliksizleştirme:</b> Her kişiye bir kod verilir (H01, H02...). Ad-kod eşleştirme listesi ayrı ve "
             "kilitli tutulur. Fotoğraflarda yüz bulanıklaştırılır; dövme, yazılı tişört gibi tanıtıcı işaretler örtülür.",
             "<b>Saklama:</b> Fotoğraflar yalnız araştırma ekibinin cihazında, şifreli klasörde kalır; internete, sosyal "
             "medyaya, mesajlaşma gruplarına yüklenmez. Analiz bitince silinir; silindiği tarih kayda geçer.",
             "<b>Paylaşım:</b> Yalnız kimliksiz, toplu sonuçlar (ör. \"PSE₂ = 1.2 cm\") paylaşılır. Tek bir kişinin "
             "ölçüsü ya da \"en uzun görünen\" bilgisi paylaşılmaz.",
             "<b>Değerlendiriciler</b> fotoğraflardaki kişileri tanımamalıdır; tanıyorsa o oturum analiz dışı kalır.",
             "<b>Bilgilendirme:</b> Deney bitince katılımcılara amaç ve genel sonuç anlatılır."]),
      P("Bu bölüm genel bir rehberdir, hukuki görüş değildir. Kurum içinde yapılacaksa kurumun etik ve veri koruma "
        "kurallarına uyulur.", "kucuk"),
      P("4. Malzemeler", "h1"),
      tablo([["Malzeme", "Not"],
             ["Telefon ya da fotoğraf makinesi + tripod", "Bütün çekimler aynı cihaz ve aynı yakınlaştırmayla."],
             ["Şerit metre (en az 3 m) ve duvar metresi", "Kamera mesafesi ve boy ölçümü için."],
             ["Kalın kitap ya da gönye", "Boy ölçümünde başın üstüne dik koymak için."],
             ["1 m'lik düz cetvel (kontrast renkli)", "Her fotoğrafta ayak hizasında; ölçekleme için."],
             ["Tartı", "Hep aynı tartı."],
             ["Düz, açık renkli arka plan", "Boş duvar ya da kumaş; kapı, çizgi, eşya yok."],
             ["Standart giysi", "Aynı tip düz tişört ve koyu eşofman altı; ayakkabısız (ince çorap olabilir)."],
             ["Bant", "Zemine ayak ve kamera işaretleri."],
             ["Kayıt formları", "Ek C (ölçüm), ek D (değerlendirici)."]], [6.4, 10.0]),
      PageBreak()]

S += [P("5. Ölçüm", "h1"),
      tablo([["Ölçü", "Nasıl", "Kayıt"],
             ["Boy", "Ayakkabısız, topuklar, kalça ve sırt duvarda, karşıya bakış. Kitap başın üstüne dik; alt kenarı "
                     "işaretlenir. Kişi uzaklaşıp yeniden durur; <b>3 ölçüm</b>, ortalaması alınır. Bütün kişiler aynı "
                     "gün, aynı saat aralığında ölçülür (boy gün içinde ~1-2 cm değişir).", "0.5 cm"],
             ["Kilo", "Hafif giysiyle, aynı tartıda.", "0.1 kg"],
             ["Omuz genişliği", "Fotoğraftan: omuzların en geniş iki noktası (deltoid) arası piksel, cetvelle cm'ye "
                                "çevrilir. Elle ölçülmez (dokunma gerektirmesin).", "0.5 cm"],
             ["Saç yüksekliği (keşifsel)", "Kafa tepesinden saçın en üstüne yaklaşık mesafe.", "0.5 cm"]],
            [3.0, 11.0, 2.4]),
      Spacer(1, 8),
      P("<b>Kimi seçmeli?</b> Amaçlı seçim deneyin gücünü belirgin artırır (bölüm 10): fotoğraflanacak kişilerin "
        "yarısı belirgin zayıf, yarısı belirgin kalıplı olsun; boyları birbirine yakın olsun (ör. 170-182 cm). Boy "
        "farkı çok büyük olan çiftler bilgi vermez: herkes uzun olanı doğru bilir."),
      P("6. Fotoğraf çekimi", "h1"),
      Image(str(SEKIL / "kurulum.png"), width=16.4 * cm, height=6.2 * cm),
      liste(["Kamera tripodda, yerden <b>100 cm</b> yükseklikte, kişiye <b>3 m</b> uzaklıkta. Zemine işaret konur; "
             "her çekimde aynı yer.",
             "Yakınlaştırma yok, geniş açı modu yok; telefonun standart (1×) lensi.",
             "Kişi zemindeki işarete ayak uçlarıyla gelir; dik ama zorlamasız durur; kollar yanda; karşıya bakar.",
             "Cetvel ayak hizasında, kişinin yanında durur (görsel hazırlanırken kırpılacak).",
             "Her kişiden 2 kare çekilir; en dik ve net olanı seçilir. Seçim yapı bilgisine bakılmadan yapılır.",
             "Işık her çekimde aynı; gölge kişinin arkasına düşmesin."]),
      PageBreak()]

S += [P("7. Görselleri hazırlama", "h1"),
      liste(["<b>Ölçek:</b> Her fotoğrafta cetvelin 100 cm'si kaç piksel, ölçülür. Bütün fotoğraflar aynı "
             "piksel/cm oranına getirilir. Böylece gerçek boy farkı görüntüde korunur.",
             "<b>Yüz:</b> Bulanıklaştırılır (yüz ipuçları algılanan boyu değiştirebilir; Re ve ark. 2013).",
             "<b>Kırpma:</b> Cetvel ve arka plandaki fazlalıklar kırpılır. Her görsel aynı genişlik ve yükseklikte.",
             "<b>Çift görseli:</b> İki kişi yan yana, ayaklar <b>aynı zemin çizgisinde</b>, aralarında sabit boşluk. "
             "Arkada boy ipucu verecek hiçbir şey yok.",
             "<b>Çift listesi:</b> Hazır kod, boy farkı ≤ 6 cm olan çiftlerden her değerlendiriciye dengeli bir liste "
             "üretir; her kişi yaklaşık eşit sayıda gösterilir, sol-sağ rastgeledir:<br/>"
             "<font face='G' color='#52514e'>python analiz_et.py tasarim hedefler.csv "
             f"{R_ON} {K} tasarim.csv</font>"]),
      Spacer(1, 4),
      P("8. Değerlendirme oturumu", "h1"),
      P("Değerlendirici kişileri tanımamalı ve deneyin hipotezini önceden bilmemelidir. Yönerge aynen okunur:"),
      P("\"Ekranda yan yana iki kişinin fotoğrafını göreceksiniz. Her seferinde hangisinin <b>daha uzun</b> "
        "olduğunu seçin. Emin olmasanız da bir seçim yapın; ilk izleniminiz yeterli. Doğru ya da yanlış cevap "
        "puanlanmıyor. Yaklaşık 7 dakika sürecek.\"", "soz"),
      liste([f"{K} çift, listedeki sırayla; her biri en fazla ~5 saniye ekranda kalır, sonra cevap beklenir.",
             "Ekran: dizüstü ya da masaüstü; telefon ekranı çok küçük kalabilir. Ekran parlaklığı ve uzaklığı "
             "herkes için benzer.",
             "Görev bittikten <b>sonra</b> iki kısa soru: yaş ve \"Bedenimden memnunum\" (1-7). Önce sorulursa beden "
             "düşüncesini tetikleyip cevapları etkileyebilir.",
             "Son soru: \"Fotoğraflardaki kişilerden tanıdığınız var mı?\" Evet ise oturum analiz dışı.",
             "İsteğe bağlı keşifsel görev (H3): her kişi tek başına gösterilir, \"Bu kişi kaç cm?\" diye sorulur."]),
      PageBreak()]

S += [P("9. Veri ve analiz", "h1"),
      P("Veriler üç CSV dosyasına girilir (şablonlar deponun <i>sablonlar/</i> klasöründe):"),
      tablo([["Dosya", "Sütunlar", "Not"],
             ["hedefler.csv", "id, boy_cm, omuz_cm, kilo_kg, sac_yuksekligi_cm, not", "Bir satır = bir kişi; ad yok"],
             ["yanitlar.csv", "degerlendirici, sira, sol, sag, secilen", "secilen = \"daha uzun\" seçilenin id'si"],
             ["degerlendiriciler.csv", "degerlendirici, yas, beden_memnuniyeti_1_7, hedefleri_taniyor_mu", "H2 için"]],
            [3.6, 8.0, 4.8]),
      Spacer(1, 6),
      P("<b>Analiz komutu:</b> <font color='#52514e'>python analiz_et.py analiz hedefler.csv yanitlar.csv</font>"),
      P("<b>Neden iki aşama?</b> Etkinin tekrar birimi <b>fotoğraflanan kişidir</b>. Değerlendiriciler binlerce cevap "
        "verir ama hepsi aynı 20-30 kişiye bakar. Bir kişi yapısıyla ilgisiz bir nedenle (saç, duruş) uzun görünürse, "
        "bu her değerlendiricide tekrar eder. Cevapları bağımsız saymak sahte \"anlamlı\" sonuç üretir: simülasyonda "
        f"bu yanlış analiz, etki yokken %{FP_NAIF:.0f} oranında \"var\" dedi; doğru analiz %{FP:.0f}."),
      liste(["<b>Aşama 1:</b> Bütün cevaplardan her kişinin \"algılanan boy\" puanı çıkarılır (Thurstone ölçeklemesi, "
             "probit).",
             "<b>Aşama 2:</b> Kişi düzeyinde regresyon: algılanan boy puanı = a + b·gerçek boy + c·yapı indeksi.",
             "<b>PSE₂ = 2c / b</b> santimetre. %95 aralık kişiler üzerinden bootstrap ile.",
             "<b>Kontrol:</b> b > 0 olmalı (gerçek boy algıyı artırmalı). Değilse görseller boy farkını göstermiyor; "
             "sonuç yorumlanmaz, görseller düzeltilir."], numarali=True),
      P("Karar kuralları (önceden sabit)", "h2"),
      tablo([["Sonuç", "Yorum"],
             ["%95 aralık tamamen 0'ın üstünde", "Kalıplı vücut aynı boyda daha uzun algılanıyor."],
             ["%95 aralık tamamen 0'ın altında", "Kalıplı vücut aynı boyda daha kısa algılanıyor."],
             ["%95 aralık 0'ı içeriyor", "Bu örneklemle fark gösterilemedi (yokluğu kanıtlamaz)."],
             ["Büyüklük", "< 0.5 cm ihmal edilebilir · 0.5-2 cm küçük · ≥ 2 cm belirgin."]], [6.4, 10.0]),
      PageBreak()]

# Güç tablosu
a = guc[(guc.secim == "amacli")]
sat = [["Kişi (N)", "Değerlendirici (R)", "Etki 1 cm", "Etki 2 cm", "Etki 3 cm", "Etki yokken yanlış alarm"]]
for N in sorted(a.N.unique()):
    for R in sorted(a.R.unique()):
        g = a[(a.N == N) & (a.R == R)].set_index("pse2_gercek").guc
        isaret = " (önerilen)" if (N == N_PR and R == R_PR) else " (asgari)" if (N == N_ON and R == R_ON) else ""
        sat.append([f"{N}{isaret}", R, f"%{100 * g[1.0]:.0f}", f"%{100 * g[2.0]:.0f}", f"%{100 * g[3.0]:.0f}",
                    f"%{100 * g[0.0]:.0f}"])
S += [P("10. Kaç kişi gerekiyor?", "h1"),
      P("Deneyin 300'er kez sentetik verilerle (gerçek vücut ölçüsü dağılımlarıyla) simüle edilmesiyle hesaplandı. "
        "Değerler amaçlı seçim içindir (yarısı zayıf, yarısı kalıplı; boylar 170-182 cm). Rastgele seçimde güç belirgin "
        "düşüktür. \"Güç\": gerçek etki varken onu yakalama olasılığı."),
      tablo(sat, [3.0, 3.0, 2.4, 2.4, 2.4, 3.2]),
      Spacer(1, 6),
      Image(str(SIM / "guc.png"), width=16.4 * cm, height=5.3 * cm),
      P("<b>Sağlamlık kontrolü (keşifsel):</b> Fotoğraflanan kişilerin yapıyla ilgisiz görünüş farkları (saç, duruş) "
        "varsayılandan büyükse (τ = 2 cm) güç düşer. Bu durumda 2 cm'lik etki için güç: " +
        ", ".join(f"{int(r.N)} kişi %{100 * r.guc_ya_da_yanlis_alarm:.0f}" for r in kt[kt.pse2_gercek == 2.0].itertuples()) +
        f" (30 değerlendirici). Önerilen {N_PR} kişi bu yüzden seçildi."),
      P("Önemli: güç büyük ölçüde <b>fotoğraflanan kişi sayısına</b> bağlı; değerlendirici sayısını artırmak belli "
        "bir noktadan sonra az kazandırır. Varsayımlar (kişiye özgü görünüş farkı, göz gürültüsü) simulasyon/PLAN.md'de; "
        "bunlar gerçekte daha büyükse daha çok kişi gerekir.", "kucuk"),
      PageBreak()]

S += [P("11. Kontrol listesi ve sık hatalar", "h1"),
      tablo([["Hata", "Neden sorun", "Önlem"],
             ["Kamera her çekimde farklı yerde", "Perspektif boyları bozar", "Zemin ve tripod işareti"],
             ["Arka planda kapı, çizgi", "Değerlendirici boyu cetvel gibi okur", "Düz arka plan"],
             ["Farklı giysiler", "Bol giysi yapıyı gizler ya da büyütür", "Standart tişört"],
             ["Yüz görünüyor", "Gizlilik; yüz ipuçları algıyı etkiler", "Bulanıklaştırma"],
             ["Değerlendirici kişileri tanıyor", "Gerçek boyu biliyor olabilir", "Oturumu analiz dışı bırak"],
             ["Hipotez değerlendiriciye anlatıldı", "Beklenti cevapları yönlendirir", "Amaç sonra anlatılır"],
             ["Beden sorusu görevden önce", "Beden düşüncesini tetikler", "Görevden sonra sor"],
             ["Cevapları bağımsız saymak", "Sahte anlamlılık", "Hazır iki aşamalı analiz"],
             ["Sonuç beğenilmezse yayımlamamak", "Yayın yanlılığı", "Her sonuç yayımlanır (K4)"]], [4.6, 5.8, 6.0]),
      Spacer(1, 10),
      P("Simülasyonun doğruladıkları", "h2"),
      tablo([["Test", "Sonuç", ""]] + [[r.test, r.deger, "geçti" if r.sonuc == "GEÇTİ" else "KALDI"]
                                         for r in testler.itertuples()], [1.4, 13.4, 1.6]),
      PageBreak()]

S += [P("Ek A · Katılımcı bilgilendirme ve onam formu (fotoğraflanan, taslak)", "h1"),
      P("<b>Amaç:</b> İnsanların boy algısının vücut yapısından etkilenip etkilenmediğini araştırıyoruz. Bu çalışma "
        "bir okul/gönüllü araştırma projesidir ve tıbbi bir değerlendirme değildir."),
      P("<b>Ne yapacaksınız:</b> Boyunuz ve kilonuz ölçülecek, standart bir giysiyle boydan fotoğrafınız çekilecek "
        "(~10 dakika). Fotoğrafınız, sizi tanımayan kişilere başka bir fotoğrafla yan yana gösterilecek."),
      P("<b>Gizlilik:</b> Yüzünüz bulanıklaştırılacak, adınız kullanılmayacak (kod verilecek). Fotoğraflar yalnız "
        "araştırma ekibinde, şifreli saklanacak; internette paylaşılmayacak; analiz bitince silinecek. Size ya da "
        "başkasına bedeninizle ilgili kişisel bir sonuç bildirilmeyecek."),
      P("<b>Haklarınız:</b> Katılım gönüllüdür. İstediğiniz an, gerekçe göstermeden çekilebilirsiniz; verileriniz silinir. "
        "6698 sayılı KVKK kapsamındaki haklarınızı kullanmak için iletişim: ______________________"),
      Spacer(1, 6),
      tablo([["Ad soyad", "Tarih", "İmza"], ["", "", ""]], [7.0, 4.0, 5.4], satir_h=1.2),
      Spacer(1, 4),
      P("[   ] Okudum, anladım, katılmayı kabul ediyorum.<br/>[   ] Fotoğrafımın yukarıdaki koşullarla kullanılmasına "
        "izin veriyorum."),
      Spacer(1, 12),
      P("Ek B · Veli onam formu (18 yaş altı için, taslak)", "h1"),
      P("Velisi bulunduğum ________________________ adlı çocuğumun, Ek A'da açıklanan koşullarla (ölçüm, yüzü "
        "bulanıklaştırılmış fotoğraf, kod ile saklama, analiz sonunda silme) bu araştırmaya katılmasına izin veriyorum. "
        "Çocuğum ya da ben istediğimiz an katılımı sonlandırabiliriz."),
      tablo([["Veli ad soyad", "Yakınlık", "Tarih", "İmza"], ["", "", "", ""]], [6.0, 3.0, 3.0, 4.4], satir_h=1.2),
      PageBreak()]

S += [P("Ek C · Ölçüm kayıt formu", "h1"),
      P("Ad bu forma yazılmaz. Kod-ad listesi ayrı ve kilitli tutulur.", "kucuk"),
      tablo([["Kod", "Boy 1", "Boy 2", "Boy 3", "Kilo", "Saç (cm)", "Saat", "Fotoğraf no", "Not"]] +
            bos_satirlar(22, range(9)), [1.4, 1.5, 1.5, 1.5, 1.5, 1.6, 1.4, 2.2, 3.8], satir_h=0.85),
      PageBreak(),
      P("Ek D · Değerlendirici formu", "h1"),
      P("Görevden <b>sonra</b> doldurulur.", "kucuk"),
      tablo([["Değerlendirici no", "Yaş", "\"Bedenimden memnunum\" (1 hiç - 7 tamamen)",
              "Fotoğraflardaki kişileri tanıyor musunuz?", "Tarih"]] + bos_satirlar(16, range(5)),
            [3.0, 1.6, 5.2, 4.2, 2.4], satir_h=0.8),
      Spacer(1, 10),
      P("Kaynaklar", "h2"),
      P("Beck DM, Emanuele B, Savazzi S. Psychon Bull Rev 2013;20:1154. · Duguid MM, Goncalo JA. Psychol Sci "
        "2012;23:36. · Fessler DMT, Holbrook C, Snyder JK. PLoS ONE 2012;7:e32751. · Fessler DMT, Holbrook C. PLoS ONE "
        "2013;8:e71306. · Marsh AA ve ark. PLoS ONE 2009;4:e5707. · Re DE ve ark. PLoS ONE 2013;8:e80957. · ANSUR II "
        "(2012), openlab.psu.edu/ansur2. · Thurstone LL. Psychol Rev 1927;34:273 (çift karşılaştırma ölçeklemesi).",
        "kucuk")]


def sayfa(c, d):
    c.saveState()
    c.setFont("G", 8)
    c.setFillColor(colors.HexColor(MUR2))
    c.drawString(2 * cm, 1.2 * cm, "Kaslı vücut daha uzun mu görünür? · Deney protokolü · CC BY-NC 4.0 · "
                                   "Tıbbi ya da hukuki tavsiye değildir")
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(d.page))
    c.restoreState()


doc = SimpleDocTemplate(str(CIKTI / "deney_protokolu.pdf"), pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm,
                        topMargin=2 * cm, bottomMargin=2 * cm, title="Kaslı vücut daha uzun mu görünür? Deney protokolü",
                        author="arastirma deposu", subject="Algılanan boy ve vücut yapısı, sürüm 2")
doc.build(S, onFirstPage=sayfa, onLaterPages=sayfa)
print("Yazıldı:", CIKTI / "deney_protokolu.pdf")
