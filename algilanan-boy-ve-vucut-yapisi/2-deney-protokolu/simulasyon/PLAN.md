# Deney ve Simülasyon Planı: "Kaslı Vücut Daha Uzun mu Görünür?" Fotoğraf Deneyi

> **Plan sürümü:** 1 · **Tarih:** 2026-10-08 · **Durum:** ön kayıt (kod yazılmadan ve çalıştırılmadan önce commit edildi)
>
> Bu dosya iki şeyi önceden sabitler: (1) gerçek deneyin hipotezleri, tasarımı ve analizi; (2) bu analizin doğruluğunu ve deneyin gücünü sınayan simülasyon. Deney verisi toplanmadan ve simülasyon çalışmadan yazıldı. Ölçütler sonradan değiştirilmez; her değişiklik "Plandan sapmalar" tablosuna yazılır.

## 1. Soru ve hipotezler

Sürüm 1, merkezi soruyu cevaplayamadı: aynı gerçek boyda kaslı, kalıplı biri, zayıf birine göre daha uzun mu görünür? Bu deney bunu doğrudan ölçer.

| # | Hipotez | Test |
|---|---|---|
| **H1** (birincil) | Gerçek boy farkı sabitken, yapı indeksi yüksek olan kişi daha uzun algılanır. | PSE₂ ≠ 0 (iki yönlü, α = 0.05). PSE₂: yapı farkı 2 SD olan iki kişi için "aynı boyda görünme" noktası, cm. Pozitif = kalıplı daha uzun görünür. |
| **H2** (ikincil) | Bedeninden memnun olmayan değerlendiricilerde bu etki daha büyüktür. | Değerlendirici başına PSE₂'nin beden memnuniyeti puanıyla eğimi (iki yönlü). |
| **H3** (keşifsel) | Fotoğraflar tek tek gösterilip cm tahmini istendiğinde de aynı yönde kayma vardır. | Tahmin − gerçek boy, yapı indeksiyle regresyon. |

**Benzetme:** Tartıda iki kişi var. Biz gerçek ağırlıklarını (boylarını) biliyoruz. Kişiyi tanımayan 30 kişiye "hangisi ağır?" diye soruyoruz. Gerçek fark sabitken cevaplar kalıplının lehine kayıyorsa, terazinin "göz" eli gerçek.

## 2. Deney tasarımı (ön kayıt)

### 2.1 Katılımcılar

| Rol | Kim | Sayı |
|---|---|---|
| **Fotoğraflanan (hedef)** | 16-25 yaş erkekler. Yapıya göre **amaçlı seçim**: yarısı zayıf, yarısı kalıplı. Boylar mümkün olduğunca dar bir aralıkta (ör. 170-182 cm), çünkü karşılaştırma ancak boylar yakınsa bilgi verir. | Güç analizinden (bölüm 5); en az bölüm 5'te önerilen sayı |
| **Değerlendirici** | Hedefleri tanımayan, 16 yaş ve üstü herkes. | Güç analizinden |

18 yaş altı her katılımcı için **veli onayı** ve katılımcının kendi onayı alınır. Fotoğraflar kişisel veridir: yüzler bulanıklaştırılır, dosyalar yalnız araştırma ekibinde kalır, yayımlanmaz, analiz bitince silinir. Yalnız kimliksiz, toplu sonuçlar paylaşılır. Okulda yapılacaksa okul yönetiminin izni alınır.

### 2.2 Ölçümler (hedefler)

| Ölçü | Yöntem |
|---|---|
| Boy | Ayakkabısız, duvara yaslanmış, başın üstüne dik açılı düz bir cisim (kitap); 3 ölçümün ortalaması; aynı gün, aynı saat aralığı. 0.5 cm hassasiyet. |
| Omuz genişliği (bideltoid) | Standart fotoğraftan, kalibrasyon cetveliyle piksel → cm. Yapı ölçüsünün ana bileşeni. |
| Kilo | Aynı tartı, hafif giysi. |
| Yapı indeksi z_yapı | Omuz genişliği ve kilonun boya göre doğrusal regresyon artıklarının standartlaştırılmış ortalaması (sürüm 1 ile aynı tanım), deney örneğinde hesaplanır. |

### 2.3 Fotoğraf standardı

- Düz, açık renkli arka plan; arka planda **boy ipucu yok** (kapı, çizgi, eşya yok).
- Kamera: her hedef için aynı mesafe (3 m), aynı yükseklik (yerden 100 cm), aynı yakınlaştırma; tripod.
- Hedef: ayakkabısız ya da aynı tip ince çorapla; dik duruş, kollar yanda, karşıya bakış.
- Giysi: aynı tip düz tişört ve koyu eşofman altı (giysi farkı yapı algısını değiştirmesin).
- Saç: ölçüm saçın üstünden değil kafa tepesinden; fotoğrafta saç olduğu gibi kalır (gerçek hayatta da öyle). Saç yüksekliği ayrıca not edilir (keşifsel).
- Yüz bulanıklaştırılır (yüz ipuçları algılanan boyu etkileyebilir: Re 2013).
- Her fotoğrafta zemin hizasında bir kalibrasyon cetveli; görsel hazırlanırken kırpılır.

