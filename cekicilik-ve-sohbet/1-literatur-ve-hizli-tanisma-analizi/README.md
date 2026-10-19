# Çekicilik ve Sohbet · Sürüm 1: Literatür ve Hızlı Tanışma Analizi

> **Sürüm:** 1 · **Tarih:** 2026-10-19 · **Durum:** taslak
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
| **D** | Model, varsayım ya da yapay zekâ ile yazılmış örnek |

---

## Soru ve kapsam

1. Kadınlar ilk tanışmada bir erkekten hoşlanırken **en çok nelere** tepki veriyor? Görünüşün payı ne, sohbetin payı ne?
2. Sohbette **hangi davranışların** beğeniyi artırdığına dair kanıt var?
3. İnsanların **söylediği** tercih ile **gerçek kararı** örtüşüyor mu?
4. "Ortak ilgi alanı" önceden var olan bir benzerlik mi, yoksa sohbette **oluşan bir algı** mı?
5. Bir sesi yanlış çıkarmak (ör. "r"yi "l" gibi söylemek) dinleyicinin algısını nasıl etkiliyor, düzelir mi?

**Kapsam dışı:** Manipülasyon teknikleri; 18 yaş altı katılımcılarla deney; belirli bir kişiye yönelik tavsiye. Eşcinsel çiftler bu verilerde ayrı incelenmedi.

## Yöntem

### 1. Literatür

Sohbet davranışları, ilk izlenim, söylenen ve gerçek tercih, konuşma sesi hataları. Tam metni okunamayan bulgular `[ikincil]` diye işaretlenecek.

### 2. Gerçek veri (V)

| Veri | Rol |
|---|---|
| **D1: Hızlı tanışma deneyi** (Fisman ve Iyengar, Columbia Üniversitesi; DataHub kopyası) | Her 4 dakikalık buluşmadan sonra katılımcı karşısındakini 6 özellikte puanlıyor ve "evet/hayır" diyor. Yaş-farkı araştırmasıyla aynı dosya ve aynı SHA-256 |
| **D2: 45 ülke açık verisi** (Walter ve ark. 2020) | İdeal partnerde 5 özelliğin önemi (1-7). `sex = 0` kadın |

Veriler kaynağından indirilir, SHA-256 doğrulanır; repoya kopyalanmaz.

### 3. Ön kayıtlı analiz planı

**Ortak kurallar (D1):**
- Kişi kimliği yaş-farkı araştırmasıyla aynı kurulur (`KIMLIK` sütunları).
- Yordayıcılar: karar verenin karşısındakine verdiği 6 puan: çekicilik, samimiyet, zekâ, komiklik, hırs, ortak ilgi (`*_partner`). 6 puandan biri eksik olan satır çıkarılır.
- **Kişi içi model:** Her değişkenden karar verenin kendi ortalaması çıkarılır. Böylece "seçici biri" ile "seçici olmayan biri" karıştırılmaz. Yordayıcılar o cinsiyetteki kişi içi standart sapmaya bölünür. Doğrusal olasılık modeli (EKK).
- Katsayı × 100 = o özellik 1 standart sapma yüksek bulunduğunda "evet" olasılığının kaç puan değiştiği.
- **%95 aralık:** kişiler üzerinden 2000 bootstrap, tohum 20261019.

| Kod | Analiz |
|---|---|
| A1 | Kadınların kararı: 6 yordayıcılı kişi içi model |
| A2 | Erkeklerin kararı: aynı model; her özellik için fark (erkek − kadın) |
| A3 | **Söylenen ve gerçek tercih (kadınlar):** A1 modeline 3 etkileşim eklenir: karşısındakinin çekicilik, komiklik ve zekâ puanı × karar verenin etkinlikten önce o özelliğe "ne kadar önem veririm" dediği değer (`*_important`). Önem puanı dalga (wave) içinde standartlaştırılır, çünkü bazı dalgalarda ölçek farklı |
| A4 | **Kâğıt üzerindeki benzerlik ve algılanan ortak ilgi (kadınlar):** İki ayrı tek yordayıcılı kişi içi model, aynı satırlarda: (a) hobi listelerinin nesnel korelasyonu (`interests_correlate`); (b) algılanan ortak ilgi (`shared_interests_partner`). Fark: (b) − (a) |
| A5 | **D2, 45 ülke:** Her ülkede kadınların 5 özelliğe verdiği ortalama önem; hangi özelliğin kaç ülkede birinci olduğu; Türkiye satırı |
| A6 | A5'in erkekler için aynısı (karşılaştırma) |

