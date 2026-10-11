# Talk To arayüz ilkeleri ve talepleri

Bu belge iki uygulamanın (telefonda **Talk To Linux**, bilgisayarda **Talk To Android**) arayüz
kararlarının neye dayandığını yazar. Kaynaklar 2026 Ekim'inde okundu. Her ilkenin yanında kanıtın
türü var: **D** deneysel çalışma, **K** platform ya da uzman kılavuzu, **Z** zayıf ya da tartışmalı.

## 1. Araştırmalardan çıkanlar

### Dikkat ve bellek
- **Çalışan bellek ~4 parça taşır, 7 değil.** Cowan 2010 (D). "7±2 menü öğesi" yaygın ama
  yanlış bir uygulamadır; tanınarak taranan listeler daha uzun olabilir.
  → Eşleşme kodu `482 913` gibi 3+3 gruplanır ve eşleşme bitene kadar ekranda kalır.
- **Hatırlamak yerine tanımak.** NN/g (K). Simgeler yazısız anlaşılmaz (NN/g simge araştırması).
  → Her simgenin görünür bir yazısı ya da etiketli bir menüsü olur.
- **Hick yasası:** seçenek arttıkça karar uzar (D, tanıdık seçenekler için). Bilinmeyen öğeleri taramak
  doğrusal artar; keyfi sayı sınırlarını haklı çıkarmaz.
- **Bilişsel yük ve dikkat bölünmesi.** Sweller (D, öğretim deneyleri). Açıklama, ilgili olduğu yerin
  hemen altında olmalı; süs ve tekrar eden metin yük bindirir.

### Düzen ve hiyerarşi
- **Yakınlık en güçlü gruplama ilkesidir.** Kubovy 1998, Wagemans 2012 (D). Aralıklardan biri
  diğerinin ~1,5 katını geçince gruplama neredeyse hep yakın olanlardan yapılır.
  → Gruplar arası boşluk, grup içi boşluğun en az 2 katı.
- **Göz katman katman tarar.** NN/g göz izleme (D). Her bölümün başlığı olur, satır anahtar
  kelimeyle başlar, alt yazı tek satırı geçmez.
- **Kademeli gösterim.** NN/g (K). Sık kullanılan önde, nadir olan tek bir "Gelişmiş" altında;
  ikiden derin katman kullanılmaz.
- **Görsel karmaşıklık beğeniyi düşürür.** Reinecke ve ark. 2013, 450 site (D). Yüksek karmaşıklık
  beğeniyi belirgin düşürüyor; düşük karmaşıklık orta kadar beğeniliyor; 45 yaş üstü sadeyi seviyor;
  renklilik küçük etki. → İlk ekranda en çok 5 görsel blok, tek vurgu rengi.
- **"Güzel olan kullanışlıdır" etkisi tartışmalı.** Kurosu ve Kashimura 1995, Tractinsky 2000 (D,
  ilişkisel); Tuch 2012 tersini buldu (Z). Lavie ve Tractinsky: "klasik" estetik (düzenli, açık)
  ile "dışavurumcu" estetik ayrı. → Klasik estetik hedeflenir; kararlar görev başarısıyla sınanır.

### Geri bildirim ve süre
- **0,1 s / 1 s / 10 s sınırları.** Nielsen, Miller 1968 (D/K). 0,1 s anlık, 1 s akış bozulmaz,
  10 s dikkat kopar.
- **Material 3:** 200 ms altı gösterge yok; 200 ms–5 s belirsiz gösterge; 5 s üstü yüzde (K).
  **GNOME:** ~3 s sonra gösterge; 30 s üstü metinli ilerleme çubuğu (K).
- **Hareket:** sık geçişler 100–300 ms, büyükler en çok 400 ms; durum göstergesinde sonsuz döngü
  yok; animasyonlar kapalıyken anlam kaybolmaz (NN/g, M3 hareket, K).

