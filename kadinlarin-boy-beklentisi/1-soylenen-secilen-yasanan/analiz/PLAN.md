# Ön kayıt: Kadınların boy beklentisi — söylenen, seçilen, yaşanan

> **Durum:** Bu plan, aşağıdaki analizler **çalıştırılmadan önce** yazıldı ve commit edildi. Sonuçlar görüldükten sonra değiştirilmeyecek; her değişiklik "Plandan sapmalar" bölümüne tarih ve gerekçeyle eklenecek.
>
> **Tarih:** 2026-10-31

## Soru

Gerçek kadınlar partnerde hangi boyu bekliyor, bu beklenti gerçek seçime ve gerçek birlikteliğe ne kadar yansıyor? Özellikle: Türkiye'de 176 cm ve 178 cm bir erkek bu dağılımlarda nerede duruyor, 176 → 178 cm farkı ne kadar şey değiştiriyor?

Üç katman ayrı ayrı ölçülecek, çünkü literatür bunların birbirinden farklı olabildiğini gösteriyor:

1. **Söylenen:** Kadınların anketle beyan ettiği tercih edilen partner boyu.
2. **Seçilen:** Boyu rastgele atanmış profiller arasında gerçek seçim davranışı.
3. **Yaşanan:** Ölçülmüş boylarla gerçek çiftler ve erkeklerin partnerle yaşama oranı.

## Veri