### 2.4 Uyaranların hazırlanması

- Bütün fotoğraflar **aynı ölçeğe** getirilir (1 cm = aynı piksel). Böylece gerçek boy farkı görüntüde korunur.
- **Çift görevi (H1, H2):** İki hedef yan yana, ayaklar aynı zemin çizgisinde, arka plan aynı. Soru: "Hangisi daha uzun?" (iki seçenekli zorunlu seçim). Sol-sağ yerleşimi her çiftte rastgele.
- Çift seçimi: gerçek boy farkı ≤ 6 cm olan bütün çiftler; yetmezse en yakın farklar. Her değerlendirici K = 60 çift görür (yaklaşık 6-8 dakika).
- **Tek görev (H3, keşifsel):** Her hedef tek başına, ölçek ipucu olmadan; "Bu kişi kaç cm?" tahmini.
- Değerlendirici, görevden **sonra** kısa bir beden memnuniyeti sorusu cevaplar (H2). Önce sorulursa beden düşüncesi tetiklenip cevapları etkileyebilir.

### 2.5 Analiz (ön kayıt)

**Neden iki aşama:** Etkinin tekrar birimi **hedef kişidir.** Değerlendiriciler binlerce yanıt üretir ama hepsi aynı 20-30 kişiye bakar. Bir hedefin yapıyla ilgisiz bir nedenle (saç, duruş, yüz) uzun görünmesi, her değerlendiricide tekrar eder. Yanıtları bağımsız saymak sahte "anlamlı" sonuç üretir. Bu yüzden:

1. **Aşama 1, algılanan boy ölçeği:** Bütün yanıtlarla bir probit modeli kurulur: P(A uzun) = Φ(s_A − s_B). s_i, hedef i'nin "algılanan boy" değeridir (Thurstone ölçeklemesi; ortalaması 0'a sabitlenir).
2. **Aşama 2, hedef düzeyinde regresyon:** s_i = a + b · boy_i + c · z_yapı_i + e_i (sıradan en küçük kareler; n = hedef sayısı).
3. **PSE₂ = 2c / b** (cm). %95 güven aralığı: hedefler üzerinden 2000 tekrarlı yüzdelik bootstrap (aşama 2). H1: aralık 0'ı içermiyorsa reddedilir.
4. **H2:** Her değerlendirici için aşama 1-2 ayrı ayrı (değerlendirici başına PSE₂, gürültülü); bu değerlerin beden memnuniyeti puanına regresyonu.
5. **Kontrol:** b > 0 olmalı (gerçek boy algıyı artırmalı). b'nin aralığı 0'ı içeriyorsa uyaranlar boy farkını göstermiyor demektir; deney geçersiz sayılır.

## 3. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Sentetik veri, analiz kodundan **bağımsız** bir üreteçle üretilir; analiz kodu gerçek veride de aynen kullanılır. |
| S2 | Hedef özellikleri gerçek veriden: yapı indeksi ANSUR II'den (sürüm 1'deki tanımla, 17-24 yaş erkek), boy Türk referansından (175.8 ± 6.3 cm). Amaçlı seçimde yapı indeksinin alt ve üst %30'undan eşit sayıda hedef çekilir ve boylar 170-182 cm aralığıyla sınırlanır. |
| S3 | Sabit tohum 20261009, tek komut (`python calistir.py`), bütün sayılar `ciktilar/` altında. |
| S4 | **Şaşırtıcı sonuç önce hata sayılır.** |

## 4. Sentetik veri modeli

Değerlendirici r, çift (A, B) için:

```
D = (H_A − H_B) + (β + u_r) · (z_A − z_B) + (t_A − t_B) + ε,   ε ~ N(0, σ_r²)
"A uzun" ⇔ D > 0
```

| Terim | Anlamı | Değer |
|---|---|---|
| β | Gerçek yapı etkisi, cm / SD. PSE₂ = 2β | Izgara: PSE₂ ∈ {0, 1, 2, 3} cm |
| u_r | Değerlendiriciye özgü sapma | N(0, 0.25²) cm / SD (**varsayım**) |
| t_i | Hedefe özgü, yapıyla ilgisiz görünüş farkı (saç, duruş, yüz) | N(0, τ²), τ = 1.0 cm; duyarlılık 0.5 ve 2.0 (**varsayım**) |
| σ_r | Değerlendiricinin yan yana karşılaştırma gürültüsü | U(2, 4) cm (sürüm 1 ile aynı; **varsayım**) |

