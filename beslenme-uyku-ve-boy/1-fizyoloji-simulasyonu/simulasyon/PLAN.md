# Simülasyon Planı: Beslenme, İştah, Vücut Yağı, Uyku ve Boy (16-25 yaş)

> **Plan sürümü:** 1 · **Tarih:** 2026-10-07 · **Durum:** ön kayıt (kod yazılmadan ve çalıştırılmadan önce commit edildi)
>
> Bu dosya hiçbir simülasyon sonucu görülmeden yazıldı. Testler çalıştıktan sonra **ölçütler değiştirilmez.** Her değişiklik "Plandan sapmalar" tablosuna tarih ve gerekçesiyle yazılır.

## 1. Soru

Plakları henüz kapanmamış 16 yaşındaki bir gencin **ne yediği, ne kadar yediği, iştahı, vücut yağı ve uykusu**, ulaşacağı son boyu ne kadar değiştirir?

Alt sorular:

1. Bir diyetin gerçek besin içeriği (enerji, protein, yağ, doymuş yağ, karbonhidrat, kalsiyum, demir, çinko, D vitamini) nedir? Yiyecek adı yerine yiyeceğin **besin vektörü** kullanılır: "et" değil, "100 g'da 31 g protein, 3.6 g yağ, 1 mg çinko…".
2. Diyet, spor ve uyku değişince kilo, yağ kütlesi ve yağsız kütle nasıl değişir? İştah buna nasıl karşı koyar?
3. Bu değişiklikler büyüme plağına hangi yoldan ve ne büyüklükte ulaşır?
4. "Daha fazla protein/takviye boyu uzatır mı?" sorusuna model ne der, bu cevabın ne kadarı veri, ne kadarı varsayım?

**Kapsam dışı:** ilaç, hormon, hastalık tedavisi; 16 yaşından önceki beslenme; ergenliğin zamanlaması (16 yaşta çoğu gencin ergenliği büyük ölçüde tamamlanmış). Tam bir "anatomi simülasyonu" (organ organ) yapılmaz: büyüme sorusu için gereken katmanlar modellenir, gerisi kanıtsız ayrıntı ekler.

**Benzetme:** Büyüme plağı bir fabrika, besin ve enerji hammadde, iştah depo yöneticisi, vücut yağı depo, uyku da gece vardiyası. Soru şu: hammadde zaten yetiyorsa fazlası üretimi artırır mı, yetmiyorsa ne kadar düşürür, fabrika zaten kapanmaya yakınsa bunun önemi kalır mı?

## 2. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Her denklem yayınlanmış bir mekanizmaya ya da ölçüme dayanır; kaynağı yazılır. |
| S2 | Her parametre **ölçülmüş**, **kalibre** ya da **varsayım** diye sınıflanır. Her varsayım için duyarlılık analizi yapılır (bölüm 5). |
| S3 | Fiziksel tutarlılık kontrolleri kodda assert olarak bulunur: enerji korunumu, kütle korunumu (W = FM + FFM), FM > 0, FFM > 0, büyüme hızı ≥ 0, çarpanlar [0, 1] aralığında, zaman adımı yakınsaması. |
| S4 | **Tavan ilkesi (yapısal varsayım):** Beslenme ve uyku çarpanları en fazla 1'dir. Yani yeterli olanın fazlası büyümeyi hızlandırmaz. Bu bir test değil, modelin varsayımıdır ve raporda açıkça böyle yazılır. Bir senaryo referanstan **uzun** çıkarsa bu hata sayılır (assert). |
| S5 | Büyüme modeli yeniden kalibre edilmez. Boy uzaması 16-18 yaş araştırmasının sürüm 3 modeli (`model.simule_et`, `Senaryo.N`) ve spor araştırmasının sanal kohort fonksiyonu (`plak.kohort`) olduğu gibi kullanılır. |
| S6 | Sabit tohum (20261007), tek komut (`python calistir.py`), bütün sayılar `ciktilar/` altında. Dış veri (USDA) indirilir, SHA-256 ile doğrulanır, repoya konmaz. |
| S7 | Kanıt seviyesi: enerji katmanı yayınlanmış denklemlerden kurulur ve F2-F3 testleriyle yayınlanmış sonuçlara karşı denetlenir. Büyüme bağlantısı (bölüm 3.5) insan verisiyle doğrulanmamıştır, **D** etiketlidir. |
| S8 | **Şaşırtıcı sonuç önce hata sayılır.** Beklenmedik bir sayı çıkarsa yayından önce kod kontrol edilir; bulunan hata raporda yazılır. |