| Kod | Veri | Ne içeriyor | Erişim |
|---|---|---|---|
| PI | Pisanski ve ark. 2022, OSF ah97w `Dataset.xlsx` (SHA-256 `312e65b3…40e0`) | 4 ülke, ~333 kadın; kendi boyu + tercih edilen partner boyu (5 basamaklı silüet: 165-170-175-180-185 cm), uzun/kısa süreli bağlam | Serbest |
| UV | Witmer ve ark. 2025, OSF 84abw (UvA seçim deneyi; sürüm 3'te kullanıldı) | 224 kadın, profil boyu 170-189 cm rastgele, kendi boyu | Serbest |
| SL | Sleiman, Melios ve Dolan 2025, Dataverse G1H0UA `cjoint_wide.dta` (CC0) | ~1.250 kadın × 16 ikili seçim; erkek profil boyu 5'8" (172,7) / 6'0" (182,9) rastgele; kendi boyu | Serbest |
| BR | IBGE POF 2008-09 (Brezilya), `Dados_20231009.zip` (SHA-256 `cc2d5279…a265`), kişi dosyası `T_MORADOR_S` | ~190 bin kişi, **ölçülmüş** boy (V0434), hane ve aile içi konum, yaş, eğitim, ağırlık | Serbest, kamu verisi |
| TR | TBSA 2017, 19-30 yaş, stadiometre (L4 raporundan) | Kadın 160,5 ± 6,62; erkek 174,7 ± 6,88 cm | Yayımlanmış özet |

**Gizlilik:** SL dosyasında IP adresi ve konum sütunları var. Kod dosyayı indirir, yalnız gerekli sütunları alır, ham dosyayı siler; IP/konum hiçbir çıktıya yazılmaz.

**Türkiye notu:** Türk kadınlarının partner boyu tercihi hiçbir yerde ölçülmemiş (L4 taraması). Türkiye için her sonuç, başka ülkelerdeki ilişkinin Türk boy dağılımına **aktarılmasıdır** ve öyle etiketlenecek.

## Önceden bilinenler (körlük beyanı)

- **UV** sürüm 3'te analiz edildi: 7 cm boy +1,2 yp; boyun etkisi kadının boyuna göre değişiyor. UV'deki testler bu yüzden **kör değil.**
- **BR**'de veri keşif ajanı (L5) şunları raporladı: 30.071 çift, eşler arası r = 0,368, kadının uzun olduğu çift oranı %6,98. Çift testleri (T3, H7) bu yüzden **kör değil.** Erkeklerin partnerle yaşama oranının boya göre değişimi (H6) **hiç bakılmadı.**
- **PI**: L5 ajanı ortalama tercih − kendi boy = +15 cm, r = 0,35 ve %35 tavan raporladı. Aralıklı modelin sonuçlarına bakılmadı.
- **SL**: Yayımlanmış marjinal olasılıklar (kadınlar: kısa 0,382, uzun 0,435) biliniyor ve kodlama kontrolü (T1) olarak kullanılacak. Kendi boy etkileşimi ve diğer özelliklerle karşılaştırma **bakılmadı.**

## Analizler

### A. Söylenen (PI)

- **A1.** Uzun süreli bağlamda kadınlar. Tercih edilen boy aralıklı normal regresyonla modellenir: seçilen silüet c ise gerçek tercih [c − 2,5, c + 2,5) aralığında; 165 seçimi (−∞, 167,5), 185 seçimi [182,5, ∞) olarak alınır. Model: tercih = a + b · (kendi boy − 165) + ülke etkisi + hata, hata ~ N(0, s²). Ülke etkileri sabit; Türkiye tahmini için ülkelerin eşit ağırlıklı ortalaması kullanılır.
- **A2.** Türk kadın dağılımına aktarım: kendi boy ~ N(160,5; 6,62). Her kadın için tercih ~ N(a + b(kendi − 165), s²). Çıktı: tercihi ≤ 176 ve ≤ 178 olan kadın oranı; medyan tercih. Duyarlılık: İstanbul üniversiteli kadınlar N(164,3; 5,9), ülke ülke ayrı tahmin, kısa süreli bağlam.
- **A3.** Literatürden parametre modeli (karşılaştırma için): Stulp, Buunk ve Pollet 2013 (en az kabul edilen fark +3,72 ± 5,54; istenen fark +13,45 ± 5,61 cm). Türk kadın dağılımında: erkeğin boyu, kadının "en az" sınırını geçiyor mu / "istenen" düzeyine ulaşıyor mu? Fark kadının boyundan bağımsız varsayılır (eğim 1); duyarlılık: A1'den gelen eğim.

### B. Seçilen

- **B1 (UV).** Kadın içi doğrusal olasılık modeli: seçildi ~ profil boyu (175, 180 ve 185 cm'de düğümlü doğrusal parça) + diğer profil özellikleri (çekicilik, zekâ, biyografi, meslek); kadın sabit etkisi. Çıktı: Δ(176→178), Δ(176→180), Δ(176→185) yüzde puan, kadına göre küme bootstrap (2.000 tekrar, tohum 20261031).
- **B2 (UV).** Aynısı, profil boyu yerine **göreli boy** (profil − kadının boyu) ile: 160,5 cm'lik kadın için Δ(176→178).
- **B3 (SL).** Kadın katılımcılar, erkek profil setleri. Her görev için iki profil, 7 ikili özellik (parti, ırk, eğitim, çekicilik, boy, beslenme, siyasi ilgi/ideoloji) tasarım dosyasındaki (2.reshape.do) tanımlardan kodlanır. Model: profil seçildi ~ 7 özellik (doğrusal olasılık, kişiye göre küme bootstrap). Çıktı: uzun (182,9) – kısa (172,7) etkisi, çekicilik ve eğitim etkisiyle aynı ölçekte.
- **B4 (SL).** Kadının kendi boyuyla etkileşim: boy etkisi, kadın boyu < 160, 160-169,9, ≥ 170 gruplarında ayrı.
- **B5.** 176 → 178'e aktarım: B3 etkisi 10,2 cm için; doğrusal kabulle 2 cm'lik pay = etki × 2/10,2 (varsayım olarak etiketlenir; B1 eğrisiyle karşılaştırılır).

### C. Yaşanan (BR)

- **C0. Hazırlık:** Ölçülmüş boy V0434 (999,9 ve 120-215 cm dışı eksik). Aile = hane + tüketim birimi + NUM_FAMILIA. Bir kişi, ailesinde referans kişi (COND_FAMILIA = 1) olup aynı ailede eş (2) varsa ya da kendisi eş (2) ise **partnerle yaşıyor** sayılır.
- **C1. Çiftler:** Karşı cins çiftler (ikisi de ≥ 20 yaş, ölçülmüş boy). Gözlenen "kadın daha uzun" oranı ile rastgele eşleşme (aynı erkek ve kadınların 1.000 kez karıştırılması) karşılaştırılır.
- **C2. Partnerle yaşama:** 25-44 yaş erkekler (ağırlıklı, PESO_FINAL). Boy, 5 yıllık yaş grupları içinde z-puanına çevrilir. Model: partnerle yaşıyor ~ boy z-puanı (doğal kübik spline, 4 serbestlik derecesi) + yaş grubu. Düzeltilmiş model: + eğitim yılı + eyalet (COD_UF). Çıktı: Türk 176 cm'nin yüzdelik karşılığı (TBSA'ya göre z = 0,189, %57,5) ve 178 cm (z = 0,480, %68,4) noktasında, medyana (z = 0) ve %10'luk dilime (z = −1,28) göre fark. Güven aralığı: COD_UPA (örneklem birimi) kümeli bootstrap, 500 tekrar.
- **C3. Kimle?** Partnerli erkeklerde, aynı yüzdeliklerde eşin boyu (kadın dağılımında z-puanı) ve eşin kocadan uzun olma olasılığı (z-puanı ±0,3 bandındaki erkekler).
- **C4. Eksik boy kontrolü:** Ölçülmüş boyu eksik olma oranı partnerli ve partnersiz erkeklerde ayrı raporlanır; fark > 5 yp ise duyarlılık olarak atanmış boy (ALTURA_IMPUTADA) ile C2 tekrarlanır.

## Ön kayıtlı testler

**Teknik testler (geçmezse ilgili analiz geçersiz sayılır):**

| Kod | Test | Ölçüt |
|---|---|---|
| T1 | SL kodlama: kadınların kısa/uzun profil seçme oranı yayımlanmış değerleri (0,382 / 0,435) tekrar ediyor | ikisi de ±0,015 içinde |
| T2 | UV rastgeleleştirme: profil boyu ile diğer özellikler arası en büyük \|r\| | < 0,05 |
| T3 | BR çift sayısı ve r | n ≥ 25.000 ve 0,30 ≤ r ≤ 0,45 |
| T4 | PI uzun süreli bağlamda kendi boyu ve tercihi olan kadın | n ≥ 300 |

**Hipotezler (yön ve eşik önceden):**

| Kod | Hipotez | Geçme ölçütü |
|---|---|---|
| H1 | Söylenen: 160,5 cm'lik bir kadının (Türk ortalaması) medyan tercih ettiği partner boyu 180 cm'nin altında | A1 tahmini < 180 ve %95 GA üst sınırı < 182 |
| H2 | Söylenen: Kadın boyu arttıkça tercih edilen partner boyu artıyor | A1 eğimi b > 0, %95 GA alt sınırı > 0 |
| H3 | Seçilen: UV'de 176 → 178 cm farkı seçilme olasılığını küçük ölçüde değiştiriyor | Δ(176→178) %95 GA üst sınırı < 3 yp |
| H4 | Seçilen: SL'de uzun profil avantajı kısa kadınlarda (< 160) uzun kadınlardan (≥ 170) küçük | fark (≥170 − <160) > 0, bootstrap tek yönlü p < 0,05 |
| H5 | Seçilen: SL'de boyun etkisi çekiciliğin etkisinden küçük | boy etkisi < çekicilik etkisi, farkın %95 GA üst sınırı < 0 |
| H6a | Yaşanan: Brezilya'da Türk-176 yüzdeliğindeki (%57,5) erkeklerin partnerle yaşama oranı medyandaki erkeklerden düşük değil | fark (z=0,189 − z=0) %95 GA alt sınırı > −2 yp |
| H6b | Yaşanan: En kısa %10'luk dilimde ceza var | fark (z=−1,28 − z=0) %95 GA üst sınırı < 0 |
| H7 | Yaşanan: Gerçek çiftlerde "kadın daha uzun" oranı rastgele eşleşmeden düşük | gözlenen < rastgele 1.000 karıştırmanın %2,5'lik dilimi |
| H8 | Yaşanan: Türk-176/178 yüzdeliğindeki partnerli erkeklerin eşinin kendisinden uzun olma olasılığı küçük | iki yüzdelikte de < %5 |

## Karar kuralları (sonuç cümleleri önceden)

- **K1 (söylenen):** A2'de tercihi ≤ 176 olan Türk kadın oranı p ise: p ≥ %67 → "176, kadınların çoğunun söylediği tercihi karşılıyor"; %33 ≤ p < %67 → "yarı yarıya"; p < %33 → "176, kadınların çoğunun söylediği tercihin altında". Aynı kural 178 için.
- **K2 (seçilen):** H3 geçerse "176 → 178 seçimde küçük fark"; geçmezse "176 → 178 seçimde fark edilir fark" denecek ve büyüklüğü yazılacak.
- **K3 (yaşanan):** H6a geçerse "medyanın biraz üstündeki erkekler için partnerle yaşamada ceza görülmedi"; geçmezse açıkça "ceza görüldü" denecek.
- **K4 (çelişki):** Söylenen ile seçilen/yaşanan katman farklı sonuç verirse ikisi de yazılacak; hangisinin daha gerçekçi olduğu yorumu "D" (çıkarım) olarak etiketlenecek.

## Simülasyon kuralları

Bu sürümde simülasyon yok. A2 ve A3'teki Türk dağılımına aktarım Monte Carlo ile değil, normal dağılım üzerinden sayısal integralle (ya da 1.000.000 çekilişle, tohum 20261031) hesaplanır.

## Plandan sapmalar

(Henüz yok.)
