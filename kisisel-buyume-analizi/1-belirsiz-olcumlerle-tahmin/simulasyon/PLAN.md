# Simülasyon Planı: Belirsiz Ev ve Okul Ölçümlerinden Kişisel Kalan Boy Tahmini

> **Plan sürümü:** 1 · **Tarih:** 2026-10-07 · **Durum:** ön kayıt (kod yazılmadan ve çalıştırılmadan önce commit edildi)
>
> Bu dosya hiçbir sonuç görülmeden yazıldı. Testler çalıştıktan sonra ölçütler değiştirilmez. Değişiklikler "Plandan sapmalar" tablosuna yazılır.
>
> **Gizlilik kuralı:** Gerçek bir kişinin verisi (ölçümler, doğum tarihi, anne-baba boyu, tahliller) **repoya hiçbir zaman girmez.** Kişisel girdi `.kisisel/` klasöründe durur, bu klasör `.gitignore` ile dışlanmıştır. Kişisel sonuçlar da yalnızca oraya yazılır. Repodaki rapor yalnızca yöntemi, gerçek veriyle doğrulamayı ve **uydurma bir örnek kişiyi** içerir.

## 1. Soru

Bir gencin elinde genellikle düzgün ölçüm olmaz. Elinde olanlar şunlardır:
- okulda bir kez ölçülmüş, yuvarlanmış birkaç değer (saati ve ayakkabı durumu belli değil);
- kapıya çizilmiş bir işaret ("şu an akşam ölçünce işaretle aynı geliyorum");
- anne ve baba boyu.

Böyle **belirsiz** verilerle şunlar ne kadar iyi tahmin edilebilir?
1. Son yıllarda ne kadar uzadığı?
2. Büyümenin hâlâ sürüp sürmediği?
3. Kalan büyümesi ve erişkin boyu?

İkinci soru: Böyle belirsiz veriden yapılan tahmin, gerçek uzunlamasına veride (Berkeley) **dürüst** mü? Yani "%80 aralık" dediğinde gerçek değer gerçekten ~%80 oranında o aralıkta çıkıyor mu?

**Benzetme:** Bulanık birkaç fotoğraftan arabanın hızını tahmin etmek. Fotoğrafın bulanık olduğunu kabul edersen dürüst bir aralık verirsin; net sanırsan kendinden emin ama yanlış olursun.

## 2. Simülasyon kuralları

| # | Kural |
|---|---|
| S1 | Büyüme modeli yeniden kalibre edilmez. Önsel, boy araştırması sürüm 3 modelinin sanal kohortudur (`plak.kohort`, Türk uyarlamalı, `model.simule_et`). |
| S2 | Ölçüm belirsizlikleri (yaş penceresi, gün içi saat, ayakkabı, yuvarlama, işaret hatası) modele **açıkça** girer ve her biri ölçülmüş, kalibre ya da varsayım diye sınıflanır. |
| S3 | Doğrulama, gerçek uzunlamasına veride (Berkeley erkekleri) aynı bilgi yapısı **taklit edilerek** yapılır. Sentetik gürültü, modelin varsaydığıyla aynı süreçten üretilir. |
| S4 | Sabit tohum (20261007). Çıktılar `ciktilar/` (örnek kişi ve doğrulama) ve `.kisisel/ciktilar/` (gerçek kişi, repoya girmez). |
| S5 | Kanıt seviyesi: doğrulama V; kişisel tahmin D (model + varsayımlar). Tahliller modele **girmez**. Bunların büyümeye sayısal etkisini verecek kaynak yok; yalnızca laboratuvarın kendi referans aralığına göre betimlenir. Yorum hekime aittir. |
| S6 | Tıbbi tavsiye değildir. Bu araç kemik yaşı röntgeni ve hekim değerlendirmesinin yerini tutmaz. |

## 3. Model

### 3.1 Önsel (bireyin olası büyüme eğrileri)

- N = 200 000 sanal genç: `plak.kohort(cinsiyet, N, rng)`. Her birinin 11-25 yaş boy eğrisi (sabah boyu, cm) sürüm 3 modeliyle hesaplanır.
- **Anne-baba bilgisi:** Kohortun erişkin boy dağılımı (ortalama m_k, SD s_k) hedef dağılıma yeniden ağırlıklandırılır:
  - Hedef dağılım N(μ_h, 5.83²), μ_h = m_k + 0.746·(OAB − m_k).
  - OAB = (baba + anne ± 13)/2; erkekte +, kızda −.
  - Ağırlık w_önsel = φ(H25; μ_h, 5.83) / φ(H25; m_k, s_k).
  - Eğim 0.746 ve artık SD 5.83 cm: Galton verisi (n = 481 erkek), sürüm 3, Ek_galton. **Ölçülmüş (V).**
  - Kızda 0.687 ve 5.13.
  - Türk erişkin ortalaması yerine kohort ortalaması kullanılır (Türk uyarlamalı).
  - **Varsayım:** Anne-baba kuşağı ile çocuk kuşağı arasındaki seküler artış ihmal edilir.

