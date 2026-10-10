#!/bin/sh
# Ubuntu/Debian/Mint/Pop!_OS için .deb paketi üretir:
#   sh paket/deb-olustur.sh        → paket/talk-to-android_<sürüm>_all.deb
# Kullanıcı bu dosyaya çift tıklayınca Uygulama Merkezi / Yazılım ile kurulur;
# GTK, libadwaita ve adb gibi bağımlılıkları paket yöneticisi kendisi getirir.
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
VER=$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import talkto; print(talkto.__version__)")
BUILD=$(mktemp -d)
ROOT=$BUILD/talk-to-android
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/lib/talk-to-android" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
    "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/metainfo" "$ROOT/usr/share/doc/talk-to-android"
cp -r "$HERE/talkto" "$ROOT/usr/lib/talk-to-android/"
find "$ROOT/usr/lib/talk-to-android" -name __pycache__ -prune -exec rm -rf {} +
cat > "$ROOT/usr/bin/talk-to-android" <<'SH'
#!/bin/sh
PYTHONPATH="/usr/lib/talk-to-android${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m talkto "$@"
SH
cp "$HERE/data/lab.crucible.TalkToAndroid.desktop" "$ROOT/usr/share/applications/"
cp "$HERE/data/icons/hicolor/scalable/apps/lab.crucible.TalkToAndroid.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cp "$HERE/data/lab.crucible.TalkToAndroid.metainfo.xml" "$ROOT/usr/share/metainfo/"
cp "$HERE/../README.md" "$ROOT/usr/share/doc/talk-to-android/"
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CTL
Package: talk-to-android
Version: $VER
Section: net
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.4), python3-cryptography | openssl
Recommends: adb, xdg-user-dirs
Installed-Size: $SIZE
Maintainer: Crucible ekibi <noreply@crucible.invalid>
Homepage: https://github.com/cruciblelab/arastirma
Description: Android telefonu USB, Wi-Fi ya da Bluetooth ile Linux'a bağlar
 Telefon bildirimlerini masaüstünde gösterir, iki yönde medya kontrolü,
 dosya ve pano aktarımı sağlar. Her yeni telefon için onay ya da şifre ister.
CTL
cat > "$ROOT/DEBIAN/prerm" <<'SH'
#!/bin/sh
set -e
# Uygulama root olarak çalıştırıldıysa oluşmuş olabilecek Python önbelleklerini sil.
find /usr/lib/talk-to-android -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
exit 0
SH
chmod 755 "$ROOT/usr/bin/talk-to-android" "$ROOT/DEBIAN/prerm"
find "$ROOT/usr" -type d -exec chmod 755 {} +
find "$ROOT/usr" -type f ! -path "*/usr/bin/*" -exec chmod 644 {} +
OUT="$HERE/paket/talk-to-android_${VER}_all.deb"
dpkg-deb --root-owner-group --build "$ROOT" "$OUT" >/dev/null
echo "$OUT"
