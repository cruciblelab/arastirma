> **Güncel sürüm:** [3-anatomik-iskelet](../3-anatomik-iskelet/). Bu sürüm dondurulmuştur.

# Omurga Büyümesi · Sürüm 2: Bilgilendirme Videosu

> **Sürüm:** 2 · **Tarih:** 2026-10-08 · **Durum:** güncel
>
> **Acelen varsa:** en alttaki [En basit özet](#en-basit-özet) bölümüne atla.
>
> Bu doküman ve video **tıbbi tavsiye değildir.** Eğrilik, sırt ağrısı, yavaşlayan büyüme ya da uyku sorunu varsa hekime git. Tedavi yalnızca **hekim kararıyla** yapılır.

**Kanıt seviyeleri:**

| Etiket | Anlamı |
|---|---|
| **A** | Meta-analiz ya da birden çok randomize kontrollü çalışma |
| **B** | Tek RCT ya da büyük, iyi tasarlanmış kohort |
| **C** | Gözlemsel çalışma, ölçüm çalışması, derleme |
| **V** | Bu depodaki gerçek veri analizi (Berkeley) |
| **D** | Model çıktısı, simülasyon ya da varsayım |

**Video:** [omurga_bilgilendirme.mp4](video/ciktilar/omurga_bilgilendirme.mp4) (2 dk 36 sn, 1280×720, sessiz) · Altyazı: [omurga_bilgilendirme.srt](video/ciktilar/omurga_bilgilendirme.srt)

---

## Soru ve kapsam

**Amaç:** Sürüm 1'in bulgularını, raporu okumayacak biri için kısa, madde madde ve görsel bir videoya çevirmek. Video, araştırmanın simülasyon sistemiyle üretilir:
- simülasyon sahnesi her karede modelden yeniden hesaplanır;
- videodaki sayılar elle yazılmaz, araştırmaların çıktı dosyalarından okunur.

**Kapsam dışı:** Yeni bir bulgu. Bu sürüm yeni analiz yapmaz; sürüm 1'i ve plak kapanma sırası araştırmasını anlatır.

## Önceki sürümden değişenler

| Konu | Sürüm 1 | Sürüm 2 |
|---|---|---|
| Görsel anlatım | 14 sn'lik GIF/MP4 animasyon (yalnızca simülasyon) | 2 dk 36 sn'lik bilgilendirme videosu: 10 sahne, sahne başına 3-6 kısa madde, altyazı dosyası |
| Sayıların kaynağı | Animasyon kendi hesabını yapıyordu | Videodaki her sayı çıktı dosyalarından okunuyor ve [`sayilar.csv`](video/ciktilar/sayilar.csv)'ye kaynağıyla yazılıyor |
| Bulgular | – | Değişmedi |

## Yöntem

- `cd video && python calistir.py` (~7 dk). Sistemde ffmpeg (libx264) gerekir.
- **Sahneler:**
  1. Kapak.
  2. 16 yaşından sonra boy nereden gelir? (Berkeley, V)
  3. Simülasyon: tipik erkek, yaş 13 → 22 (sürüm 3 modeli, D).
  4. Gece-gündüz disk değişimi.
  5. Eğrilik (Stokes 2008).
  6. Kaldıraçlar (mm).
  7. Ne işe yaramaz, ne gerçekten önemli.
  8. Evde ölçüm protokolü (simülasyon).
  9. Özet.
  10. Şeffaflık (tıbbi tavsiye değil, model tahmini, yapay zekâ ile hazırlandı, lisans).
- **Okuma süresi:** Her madde metin uzunluğuna göre 2.0-3.8 sn ekranda kalır, 0.4 sn'de belirir. Seslendirme yok: bu ortamda Türkçe ses sentezi aracı bulunmuyor. Her madde ayrıca `.srt` altyazı dosyasında var.
- **Sayıların kaynağı:** Ekrandaki 16 sayının listesi ve kaynak dosyaları [`sayilar.csv`](video/ciktilar/sayilar.csv)'de. Simülasyon sahnesindeki boy, oturma boyu ve bacak değerleri her kare için sürüm 3 modelinden hesaplanır.
- **Tasarım:** Depo paleti (bacak mavi, gövde yeşil, kayıp turuncu, geçici gri taralı). Şematik çizim sürüm 1'in `animasyon.py` modülünden alınır.

## Bulgular

**Testler** ([`testler.csv`](video/ciktilar/testler.csv)):

| Test | Ne sınıyor | Sonuç | |
|---|---|---|---|
| V1 | Biçim: H.264, 1280×720, yuv420p (her oynatıcıda açılır) | h264, 1280×720, yuv420p | ✅ |
| V2 | Süre 60-180 sn, boyut < 25 MB | 155.7 sn, 2.3 MB | ✅ |
| V3 | Simülasyon sahnesindeki sayılar = sürüm 3 modeli | fark 1.4·10⁻¹⁴ cm | ✅ |
| V4 | Örnek sayılar, kaynak dosyaların bağımsız yeniden okunmasıyla aynı | aynı | ✅ |

**Videoda anlatılanlar** (her sayının kaynağı `sayilar.csv`'de):
- 16 yaştan sonra uzamanın ~%90'ı gövdeden. Bacak erkeklerde medyan 16 yaşında, gövde en az 18 yaşında biter; bacak bittikten sonra gövde en az ~3.4 cm uzar.
- Akşam ~1.4 cm kısa ölçülürsün (geçici).
- 30° skolyoz ~11 mm, 45° ~21 mm ölçülen boy kaybı.
- Tipik erkek, 17 → 25 yaş: gövde ~16 mm, bacak ~1 mm.
- Ev ölçüm protokolü: ayda bir, 18 ay → %86; 3 ayda bir → %50; koşul sabitse ~%99; bacak ~%25.

**Kontrol:** Üretilen videonun her sahnesinin son karesi incelendi. Taşan ya da üst üste binen yazılar iki turda düzeltildi:
- satır kaydırma hesabı;
- kaldıraç grafiğinin yeri;
- "%92" yazımı;
- işaret açıklaması.

## Sonuçlar

1. **Sürüm 1'in bulguları 2.5 dakikalık, madde madde bir videoya çevrildi.** Videodaki her sayı bir çıktı dosyasından okunuyor ve kaynağıyla listeleniyor; elle yazılmış sayı yok. (V + D)
2. **Simülasyon sahnesi modelle birebir aynı:** fark 10⁻¹⁴ cm. Çizimler şematik; bu, videonun her karesinin altında yazıyor. (D)
3. **Videonun ana mesajı:** 16 yaştan sonra uzamanın çoğu omurgadan gelir. Omurgayı genetiğinin üstüne uzatan bilinen bir yöntem yoktur. Destek, eksik bırakmamaktır. Eğrilik ve günün saati ölçülen boyu büyümeden çok değiştirebilir. (V + C + D)

## Sınırlamalar

- **Video sessiz.** Bu ortamda Türkçe ses sentezi yok. Maddeler ekranda ve altyazıda var; sesli anlatım istenirse `.srt` metni seslendirme için hazır bir senaryodur.
- **Yeni analiz değil.** Sürüm 1'in bütün sınırlamaları (model aralıklarının darlığı, protokol hata varsayımları, Stokes formülünün kapsamı) aynen geçerli.
- **"Tipik erkek" tek bir eğridir.** Gerçek kişiler ondan sapar; kızlar için ayrı video yapılmadı.
- **Okuma süreleri** genel okuma hızına göre seçildi. Herkes için yeterli olmayabilir; video duraklatılabilir.

## Kaynaklar

- [Sürüm 1: kaldıraçlar, ölçüm protokolü ve animasyon](../1-kaldiraclar-protokol-ve-animasyon/README.md) (videodaki sayıların çoğu)
- [Büyüme plaklarının kapanma sırası, sürüm 1: Berkeley analizi](../../buyume-plaklari-kapanma-sirasi/1-literatur-ve-berkeley-analizi/README.md)
- [Stokes 2008, Stature and growth compensation for spinal curvature](https://pubmed.ncbi.nlm.nih.gov/18809998/)
- [Insights into the Pathophysiology of Scheuermann's Kyphosis, 2025 (PMC12839117)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12839117/)
- [Effects of Supervised Strength Training in Children and Adolescents: A Systematic Review, 2025 (PMC12101325)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12101325/)
- [Spor ve boy, sürüm 1](../../spor-egzersiz-ve-boy/1-fizik-tabanli-simulasyon/README.md) · [Beslenme, uyku ve boy, sürüm 1](../../beslenme-uyku-ve-boy/1-fizyoloji-simulasyonu/README.md)

## En basit özet

- **2.5 dakikalık bir video hazırlandı.** Omurganın 16 yaşından sonra nasıl uzadığını madde madde anlatıyor.
- **İçindeki sayılar elle yazılmadı;** araştırmaların kendi sonuç dosyalarından okunuyor. Her sayının nereden geldiği bir listede duruyor.
- **Ana mesaj:** Bacaklar önce durur, omurga birkaç yıl daha uzar. Bunu dışarıdan hızlandıran bilinen bir yöntem yok. Eksik bırakma, sabah ölç, eğrilik varsa hekime git.
- **Video sessiz,** ama yanında altyazı dosyası var.
