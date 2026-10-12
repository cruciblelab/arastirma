#!/bin/bash
# Üst ada uçtan uca: sanal ekranda gerçek GNOME Shell (45+) + üst ada eklentisi + gerçek Talk To (sahte telefon
# olaylarıyla). Test eklentisi (cek@test) ekran görüntüsü alır ve sanal fareyle tıklar/sürükler.
# Gerekenler: gnome-shell, gjs, python3-gi, GTK4/libadwaita.   Kullanım: uctan_uca.sh ÇIKTI_KLASÖRÜ
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(realpath -m "$1"); mkdir -p "$OUT"
H=$(mktemp -d); mkdir -p "$H/run" "$H/.local/share/gnome-shell/extensions"; chmod 700 "$H/run"
python3 "$HERE/../build.py" "$H/build" > /dev/null
cp -r "$H/build/45" "$H/.local/share/gnome-shell/extensions/talkto-ada@crucible.lab"
cp -r "$HERE/cek@test" "$H/.local/share/gnome-shell/extensions/"
PY=${PY:-$(command -v python3)}  # gi bağlı Python (yerelde ör. PY=python3.12)
python3 - "$OUT/kapak.png" <<'PYEOF'
import struct, sys, zlib
w = h = 64
rows = b"".join(b"\0" + bytes(c for x in range(w) for c in (240 - y * 2, 120 + y, 60 + y * 2)) for y in range(h))
def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
open(sys.argv[1], "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                              + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
PYEOF
env HOME=$H XDG_RUNTIME_DIR=$H/run XDG_CONFIG_HOME=$H/.config XDG_DATA_HOME=$H/.local/share XDG_CACHE_HOME=$H/.cache \
    PY=$PY HERE=$HERE OUT=$OUT dbus-run-session -- bash -c '
export DBUS_SYSTEM_BUS_ADDRESS=$(dbus-daemon --session --fork --print-address=1 --nopidfile)
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.shell enabled-extensions "[\"cek@test\", \"talkto-ada@crucible.lab\"]"
gnome-shell --headless --wayland --no-x11 --virtual-monitor 1280x800 > "$OUT/shell.log" 2>&1 &
SH=$!
for i in $(seq 1 120); do gdbus introspect --session --dest test.Cek --object-path /test/Cek > /dev/null 2>&1 && break; sleep 0.5; done
sleep 1
WAYLAND_DISPLAY=wayland-0 GDK_BACKEND=wayland GSK_RENDERER=cairo timeout 200 "$PY" "$HERE/surucu.py" "$HERE/../../linux" "$OUT" "$OUT/kapak.png" \
    > "$OUT/talkto.log" 2>&1
kill $SH; wait $SH 2> /dev/null'
rm -rf "$H" 2> /dev/null || true
fail() { echo "HATA: $*"; grep -iE "JS ERROR|talkto-ada" "$OUT/shell.log" | head -20; exit 1; }
grep -q "JS ERROR" "$OUT/shell.log" && grep -B2 -A8 "JS ERROR" "$OUT/shell.log" | grep -q "talkto-ada" && fail "eklentide JS hatası"
grep -q "('media_control', 'p', 'play_pause', None)" "$OUT/eylemler.txt" 2> /dev/null || fail "adadaki oynat düğmesi Talk To'ya ulaşmadı"
grep -q "('call_action', 'p', 'k1', 1)" "$OUT/eylemler.txt" || fail "adadaki Yanıtla düğmesi ulaşmadı"
python3 - "$OUT" <<'PYEOF' || fail "Özelleştir ayarları, konum ya da bildirim temizleme Talk To'ya ulaşmadı"
import json, sys
d2, d3, d4 = (json.load(open(f"{sys.argv[1]}/{n}.json")) for n in ("durum2", "durum3", "durum4"))
assert d2["prefs"]["phone_vibrate"] and d2["prefs"]["ada_click_sound"], d2["prefs"]
assert 180 <= d3["offset"] <= 220, d3["offset"]
assert d4["notifications"] == [], d4["notifications"]
PYEOF
grep -q "('phone_timer', 'p', 60," "$OUT/eylemler.txt" || fail "zamanlayıcı (1 dk, telefonda da) kurulmadı"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['timer'] and d['timer']['phone'], d" "$OUT/durum.json" \
    || fail "zamanlayıcı durumu yanlış"
python3 - "$OUT/boyutlar.json" <<'PYEOF' || fail "küçülme/büyüme yanlış (yukarı kaydırma, üstüne gelme, tıklama)"
import json, sys
b = {k: v[3] for k, v in json.load(open(sys.argv[1])).items()}  # yükseklikler
print("ada yükseklikleri:", b)
assert b["buyuk"] > b["normal"] >= 20, "büyük/normal"
assert abs(b["kaydir1"] - b["normal"]) <= 2, "ilk yukarı kaydırma büyükten normale indirmeli"
assert b["ince"] < 14, "ikinci yukarı kaydırma ince şerit yapmalı"
assert abs(b["bakis"] - b["normal"]) <= 2, "ince şeridin üstüne gelince normal hâl görünmeli"
assert b["ayrilinca"] < 14, "fare ayrılınca ince şeride dönmeli"
assert b["tiklayinca"] > b["normal"] + 20, "ince şeritten görünen adaya tek tıklama büyütmeli"
assert b["ada-acik"] > 0 and b["ada-kapali"] > 0, "görüşmede hoparlör/sessiz simgeli düğme yok"
assert b["ada-uyari"] > 0, "cevaplanamayan aramada adada “telefondan cevapla” yazmıyor"
assert b["ozellestir"] > b["buyuk"], "Özelleştir'e basınca ada daha da büyümeli"
assert b["ada-tasan"] > 0, "Taşan dalgalar kipinde çalarken su görünmeli"
assert 5 < b["ada-tasan"] - b["ozellestir"] <= 30, \
    "su adanın yanlarından inip alt çizgisinde kalmalı (aşağı sarkmamalı): %s" % (b["ada-tasan"] - b["ozellestir"])
assert b["ozel_kapandi"] <= b["normal"] + 2, "Bitti'den sonra ada normal boyda olmalı"
assert b["ada-pil"] > 0, "telefonun pili %9'a inince ada pil uyarısını göstermeli"
assert abs(b["kilitsiz"] - b["normal"]) <= 6, "Konumu değiştir: ada normal boya iner"
x, y, w, h = json.load(open(sys.argv[1]))["konum"]
assert 820 <= x + w / 2 <= 860, f"sağa sürüklenen adanın ortası ~840 olmalı: {x + w / 2}"
PYEOF
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert (d['theme_id'], d['mode']) == ('gece', 'tasan'), d" \
    "$OUT/durum2.json" || fail "adadan seçilen tema/kip Talk To'ya yazılmadı"
[ "$(grep -c "('call_action', 'p', 'k1', 1)" "$OUT/eylemler.txt")" -ge 2 ] || fail "hoparlör düğmesi ulaşmadı"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['low_battery']['level'] == 9, d['low_battery']" \
    "$OUT/durum5.json" || fail "düşük pil adanın durumunda yok"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['low_battery'] is None, d['low_battery']" \
    "$OUT/durum6.json" || fail "şarja takılınca düşük pil uyarısı kalkmadı"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d['low_battery']['weak'] and d['event']['kind'] == 'pil', d" \
    "$OUT/durum7.json" || fail "takılı ama pil düşerken ada uyarmadı"
for f in 1-kucuk 2-sarki-degisti 3-bildirim 4-arama 4b-gorusme 5-zamanlayici 6-sayac 7-ince 8-bakis 9-normal \
         10-ozellestir 11-tasan 12-kilitsiz 12-kapandi 13-bildirimler 14-sistem-bildirimi 15-pil-az 16-sarj-yetmiyor; do [ -s "$OUT/$f.png" ] || fail "$f.png yok"; done
echo "ÜST ADA UÇTAN UCA TESTİ GEÇTİ"
