# Simülasyon Planı: Omuz, Göğüs, Bel Oranları ve Spor: Görünüşe Etkisi

> **Plan sürümü:** 1 · **Tarih:** 2026-10-09 · **Durum:** ön kayıt (kod yazılmadan ve çalıştırılmadan önce commit edildi)
>
> Bu dosya hiçbir simülasyon ya da veri analizi sonucu görülmeden yazıldı. Testler çalıştıktan sonra **ölçütler değiştirilmez.** Her değişiklik "Plandan sapmalar" tablosuna tarih ve gerekçesiyle yazılır.

## 1. Soru

Sürüm 1 "kaslı, kalıplı biri aynı boyda daha uzun görünür mü?" sorusunu genel bir "yapı" indeksiyle ele aldı. Bu sürüm vücudu parçalarına ayırıyor:

1. **Omuz genişliğinin ne kadarı iskelet, ne kadarı kas ve yağ?** İskelet sporla değişmez, kas değişir.
2. **Orantı:** Göğüs ve omzun bele oranı (V şekli) akranlar arasında nasıl dağılıyor? Aynı iskelette insanlar arasında ne kadar değişiyor?
3. **Spor bu oranları 12 ayda gerçekçi olarak ne kadar değiştirir?** Yağ kaybı ve kilo alma ile karşılaştırma.
4. **Algıya etkisi:** Bu değişim akranlar arasındaki sırayı (yüzdelik), güç izlenimini ve algılanan boyu ne kadar değiştirir?
5. **İskelet hâlâ büyüyor mu?** 17-24 yaş arasında omuz iskelet genişliği yaşla değişiyor mu?

**Kapsam dışı:** Antrenman programı yazmak; takviye; klinik değerlendirme.

**Benzetme:** Bir çadır düşün. Direkleri (iskelet) sabit; branda (kas ve yağ) değişebilir. Çadırın uzaktan nasıl göründüğü hem direklerin aralığına hem brandanın nereye gerildiğine bağlı. Bu plan önce direklerin ne kadarını, brandanın ne kadarını belirlediğini ölçer; sonra brandayı sporla değiştirmenin uzaktan görüntüyü ne kadar değiştirdiğini hesaplar.

## 2. Literatür (planı biçimlendiren bulgular)

| Konu | Bulgu | Kaynak |
|---|---|---|
| Güç ipuçları | Erkek vücut fotoğraflarında tahmin edilen güç, çekicilik puanlarının %70'inden fazlasını belirliyor; boy ve yağsızlıkla birlikte %80. Doğrusal: en güçlü en çekici, ters U görülmedi. | Sell ve ark. 2017 |
| Orta kaslılık | Kaslı erkekler daha çekici, baskın bulunuyor; ama en çekici bulunan **orta** düzey kaslılık (ters U). | Frederick & Haselton 2007 |
| Bel/göğüs oranı | Gerçek erkek görüntülerinde bel/göğüs oranı (WCR) çekiciliğin birincil belirleyicisi; BMI ikincil (Britanya, Yunanistan, kentsel Malezya). | Swami & Tovée 2005; Swami ve ark. 2007 |
| 3B tarama | Hacim-boy indeksi (VHI) ve WCR erkek vücut çekiciliğinin önemli belirleyicileri; VHI'nin bir optimumu var (çok zayıf ya da çok iri daha az çekici). | Fan ve ark. 2005; Price ve ark. 2013 |
| Neden | Düşük WCR'li (geniş göğüs, dar bel) erkekler daha baskın, daha formda ve "koruyabilir" algılanıyor; bunlar çekiciliğe aracılık ediyor. | Coy ve ark. 2014 |
| Kaslar ayrı ayrı | 1742 kişi: erkekler büyük üst vücut kaslarını daha çok tercih ediyor; kadınların tercihleri kısmen farklı. | Durkee ve ark. 2019 |
| Yanılgı | Erkekler kadınların beğendiği kaslılığı abartıyor; erkek dergilerindeki ideal, kadın dergilerindekinden daha kaslı. | Frederick ve ark. 2005; Lei & Perrett 2021 |
| Genişlik ve boy | Aynı boyda daha geniş vücut daha kısa algılanıyor; insan vücudunda etki dikdörtgenden güçlü. | Beck ve ark. 2013 |
| Antrenman | 8 haftalık direnç antrenmanı: göğüs çevresi +3.4 cm (haftada 2) ve +6.0 cm (haftada 4); kontrol +0.5 cm (genç erkekler, hafif antrenmanlı). 12 hafta: üst vücut kas kalınlığı +%12-21, alt vücut +%7-9. Kas kütlesi meta-analizi: ortalama +1.5 kg. | Arazi ve ark. 2021; Abe ve ark. 2000; Benito ve ark. 2020 |
| İskelet | Köprücük kemiğinin iç uç büyüme plağı erkekte ortalama 20.6 yaşında kaynaşmaya başlıyor, 21.9 yaşında tamamlanıyor (BT, n = 210 erkek). | Franklin & Flavel 2015 |
| Sürüm 1 | Algılanan boy modeli: güç etkisi 0-2 cm/SD, genişlik yanılgısı −1-0 cm/SD; yan yana görme gürültüsü 2-4 cm. | Bu araştırma, sürüm 1 |

