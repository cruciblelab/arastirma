# Simülasyon Planı: Omurga Uzamasını Ne Etkiler, Nasıl Ölçülür, Nasıl Gösterilir?

> **Plan sürümü:** 1 · **Tarih:** 2026-10-08 · **Durum:** ön kayıt (kod yazılmadan önce commit edildi)
>
> Testler çalıştırıldıktan sonra ölçütler değiştirilmez. Değişiklikler "Plandan sapmalar" tablosuna yazılır.

## 1. Soru

Büyüme plaklarının kapanma sırası araştırması (sürüm 1), 16 yaştan sonraki boy artışının ~%90'ının gövdeden geldiğini buldu. Bu çalışmanın soruları:

1. **Kaldıraçlar:** Omurga tarafında ölçülen boyu değiştiren etkenler nelerdir ve her biri kaç milimetredir?
   - kalan biyolojik büyüme;
   - eğrilik (skolyoz, kifoz, duruş);
   - mekanik yük;
   - disklerin gün içi değişimi.

   Hangileri kalıcı, hangileri geçici? Hangisi gerçekten "desteklenebilir"?
2. **Çalışma protokolü:** Bir genç evde, oturma boyu ve boy ölçerek şunları ayırt edebilir mi?
   - omurgasının hâlâ uzayıp uzamadığı;
   - bacaklarının (diz plaklarının) hâlâ uzayıp uzamadığı.

   Kaç ölçüm, hangi aralıkla gerekir?
3. **Animasyon:** Bu süreç (bacak önce durur, gövde devam eder, gece-gündüz disk değişimi, eğriliğin etkisi), ölçekleri açıkça not edilmiş kısa bir animasyonla gösterilebilir mi?

**Benzetme:** Omurga, araya yastıklar konmuş bir kitap yığını. Kitaplar (omurlar) yavaşça kalınlaşır, bu kalıcıdır. Yastıklar (diskler) gündüz ezilir, gece kabarır, bu geçicidir. Yığın eğik durursa boyu kısa ölçülür. "Omurga uzaması" derken bu üçünü karıştırmamak gerekir.

## 2. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Büyüme modeli yeniden kalibre edilmez. Gövde ve bacak eğrileri boy araştırması sürüm 3 modelinden (`plak.kohort`, `model.simule_et`), Türk uyarlamalı. |
| S2 | Her sayı ya bir kaynaktan, ya bu depodaki önceki bir analizin çıktısından (dosya adıyla), ya da açıkça varsayımdan gelir. |
| S3 | **Animasyon ölçekli değildir.** Omurların ve disklerin çizimi şematiktir. Animasyonda yazan **sayılar** ise model çıktısıdır ve testle doğrulanır (T1). Bu ayrım animasyonun içinde ve raporda yazılır. |
| S4 | Sabit tohum (20261008), tek komut, çıktılar `ciktilar/` altında. |
| S5 | Kanıt seviyesi: kaynak sayıları C, önceki Berkeley analizi V, model ve protokol simülasyonu D. |

## 3. Model

### 3.1 Kaldıraç tablosu (A)

| Kaldıraç | Hesap | Kaynak / sınıf |
|---|---|---|
| Kalan gövde büyümesi (16 → 25 yaş, ve 17 → 25) | Sürüm 3 modeli, medyan ve %10-90; erkek ve kız | Model (D); Berkeley karşılaştırması: plak kapanma sırası araştırması `ozet.json` (V) |
| Skolyoz eğrisinin boy kaybı | Kayıp (mm) = 1.0 + 0.066·Cobb + 0.0084·Cobb², Cobb = 10, 20, 30, 45° | Stokes 2008 (ölçülmüş, 407 röntgen; C) |
| Duruş (kifoz) | 2-4 mm | Spor araştırması sürüm 1, bölüm 4.4 (D) |
| Mekanik yük (egzersiz) | < 0.5 mm (üst sınır) | Spor araştırması sürüm 1 (D) |
| Disklerin gün içi değişimi | 14.4 mm, geçici | Spor araştırması sürüm 1, ölçülmüş kalibrasyon girdisi (C) |
| Sistemik etkenler (beslenme, uyku) | Yeterliyse +0, eksiklikte −; senaryo aralığı | Beslenme araştırması sürüm 1 (D) |

### 3.2 Ölçüm protokolü simülasyonu (B)

Gerçek büyüme doğrusal kabul edilir (12-18 aylık kısa pencerede):
- oturma boyu: S(t) = S0 + v_g·t;
- bacak: B(t) = B0 + v_b·t.

Bir ölçüm seansında k tekrar yapılır ve ortalaması alınır:
- seans hatası e = u + ε̄;
- u ~ N(0, σ_s²): o günün koşulu (saat, duruş);
- ε̄: k tekrarın ortalama okuma hatası, SD σ_o/√k.

Bacak = boy − oturma boyu, yani iki ölçümün farkıdır ve iki hatayı birlikte taşır.