## 3. Model

Dört katman, tek yönde bağlı:

```
Besin sepeti (USDA)  →  Enerji ve protein alımı  →  Vücut bileşimi (FM, FFM)  →  Büyüme çarpanı N(t)  →  Büyüme plağı (sürüm 3)
                             ↑ iştah geri beslemesi ←──────┘
         Spor (METy) ─→ harcama ve enerji uygunluğu (EA)
         Uyku ───────→ alım (+kcal) ve isteğe bağlı büyüme çarpanı
```

### 3.1 Besin katmanı

- Kaynak: USDA FoodData Central, SR Legacy (2018-04), toplu CSV. SHA-256 `b80817294b8850530aaedf2e515c02593b1824f763a0ff356e5c2081643e6fd0`.
- Her yiyecek 100 g başına bir besin vektörüdür. Kullanılan besin kimlikleri: 1008 enerji (kcal), 1003 protein, 1004 toplam yağ, 1258 doymuş yağ, 1005 karbonhidrat, 1079 lif, 1087 kalsiyum, 1089 demir, 1095 çinko, 1114 D vitamini (µg).
- Diyet = gram/gün vektörü. Diyetin besin içeriği = Σ gram × (besin / 100 g).
- Sepet, senaryonun enerji alımına **orantılı ölçeklenir**: daha az yemek, aynı yiyeceklerden daha az yemek demektir. Böylece protein ve mikro besinler enerjiyle birlikte değişir.

Kullanılan yiyecekler (fdc_id): kıyma 80/20 pişmiş 171797; tavuk göğsü pişmiş 171477; yumurta 171287; süt (tam yağlı, D katkılı) 171265; yoğurt 171284; beyaz peynir (feta) 173420; somon pişmiş 175168; hamsi 174182; tereyağı 173410; mercimek haşlanmış 172421; nohut haşlanmış 173757; kuru fasulye haşlanmış 175203; ekmek (buğday) 172686; pirinç pişmiş 168878; bulgur pişmiş 170287; makarna pişmiş 169737; patates haşlanmış 170438; domates 170457; ıspanak 168462; elma 171688; muz 173944; salatalık 168409; portakal 169097; zeytinyağı 171413; ceviz 170187; kola 174852; şeker 169655; hamburger 170694; cips 169677.

**Sepetler** (gram/gün; ölçeklenmeden önceki hali):

| Sepet | İçerik (g/gün) |
|---|---|
| **B1 Dengeli** | ekmek 200, bulgur 150, pirinç 100, patates 150, mercimek 150, nohut 100, tavuk 80, yumurta 50, süt 250, yoğurt 200, beyaz peynir 40, domates 150, salatalık 100, ıspanak 80, elma 150, portakal 150, muz 100, zeytinyağı 30, ceviz 20, şeker 20 |
| **B2 Fast food ağırlıklı** | hamburger 300, cips 100, kola 660, ekmek 100, pirinç 150, tavuk 50, süt 100, tereyağı 15, şeker 30, elma 100, domates 50 |
| **B3 Düşük protein** (uç örnek: hayvansal ürün ve baklagil yok) | ekmek 200, pirinç 250, patates 300, şeker 70, zeytinyağı 60, domates 200, salatalık 150, elma 200, muz 150, kola 500, portakal 150 |
| **B4 Yüksek protein** | B1, şu değişikliklerle: tavuk 250, yumurta 100, süt 400, yoğurt 300, ekmek 100, şeker 0, zeytinyağı 20 |
| **B5 Etsiz** | B1, şu değişikliklerle: tavuk 0, mercimek 250, nohut 150, yumurta 100 |

Not: Türkiye'de süt genellikle D vitamini katkılı değildir. USDA kaydındaki D vitamini değeri ABD katkılı sütü yansıtır; raporda bu fark yazılır.

### 3.2 Enerji harcaması