**Bulunamayan:** Antrenmanın omuz (bideltoid) genişliğini ve omuz çevresini santimetre olarak nasıl değiştirdiğini ölçen bir çalışma; V şeklinin algılanan boya etkisini doğrudan ölçen bir çalışma.

## 3. Simülasyon kuralları

- **Gerçek veri:** ANSUR II erkek, 17-24 yaş, n = 1358 (sürüm 1 ile aynı dosya, SHA-256 `0547aea0…ac64`). Kişisel veri kullanılmaz.
- **Doğrudan ölçülmemiş her etki bir aralık olarak girer;** her Monte Carlo tekrarında aralıktan düzgün dağılımla çekilir. R = 4000 tekrar, sabit tohum 20261009.
- **Ölçek:** Bütün indeksler ANSUR 17-24 yaş içinde standartlaştırılır (z). Boy, sürüm 1'deki gibi Türk referansına ölçeklenmez; burada yalnız oranlar ve yüzdelikler kullanılır.
- **Kesitsel veri sınırı:** ANSUR'daki kişiler arası farklar, aynı kişinin zaman içindeki değişimi yerine kullanılıyor. Bu bir varsayımdır (D) ve duyarlılık analizinde değiştirilir.
- **Başlangıç profili:** Genel bir "zayıf yapılı genç": ANSUR medyan boy ve medyan iskelet genişliği, kas indeksi −1 SD, yağ indeksi 0. Gerçek bir kişinin ölçüsü kullanılmaz.

## 4. Model

### 4.1 Gerçek veri analizi (V)

| Kod | Analiz |
|---|---|
| V1 | **İskelet payı:** bideltoid (omuz kasları dahil en geniş yer) genişliğinin varyansının ne kadarı biakromiyal (iskelet) genişlik ve boyla açıklanıyor (R²)? Kalan pay = kas + yağ. |
| V2 | **Kas ve yağ indeksleri:** Yağ indeksi `z_yag` = bel çevresinin boy ve biakromiyal genişliğe göre artığı. Kas indeksi `z_kas` = göğüs çevresi, omuz çevresi, kasılı pazı çevresi ve kasılı ön kol çevresinin; boy, biakromiyal genişlik ve bel çevresine göre artıklarının ortalaması (sonra standartlaştırılır). |
| V3 | **Oranlar:** WCR = bel çevresi / göğüs çevresi; SWR = omuz çevresi / bel çevresi; dağılım ve yüzdelikler. |
| V4 | **Aynı iskelet, farklı görünüş:** Boy medyanın ±2 cm'si ve biakromiyal genişlik medyanın ±1 cm'si içindeki kişilerde WCR ve bideltoid genişliğinin %5-%95 aralığı. |
| V5 | **Yaş:** 17-24 yaş arasında biakromiyal genişliğin yaşa doğrusal eğimi ve %95 güven aralığı (kesitsel). |
| V6 | **Eşleme katsayıları:** Her ölçü (göğüs, omuz çevresi, bideltoid, bel çevresi, bel genişliği, kilo) için `ölçü ~ boy + biakromiyal + z_kas + z_yag` doğrusal regresyonu. Senaryolar bu katsayılarla ölçülere çevrilir. |

### 4.2 Senaryolar (12 ay; D)

| Kod | Senaryo | Girdi |
|---|---|---|
| S0 | Hiçbir şey | değişiklik yok |
| S1 | Direnç antrenmanı (yeni başlayan) | göğüs çevresi +3 … +8 cm (kas ekseni boyunca); yağ −1 … +1 kg |
| S2 | Antrenman + hafif yağ kaybı | S1 + yağ −1 … −3 kg |
| S3 | Antrenmansız kilo alma | kas 0; yağ +2 … +5 kg |
| S4 | Yalnız yağ kaybı | kas 0; yağ −1 … −3 kg |