### Duygu ve güven
- **Norman'ın üç düzeyi** (görsel, davranışsal, yansıtıcı). Kaygı odağı daraltır; stresli ekranlarda
  (eşleşme, kurulum, hata) tek iş, tek birincil düğme, süs yok (K, kuram).
- **Sakin teknoloji.** Weiser ve Brown (Z, tasarım felsefesi; Android ve GNOME bildirim kılavuzlarıyla
  uyumlu). Bağlantı durumu çevrede (sessiz kalıcı bildirim, durum satırı) durur; kullanıcı yalnızca
  bir şey yapması gerekince rahatsız edilir.
- **Kod karşılaştırmalı eşleşme.** Uzun, Karvonen ve Asokan 2007 (D, 2×40 kişi): "Evet/Hayır"
  düğmeleriyle kullanıcıların **%20'si eşleşmeyen kodu onayladı**. "AYNI/FARKLI" etiketleri ve
  güvenli seçeneğin varsayılan olmasıyla **%0**. Kumar ve ark. 2009: sayı karşılaştırmada %10'dan
  fazla gereksiz red; tekrarlayan hatalar dikkatsizliğe iter. Tan ve ark. 2017: gruplanmış metin
  karşılaştırmayı kolaylaştırır.
- **Uyarı yorgunluğu.** Chrome saha verisi (Akhawe ve Felt 2013; Felt ve ark. 2015, D): güvenli seçenek
  öne çıkarılınca uyum %37'den %62'ye çıktı; aynı uyarı ikinci görülüşte dikkat sert düşüyor
  (Vance ve ark., D). → Kod karşılaştırması cihaz başına bir kez; gereksiz "Emin misin?" yok.
- **Renk.** Kontrast ve rengin tek ipucu olmaması güçlü kanıtlı (WCAG, D/K); "mavi güven verir" gibi
  renk psikolojisi iddiaları zayıf (Elliot 2015 derlemesi, Z). Kırmızı dikkat çeker; yalnızca gerçek
  risk için kullanılır.
- **Ses tonu.** NN/g ton çalışması: güvenilirlik beğeninin ~%52'sini açıklıyor; mizah riskli (D, küçük
  örneklem). Hatada suçlama, "geçersiz", ünlem yok.
- **Karanlık örüntüler.** deceptive.design: utandırarak onay alma, ısrar etme, önceden seçili kutu (K).

## 2. Talepler

Her talep test edilebilir. Kod: **T** ortak, **A** telefon, **L** bilgisayar.

