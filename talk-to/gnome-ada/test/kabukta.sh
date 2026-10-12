#!/bin/bash
# Gerçek GNOME Shell (sanal ekran, Wayland + XWayland) + test eklentisi (cek@test); içinde verilen komut çalışır.
# ADA=1: üst ada eklentisi de yüklenir. Kullanım: kabukta.sh ÇIKTI KOMUT [argümanlar]
set -u
OUT=$(realpath -m "$1"); shift; mkdir -p "$OUT"
G=$(cd "$(dirname "$0")/.." && pwd)
H=$(mktemp -d); mkdir -p "$H/run" "$H/.local/share/gnome-shell/extensions"; chmod 700 "$H/run"
cp -r "$G/test/cek@test" "$H/.local/share/gnome-shell/extensions/"
if [ "${ADA:-0}" = 1 ]; then python3 "$G/build.py" "$H/b" >/dev/null; cp -r "$H/b/45" "$H/.local/share/gnome-shell/extensions/talkto-ada@crucible.lab"; EXT="'cek@test', 'talkto-ada@crucible.lab'"; else EXT="'cek@test'"; fi
env HOME=$H XDG_RUNTIME_DIR=$H/run XDG_CONFIG_HOME=$H/.config XDG_DATA_HOME=$H/.local/share XDG_CACHE_HOME=$H/.cache \
    OUT=$OUT EXT="$EXT" dbus-run-session -- bash -c '
export DBUS_SYSTEM_BUS_ADDRESS=$(dbus-daemon --session --fork --print-address=1 --nopidfile)
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.shell enabled-extensions "[$EXT]"
gnome-shell --headless --wayland --virtual-monitor 1280x800 > "$OUT/shell.log" 2>&1 &
SH=$!
for i in $(seq 1 120); do gdbus introspect --session --dest test.Cek --object-path /test/Cek > /dev/null 2>&1 && break; sleep 0.5; done
sleep 1
# Test makinesinde ekran kartı yok: GTK GPU çizicisi (EGL) yazılım çizimde ara sıra açılışta takılıyor
# (CI: pencere açılırken 2 dakika bekleyip öldürüldü). Linux işindeki ekran görüntüleri gibi cairo ile çizilir.
export GSK_RENDERER=cairo
export WAYLAND_DISPLAY=wayland-0 DISPLAY=:0; export XAUTHORITY=$(ls $XDG_RUNTIME_DIR/.mutter-Xwaylandauth.* 2>/dev/null | head -1); echo "xauth=$XAUTHORITY" > "$OUT/env.txt"
timeout 120 "$@" > "$OUT/surucu.log" 2>&1
kill $SH; wait $SH 2> /dev/null' _ "$@"
# Arka planda kalan süreçler (dconf, dbus) klasöre yazarken silme yarım kalabilir: sonucu sürücünün çıktısı belirler.
rm -rf "$H" 2> /dev/null || true