### 4. Teknik testler (geçme ölçütüyle)

| Test | Ölçüt |
|---|---|
| T1 | İki dosyanın SHA-256 özeti, yaş-farkı araştırmasındaki değerlerle eşleşir |
| T2 | Kişi sayısı yaş-farkı sürüm 1 ile aynı: kadın 269, erkek 274 |
| T3 | Çekicilik katsayısının %95 aralığının alt sınırı iki cinsiyette de 0'dan büyük (kodlama hatası kontrolü) |
| T4 | Kişi içi merkezleme doğru: merkezlenmiş kararın kişi ortalamalarının mutlak en büyüğü < 1e-9 |
| T5 | D2'de 45 ülke var ve `sex = 0` grubunun kaynak (resources) ortalaması `sex = 1` grubundan yüksek (yaş-farkı sürüm 1'deki kodlamayla tutarlılık) |

### 5. Karar kuralları

| Kural | Soru | Karar |
|---|---|---|
| K1 | Kadınlarda en büyük katsayı çekicilik mi; komiklik ve ortak ilgi pozitif mi? | Üç koşul da sağlanırsa (çekicilik en büyük; komiklik ve ortak ilgi aralık alt sınırı > 0) "evet" |
| K2 | Erkekler görünüşe kadınlardan daha mı çok ağırlık veriyor? (Fisman ve ark. 2006 "evet" diyor; Eastwick ve Finkel 2008 "fark yok" diyor) | Fark (erkek − kadın) aralığı > 0 → "evet"; < 0 → "tersine"; 0'ı içerirse → "belirgin fark yok" |
| K3 | Kadınlar komikliğe erkeklerden daha mı çok ağırlık veriyor? (Bressler ve ark. 2006 yönü) | Fark (kadın − erkek) için K2 ile aynı kural. Zekâ için de aynı fark raporlanır (K3b) |
| K4 | Söylenen önem gerçek kararı öngörüyor mu? | Her etkileşim için: aralık 0'ı içerirse "öngörmüyor", alt sınır > 0 ise "öngörüyor". 3 etkileşimin en az 2'si "öngörmüyor" ise genel karar: "söylenen ve gerçek tercih örtüşmüyor" |
| K5 | Ortak ilgi sohbette mi oluşuyor? | Nesnel benzerliğin katsayı aralığı 0'ı içerirse **ya da** nokta tahmini algılanan ortak ilginin yarısından küçükse **ve** fark (algılanan − nesnel) aralığı > 0 ise: "kâğıt üzerindeki benzerlik az etkili, ortak ilgi sohbette algılanıyor" |
| K6 | 45 ülkede kadınlar uzun vadeli partnerde en çok iyi kalpliliği mi önemsiyor? | İyi kalplilik en az 25 ülkede birinciyse "evet" |

### 6. Şeffaflık notu: plan yazılmadan önce görülenler

2026-10-19'da, bir sohbet sırasında, bu plandan önce yapılan **keşif analizinde** şunlar görüldü:
- **A1'in yaklaşık sürümü:** Kişi anahtarı daha kaba kurulmuştu (dalga, yaş, ırk, alan); bootstrap yapılmadı. Kadınlarda kişi içi katsayılar (puan / 1 SS): çekicilik 12.9, ortak ilgi 8.3, komiklik 6.1, zekâ 3.0, samimiyet 0.0, hırs 0.0. Tek tek korelasyonlar da görüldü.
- **A5:** Kadınlarda iyi kalplilik 30 ülkede, sağlık 10 ülkede, zekâ 5 ülkede birinci. Türkiye: zekâ 6.01, sağlık 5.90, iyi kalplilik 5.72, fiziksel çekicilik 5.54, kaynak 5.50. Cinsiyetlere göre genel ortalamalar da görüldü.

Bu yüzden **K1, K6 ve T5 kör değildir**; yeniden üretim sayılır. **A2, A3, A4, A6 ve K2-K5 görülmedi**; bunlar gerçek ön kayıtlı testlerdir.

### Plandan sapmalar

| Sapma | Gerekçe |
|---|---|
| (henüz yok) | |
