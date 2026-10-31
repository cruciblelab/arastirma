# Ön kayıt: Ağırlıklı puan tablosu — kadınlar bir erkekte neye ne kadar ağırlık veriyor?

> **Durum:** Bu plan, puanlar hesaplanmadan önce yazıldı ve commit edildi. Sonradan yapılan her değişiklik "Plandan sapmalar" bölümüne yazılacak.
>
> **Tarih:** 2026-10-31

## Soru

Gerçek kadınların kararlarında bir erkeğin özelliklerinin her biri ne kadar ağırlık taşıyor? Farklı veri setlerindeki etkiler **tek bir 100 puanlık ölçekte** nasıl sıralanıyor? Türk kadınları ne söylüyor?

## Körlük beyanı (önemli)

Bu sürüm **yeni bir veri toplamıyor**; sürüm 1 ve 3'te ve "kadınların boy beklentisi" araştırmasında analiz edilmiş dört veri setini **ortak bir ölçeğe** çeviriyor. Ham etkilerin çoğu daha önce görüldü:

- HT (hızlı tanışma): sürüm 1'de kadın kararında çekicilik +12,9, ortak ilgi +8,4, komiklik +5,9, zekâ +3,2 yp (1 SS başına).
- UV: sürüm 3'te 1 SS fotoğraf +11,8, 7 cm boy +1,2, 15 IQ +2,3 yp.
- SL: boy beklentisi araştırmasında 8 özelliğin etkileri (keşif) görüldü.
- WA (45 ülke): sürüm 1'de Türk kadınlarında zekânın birinci olduğu görüldü.

Bu yüzden testler **kör değildir**; asıl ön kayıtlı olan, **puanlama kuralı** ve **sınıflandırma eşikleri**dir. Kural, hangi özelliğin kaçıncı çıkacağı bilinerek ama sonuç tablosu hesaplanmadan sabitleniyor.

## Veri

| Kod | Veri | Karar türü | Özellikler |
|---|---|---|---|
| HT | Fisman ve Iyengar hızlı tanışma (Columbia), kadın karar verenler | Gerçek 4 dakikalık buluşma sonrası "evet/hayır" | Kadının o erkek için verdiği puanlar: çekicilik, samimiyet, zekâ, komiklik, hırs, ortak ilgi |
| UV | Witmer ve ark. 2025 (OSF 84abw), 224 kadın | Rastgele profiller arasında seçim | Fotoğraf çekiciliği, boy, IQ, biyografi, meslek |
| SL | Sleiman, Melios ve Dolan 2025 (Dataverse G1H0UA), 1.250 kadın | İki profil arasında seçim | 8 ikili özellik: çekici, uzun (182,9 / 172,7), üniversite, beyaz ırk, İşçi Partili, hoşgörülü, ilerici, vejetaryen |
| WA | Walter ve ark. 2020 (OSF), 45 ülke; Türk kadınlar | Söylenen önem (1-7) | İyi kalplilik, zekâ, sağlık, fiziksel çekicilik, kaynak (maddi imkân) |

## Puanlama kuralı

1. **Etki:** Her davranış kaynağında (HT, UV, SL) kadın içi (kadın sabit etkili) doğrusal olasılık modeliyle, tüm özellikler birlikte; seçilme/evet olasılığı yüzde puan (yp).
   - **HT:** Her puan değişkeni kadın içi standart sapmaya bölünür; etki = kadının o erkek hakkındaki algısı 1 SS yükselince.
   - **UV:** "Gerçekçi fark" = 1 SS. Boy için erkek nüfus SS'si 7 cm; IQ için 15 puan; diğerleri (fotoğraf, biyografi, meslek) profil havuzunun SS'si.
   - **SL:** İkili özellik; etki = yüksek düzey − düşük düzey. Boy için 10,2 cm fark 7 cm'ye ölçeklenir (doğrusal kabul).
   - Güven aralığı: kadına göre küme bootstrap, 2.000 tekrar, tohum 20261031.
2. **Puan (0-100):** Her kaynakta, pozitif etkilerin toplamı 100 olacak şekilde: puan = 100 × etki / Σ(pozitif etkiler). Negatif etkiler ayrı listelenir, puana girmez.
3. **Ortak kategoriler:**

| Kategori | HT | UV | SL |
|---|---|---|---|
| Görünüş (yüz/fotoğraf) | çekicilik | fotoğraf çekiciliği | çekici |
| Boy | — | boy | uzun |
| Zekâ | zekâ | IQ | — |
| Eğitim / meslek / hırs | hırs | meslek | üniversite |
| Kişilik: samimiyet / hoşgörü | samimiyet | — | hoşgörülü |
| Mizah / eğlence | komiklik | — | — |
| Ortak ilgi / uyum | ortak ilgi | — | — |
| Kendini anlatma (profil yazısı) | — | biyografi | — |
| Siyasi değerler (İngiltere'ye özgü) | — | — | İşçi Partili, ilerici |
| Diğer (ırk, beslenme) | — | — | beyaz, vejetaryen |

4. **Genel davranış puanı:** Bir kategorinin bulunduğu davranış kaynaklarındaki puanlarının ortalaması. Kaç kaynakta bulunduğu yanına yazılır.
5. **Söylenen (WA):** Türk kadınlarında her özelliğin ortalama puanı (1-7) ve kişi içi merkezlenmiş göreli önem (kadının kendi 5 puanının ortalamasından fark). 45 ülkenin kadınlarıyla karşılaştırılır.
6. **Değiştirilebilirlik (D):** Her kategori için 0-3 arası yargı (0 = değiştirilemez, 3 = davranışla kısa sürede değişir), gerekçesiyle. Bu bir veri değil, yorumdur; puan tablosundan ayrı sütunda gösterilir.

## Sınıflandırma (karar kuralları)

- **K1:** Genel davranış puanı ≥ 25 → "en büyük ağırlık"; 12-25 → "büyük"; 6-12 → "orta"; < 6 → "küçük".
- **K2:** Bir kategori yalnız tek kaynakta varsa, sınıfın yanına "tek kaynak" yazılır.
- **K3:** Söylenen (WA) sıralama ile davranış sıralaması farklıysa ikisi de yazılır.

## Ön kayıtlı testler

| Kod | Test | Ölçüt |
|---|---|---|
| T1 | Dört veri dosyasının SHA-256 özeti | Önceki sürümlerdekiyle aynı |
| T2 | HT kadın çekicilik etkisi sürüm 1'i tekrar ediyor | 12,9 ± 0,3 yp |
| T3 | UV boy etkisi sürüm 3'ü tekrar ediyor (7 cm) | 1,2 ± 0,3 yp |
| T4 | WA Türk kadın sayısı | ≥ 500 |
| H1 | HT ve UV'de görünüş en yüksek puanlı kategori (kör değil) | ikisinde de birinci |
| H2 | Boy, her kaynakta görünüşten küçük | UV ve SL'de boy puanı < görünüş puanı; fark GA üst < 0 |
| H3 | HT'de ortak ilgi algısı zekâdan büyük (kör değil) | fark GA alt > 0 |

## Simülasyon kuralları

Simülasyon yok.

## Plandan sapmalar

(Henüz yok.)
