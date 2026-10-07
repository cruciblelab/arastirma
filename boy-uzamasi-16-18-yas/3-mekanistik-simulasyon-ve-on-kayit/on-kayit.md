# Ön Kayıt: "Geçen Yıl Kuralı"nın Gerçek Veriyle Testi

> **Kayıt tarihi:** 2026-10-07 · **Durum:** kayıtlı, henüz yeni veri yok
>
> Bu belge, kuralı test edecek **yeni bir veri setine bakılmadan önce** yazılıp commit edildi. Yeni veri geldiğinde analiz yalnızca burada yazıldığı gibi yapılır. Sonradan yapılan her ek analiz "keşifsel" diye ayrıca etiketlenir ve hipotez testi yerine geçmez.

## 1. Neden ön kayıt?

Benzetme: Okun nereye düştüğünü gördükten sonra hedefi oraya çizersen her atış on ikiden vurmuş olur. Ön kayıt, hedefi **atıştan önce** çizmek demek.

v2'deki kural (kalan ≈ son 12 ay), onu bulduğumuz Berkeley verisinde test edildi. Bu, bulunduğu yerde test edilmiş demek, kanıtlanmış değil. Kanıt için **bağımsız** veri ve **önceden yazılmış** ölçütler gerekiyor.

## 2. Hipotezler

| Kod | Hipotez | Sonuç ölçütü | Karar kuralı |
|---|---|---|---|
| **H1 (birincil)** | Büyüme hızı yavaşlayan gençlerde kalan boy ≈ k × son 12 aydaki uzama, k ≈ 1 | 16 ve 17 yaşta, sıfırdan geçen regresyonla k ve %95 GA. Ayrı ayrı: erkek, kız | **Doğrulandı:** GA tamamen [0.7, 1.3] içinde. **Reddedildi:** GA tamamen [0.7, 1.3] dışında. **Belirsiz:** diğer durumlar |
| **H2** | Kuralın pratik hatası küçük | Tahmin edilen k ile ortalama mutlak hata | Erkek < 1.0 cm, kız < 0.6 cm |
| **H3** | Kural hâlâ hızlanan gençlerde çöküyor (kalan boyu az tahmin ediyor) | Hızlananlarda (son 12 ay > önceki 12 ay) kural hatası medyanı (gerçek − tahmin), k = 1.0 erkek, 0.9 kız | Medyan > +0.5 cm ve en az 30 hızlanan kişi |
| **H4** | 18 yaşından sonra erkeklerde anlamlı büyüme var | 18 yaş ile ≥ 24 yaş arası uzama medyanı (Add Health gibi kaynaklarda) | Medyan ≥ 0.5 cm |

**Tanımlar:**
- **Kalan boy:** kişinin en son ölçümü ≥ 19.5 yaş ise o ölçüm ile a yaşındaki ölçüm arasındaki fark. Daha önce biten takipler birincil analize girmez.
- **Yavaşlayan:** [H(a) − H(a−1)] < [H(a−1) − H(a−2)].
- **Yaş toleransı:** ölçüm hedef yaşa ±3 ay içindeyse kullanılır. Yıllık artışlar gerçek ölçüm aralığına bölünüp 12 aya ölçeklenir.

## 3. Veri gereksinimleri ve dışlamalar

- **Ölçülmüş boy:** beyan edilen boy kabul edilmez.
- **Dışlananlar:** bilinen kronik hastalık, büyüme hormonu ya da seks steroidi tedavisi (veri setinde bilgi varsa).
- **Ölçüm protokolü** (günün saati, alet, gözlemci) raporlanır. Bilinmiyorsa "bilinmiyor" yazılır. Simülasyon (Ö7 ve duyarlılık analizi), protokolün sonucu ne kadar etkileyebileceğini gösteriyor.

## 4. Analiz

- **Kod:** sürüm 2'deki `analiz/calistir.py` içindeki `c_hiz_kurali` fonksiyonunun mantığı (sıfırdan geçen regresyon). Yeni veri için uyarlama yalnızca okuma kısmında yapılır.
- **Güven aralığı:** t dağılımıyla. Aile ya da okul gibi kümeler varsa küme bootstrap'ı (2.000 tekrar).
- **Çoklu karşılaştırma:** H1 dört hücrede (2 cinsiyet × 2 yaş) test edilir. "Kural doğrulandı" demek için **dört hücrenin dördü** de doğrulanmalı. Herhangi biri reddedilirse kural o hücre için reddedilmiş sayılır.

## 5. Hangi veriyle, hangi sırayla

`veri-setleri.md`'deki öneri sırası:
1. Zhongshan kohortu (yazarlardan istenecek)
2. Add Health (H4 için)
3. ALSPAC
4. Kendi ileriye dönük çalışmamız

Kendi çalışmamızın tasarımı, simülasyonun güç analizine göre belirlenir (sürüm 3 README, "Çalışma tasarımı" bölümü).

## 6. Bu belgede değişiklik

| Tarih | Değişiklik | Neden |
|---|---|---|
| - | (yok) | - |