### Ortak
| No | Talep | Dayanak |
|---|---|---|
| T1 | Bağlantı durumu her an görünür: simge + yazı + (gerekirse) tek düğme. Renk tek başına anlam taşımaz. | NN/g 1, WCAG 1.4.1 |
| T2 | Eşleşme kodu iki ekranda aynı biçimde: `482 913`, büyük, eşit genişlikli rakamlar. "Bu numarayı bir yere yazmana gerek yok." | Cowan, Uzun 2007, Tan 2017 |
| T3 | Eşleşme düğmeleri **"Numaralar aynı" / "Numaralar farklı"**; Evet/Hayır/Tamam yok. Varsayılan (Enter, Esc, pencereyi kapatma) güvenli olan **farklı**. | Uzun 2007, GNOME diyaloglar |
| T4 | Eşleşmeyen ya da reddedilen eşleşme sakin biter: "Eşleşme yapılmadı. Hiçbir şey paylaşılmadı." + "Tekrar dene". Kırmızı alarm ekranı yok. | Felt 2015, Norman |
| T5 | Kırmızı yalnızca geri alınamaz işlemde ve gerçek hatada. "Bağlı değil" nötr. | Chrome uyarıları, M3 renk rolleri |
| T6 | Her hata: ne oldu + bilinen neden + tek düğme. Suçlama, "geçersiz", ünlem yok. | NN/g hata kılavuzu |
| T7 | Boş durumlar ayrışır: bağlı değil / izin kapalı / yükleniyor / henüz yok. Her biri bir cümle ve bir düğme. | NN/g boş durum |
| T8 | 200 ms altı gösterge yok; uzun işlerde belirsiz gösterge; 5 s üstü ilerleme ve iptal. "Kontrol et" sonucu satırın altında yazıyla. | Nielsen, M3, GNOME |
| T9 | Gruplar arası boşluk ≥ 2× grup içi. Bölümde en çok ~5 satır. | Gestalt yakınlık |
| T10 | Ekranda tek birincil (dolu) düğme; ekranda en çok 3 yazı boyutu. | NN/g hiyerarşi |
| T11 | Teknik ayrıntı (IP, port, güvenlik kodu, terminal komutları) tek "Gelişmiş"/ayrı sayfa altında; varsayılan yolda IP sorulmaz. | Kademeli gösterim |
| T12 | Ortak sözlük (aşağıda). İki uygulama aynı şeye aynı adı verir. | Jakob, NN/g 4 |
| T13 | İzin, onu gerektiren adımda ve tek cümlelik faydayla istenir; "Şimdi değil" nötr; tekrar tekrar sorulmaz; izin yokken uygulama çalışır. USB ile bağlıyken **bilgisayar telefonu tek tıkla ayarlar**. | Android izin kılavuzu, deceptive.design |
| T14 | Tekrarlayan uyarı yok: güvenlik kodu cihaz başına bir kez karşılaştırılır; yalnızca geri alınamaz komut onay ister, onay düğmesi fiildir ("Kapat", "Tamam" değil). | Vance, NN/g onay diyaloğu |
| T15 | Sık geçişler 100–300 ms; durum göstergesi döngüsü yok (arama göstergesi hariç); animasyon kapalıyken her şey çalışır. | M3/NN/g hareket |
| T16 | **Basit mod** (yeni kurulumda açık): yalnızca bildirimler, çalan müzik ve telefonu bul. Diğer özellikler kaldırılmaz, gizlenir; neyin gizli olduğu ve nereden ekleneceği ekranda tek satırla yazar ("Özellik ekle"). Hafif sürümden farklı: o telefonda bildirim özelliğini hiç içermez. Ayar yalnızca görünümdür; izinleri profil belirler. | Kademeli gösterim, Hick yasası, Cowan |

### Telefon (Talk To Linux)
| No | Talep |
|---|---|
| A1 | Kenar boşluğu 16 dp, aralıklar 8 dp'nin katları (4 dp ince ayar). Kart köşesi tema şekli (12–16 dp), tek kart türü. |
| A2 | Alt gezinme 3–4 sekme (basit modda Dosyalar yok), yazılar hep görünür; seçili sekmeye yeniden dokununca başa kayar. Gizlenen sekmede kalınmaz. |
| A3 | Üst çubukta yazısız belirsiz simge yok: "İzinler", "Kurulum", "Bağlantıyı kes" etiketli menüde. |
| A4 | Ana sayfa: üstte tek durum kartı (her şey yolunda ya da tek sorun + tek düzeltme), altında en çok 4 hızlı işlem. Yarım kalan kurulum "Kurulumu bitir (n/N)" olarak görünür. |
| A5 | Bağlı değilken: nötr durum kartı + bulunan bilgisayarlar; "IP adresiyle bağlan" "Diğer yollar" altında. |
| A6 | İzinler ekranı: üstte "n/N hazır" özeti; eksik varsa ve USB ile bağlıysa birincil "Bilgisayar ayarlasın" kartı; tamamlananlar tek satırda toplanır, istenince açılır. |
| A7 | Güç komutları (uyku, kapat, yeniden başlat) nötr görünür, ayrı "Güç" grubunda, sık kullanılanlardan uzakta; onay diyaloğunda fiil + kırmızı. |
| A8 | Dokunma hedefi ≥ 48 dp; yazısız her denetimin `contentDescription`'ı var; süs simgeleri `null`. |
| A9 | Kenardan kenara (targetSdk 35) ve öngörülü geri hareketi (`enableOnBackInvokedCallback`). |
| A10 | Bağlantı hizmeti bildirimi düşük önemli ve sessiz, "Bağlantıyı kes" eylemli. |
| A11 | "Görünüm ve özellikler" (⋮ menüsü): basit mod anahtarı ve eklenebilir özellikler (dosya ve pano; bilgisayar komutları ve durumu). |

