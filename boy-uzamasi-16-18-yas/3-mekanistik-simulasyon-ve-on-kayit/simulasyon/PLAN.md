# Simülasyon Planı: Büyüme Plağı Dijital İkizi

> **Plan sürümü:** 1 · **Tarih:** 2026-10-07 · **Durum:** ön kayıt (testler çalıştırılmadan önce commit edildi)
>
> Bu dosya kod sonuçları görülmeden yazılıp commit edildi. Git geçmişindeki tarih bunun kanıtı. Testler çalıştırıldıktan sonra bu dosyadaki **ölçütler değiştirilmez.** Her değişiklik en alttaki "Plandan sapmalar" tablosuna gerekçesiyle yazılır.

## 1. Amaç

Üç soruyu cevaplayacak bir **sanal kohort** (dijital ikiz) kurmak:

1. **Mekanizma:** "Kalan boy ≈ son 12 aydaki uzama" kuralı biyolojiden kendiliğinden çıkıyor mu, yoksa Berkeley verisine özgü bir rastlantı mı?
2. **Sınırlar:** Kural kimde ve hangi koşulda çöküyor? (v2 sonrası bulgu: hâlâ hızlananlarda çöküyor.)
3. **Kanıtlama tasarımı:** Kuralı gerçek bir çalışmada test etmek için kaç kişi, hangi ölçüm protokolü ve ne kadar süre gerekir?

**Benzetme:** Bir uçağı gerçekten uçurmadan önce rüzgâr tünelinde ve simülatörde denersin. Simülatör uçağın yerini tutmaz, ama hangi testi nasıl yapacağını ve neyin ters gidebileceğini gösterir. Bu simülasyon da gerçek çalışmanın yerini tutmaz; onu doğru tasarlamaya yarar.

## 2. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Her denklem literatürde gösterilmiş bir biyolojik ya da fiziksel mekanizmaya dayanır. Mekanizma ve kaynağı yazılır. |
| S2 | Her parametre üç sınıftan birine girer: **Ölçülmüş** (literatür değeri), **Kalibre** (veriye fit edilmiş), **Varsayım**. Varsayımlar için duyarlılık analizi zorunludur. |
| S3 | Her çalıştırmada fiziksel tutarlılık kontrolleri (assert) yapılır: hücre stoku hiç artmaz, büyüme hızı negatif olmaz, toplam boy = bacak + gövde (korunum), zaman adımı yarıya indirilince sonuç 0.05 cm'den fazla değişmez. |
| S4 | Kalibrasyon ve doğrulama ayrıktır. Doğrulama testleri ve geçme ölçütleri bu planda, testler çalıştırılmadan önce sabitlenir. |
| S5 | Başarısız test saklanmaz. Sonuç ne olursa olsun raporlanır. |
| S6 | Sabit tohum, tek komut (`python calistir.py`), tüm çıktılar `ciktilar/` altında. |
| S7 | Model çıktıları kanıt seviyesi **D**'dir. Yalnızca gerçek veriyle karşılaştırılan kısımlar **V** olarak işaretlenir. |
| S8 | Basitlik: aynı veriyi eşit iyi açıklayan iki modelden daha az parametreli olan tercih edilir. Mekanistik model, v2'nin PB1 modeli ve basit kuralla karşılaştırılır. |

## 3. Model

Model dört katmandan oluşuyor:

```
[1] Hormon ortamı ──► [2] Büyüme plakları (bacak, gövde) ──► gerçek boy
                                                                │
                              [3] Ölçüm fiziği (omurga sıkışması, alet hatası) ◄┘
                                                                │
                              [4] Çalışma tasarımı (kim, ne zaman, kaç kez ölçülüyor)
```

### 3.1 Katman 1: Hormon ortamı

| Değişken | Denklem | Mekanizma | Kaynak |
|---|---|---|---|
| Östrojen etkisi E(t) | E = a_rom · σ((t − T_p) / w_E), σ = lojistik | Ergenlikte artan seks steroidleri. Erkekte östrojen testosteronun aromatizasyonundan gelir. a_rom = 1 normal, aromataz inhibitörü senaryosunda < 1 | Smith 1994; Morishima 1995 |
| GH/IGF-1 ekseni I(t) | I = 1 + A_p · E | Ergenlikteki GH artışı östrojen aracılıklı. Aromatize olmayan androjen GH'yi artırmıyor | Östrojen-GH literatürü (bkz. Kaynaklar) |
| Beslenme/hastalık N(t) | 1 = normal, < 1 = eksiklik (senaryo girdisi) | Enerji ve protein eksikliği büyümeyi baskılar | REDs 2023, anoreksiya serileri |

