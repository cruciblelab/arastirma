# Yaş Farkı Tercihleri · Sürüm 1: Literatür ve Gerçek Veri

> **Sürüm:** 1 · **Tarih:** 2026-10-16
>
> **Durum:** taslak
>
> Bu doküman tıbbi tavsiye değildir.

Taslak. Aşağıdaki analiz planı, analiz kodu yazılmadan ve sonuçlara bakılmadan önce commit edildi. Yalnız sütun adları ve örneklem büyüklükleri görüldü.

## Ön kayıtlı analiz planı

**Veri**
- **D1:** Walter ve ark. 2020, 45 ülke açık verisi (OSF gb5cn, `ReplicationProcessedfinaldata04202018.csv`). n = 14 399; partner yaşını bildiren 8920 kişi. Türkiye: 1061 katılımcı (İstanbul, İzmir), 734'ü partner yaşını bildirmiş. Değişken `mate_age` **gerçek partnerin yaşıdır, ideal yaş değildir.**
- **D2:** Fisman ve Iyengar hızlı tanışma deneyi (Columbia, 21 dalga, 8378 buluşma; DataHub kopyası, kamu malı). Her satır bir kişinin bir buluşmada partnerine "evet" ya da "hayır" demesidir.
- **Cinsiyet kodu (D1):** Belgelenmemiş. Erkek grubu, "fiziksel çekicilik" tercihi ortalaması daha yüksek olan grup olarak tanımlanır; bu, literatürün en tutarlı bulgusudur. A1 replikasyonu doğrular.

**Analizler**

| Kod | Analiz |
|---|---|
| A1 | Replikasyon: bütün ülkelerde yaş farkı (partner − kendi) ortalaması, cinsiyete göre. Makalede: kadınlar +2.43, erkekler −2.26 (n = 8920) |
| A2 | Türkiye: cinsiyete göre ortalama, %95 güven aralığı, dağılım. Partner 5 ve 10 yaştan fazla büyük ya da küçük olanların payı. Yaş grupları: 18-24, 25-34, 35+ |
| A3 | Ülke sıralaması: her ülkede erkek ortalaması − kadın ortalaması; Türkiye'nin yeri |
| A4 | Yaşla değişim: yaş farkının katılımcının kendi yaşına eğimi, cinsiyete göre; bütün ülkeler ve Türkiye |
| A5 | Duyarlılık: partner yaşı 10'dan küçük bildirilen kayıtlar çıkarılarak A1-A4 yeniden |
| B1 | Hızlı tanışma: "evet" oranı, partnerin yaş farkına göre (≤ −4, −3…−2, −1…+1, +2…+3, ≥ +4 yıl), cinsiyete göre. Kişinin genel seçiciliği çıkarılır (kişi içi ortalamadan sapma) |
| B2 | Hızlı tanışma: kişi içi doğrusal model; partner büyükse ve küçükse yıl başına "evet" olasılığı değişimi, ayrı ayrı. %95 aralık, kişiler üzerinden bootstrap (1000) |

**Ön kayıtlı testler**

| Test | Ölçüt |
|---|---|
| T1 | İki veri dosyasının SHA-256 özeti, ilk indirmede kaydedilen değerle eşleşir |
| T2 | A1, makaledeki değerleri ±0.05 içinde verir ve n = 8920 |
| T3 | D2: 8378 satır; cinsiyet yalnız "female" ve "male" |
| T4 | B1'de kişi içi merkezleme sonrası her kişinin ortalama sapması 0 (±10⁻⁹) |
| T5 | B2 eğimlerinin bootstrap standart hatası < 0.01 (yıl başına olasılık) |

**Karar kuralları**
- **K1:** Türkiye'de kadınların partneri ortalama olarak daha büyük, erkeklerinki daha küçük mü? %95 aralıklar 0'ı dışlarsa "evet".
- **K2:** Türkiye'deki cinsiyet farkı, 41 ülkenin ortancasından büyük mü?
- **K3:** Hızlı tanışmada partner yaşı "evet" kararını etkiliyor mu? B2 eğiminin %95 aralığı 0'ı dışlarsa "etkiliyor".
