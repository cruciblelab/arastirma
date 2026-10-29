# Simülasyon Planı: "Rüyam Çıktı" Tesadüfleri

> **Plan sürümü:** 1 · **Tarih:** 2026-10-29 · **Durum:** ön kayıt (kod yazılmadan ve çalıştırılmadan önce commit edildi)
>
> Bu dosya sonuçlar görülmeden yazılıp commit edildi. Testler çalıştıktan sonra **ölçütler değiştirilmez.** Her değişiklik "Plandan sapmalar" tablosuna gerekçesiyle yazılır.

## 1. Soru

Rüyalar geleceği **hiç göstermese bile** "rüyamda kötü bir şey gördüm, birkaç gün sonra kötü bir şey oldu" deneyimi ne sıklıkla yaşanır? Seçici hatırlama, rüyaların "isabet oranını" ne kadar şişirir?

**Sıfır hipotezi modelin kendisidir:** Rüyalar ve olaylar birbirinden tamamen bağımsız üretilir. Model, kehanet olmayan bir dünyada ne kadar "kehanet" yaşanacağını sayar.

**Benzetme:** Her gece zar atan biri, yeterince gece atarsa "çift altı"yı mutlaka görür. Zarın bir şey bildiğini değil, çok sayıda atış yapıldığını gösterir.

## 2. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Her parametre **ölçülmüş** (kaynaklı), **varsayım** ya da **veriden** (aynı sürümdeki DreamBank analizi) diye sınıflanır. Varsayımlar için duyarlılık ızgarası zorunlu |
| S2 | Rüya ve olay süreçleri **bağımsızdır** (kehanet yok). Bu, kodda test edilir (T2) |
| S3 | Testler ve geçme ölçütleri bu planda sabittir. Sonuç ne olursa olsun raporlanır |
| S4 | Sabit tohum (20261029), tek komut, çıktılar `ciktilar/` altında. Model sonuçlarının kanıt düzeyi D |
| S5 | Kullanıcıya ait kişisel bir örnek modele ya da rapora girmez |

## 3. Model

Bir kişinin 365 günü simüle edilir. Gece n'de görülen rüya, gün n'den önce gelir.

| Süreç | Tanım |
|---|---|
| Hatırlanan rüyalar | Gece başına Poisson(r / 7); r = haftada hatırlanan rüya sayısı |
| Olumsuz rüya | Her hatırlanan rüya p_neg olasılıkla olumsuz/tehditkâr içerikli |
| Belirgin olumsuz olay | Her gün p_e olasılıkla (günde en fazla 1) |
| Pencere | Olay günü d için rüya penceresi: d−W+1 … d gecelerinin rüyaları (W gün) |
| Eşleşme gevşekliği | Bir olumsuz rüya ile bir olumsuz olay s olasılıkla "aynı şey" diye eşleştirilir (s = 1: her olumsuz rüya her olumsuz olaya bağlanabilir, sembolik yorum; s = 0.1: yalnızca konusu tutan, birebir yorum) |
| Seçici hatırlama | Olaydan sonra, eşleşen bir rüya m_hit olasılıkla hatırlanır. Hiçbir olayla eşleşmeyen olumsuz bir rüya m_miss olasılıkla hatırlanır |

**Çıktılar:**

| Kod | Çıktı | Tanım |
|---|---|---|
| O1 | Yılda "rüyam çıktı" sayısı | Pencerede en az bir olumsuz rüyası olan, bu rüya olayla eşleşen **ve** hatırlanan olay sayısı. Her (rüya, olay) çifti s · m_hit olasılıkla bağımsız |
| O2 | P(yılda ≥ 1) | Kişilerin yüzde kaçı yılda en az bir kez "rüyam çıktı" yaşar |
| O3 | Milyon kişide günlük | 10⁶ · E[O1] / 365 |
| O4 | Gerçek isabet oranı | Olumsuz rüyaların yüzde kaçının ardından sonraki W gün içinde eşleşen bir olay geliyor. Analitik değer: 1 − Σ_k P(k olay) (1 − s)^k |
| O5 | Algılanan isabet oranı | Hatırlanan doğrulanmış rüyalar / tüm hatırlanan olumsuz rüyalar = m_hit·c / (m_hit·c + m_miss·(1−c)), c = O4 |