| Parametre | Ana | Varyant | Sınıf |
|---|---|---|---|
| Gövde hızı v_g | 0.6 cm/yıl | 0.3, 1.0 | Berkeley erkek 18-20 yaş ortalama gövde hızı ~0.6-0.8 (plak kapanma sırası araştırması grafiği; V) |
| Bacak hızı v_b | 0.3 cm/yıl | 0.1, 0.5 | Berkeley erkek 17-18 yaş (aynı grafik; V) |
| Okuma hatası σ_o | 0.5 cm | 0.3, 0.8 | Varsayım (oturma boyu duruşa duyarlı) |
| Seans koşulu σ_s | 0.3 cm | 0, 0.5 | Varsayım. Protokol sabah aynı saatte ölçmeyi şart koşar; gün içi 14.4 mm fark bu yüzden büyük ölçüde dışarıda kalır |

Tasarımlar:
- seans aralığı 1, 2, 3 ya da 6 ay;
- toplam süre 6, 12 ya da 18 ay;
- seans başına tekrar k = 1, 3 ya da 5.

Analiz: Seans ortalamalarına en küçük kareler doğrusu oturtulur. Tek yönlü test (eğim > 0), α = 0.05. Güç = P(eğim anlamlı > 0). Ayrıca eğimin %90 güven aralığı genişliği. 20 000 Monte Carlo tekrarı.

**Önerilen protokol (karar kuralı):** Ana parametrelerde gövde büyümesi için güç ≥ 0.80 sağlayan, toplam ölçüm sayısı (seans × k) en küçük ve süresi en kısa tasarım.

### 3.3 Animasyon (C)

- **Sol:** Şematik omurga. 24 omur ve aralarındaki diskler; gövde yüksekliği modeldeki medyan erkeğin oturma boyuna orantılı. Omur sonlanma plakları büyüme hızına göre renklenir: parlak = aktif, gri = kapanmış. Yanında bacak sütunu, aynı renk kodu.
- **Sağ üst:** Boy, oturma boyu ve bacak eğrileri; o anki yaş işaretli.
- **Sağ alt:** O yaştaki bacak ve gövde hızları (cm/yıl).
- **Alt bant:** O aşamayı anlatan not, aşamaya göre değişir.
- Yaş 13 → 22. Ardından iki kısa ek sahne:
  - **gece-gündüz:** disklerin 14.4 mm değişimi, "geçici";
  - **eğrilik:** 30° Cobb skolyozun boy kaybı (Stokes), "ölçülen boy kısalır, omurga kısalmaz".
- Biçim: GIF (repoda gösterilebilir), ayrıca ffmpeg varsa MP4. Kare sayısı ve boyut küçük tutulur (GIF < 5 MB).

## 4. Ön kayıtlı testler

| # | Test | Ölçüt |
|---|---|---|
| **T1** | Animasyonda gösterilen boy, oturma boyu ve bacak değerleri, sürüm 3 modelinin aynı kişi ve yaşlardaki çıktısıyla aynı mı? | En büyük fark < 1e-6 cm |
| **T2** | Stokes formülü kaynağın örneğini üretiyor mu? (Cobb 30 → 40°: ~6.7 mm) | \|Δ − 6.7\| < 0.3 mm |
| **T3** | Protokol simülasyonunda test doğru mu? (v = 0'da yanlış pozitif oranı) | 0.04-0.06 |
| **T4** | Monte Carlo kararlılığı: ana tasarımda iki tohumla güç farkı | < 0.02 |
| **T5** | Animasyon dosyası üretildi ve sınırın içinde | GIF < 5 MB, kare sayısı ≥ 60 |

## 5. Duyarlılık

- Protokol: bölüm 3.2'deki bütün varyantlar, birer birer.
- Kaldıraç tablosu: model aralığı (%10-90) ve cinsiyet.

## 6. Önceden bilinen sınırlamalar

- **Hızlar doğrusal kabul edildi.** Gerçekte azalarak gider; 12-18 aylık pencerede doğrusal yaklaşım kabul edilebilir.
- **Ölçüm hataları varsayım.** Gerçek ev ölçümlerinde ölçülmedi.
- **Oturma boyu yalnız omurga değildir:** leğen ve kafa tabanı da içinde.
- **Stokes formülü skolyozlu hastalardan.** Cobb = 0'da 1 mm veriyor (regresyon sabiti); küçük açılarda yorum dikkatli yapılır.
- **Animasyon şematik.** Omur ve disk oranları gerçek anatomiyi temsil etmez; yalnızca sayılar modeldir.

## 7. Plandan sapmalar

| Tarih | Ne değişti | Neden | Sonuçlar görüldükten sonra mı? |
|---|---|---|---|
| – | – | – | – |

**Şeffaflık notu:** Plan yazılmadan önce görülen sonuçlar:
- plak kapanma sırası araştırmasının Berkeley bulguları (gövde hızı 18-20 yaşta ~0.6-0.8 cm/yıl);
- sürüm 3 modelinin gövde payı (%88);
- Stokes 2008 özetindeki örnek. T2 bu yüzden yalnızca kodun doğruluğunu sınar.
