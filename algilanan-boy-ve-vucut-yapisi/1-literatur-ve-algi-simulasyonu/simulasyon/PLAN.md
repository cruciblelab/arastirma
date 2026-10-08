# Simülasyon Planı: Kaslı Vücut Daha Uzun mu Görünür? Gerçek Boy, Görünür Boy, Algılanan Boy

> **Plan sürümü:** 1 · **Tarih:** 2026-10-08 · **Durum:** ön kayıt (kod yazılmadan ve çalıştırılmadan önce commit edildi)
>
> Bu dosya hiçbir simülasyon sonucu görülmeden yazıldı. Testler çalıştıktan sonra **ölçütler değiştirilmez.** Her değişiklik "Plandan sapmalar" tablosuna tarih ve gerekçesiyle yazılır.

## 1. Soru

Zayıf yapılı, ortalama boylu 17 yaşında bir erkek gözlemliyor: "Benimle aynı boyda, hatta benden kısa ama kaslı, kalıplı çocuklar benden çok daha uzun duruyor."

1. Bu gözlemin ne kadarı **gerçek bir fiziksel fark** (ayakkabı, saç, duruş)?
2. Ne kadarı **herkesin yaptığı bir algı yanılgısı** (güçlü görüneni büyük görme, geniş vücudu kısa görme)?
3. Ne kadarı **gözlemciye özgü** (kendini eksik hissetmek, yukarı doğru kıyaslama, kaslı bedene seçici dikkat ve bellek)?
4. Bir haftalık gözlemde "benden kısa ama daha uzun görünen kaslı biri" olayı, hiçbir yanlılığı olmayan bir gözlemcide bile ne sıklıkla olur?

**Kapsam dışı:** Boy uzatma; kas kazanma programı; klinik değerlendirme (kas dismorfisi tanısı).

**Benzetme:** Bir terazi düşün. Kefelerde iki kişinin gerçek boyu var. Teraziyi üç el itiyor: birincisi gerçek eller (ayakkabı tabanı, saç, dik duruş), ikincisi herkesin gözünde olan eller (güçlü görüneni büyük görme, geniş olanı kısa görme), üçüncüsü yalnız bakan kişinin eli (kendini eksik hissetmek). Simülasyon her elin terazide kaç santimetre ittiğini ayırmaya çalışır.

## 2. Literatür (planı biçimlendiren bulgular)

| Konu | Bulgu | Kaynak |
|---|---|---|
| Doğrudan test | Aynı gerçek boyda kaslı ve ince vücudu karşılaştırıp algılanan boyu ölçen çalışma **bulunamadı**. | – |
| Güç = boyut | Silah tutan elin sahibi +1.3 ile +3.6 cm daha uzun tahmin ediliyor (N = 424-628). Fiziksel olarak kısıtlanan erkek, kızgın hedefi +2.4 cm uzun, kendini −8.8 cm kısa tahmin ediyor. Arkadaşlarıyla olan erkek hasmı −4.0 cm kısa görüyor (bir çalışmada; ikincisinde anlamsız). Bu çalışmalarda vücut görünmüyor; ölçülen şey zihinde canlandırılan boy. | Fessler ve ark. 2012; Fessler & Holbrook 2013a, 2013b |
| Statü ve duruş | Yüksek statü duruşu +2.3 cm daha uzun algılanıyor; bu duruş görüntüde %60 daha geniş olduğu halde. | Marsh ve ark. 2009 |
| Gözlemcinin gücü | Güçlü hissettirilen gözlemci karşıdakini ~4 cm kısa, kendini +3.1 cm uzun tahmin ediyor; güçsüz hissettirilen ile kontrol arasında karşıdaki için ~0.9 cm fark. | Duguid & Goncalo 2012 |
| Geometri | Aynı boyda, %19 daha geniş vücut yargıların %71'inde daha kısa bulunuyor; yanılgı boyun %7'sinden küçük. | Beck ve ark. 2013 |
| Doğruluk | Fotoğraftan boy tahmininde ortalama mutlak hata 6.3 cm. Resimde iki figür arasında 4 cm farkı ayırt etme %70'in üstünde, 1-3 cm'de şansa yakın. | Martynov ve ark. 2020; Coury ve ark. 2022 |
| Fiziksel | Gevşek duruştan dik duruşa geçiş erkekte +1.3 cm. Ayakkabı erkekte ~+2.5 cm (her iki kişide de var; fark önemli). Erkek saç modelinin görünür boya katkısı için ölçüm yok. | Prushansky ve ark. 2013; ergonomi düzeltmesi |
| Dikkat ve bellek | Bedeninden memnun olmayan erkekler kaslı bedenlere daha uzun ve daha sık bakıyor, kaslılıkla ilgili bilgileri daha iyi hatırlıyor. Yukarı doğru kıyaslama ile memnuniyetsizlik birbirini besliyor. | Cho & Lee 2013; Porras-Garcia 2020; Unterhalter 2007; Ooi 2025 |
| Boy referansı | Türkiye, 2019: 17 yaş 174.9, 18 yaş 175.8 cm; SD ~6.2-6.4 cm. | NCD-RisC 2020; Günöz 2014 |
| Vücut yapısı | ANSUR II, 17-24 yaş erkek (n = 1358): boy sabitken omuz (bideltoid) genişliği ve kilo büyük ölçüde boydan bağımsız değişiyor. | ANSUR II (2012) |

