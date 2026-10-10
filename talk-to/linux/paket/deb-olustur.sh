#!/bin/sh
# Ubuntu/Debian/Mint/Pop!_OS için .deb paketi üretir:
#   sh paket/deb-olustur.sh [talk-to-linux.apk]   → paket/talk-to-android_<sürüm>_all.deb
#
# Ubuntu'nun Uygulama Merkezi yerel .deb kurarken eksik bağımlılıkları kendisi
# indirmez ("unmet dependencies"). Bu yüzden zorunlu bağımlılık yalnızca python3;
# GTK4/libadwaita "önerilen"dir ve yoksa uygulama ilk açılışta bilgisayarın şifre
# penceresiyle kendisi kurar (talkto/bootstrap.py). `sudo apt install ./paket.deb`
# ise önerilenleri de kurar.
#
# APK verilirse (ya da android/ altında derlenmişse) pakete eklenir: bilgisayardaki
# uygulama onu telefona USB üzerinden tek tıkla kurar (Play Protect engeline takılmaz).
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
VER=$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import talkto; print(talkto.__version__)")
BUILD=$(mktemp -d)
ROOT=$BUILD/talk-to-android
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/lib/talk-to-android" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
    "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/icons/hicolor/256x256/apps" \
    "$ROOT/usr/share/metainfo" "$ROOT/usr/share/doc/talk-to-android" "$ROOT/usr/share/talk-to-android"
cp -r "$HERE/talkto" "$ROOT/usr/lib/talk-to-android/"
find "$ROOT/usr/lib/talk-to-android" -name __pycache__ -prune -exec rm -rf {} +
cat > "$ROOT/usr/bin/talk-to-android" <<'SH'
#!/bin/sh
PYTHONPATH="/usr/lib/talk-to-android${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m talkto "$@"
SH
cp "$HERE/data/lab.crucible.TalkToAndroid.desktop" "$ROOT/usr/share/applications/"
cp "$HERE/data/icons/hicolor/scalable/apps/lab.crucible.TalkToAndroid.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cp "$HERE/data/icons/hicolor/256x256/apps/lab.crucible.TalkToAndroid.png" "$ROOT/usr/share/icons/hicolor/256x256/apps/"
APK=${1:-$HERE/../android/app/build/outputs/apk/release/app-release.apk}
if [ -f "$APK" ]; then
    cp "$APK" "$ROOT/usr/share/talk-to-android/talk-to-linux.apk"
    echo "APK pakete eklendi: $APK" >&2
else
    echo "Not: APK yok; paket telefona kurulum düğmesi olmadan üretiliyor." >&2
fi
cp "$HERE/data/lab.crucible.TalkToAndroid.metainfo.xml" "$ROOT/usr/share/metainfo/"
cp "$HERE/../README.md" "$ROOT/usr/share/doc/talk-to-android/"
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CTL
Package: talk-to-android
Version: $VER
Section: net
Priority: optional
Architecture: all
Depends: python3 (>= 3.10)
Recommends: python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.4), python3-cryptography | openssl, adb, xdg-user-dirs, zenity
Installed-Size: $SIZE
Maintainer: Crucible ekibi <noreply@crucible.invalid>
Homepage: https://github.com/cruciblelab/arastirma
Description: Android telefonu USB, Wi-Fi ya da Bluetooth ile Linux'a bağlar
 Telefondaki Talk To Linux uygulamasıyla eşleşir. Telefon bildirimlerini
 masaüstünde gösterir; iki yönde medya kontrolü, dosya ve pano aktarımı sağlar;
 telefondan bilgisayara kilitle, uyku, ekran görüntüsü ve kendi tanımladığın
 Linux komutlarını çalıştırır. Her yeni telefon için onay ya da şifre ister ve
 telefonları profillerle tanır. Telefon uygulamasını USB'den tek tıkla kurar.
 .
 İlk açılışta GTK4 ve libadwaita eksikse bilgisayarın şifre penceresiyle kurar.
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
