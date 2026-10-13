// Temaların süslerini (src/sahne.js) kabuk olmadan çizer: her durum için bir PNG. Talk To'daki önizleme
// (linux/talkto/ui/ada_sahne.py) aynı resmi çizmeli; karşılaştırma linux/tests/test_ada_place.py'de.
// Kullanım: gjs sahne_ciz.js SAHNE_JS DURUMLAR_JSON ÇIKTI_KLASÖRÜ
//   DURUMLAR_JSON: [{name, w, h, t, scale, radius, colors: {bg1, bg2}, fx: [...]}]
const [sahnePath, casesPath, out] = ARGV;
const {GLib} = imports.gi;
const Cairo = imports.cairo;
const read = p => new TextDecoder().decode(GLib.file_get_contents(p)[1]);
// eslint-disable-next-line no-new-func
const api = new Function('Cairo', `${read(sahnePath)}\nreturn {sahnePaint, sahneBackground};`)(Cairo);
for (const c of JSON.parse(read(casesPath))) {
    const surf = new Cairo.ImageSurface(Cairo.Format.ARGB32, c.w, c.h);
    const cr = new Cairo.Context(surf);
    api.sahneBackground(cr, c.w, c.h, c.colors, c.radius);
    api.sahnePaint(cr, c.w, c.h, c.t, c.fx, {scale: c.scale, radius: c.radius});
    surf.writeToPNG(`${out}/${c.name}.png`);
    cr.$dispose();
}
print('tamam');
