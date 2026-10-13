#!/bin/bash
# Gerçek Android'de (emülatör) uçtan uca deneme: USB yolu (adb reverse), eşleşme, bildirim
# dinleyicisi, telefondan bilgisayara bildirim, güncelleme sonrası yeniden bağlanma.
#   bash talk-to/linux/tests/emulator_e2e.sh talk-to-linux.apk sonuc-klasoru [play.apk]
# play.apk verilirse önce o (Google Play'e uygun sürüm) kurulur; 5. adımdaki güncelleme onu tam sürüme
# yükseltir (bilgisayardaki "Tam sürüme yükselt" düğmesinin yaptığı): eşleşme korunmalı.
# Emülatör açık ve `adb` onu görüyor olmalı. Ekran görüntüleri ve günlükler sonuç klasörüne yazılır.
set -euo pipefail
APK=$(realpath "$1")
FIRST=$APK FIRST_FLAVOR=tam
if [ -n "${3:-}" ]; then FIRST=$(realpath "$3") FIRST_FLAVOR=play; fi
OUT=$(realpath -m "${2:-emulator-sonuc}")
HERE=$(cd "$(dirname "$0")" && pwd)
PKG=lab.crucible.talktolinux
EV="$OUT/olaylar.jsonl"
mkdir -p "$OUT"
: > "$EV"

log() { echo "== $*"; }
fail() {
    echo "HATA: $*" >&2
    adb exec-out screencap -p > "$OUT/hata.png" || true
    exit 1
}
shot() { adb exec-out screencap -p > "$OUT/$1.png"; }

# Olaylar üzerinde Python ifadesi (ev: olay listesi); doğru olana kadar bekler.
wait_for() {
    local what=$1 expr=$2 secs=${3:-30}
    for _ in $(seq "$secs"); do
        if python3 - "$EV" "$expr" <<'EOF'
import json, sys
ev = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
def of(name): return [e["data"] for e in ev if e["event"] == name]
def phone():
    st = of("status")
    s = st[-1]["sessions"] if st else []
    return (s[0].get("phone") or {}) if s else {}
sys.exit(0 if eval(sys.argv[2]) else 1)
EOF
        then log "tamam: $what"; return 0; fi
        sleep 1
    done
    fail "$what ($secs sn içinde olmadı)"
}