### 3.2 Ölçüm modeli

Her ölçüm i bir "okumadır":

```
r_i = H(a_i) − D·f_i + s_i
y_i = r_i + e_i
```

| Bileşen | Anlamı | Sınıf | Değer |
|---|---|---|---|
| a_i | Ölçüm yaşı | Kişinin verdiği pencere içinde düzgün dağılım | girdi |
| D | Sabah-akşam boy farkı | Ölçülmüş | 1.44 cm (spor araştırması sürüm 1, disk modeli kalibrasyon girdisi) |
| f_i | Günün hangi saati (0 = sabah kalkınca, 1 = gece) | Varsayım | sabah U(0, 0.3); akşam U(0.7, 1); bilinmiyor U(0, 1) |
| s_i | Ayakkabı | Varsayım | ana: 0 (çıplak ayak); duyarlılık: bilinmiyorsa U(0, 2.5) cm |
| e_i | Okuma hatası | Varsayım | girdi (öneri: okul/yuvarlanmış 1.0 cm; ev ölçümü 0.7 cm) |
| y_i | Bildirilen değer | girdi | tek değer ya da aralık (ör. "175-176"); aralık genişliği w ise ek varyans w²/12 |

**Eşitlik gözlemi** ("şimdi akşam ölçünce eski işaretle aynı geliyorum"): r_a − r_b ~ N(0, σ_eş²), σ_eş = 0.5 cm (varsayım). İşaretin kendi değeri bilinmez; yalnızca şimdiki okumaya eşitliği bilinir.

### 3.3 Sonsal (posterior)

- Önem örneklemesi. Her sanal kişi için belirsiz büyüklükler (a_i, f_i, s_i) **birer kez** çekilir.
- Ağırlık w = w_önsel × Π N(y_i; r_i, σ_i²) × Π N(r_a − r_b; 0, σ_eş²).
- Etkin örneklem büyüklüğü (ESS) raporlanır.

**Çıktılar:**
- Ölçüm yaşlarındaki gerçek (sabah) boy.
- Son 1 yılda uzama: H(şimdi) − H(şimdi − 1).
- Kalan büyüme: H(25) − H(şimdi).
- Erişkin boy H(25), sabah. Akşam boyu yaklaşık D kadar kısa.
- P(kalan ≥ 0.5 / 1 / 2 / 3 cm).
- En hızlı büyüme yaşı: 11-17.5 yaş arasında hızın en yüksek olduğu yaş.

Kalan büyüme ve erişkin boy için %50 (medyan), %10-90 ve %2.5-97.5 aralıkları verilir.

### 3.4 Doğrulama (Berkeley erkekleri)

- **Seçim:** 13.5 yaşından önce ve 21.0 yaşında ölçümü olan erkekler. Gerçek boy eğrisi, gözlenen yarım yıllık ölçümler arasında doğrusal aradeğerlenir.
- **Taklit edilen bilgi yapısı** (örnek kişiyle aynı; her Berkeley kişisi için tohumlu bir sentetik gürültü çekilişi):

  | Ölçüm | Yaş | Saat | Kayıt biçimi |
  |---|---|---|---|
  | 1 | U(14.10, 14.20) | bilinmiyor | tam sayıya yuvarlanmış değer |
  | 2 | U(14.90, 15.15) | bilinmiyor | tam sayıya yuvarlanmış değer |
  | işaret | U(16.20, 16.45) | bilinmiyor | değer yok |
  | şimdi | 17.20 | akşam | 1 cm genişliğinde aralık (ör. [175, 176]) |

  Eşitlik gözlemi: işaret okuması ile şimdiki okuma arasındaki fark, sentetik veride gerçekten hesaplanır ve gözlem olarak verilir.

- Berkeley'de anne-baba boyu yok. Doğrulama **anne-baba ağırlığı olmadan** yapılır; anne-baba kısmı Galton analizinde (sürüm 3) ayrıca doğrulanmıştı.
- **Sızıntı notu:** Kohortun parametreleri Berkeley'e fit edilmişti, test edilen kişiler de bunun içinde. Bu, kapsama oranını biraz iyimser gösterebilir. Rapora yazılır.

## 4. Ön kayıtlı testler

| # | Test | Geçme ölçütü |
|---|---|---|
| **T1** | Berkeley: kalan büyüme (17.2 → 21.0) için %80 aralığın kapsama oranı | 0.68-0.92 |
| **T2** | Berkeley: 21.0 yaş boyu için %80 aralığın kapsama oranı | 0.68-0.92 |
| **T3** | Berkeley: sonsal medyanın kalan büyüme hatası (MAE), yalnızca önselin medyanına göre daha küçük mü? (Kişisel ölçümler bilgi ekliyor mu?) | MAE_sonsal < MAE_önsel |
| **T4** | Etkin örneklem: örnek kişide ve Berkeley vakalarının medyanında | ESS ≥ 200 |
| **T5** | Monte Carlo kararlılığı: örnek kişide iki farklı tohumla kalan büyüme medyanı farkı | < 0.1 cm |

