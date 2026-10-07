# Araştırma

Crucible ekibinin araştırma deposu. Her araştırma kökte kendi başlığıyla açılmış bir
klasörde yaşar. Bir araştırma derinleştikçe aynı klasörün içine numaralı yeni
sürümler eklenir.

## Araştırmalar

| Klasör | Konu | Güncel sürüm |
|---|---|---|
| [boy-uzamasi-16-18-yas](boy-uzamasi-16-18-yas/) | Plakları açık 16-18 yaş gençlerde genetik boy potansiyeline ulaşmak | [3 · mekanistik simülasyon ve ön kayıt](boy-uzamasi-16-18-yas/3-mekanistik-simulasyon-ve-on-kayit/) |
| [spor-egzersiz-ve-boy](spor-egzersiz-ve-boy/) | 16 yaş ve sonrasında barfiks, şınav, esneme, asılma ve sporların gerçek boya etkisi | [1 · fizik tabanlı simülasyon](spor-egzersiz-ve-boy/1-fizik-tabanli-simulasyon/) |
| [beslenme-uyku-ve-boy](beslenme-uyku-ve-boy/) | Gerçek besin değerleri, enerji dengesi, iştah, vücut yağı ve uykunun 16 yaş sonrası boya etkisi | taslak · [1 · fizyoloji simülasyonu](beslenme-uyku-ve-boy/1-fizyoloji-simulasyonu/) |

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

### 5b. Simülasyon kuralları (simülasyon içeren her sürüm)

- Simülasyon klasöründe kod yazılmadan önce bir **`PLAN.md`** bulunur ve commit edilir. Plan şu bölümleri içerir: **Simülasyon kuralları**, **Ön kayıtlı testler** (her test için sayısal geçme ölçütüyle), **Plandan sapmalar**.
- Her denklem bilinen bir mekanizmaya dayanır. Her parametre **ölçülmüş**, **kalibre** ya da **varsayım** diye sınıflanır. Varsayımlara duyarlılık analizi yapılır.
- Fiziksel tutarlılık kontrolleri (korunum, işaret, zaman adımı yakınsaması) kodda assert olarak bulunur.
- Testler çalıştırıldıktan sonra ölçüt değiştirilmez. Plan değişirse "Plandan sapmalar" tablosuna tarih ve gerekçeyle yazılır.
- Plan yazılmadan önce görülen her sonuç planda **şeffaflık notu** olarak belirtilir (o test tamamen kör sayılmaz).

### 5c. Taslak sürüm

- Ön kayıt gibi işler bitmeden önce paylaşılması gereken durumlarda sürüm, README'sinde `**Durum:** taslak` satırıyla push edilebilir.
- Yeni bir konunun tek sürümü taslak olabilir; o konu ilk yayına kadar "taslak" olarak listelenir.
- Taslak her zaman en yüksek numaralı sürümdür, "güncel sürüm" sayılmaz. Tam rapor denetimi taslak kalktığında uygulanır.

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