## 3. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Model üç katmanlıdır: **gerçek boy → görünür boy → algılanan boy.** Her katmanın katkısı ayrı ayrı raporlanır. |
| S2 | Doğrudan ölçülmemiş her etki bir **aralık** olarak girer ve her Monte Carlo tekrarında bu aralıktan çekilir. Sonuç tek sayı değil, belirsizlik aralığıyla verilir. |
| S3 | Vücut yapısı dağılımı gerçek veriden gelir: ANSUR II erkek veri seti (indirilir, SHA-256 `0547aea0170e5293de519389981135e75803f02e6d40c77ace740decc0caac64` ile doğrulanır, repoya konmaz). Boy dağılımı Türk referansına ölçeklenir. |
| S4 | Gözlemci **genel bir kişidir:** ortalama boylu (Türk 17-18 yaş medyanı), zayıf yapılı (yapı indeksi −1 SD). Gerçek bir kişinin verisi kullanılmaz. |
| S5 | Sabit tohum 20261008, tek komut (`python calistir.py`), bütün sayılar `ciktilar/` altında. |
| S6 | **Şaşırtıcı sonuç önce hata sayılır.** |

## 4. Model

### 4.1 Kişiler

- Kohort: ANSUR II, 17-24 yaş erkek (n ≈ 1358). Her kişi için boy (mm), bideltoid genişlik (mm), kilo (kg).
- **Yapı indeksi (z_yapı):** Bideltoid genişlik ve kilonun, boya göre doğrusal regresyon artıklarının standartlaştırılmış ortalaması, yeniden standartlaştırılmış. Yani "boyuna göre ne kadar geniş ve iri". (Kaslılığı yağdan ayıramaz; sınırlama olarak yazılır.)
- **Genişlik indeksi (z_en):** Yalnız bideltoid artığı, standartlaştırılmış.
- Türk ölçeklemesi: boy = 175.8 + 6.3 · z_boy (cm). z_boy ANSUR'daki standartlaştırılmış boy.

### 4.2 Görünür boy (fiziksel katman)

```
G = boy + ayakkabı + saç − 1.3 · eğilme
```

| Bileşen | Dağılım | Sınıf |
|---|---|---|
| Ayakkabı (iki kişi arasındaki fark önemli) | Herkes için 2.5 cm + N(0, 0.8) cm | Ortalama ölçülmüş (ergonomi düzeltmesi); kişiler arası yayılım **varsayım** |
| Saç | U(0, 3) cm | **Varsayım** (erkek saçı için ölçüm yok) |
| Eğilme (0 = tam dik, 1 = gevşek) | Beta(2, 2), ortalaması μ_e − κ · z_yapı ile kaydırılır | 1.3 cm katsayısı ölçülmüş (Prushansky 2013); κ **varsayım** |
| κ (kaslı kişinin daha dik durma eğilimi) | Ana: 0. Varyant: her tekrarda U(0, 0.15) | **Varsayım** |

