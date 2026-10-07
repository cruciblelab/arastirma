# Veri Setleri Envanteri

> Tarih: 2026-10-07 · Amaç: "Kalan boy ≈ son 12 aydaki uzama" kuralını ve büyümenin 18 sonrası kuyruğunu **bağımsız** veriyle test etmek, simülasyonu Türk nüfusuna ayarlamak.
>
> "Denendi" sütunu bu oturumda gerçekten yapılan erişim denemesini gösterir. Kayıt ya da başvuru gerektiren kaynaklarda hesap açılamadığı için yalnızca erişim koşulu kontrol edildi.

## Aradığımız veri

Kuralı test etmek için gereken veri:
- **Aynı kişiler**, 15-20 yaş arasında
- **En az yıllık** aralıkla
- **Ölçülmüş** boy (beyan edilen değil)

Bu üçünü birlikte sağlayan ve indirmeye açık **ikinci bir veri seti bulamadık.** Aşağıdaki tablo neyin var olduğunu ve neye nasıl ulaşılabileceğini gösteriyor.

## A. Hemen erişilebilir (indirildi)

| # | Veri seti | İçerik | Bu iş için değeri | Denendi |
|---|---|---|---|---|
| 1 | **Berkeley Child Guidance Study** (R `sitar`, `berkeley`) | 136 kişi, 8-18 yaş arası 6 ayda bir, bir kısmı 21 yaşına kadar. Boy + **oturma boyu (gövde)** | Ana veri. v2'de kullanıldı. v3'te mekanistik modelin kalibrasyonu ve bacak/gövde ayrımı | ✅ İndirildi, SHA-256 doğrulandı |
| 2 | **Günöz ve ark. 2014, Türk boy Z-skor referansı** (JCRPE 6:28, PDF) | İstanbul çocukları, 6-18 yaş, yarım yıllık **ortalama ve SD** (kesitsel) | Simülasyonu Türk nüfusuna ayarlamak. Türk ortalamasında 16→18 artış erkek 2.6, kız 0.7 cm | ✅ İndirildi, tablolar ayrıştırıldı. **Not:** PDF'te kız 16.0 yaş ortalaması "152.4" yazıyor; ±SD sütunlarından doğrusu 162.4. Dizgi hatası, düzeltilerek kullanıldı |
| 3 | **Galton aileleri** (R `HistData`, `GaltonFamilies`) | 205 aile, 934 çocuk, anne-baba ve çocuk erişkin boyu (1880'ler, İngiltere) | Hedef boy varsayımını test etmek. Sonuç: çocuk boyunun Tanner hedef boyuna eğimi erkek 0.75, kız 0.69; araçtaki 0.72 doğrulandı. Belirsizlik (SD) erkek 5.8, kız 5.1 cm (araçta 5.0'dı) | ✅ İndirildi |
| 4 | WHO 2007, CDC 2000, UK90 referansları (`sitar`) | LMS referans eğrileri, kesitsel | Karşılaştırma | ✅ Pakette mevcut |
| 5 | Oxford erkekleri (`nlme::Oxboys`), Chard kızları (`sitar::heights`) | 26 erkek 11-13 yaş; 12 kız 8-16 yaş | 16 yaş sonrası yok, **işe yaramaz** | ✅ İncelendi |
| 6 | `fda::growth` | Berkeley'in alt kümesi | **Bağımsız değil**, ek bilgi yok | ✅ Belgeden doğrulandı |

## B. Ücretsiz kayıtla erişilebilir (hesap senin açman gerekiyor)

| # | Veri seti | İçerik | Bu iş için değeri | Not |
|---|---|---|---|---|
| 7 | **Add Health** public-use (ICPSR 21600) | Wave III (2001-02, 18-26 yaş) ve Wave IV (2008-09, 24-32 yaş): **ölçülmüş** boy. Public-use Wave III n=4.882 | **18 sonrası büyüme kuyruğu**: Wave III'te 18-19 yaşında olanların Wave IV'teki boyu. v2'deki "18 sonrası ~0.8 cm" bulgusunu büyük örneklemde test eder | ICPSR hesabı (ücretsiz). Wave I/II boyları beyana dayalı, kural testine uygun değil |
| 8 | **Young Lives** (UK Data Service, SN 9543) | Etiyopya, Hindistan, Peru, Vietnam. Ölçülmüş boy: 15, 19, 22 yaş (eski kohort) | 19→22 kuyruk testi. Düşük-orta gelirli ülkeler, beslenme etkisi | UKDS kaydı |
| 9 | **CHNS** (Çin, UNC) | Ölçülmüş boy, 2-4 yılda bir, 1989-2015 | Kaba test: aralık uzun, yıllık hız hesaplanamaz | Ücretsiz kayıt |
| 10 | NLSY97 (NLS Investigator) | Yıllık **beyan edilen** boy (feet/inç) | **Uygun değil:** beyan hatası (~2-3 cm), ölçmek istediğimiz 1 cm'lik farktan büyük | Ücretsiz |

## C. Başvuru ya da iş birliği gerektirir

