# Simülasyon Planı: Egzersiz ve Boy (16 yaş ve sonrası)

> **Plan sürümü:** 1 · **Tarih:** 2026-10-07 · **Durum:** ön kayıt (testler çalıştırılmadan önce commit edildi)
>
> Bu dosya kod sonuçları görülmeden yazılıp commit edildi. Testler çalıştıktan sonra **ölçütler değiştirilmez.** Her değişiklik "Plandan sapmalar" tablosuna gerekçesiyle yazılır.

## 1. Soru

Barfiks, şınav, esneme, asılma/ters asılma, koşu, basketbol ve ağırlık gibi egzersizler 16 yaş ve sonrasında **gerçek boyu** değiştirir mi?

Boy üç ayrı şeyle değişebilir. Bunlar birbirine karıştırılmamalı, bu yüzden modelde ayrı katmanlar:

| Katman | Ne | Kalıcı mı? |
|---|---|---|
| **A. Kemik uzunluğu** | Büyüme plaklarında mekanik yükün büyüme hızına etkisi (Hueter-Volkmann yasası) | Evet |
| **B. Omurga diskleri** | Yük altında disklerin su kaybedip incelmesi, yük kalkınca şişmesi (viskoelastik sünme) | Hayır, saatler içinde geri döner |
| **C. Duruş** | Sırt eğriliğinin (kifoz) ölçülen boya geometrik etkisi | Duruş korundukça |

Ek olarak:
- **D. Seçilim yanılgısı:** Basketbolcular neden uzun? Antrenman mı, seçilim mi?

**Benzetme:**
- **A** bir binanın kat sayısı: inşaat bitmeden değişebilir.
- **B** bir yatağın yaylarının akşam çökmesi ve sabah düzelmesi.
- **C** binanın dik mi eğik mi durduğu.

## 2. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Her denklem literatürde gösterilmiş bir mekanizmaya dayanır; kaynağı yazılır. |
| S2 | Her parametre **ölçülmüş**, **kalibre** ya da **varsayım** diye sınıflanır. Varsayımlar için duyarlılık analizi zorunlu. |
| S3 | Fiziksel tutarlılık kontrolleri kodda assert olarak bulunur: büyüme hızı ≥ 0, kalıcı etki yalnızca A katmanından gelir, zaman adımı yakınsaması. Ayrıca A katmanı, çarpanlar 1 iken sürüm 3 modeliyle aynı sonucu vermeli. |
| S4 | Testler ve geçme ölçütleri bu planda sabittir. Sonuç ne olursa olsun raporlanır. |
| S5 | **Üst sınır ilkesi:** Belirsiz parametrelerde, egzersize **en çok etki** veren uçtaki değerle de hesap yapılır. Üst sınırda bile etki küçükse sonuç sağlamdır. |
| S6 | Sabit tohum, tek komut, çıktılar `ciktilar/` altında. Kanıt seviyesi: model D, gerçek veriyle karşılaştırılan kısım V. |

## 3. Model

### 3.1 Katman A: Plak mekaniği (Hueter-Volkmann)

**Mekanizma:** Plağa binen sürekli basınç büyümeyi yavaşlatır, çekme hızlandırır. İlişki doğrusaldır. Yük kalkınca büyüme hızı normale döner (Stokes 2002, 2006). Yük günün yalnızca bir kısmında uygulanınca etki kabaca süreyle orantılı küçülür (Stokes 2005: 12 saatlik yük, tam günün yaklaşık yarısı kadar etki).

```
D_j  = (1/24) · Σ_aktivite  süre_saat · (L_aktivite,j − L_yerine_gecen,j)    (günlük ortalama göreli yük farkı)
M_j  = 1 − β · η · D_j              (D_j > 0, basınç)
M_j  = 1 + 0.5 · β · η · |D_j|      (D_j < 0, çekme; Stokes: "daha küçük hızlanma")
v_j' = v_j · M_j                    (sürüm 3 büyüme plağı modeline, bölme bazında, program süresince uygulanır)
```

- L: o aktivitede plağa binen yükün **rahat ayakta durmaya** oranı (1 = rahat ayakta).
- Bölmeler: j = bacak, gövde.

| Parametre | Anlamı | Sınıf | Değer |
|---|---|---|---|
| β | Normal yük kadar ek **sürekli** yükün büyümeyi yavaşlatma oranı | Ölçülmüş aralık (sıçan/tavşan) | Vücut ağırlığı düzeyinde yük ~%20; "fizyolojik büyüklükte" yük ≥%40 → **β ∈ [0.2, 0.4]** |
| η | Aralıklı, dinamik egzersiz yükünün sürekli statik yüke göre etkinliği | **Varsayım** (insan verisi yok) | Üst sınır 1.0, gerçekçi 0.5, alt 0.25 |
| Süre orantısı | Kısmi gün yükünün etkisi süreyle orantılı | Ölçülmüş (yaklaşık) | Stokes 2005 |