### 4.3 Algılanan boy (algı katmanı)

Bir gözlemcinin bir hedef için algıladığı boy:

```
A = G + β_güç · z_yapı + β_en · z_en + δ_gözlemci · [hedef gözlemciden iri] + ε
```

| Parametre | Her tekrarda çekiliş | Gerekçe |
|---|---|---|
| β_güç (güçlü görüneni büyük görme), cm / SD | U(0, 2) | Fessler çalışmalarında güçlü bir ipucu (silah, kısıtlanma) +1.3-3.6 cm. Kaslılık daha zayıf, görsel bir ipucu; ±1 SD arası fark 0-4 cm. **Çıkarım** |
| β_en (geniş olanı kısa görme), cm / SD | U(−1, 0) | Beck 2013: %19 genişlik farkı, boyun %7'sinden küçük yanılgı. Bideltoid ±1 SD ≈ %12 fark. **Çıkarım** |
| δ_gözlemci (kendini eksik hisseden gözlemcinin iri hedefi büyütmesi), cm | Ana katmanda 0; "kişisel" katmanda U(0, 2.4) | Duguid & Goncalo (güçsüz − kontrol ≈ +0.9 cm), Fessler & Holbrook (kısıtlanmış: +2.4 cm). **Çıkarım** |
| ε, yan yana karşılaştırma gürültüsü (iki kişinin farkı için SD) | σ_yan ~ U(2, 4) cm | Coury 2022: 4 cm farkta > %70, 1-3 cm'de şansa yakın. **Varsayım** |
| ε, ayrı zamanlarda görme (fark için SD) | σ_ayrı ~ U(5, 9) cm | Martynov 2020: tek kişide MAE 6.3 cm (SD ≈ 7.9); iki tahminin farkı daha da gürültülü, ama gözlemci kendini iyi tanır. **Varsayım** |

Karşılaştırma kararı: "Hedef benden uzun" ⇔ A_hedef − A_gözlemci_öz > 0. Gözlemcinin kendi boyu için öz-algı: gerçek görünür boyu + gürültü (ayrı zamanlarda) ya da aynı aynada/yan yana durum.

### 4.4 Çıktılar

**(a) Eşit boy testi.** Gerçek boyları aynı olan iki kişi: biri kaslı (z_yapı = +1, z_en = +1), biri zayıf (−1, −1). Tarafsız bir gözlemcinin kaslıyı daha uzun bulma olasılığı. Katmanlar ayrı ayrı açılarak:
- K0: yalnız gürültü;
- K1: + fiziksel katman (κ ana = 0, varyant > 0);
- K2: + algı katmanı (β_güç, β_en);
- K3: + kişisel katman (δ_gözlemci; gözlemci zayıf olanın kendisi).

**(b) Öznel eşitlik noktası (PSE).** Kaslı kişi zayıf gözlemciden kaç cm kısa olduğunda gözlemciye "aynı boyda" görünür? Her katmanın PSE'ye katkısı (cm) ve toplamı.

**(c) Bir haftalık gözlem.** Zayıf, ortalama boylu gözlemci bir haftada 100 akranla karşılaşır (Türk boy dağılımı, ANSUR yapı dağılımı; %50 yan yana, %50 ayrı zamanda görme; **varsayım**). Sayılır:
- "Gerçekte benden kısa ya da eşit ama daha uzun göründü" olayları;
- bunların kaçının kaslı (z_yapı > 0.5) kişilerde olduğu;
- **hatırlama yanlılığı:** kaslı kişideki olayın hatırlanma olasılığı m kat (m ~ U(1, 2); Unterhalter 2007 ve dikkat çalışmalarından yön, büyüklük **varsayım**). Hatırlanan olaylarda kaslıların payı.
- Karşılaştırma: aynı hafta, yanlılıksız bir gözlemci (yalnız K0 + K1).

