#!/bin/bash
# Gerçek Android'de (emülatör) uçtan uca deneme: USB yolu (adb reverse), eşleşme, bildirim
# dinleyicisi, telefondan bilgisayara bildirim, güncelleme sonrası yeniden bağlanma.
#   bash talk-to/linux/tests/emulator_e2e.sh talk-to-linux.apk sonuc-klasoru
# Emülatör açık ve `adb` onu görüyor olmalı. Ekran görüntüleri ve günlükler sonuç klasörüne yazılır.
set -euo pipefail
APK=$(realpath "$1")
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
for n in root.iter("node"):
    if sys.argv[2] in (n.get("text"), n.get("content-desc")):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        print((x1 + x2) // 2, (y1 + y2) // 2)
        sys.exit(0)
sys.exit(1)
EOF
)
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
/usr/bin/python3 "$HERE/emulator_sunucu.py" "$EV" > "$OUT/sunucu.out" 2> "$OUT/sunucu.log" &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true; adb logcat -d > "$OUT/logcat.txt" 2>/dev/null || true' EXIT
for _ in $(seq 50); do grep -q hazir "$OUT/sunucu.out" 2>/dev/null && break; sleep 0.2; done
grep -q hazir "$OUT/sunucu.out" || fail "sunucu açılmadı: $(cat "$OUT/sunucu.log")"

log "uygulama kuruluyor"
adb install -r "$APK"
adb shell pm grant $PKG android.permission.POST_NOTIFICATIONS || true
adb shell cmd notification allow_listener $PKG/$PKG.service.NotificationListener
adb shell dumpsys deviceidle whitelist +$PKG > /dev/null || true
adb reverse tcp:47600 tcp:47600
adb logcat -c || true

log "1) ilk bağlantı (USB yolu, bilgisayarda onay)"
adb shell am start -W -n $PKG/.ui.MainActivity > /dev/null
sleep 4
shot 01-baglan
tap_text "USB kablosu" 30
wait_for "bilgisayar eşleşme istedi" 'of("ask")' 30
wait_for "bağlandı" 'of("connected")' 30
wait_for "telefon durumunu bildirdi" 'phone().get("flavor") == "tam"' 30
wait_for "bildirim erişimi açık" 'phone().get("notif_access") is True' 20
wait_for "bildirim dinleyicisi bağlı" 'phone().get("listener") is True' 30
sleep 2
shot 02-ana-sayfa

log "2) telefondaki bir bildirim bilgisayara geliyor mu"
# adb shell argümanları telefondaki kabukta yeniden bölünür: tırnaklar tek dizgenin içinde olmalı.
adb shell "cmd notification post -S bigtext -t 'Emulator testi' e2e1 'Merhaba bilgisayar'"
wait_for "bildirim bilgisayara ulaştı" 'any(n["title"] == "Emulator testi" for n in of("notification"))' 30

wait_for "uygulama adı paket adı değil" \
    'any(n["title"] == "Emulator testi" and n["app"] != n["package"] for n in of("notification"))' 5
wait_for "başlıksız medya oturumu müzik sayılmıyor" \
    'not any(m["state"].get("active") and not m["state"].get("title") for m in of("media"))' 3

log "3) uygulamadaki Deneme bildirimi düğmesi"
tap_text "Deneme bildirimi gönder"
wait_for "deneme bildirimi bilgisayara ulaştı" \
    'any(n["title"] == "Talk To Linux deneme bildirimi" for n in of("notification"))' 30

log "4) sekmeler"
for t in Medya Dosyalar Bilgisayar; do
    tap_text "$t"
    sleep 2
    shot "03-$t"
done
tap_text "Ana sayfa"

log "5) güncelleme (USB'den yeniden kurulum) sonrası"
adb install -r "$APK"
sleep 2
adb shell am start -W -n $PKG/.ui.MainActivity > /dev/null
wait_for "kendiliğinden yeniden bağlandı (onaysız)" 'len(of("connected")) >= 2 and len(of("ask")) == 1' 45
wait_for "güncellemeden sonra da dinleyici bağlı" \
    'phone().get("listener") is True and len([e for e in ev if e["event"] == "status"]) > 0' 40
adb shell "cmd notification post -S bigtext -t 'Guncelleme sonrasi' e2e2 'Hala geliyor mu'"
wait_for "güncellemeden sonra bildirim ulaştı" 'any(n["title"] == "Guncelleme sonrasi" for n in of("notification"))' 30
shot 04-guncelleme-sonrasi

log "EMÜLATÖR TESTİ GEÇTİ"