# Ekranda yazısı görünen öğeye dokunur (uiautomator dökümünden konumu bulur).
tap_text() {
    local text=$1 secs=${2:-20}
    for _ in $(seq "$secs"); do
        adb shell uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 || true
        adb pull /sdcard/ui.xml "$OUT/ui.xml" > /dev/null 2>&1 || true
        local xy
        xy=$(python3 - "$OUT/ui.xml" "$text" <<'EOF' || true
import re, sys, xml.etree.ElementTree as ET
try:
    root = ET.parse(sys.argv[1]).getroot()
except Exception:
    sys.exit(1)
nodes = list(root.iter("node"))
# Emülatörün kendi "… isn't responding" penceresi (ör. Pixel Launcher) her şeyin üstünü kapatabiliyor:
# önce onu "Wait" ile kapat (bizim uygulama değil; uygulamamızınki çıkarsa test yine düşer).
if any("isn't responding" in (n.get("text") or "") and "Talk To" not in (n.get("text") or "") for n in nodes):
    want, prefix = "Wait", "ANR "
else:
    want, prefix = sys.argv[2], ""
for n in nodes:
    if want in (n.get("text"), n.get("content-desc")):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        print(prefix + f"{(x1 + x2) // 2} {(y1 + y2) // 2}")
        sys.exit(0)
sys.exit(1)
EOF
)
        if [ "${xy#ANR }" != "$xy" ]; then
            # shellcheck disable=SC2086
            adb shell input tap ${xy#ANR }
            log "sistemin “yanıt vermiyor” penceresi kapatıldı (Wait)"
            sleep 1
            continue
        fi
        if [ -n "$xy" ]; then
            # shellcheck disable=SC2086
            adb shell input tap $xy
            log "dokunuldu: $text"
            return 0
        fi
        sleep 1
    done
    fail "ekranda “$text” bulunamadı"
}

log "sunucu başlıyor"
CMD="$OUT/komutlar.jsonl"
/usr/bin/python3 "$HERE/emulator_sunucu.py" "$EV" "$CMD" > "$OUT/sunucu.out" 2> "$OUT/sunucu.log" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true; adb logcat -d > "$OUT/logcat.txt" 2>/dev/null || true' EXIT
for _ in $(seq 50); do grep -q hazir "$OUT/sunucu.out" 2>/dev/null && break; sleep 0.2; done
grep -q hazir "$OUT/sunucu.out" || fail "sunucu açılmadı: $(cat "$OUT/sunucu.log")"

log "uygulama kuruluyor ($FIRST_FLAVOR)"
adb install -r "$FIRST"
# İzinler burada verilmez: 2. adımda telefondaki "Bilgisayar ayarlasın" düğmesiyle bilgisayar verir.
adb reverse tcp:47600 tcp:47600
adb logcat -c || true

log "0) ilk açılış: kurulum sihirbazı"
adb shell am start -W -n $PKG/.ui.MainActivity > /dev/null
sleep 3
shot 00-kurulum-1
tap_text "Başla"
for n in 2 3 4; do sleep 2; shot "00-kurulum-$n"; tap_text "İleri"; done
sleep 2
shot 00-kurulum-5

# Sihirbazın son adımında "Bitir"e basılmaz: bilgisayardaki "Bağlan" düğmesinin yaptığı gibi uygulama
# adb'nin açabildiği kapıdan açılır. Telefonda dokunmadan bağlanmalı ve sihirbaz kendiliğinden kapanmalı.
log "1) ilk bağlantı: bilgisayardaki “Bağlan” (telefonda dokunmadan, bilgisayarda onay)"
adb shell am start -n $PKG/.ui.UsbBaglan > "$OUT/kapi.txt" 2>&1
cat "$OUT/kapi.txt"
grep -qi "error\|exception" "$OUT/kapi.txt" && fail "bağlan kapısı açılmadı"
sleep 3
shot 01-baglan
adb shell uiautomator dump /sdcard/ui.xml > /dev/null 2>&1 || true
adb pull /sdcard/ui.xml "$OUT/ui.xml" > /dev/null 2>&1 || true
grep -q 'text="Bitir"' "$OUT/ui.xml" && fail "bilgisayar bağlarken telefondaki sihirbaz kapanmadı"
log "tamam: sihirbaz kendiliğinden kapandı"
wait_for "bilgisayar eşleşme istedi" 'of("ask")' 30
wait_for "bağlandı" 'of("connected")' 30
wait_for "telefon durumunu bildirdi ($FIRST_FLAVOR)" "phone().get('flavor') == '$FIRST_FLAVOR'" 30
wait_for "bildirim erişimi başta kapalı" 'phone().get("notif_access") is False' 10
sleep 2
shot 02-izin-eksik

log "1b) telefondaki “Bilgisayar ayarlasın”: bilgisayar adb ile izinleri verir"
tap_text "Bilgisayar ayarlasın"
wait_for "bilgisayar ayarlamaya başladı" 'of("phone_setup")' 20
wait_for "bildirim erişimi açık" 'phone().get("notif_access") is True' 40
wait_for "bildirim dinleyicisi bağlı" 'phone().get("listener") is True' 40
# Telefon dinleyiciyi bildirdiğinde bilgisayar hâlâ erişimi yeniden okuyor olabilir; pil adımı ondan sonra.
wait_for "bilgisayar ayarlamayı bitirdi" 'any(d.get("setting_up") for u in of("usb") for d in u.get("devices", [])) and not any(d.get("setting_up") for d in of("usb")[-1].get("devices", []))' 30
adb shell dumpsys deviceidle whitelist | grep -q $PKG || fail "pil kısıtlaması kaldırılmadı"
adb shell dumpsys package $PKG | grep -q "POST_NOTIFICATIONS: granted=true" || fail "bildirim izni verilmedi"
adb shell dumpsys package $PKG | grep -q "ANSWER_PHONE_CALLS: granted=true" || fail "aramayı cevaplama izni verilmedi"
log "tamam: pil kısıtlaması, bildirim ve aramayı cevaplama izni de verildi"
sleep 2
shot 02-ana-sayfa

log "2) telefondaki bir bildirim bilgisayara geliyor mu"
# adb shell argümanları telefondaki kabukta yeniden bölünür: tırnaklar tek dizgenin içinde olmalı.
adb shell "cmd notification post -S bigtext -t 'Emulator testi' e2e1 'Merhaba bilgisayar'"
wait_for "bildirim bilgisayara ulaştı" 'any(n["title"] == "Emulator testi" for n in of("notification"))' 30

wait_for "uygulama adı paket adı değil" \
    'any(n["title"] == "Emulator testi" and n["app"] != n["package"] for n in of("notification"))' 5
# Emülatörde gerçek bir oynatıcı yok: bu denetim yalnızca bir medya olayı geldiyse anlamlı (Google
# uygulamasının boş oturumu gibi). Olay yoksa "geçti" sayılmaz, yalnızca bilgi olarak yazılır.
n_media=$(python3 -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l)["event"]=="media"))' "$EV")
if [ "$n_media" -gt 0 ]; then
    wait_for "başlıksız medya oturumu müzik sayılmıyor" \
        'not any(m["state"].get("active") and not m["state"].get("title") for m in of("media"))' 3