**Ayarlar:**
- **Üst sınır:** β = 0.4, η = 1.0
- **Gerçekçi:** β = 0.3, η = 0.5
- **Alt:** β = 0.2, η = 0.25

**Göreli yükler (L):**

| Aktivite | Gövde L (bel diski basıncı ÷ 0.50 MPa) | Bacak L (diz yükü ÷ ayakta 1.07 BW) | Kaynak / sınıf |
|---|---|---|---|
| Uyku / uzanma | 0.20 | 0.0 | Wilke 1999 (ölçülmüş); bacak varsayım |
| Oturma | 0.92 | 0.1 | Wilke 1999; bacak varsayım |
| Ayakta + yürüme (karışık) | 1.15 | 1.3 | Wilke (yürüme 1.06-1.3); diz: yürüme tepe 2.4, gün ortalaması **varsayım** |
| Koşu | 1.3 (aralık 0.7-1.9) | 3.0 (aralık 2-5) | Wilke koşu 0.35-0.95 MPa; bacak **varsayım** |
| Basketbol / zıplama | 1.5 | 3.5 | **Varsayım** (Wilke merdiven, iki basamak: 0.6-2.4) |
| Ağırlık (aktif set) | 3.0 | 3.0 | Wilke 20 kg kaldırma 2.2-4.6; diz merdiven/çömelme 2.4-3.2; **varsayım** |
| Barfiks (aktif) | 0.5 | −0.15 | **Varsayım:** kaslar omurgayı sıkıştırır, bacaklar sarkar (çekme) |
| Pasif asılma | −0.3 | −0.15 | **Varsayım:** belin altındaki ağırlık omurgayı çeker |
| Ters asılma | −0.6 | −0.75 | **Varsayım:** gövde ağırlığı omurgayı, tüm vücut bacakları çeker |
| Şınav | 0.6 | 0.3 | **Varsayım** |
| Esneme (yerde) | 0.3 | 0.2 | **Varsayım** |

**Normal gün (karşılaştırma tabanı):** 8 saat uyku, 7 saat oturma, 8 saat ayakta/yürüme, 1 saat hafif aktivite (ayakta). Programlar **oturma süresinin** yerine geçer.

**Programlar** (16.0-21.0 yaş arası, haftalık ortalamaya çevrilir):

| Program | İçerik |
|---|---|
| P1 Barfiks + asılma | Günde 5 dk aktif barfiks + 5 dk pasif asılma, haftada 7 gün |
| P2 Şınav | Günde 10 dk, 7 gün |
| P3 Esneme | Günde 20 dk, 7 gün |
| P4 Ters asılma | Günde 10 dk, 7 gün |
| P5 "Boy uzatma rutini" | P1 + P3 + P4 her gün (40 dk) |
| P6 Koşu | 45 dk, haftada 5 gün |
| P7 Basketbol | 90 dk, haftada 4 gün |
| P8 Ağırlık | 60 dk seans (15 dk aktif ağır set + 45 dk ayakta), haftada 4 gün |
| P9 Aşırı yük | Günde 3 saat yüksek etki (gövde 2.0, bacak 3.5), haftada 6 gün |
| P10 Jimnastik profili (doğrulama) | P9 ile aynı yük, ama **9-16 yaş arası** |

**Kohort:** Sürüm 3'ün sanal Türk kohortu. Parametreler sürüm 3'ün `ciktilar/` dosyalarından okunur, yeniden kalibrasyon yok. Cinsiyet başına 5.000 kişi.

### 3.2 Katman B: Disk sünmesi (geçici)

```
dy/dt = (y_denge(P) − y) / τ        τ = τ_c (sıkışırken), τ_r (açılırken)
y_denge(P) = −k · (P − 0.10)        P: bel diski basıncı (MPa, Wilke 1999); 0.10 = uzanma
```

| Parametre | Sınıf | Değer |
|---|---|---|
| P (aktiviteye göre) | Ölçülmüş | Wilke 1999 tablosu. Asılma/traksiyon için **varsayım:** pasif asılma 0.05, traksiyon 0.03, ters asılma 0.0 |
| k | **Kalibre** | Günlük boy farkı 14.4 mm'ye (16 saat ayakta/oturma + 8 saat uyku döngüsü, kararlı periyodik çözüm) |
| τ_c | Varsayım | 1.5 saat (duyarlılık 0.5-3) |
| τ_r | Varsayım | 2.5 saat (duyarlılık 1-4) |

