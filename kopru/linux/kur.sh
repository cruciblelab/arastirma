#!/bin/sh
# Köprü'yü yalnızca bu kullanıcı için kurar (sudo gerekmez):
#   sh kur.sh                      kur
#   sh kur.sh --otomatik-baslat    kur + oturum açılınca arka planda başlat
#   sh kur.sh --kaldir             kaldır (ayarlar ~/.config/kopru'da kalır)
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
DATA=${XDG_DATA_HOME:-$HOME/.local/share}
BIN=$HOME/.local/bin
APP=$DATA/kopru
AUTOSTART=${XDG_CONFIG_HOME:-$HOME/.config}/autostart/lab.crucible.Kopru.desktop

if [ "${1:-}" = "--kaldir" ]; then
    rm -rf "$APP" "$BIN/kopru" "$DATA/applications/lab.crucible.Kopru.desktop" \
        "$DATA/icons/hicolor/scalable/apps/lab.crucible.Kopru.svg" "$AUTOSTART"
    echo "Köprü kaldırıldı. Ayarlar ve eşleşmiş telefonlar: ~/.config/kopru (istersen sil)."
    exit 0
fi

eksik=""
python3 -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null || eksik="$eksik python3(>=3.10)"
python3 - <<'PY' 2>/dev/null || eksik="$eksik gtk4/libadwaita(>=1.4)"
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import Adw
assert (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 4)
PY
if [ -n "$eksik" ]; then
    echo "Eksik:$eksik"
    echo "  Ubuntu/Debian: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-cryptography adb"
    echo "  Fedora:        sudo dnf install python3-gobject gtk4 libadwaita python3-cryptography android-tools"
    echo "  Arch:          sudo pacman -S python-gobject gtk4 libadwaita python-cryptography android-tools"
    exit 1
fi
command -v adb >/dev/null 2>&1 || echo "Not: adb yok; USB bağlantısı için kur (Ubuntu: sudo apt install adb). Wi-Fi onsuz çalışır."
python3 -c 'import cryptography' 2>/dev/null || command -v openssl >/dev/null 2>&1 || {
    echo "Eksik: python3-cryptography ya da openssl (TLS sertifikası üretmek için)"; exit 1; }

rm -rf "$APP"
mkdir -p "$APP" "$BIN" "$DATA/applications" "$DATA/icons/hicolor/scalable/apps"
cp -r "$HERE/kopru" "$APP/"
find "$APP" -name __pycache__ -prune -exec rm -rf {} +
cat > "$BIN/kopru" <<SH
#!/bin/sh
PYTHONPATH="$APP\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m kopru "\$@"
SH
chmod +x "$BIN/kopru"
sed "s|^Exec=kopru|Exec=$BIN/kopru|" "$HERE/data/lab.crucible.Kopru.desktop" > "$DATA/applications/lab.crucible.Kopru.desktop"
cp "$HERE/data/icons/hicolor/scalable/apps/lab.crucible.Kopru.svg" "$DATA/icons/hicolor/scalable/apps/"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DATA/applications" || true

if [ "${1:-}" = "--otomatik-baslat" ]; then
    mkdir -p "$(dirname "$AUTOSTART")"
    sed "s|^Exec=kopru|Exec=$BIN/kopru --arka-planda|" "$HERE/data/lab.crucible.Kopru.desktop" > "$AUTOSTART"
    echo "Oturum açılınca arka planda başlayacak."
fi

echo "Kuruldu. Uygulama menüsünde “Köprü”, ya da terminalde: kopru"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    echo "Güvenlik duvarı açık. Wi-Fi bağlantısı için: sudo ufw allow 47600/tcp && sudo ufw allow 47601/udp"
fi