| Bileşen | Denklem | Sınıf | Kaynak |
|---|---|---|---|
| Bazal metabolizma (BMR) | Schofield (ağırlık + boy), kcal/gün. Erkek 10-18: 16.6W + 77H + 572; 18-30: 15.4W − 27H + 717. Kız 10-18: 7.4W + 482H + 217; 18-30: 13.3W + 334H + 35 (W kg, H m) | Ölçülmüş (regresyon) | FAO/WHO/UNU 1985, Annex 1 |
| 18 yaş geçişi | 17.5-18.5 yaş arasında iki denklem doğrusal harmanlanır (denklem değişiminde yapay sıçrama olmasın diye) | Uygulama ayrıntısı | – |
| Toplam harcama (TEE) | TEE = BMR × PAL_taban + EEE_net | – | – |
| PAL_taban | 1.55 (az hareketli ergen) | **Varsayım** | Duyarlılık: 1.40 / 1.70 |
| Spor harcaması | EEE_net = (METy − 1.4) × BMR/24 × saat/gün. Spor, oturarak ders çalışmanın (METy 1.4) yerine geçer | Ölçülmüş (METy) | Youth Compendium 2017, ek dosya 4 (16-18 yaş) |
| METy değerleri | Futbol maçı 8.7; basketbol maçı 7.5; koşu (serbest tempo) 9.8; şınav 4.1; el ağırlıkları 2.9; ders çalışma 1.4; sessizce uzanma 1.1 | Ölçülmüş | Aynı. METy, Schofield BMR'ye bölünerek tanımlandığı için bu modelle tutarlı |

### 3.3 Vücut bileşimi (yağ kütlesi FM, yağsız kütle FFM)

- Enerji dengesi: dE/dt = EI − TEE (kcal/gün). Zaman adımı 1 gün (Euler; Euler bu denklemde enerjiyi tam korur).
- Değişimin bölüşümü (Forbes eğrisinin türevi): dFFM/dW = 10.4 / (10.4 + FM). **Ölçülmüş** (Hall 2007, 2008).
- Enerji yoğunlukları: yağ ρF = 39.5 MJ/kg = 9441 kcal/kg; yağsız doku ρL = 7.6 MJ/kg = 1816 kcal/kg. **Ölçülmüş/türetilmiş** (Hall 2008).
- Böylece ΔW = ΔE / [p·ρL + (1 − p)·ρF], p = 10.4/(10.4 + FM).
- Başlangıç (16 yaş):
  - Boy H0: sanal kohortta modelin 16 yaş boyu.
  - BMI0: log-normal, medyan 21, log-SD 0.13, [16, 32] aralığına kırpılır. **Varsayım.** W0 = BMI0 · H0².
  - Yağ yüzdesi: Deurenberg 1991 çocuk denklemi, BF% = 1.51·BMI − 0.70·yaş − 3.6·cinsiyet + 1.4 (erkek = 1), [5, 45] aralığına kırpılır. **Ölçülmüş** (≤ 15 yaş için türetilmiş; 16 yaşa bir yıl dışa uzatma, sınırlama olarak yazılır).
- Büyümeye eşlik eden doku: "set noktası" ağırlığı W_set(t) = W0 · (H(t)/H0)² (BMI sabit). Bu dokuyu yapmanın enerjisi referans alıma eklenir. **Varsayım** (16 yaş sonrası boy artışı küçük olduğu için etkisi ihmal edilebilir; çıktıda ayrıca kcal/gün olarak raporlanır).

### 3.4 Alım ve iştah

```
EI(t) = EI_ref(t) + Δ_senaryo(t) + k · (W_set(t) − W(t))
EI_ref(t) = BMR(W_set, H, yaş) × PAL_taban + büyüme dokusu maliyeti   [+ EEE_net, yalnızca "spora göre yiyen" senaryolarda]
```

- S0'da (Δ = 0) kişi set noktasında kalır: kilo değişmez (yalnızca boyla birlikte BMI sabit büyür). **Varsayım:** Gerçek ergenlerde 16-21 yaşta kilo artar; senaryolar S0'a göre fark olarak raporlandığı için bu, farkları çok az etkiler.
- **İştah geri beslemesi:** k = 100 kcal/gün, kaybedilen her kg için. **Ölçülmüş** (Polidori 2016, yetişkin, SGLT2 deneyi). Ergenlere uygulanması **varsayım**.
- Kilo **artışında** iştahın aynı güçle azalıp azalmadığı bilinmiyor. Ana model: simetrik (k = 100 her iki yönde). Duyarlılık: artışta k = 0 (yalnızca kayıpta geri besleme) ve her iki yönde k = 0 (sabit alım, Hall tarzı).
- EI ≥ 0'a kırpılır.

