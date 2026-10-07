# Araştırma

Crucible ekibinin araştırma deposu. Her araştırma, kök dizinde kendi başlığıyla
açılmış ayrı bir klasörde yaşar.

## Kural

```
<arastirma-basligi>/
  README.md        ana rapor: özet, bulgular, kanıt düzeyi, sınırlamalar, kaynaklar
  simulasyon/      (varsa) kod + requirements.txt + ciktilar/
```

- Klasör adları küçük harf, tireli, Türkçe karakter olmadan (ör. `boy-uzamasi-16-18-yas`).
- Her iddianın yanında kanıt düzeyi; varsayımlar açıkça "varsayım" diye yazılır.
- Simülasyonlar sabit tohumla tekrar üretilebilir olmalı.

## Araştırmalar

| Klasör | Konu | Durum |
|---|---|---|
| [boy-uzamasi-16-18-yas](boy-uzamasi-16-18-yas/) | Plakları açık 16-18 yaş gençlerde genetik boy potansiyeline ulaşmak | v1 |
