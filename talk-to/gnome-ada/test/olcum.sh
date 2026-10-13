#!/bin/bash
# Üst ada başarım ölçümü: sanal ekranda gerçek GNOME Shell + eklenti + gerçek Talk To; durumlar olcum.py'de.
# Kullanım: olcum.sh ÇIKTI_KLASÖRÜ   (yerelde: PY=python3.12)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(realpath -m "$1"); mkdir -p "$OUT"
H=$(mktemp -d); mkdir -p "$H/run" "$H/.local/share/gnome-shell/extensions"; chmod 700 "$H/run"
python3 "$HERE/../build.py" "$H/build" > /dev/null
cp -r "$H/build/45" "$H/.local/share/gnome-shell/extensions/talkto-ada@crucible.lab"
cp -r "$HERE/cek@test" "$H/.local/share/gnome-shell/extensions/"
PY=${PY:-$(command -v python3)}  # gi bağlı Python (yerelde ör. PY=python3.12)
env HOME=$H XDG_RUNTIME_DIR=$H/run XDG_CONFIG_HOME=$H/.config XDG_DATA_HOME=$H/.local/share XDG_CACHE_HOME=$H/.cache \
    PY=$PY HERE=$HERE OUT=$OUT dbus-run-session -- bash -c '
export DBUS_SYSTEM_BUS_ADDRESS=$(dbus-daemon --session --fork --print-address=1 --nopidfile)
gsettings set org.gnome.shell disable-user-extensions false
gsettings set org.gnome.shell enabled-extensions "[\"cek@test\", \"talkto-ada@crucible.lab\"]"
gnome-shell --headless --wayland --no-x11 --virtual-monitor 1280x800 > "$OUT/shell.log" 2>&1 &
SH=$!
for i in $(seq 1 120); do gdbus introspect --session --dest test.Cek --object-path /test/Cek > /dev/null 2>&1 && break; sleep 0.5; done
sleep 1
WAYLAND_DISPLAY=wayland-0 GDK_BACKEND=wayland GSK_RENDERER=cairo timeout 400 "$PY" "$HERE/olcum.py" "$HERE/../../linux" "$OUT" \
    > "$OUT/talkto.log" 2>&1
kill $SH; wait $SH 2> /dev/null'
rm -rf "$H" 2> /dev/null || true
cat "$OUT/olcum.json"
