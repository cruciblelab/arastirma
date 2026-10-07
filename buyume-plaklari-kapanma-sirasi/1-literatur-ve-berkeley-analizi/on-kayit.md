# Ön Kayıt: Bacak ve Gövde Büyümesinin Bitiş Sırası (Berkeley)

> **Tarih:** 2026-10-07 · Analiz kodu yazılmadan ve veri bu soru için incelenmeden önce commit edildi.
>
> **Şeffaflık notu:** Boy araştırmasının sürüm 3 modeli, 16 yaştan sonra erkeklerde kalan büyümenin (~3.4 cm) büyük kısmının gövdeden geldiğini **model çıktısı** olarak göstermişti (bacak 0.40, gövde 2.99 cm). Aynı Berkeley verisi o modelin kalibrasyonunda kullanıldı. Bu yüzden H3 tamamen kör değildir. H1 ve H2 bu veride daha önce hiç hesaplanmadı.

## Soru

Vücuttaki büyüme plakları aynı anda kapanmaz. Bacak (uzun kemikler, özellikle diz çevresi) büyümesi bittikten sonra gövde (omurga ve leğen) büyümeye devam ediyor mu? Ediyorsa ne kadar?

## Veri

- Berkeley Child Guidance Study, `sitar` 1.5.0 paketi (SHA-256 `312466b96e1a38fea4d4bc591f91c69dfe7b425fb92aef9ccd02db00c40b97c5`).
- Boy ve oturma boyu ("stem length") yarım yıllık aralıklarla ölçülmüş.
- Gövde = oturma boyu (leğen + omurga + baş). Bacak = boy − oturma boyu.
- Boy araştırması sürüm 3'ün `veri.py` modülüyle indirilir ve doğrulanır.

## Tanımlar

- **Bitiş yaşı (bölme başına):** Kişinin son ölçümüne kadar o bölmede kalan büyümenin ilk kez ≤ 0.5 cm olduğu yaş. Duyarlılık: 0.3 ve 1.0 cm.
- **Kalan gövde büyümesi:** Bacak bitiş yaşından son ölçüme kadar gövdedeki artış.
- **Sansür:** Berkeley ölçümleri 18-21 yaşta bitiyor. Son ölçümde hâlâ büyüyen bölmenin bitiş yaşı bilinemez. Bu yüzden şu üç büyüklük **alt sınırdır** ve öyle raporlanır:
  - gövde bitiş yaşı;
  - kalan gövde büyümesi;
  - "gövde bacaktan sonra biter" oranı.

  "Son 1 yılda gövde > 0.5 cm uzadı" olanlar sansürlü sayılır ve ayrıca raporlanır.
- **Dahil etme:** 13.0 yaşından önce ve 18.0 yaşında ya da sonrasında, boy ve oturma boyu ölçümü olan kişiler.

## Hipotezler (sonuç ne olursa olsun raporlanır)

| # | Hipotez | Destek ölçütü |
|---|---|---|
| H1 | Gövde büyümesi bacaktan **sonra** biter | Kişilerin ≥ %60'ında gövde bitiş yaşı > bacak bitiş yaşı (her cinsiyet ayrı) |
| H2 | Bacak büyümesi bittikten sonra gövde hâlâ anlamlı uzar | Erkeklerde kalan gövde büyümesi medyanı ≥ 0.5 cm |
| H3 | 16 yaştan sonraki boy artışının çoğu gövdeden gelir | Erkeklerde 16 yaştan son ölçüme toplam artışın medyan gövde payı > %50 |

## Ek (keşifsel, hipotez değil)

- Bacak bitiş yaşı ve gövde bitiş yaşı dağılımları.
- Kızlarda aynı büyüklükler.
- Sürüm 3 modelinin bölme bazında aynı büyüklükleri (D), gerçek veriyle karşılaştırma için.

## Sınırlamalar (önceden bilinen)

- Berkeley 1930'lar ABD kohortu, 136 kişi. Ölçüm hatası her ölçümde ~0.3-0.5 cm; iki ölçüm farkında daha büyük. 0.5 cm eşiği bu yüzden duyarlılıkla sınanır.
- Oturma boyu, omurganın yanında leğen ve kafa tabanını da içerir. "Omurga büyümesi" tam olarak ayrıştırılamaz.
- Diz plaklarının kapanması doğrudan görülmez. "Bacak büyümesi bitti" ölçümle tanımlanır, röntgenle değil.

## Plandan sapmalar

| Tarih | Ne değişti | Neden | Sonuç görüldükten sonra mı? |
|---|---|---|---|
| – | – | – | – |
