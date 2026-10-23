# Çekicilik ve Sohbet · Sürüm 3: Ortalama Boydan Sonra Ne Önemli? Boy mu, Fizik mi, Zekâ mı?

> **Sürüm:** 3 · **Tarih:** 2026-10-23 · **Durum:** taslak
>
> Bu doküman **tıbbi tavsiye değildir.** İlişki tavsiyesi de değildir; araştırmaların ortalama olarak ne bulduğunu anlatır.
>
> Bu taslak, **analiz kodu yazılmadan önce** commit edilen ön kayıttır. Rapor bölümleri analizden sonra eklenecek.

**Kanıt seviyeleri:**

| Etiket | Anlamı |
|---|---|
| **A** | Meta-analiz ya da birden çok büyük, bağımsız çalışma |
| **B** | Tek büyük, iyi tasarlanmış çalışma |
| **C** | Küçük çalışma, vaka serisi, ikincil kaynak |
| **V** | Bu çalışmanın kendi gerçek veri analizi |
| **D** | Model ya da varsayım |

---

## Soru ve kapsam

Ortalama boya ulaşmış bir erkek için:

1. **Ek boy** mu, daha **çekici görünüş ve fizik** mi, **zekâ** mı, **kişilik** mi, **statü** mü daha çok fark yaratıyor?
2. Boyun etkisi ortalamanın üstünde **azalıyor** mu (eşik, plato)?
3. **Kadının kendi boyu**, erkeğin boyuna verdiği önemi değiştiriyor mu?
4. Özellikler birbirini **telafi** ediyor mu, yoksa önce bir **eşik** mi aşılmalı?
5. **Gerçek hayat sonuçlarında** (partner sayısı, ilişki, evlilik, çocuk) sıralama aynı mı?
6. **Türkiye'de** bir şey değişiyor mu?

**Kapsam:** Kadınların erkekleri seçmesi (soruyu soran kişi erkek). Heteroseksüel örneklemler.
**Kapsam dışı:** Boy uzatma yöntemleri (ayrı konu: [boy-potansiyeli-gozden-kacanlar](../../boy-potansiyeli-gozden-kacanlar/)); belirli bir kişiye tavsiye; 18 yaş altı katılımcılarla deney.

## Yöntem

### 1. Literatür (çok ajanlı tarama)

Dört aşama, her aşamada koordinatör (bu raporu yazan) sonuçları kontrol ediyor:

1. **Tarama.** On paralel ajan:
   - L1 boy eğrisi ve eşik;
   - L2 beden ipuçları (omuz-kalça, kas, güç);
   - L3 yüz ve değiştirilebilir görünüm;
   - L4 zekâ ve eğitim;
   - L5 statü, gelir, hırs;
   - L6 kişilik ("zorunluluk ve lüks");
   - L7 gerçek hayat sonuçları;
   - L8 özellikler nasıl birleşiyor (telafi ve eşik);
   - L9 Türkiye ve kültürlerarası farklar;
   - D1 açık veri keşfi.

   Kural: sayılar mümkünse tam metinden okunur; okunamayan her sayı `[doğrulanmadı]` diye işaretlenir.
2. **Kendi analiz** (aşağıda, bölüm 2).
3. **Çapraz doğrulama.** Rapora girecek kilit sayılar, onları bulan ajandan bağımsız ajanlarca birincil kaynaktan yeniden kontrol edilir. Ayrıca bir "şeytanın avukatı" ajanı ana sonuçları çürütmeye çalışır.
4. **Rapor.** Doğrulanamayan sayı Sonuçlar bölümüne girmez.

### 2. Gerçek veri (V)

Üç açık veri seti. Hiçbiri repoya kopyalanmaz: kod indirir, SHA-256 doğrular, `.veri/` altında tutar.

