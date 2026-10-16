# Yaş Farkı Tercihleri · Sürüm 2: Kadının Büyük Olduğu Çiftler ve Eğitim

> **Sürüm:** 2 · **Tarih:** 2026-10-16
>
> **Durum:** taslak
>
> Bu doküman tıbbi tavsiye değildir.

Taslak. Aşağıdaki analiz planı, analiz kodu yazılmadan ve yeni sonuçlara bakılmadan önce commit edildi. Veriler sürüm 1'dekilerle aynı; yeni değişkenlerden yalnız sütun adları ve dolu değer sayıları görüldü.

**Soru:** Eğitimli ya da gelişmiş ortamlarda yaş farkının yönü bir şey değiştiriyor mu? Özellikle:
- erkek 3-4 yaş büyük olduğunda;
- kadın 3-4 yaş büyük olduğunda.

Kadınlar kendilerinden 3-4 yaş küçük erkekleri özellikle tercih ediyor ya da reddediyor mu? Bu, kişinin yaşına göre değişiyor mu?

## Ön kayıtlı analiz planı

**Veri**
- **D1:** Walter ve ark. 2020, 45 ülke açık verisi. Yalnız partner yaşı 10'dan büyük kayıtlar kullanılır (sürüm 1'deki temizlenmiş veri). Ülke düzeyinde Küresel Cinsiyet Eşitliği Endeksi (`gggi`, 45 ülkede dolu) ve kişi başı gelir (`gdp_percap`) dosyada var.
- **D2:** Fisman ve Iyengar hızlı tanışma deneyi. Katılımcılar Columbia Üniversitesi öğrencileri (çoğu yüksek lisans), yani **yüksek eğitimli örneklem**. Kişi kimliği sürüm 1'deki gibi yeniden kurulur. `match` sütunu: iki taraf da "evet" dedi mi.
- **Yaş farkı:** partnerin yaşı − kendi yaşı (yıl). Kadın için "erkek 3-4 yaş küçük" = fark −4 ya da −3. Erkek için "kadın 3-4 yaş büyük" = fark +3 ya da +4. Referans: yaşıt, yani fark −1, 0 ya da +1.

**Analizler**

| Kod | Analiz |
|---|---|
| C1 | D2, kadınların kararı: kişi içi merkezlenmiş "evet" sapmasının ortalaması. 3-4 yaş küçük erkeklere karşı yaşıt erkekler; 3-4 yaş büyük erkeklere karşı yaşıt erkekler. Fark yüzde puan olarak verilir; %95 aralık için kişiler üzerinden 2000 bootstrap |
| C2 | D2, erkeklerin kararı: aynı hesap. 3-4 yaş büyük kadınlara karşı yaşıt kadınlar; 3-4 yaş küçük kadınlara karşı yaşıt kadınlar |
| C3 | C1 ve C2, karar verenin yaşına göre ikiye bölünerek: cinsiyet içinde kişi yaşı ortancasının altı ve ortanca ile üstü |
| C4 | D2, karşılıklı eşleşme (`match`) oranı. Kadının bakış açısından satırlarda: kadın 3-4 yaş büyük, yaşıt, erkek 3-4 yaş büyük. Yaşıta göre fark, kadınlar üzerinden bootstrap |
| C5 | D1, ülke düzeyi: kadınlar içinde partneri en az 3 yaş küçük olanların payı. Yalnız en az 10 kadın ve 10 erkek bildirimi olan ülkeler. Bu pay ile `gggi` ve `gdp_percap` arasında Spearman korelasyonu. Ek olarak ülkenin cinsiyet farkı (erkek ortalaması − kadın ortalaması) ile `gggi` arasında Spearman korelasyonu. Türkiye'nin değeri ve sırası |
| C6 | D1, kadınların yaş grubuna göre (18-24, 25-34, 35+) partneri en az 3 yaş küçük olanların payı. Bütün ülkeler ve Türkiye |

**Ön kayıtlı testler**

| Test | Ölçüt |
|---|---|
| T1 | İki veri dosyasının SHA-256 özeti, sürüm 1'deki değerlerle eşleşir |
| T2 | Sürüm 1 ile tutarlılık: kadınlarda yaşıt bölmesinin "evet" oranı 0.3738 (±0.0001) |
| T3 | C1 ve C2'deki her bölmede en az 150 buluşma |
| T4 | C1 ve C2 farklarının bootstrap standart hatası < 3 yüzde puan |
| T5 | C5'te en az 35 ülke |

**Karar kuralları**
- **K1:** Eğitimli örneklemde kadınlar, 3-4 yaş küçük erkeklere yaşıtlarından daha az mı "evet" diyor? C1 farkının %95 aralığı tümüyle 0'ın altındaysa "evet". Tümüyle üstündeyse "tersine, daha çok". Aralık 0'ı içeriyorsa "belirgin fark yok".
- **K2:** Erkekler, 3-4 yaş büyük kadınlara daha az mı "evet" diyor? Ölçüt K1 ile aynı.
- **K3:** Kadının 3-4 yaş büyük olduğu buluşmalarda eşleşme oranı, yaşıt buluşmalardan düşük mü? Ölçüt K1 ile aynı (C4).
- **K4:** Cinsiyet eşitliği yüksek ülkelerde kadının büyük olduğu çiftler daha mı yaygın? C5'teki `gggi` korelasyonu pozitif ve p < 0.05 ise "evet".