| # | Veri seti | İçerik | Değeri | Erişim |
|---|---|---|---|---|
| 11 | **ALSPAC** (İngiltere) | Ölçülmüş boy: 15.5 (n≈5.500), 17.8 (n≈5.100), 24 yaş (n≈4.000) | **İdeal.** 15.5→17.8 hızı ile 17.8→24 kalan boy: kuralın ve kuyruğun doğrudan testi | Proje önerisi + ücret |
| 12 | **Zhongshan kohortu** (Çin) | 13.143 çocuk, 2006-2016, **yıllık** okul ölçümü | Çok değerli: büyük örneklem, yıllık, geç ergenliğe kadar | Makalede "yazarlardan istenebilir, gereksiz kısıtlama olmadan" yazıyor. **E-posta ile istenebilir: en ucuz yol** |
| 13 | ABCD (ABD, NBDC Data Hub) | ~11.800 çocuk, 9-10 yaştan itibaren yıllık ölçülmüş boy | Büyük ve güncel. Kohort şu an geç ergenlikte | Kurumsal Veri Kullanım Sertifikası (DUC) gerekir |
| 14 | Fels Longitudinal (ABD) | 18'e kadar 6 ayda, 24'e kadar 2 yılda bir ölçüm | Kuyruk için ideal | İş birliği |
| 15 | Zürih ZLS | 1954-61 doğumlu 445 kişi, oturma boyu dahil | Bacak/gövde ayrımı | İş birliği |
| 16 | Kore GP kohortu | 54.374 çocuk, 2013-2024 | Büyük | Şirket verisi, talep |
| 17 | Yunan okul çocukları (1.514 kişi, 6 ayda bir) | 6-18 yaş, 3 okul yılı | Makaleye göre ham veri bir doktora tezinde (139 sayfa). **Bireysel veri içerdiği doğrulanamadı** | Tez görüntüleyicisi |
| 18 | Brush (ABD), Florianópolis (Brezilya) | Uzunlamasına | Orta | Talep üzerine |

## D. Toplu (bireysel değil)

| # | Veri seti | Not |
|---|---|---|
| 19 | NCD-RisC (ülke bazında yaşa göre ortalama boy, Türkiye dahil) | İlk denemede sunucu 421 hatası verdi, sonraki bağlantı kontrolünde sayfa açıldı. Veri dosyaları **indirilmedi**: Günöz 2014 tablosu nüfus ortalaması için yeterliydi. Kural testi için uygun değil (bireysel değil) |

## Öneri: sırayla

1. **Zhongshan yazarlarına e-posta** (bedava, yıllık ölçüm, binlerce kişi): kural testi için en iyi fiyat/fayda.
2. **Add Health** (ücretsiz ICPSR hesabı): 18 sonrası kuyruğu binlerce kişide test eder.
3. **ALSPAC** (ücretli): kural + kuyruk testinin en temiz hali. Kurumsal bir ortakla.
4. **Kendi ileriye dönük çalışmamız**: tasarımı bu sürümdeki simülasyonla yapıldı (bkz. README, bölüm "Çalışma tasarımı").

Her yeni veri, sürüm 3'teki **ön kayıtlı** ölçütlerle test edilecek (bkz. `on-kayit.md`). Böylece "veriyi görünce kuralı esnetme" mümkün olmayacak.

## Kaynaklar

- [sitar (CRAN)](https://cran.r-project.org/web/packages/sitar/index.html) · [HistData (CRAN)](https://cran.r-project.org/web/packages/HistData/index.html)
- [Günöz H ve ark. Z-score reference values for height in Turkish children aged 6 to 18 years. JCRPE 2014;6:28](https://jcrpe.org/pdf/cf9d60d6-523c-458a-a2e6-78728d3ffbb0/articles/Jcrpe.1260/JCRPE-6-28-En.pdf)
- [Add Health public-use, ICPSR 21600](https://www.icpsr.umich.edu/web/ICPSR/studies/21600/versions/V26/summary)
- [Young Lives veri sayfası](https://www.younglives.org.uk/data)
- [CHNS (UNC Carolina Population Center)](https://www.cpc.unc.edu/projects/china/about)
- [NLSY97 (BLS)](https://www.bls.gov/nls/nlsy97.htm)
- [ALSPAC klinik oturumları](https://www.bristol.ac.uk/media-library/sites/alspac/documents/researchers/clinics/focusclinicsessions.pdf) · [ALSPAC erişim politikası](https://www.bristol.ac.uk/media-library/sites/alspac/documents/researchers/data-access/ALSPAC_Access_Policy.pdf)
- [Zhongshan kohortu makalesi (veri erişim beyanı)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9354934/)
- [ABCD veri sürümleri (NIDA)](https://nida.nih.gov/research-topics/adolescent-brain/longitudinal-study-adolescent-brain-cognitive-development-abcd-study/abcd-curated-data-releases)
- [Fels Longitudinal Study](https://medicine.wright.edu/lifespan-health-research-center/fels-longitudinal-study/history)
- [Kore GP kohortu (veri erişim beyanı)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11457228/)
- [Yunan okul çocukları çalışması](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9221559/)
- [Brush ve Berkeley karşılaştırması](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5711808/)
- [NCD-RisC boy verisi](https://www.ncdrisc.org/data-downloads-height.html)
