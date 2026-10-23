# Çekicilik ve Sohbet · Sürüm 2: Hoşlandığını Göstermek mi, Söylemek mi?

> **Sürüm:** 2 · **Tarih:** 2026-10-23 · **Durum:** taslak
>
> Bu doküman **tıbbi tavsiye değildir.** İlişki tavsiyesi ya da "taktik" listesi de değildir; araştırmaların ortalama olarak ne bulduğunu anlatır.
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

1. Birinden hoşlandığını **göstermek** mi, açıkça **söylemek** mi daha olumlu sonuçlanıyor?
2. "Karşımdaki benden hoşlanıyor" hissi, insanın kendi ilgisini ne kadar artırıyor?
3. **Seçici ilgi** (yalnız o kişiye ilgi) ile **seçici olmayan ilgi** (herkese ilgi) aynı karşılığı görüyor mu?
4. İnsanlar karşısındakinin ilgisini ne kadar doğru okuyor?

**Kapsam dışı:** Manipülasyon teknikleri; 18 yaş altı katılımcılarla deney; belirli bir kişiye yönelik tavsiye.

## Yöntem

### 1. Literatür

Karşılıklı hoşlanma, seçici ve seçici olmayan ilgi, belirsizlik etkisi, "seni seviyorum"u kimin önce söylediği ve tepkiler, flört tarzları, açılma ve hoşlanma, karşılıksız aşk ve pişmanlık, ilginin yanlış okunması. Tam metni okunamayan bulgular `[ikincil]` diye işaretlenecek.

### 2. Gerçek veri (V)

**Veri:** Sürüm 1 ile aynı hızlı tanışma deneyi (Fisman ve Iyengar, Columbia Üniversitesi; DataHub kopyası; aynı SHA-256). Her 4 dakikalık buluşmadan sonra katılımcı:
- karşısındakini 6 özellikte puanlıyor;
- "karşımdakinin bana evet deme olasılığı" tahminini 1-10 arası veriyor (`guess_prob_liked`);
- "evet" ya da "hayır" diyor (`decision`).

Karşısındakinin bu kişi hakkındaki kararı da veride var (`decision_o`).

**Önemli sınır:** Veride kimse hoşlandığını **açıkça söylemedi**. Kararlar gizliydi. Yani bu veri "söylemenin" etkisini değil, 4 dakikalık sohbette **davranışla gösterilen ve algılanan ilginin** etkisini ölçebilir. "Söylemek" sorusu literatürden cevaplanacak.

**Kimlikler:**
- Karar veren: sürüm 1'deki `KIMLIK` sütunlarıyla.
- Karşısındaki: kayıtta bulunan, kişiye özgü sabit özelliklerle: dalga, cinsiyet (karar verenin tersi), `age_o`, `race_o` ve 6 `pref_o_*` sütunu (karşısındakinin etkinlik öncesi söylediği tercihler).

**Değişkenler:**
- `algilanan` = `guess_prob_liked`.
- `karsi_secici_olmayan` = karşısındakinin bütün buluşmalarındaki "evet" oranı. Yüksekse, o kişi herkese evet diyor.
- `karsi_ozgun` = karşısındakinin **bu** kişiye kararı − kendi "evet" oranı. Pozitifse, bu kişiyi diğerlerinden çok seçmiş.

**Model:** Sürüm 1'deki kişi içi doğrusal olasılık modeli. Her değişkenden karar verenin kendi ortalaması çıkarılır ve yordayıcılar kişi içi standart sapmaya bölünür. Katsayı × 100, yordayıcı 1 SS arttığında "evet" olasılığının kaç puan değiştiğini gösterir. %95 aralık: karar verenler üzerinden 2000 bootstrap, tohum 20261023.

| Kod | Analiz |
|---|---|
| B1 | **Algılanan karşılık:** karar ~ 6 özellik + `algilanan`. Kadın ve erkek karar verenler ayrı |
| B2 | **Gerçek karşılık, ikiye bölünmüş:** karar ~ 6 özellik + `karsi_ozgun` + `karsi_secici_olmayan`. Cinsiyetler ayrı |
| B3 | B2'nin 6 özellik olmadan hali (betimsel) |
| B4 | **İlgiyi okuma doğruluğu:** `algilanan` ile `decision_o` arasındaki kişi içi korelasyon. Cinsiyetler ayrı |

### 3. Teknik testler (geçme ölçütüyle)

| Test | Ölçüt |
|---|---|
| T1 | Dosyanın SHA-256 özeti sürüm 1 ile aynı |
| T2 | Karşı taraf kimliği tutarlı: her dalga ve cinsiyet için karşı taraf kimliği sayısı ile o dalga ve cinsiyetteki karar veren sayısının mutlak farklarının toplamı, karar veren toplamının %5'inden az |
| T3 | Karşı tarafların en az %90'ının "evet" oranı en az 5 buluşmadan hesaplanıyor |
| T4 | Kişi içi merkezleme doğru: merkezlenmiş kararın kişi ortalamalarının mutlak en büyüğü < 1e-9 |
| T5 | Kodlama kontrolü: B1'de çekicilik katsayısının aralık alt sınırı iki cinsiyette de > 0 |

### 4. Karar kuralları

| Kural | Soru | Karar |
|---|---|---|
| K1 | "Benden hoşlanıyor" hissi, kişinin kendi "evet"ini artırıyor mu? (B1) | Aralık alt sınırı > 0 → "evet". Her cinsiyet için ayrı |
| K2 | Seçici ilgi karşılık görüyor mu? (B2, `karsi_ozgun`) | Aralık alt sınırı > 0 → "evet"; 0'ı içerirse → "belirgin fark yok" |
| K3 | Herkese ilgi gösteren daha az mı ilgi görüyor? (B2, `karsi_secici_olmayan`) | Aralık üst sınırı < 0 → "evet, ters tepiyor"; 0'ı içerirse → "belirgin fark yok"; alt sınırı > 0 → "tersine, daha çok ilgi görüyor" |
| K4 | İnsanlar ilgiyi doğru okuyor mu? (B4) | Aralık alt sınırı > 0 ise "okuyor". Nokta tahmini < 0.3 → "zayıf", 0.3-0.5 → "orta", > 0.5 → "güçlü" |

**Literatürden beklenen yön:** Eastwick ve ark. 2007'de seçici ilgi karşılık gördü, herkese ilgi ters tepti (K2 evet, K3 evet). Bu beklenti kararı değiştirmez.

### 5. Şeffaflık notu

Bu sürümdeki analizlerin (B1-B4) hiçbiri plan yazılmadan önce bu veride çalıştırılmadı. Sürüm 1'deki 6 özellik katsayıları biliniyor, ama burada yalnız kontrol değişkeni olarak kullanılıyor.

### Plandan sapmalar

| Sapma | Gerekçe |
|---|---|
| (henüz yok) | |