### 3.5 Büyüme bağlantısı (D: insan verisiyle doğrulanmamış)

Sürüm 3 modelinde beslenme, büyüme hızını çarpan olarak etkiler: v_j = G_j · I^α_j · **N(t)** · S_j^γ · Φ(S_j). N plak çıktısını düşürdüğünde kullanıma bağlı stok tükenmesi de yavaşlar (yakalama mekanizması). Östrojene bağlı tükenme ise devam eder. Aynı N, her iki bölmeye (bacak, gövde) uygulanır.

```
N(t) = min( N_E(EA), N_P ) × N_uyku
```

**a) Enerji uygunluğu (EA).** EA = (EI − EEE_brüt) / FFM, kcal/kg FFM/gün. EEE_brüt = METy × BMR/24 × saat.

| Varyant | Biçim | Sınıf |
|---|---|---|
| **Eşik (ana)** | EA ≥ 30: N_E = 1; 30 → 20 arasında doğrusal düşüş; EA ≤ 20: N_E = N_min | Eşikler ölçülmüş (Loucks & Thuma 2003: LH ritmi 30'un altında bozuluyor; Ihle & Loucks 2004: IGF-I, T3 ve osteokalsin 20-30 arasında ani düşüyor). N_min **varsayım** |
| Doğrusal | EA ≥ 45: N_E = 1; 45 → 10 arasında 1'den 0.5'e doğrusal; altında 0.5 | **Varsayım** (kötümser: hafif açığı da cezalandırır) |

- N_min = 0.5 (ana), duyarlılık: 0.3 / 0.8.
- **Sınırlama:** Eşikler genç yetişkin kadınlarda ölçüldü. Erkeklere ve 16 yaşa aynen uygulanması varsayım.

**b) Protein.** Günlük protein P = sepetin protein/kcal oranı × EI.

- Bireysel ihtiyaç R_i = EAR × W × r_i. EAR: erkek 0.73, kız 0.71 g/kg/gün (DRI, 14-18 yaş). r_i ~ Normal(1, 0.12) **varsayım** (EAR'dan RDA'ya geçişte kullanılan tipik değişkenlik).
- P ≥ R_i ise N_P = 1. Altında N_P = max(0, 1 − b · (1 − P/R_i)).
- b = 1 (ana: ihtiyacın %10 altı, büyümenin %10 altı), duyarlılık 0.5 / 2. **Varsayım.**
- EAR, 18 yaştan sonra da 14-18 değeriyle kullanılır (müdahale 16-18 arasında; sonrasında herkes B1 sepetine döner).

**c) Uyku.**

- Kısa uyku → alım +385 kcal/gün. **Ölçülmüş** (Al Khatib 2017 meta-analizi; çoğunlukla yetişkin). Harcamada anlamlı değişiklik bulunmadığı için harcama değiştirilmez. Duyarlılık: uyanık kalınan sürenin oturarak geçmesiyle mekanik ek harcama (METy 1.4 − 1.1).
- Normal aralıkta uyku süresinin büyümeye doğrudan etkisi: N_uyku = 1 (ana). Kötümser varyant 0.95. **Varsayım:** Sağlıklı ergende bu etkiyi ölçen çalışma bulunamadı.
- Tedavi edilmemiş uyku bozukluğu (uyku apnesi gibi): N_uyku = 0.9, duyarlılık 0.8 / 0.95. **Varsayım:** Yönü, çocuklarda ameliyat sonrası boy ve IGF-1 artışından (Bonuck meta-analizi, boy SMD 0.34) gelir; büyüklüğü bilinmiyor.

**d) Mikro besinler (kalsiyum, demir, çinko, D vitamini).** Büyüme çarpanına **bağlanmaz**. Eksikliğin boya etkisini 16 yaş ve sonrası için sayıya çevirecek bir kaynak yok. Her sepet için RDA'nın yüzdesi raporlanır (DRI 14-18: Ca 1300 mg; Fe erkek 11 / kız 15 mg; Zn erkek 11 / kız 9 mg; D vitamini 15 µg). Uydurma bir çarpan eklemek sahte kesinlik olurdu.