### 3.3 Katman C: Duruş geometrisi

Göğüs omurgası (T1-T12) bir çember yayı. Kifoz açısı θ, yayın merkez açısı. Dikey yükseklik = yay boyu × sinc(θ/2), sinc(x) = sin(x)/x.

```
ΔH = L_T · [sinc(θ_son/2) − sinc(θ_ilk/2)]
```

| Parametre | Sınıf | Değer |
|---|---|---|
| L_T (göğüs omurgası yay boyu) | Varsayım | 0.16 × boy (duyarlılık 0.14-0.18) |
| θ dağılımı, 16 yaş erkek | Ölçülmüş | 36.5° ± 7.85° (esnek cetvel) |
| Egzersizle göreli düzelme | Ölçülmüş (RCT, 12 hafta, kifotik ergen) | Sadece sırt egzersizi: −%13; kapsamlı program: −%26; kontrol: ~0 |
| Ölçek farkı | Varsayım | Esnek cetvel açısındaki göreli düzelme, gerçek eğriliğe aynen uygulanır |
| Kambur duruş (günlük hayat) | Varsayım | Dik duruşa göre +10° ile +20° ek kifoz (yalnızca görünür boy için örnek) |

### 3.4 Katman D: Seçilim

- Türk 18 yaş erkek boyu ~ N(176.0, 6.24) (Günöz 2014).
- Takıma en uzun %10, %5, %1 seçilirse ortalama ne kadar uzun olur? Antrenman etkisi sıfır varsayılır.

## 4. Ön kayıtlı testler

| Kod | Test | Ölçüt | Tür |
|---|---|---|---|
| **T1** | Disk: uyanınca 1 saat ayakta (0.50 MPa), sonra 20 dk sırtüstü (0.10) | 20 dakikada geri kazanılan < 1 saatte kaybedilenin %30'u (literatür: 20 dk dinlenmede anlamlı toparlanma yok) | Literatürle karşılaştırma |
| **T2** | Disk: normal günün 4. saatinde 15 dk traksiyon (0.03 MPa) | Traksiyon öncesine göre kazanç 1-8 mm (literatür: 3.2-5.4 mm) | Literatürle karşılaştırma |
| **T3** | Disk: günün 2. saatinde 33 dk koşu (ortalama 0.65 MPa) | Koşu boyunca kısalma 1-6 mm (literatür: 6 km koşuda 3.25 mm) | Literatürle karşılaştırma |
| **T4** | Plak, **gerçekçi ayar**, jimnastik profili (P10, 9-16 yaş) | Medyan nihai boy kaybı < 1.0 cm (literatür: elit jimnastik erişkin boyu düşürmüyor) | Literatürle tutarlılık |
| **T5** | **Karar kuralı.** Plak, **üst sınır ayarı**, P1-P8 (16-21 yaş, erkek ve kız) | Tüm programlarda \|medyan nihai etki\| < 0.2 cm ise: "16 yaş sonrası egzersiz plak mekaniği yoluyla gerçek boyu anlamlı değiştirmez" | Karar |
| **T6** | **Karar kuralı.** Duruş: kifotik gençlerde (θ ≥ 45°) kapsamlı programın (−%26) ölçülen boya katkısı | Medyan < 1.0 cm ise: sürüm 1-2'deki "duruşla 1-2 cm" ifadesi **ölçülen boy için** desteklenmiyor, düzeltilir | Karar |
| **T7** | Tutarlılık: A katmanı çarpanlar = 1 iken sürüm 3 modeliyle aynı | En büyük fark < 0.01 cm. Zaman adımı yarıya inince fark < 0.05 cm | Fiziksel kontrol (S3) |

## 5. Duyarlılık analizi

Tek tek uca getirilecek parametreler:
- Katman A: β (0.2-0.4), η (0.25-1), bacak L değerleri (koşu 2-5).
- Katman B: τ_c (0.5-3), τ_r (1-4).
- Katman C: L_T (0.14-0.18).

T5'teki en büyük etki ve T1-T3 değerleri raporlanır.

## 6. Önceden bilinen sınırlamalar