## 5. Güç analizi

Izgara: hedef sayısı N ∈ {10, 16, 20, 30, 40}; değerlendirici sayısı R ∈ {15, 30, 50}; K = 60 çift; hedef seçimi ∈ {amaçlı, rastgele}; gerçek PSE₂ ∈ {0, 1, 2, 3} cm. Her hücrede 300 sentetik deney. Güç = H1'in reddedilme oranı.

**Önerilen tasarım kuralı (önceden sabit):** Amaçlı seçimle, PSE₂ = 2 cm için gücü ≥ %80 olan en küçük N; bu N için gücü ≥ %80 olan en küçük R. (PSE₂ = 2 cm, sürüm 1'deki toplam etkinin merkezi tahmini.) Hiçbir hücre %80'e ulaşmazsa bu raporda açıkça yazılır.

## 6. Ön kayıtlı testler

| # | Test | Geçme ölçütü |
|---|---|---|
| **D1** | Yansızlık: büyük sentetik deney (N = 40, R = 200), gerçek PSE₂ = 2 cm; 100 tekrarın ortalama tahmini | Ortalama tahmin 2 ± 0.2 cm |
| **D2** | Yanlış alarm: önerilen tasarımda gerçek PSE₂ = 0 iken H1'in reddedilme oranı (500 tekrar) | %2.5 - %8 |
| **D3** | Kapsama: önerilen tasarımda, PSE₂ = 2 cm iken %95 aralığın gerçeği içerme oranı (500 tekrar) | %90 - %98 |
| **D4** | Tasarım dengesi: çift üreticisinde her hedefin gösterilme sayısı ve sol-sağ dengesi (R = 30) | Gösterilme sayısı en çok/en az oranı ≤ 1.5; "solda" oranı 0.50 ± 0.03 |
| **D5** | Hedef düzeyindeki analizin gerekliliği: aynı veride yanıtları bağımsız sayan naif analizin (yanıt düzeyinde probit, gerçek PSE₂ = 0, τ = 1) yanlış alarm oranı | Raporlanır; D2'den belirgin yüksek olması **beklenir** (iki aşamalı analizin gerekçesi). Geçme ölçütü değil, gösterim. |

### Karar kuralları (gerçek deney için, önceden sabit)

| # | Kural |
|---|---|
| K1 | Kontrol (2.5-5) başarısızsa sonuç yorumlanmaz; uyaranlar düzeltilip deney tekrarlanır. |
| K2 | PSE₂'nin %95 aralığı tamamen 0'ın üstündeyse: "kalıplı vücut aynı boyda daha uzun algılanıyor"; tamamen altındaysa: "daha kısa algılanıyor"; 0'ı içeriyorsa: "bu örneklemle fark gösterilemedi" (yokluğu kanıtlamaz). |
| K3 | PSE₂ büyüklüğü sürüm 1'in kararlarıyla aynı eşiklerle sınıflanır: < 0.5 cm ihmal edilebilir; 0.5-2 cm küçük; ≥ 2 cm belirgin. |
| K4 | Sonuç ne olursa olsun yayımlanır; yalnız kimliksiz, toplu sayılar. |

## 7. Plandan sapmalar

| Tarih | Sapma | Gerekçe | Etkisi |
|---|---|---|---|
| 2026-10-08 | **Hız ayarı:** `calistir.py` paralel işlemlerde matris kütüphanesi iş parçacıklarını 1'e sabitliyor (`OMP_NUM_THREADS=1` vb.). İlk çalıştırma 4 işlem × çok iş parçacığı çekişmesi yüzünden ~25 dakikada bitmedi ve durduruldu; aynı kodla tek iş parçacığıyla yeniden çalıştırıldı. | Yalnız hız. | Sabit tohumlar aynı; sonuçlar değişmez. |
| 2026-10-08 | **Keşifsel ek (ön kayıtlı değil):** Bölüm 5 kuralı en küçük tasarımı seçti: N = 10, R = 30 (PSE₂ = 2 cm için güç %81). Duyarlılık analizinde hedefe özgü görünüş farkı τ = 2 cm iken bu tasarımın gücü %36'ya düştü. `kesifsel_tau.py`, τ = 2 cm için N ∈ {10, 20, 30, 40} (R = 30) gücünü hesapladı. | Ön kayıtlı öneri, bilinmeyen bir varsayıma (τ) karşı kırılgan çıktı. | Ön kayıtlı öneri (N = 10) "asgari tasarım" olarak korunur. Protokolde ayrıca "pratik öneri" verilir: τ = 2 cm'de de güç ≥ %80 olan en küçük N (R = 30). Açıkça keşifsel etiketlidir. |
