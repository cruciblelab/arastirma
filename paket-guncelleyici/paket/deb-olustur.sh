#!/bin/sh
# .deb paketi üretir:  sh paket/deb-olustur.sh  → paket/paket-guncelleyici_<sürüm>_all.deb
# DEB_IMZA_ANAHTARI (gizli anahtar dosyası) verilirse paket imzalanır (paket/deb-imzala.py).
set -eu
HERE=$(cd "$(dirname "$0")/.." && pwd)
VER=$(python3 -c "import sys; sys.path.insert(0, '$HERE'); import guncelleyici; print(guncelleyici.__version__)")
BUILD=$(mktemp -d)
ROOT=$BUILD/paket-guncelleyici
trap 'rm -rf "$BUILD"' EXIT

mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/lib/paket-guncelleyici" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
    "$ROOT/usr/share/icons/hicolor/scalable/apps" "$ROOT/usr/share/metainfo" \
    "$ROOT/usr/share/doc/paket-guncelleyici" "$ROOT/usr/share/keyrings"
cp -r "$HERE/guncelleyici" "$ROOT/usr/lib/paket-guncelleyici/"
find "$ROOT/usr/lib/paket-guncelleyici" -name __pycache__ -prune -exec rm -rf {} +
cat > "$ROOT/usr/bin/paket-guncelleyici" <<'SH'
#!/bin/sh
PYTHONPATH="/usr/lib/paket-guncelleyici${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m guncelleyici "$@"
SH
cp "$HERE/data/lab.crucible.PaketGuncelleyici.desktop" "$ROOT/usr/share/applications/"
cp "$HERE/data/icons/hicolor/scalable/apps/lab.crucible.PaketGuncelleyici.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cp "$HERE/data/lab.crucible.PaketGuncelleyici.metainfo.xml" "$ROOT/usr/share/metainfo/"
cp "$HERE/README.md" "$ROOT/usr/share/doc/paket-guncelleyici/"
cp "$HERE/paket/paket-guncelleyici-paket.gpg" "$ROOT/usr/share/keyrings/"
cp "$HERE/paket/paket-guncelleyici-paket.json" "$ROOT/usr/share/keyrings/"
SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<CTL
Package: paket-guncelleyici
Version: $VER
Section: admin
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gpgv, apt, dpkg, pkexec | policykit-1
Installed-Size: $SIZE
Maintainer: Crucible ekibi <noreply@crucible.invalid>
Homepage: https://github.com/cruciblelab/arastirma
Description: .deb dosyasını kurulu sürümle karşılaştırıp imzasını denetleyerek kurar
 Ubuntu'nun Uygulama Merkezi yerel .deb dosyasında sürümleri karşılaştırmıyor.
 Paket Güncelleyici dosyayı kurulu sürümle karşılaştırır, yayıncının imzasını
 kurulu sürümün anahtarıyla denetler, kurmadan önce başka hangi paketlerin
 kurulacağını ya da kaldırılacağını gösterir ve Ubuntu'nun otomatik
 güncellemesi sürerken sıraya girip bekler.
CTL
cat > "$ROOT/DEBIAN/prerm" <<'SH'
#!/bin/sh
set -e
find /usr/lib/paket-guncelleyici -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
exit 0
SH
chmod 755 "$ROOT/usr/bin/paket-guncelleyici" "$ROOT/DEBIAN/prerm"
find "$ROOT/usr" -type d -exec chmod 755 {} +
find "$ROOT/usr" -type f ! -path "*/usr/bin/*" -exec chmod 644 {} +
OUT="$HERE/paket/paket-guncelleyici_${VER}_all.deb"
dpkg-deb --root-owner-group --build "$ROOT" "$OUT" >/dev/null
if [ -n "${DEB_IMZA_ANAHTARI:-}" ] && [ -f "$DEB_IMZA_ANAHTARI" ]; then
    python3 "$HERE/paket/deb-imzala.py" imzala "$OUT" "$DEB_IMZA_ANAHTARI" >&2
fi
echo "$OUT"