**Parametreler:**

| Parametre | Temel değer | Izgara | Sınıf ve kaynak |
|---|---|---|---|
| r (haftada hatırlanan rüya) | 1 | 0.25, 1, 2, 5 | Ölçülmüş: temsili Alman örnekleminde ortalama ~haftada 1 (Schredl 2008, özet); çok hatırlayanlarda ~5 (Eichenlaub 2014) |
| p_neg (olumsuz rüya oranı) | 0.33 | 0.20, 0.33, 0.50, 0.72 | Ölçülmüş/ikincil: en az bir talihsizlik içeren rüya ~1/3 (Hall ve Van de Castle normları, ikincil); en az bir tehdit %72 (Revonsuo ve Valli 2000). Ek senaryo: aynı sürümdeki DreamBank analizinden çıkan oran (bkz. README, D1) |
| p_e (belirgin olumsuz olay olasılığı, gün başına) | 0.10 | 0.03, 0.10, 0.20, 0.40 | **Varsayım** (ayda ~3 belirgin kötü olay). Üst uç 0.40, "en az bir stres etkeni olan gün" oranı (Almeida ve ark. 2002, özet) |
| W (pencere, gün) | 7 | 1, 3, 7, 14 (yalnız temel senaryoda) | Varsayım. Kişisel olarak önemli olaylar rüyada 1-2 ve 5-7 gece sonra yeniden beliriyor (rüya gecikmesi etkisi) |
| s (eşleşme gevşekliği) | 1.0 | 1.0, 0.3, 0.1 | Varsayım (sembolik ve birebir yorum uçları) |
| m_hit / m_miss | 0.52 / 0.215 | sabit | Ölçülmüş: doğrulanan rüya-olay çiftlerinin 4'te 2.09'u, doğrulanmayanların 4'te 0.86'sı hatırlandı (Watt ve ark. 2014, tam metin) |
| Kişi sayısı | 100 000 (temel) | 2 000 (ızgaranın her senaryosu) | — |

Izgara: r × p_neg × p_e × s = 4 × 4 × 4 × 3 = **192 senaryo** (W = 7). Ayrıca temel senaryoda W taraması.

## 4. Ön kayıtlı testler

| Test | Ölçüt |
|---|---|
| T1 | Temel senaryoda simüle edilen gerçek isabet oranı (O4) ile analitik değer arasındaki fark < 0.005 |
| T2 | Bağımsızlık kontrolü (temel senaryo): olumsuz rüyalı geceyi izleyen günde olay olasılığı ile rastgele bir günde olay olasılığı arasındaki farkın %95 aralığı 0'ı içerir |
| T3 | Aynı tohumla iki çalıştırma, temel senaryo çıktıları birebir aynı |
| T4 | p_e = 0 iken O1 = 0; s = 0 iken O1 = 0 |

## 5. Karar kuralları

| Kural | Soru | Karar |
|---|---|---|
| K1 | Temel senaryoda kehanet olmadan "rüyam çıktı" yaygın mı? | O2 ≥ 0.5 → "insanların çoğu, hiçbir kehanet olmadan yılda en az bir kez yaşar"; değilse → "yaygın değil" |
| K2 | Bu sonuç varsayımlara ne kadar bağlı? | 192 senaryonun yüzde kaçında O2 ≥ 0.5; bu oran ve hangi parametrelerde düştüğü raporlanır |
| K3 | Seçici hatırlama isabeti şişiriyor mu? | Temel senaryoda O5 / O4 ≥ 1.5 → "evet, belirgin"; değilse → "sınırlı" |
| K4 | Toplumda ölçek | O3 (milyon kişide günde) raporlanır; ≥ 100 → "her gün yüzlerce" |
| K5 | Birebir yorumda (s = 0.1) temel senaryo O2 | Raporlanır ve s = 1 ile karşılaştırılır (yorumun gevşekliğinin etkisi) |

## 6. Plandan sapmalar

| Sapma | Gerekçe |
|---|---|
| (henüz yok) | |
