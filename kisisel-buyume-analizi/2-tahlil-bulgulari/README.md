# Kişisel Büyüme Analizi · Sürüm 2: Tahlil Bulguları

> **Sürüm:** 2 · **Tarih:** 2026-10-07 · **Durum:** güncel
>
> **Acelen varsa:** en alttaki [En basit özet](#en-basit-özet) bölümüne atla.
>
> Bu doküman **tıbbi tavsiye değildir.** Tahlil yorumu ve tedavi kararı hekime aittir. Takviye ve ilaçlar yalnızca **hekim kararıyla** kullanılır; doz yazılmaz.
>
> **Veri ve rıza:** Bu sürümdeki tahlil değerleri, sürüm 1'deki gerçek vakanın sahibinin **açık isteğiyle** yayınlanmıştır. Yalnızca analizi etkileyen değerler alındı. Ad, doğum tarihi, kimlik bilgisi, sağlık kuruluşu ve kesin tarihler alınmadı; ölçüm zamanı yalnızca yaş olarak (bir ondalık) verildi. Asıl tahlil dosyaları ayıklamadan sonra silindi. Vakanın boy ölçümleri ve anne-baba boyu bu sürümde de **yayınlanmadı.**

**Kanıt seviyeleri:**

| Etiket | Anlamı |
|---|---|
| **A** | Meta-analiz ya da birden çok randomize kontrollü çalışma |
| **B** | Tek RCT ya da büyük, iyi tasarlanmış kohort |
| **C** | Gözlemsel çalışma, mekanizma, uzlaşı/kılavuz eşiği |
| **V** | Bu çalışmanın kendi gerçek veri analizi (burada: vakanın kendi tahlil değerleri) |
| **D** | Model çıktısı ya da varsayım |

---

## Soru ve kapsam

Sürüm 1'deki gerçek vakanın (erkek, 16-17 yaş) tahlilleri:
1. Sürüm 1'in büyüme tahminini geçersiz kılacak bir şey gösteriyor mu?
2. Önceki araştırmanın "16 yaşından sonra eksik bırakma" sonucu açısından somut bir eksiklik var mı?
3. Kalan büyümeyi değerlendirmek için hangi test eksik?

**Kapsam dışı:** Tanı koymak ve tedavi önermek. Tahlil değerleri büyüme modeline sayısal olarak **girmez**; bunu yapacak yayınlanmış bir ilişki yok.

## Önceki sürümden değişenler

| Konu | Sürüm 1 | Sürüm 2 |
|---|---|---|
| Tahliller | Kullanılmadı, yayınlanmadı | Analizi etkileyen 22 değer, veri sahibinin isteğiyle kimliksizleştirilerek yayınlandı ([`tahlil_secilmis.csv`](analiz/tahlil_secilmis.csv)) |
| Ferritin yorumu | (Sohbette verilen ilk yorum: "demir deposu düşük") | Düzeltildi: Laboratuvar aralığının altında, ama DSÖ 2020'nin ergen eşiğinin (< 15 µg/L) **hemen üstünde**. Doğrusu "sınırda düşük depo", eksiklik değil |
| Sürüm 1'in tahmin aracı ve doğrulaması | – | Değişmedi. Sürüm 1'in sonuçları geçerli |

## Yöntem

- **Seçim:** Üç tahlil raporundan (vaka 16.2, 16.8 ve 16.9 yaşındayken) yalnızca şu soruları etkileyen değerler alındı:
  - kemik/mineral (D vitamini, kalsiyum, fosfor);
  - demir durumu (ferritin, demir, TDBK, hemoglobin, MCV, MCHC);
  - tiroid (TSH, serbest T4);
  - iltihap ve kronik hastalık dışlaması (CRP, ALT, AST, kreatinin);
  - beslenme (B12, folat).

  Hepatit/HIV serolojisi, kan grubu, idrar tetkiki, glukoz ve kan sayımının diğer kalemleri alınmadı: büyüme sorusunu etkilemiyorlar.
- **Değerlendirme** ([`analiz/calistir.py`](analiz/calistir.py)). Her değer iki ölçüte göre işaretlendi:
  1. laboratuvarın kendi referans aralığı;
  2. varsa yayınlanmış eşik:
     - D vitamini ≥ 20 ng/mL (IOM 2011);
     - ferritin < 15 µg/L, 10-19 yaş, iltihap yokken demir eksikliği (DSÖ 2020).
- Transferrin doygunluğu = demir / TDBK hesaplandı.
- `cd analiz && python calistir.py`. Çıktılar `analiz/ciktilar/` altında.

## Bulgular

Kaynak: [`tahlil_degerlendirme.csv`](analiz/ciktilar/tahlil_degerlendirme.csv), [`ozet.json`](analiz/ciktilar/ozet.json).

| Yaş | Test | Değer | Laboratuvar aralığı | Laboratuvara göre | Yayınlanmış eşiğe göre |
|---|---|---|---|---|---|
| 16.2 | **25-OH D vitamini** | **18.73 ng/mL** | verilmemiş | – | **20 ng/mL eşiğinin altında** (IOM 2011) |
| 16.2 | **Ferritin** | **16.9 µg/L** | 23.9-336.2 | **altında** | DSÖ eksiklik eşiğinin (< 15) hemen **üstünde**: sınırda |
| 16.2 | Demir | 107 µg/dL | 70-180 | içinde | – |
| 16.2 | TDBK | 295 µg/dL | 155-355 | içinde | Transferrin doygunluğu %36.3 |
| 16.2 / 16.8 / 16.9 | Hemoglobin | 15.6 / 15.7 / 16.1 g/dL | 12-16.8 (16.8 yaşta 12-17.5) | içinde | Kansızlık yok |
| 16.2 / 16.8 / 16.9 | MCV | 86.6 / 89.0 / 87.3 fL | 80-100 (82-98) | içinde | – |
| 16.8 / 16.9 | MCHC | 31.7 / 33.4 g/dL | 32-36 | 16.8'de çok hafif altında, 16.9'da içinde | – |
| 16.2 | **Fosfor** | **4.9 mg/dL** | 2.5-4.5 | **üstünde** | Aşağıdaki nota bakınız |
| 16.2 | Kalsiyum | 10.29 mg/dL | 8.8-10.6 | içinde | – |
| 16.2 | TSH / serbest T4 | 1.668 mIU/L / 0.77 ng/dL | 0.38-5.33 / 0.60-1.34 | içinde | – |
| 16.2 | CRP | 0.27 mg/L | 0-5 | içinde | İltihap yok, ferritin eşiği 15 geçerli |
| 16.2 | ALT / AST / kreatinin | 16 / 20 U/L / 0.69 mg/dL | 0-50 / 0-50 / 0.67-1.17 | içinde | – |
| 16.2 | B12 / folat | 363 ng/L / 5.8 µg/L | 222-1439 / > 3.9 | içinde | – |

**Sürüm 1'e etkisi:**
- **Model geçerliliği:** Kronik hastalık ve iltihap göstergeleri (CRP, karaciğer, böbrek) ve tiroid normal. Sürüm 1'in "sağlıklı büyüme" varsayımıyla çelişen bir bulgu yok; büyüme tahmini geçerli kalıyor.
- **Tiroid:** Büyüme yavaşlamasının tedavi edilebilir bir nedeni olan tiroid bozukluğuna işaret yok. Serbest T4 aralığın alt yarısında, TSH normal.
- **Fosfor:** Laboratuvarın kullandığı 2.5-4.5 mg/dL yetişkin aralığı. Çocuk ve ergenlerde fosforun yetişkinden yüksek olması ve büyümeyle ilişkili olması yaygın bilinen bir durum, ama bu sürümde yaşa özgü bir referans aralığı kaynaktan açılamadı: [doğrulanmadı]. Bu yüzden fosfor büyüme sürüyor diye kanıt olarak **kullanılmadı.**
- **Eksik bırakılmamış mı?** Beslenme araştırması, 16 yaşından sonra boyu korumak için yapılacak şeyin "fazlası değil, eksik bırakmamak" olduğunu bulmuştu. Bu vakada o listenin iki maddesi somut olarak eksik ya da sınırda:
  - **D vitamini:** eşiğin altında.
  - **Demir deposu:** laboratuvara göre düşük, DSÖ'ye göre sınırda. Hemoglobin normal ve yükseliyor, yani kansızlık yok.
- Bu iki değer ölçümden sonra (16.8 ve 16.9 yaştaki tahlillerde) **tekrarlanmamış.**

**Kalan büyüme için eksik olan testler:**
- **ALP (alkalen fosfataz):** büyüme sürerken yüksektir.
- **IGF-1:** büyüme hormonu ekseni.
- **Kemik yaşı röntgeni:** plakların durumunu doğrudan gösterir, en güçlü bilgi kaynağıdır.

Bu tahlillerde üçü de yok. Sürüm 1'in belirsiz ölçümlerle verebildiği aralığı ancak bunlar daraltabilir.

## Sonuçlar

1. **Tahliller, sürüm 1'in büyüme tahminini geçersiz kılacak bir şey göstermiyor.** Tiroid, iltihap, karaciğer ve böbrek göstergeleri laboratuvar aralığında. (V)
2. **D vitamini, IOM 2011'in nüfus ihtiyacı eşiğinin (20 ng/mL) altında: 18.73.** (V + C)
3. **Ferritin laboratuvar aralığının altında (16.9; alt sınır 23.9), ama DSÖ 2020'nin ergenlerde demir eksikliği eşiğinin (< 15) hemen üstünde.** Hemoglobin normal ve sonraki iki tahlilde yükselmiş. Doğru tanım: kansızlık olmadan sınırda düşük demir deposu. (V + C)
4. **Önceki araştırmanın "eksik bırakma" ilkesi bu vakada D vitamini ve demir deposu olarak somutlaşıyor.** İkisinin de tekrar ölçülüp gerekiyorsa düzeltilmesi hekim kararıdır. Bunun boya etkisinin büyüklüğü bilinmiyor; düzeltmenin gerekçesi önce kemik ve genel sağlık. (C + D)
5. **Kalan büyüme sorusunu tahliller değil, kemik yaşı röntgeni ve standart boy ölçümü çözer.** Mevcut tahlillerde ALP ve IGF-1 yok. (C)

## Sınırlamalar

- **Tek vaka.** Genelleme yapılamaz.
- **Kimliksizleştirme sınırlı.** Ad, tarih ve kurum çıkarıldı. Yine de bir vakanın yaş ve tahlil değerlerinin birlikte yayınlanması, onu tanıyan biri için tamamen anonim değildir. Veri sahibi bunu bilerek yayın istedi.
- **Laboratuvarlar farklı.** Aralıklar laboratuvardan laboratuvara değişir; aynı test için farklı aralıklar görüldü (hemoglobin, MCV).
- **D vitamini mevsime bağlı.** Ölçüm bir kez yapıldı; zamanına göre değişir.
- **Ferritin akut faz proteinidir.** Bu tahlilde CRP normal, ama tek ölçümdür.
- **Fosfor için yaşa özgü aralık doğrulanamadı** ([doğrulanmadı]); sonuçlarda kullanılmadı.

## Kaynaklar

- [Ross ve ark. 2011, The 2011 report on dietary reference intakes for calcium and vitamin D from the Institute of Medicine: what clinicians need to know, JCEM](https://pubmed.ncbi.nlm.nih.gov/21118827/): ≥ 20 ng/mL (50 nmol/L) nüfusun %97.5'inin ihtiyacını karşılar.
- [WHO 2020, WHO guideline on use of ferritin concentrations to assess iron status in individuals and populations](https://iris.who.int/handle/10665/331505): ergenlerde (10-19 yaş) iltihap yokken < 15 µg/L, iltihap varken < 70 µg/L demir eksikliği.
- [Sürüm 1: belirsiz ölçümlerle tahmin ve Berkeley doğrulaması](../1-belirsiz-olcumlerle-tahmin/README.md)
- [Beslenme, uyku ve boy, sürüm 1: "eksik bırakmama" sonucu](../../beslenme-uyku-ve-boy/1-fizyoloji-simulasyonu/README.md)

## En basit özet

- **Tahlillerde büyümeyi durduracak bir hastalık işareti yok.** Tiroid, karaciğer, böbrek ve iltihap değerleri normal; boy tahmini geçerli.
- **D vitamini biraz düşük** (18.7; 20 ve üstü yeterli kabul ediliyor). Güneş ve hekim kontrolü.
- **Demir deposu sınırda** (ferritin 16.9; laboratuvar "düşük" diyor, DSÖ'nün eksiklik sınırı 15). Kansızlık yok.
- **İkisi de bir daha ölçülmemiş.** Tekrar ölçtürmek mantıklı. Takviye kararı ve dozu hekimin.
- **"Daha uzar mıyım" sorusunu bu tahliller cevaplamıyor.** Kemik yaşı röntgeni, ALP ve IGF-1 cevaplar.
- **Benzetme:** Tahliller arabanın yağına ve suyuna bakmak gibi. Motor sağlam, iki sıvı biraz eksik. Ama yolun ne kadar kaldığını göstermiyor; onu kemik yaşı gösterir.