else
    log "bilgi: medya olayı yok, başlıksız oturum denetimi yapılamadı"
fi

log "3) uygulamadaki Deneme bildirimi düğmesi"
tap_text "Deneme bildirimi"
wait_for "deneme bildirimi bilgisayara ulaştı" \
    'any(n["title"] == "Talk To deneme bildirimi" for n in of("notification"))' 30

log "4) sekmeler (basit mod: Dosyalar sekmesi yok)"
for t in Medya Bilgisayar; do
    tap_text "$t"
    sleep 2
    shot "03-$t"
done
tap_text "Ana sayfa"
log "4b) basit moda özellik ekleme: Dosya ve pano → Dosyalar sekmesi görünür"
tap_text "Diğer seçenekler"
tap_text "Görünüm ve özellikler"
tap_text "Dosya ve pano"
sleep 1
shot 03-ozellikler
adb shell input keyevent KEYCODE_BACK
tap_text "Dosyalar"
sleep 2
shot 03-Dosyalar
tap_text "Ana sayfa"
tap_text "Diğer seçenekler"
tap_text "İzinler ve yetkiler"
sleep 2
shot 03-izinler
adb shell input keyevent KEYCODE_BACK

log "5) güncelleme (USB'den yeniden kurulum; $FIRST_FLAVOR → tam) sonrası"
# Sayımlar güncellemeden hemen önceki değerlere göre: önceki adımlarda bir kopma olduysa yanıltmasın.
count() { python3 -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l)["event"]==sys.argv[2]))' "$EV" "$1"; }
C0=$(count connected)
A0=$(count ask)
adb install -r "$APK"
# Uygulama açılmaz: güncellenince telefonun verdiği haber (MY_PACKAGE_REPLACED) servisi başlatır, kendiliğinden
# bağlanır (telefon açılınca da aynı yol).
wait_for "kendiliğinden yeniden bağlandı (onaysız, uygulama açılmadan)" \
    "len(of('connected')) > $C0 and len(of('ask')) == $A0" 60
adb shell am start -W -n $PKG/.ui.MainActivity > /dev/null
wait_for "güncellemeden sonra da dinleyici bağlı (tam sürüm)" \
    'phone().get("listener") is True and phone().get("flavor") == "tam"' 40
adb shell "cmd notification post -S bigtext -t 'Guncelleme sonrasi' e2e2 'Hala geliyor mu'"
wait_for "güncellemeden sonra bildirim ulaştı" 'any(n["title"] == "Guncelleme sonrasi" for n in of("notification"))' 30
shot 04-guncelleme-sonrasi

log "6) arama: telefonun kendi araması bilgisayarda; düğmeler bilgisayardan"
# Bilgisayardaki düğme: son aramanın, adı verilen düğmelerden birine basılır (dil farkı için birkaç ad).
press() {
    python3 "$HERE/emulator_dugme.py" "$EV" "$1" >> "$CMD" || fail "aramada “$1” düğmesi yok"
}
calls_now() { adb emu gsm list | grep -ci "inbound" || true; }
last_call() {
    python3 -c 'import json,sys; ev=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]; c=[e["data"] for e in ev if e["event"]=="call"][-1]; print(c["app"], "|", c["caller"], "|", c["state"], "|", [a["title"] for a in c["actions"]])' "$EV"
}

adb shell input keyevent KEYCODE_HOME
adb emu gsm call 5551234
wait_for "gelen arama bilgisayara geldi (çalıyor)" 'any(c["state"] == "ringing" for c in of("call"))' 30
last_call
shot 05-arama-caliyor
press "decline|reddet"
wait_for "bilgisayardan reddedildi (arama bitti)" 'of("call_ended")' 20
sleep 2
[ "$(calls_now)" = "0" ] || fail "arama telefonda hâlâ sürüyor"

