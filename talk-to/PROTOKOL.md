# Talk To Linux ↔ Talk To Android protokolü (sürüm 1)

Linux tarafı (Talk To Android): [`linux/talkto/`](linux/talkto/) · Android tarafı (Talk To Linux): [`android/app/src/main/java/lab/crucible/talktolinux/net/`](android/app/src/main/java/lab/crucible/talktolinux/net/)

## Taşıma

| | |
|---|---|
| Sunucu | Linux uygulaması, TCP **47600**, TLS 1.2+ |
| İstemci | Telefon |
| Wi-Fi | Sunucu `0.0.0.0:47600` dinler (yalnızca "Kablosuz" açıkken) |
| USB | Bilgisayar `adb reverse tcp:47600 tcp:47600` kurar; telefon `127.0.0.1:47600`'e bağlanır, bağlantı bilgisayarda `127.0.0.1`'den gelir ve **USB** sayılır |
| Bluetooth | Bilgisayar BlueZ'e `a3c5e9d4-7b1f-4c6e-9d2a-5f8b3e1c7a90` UUID'li RFCOMM sunucu profili kaydeder (`RequireAuthentication`: cihazlar sistemde eşleşmiş olmalı). Telefon bu UUID ile bağlanır; TLS akış üzerinde SSLEngine ile kurulur. Bundan sonrası TCP ile aynı |
| Sertifika | Bilgisayarda bir kez üretilen kendinden imzalı EC P-256 sertifika. Telefon zinciri doğrulamaz; **SHA-256 parmak izini** ilk eşleşmede kaydeder, sonra değişirse bağlanmaz |

## Keşif (UDP 47601)

- Telefon `{"talkto":1,"type":"probe"}` paketini `255.255.255.255:47601`'e yollar.
- Bilgisayar (kablosuz açıkken) 3 saniyede bir ve her probe'a cevap olarak duyurur:
  `{"talkto":1,"type":"announce","app":"talk-to-android","id","name","port","fp","password":bool}`
- Duyurudaki `fp` yalnızca kolaylık içindir; güven TLS bağlantısında görülen parmak izine dayanır.

## Çerçeve

```
1 bayt tür | 4 bayt uzunluk (big-endian) | gövde
'J' 0x4A   | n                           | UTF-8 JSON nesnesi, "type" alanı zorunlu (en çok 4 MiB)
'B' 0x42   | 4 + n                       | 4 bayt aktarım no + n bayt dosya verisi (n ≤ 1 MiB, normalde 256 KiB)
```

İkili çerçeveler JSON iletileriyle aynı bağlantıda araya girer; büyük dosya giderken bildirimler beklemez.

## El sıkışma ve kimlik doğrulama

```
telefon → hello {proto:1, app:"talk-to-linux", device_id, name, model, platform, token|null}
bilgisayar → hello {proto:1, app:"talk-to-android", version, device_id, name, platform:"linux"}
```