| Kod | Veri | Ne var | İndirme |
|---|---|---|---|
| UvA | Witmer ve ark. 2025, *Computers in Human Behavior Reports* (Amsterdam Üniversitesi; OSF jmgya), kadın katılımcı dosyası | 224 Alman kadın (18-35). Her biri 12 kez 3 erkek profili arasından birini seçiyor ya da hiçbirini seçmiyor: 8.064 profil kararı. Profillerde 5 özellik birbirinden bağımsız rastgele atanmış: fotoğraf çekiciliği (28 fotoğraf, önceden puanlanmış), boy (170-189 cm), IQ (80-120), biyografi, meslek prestiji. Kadının kendi boyu da kayıtlı | `https://osf.io/download/84abw/`, SHA-256 `e8de84b6…0c3205` |
| MA | Mautz ve ark. 2013, *PNAS*, ham veri (Aich ve ark. 2026, *PLOS Biology* ek dosyası S1) | 105 kadın, gerçek boyutta yansıtılan 343 bilgisayar figüründen 49'ar tanesini 1-7 puanlıyor (5.145 puan). Figürlerde boy (±2 SS, 7 düzey), omuz-kalça oranı ve penis boyu birbirinden bağımsız. Puanlayan kadının boyu kayıtlı | PLOS ek dosyası `pbio.3003595.s003`, SHA-256 `f4e0e38b…942925` |
| KO | Kordsmeyer ve ark. 2018, *Evolution and Human Behavior* (Mendeley, CC BY 4.0) | 164 heteroseksüel Alman erkek. Ölçülmüş boy, el kavrama ve üst beden kuvveti; kadınların yüz ve beden çekiciliği puanları; son 12 ay / yaşam boyu partner davranışı (SOI-R davranış); ilişki durumu | Mendeley `4bwxnwhwd3`, SHA-256 `7a8630b8…e7d93a` |

