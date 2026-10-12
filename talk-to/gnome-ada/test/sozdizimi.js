// gjs ile sözdizimi denetimi: GNOME 45+ sürümü (ES modülü) ve 42–44 sürümü (eski betik) ayrıştırılabiliyor mu.
// Kullanım: gjs sozdizimi.js DOSYA modul|betik
const [path, kind] = ARGV;
const {GLib} = imports.gi;
const text = new TextDecoder().decode(GLib.file_get_contents(path)[1]);
try {
    if (kind === 'betik')
        new Function(text);
    else
        new Function(text.replace(/^import .*$/mg, '').replace(/^export default /m, ''));
    print(`tamam ${path}`);
} catch (e) {
    printerr(`HATA ${path}: ${e}`);
    imports.system.exit(1);
}
