# Araştırma

Crucible ekibinin araştırma deposu. Her araştırma kökte kendi başlığıyla açılmış bir
klasörde yaşar. Bir araştırma derinleştikçe aynı klasörün içine numaralı yeni
sürümler eklenir.

## Araştırmalar

| Klasör | Konu | Güncel sürüm |
|---|---|---|
| [boy-uzamasi-16-18-yas](boy-uzamasi-16-18-yas/) | Plakları açık 16-18 yaş gençlerde genetik boy potansiyeline ulaşmak | [2 · gerçek veriyle doğrulama](boy-uzamasi-16-18-yas/2-gercek-veriyle-dogrulama/) |

---

## Kurallar

Kurallar `kontrol.py` ile otomatik denetlenir. **Denetimden geçmeyen sürüm yayınlanmaz.**

```bash
python kontrol.py
```

### 1. Klasör ve sürüm düzeni

```
<konu-basligi>/
  README.md                      konu dizini: sürümlerin listesi ve hangisinin güncel olduğu
  1-<surum-adi>/README.md        ilk sürüm
  2-<surum-adi>/README.md        sonraki sürüm
  2-<surum-adi>/analiz/          (varsa) kod, requirements.txt, calistir.py, ciktilar/
```

- Klasör adları küçük harf, rakam ve tire. Türkçe karakter yok.
- Sürümler 1'den başlar ve boşluksuz artar. Sürüm adı ne değiştiğini söyler (ör. `2-gercek-veriyle-dogrulama`).
- **Eski sürümler silinmez ve içerikleri değiştirilmez.** Tek izin verilen değişiklik en üste "güncel sürüm" bağlantısı eklemektir. Böylece neyin ne zaman, neden değiştiği her zaman görülür.
- Konu dizini (`<konu>/README.md`) her sürüme bağlantı verir.

### 2. Sürüm raporunun zorunlu bölümleri

Güncel sürümün `README.md` dosyası şu `##` başlıklarını içermek zorunda:

| Bölüm | İçerik |
|---|---|
| **Soru ve kapsam** | Tam olarak neyi soruyoruz, neyi sormuyoruz |
| **Önceki sürümden değişenler** | (2. sürümden itibaren) neyin değiştiği, neyin düzeltildiği, neden |
| **Yöntem** | Veri, model, analiz. Başkası tekrar edebilecek kadar açık |
| **Bulgular** | Sayılar, tablolar, grafikler |
| **Sonuçlar** | Numaralı maddeler. **Her madde kanıt seviyesi etiketi taşır** |
| **Sınırlamalar** | Neyin yanlış olabileceği, açıkça |
| **Kaynaklar** | Bağlantılı kaynak listesi |
| **En basit özet** | **Son bölüm.** Madde madde, hiç bilmeyen birinin anlayacağı dilde |

Ayrıca raporun başında bir `**Sürüm:**` satırı ve bir kanıt seviyeleri tablosu bulunur.

### 3. Kanıt seviyeleri

| Etiket | Anlamı |
|---|---|
| **A** | Meta-analiz ya da birden çok randomize kontrollü çalışma |
| **B** | Tek RCT ya da büyük, iyi tasarlanmış kohort |
| **C** | Gözlemsel çalışma, vaka serisi, mekanizma |
| **V** | Bu çalışmanın kendi gerçek veri analizi |
| **D** | Model çıktısı ya da varsayım. Yön gösterir, kesin sayı vermez |

Sonuçlar bölümündeki her madde `(A)`, `(B + D)`, `(A-B)` gibi bir etiketle biter.

### 4. Kaynak kuralı

- Her kaynak bağlantılıdır ve o sürüm hazırlanırken **açılıp kontrol edilir**.
- Kontrol edilemeyen kaynak `[doğrulanmadı]` etiketi taşır. **Sonuçlar bölümü doğrulanmamış kaynağa dayanamaz.** Denetim bunu kontrol eder.
- Bir sayı ya bir kaynağa, ya bu çalışmanın verisine (V) ya da açıkça modele/varsayıma (D) bağlanır. Kaynaksız sayı yazılmaz.
- Önceki sürümde bulunan kaynak hatası, "Önceki sürümden değişenler" tablosunda açıkça yazılır.

### 5. Analiz ve simülasyon kuralı

- Analiz klasörü varsa `requirements.txt` ve tek komutla her şeyi üreten `calistir.py` bulunur.
- Sabit rastgele tohum: aynı kod her seferinde aynı sayıyı üretir.
- Dış veri repoya kopyalanmaz. Kaynağından indirilir ve hash (SHA-256) ile doğrulanır.
- Raporda geçen her sayı `ciktilar/` altındaki bir dosyadan gelir.
- Gerçek veriyle doğrulanmamış model "kanıt seviyesi D" diye etiketlenir. Bilinmeyen parametreler için **duyarlılık analizi** zorunludur.
- **Şaşırtıcı sonuç önce hata sayılır.** Beklenmedik bir sayı çıkarsa yayınlamadan önce kod kontrol edilir ve bulunan hata raporda yazılır.

### 6. Sağlık konuları

- Rapor başında "tıbbi tavsiye değildir" uyarısı bulunur.
- İlaç ve tedavi yalnızca "hekim kararıyla" çerçevesinde anılır. Doz ve kullanım talimatı yazılmaz.
- Zararlı olduğu bilinen şeyler (doping, onaysız ilaç) açıkça "yapma" diye yazılır.

### 7. Yayın akışı

1. Yeni sürüm klasörünü aç: `<konu>/<n+1>-<ad>/`.
2. Analiz varsa `python calistir.py` ile çıktıları üret.
3. Raporu yaz. Her kaynağı aç ve kontrol et.
4. Eski sürümün README'sinin en üstüne güncel sürüm bağlantısını ekle. Konu dizinini ve bu dosyadaki tabloyu güncelle.
5. `python kontrol.py` geçmeden commit/push yok.