### 3.2 Katman 2: Büyüme plakları (iki bölme)

İki bölme var: **b = bacak** (uzun kemik plakları) ve **g = gövde** (omurga uç plakları + baş). Ayrım gerçek veriye dayanıyor. Berkeley'de 16 yaş sonrası erkek büyümesinin ~%87'si gövdeden geliyor (oturma boyu ölçümü).

Her bölme j için:

```
büyüme hızı:    v_j = G_j · I^α_j · N · S_j^γ · Φ(S_j)           (cm/yıl)
stok tükenmesi: dS_j/dt = − S_j · [ κ_j · v_j / G_j  +  ε_j · E ]  (1/yıl)
uzunluk:        dL_j/dt = v_j
boy:            H = L_b + L_g
kaynaşma kapısı: Φ(S) = σ((S − S_f) / (0.15 · S_f))
```

| Terim | Fiziksel/biyolojik anlamı | Kaynak |
|---|---|---|
| G_j · S^γ | Plak çıktısı = kolon sayısı × kolon başına hücre üretimi × hipertrofik hücre boyu. Üçü de senesansla azalır. Büyümenin ~%59'u hipertrofik hücre büyümesinden gelir | Wilsman ve ark. 1996 |
| κ_j · v_j/G_j | **Kullanıma bağlı tükenme:** öncü hücreler bölündükçe stok azalır. Büyüme baskılanırsa stok korunur → yakalama büyümesi | Baron 1994; Pediatric Research 2001 (tavşan) |
| ε_j · E | **Östrojenin doğrudan hızlandırması:** östrojen senesansı büyümeden bağımsız olarak hızlandırır | Weise ve ark. 2001 (PNAS) |
| Φ(S) | Stok tükenince plak kaynaşır. Kaynaşma aylar süren bir geçiş, bu yüzden yumuşak kapı | Weise ve ark. 2001 |
| İki bölme | Bacak plakları gövdeden önce kapanır (östrojen etkisi) | Berkeley (V); pubertal zamanlama-bacak uzunluğu literatürü |