- Göğüs aralığının gerekçesi: 8 haftada +3.4 ile +6.0 cm ölçülmüş (Arazi 2021); erken artışın bir kısmı sıvı olabilir, kazanç zamanla yavaşlar ve devamlılık kusursuz değildir. Bu yüzden 12 ay için 3-8 cm.
- Kas değişimi `Δz_kas = Δgöğüs / b_göğüs,kas` ile, yağ değişimi `Δz_yag = Δyağ_kg / b_kilo,yag` ile indekslere çevrilir. Diğer ölçüler V6 katsayılarıyla hesaplanır. Biakromiyal genişlik ve boy değişmez.

### 4.3 Algı çıktıları

1. **Yüzdelik:** Başlangıç ve 12 ay sonrası; WCR (düşük = daha V), SWR ve kas indeksi için ANSUR 17-24 akranları arasındaki sıra.
2. **Algılanan boy (cm):** Sürüm 1 modeli, ipuçları ayrıştırılarak:
   `ΔA = b_güç · Δz_kas + b_en · Δz_gen`
   - `z_gen`: önden görünen genişlik indeksi; bideltoid genişliği ve bel genişliğinin boya göre artıklarının ortalaması (standartlaştırılmış). Beck 2013 yanılgısı burada.
   - `b_güç` ∈ [0, 2] cm/SD ve `b_en` ∈ [−1, 0] cm/SD, sürüm 1 ile aynı aralıklar.
   - Sürüm 1'den fark: Güç ipucu artık kilo içermiyor; yalnız kas indeksi. Gerekçe: Sell 2017'ye göre yağsızlık ayrı ve olumlu bir ipucu.
3. **Karşılaştırma:** Sürüm 1'de ölçülen dik duruş etkisi (+1.3 cm, gerçek) ile karşılaştırılır.

### 4.4 Belirsizlik

Her tekrarda göğüs artışı, yağ değişimi, `b_güç` ve `b_en` çekilir. Raporlanan: medyan ve %5-%95.

## 5. Ön kayıtlı testler

| Test | Ne sınıyor | Geçme ölçütü |
|---|---|---|
| B1 | Veri bütünlüğü | SHA-256 eşleşir; n = 1358 |
| B2 | İndeks yapısı | `z_kas`, `z_yag` ortalaması |0| < 10⁻⁹, SD = 1 ± 10⁻⁹; \|r(z_kas, z_yag)\| < 0.05 |
| B3 | Eşleme | S1'de uygulanan göğüs artışı, V6 katsayılarıyla geri hesaplandığında aynı çıkar (fark < 10⁻⁹ cm) |
| B4 | Sıfır senaryosu | S0'da ΔA = 0 ve yüzdelikler değişmez |
| B5 | Yön | S3'te yağ arttıkça WCR yükselir (daha az V) ve ΔA azalır (kesin monoton, 5 nokta) |
| B6 | Monte Carlo hatası | S2'de ΔA medyanının bootstrap SE'si < 0.02 cm |

### Karar kuralları (yorum önceden sabit)

- **K1, "Spor V oranını belirgin değiştirir mi?":** S2'de WCR yüzdeliğindeki iyileşmenin medyanı ≥ 15 puansa "belirgin", 5-15 puansa "orta", < 5 puansa "küçük".
- **K2, "Algılanan boyu değiştirir mi?":** S2'de ΔA'nın %5-%95 aralığı tamamen 0'ın üstündeyse "biraz daha uzun gösterir"; 0'ı içeriyorsa "yönü belirsiz". Büyüklük: medyan < 1 cm "küçük", 1-2 cm "orta", > 2 cm "büyük".
- **K3, "Omuz genişliğinin çoğu iskelet mi?":** V1'de R² > 0.5 ise "çoğu iskelet", 0.3-0.5 "karışık", < 0.3 "çoğu yumuşak doku".
- **K4, "İskelet 17-24 arasında büyüyor mu?":** V5 eğiminin %95 aralığı 0'ın üstündeyse "kesitsel veride büyüme görülüyor"; değilse "görülmüyor". (Kesitsel veri; kesin kanıt değil.)

## 6. Duyarlılık analizi

| Varyant | Değişiklik |
|---|---|
| D1 | Güç etkisi güçlü: `b_güç` ∈ [1, 3] |
| D2 | Genişlik yanılgısı güçlü: `b_en` ∈ [−2, −1] |
| D3 | Antrenman omzu daha az genişletir: bideltoid katsayısı yarıya indirilir |
| D4 | Başlangıç profili ortalama yapılı (kas indeksi 0) |
| D5 | Göğüs artışı düşük: +1 … +3 cm (düzensiz antrenman) |

## 7. Plandan sapmalar

| Tarih | Sapma | Gerekçe |
|---|---|---|
| – | – | – |