E0=$(count call_ended)
R0=$(python3 -c 'import json,sys; print(sum(1 for l in open(sys.argv[1]) if l.strip() and json.loads(l)["event"]=="call" and json.loads(l)["data"]["state"]=="ringing"))' "$EV")
adb emu gsm call 5551234
wait_for "ikinci arama geldi" "len([c for c in of('call') if c['state'] == 'ringing']) > $R0" 30
press "answer|cevapla"
wait_for "bilgisayardan cevaplandı (görüşme sürüyor)" 'of("call")[-1]["state"] == "ongoing"' 20
last_call
shot 05-arama-suruyor
# Görüşme sesi: telefon sonucu (önce/sonra) bildirir. Kısarak denenir (varsayılan ses en üstte olabilir).
python3 -c 'import json,sys; ev=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]; c=[e["data"] for e in ev if e["event"]=="call"][-1]; print(json.dumps({"method": "call_volume", "args": [c["device_id"], False]}))' "$EV" >> "$CMD"
wait_for "görüşme sesi bilgisayardan kısıldı" \
    'any(r["kind"] == "volume" and r["before"] is not None and r["after"] is not None and r["after"] < r["before"] for r in of("call_result"))' 15
python3 -c 'import json,sys; ev=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]; print([e["data"] for e in ev if e["event"]=="call_result"])' "$EV"
# Uygulamanın kendi ek düğmesi (telefon aramasında hoparlör) da bilgisayardan basılabilir.
press "speaker|hoparlör"
wait_for "hoparlör düğmesine basıldı (hata yok)" \
    'any(r["kind"] == "action" and "peaker" in (r["title"] or "") and not r["error"] for r in of("call_result"))' 15
press "hang up|kapat|end"
wait_for "bilgisayardan kapatıldı" "len(of('call_ended')) > $E0" 20

log "7) telefon yeniden başlamış gibi: uygulama kapalıyken açılış haberi gelir, kendiliğinden bağlanır"
C2=$(count connected)
adb shell input keyevent KEYCODE_HOME
adb shell am force-stop $PKG
sleep 3
# Açılış haberini (BOOT_COMPLETED) yalnızca sistem gönderebilir: emülatörde adb root ile.
adb root > /dev/null 2>&1 || true
adb wait-for-device
sleep 3
[ "$(adb shell id -u | tr -d '\r')" = "0" ] || fail "adb root olmadı (açılış haberi gönderilemez)"
adb shell am broadcast -a android.intent.action.BOOT_COMPLETED -f 0x20 -n $PKG/.service.BootReceiver
wait_for "açılıştan sonra uygulama açılmadan bağlandı" "len(of('connected')) > $C2" 90
shot 06-acilistan-sonra

log "8) karekodla eşleşme (onaysız)"
# Emülatörde kamera yok: karekodun içindeki bağlantı, telefonun kamerası okumuş gibi uygulamaya verilir
# (talkto://pair?…). El sıkışma, karekod anahtarının kanıtı ve eşleşme gerçek.
C3=$(count connected)
A3=$(count ask)
echo '{"method": "forget_all"}' >> "$CMD"
wait_for "bilgisayar telefonu unuttu, bağlantı kapandı" "len(of('disconnected')) > 0 and len(of('connected')) == $C3" 30
sleep 2
echo '{"method": "qr_start"}' >> "$CMD"
wait_for "karekod hazır" "len(of('qr')) > 0" 20
# Emülatör bilgisayara 10.0.2.2'den ulaşır (bilgisayarın kendi adresleri emülatörde başka ağ).
LINK=$(python3 -c '
import json, re, sys
ev = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
link = [e["data"]["link"] for e in ev if e["event"] == "qr"][-1]
print(re.sub(r"([?&])h=[^&]*", r"\1h=10.0.2.2", link))
' "$EV")
echo "karekod: $LINK"
adb shell "am start -W -a android.intent.action.VIEW -d '$LINK' $PKG" > /dev/null
sleep 2
shot 07-karekod-soru
tap_text "Eşleş"
wait_for "karekodla eşleşti: bilgisayarda onay sorulmadı" \
    "len(of('paired_by_qr')) == 1 and len(of('connected')) > $C3 and len(of('ask')) == $A3" 40
shot 08-karekodla-bagli

log "protokol: gerçek telefonun ve bilgisayarın bütün iletileri protocol/messages.json'a uymalı"
python3 -c '
import json, sys
bad = [json.loads(l)["data"]["problem"] for l in open(sys.argv[1], encoding="utf-8")
       if l.strip() and json.loads(l)["event"] == "protocol_problem"]
for p in sorted(set(bad)):
    print("  protokole uymuyor:", p)
sys.exit(1 if bad else 0)
' "$EV" || fail "protokole uymayan ileti var (yukarıda)"
log "EMÜLATÖR TESTİ GEÇTİ"