**Ortak istatistik:** Kişi içi doğrusal model. Her kadının kendi ortalaması çıkarılır (kadının genel seçiciliği sabitlenir). %95 aralık: puanlayan kadınlar (KO'da erkekler) üzerinden 2000 bootstrap, tohum 20261023.

**Birimler (karşılaştırma için):**
- **Boy:** cm başına; senaryoda **+5 cm**.
- **Çekicilik:** fotoğraf havuzunun **1 SS**'si.
- **IQ:** **15 puan** (nüfusta 1 SS).
- **Biyografi ve meslek:** profil havuzunun 1 SS'si.

**"Ortalama" noktaları (kırılma noktaları):**
- **Boy 180 cm:** genç Alman erkek ortalamasına yakın, aynı zamanda tasarım aralığının ortası.
- **IQ 100.**
- **Çekicilik:** fotoğraf havuzunun ortalaması.

Parçalı doğrusal terim: `alt = min(x − kırılma, 0)`, `üst = max(x − kırılma, 0)`. "Üst" katsayısı, ortalamanın üstündeki eğimdir.

| Kod | Veri | Analiz | Kör mü? |
|---|---|---|---|
| U1 | UvA | seçildi × 100 ~ çekicilik (parçalı) + boy (parçalı) + IQ (parçalı) + biyografi + meslek; kişi içi | **Hayır** (bölüm 5) |
| U2 | UvA | Doğrusal U1 + **boy × kadının kendi boyu** | Evet |
| U3 | UvA | Doğrusal U1 + **boy × çekicilik** + **IQ × çekicilik** (telafi mi, çarpım mı?) | Evet |
| U4 | UvA | Sağlamlık: U1-U3'ün koşullu logit karşılığı. Bir profilin 3'lü sette seçilme olasılığı; seçim yapılan setler; aynı terimler. Ölçek etkisini (olasılık mı, log-odds mu) ayırmak için | — |
| M1 | MA | puan ~ omuz-kalça (doğrusal + kare) + penis (doğrusal + kare) + boy (parçalı, 0'da kırılma); kişi içi | **Hayır** (bölüm 5) |
| M2 | MA | Doğrusal ve kare boy ile M1 + **boy × puanlayanın boyu** (U2'nin bağımsız tekrarı) | Evet |
| M3 | MA | M2 + **boy × omuz-kalça** | Evet |
| G1 | KO | SOI-R davranış ~ boy + yüz çekiciliği + beden çekiciliği + el kavrama/üst beden kuvveti + yaş (hepsi z-puanı); en küçük kareler | **Hayır** (bölüm 5) · keşif |
| G2 | KO | İlişkide olmak (0/1) × 100 ~ aynı yordayıcılar | Evet · keşif |

**Türetilen senaryo (U1'den, betimsel):** 180 cm, ortalama çekicilikte ve IQ 100 olan bir profil için şu değişikliklerin her birinin seçilme olasılığına etkisi (yüzde puan):
- +5 cm boy;
- +1 SS çekicilik;
- +15 IQ;
- +1 SS biyografi;
- +1 SS meslek.

### 3. Teknik testler (geçme ölçütüyle)

| Test | Ölçüt |
|---|---|
| T1 | Üç dosyanın da SHA-256 özeti yukarıdakiyle aynı |
| T2 | UvA: 224 kadın × 36 satır; her 3'lü sette en fazla 1 seçim |
| T3 | UvA rastgeleleştirme: 5 profil özelliği arasındaki korelasyonların mutlak en büyüğü < 0.05 |
| T4 | Kişi içi merkezleme doğru: merkezlenmiş sonucun kişi ortalamalarının mutlak en büyüğü < 1e-9 (UvA ve MA) |
| T5 | Kodlama kontrolü: UvA'da çekiciliğin doğrusal katsayısı ve MA'da omuz-kalça doğrusal katsayısı, aralık alt sınırı > 0 |
| T6 | MA: 105 kadın × 49 puan, figür boyu 7 düzey. KO: 164 satır, boy 150-210 cm arasında |
| T7 | U4 koşullu logit yakınsadı: gradyan normu < 1e-6 |

### 4. Karar kuralları

"Aralık" = %95 bootstrap aralığı. **Fark** sütunundaki büyüklükler aynı modelden ve aynı bootstrap örneklerinden hesaplanır.

| Kural | Soru | Karar |
|---|---|---|
| K1 | Ortalamanın üstünde **+1 SS çekicilik** mi, **+5 cm boy** mu daha değerli? (U1; fark = çekicilik_üst − 5 × boy_üst) | Alt sınır > 0 → "çekicilik"; üst sınır < 0 → "boy"; 0'ı içerirse → "ayırt edilemiyor" |
| K2 | Ortalamanın üstünde **+15 IQ** mı, **+5 cm boy** mu? (U1; fark = 15 × IQ_üst − 5 × boy_üst) | Aynı biçimde: "IQ" / "boy" / "ayırt edilemiyor" |
| K3 | Boyun getirisi ortalamanın üstünde azalıyor mu? (U1; fark = boy_alt − boy_üst) | Alt sınır > 0 → "azalıyor"; üst sınır < 0 → "artıyor"; 0'ı içerirse → "fark gösterilemedi". Ayrıca boy_üst aralığı 0'ı içeriyorsa → "180 cm üstünde belirgin etki yok" |
| K4 | IQ'nun getirisi 100'ün üstünde azalıyor mu? (U1; IQ_alt − IQ_üst) | K3 ile aynı |
| K5 | Çekiciliğin getirisi ortalamanın üstünde değişiyor mu? (U1; çekicilik_üst − çekicilik_alt) | Alt sınır > 0 → "üstte daha dik"; üst sınır < 0 → "üstte azalıyor"; 0'ı içerirse → "fark gösterilemedi" |
| K6 | Uzun kadınlar boya daha çok mu önem veriyor? (U2; boy × kendi boyu) | Alt sınır > 0 → "evet"; üst sınır < 0 → "tersine"; 0'ı içerirse → "gösterilemedi" |
| K7 | K6 bağımsız veride tekrarlanıyor mu? (M2; boy × puanlayanın boyu) | K6 ile aynı kural. İkisi de "evet" → "tekrarlandı" |
| K8 | Boy, çekici profillerde mi daha çok işe yarıyor, yoksa çekici olmayanlarda telafi mi ediyor? (U3; boy × çekicilik) | Alt sınır > 0 → "çarpımsal: çekicilikle birlikte artıyor"; üst sınır < 0 → "telafi edici"; 0'ı içerirse → "toplanıyor (etkileşim yok)" |
| K9 | IQ için aynı soru (U3; IQ × çekicilik) | K8 ile aynı |
| K10 | Beden şekli iyiyken boy daha mı önemli? (M3; boy × omuz-kalça) | K8 ile aynı |
| K11 | Ölçek denetimi: K3-K10'da "fark gösterilemedi / toplanıyor" dışındaki her karar için U4 (koşullu logit) aynı işareti veriyor mu? | Aynı işaret ve aralık 0'ı dışlıyor → "sağlam"; değilse karar "ölçeğe bağlı" etiketi alır |
| K12 | Gerçek davranışta (KO) hangi özellik öne çıkıyor? (G1, G2; keşif) | Her yordayıcı için: aralık 0'ı dışlıyorsa yön bildirilir. Ayrıca yüz − boy ve beden − boy farklarının aralıkları. Örneklem küçük (n=164); "belirgin değil" sonucu "etki yok" diye okunmayacak |

**Literatürden beklenen yön** (karar kuralını değiştirmez):
- **K1:** çekicilik, çünkü birinci aşama raporlarına göre fotoğraf çekiciliğinin etkisi boyunkinin 7-20 katı.
- **K3:** azalıyor.
- **K6/K7:** evet (kendinden uzun erkek normu).
- **K8:** belirsiz. Eşik modeli (Li 2002, Conroy-Beam) çarpımsal etkiyi, Hitsch'in gelir-boy takası telafi edici etkiyi öngörüyor.

### 5. Şeffaflık notu (bu analiz tam kör değil)

Ön kayıttan **önce** aşağıdakiler görüldü. Birinci aşamadaki ajanlar veri setlerini tanımak için hızlı analizler yaptı ve bunlar koordinatöre raporlandı:

- **UvA:**
  - Havuzlanmış logit katsayıları (SS başına): çekicilik 0.77, IQ 0.13, biyografi 0.13, boy 0.07, meslek 0.03.
  - 5 cm'lik boy gruplarında seçilme oranları: %17.1, %19.8, %19.6, %20.5.
  - Bu yüzden **U1, K1, K2 ve K3 kör değil.**
  - Ayrıca yayımlanmış makale ana etkileri, cinsiyet etkileşimlerini ve "benzerlik" (|fark|) terimlerini raporluyor. Benzerlik sonuçları koordinatör tarafından görülmedi.
- **MA:**
  - Boy düzeylerine göre ortalama puanlar (163→175 cm: +0.51 puan; 175→187: +0.25; 183→187: ≈0).
  - Çevrimiçi puanlarda boyun açıkladığı varyans.
  - Bu yüzden **M1 kör değil.** Mautz 2013 boy × penis etkileşimini raporluyor; boy × omuz-kalça (M3) ve boy × puanlayanın boyu (M2) koordinatör tarafından görülmedi.
- **KO:**
  - SOI davranış ~ boy 0.02, kuvvet 0.02, üst beden 0.28, yüz çekiciliği 0.20.
  - Video çekiciliği regresyonu.
  - Yayımlanmış makale de benzer yapısal modeller raporluyor. Bu yüzden **G1 kör değil**; G2 (ilişki durumu) görülmedi.
- **Bakılmadan yalnızca yapısı incelenenler:** sütun adları, düzey sayıları, satır sayıları, profil özellikleri arası korelasyonlar (T3; en büyük |r| 0.015 görüldü) ve 3'lü setlerdeki seçim sayısı dağılımı.

**Kör analizler:** U2, U3, M2, M3, G2 ve kurallar K4-K10.

### Plandan sapmalar

| Sapma | Gerekçe |
|---|---|
| (henüz yok) | |
