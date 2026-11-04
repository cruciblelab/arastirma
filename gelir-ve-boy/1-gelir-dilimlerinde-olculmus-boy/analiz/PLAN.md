# Ön kayıt: Gelir dilimlerinde ölçülmüş boy — zenginler ne kadar uzun?

> **Durum:** Bu plan, aşağıdaki analizler **çalıştırılmadan önce** yazıldı ve commit edildi. Değişiklikler "Plandan sapmalar" bölümüne tarih ve gerekçeyle eklenecek.
>
> **Tarih:** 2026-11-04

## Soru

Yüksek gelirli, yüksek hayat standardında yaşayan yetişkinler ortalamada ne kadar uzun? En yüksek gelir dilimi ile en düşük dilim ve ortanca arasında kaç cm fark var? Bu farkın ne kadarı bölge, ırk/köken ve kent-kır gibi bileşim farklarından geliyor? En tepede (en zengin %1) fark büyümeye devam ediyor mu?

## Veri

| Kod | Veri | Boy | Gelir | Erişim |
|---|---|---|---|---|
| BR | IBGE POF 2008-09 (Brezilya), kişi dosyası (SHA-256 `cc2d5279…a265`; "kadınların boy beklentisi" araştırmasıyla aynı dosya) | **Ölçülmüş** (V0434) | Hanenin (tüketim birimi) kişi başı aylık geliri (RENDA_PERCAPITA) | Kamu verisi |
| US | NHANES 2017-Mart 2020 (ABD, CDC), P_DEMO ve P_BMX (SHA-256 `2e46c6c2…7913`, `7038d0da…ed66`) | **Ölçülmüş** (BMXHT) | Ailenin gelir/yoksulluk sınırı oranı (INDFMPIR; 5'te kesilmiş) | Kamu verisi |

**Önemli sınır:** NHANES gelir oranı 5'te kesildiği için ABD'de en üst grup "yoksulluk sınırının ≥ 5 katı" (kabaca en zengin beşte bir); en zengin %1 ayrılamaz. Brezilya'da en zengin %1 ayrılabilir.

## Örneklem

- 25-59 yaş, ölçülmüş boyu 130-215 cm arasında, gelir bilgisi olan yetişkinler. Erkek ve kadın ayrı.
- BR: Ağırlık PESO_FINAL; küme COD_UPA. US: ağırlık WTMECPRP; küme SDMVSTRA × SDMVPSU.
- Hamile kadınlar (BR V0406, US RIDEXPRG = 1) dışarıda.

## Analizler

- **A1. Dilim ortalamaları.** Gelir dilimleri, aynı cinsiyet ve yaş aralığındaki kişiler arasında ağırlıklı yüzdeliklere göre:
  - BR: 10 dilim + en zengin %1.
  - US: gelir oranı grupları <1, 1-2, 2-3, 3-4, 4-5, ≥5.
  - Her dilimde ağırlıklı ortalama boy (cm).
- **A2. Ham farklar:**
  - BR: en üst dilim − en alt dilim; en üst dilim − 5. ve 6. dilimler (ortanca); en zengin %1 − en üst dilim.
  - US: ≥5 − <1; ≥5 − 2-3.
  - Güven aralığı: küme bootstrap, 1.000 tekrar, tohum 20261104.
- **A3. Düzeltilmiş farklar:** Ağırlıklı doğrusal model: boy ~ gelir dilimi göstergeleri + yaş (5 yıllık grup) + bileşim.
  - BR bileşim: eyalet (COD_UF), kent/kır, ırk/renk (V0429).
  - US bileşim: ırk/köken (RIDRETH3), ABD'de doğmuş olmak (DMDBORN4).
  - Aynı farklar düzeltilmiş olarak raporlanır.
- **A4. Eğim:** Gelir yüzdeliğinde 10 puanlık artış başına cm (doğrusal, ham ve düzeltilmiş).

## Ön kayıtlı testler

**Teknik:**

| Kod | Test | Ölçüt |
|---|---|---|
| T1 | Veri dosyalarının SHA-256 özeti | Kayıtlı değerlerle aynı |
| T2 | BR örneklemi: 25-59 yaş erkek ve kadın, ölçülmüş boy + gelir | Her cinsiyette ≥ 20.000 |
| T3 | US örneklemi: 25-59 yaş, ölçülmüş boy + gelir oranı | Her cinsiyette ≥ 1.500 |
| T4 | US ortalama erkek boyu makul aralıkta (ağırlıklı) | 172-178 cm |

**Hipotezler:**

| Kod | Hipotez | Geçme ölçütü |
|---|---|---|
| H1 | BR: en üst gelir dilimindeki erkekler en alt dilimdekilerden en az 3 cm uzun (ham) | fark ≥ 3 cm ve GA alt > 0 |
| H2 | BR: bölge, kent-kır ve ırk düzeltmesi farkı küçültüyor ama sıfırlamıyor (erkek) | düzeltilmiş < ham ve düzeltilmiş GA alt > 0 |
| H3 | US: ≥5 grubu erkekleri <1 grubundan uzun (ham) | fark GA alt > 0 |
| H4 | US: ırk/köken ve doğum yeri düzeltmesinden sonra da fark kalıyor (erkek) | düzeltilmiş GA alt > 0 |
| H5 | Kadınlarda da gradyan var (BR ve US, en üst − en alt, ham) | ikisinde de GA alt > 0 |
| H6 | BR: tepede plato — en zengin %1, en üst dilimin geri kalanından belirgin uzun değil (erkek) | (en zengin %1 − en üst dilim) GA üst < 2 cm |

## Karar kuralları

- **K1:** BR'de en üst dilim − ortanca farkı (erkek, düzeltilmiş) < 2 cm ise "zenginler ortalamadan biraz uzun"; 2-4 cm ise "belirgin uzun"; > 4 cm ise "çok uzun" denecek.
- **K2:** Ham ile düzeltilmiş fark arasındaki oran raporlanacak: farkın ne kadarı bileşimden geliyor.
- **K3:** Nedensellik dili: Bu analiz ilişkiyi ölçer, yönü ayıramaz. Raporda yön yorumu yalnız literatüre (G1, G2) dayanarak ve "D" etiketiyle yapılacak.

## Simülasyon kuralları

Simülasyon yok.

## Plandan sapmalar

1. **Bootstrap'te tekil matris (ilk çalıştırma, 2026-11-04):** ABD verisinde küme sayısı az (~50); bazı bootstrap örneklerinde nadir bir kategori (ör. doğum yeri "bilinmiyor") boş kalınca düzeltilmiş model çözülemedi. Bootstrap çözümüne çok küçük bir sırt terimi (1e-8) eklendi; ana tahminleri değiştirmez. Brezilya sonuçları ilk çalıştırmayla aynı.
