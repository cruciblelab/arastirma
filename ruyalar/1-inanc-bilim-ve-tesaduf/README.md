# Rüyalar · Sürüm 1: İnanç, Bilim ve Tesadüf

> **Sürüm:** 1 · **Tarih:** 2026-10-29 · **Durum:** taslak
>
> Bu doküman **tıbbi tavsiye değildir.** Dinî inançları yargılamaz; rüya hakkında bilimsel olarak bilinenleri ve bilinmeyenleri anlatır.
>
> Bu taslak, **analiz kodu yazılmadan önce** commit edilen ön kayıttır. Rapor bölümleri analizden sonra eklenecek.

**Kanıt seviyeleri:** A meta-analiz ya da birden çok büyük çalışma · B tek iyi çalışma · C küçük çalışma ya da ikincil kaynak · V bu çalışmanın kendi veri analizi · D model ya da varsayım.

## Soru ve kapsam

1. İnsanlar rüyalara neden inanıyor?
2. Bilim rüya hakkında ne biliyor? Rüyalar neyi yansıtır, ne işe yarar?
3. Rüyalar geleceği gösterir mi? "Rüyam çıktı" deneyimi tesadüfle ne kadar açıklanır?
4. Türkiye'de ve İslam geleneğinde rüyaya nasıl bakılıyor?

## Yöntem

**Dört aşama:**
1. **Tarama:** 5 paralel literatür ajanı (inancın psikolojisi, rüyanın bilimi, kehanet rüyaları ve tesadüf, rüya içeriği istatistikleri ve açık veri, Türkiye ve kültür). Okunamayan sayılar `[doğrulanmadı]` diye işaretlendi.
2. **Kendi analiz:** (a) Ön kayıtlı tesadüf simülasyonu: [simulasyon/PLAN.md](simulasyon/PLAN.md). (b) DreamBank rüya raporlarında ön kayıtlı içerik sayımı (aşağıda).
3. **Doğrulama:** Kilit sayılar bağımsız ajanlarca birincil kaynaktan yeniden kontrol edilecek. Bir "şeytanın avukatı" ajanı sonuçları çürütmeye çalışacak.
4. **Rapor.**

### DreamBank içerik analizi (ön kayıt)

**Veri:** DreamBank (Domhoff ve Schneider; CC BY-NC-SA 4.0), Cortal'ın Hugging Face kopyası `gustavecortal/DreamBank-annotated` (`train.csv`, SHA-256 `aacabafe17adf3d4…c1e7447`).
- 27.952 rapor, 72 rüya dizisi.
- Kod dosyayı indirir ve özetini doğrular. Veri repoya kopyalanmaz.
- Boş ve birebir tekrar eden raporlar atılır.
- Modelin ürettiği `character` ve `emotion` sütunları **kullanılmaz**; yalnızca rapor metni kullanılır.

**Yöntem:** Önceden sabitlenmiş İngilizce kelime listeleri; büyük-küçük harf duyarsız, kelime sınırlı düzenli ifadeler.

| Liste | Kelimeler (kök sonuna `*` = ekleri de kapsar) |
|---|---|
| OLAY (olumsuz olay) | die, dies, died, dying, dead, death, kill*, accident*, crash*, fell, fall, falling, injur*, hurt*, bleed*, blood*, sick*, hospital*, lost, lose, losing, fail*, broke, broken, fire, burn*, drown*, attack*, chase*, chasing, fight*, fought, stab*, shot, shoot*, bite, bit, bites, biting, bitten |
| DUYGU (olumsuz duygu) | afraid, scared, fear*, terrif*, panic*, anxious, anxiety, worr*, scream*, cry, cried, crying, upset, angry, anger, sad, sadness |
| HAYVAN | animal*, cat, cats, kitten*, dog, dogs, puppy, puppies, horse*, bird*, snake*, spider*, rat, rats, mouse, mice, lion*, tiger*, wolf, wolves, shark*, bee, bees, monkey*, cow, cows, pig, pigs, insect*, bug, bugs |
| SALDIRI | bite, bit, bites, biting, bitten, scratch*, attack*, claw*, sting*, stung |

| Kod | Ölçü |
|---|---|
| D1 | Raporların yüzde kaçında OLAY, DUYGU ve OLAY ya da DUYGU var. Tümü, Hall ve Van de Castle norm dizileri (991 rapor) ve cinsiyete göre |
| D2 | Raporların yüzde kaçında HAYVAN; HAYVAN ve SALDIRI birlikte; "cat/cats/kitten*" ve "bite/bit/bites/biting/bitten" birlikte |
| D3 | En az 200 raporu olan uzun dizilerde (kişi bazında) D1 oranının dağılımı: medyan, en düşük, en yüksek |
| D4 | D1'deki "OLAY ya da DUYGU" oranı, simülasyonda ek bir p_neg senaryosu olarak kullanılır (PLAN.md) |

**Teknik testler:**

| Test | Ölçüt |
|---|---|
| T5 | SHA-256 özeti eşleşir |
| T6 | Temizlikten sonra en az 27.000 rapor kalır |
| T7 | Düzenli ifade kontrolü, sabit örnek cümlelerle. "the cat bit my hand" → HAYVAN ve SALDIRI; "I caught a bus" → hiçbiri; "bitter coffee" → SALDIRI değil |

**Kesinlik kontrolü:** Koordinatör, OLAY ya da DUYGU işaretli 30 rastgele raporu ve HAYVAN ile SALDIRI işaretli 30 rastgele raporu (tohum sabit) okuyup gerçekten olumsuz ya da gerçekten hayvan saldırısı içerip içermediğini sayar. Kesinlik raporlanır; hiçbir karar buna bağlı değildir.

**Karar kuralı K6:** HAYVAN ve SALDIRI birlikte geçen raporlar %5'in altındaysa → "hayvan saldırısı rüyası nadir". Yine de bir milyon kişide gecede kaç kez görüleceği, haftada 1 hatırlanan rüya varsayımıyla raporlanır.

### Şeffaflık notu

DreamBank verisinin yalnızca yapısına (sütunlar, satır sayıları, dizi adları, tekrar sayısı) bakıldı; rapor içeriği okunmadı ve sayılmadı. Simülasyon parametreleri literatürden alındı; simülasyon kodu henüz yazılmadı.

### Plandan sapmalar

| Sapma | Gerekçe |
|---|---|
| (henüz yok) | |