### Bilgisayar (Talk To Android)
| No | Talep |
|---|---|
| L1 | Üst düzey görünüm sayısı 3–5 (GNOME HIG). Bağlantı yolları ve genel ayarlar ayrı **Tercihler** penceresinde (Ctrl+,). |
| L2 | İlk sayfa "Telefonlar": bağlı telefonun durumu, USB'deki telefonun işlemleri (kur, **telefonu ayarla**, ekranını aç), güvenilen telefonlar ve profiller. |
| L3 | Boş/bağlı değil durumları `AdwStatusPage`: simge, başlık, bir cümle, tek düğme. |
| L4 | Tek seferlik olaylar toast; süren durumlar sayfanın üstünde şerit. |
| L5 | Başlık çubuğunda vurgulu ya da kırmızı düğme yok; her simge düğmesinin ipucu (tooltip) var. |
| L6 | Komutlar sayfası kısa: hazır komutlar, özel komutlar; terminal kullanımı ayrı açılan bölümde. |
| L7 | Klavye: Ctrl+Q çık, Ctrl+W pencereyi kapat, Ctrl+, tercihler, Esc diyalog kapatır. |
| L8 | İçerik `AdwClamp` içinde (en çok ~600–700 px), 22.04'teki libadwaita 1.1'de çalışan parçalarla. |
| L9 | Basit modda 3 görünüm (Telefonlar, Medya, Bildirimler); Tercihler'in ilk sayfası **Özellikler**. "Telefonu bul" yazılı düğme. |
| L10 | Telefonda çalan için **mini oynatıcı** (küçük ayrı pencere, sabitlenebilir: müzik başlayınca kendiliğinden açılır) ve şarkı değişince kısa masaüstü bildirimi (duraklat, sonraki; tıklayınca mini oynatıcı). Mini oynatıcı açıkken bildirim çıkmaz. Uygulama pencereyi diğerlerinin üstünde tutamaz (Wayland izin vermez); "Üstte tut" düğmesi pencere yöneticisinin menüsünü açar. |

## 3. Ortak sözlük
| Kavram | Kullanılacak söz | Kullanılmayacak |
|---|---|---|
| Uygulamanın kurduğu güven | **Eşleşme** / "eşleştir" | bağla (bağlantı başka şey), pair |
| Ekrandaki 6 hane | **Numara** (eşleşme numarası) | kod, PIN, şifre |
| Sertifika parmak izi | **Güvenlik kodu** | parmak izi, fingerprint, sertifika |
| Telefonun bilgisayardaki hakları | **Profil** ve **izin** | yetki seviyesi, rol |
| Telefonun Android ayarları | **Telefondaki izinler** | yetkiler, permission |
| Kablo | **USB** | adb (yalnızca gelişmiş metinde) |

## 4. Bilerek yapılmayanlar
- **QR ile eşleşme** (Tan 2017 "insanı döngüden çıkar" önerisi): kamera izni ve ek kütüphane ister;
  ayrı bir iş olarak bekliyor.
- **Arayüz renk "psikolojisi":** kanıtı zayıf; renk yalnızca tema rolleriyle ve anlamı yazıyla
  desteklenerek kullanılır.