**e) Mekanik etki:** Spor araştırması (sürüm 1) egzersizin plağa mekanik etkisinin < 0.5 mm olduğunu buldu. Burada eklenmez.

### 3.6 Çözüm düzeni

1. Kohort: `plak.kohort(cinsiyet, 2000, rng)`, cinsiyet başına 2000 kişi, Türk uyarlamalı.
2. 1. geçiş: N = 1 ile büyüme → H_ref(t), 16-25 yaş.
3. Enerji/vücut bileşimi modeli H_ref(t) ile günlük adımla çözülür → EA(t), P(t), N(t).
4. 2. geçiş: `model.simule_et(..., senaryo=Senaryo(N=…))` (RK2, Δt = 0.02 yıl). N(t), günlük seriden RK2 zaman noktalarına doğrusal aradeğerlenir.
5. Bağlantı zayıf olduğu için (boy değişimi BMR'yi < 1 kcal/gün değiştirir) tek iterasyon yeterli olmalı. Bu, ikinci bir iterasyonla kontrol edilir (F4).
6. Müdahale 16.0-18.0 yaş arasındadır; 18'de herkes S0 koşullarına döner. Boy 18 ve 25 yaşta ölçülür. Fark, aynı kişinin S0 değeriyle eşleştirilerek hesaplanır.

### 3.7 Senaryolar (16.0-18.0 yaş)

| # | Senaryo | Sepet | Δ_senaryo | Spor | Uyku |
|---|---|---|---|---|---|
| S0 | Referans | B1 | 0 | yok | 8.5 sa |
| S1 | Diyet −500 kcal | B1 | −500 | yok | 8.5 |
| S1b | Sert diyet −1000 kcal | B1 | −1000 | yok | 8.5 |
| S2 | Yoğun spor, yemeği artırmıyor | B1 | 0 (telafi yok, yalnızca iştah; düzeltme 1) | futbol 2 sa/gün, 6 gün/hafta | 8.5 |
| S2b | Yoğun spor + kilo vermeye çalışıyor | B1 | −500 (düzeltme 1) | S2 gibi | 8.5 |
| S3 | Yüksek protein (aynı enerji) | B4 | 0 | yok | 8.5 |
| S4 | Düşük protein (aynı enerji) | B3 | 0 | yok | 8.5 |
| S5 | Fast food + fazla yeme | B2 | +500 | yok | 8.5 |
| S6 | Kısa uyku | B1 | +385 | yok | 6 sa |
| S7 | Tedavi edilmemiş uyku bozukluğu | B1 | 0 | yok | N_uyku = 0.9 |
| S8 | Yoğun spor + yeterli beslenme | B1 | 0 (EI_ref içinde EEE_net var) | S2 gibi | 8.5 |
| S9 | Etsiz | B5 | 0 | yok | 8.5 |

Raporlanacak çıktılar (cinsiyet ve senaryo başına): 18 ve 25 yaşta boy farkı (medyan, %5-%95), 18 yaşta kilo, yağ yüzdesi ve BMI değişimi, en düşük EA, protein (g/kg), sepetlerin makro/mikro besin profili (RDA yüzdesi, enerjinin yağdan ve doymuş yağdan gelen yüzdesi), "yakalama oranı" (18'deki açığın 25'e kadar kapanan kısmı).

## 4. Ön kayıtlı testler

| # | Test | Geçme ölçütü |
|---|---|---|
| **F1** | Enerji korunumu: Σ(EI − TEE)·Δt ile ρF·ΔFM + ρL·ΔFFM karşılaştırması, bütün senaryolar ve kişiler | Göreli hata < %0.1 (Σ\|EI − TEE\|·Δt'ye göre) |
| **F2** | Harcama gerçeğe yakın mı? 16 yaş medyan erkek (kohort medyan W ve H), PAL 1.55: model TEE'si ile IOM EER (erkek 9-18: 88.5 − 61.9·yaş + PA·(26.7·W + 903·H) + 25, "az aktif" PA = 1.13) | Fark ±%10 içinde |
| **F3** | Kilo dinamiği Hall 2011 ile uyumlu mu? Fazla kilolu yetişkin benzeri kişi (erkek, 25 yaş, H 1.75 m, W 90 kg, FM 27 kg, PAL 1.55, iştah geri beslemesi kapalı), alım +100 kJ/gün (23.9 kcal) sabit artış | (a) 10 yılda kilo artışı 0.8-1.25 kg; (b) yarılanma süresi 0.4-1.2 yıl |
| **F4** | Sayısal yakınsama | (a) Enerji modelinde Δt = 1 gün ile 0.5 gün arasında 18 yaş kilo farkı < 0.05 kg; (b) RK2 Δt ile Δt/2 arasında son boy farkı < 0.01 cm; (c) ikinci iterasyonla boy farkı < 0.01 cm |
| **F5** | Sıfır kontrolü: S0'da N ≡ 1 iken boy, sürüm 3 modelinin senaryosuz çıktısıyla aynı | Fark < 1e-9 cm |

**Şeffaflık notu:** F2 ve F3 için plan yazılırken kâğıt-kalem tahmini yapıldı: F2 için model ≈ 2660, EER ≈ 2740 kcal (yaklaşık −%3). F3 için eğim ≈ 24 kcal/kg/gün, nihai artış ≈ 1 kg, yarılanma ≈ 0.6 yıl. Bu yüzden F2 ve F3 tamamen kör değildir. Bu testler denklemlerin doğru kodlandığını ve modelin yayınlanmış sonuçlarla aynı büyüklükte olduğunu sınar. Büyüme bağlantısını (3.5) doğrulamazlar; o kısım için kullanılabilir insan verisi yok.

**F3 ölçütünün gerekçesi:** Hall 2011'e göre her 100 kJ/gün değişiklik sonunda ~1 kg değişim getirir; değişimin yarısı ~1 yılda, %95'i ~3 yılda gerçekleşir. Tek üstel eğride %95'in 3 yılda tamamlanması zaman sabitinin ~1 yıl, yarılanmanın ~0.7 yıl olması demektir. "~1 yıl" ifadesi yaklaşık olduğu için aralık geniş tutuldu.

### Karar kuralları (yorum önceden sabit)

| # | Kural |
|---|---|
| K1 | Son boy (25 yaş) farkının medyanı: **≥ 0.5 cm** "fark edilir etki"; **0.1-0.5 cm** "ölçülemeyecek kadar küçük" (boy ölçüm hatası ~0.3-0.5 cm); **< 0.1 cm** "etki yok". |
| K2 | Sonuç, bölüm 5'teki bütün varyantlarda aynı K1 sınıfında kalıyorsa **sağlam**, sınıf değişiyorsa **varsayıma bağlı** diye yazılır. Hangi varsayıma bağlı olduğu belirtilir. |
| K3 | Sürüm 3'te yakalama büyümesi testi kaldı (model yakalamayı olduğundan zayıf gösteriyor). Bu yüzden 25 yaştaki kayıplar **üst sınır** sayılır. 18 yaştaki açık ayrıca raporlanır. |
| K4 | Bir senaryo S0'dan uzun çıkarsa (S4 tavan ilkesi gereği imkânsız) bu bir koddaki hata sayılır, assert ile durdurulur. |

## 5. Duyarlılık analizi

| Varsayım | Ana | Varyantlar |
|---|---|---|
| N_E biçimi | eşik | doğrusal |
| N_min | 0.5 | 0.3, 0.8 |
| Protein eğimi b | 1 | 0.5, 2 |
| Protein ihtiyacı değişkenliği (CV) | 0.12 | 0.08, 0.16 |
| İştah k (artış yönü / kayıp yönü) | 100 / 100 | 0 / 100; 0 / 0 |
| PAL_taban | 1.55 | 1.40, 1.70 |
| S6 uyku: N_uyku ve ek harcama | 1, yok | 0.95; mekanik ek harcama |
| S7 N_uyku | 0.9 | 0.8, 0.95 |
| Başlangıç BMI medyanı | 21 | 18.5, 25 |

Her varyant tek tek değiştirilir (bir seferde bir varsayım); ayrıca en kötümser kombinasyon (doğrusal N_E, N_min 0.3, b = 2, k = 0/0) bir kez hesaplanır.

## 6. Önceden bilinen sınırlamalar

- Büyüme bağlantısının (3.5) biçimi ve büyüklüğü varsayımdır. 16+ yaşta beslenme ile boy arasındaki ilişkiyi ölçen müdahale verisi bulunamadı.
- EA eşikleri yetişkin kadınlardan geliyor. İştah katsayısı ilaçla kilo veren yetişkinlerden geliyor. Uyku-alım etkisi çoğunlukla yetişkinlerden geliyor.
- Sürüm 3 modeli yakalama büyümesini zayıf gösteriyor (Ö5b kaldı). Kalıcı kayıplar abartılmış olabilir.
- Yağ dokusunun östrojen üretimi (aromataz) ile plak kapanmasını hızlandırma ihtimali modellenmez. 16+ yaş için sayısal kaynak yok.
- Mikro besin eksikliklerinin büyümeye etkisi sayıya çevrilmez.
- Kohortun BMI dağılımı varsayımdır (Türk ergen BMI referansı bu sürümde indirilmedi).

## 7. Plandan sapmalar

| Tarih | Ne değişti | Neden | Sonuçlar görüldükten sonra mı? |
|---|---|---|---|
| 2026-10-07 | **Düzeltme 1.** S2'de Δ_senaryo = −EEE_net yerine **0**; S2b'de −EEE_net − 500 yerine **−500** | Plan hatası: 3.4'te EI_ref, spor harcamasını yalnızca "spora göre yiyen" senaryoda (S8) içeriyor. Spor harcaması zaten TEE'ye ekleniyor. Yani "telafi yok" demek Δ = 0 demek. −EEE_net, açığı iki kez saymak olurdu: kişi spora başlayınca öncekinden daha az yemiş olurdu | Hayır. Kod yazılmadan önce fark edildi |
| 2026-10-07 | **Uygulama ayrıntıları** (kod yazılmadan önce sabitlendi): (a) r_i = 1 + CV·z, z ~ N(0,1) kişi başına bir kez çekilir, [0.5, 1.5] aralığına kırpılır; CV varyantları aynı z'yi kullanır. (b) En kötümser kombinasyonda doğrusal N_E'nin tabanı 0.5 yerine 0.3 (N_min = 0.3 ile tutarlı). (c) F4a ve F4b-c, en dinamik senaryo olan S2b'de, bütün kişiler üzerinde en büyük mutlak farkla değerlendirilir. (d) Bir yiyecekte D vitamini kaydı yoksa 0 sayılır, eksik kayıt sayısı çıktıda raporlanır. (e) FM0 = W0 · BF%/100. (f) F3'te yarılanma süresi, artışın 10 yıllık değerinin yarısına ilk ulaşıldığı gün. (g) S6'nın "mekanik ek harcama" varyantı: 2.5 sa/gün × (1.4 − 1.1) × BMR/24. (h) F1'in paydası max(Σ\|EI − TEE\|·Δt, 1 kcal) | Planın açık bıraktığı noktalar | Hayır |
| 2026-10-07 | **Kod hatası 1.** 25 yaş anlık kaydı alınmıyordu: günlük adımın son günü 24.9993 yaşa düşüyor | Son adımda eksik anlık kayıtlar da alınıyor. Sonuç sayısı üretilmeden önce program durdu | Hayır (çıktı üretilmeden çöktü) |
| 2026-10-07 | **Sapma 2: K4 toleransı 1e-9 cm → 1e-4 cm (0.001 mm).** S2'de bazı kişiler referanstan en fazla **+1.7·10⁻⁷ cm** uzun çıktı, K4 assert'i durdurdu | İnceleme: Kod hatası değil, modelin kendi doğrusal olmama özelliği. Plağı neredeyse kapanmış kişide kısa süreli N < 1, kullanıma bağlı stok tükenmesini yavaşlatıyor. Kaynaşma kapısı Φ(S) çok dik olduğu için korunan küçük stok, toplam büyümeyi ihmal edilebilir miktarda artırabiliyor. Planda "tavan ilkesi gereği imkânsız" demek yanlıştı: tavan ilkesi N ≤ 1'i garanti eder, son boyun her zaman kısalmasını değil. Görülen en büyük pozitif fark `ozet.json`'a yazılır | **Evet.** Tanı çıktısı görüldükten sonra (S1, S2, S2b, S7 için en büyük, en küçük ve medyan farklar). Hiçbir F testi ölçütü ya da K1-K3 eşiği değişmedi |
| 2026-10-07 | **Sapma 3: K4 yalnızca S0 tavandayken (bütün kişilerde N ≡ 1) assert edilir.** Öbür durumlarda "referanstan uzun çıkan" kişiler `K4_S0_kisitli_varyantlar.csv` dosyasına yazılır | "N_E doğrusal" varyantında S5 (fast food, +500 kcal) bazı kişilerde referanstan uzun çıktı. Neden: Bu varyant 45'in altındaki her EA'yı cezalandırıyor, bu yüzden S0'da normal yiyen bazı kişilerin N'si de 1'in altında. Daha çok yiyen kişinin N'si S0'dakinden yüksek. Bu, kod hatası değil, varsayımın sonucu ve raporda yazılır | **Evet.** Yalnızca assert mesajı görüldükten sonra. Hiçbir F testi ölçütü değişmedi |
| 2026-10-07 | **Sapma 4: İştah kapalı (k = 0) varyantlarda doku tükenmesi "sürdürülemez" diye kaydedilir; her senaryoda 18 yaşta BMI < 16 (DSÖ ağır zayıflık sınırı) yüzdesi raporlanır. Ayrıca keşifsel bir varyant eklendi: zayıf iştah, k = 25** | "k = 0 (sabit alım)" varyantında, iki yıl süren −500 kcal açıkta bile erkeklerde 18 yaş BMI medyanı 14.8'e iniyor. Kızlarda S1, S1b, S2 ve S2b'de yağsız doku sıfırın altına düşüp S3 assert'ini tetikledi. Fizik doğru (Hall tipi sabit alımda 500 kcal/gün sonunda ~20 kg kayıp demek), ama böyle bir genç tıbben acil durumdadır, boy sorusu anlamını yitirir. Ana modelde (k > 0) assert durdurucu kalır. Keşifsel k = 25 varyantı sonuçlar görüldükten sonra eklendi, K2 sınıflamasına girmez, ayrı dosyada raporlanır | **Evet.** Assert ve tanı çıktısı (erkek ve kızlarda S1, S1b, S2, S2b için 18 yaş kilo/BMI) görüldükten sonra. Hiçbir F testi ölçütü değişmedi |

## Kaynaklar

- [USDA FoodData Central, SR Legacy (2018-04), toplu CSV](https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip)
- [FAO/WHO/UNU 1985, Energy and protein requirements, Annex 1 (Schofield denklemleri)](https://www.fao.org/4/AA040E/AA040E15.htm)
- [Butte ve ark. 2018, A Youth Compendium of Physical Activities (PMC5768467)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5768467/). METy değerleri ek dosya 4'ten (mss-50-246-s006.xlsx, Europe PMC ek dosya paketi; dosya SHA-256 `5aa040041d36bae88e908c851f7a7464044e269cd4dcb31c714497dd38139417`).
- [Hall 2008, What is the required energy deficit per unit weight loss? (PMC2376744)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2376744/): ρF 39.5, ρL 7.6 MJ/kg; 10.4 katsayısı
- [Hall ve ark. 2011, Quantification of the effect of energy imbalance on bodyweight, Lancet](https://pubmed.ncbi.nlm.nih.gov/21872751/)
- [Polidori ve ark. 2016, How strongly does appetite counter weight loss? (PMC5108589)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5108589/): ~100 kcal/gün/kg
- [Deurenberg ve ark. 1991, Body mass index as a measure of body fatness, Br J Nutr](https://doi.org/10.1079/bjn19910073)
- [Loucks & Thuma 2003, LH pulsatility and energy availability, JCEM](https://pubmed.ncbi.nlm.nih.gov/12519869/)
- [Ihle & Loucks 2004, Dose-response relationships between energy availability and bone turnover, JBMR](https://pubmed.ncbi.nlm.nih.gov/15231009/)
- [Al Khatib ve ark. 2017, The effects of partial sleep deprivation on energy balance, Eur J Clin Nutr](https://doi.org/10.1038/ejcn.2016.201)
- [Institute of Medicine, Dietary Reference Intakes (NAP)](https://nap.nationalacademies.org/catalog/10490)
- Bonuck ve ark., adenotonsillektomi sonrası büyüme meta-analizi (boy SMD 0.34, IGF-1 SMD 0.53). Bağlantı rapor aşamasında eklenecek.