### 4.5 Belirsizlik

R = 4000 Monte Carlo tekrarı. Her tekrarda parametreler aralıklarından çekilir; eşit boy olasılıkları her tekrarda 2000 karşılaştırmayla, haftalık gözlem her tekrarda bir hafta olarak hesaplanır. Raporlanan: medyan ve %5-%95.

## 5. Ön kayıtlı testler

| # | Test | Geçme ölçütü |
|---|---|---|
| **A1** | Veri bütünlüğü: ANSUR SHA-256 eşleşir; 17-24 yaş erkek sayısı ve r(boy, biakromiyal) bağımsız hesapla aynı | n = 1358; r = 0.508 ± 0.005 |
| **A2** | Sıfır kontrolü: bütün etkiler 0 iken eşit boylu iki kişide "kaslı daha uzun" olasılığı | 0.50 ± 0.01; PSE = 0 ± 0.05 cm |
| **A3** | Yön tutarlılığı: β_güç arttıkça olasılık artar, β_en daha negatif oldukça azalır (diğerleri sabit) | Kesin monoton |
| **A4** | Toplanabilirlik: katman PSE'lerinin toplamı, bütün katmanlar açıkken hesaplanan PSE'ye eşit | Fark < 0.1 cm |
| **A5** | Monte Carlo yakınsaması: ana olasılığın standart hatası | < 0.005 |

### Karar kuralları (yorum önceden sabit)

| # | Kural |
|---|---|
| K1 | Bir katmanın PSE katkısı (medyan): **< 0.5 cm** "ihmal edilebilir"; **0.5-2 cm** "küçük ama yan yana fark edilebilir"; **≥ 2 cm** "belirgin". |
| K2 | Bir katmanın %5-%95 aralığı sıfırı içeriyorsa "yönü belirsiz" diye yazılır. |
| K3 | "Herkes görür mü?" sorusu: K2 katmanının (algı) PSE katkısının medyanı ≥ 0.5 cm ve aralığı sıfırı içermiyorsa "evet, herkes için geçerli bir eğilim"; aralık sıfırı içeriyorsa "bilinmiyor, deney gerekli". |
| K4 | "Kişisel mi?" sorusu: K3 katmanı (kişisel) katkısı K2'ninkinden büyükse "gözlem büyük ölçüde gözlemciye özgü"; küçükse "büyük ölçüde herkes için geçerli"; aralıklar örtüşüyorsa "ikisi karışık". |
| K5 | Model bu soruyu kesin cevaplayamaz, çünkü merkezi etki (β_güç, β_en) doğrudan ölçülmemiştir. Raporda bunu çözecek bir **deney tasarımı** önerilir. |

## 6. Duyarlılık analizi

| Varsayım | Ana | Varyantlar |
|---|---|---|
| κ (kaslının dik durması) | 0 | U(0, 0.15) |
| Saç | U(0, 3) | 0 (herkes eşit) |
| β_güç aralığı | U(0, 2) | U(0, 1); U(1, 3) |
| β_en aralığı | U(−1, 0) | 0; U(−2, −1) |
| Haftalık karşılaşma sayısı | 100 | 30; 300 |
| Hatırlama çarpanı m | U(1, 2) | 1 (yanlılık yok); U(2, 3) |

## 7. Plandan sapmalar

| Tarih | Sapma | Gerekçe | Etkisi |
|---|---|---|---|
| 2026-10-08 | **Etiket düzeltmesi (kodda, sonuç görüldükten sonra):** Haftalık gözlemde karşılaştırma grubu "yanlılıksız gözlemci" diye adlandırılmıştı. Bu grupta algı katmanları kapalı, ama hatırlama yanlılığı (m) iki grupta da açık; plan 4.4(c) bunu ayırmamıştı. Etiket "algı yanlılığı yok (hatırlama yanlılığı açık)" olarak düzeltildi. Hatırlamanın tek başına etkisi duyarlılık analizindeki "m = 1" varyantından okunur. | Etiket, sayının anlamını yanlış anlatıyordu. | Hiçbir sayı değişmedi. |
