# Kişisel Büyüme Analizi (tek kişilik vaka aracı)

> Bu araştırma tıbbi tavsiye değildir. [Sorumluluk Reddi Beyanı](../SORUMLULUK-REDDI.md) bütün sürümleri için geçerlidir.

Saati, ayakkabısı ve tarihi belirsiz okul/ev ölçümleri ve anne-baba boyundan; son yıllardaki uzama, büyümenin sürüp sürmediği ve kalan boy ne kadar dürüst tahmin edilebilir?

**Gizlilik:** Gerçek kişilerin boy verisi ve kişisel sonuçları bu repoya girmez (`.kisisel/` klasörü `.gitignore` ile dışlanır). İstisna: Sürüm 2'deki seçilmiş tahlil değerleri, veri sahibinin açık isteğiyle ve kimliksizleştirilerek yayınlandı.

| Sürüm | Ad | Tarih | Ne yapıldı |
|---|---|---|---|
| **2 (güncel)** | [2-tahlil-bulgulari](2-tahlil-bulgulari/) | 2026-10-07 | Vakanın analizi etkileyen 22 tahlil değeri (veri sahibinin isteğiyle, kimliksizleştirilmiş) laboratuvar aralıkları ve yayınlanmış eşiklerle (IOM 2011, DSÖ 2020) değerlendirildi. D vitamini eşiğin altında, ferritin sınırda; büyüme tahminini geçersiz kılan bulgu yok |
| 1 | [1-belirsiz-olcumlerle-tahmin](1-belirsiz-olcumlerle-tahmin/) | 2026-10-07 | Belirsiz okul/ev ölçümlerinden Bayesçi kalan boy tahmini; Berkeley'de 66 gerçek gençle doğrulama. 5 ön kayıtlı testten 3'ü geçti: tahminin merkezi iyi (hata 0.49 cm), aralıklar fazla dar (kapsama %30) → Berkeley hatalarıyla kalibre edildi |

**Hızlı cevap için:** [Sürüm 2 → En basit özet](2-tahlil-bulgulari/README.md#en-basit-özet) · [Sürüm 1 → En basit özet](1-belirsiz-olcumlerle-tahmin/README.md#en-basit-özet)

İlgili: [boy-uzamasi-16-18-yas](../boy-uzamasi-16-18-yas/) (büyüme modeli), [spor-egzersiz-ve-boy](../spor-egzersiz-ve-boy/) (gün içi boy değişimi).

## Sonradan bulunan düzeltmeler

| Nerede | Ne yazıyordu | Doğrusu | Kaynak |
|---|---|---|---|
| Sürüm 1, `simulasyon/vaka.py` (ızgara) | Önsel boy eğrileri 0.05 yıl aralıklı ızgarada kaydediliyordu | Büyüme modeli kayıt yaşlarını 0.02 yıllık adıma yuvarlıyor; bu yüzden ızgara noktalarının yarısı ±0.01 yıl kaymış kaydedildi. Etkisi boy değerinde en fazla 1.7 mm (ölçüm pencerelerinde en fazla 1.3 mm, medyan 0). Okul ölçümlerinin ~1 cm hatası yanında sonuçları ve testleri değiştirmez. Yeni çalışmalarda 0.02'nin katı olan ızgara kullanılıyor | [omurga-buyumesi, sürüm 1, PLAN sapmaları](../omurga-buyumesi/1-kaldiraclar-protokol-ve-animasyon/simulasyon/PLAN.md) |