Başlangıç: t₀ = 9 yaş (Berkeley'de oturma boyunun herkes için başladığı yaş), S_j(9) = 1 (normalize), L_j(9) = kişinin ölçülmüş bacak ve gövde uzunluğu. Sayısal çözüm: Euler, Δt = 0.02 yıl.

### 3.3 Parametreler

| Parametre | Düzey | Sınıf | Değer / aralık |
|---|---|---|---|
| G_b, G_g (çocukluk büyüme ölçeği) | Bireysel | Kalibre | Berkeley |
| T_p (ergenlik zamanı) | Bireysel | Kalibre | Berkeley |
| A_p (ergenlik GH yükseltmesi) | Bireysel | Kalibre | Berkeley |
| κ_b, κ_g, γ, S_f (hücre düzeyi) | **Cinsiyetler ortak** | Kalibre | Berkeley (iki cinsiyet birlikte) |
| w_E, ε_b, ε_g, α_g (hormon ortamı) | Cinsiyete özgü | Kalibre | Berkeley |
| α_b | - | Varsayım | 1 (sabit, ölçek belirleyici) |
| Kaynaşma kapısı genişliği | - | Varsayım | 0.15 · S_f |
| t₀, S(t₀) = 1 | - | Varsayım | 9 yaş |

**Neden hücre parametreleri ortak?** Plan öncesi prototipte cinsiyetler ayrı fit edildiğinde kızlarda κ ≈ 0 çıktı. Sebep: kızlarda ergenlik 9 yaşa çok yakın başladığı için veri kullanıma bağlı tükenmeyi östrojen etkisinden ayıramıyor. κ = 0 ise yakalama büyümesi imkânsızlaşır, bu da deneysel olarak gösterilmiş biyolojiye aykırı (Baron 1994). Kondrosit biyolojisinin cinsiyetler arasında aynı, hormon ortamının farklı olduğu varsayıldı.

### 3.4 Katman 3: Ölçüm fiziği

```
ölçülen boy = gerçek boy − D_max · (1 − exp(−τ / τ_c)) + e_okuma + b_gözlemci, 0.1 cm'ye yuvarlanır
```

| Parametre | Anlamı | Sınıf | Değer | Duyarlılık aralığı |
|---|---|---|---|---|
| D_max | Gün içi omurga disk sıkışmasının üst sınırı | Ölçülmüş | 1.44 cm (ort. 14.4 mm) | 1.0 - 2.0 |
| τ | Uyanıştan beri geçen süre (saat) | Protokol | Sabah: 0-2 saat. Rastgele: 1-13 saat | - |
| τ_c | Sıkışma zaman sabiti | Varsayım | 1.5 saat | 0.5 - 4 |
| e_okuma | Tek okuma hatası (SD) | Varsayım | 0.3 cm (çocuklarda bildirilen %TEM 0.19-0.70 ile uyumlu) | 0.2 - 0.6 |
| 3 okuma ortalaması | | Varsayım | SD / √3 (okumalar bağımsız) | - |
| b_gözlemci | Farklı gözlemci sistematik farkı (SD) | Varsayım | 0.3 cm | 0 - 0.5 |

**Ölçüm protokolleri:**
- **P1:** sabah, aynı gözlemci, 3 okuma ortalaması.
- **P2:** günün rastgele saati, aynı gözlemci, tek okuma.
- **P3:** günün rastgele saati, her ziyarette farklı gözlemci, tek okuma.

### 3.5 Katman 4: Türk nüfusuna uyarlama ve sanal kohort

1. Berkeley'e fit edilen bireysel parametrelerin ortak dağılımı (log G_b, log G_g, T_p, log A_p, L_b(9), L_g(9); çok değişkenli normal, korelasyonlar dahil) cinsiyete göre çıkarılır.
2. Türk uyarlaması için cinsiyet başına 2 parametre fit edilir: **ΔT_p** (zamanlama kayması) ve **c** (boyut çarpanı; G'ler ve başlangıç uzunlukları). Hedef: Günöz ve ark. 2014 Türk referansının 9-18 yaş ortalama boyları. **Kabul ölçütü:** ortalama eğri RMSE ≤ 0.7 cm. Tutmazsa raporlanır.
3. Cinsiyet başına 20.000 kişilik sanal Türk kohortu üretilir.

### 3.6 Katman 4: Çalışma tasarımı simülasyonu

Kuralı gerçek bir çalışmada test etmeyi simüle eder.

| Tasarım | Başlangıç yaşı | Ölçüm | Bitiş | Kural nerede uygulanır |
|---|---|---|---|---|
| **Uzun** | U(15.5, 16.5) | 6 ayda bir | 20 yaş | Başlangıç + 1 yılda (önceki 12 ayın artışıyla). Sonuç: 20 yaştaki boy |
| **Kısa** | U(16.0, 17.0) | 6 ayda bir | 19 yaş | Aynı. Sonuç: 19 yaştaki boy. Kesik takip, yanlılığı gösterilir |

- **Değişkenler:** n ∈ {30, 60, 100, 200} (cinsiyet başına), protokol ∈ {P1, P2, P3}, yıllık %10 kayıp.
- **Birincil analiz:** sıfırdan geçen regresyonla kural katsayısı k ve %95 güven aralığı, ortalama mutlak hata.
- **"Çalışma başarılı" tanımı:** k'nın %95 GA'sı [0.7, 1.3] içinde **ve** ortalama mutlak hata < 1.0 cm.
- Her kombinasyon için 300 tekrar → başarı olasılığı.
- Ayrıca kural yanlış olsaydı (gerçek katsayı 0.5 ya da 1.6 olacak şekilde sonuç ölçeklenmiş), "başarılı" çıkma olasılığı hesaplanır (yanlış pozitif).

## 4. Kalibrasyon ve doğrulama prosedürü

- **Veri:** Berkeley, boy ve oturma boyu, 9-21 yaş.
- **Tam kalibrasyon:** Tüm bireyler, tüm veri. Sanal kohort ve senaryolar için.
- **Çapraz doğrulama (testler için):** Bireyler cinsiyet içinde 5 kata bölünür (sabit tohum). Her kat için:
  - Popülasyon parametreleri diğer 4 katın **tüm** verisiyle fit edilir.
  - Test bireylerinin kendi parametreleri yalnızca **kesme yaşına kadarki** verisiyle fit edilir (c = 16.0 ve 17.0).
  - Sonrası tahmin edilir.

**Karşılaştırıcılar (aynı bilgiyle, kesme yaşına kadar):**
- **K1 "Büyüme bitti":** H(c).
- **K2 "Basit kural":** H(c) + k · [H(c) − H(c−1)]. k eğitim katlarından, 18'e kadar.
- **K3 PB1:** kişinin kesme yaşına kadarki boy verisine PB1 fit edilip 18'e uzatılır.
- **M:** Mekanistik model.

## 5. Ön kayıtlı testler ve geçme ölçütleri

| Kod | Test | Ölçüt (GEÇER) | Tür |
|---|---|---|---|
| **Ö1** | Kesme 16.0 → 18 yaştaki boyu tahmin (çapraz doğrulama), her cinsiyet ayrı | Ortalama mutlak hata (M) ≤ hata (K2) + 0.10 cm | Gerçek veri, örneklem dışı |
| **Ö2** | Kesme 17.0 → 18, aynı | Aynı ölçüt | Gerçek veri, örneklem dışı |
| **Ö3** | 18 sonrası kuyruk. 18'den sonra ölçülmüş erkekler (n≈41). Test bireyi 18'e kadarki verisiyle fit edilir, son ölçüme kadar uzama tahmin edilir | Medyan tahmin ile medyan gözlem farkı ≤ 0.30 cm | Gerçek veri, örneklem dışı |
| **Ö4** | Bölme ayrımı. Erkeklerde 16→18 büyümede gövde payı (toplam gövde artışı ÷ toplam boy artışı), kesme 16.0 ile | Tahmin edilen pay ile gözlenen pay farkı ≤ 0.15 | Gerçek veri, örneklem dışı |
| **Ö5a** | Östrojen yokluğu (E ≡ 0, ömür boyu). Medyan sanal erkek | 25 yaşında hız ≥ 0.5 cm/yıl **ve** 28 yaşında boy ≥ ortalama + 2 SD | Literatür olgusu, kalibrasyonda kullanılmadı |
| **Ö5b** | Yakalama. N = 0.6, 9-11 yaş (ergenlik öncesi), sonra normal | Nihai kayıp ≤ 11 yaşındaki kaybın %25'i | Literatür olgusu |
| **Ö5c** | Aynı eksiklik 13-15 yaşta (erkek, ergenlik içi) | Nihai kayıp ≥ Ö5b'deki nihai kaybın 2 katı | Literatür olgusu (Rivkees 1988) |
| **Ö5d** | Aromataz inhibitörü. Geç olgunlaşan erkek (T_p + 2 yıl), a_rom = 0.2, 15.2-16.2 yaş | Nihai boy kazancı +0.5 ile +8 cm arası | Literatür olgusu (Wickman 2001) |
| **Ö5e** | Ergenlik öncesi aromataz inhibitörü (9-11 yaş) | \|kazanç\| < 0.5 cm | Literatür olgusu (2019, monoterapi faydasız) |
| **Ö5f** | Dış steroid. 16-16.5 yaş arası E'ye +0.5 eklenir | 16 yaşında hızı > 1 cm/yıl olanların ≥ %95'inde nihai boy düşer | Literatür olgusu (AAP) |
| **Ö6a** | Kural, sanal Türk kohortunda, gerçek boyla (ölçüm hatası yok). Yavaşlayanlar (son yıl < önceki yıl) | 16 ve 17 yaşta katsayı [0.7, 1.3] içinde | Model tahmini (D). Gerçek veriyle ileride test edilecek |
| **Ö6b** | Aynı kohortta hâlâ hızlananlar | Kural hatasının (gerçek − tahmin) medyanı > +0.5 cm | Model tahmini (D) |
| **Ö7** | Ölçüm katmanı gerçekçiliği. Sanal kızlarda 16.5-18 yaş arası 6 aylık artışların negatif olma oranı (Berkeley'de %14) | P1, P2, P3'ten en az birinde %7 ile %25 arası | Kalibrasyon tutarlılığı |

**Şeffaflık notu (plan öncesi görülenler):** Model yapısını seçmek için yapılan prototip kalibrasyonlarda (tüm veri, örneklem içi) şu sayılar görüldü:
- Erkeklerde 18→19.3 uzama tahmini ~0.45-0.48 cm, gözlenen 0.8 cm.
- Kızlarda 16→18 tahmini ~0.35-0.41 cm, gözlenen 0.7 cm.
- Erkeklerde gövde payı 0.87-0.93.

Bu yüzden Ö3, Ö4 ve kızların Ö1'i **tamamen kör değildir.** Ölçütler bu sayılara bakılarak gevşetilmedi; v2'den bilinen hedeflere göre konuldu. Bu testlerden bazılarının geçmemesi beklenebilir.

## 6. Duyarlılık analizi

Her varsayım parametresi (τ_c, D_max, e_okuma, b_gözlemci, kaynaşma kapısı genişliği) aralığının alt ve üst ucuna tek tek getirilip şu çıktılar yeniden hesaplanır:
- Ö6a katsayısı.
- Ö7 oranı.
- Uzun tasarımda n = 100, P1 ve P2 için başarı olasılığı.

Sonuç tablo olarak raporlanır.

## 7. Çıktılar

`ciktilar/` altında: kalibrasyon parametreleri, uyum tablosu, test sonuçları (`on_kayitli_testler.csv`, GEÇTİ/KALDI), çalışma tasarımı güç tablosu, duyarlılık tablosu, grafikler.

## 8. Önceden bilinen sınırlamalar

- **Tek kalibrasyon kohortu** (Berkeley, 1928 doğumlu). Türk uyarlaması yalnızca ortalama ve zamanlamayı ayarlar, bireysel değişkenliğin yapısı Berkeley'den gelir.
- **Hormon ortamı basitleştirildi** (tek bir östrojen indeksi). Tiroid, kortizol ve leptin ayrı modellenmedi; hepsi N(t) içinde.
- **İki bölme yaklaşımı** gerçek anatomiden (onlarca plak) basit.
- **Senaryo büyüklükleri** (N = 0.6, a_rom = 0.2 gibi) varsayım. Yön testi içindir, kesin cm vermez.

## 9. Plandan sapmalar

| Tarih | Ne değişti | Neden | Ölçütleri etkiliyor mu |
|---|---|---|---|
| - | (henüz yok) | - | - |

## Kaynaklar

- [Weise M ve ark. Effects of estrogen on growth plate senescence and epiphyseal fusion. PNAS 2001](https://pmc.ncbi.nlm.nih.gov/articles/PMC34445)
- [Catch-up growth is associated with delayed senescence of the growth plate in rabbits. Pediatric Research 2001](https://www.nature.com/articles/pr2001230)
- Baron J ve ark. Catch-up growth after glucocorticoid excess: a mechanism intrinsic to the growth plate. *Endocrinology* 1994 (arama özetinden; tam metin açılmadı)
- Wilsman NJ ve ark. Differential growth by growth plates as a function of multiple parameters of chondrocytic kinetics. *J Orthop Res* 1996 **[doğrulanmadı: bağlantıya erişilemedi]**
- [Smith EP ve ark. NEJM 1994](https://pubmed.ncbi.nlm.nih.gov/8090165/) · [Morishima A ve ark. JCEM 1995](https://www.osti.gov/biblio/391044)
- [Almeida M ve ark. Estrogens and androgens in skeletal physiology and pathophysiology. Physiol Rev 2017 (derleme: ergenlikte östrojenin büyüme ve plak kapanmasındaki rolü)](https://pmc.ncbi.nlm.nih.gov/articles/PMC5539371) · [Aromatize östrojen GH salınımını artırır (yetişkin erkek, JCEM 2018)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6212797)
- [Gün içi boy değişimi (BJSM)](https://bjsm.bmj.com/content/20/3/119)
- [Pubertal zamanlama ve bacak uzunluğu](https://pubmed.ncbi.nlm.nih.gov/20961561)
- [Günöz H ve ark. Türk boy referansı, JCRPE 2014](https://jcrpe.org/pdf/cf9d60d6-523c-458a-a2e6-78728d3ffbb0/articles/Jcrpe.1260/JCRPE-6-28-En.pdf)
- [Rivkees ve ark. hipotiroidi ve nihai boy (sistematik derleme içinde)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11674360/)
- [Wickman 2001 ve aromataz inhibitörü derlemesi](https://www.degruyterbrill.com/document/doi/10.1515/jpem-2022-0177/html) · [Letrozol monoterapi 2019](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6460933/)