- **Plak duyarlılığı hayvan deneylerinden** (sıçan, tavşan) ve **statik** yükten geliyor. İnsanda aralıklı egzersiz yükü için doğrudan veri yok. Bu yüzden üst sınır ilkesi uygulanıyor.
- **Sürüm 3 modeli yakalama büyümesini zayıf üretiyor** (sürüm 3, Ö5b). Bu, kalıcı etkileri **büyük** gösterir; yani üst sınır yönünde temkinlidir.
- **Bacak yükleri** (koşu, zıplama) için ölçülmüş genç verisi yok; varsayım ve duyarlılık.
- **Duruş modeli basit:** tek yay, bel lordozu ve baş duruşu sabit. Kifoz ölçüm yöntemleri arası fark var.
- **Enerji dengesi** (yoğun antrenman + az yemek) bu simülasyonda modellenmiyor; sürüm 3 bu tür bozulmaları güvenilir hesaplayamıyordu. Literatürle ele alınır.

## 7. Plandan sapmalar

| Tarih | Ne değişti | Neden | Ölçütleri etkiliyor mu |
|---|---|---|---|
| 2026-10-07, testlerden önce | **Uygulama ayrıntıları** sabitlendi (aşağıda) | Planda belirsiz kalan tanımlar sonuç görülmeden netleştirilmeli | Hayır |

**Uygulama ayrıntıları:**

1. **T4:** erkek ve kızda ayrı değerlendirilir; **ikisinde de** medyan kayıp < 1.0 cm olmalı.
2. **T5:** erkek ve kız × P1-P8 = 16 hücre; **hepsinde** \|medyan\| < 0.2 cm olmalı. P9 (aşırı yük) karar kuralına dahil değil, bilgi amaçlı.
3. **T6:**
   - Erkek kifoz dağılımı N(36.5, 7.85).
   - Boy, Türk 18 yaş erkek N(176.0, 6.24).
   - 100.000 örnek; θ ≥ 45° alt grubunda medyan.
4. **Disk katmanı gün düzeni** (kalibrasyon ve T1-T3):
   - 0-1. saat ayakta (0.50)
   - 1-8. saat oturma (0.46)
   - 8-16. saat ayakta/yürüme (0.59 = Wilke yürüme aralığının ortası)
   - 16-24. saat uyku (0.10)
   - Kararlı periyodik çözüm için 10 gün ısınma.
5. **Nihai boy:** 30 yaştaki boy. Program etkisi = programlı − programsız, aynı kişi.

## Kaynaklar

- [Stokes IAF ve ark. Endochondral growth in growth plates of three species at two anatomical locations modulated by mechanical compression and tension. J Orthop Res 2006](https://www.uvm.edu/~istokes/pdfs/growth.pdf)
- [Stokes IAF ve ark. Modulation of vertebral and tibial growth by compression loading: diurnal versus full-time loading. J Orthop Res 2005](https://www.uvm.edu/~istokes/pdfs/diurnal.pdf)
- [Stokes IAF. Mechanical effects on skeletal growth. J Musculoskel Neuron Interact 2002](https://www.uvm.edu/~istokes/pdfs/sun_valley.pdf)
- [Wilke HJ ve ark. New in vivo measurements of pressures in the intervertebral disc in daily life. Spine 1999](https://www.fonar.com/pdf/spine_vol_24.No.8.pdf)
- [Diz eklemi in vivo yükleri, enstrümanlı protez (yürüme %261, iki ayak %107 BW)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3900456)
- [Gün içi boy değişimi 14.4 mm ve egzersizle kısalma (BJSM)](https://bjsm.bmj.com/content/20/3/119)
- [Traksiyon ve omurga uzaması ölçümleri (pnömatik dekompresyon kemeri çalışması ve kaynakları)](https://www.backfitpro.com/medical-scientific-articles/2016-2017/[8]-Cannon,J.-(2016)-Evidence-on-the-ability-of-a-pneumatic-decompression-belt-to-restore-spinal-height-[J.Mani.-and-Physio-Therapeutics].pdf)
- [Kifoz düzeltici egzersiz RCT'si, ergenler (Healthcare 2022)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9778671/)
- [13-18 yaş erkeklerde normal kifoz aralığı](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4045366/)
- [Elit jimnastikçilerde büyüme ve olgunlaşma (Malina ve ark. 2013)](https://dro.deakin.edu.au/articles/journal_contribution/Role_of_intensive_training_in_the_growth_and_maturation_of_artistic_gymnasts/20948449)
- [Günöz H ve ark. Türk boy referansı, JCRPE 2014](https://jcrpe.org/pdf/cf9d60d6-523c-458a-a2e6-78728d3ffbb0/articles/Jcrpe.1260/JCRPE-6-28-En.pdf)