1. `token` bilgisayarın kayıtlı belirteciyle (SHA-256'sı saklanır) eşleşirse → `welcome {}`.
2. Değilse yöntem seçilir:
   - **USB**, **Bluetooth** ya da **Wi-Fi + şifre yok** → `auth_required {method:"approval", nonce}`.
     İki taraf da `kod = SHA-256("nonce:parmakizi:device_id")` ilk 4 baytı mod 10⁶ (6 hane) hesaplar.
     Bilgisayar kodu onay penceresinde, telefon ekranında gösterir. Kullanıcı aynı olduğunu görüp onaylar.
     Telefon kodu **kendi gördüğü** sertifikadan hesapladığı için araya giren biri varsa kodlar farklı çıkar.
   - **Wi-Fi + şifre** → `auth_required {method:"password", nonce}`; telefon
     `auth_password {proof: HMAC-SHA256(şifre, "nonce:parmakizi")}` yollar. Parmak izi iletiye girdiği için
     kanıt başka bir sunucuya aktarılamaz.
3. Başarılıysa `welcome {token}` (32 bayt rastgele, hex). Telefon belirteci bilgisayarın parmak iziyle birlikte saklar.
   Onay penceresinde telefona bir **profil** seçilir; şifreyle eşleşen telefon varsayılan profili alır.
4. Başarısızsa `auth_failed {reason}`: `wrong_password`, `rejected` (reddedildi ya da 60 sn doldu), `too_many_attempts`
   (aynı IP'den 10 dakikada 5 hata), bağlantı kapanır.

Ortak test vektörleri: [`protokol-test-vektorleri.json`](protokol-test-vektorleri.json) (iki tarafın testleri de bu dosyayı okur).

## İletiler (kimlik doğrulandıktan sonra)

| Tür | Yön | Alanlar |
|---|---|---|
| `ping` / `pong` | iki yön | 15 sn'de bir; 50 sn hiçbir şey gelmezse bağlantı kopmuş sayılır |
| `battery` | telefon → bilgisayar | `level` (0-100), `charging` |
| `notification` | telefon → bilgisayar | `key`, `package`, `app`, `title`, `text`, `time_ms` |
| `notification_removed` | telefon → bilgisayar | `key` |
| `app_icon` | telefon → bilgisayar | `package`, `data` (base64 PNG); paket başına oturumda bir kez |
| `media_state` | iki yön | `active`, `player`, `title`, `artist`, `album`, `playing`, `position_ms`, `duration_ms`, `volume` (0-100 ya da null), `can_seek`, `art_id` |
| `media_art` | iki yön | `art_id`, `mime`, `data` (base64); yalnızca kapak değişince |
| `media_control` | iki yön (oynatıcının sahibine) | `action`: `play_pause` `play` `pause` `next` `previous` `seek` `volume`; `value` (ms ya da 0-100) |
| `clipboard` | iki yön | `text` |
| `open_url` | telefon → bilgisayar | `url` (yalnızca http/https) |
| `ring` / `ring_stop` | bilgisayar → telefon | telefonu bul |
| `profile` | bilgisayar → telefon | `id`, `name`, `permissions` {notifications, media, files, clipboard, open_url, commands, power, screenshot}; bağlanınca ve profil değişince |
| `commands` | bilgisayar → telefon | `items`: [{`id`, `name`, `icon`, `power`}] — profilin izin verdiği komutlar |
| `run_command` | telefon → bilgisayar | `id` (yalnızca listedeki bir kimlik; komut metni gönderilmez) |
| `command_result` | bilgisayar → telefon | `id`, `name`, `ok`, `code`, `output` (son 8000 karakter) |
| `sysinfo_request` / `sysinfo` | telefon ↔ bilgisayar | `host`, `os`, `cpu`, `cores`, `load`, `mem_used`, `mem_total`, `disk_used`, `disk_total`, `battery`, `uptime`, `volume`, `muted` |
| `pc_volume` | telefon → bilgisayar | `value` (0-100 ya da null), `toggle_mute`; cevap `sysinfo` |
| `screenshot_request` | telefon → bilgisayar | bilgisayar görüntüyü alıp `file_offer` ile yollar |
| `notify` | bilgisayar → telefon | `title`, `text` (ör. terminalde `talk-to-android bildirim`) |
| `file_offer` | gönderen → alan | `transfer_id`, `name`, `size`, `mime` |
| `file_accept` / `file_reject` | alan → gönderen | `transfer_id`, (`reason`) |
| *ikili parçalar* | gönderen → alan | `transfer_id` + veri |
| `file_done` | gönderen → alan | `transfer_id`, `sha256` |
| `file_result` | alan → gönderen | `transfer_id`, `ok`, (`reason`) |
| `file_cancel` | iki yön | `transfer_id` |

Bilinmeyen türler yok sayılır (ileri uyumluluk). Aktarım numaraları gönderene göre ayrı tutulur.
Bilgisayar her iletiyi telefonun **güncel** profil izniyle denetler; izin yoksa ileti yok sayılır ya da reddedilir
(dosya: `file_reject`, komut ve ekran görüntüsü: `command_result {ok:false}`).

Alan taraf dosyayı geçici bir yere yazar, boyut ve SHA-256 tutarsa asıl adına taşır; tutmazsa siler.
Linux'ta gelen ad tek bir dosya adına indirgenir (`../../.bashrc` → `_.._.bashrc`) ve var olan dosyanın
üzerine yazılmaz (`ad (1).uzantı`).
