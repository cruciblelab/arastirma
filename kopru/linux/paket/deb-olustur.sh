#!/bin/sh
# Ubuntu/Debian/Mint/Pop!_OS için .deb paketi üretir:
#   sh paket/deb-olustur.sh        → paket/kopru_<sürüm>_all.deb
# Kullanıcı bu dosyaya çift tıklayınca Uygulama Merkezi / Yazılım ile kurulur;
# GTK, libadwaita ve adb gibi bağımlılıkları paket yöneticisi kendisi getirir.
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
VER=$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import kopru; print(kopru.__version__)")
BUILD=$(mktemp -d)
ROOT=$BUILD/kopru
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/lib/kopru" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
    "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/metainfo" "$ROOT/usr/share/doc/kopru"
cp -r "$HERE/kopru" "$ROOT/usr/lib/kopru/"
find "$ROOT/usr/lib/kopru" -name __pycache__ -prune -exec rm -rf {} +
cat > "$ROOT/usr/bin/kopru" <<'SH'
#!/bin/sh
PYTHONPATH="/usr/lib/kopru${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m kopru "$@"
SH
cp "$HERE/data/lab.crucible.Kopru.desktop" "$ROOT/usr/share/applications/"
cp "$HERE/data/icons/hicolor/scalable/apps/lab.crucible.Kopru.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cp "$HERE/data/lab.crucible.Kopru.metainfo.xml" "$ROOT/usr/share/metainfo/"
cp "$HERE/../README.md" "$ROOT/usr/share/doc/kopru/"
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CTL
Package: kopru
Version: $VER
Section: net
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.4), python3-cryptography | openssl
Recommends: adb, xdg-user-dirs
Installed-Size: $SIZE
Maintainer: Crucible ekibi <noreply@crucible.invalid>
Homepage: https://github.com/cruciblelab/arastirma
Description: Android telefonu USB ya da Wi-Fi ile Linux'a bağlar
 Telefon bildirimlerini masaüstünde gösterir, iki yönde medya kontrolü,
 dosya ve pano aktarımı sağlar. Her yeni telefon için onay ya da şifre ister.
CTL
cat > "$ROOT/DEBIAN/prerm" <<'SH'
#!/bin/sh
set -e
# Uygulama root olarak çalıştırıldıysa oluşmuş olabilecek Python önbelleklerini sil.
find /usr/lib/kopru -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
exit 0
SH
chmod 755 "$ROOT/usr/bin/kopru" "$ROOT/DEBIAN/prerm"
find "$ROOT/usr" -type d -exec chmod 755 {} +
find "$ROOT/usr" -type f ! -path "*/usr/bin/*" -exec chmod 644 {} +
OUT="$HERE/paket/kopru_${VER}_all.deb"
dpkg-deb --root-owner-group --build "$ROOT" "$OUT" >/dev/null
echo "$OUT"