### Karar kuralları

- **K1:** T1 ya da T2 kalırsa kişisel aralıklar "kalibre değil" diye işaretlenir. Kapsama düşükse aralık "fazla dar", yüksekse "fazla geniş" diye yazılır.
- **K2:** T3 kalırsa "bu tür ev ve okul ölçümleri kalan büyüme tahminine bilgi eklemiyor" diye yazılır; kişisel tahmin önselden ayırt edilemez.
- **K3:** Kişisel sonuçta kalan büyümenin %80 aralığı 0'ı içeriyorsa, "büyümenin sürüp sürmediği bu verilerle ayırt edilemiyor" diye yazılır. Ayırt etmenin yolu ölçüm protokolüdür (bölüm 6).

## 5. Duyarlılık analizi (örnek kişide ve kişisel vakada)

| Varsayım | Ana | Varyantlar |
|---|---|---|
| Ayakkabı (saati/koşulu bilinmeyen ölçümler) | 0 | U(0, 2.5) cm |
| Sabah-akşam farkı D | 1.44 | 1.0, 2.0 |
| İşaretin çizildiği saat | bilinmiyor U(0, 1) | yalnızca sabah U(0, 0.3); yalnızca akşam U(0.7, 1) |
| Okuma hataları | girdi | 2 katı |
| Anne-baba bilgisi | var | yok |
| Yaş pencereleri | girdi | her iki yana 0.1 yıl genişletilmiş |

## 6. Önceden bilinen sınırlamalar

- Sonuç, sürüm 3 modelinin büyüme eğrisi ailesiyle sınırlı. O model yakalama büyümesini zayıf gösteriyor (sağlıklı büyümede önemsiz).
- Kemik yaşı en güçlü bilgi kaynağıdır ve burada yok. Varsa araca eklenebilir (sürüm 2 aracı kemik yaşını kullanıyordu).
- Tahliller sayısal olarak modele girmez.
- Berkeley 1930'lar ABD kohortu. Türk uyarlaması yalnızca ölçek ve zamanlama düzeyinde.

## 7. Plandan sapmalar

| Tarih | Ne değişti | Neden | Sonuçlar görüldükten sonra mı? |
|---|---|---|---|
| 2026-10-07 | **Sapma 1: Doğrulama bitiş noktası 21.0 yaş yerine her kişinin son ölçüm yaşı (18.0-21.0).** Seçim: 13.5'tan önce ölçümü ve 18.0 ya da sonrasında ölçümü olan erkekler. T1 ve T2 bu bitiş noktasıyla değerlendirilir; geçme ölçütleri (0.68-0.92) değişmedi. Izgara 21 yaşa kadar uzatıldı | İlk çalıştırmada doğrulamaya yalnızca **1** kişi girdi (T1 = 1.00, T2 = 0.00). Berkeley erkeklerinin çoğu 18-19 yaşına kadar izlenmiş, 21 yaşında ölçümü olan tek kişi var. Planda bu kontrol edilmemişti | **Evet.** T1-T4'ün tek kişilik sonucu görüldükten sonra |
| 2026-10-07 | **Sapma 2: Önsel örneklem N = 200 000 → 1 200 000** | T4 kaldı (ESS örnek kişide 154, Berkeley medyanında 44). Ölçümler birlikte dar bir olabilirlik oluşturduğu için 200 000 örnek yetmedi. Bu, sonucun değil Monte Carlo çözünürlüğünün değişikliği; T4 ölçütü (≥ 200) değişmedi | **Evet.** İlk çalıştırma görüldükten sonra. O çalıştırmada örnek kişinin ve kişisel vakanın sonuç dosyaları da üretildi; açılıp bakılmadı |
| 2026-10-07 | **Sapma 3: Kalibre edilmiş aralık eklendi.** Sonsal medyana, Berkeley doğrulamasındaki gerçek hata (artık = gerçek − sonsal medyan) yüzdelikleri eklenerek ikinci bir aralık raporlanır. Asıl sonsal aralıklar da raporda kalır | T1 kaldı (kapsama 0.30): sonsal aralıklar fazla dar (medyan genişlik 0.30 cm, gerçek hatanın SD'si 0.72 cm). Sistematik sapma yok (ortalama +0.17 cm). Neden: Sürüm 3'ün eğri ailesi gerçek bireylerden daha katı. K1 gereği aralıklar "kalibre değil" diye işaretlenir; bu düzeltme sonradan eklenen, açıkça etiketli bir ektir | **Evet** |

**Şeffaflık notu:** Plan yazılmadan önce yalnızca kohortun erişkin boy dağılımı görüldü (ortalama 177.8, SD 6.45 cm) ve önselin 17.2 → 25 yaş kalan büyüme medyanı (1.49 cm; anne-baba ağırlığı ve ölçümler olmadan). Bu, ağırlıklandırmanın mümkün olduğunu kontrol etmek içindi (s_k > 5.83 olmalı). Kişisel vakanın ve örnek kişinin hiçbir sonucu görülmedi.