- **Hoş geldin karuseli / ipucu balonları:** NN/g'ye göre görev başarısını artırmıyor.
- **İngilizce "Header Capitalization":** GNOME'un İngilizce kuralı; Türkçe arayüzde cümle düzeni
  (yalnızca ilk harf büyük) kullanılır.

## 5. Kaynaklar
- NN/g: [10 kural](https://www.nngroup.com/articles/ten-usability-heuristics/),
  [yanıt süreleri](https://www.nngroup.com/articles/response-times-3-important-limits/),
  [kademeli gösterim](https://www.nngroup.com/articles/progressive-disclosure/),
  [görsel hiyerarşi](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/),
  [tanıma ve hatırlama](https://www.nngroup.com/articles/recognition-and-recall/),
  [hata mesajları](https://www.nngroup.com/articles/error-message-guidelines/),
  [boş durumlar](https://www.nngroup.com/articles/empty-state-interface-design/),
  [mobil tanıtım](https://www.nngroup.com/articles/mobile-app-onboarding/),
  [sihirbazlar](https://www.nngroup.com/articles/wizards/),
  [ses tonu](https://www.nngroup.com/articles/tone-of-voice-dimensions/),
  [animasyon süresi](https://www.nngroup.com/articles/animation-duration/),
  [onay diyaloğu](https://www.nngroup.com/articles/confirmation-dialog/)
- Cowan 2010, çalışan bellek: https://pmc.ncbi.nlm.nih.gov/articles/PMC2864034/
- Wagemans ve ark. 2012, Gestalt: https://pmc.ncbi.nlm.nih.gov/articles/PMC3482144/
- Reinecke ve ark. 2013, karmaşıklık ve renklilik: https://kgajos.seas.harvard.edu/papers/reinecke13aesthetics.pdf
- Kurosu ve Kashimura 1995: https://chi1995.chistatic.hosting.acm.org/proceedings/shortppr/mk_bdy.htm
- Tractinsky ve ark. 2000: https://academic.oup.com/iwc/article/13/2/127/898608
- Norman, duygusal tasarım: https://jnd.org/emotion-design-attractive-things-work-better/
- Weiser ve Brown, sakin teknoloji: https://calmtech.com/papers/designing-calm-technology.html
- Uzun, Karvonen, Asokan 2007: https://sprout.ics.uci.edu/pubs/usability_analysis_method.pdf
- Kumar, Saxena, Uzun 2009: https://arxiv.org/pdf/0907.4743
- Tan ve ark. 2017: https://users.ece.cmu.edu/~lbauer/papers/2017/chi2017-fingerprints-author.pdf
- Akhawe ve Felt 2013: https://www.usenix.org/conference/usenixsecurity13/technical-sessions/presentation/akhawe
- Felt ve ark. 2015: https://static.googleusercontent.com/media/research.google.com/en//pubs/archive/43265.pdf
- Elliot 2015, renk ve psikoloji: https://pmc.ncbi.nlm.nih.gov/articles/PMC4383146/
- Material 3: https://m3.material.io/ (düzen, gezinme çubuğu, kartlar, listeler, yazı, renk, ilerleme),
  https://developer.android.com/develop/ui/compose/designsystems/material3
- Android: [erişilebilirlik](https://developer.android.com/guide/topics/ui/accessibility/apps),
  [temel kalite](https://developer.android.com/docs/quality-guidelines/core-app-quality),
  [izin isteme](https://developer.android.com/training/permissions/requesting),
  [bildirimler](https://developer.android.com/design/ui/mobile/guides/home-screen/notifications)
- GNOME HIG: https://developer.gnome.org/hig/ (kutulu listeler, başlık çubukları, görünüm değiştirici,
  toast/şerit/diyalog, yer tutucu sayfalar, yazım), libadwaita stil sınıfları
- WCAG 2.2: https://www.w3.org/TR/WCAG22/ (1.4.1, 1.4.3, 1.4.11, 2.5.8, 3.3.1–3.3.3)
- deceptive.design: https://www.deceptive.design/types
