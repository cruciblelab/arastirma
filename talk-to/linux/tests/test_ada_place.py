"""Ada Place: tema tablosu, süslerin çizimi ve önizleme galerisi.

En önemli denetim: Talk To'daki önizleme (talkto/ui/ada_sahne.py) adanın kendi çizimiyle (gnome-ada/src/sahne.js,
gjs ile kabuksuz çalıştırılır) aynı resmi mi çiziyor. pycairo ya da gjs yoksa atlanır (CI'da TALKTO_TEST_STRICT=1
iken atlanmaz).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import ada_temalar  # noqa: E402
from talkto.ui import ada_sahne  # noqa: E402

GNOME_ADA = Path(__file__).resolve().parents[2] / "gnome-ada"
SAHNE_JS = GNOME_ADA / "src" / "sahne.js"
GJS = shutil.which("gjs")
HAVE_CAIRO = ada_sahne.cairo is not None
STRICT = bool(os.environ.get("TALKTO_TEST_STRICT"))
if STRICT and not (HAVE_CAIRO and GJS):
    raise RuntimeError("Ada Place çizim testleri çalıştırılamıyor: python3-gi-cairo ya da gjs yok")


class ThemeTableTest(unittest.TestCase):
    def test_table_is_valid(self):
        self.assertEqual(ada_temalar.problems(), [])
        self.assertIn(ada_temalar.DEFAULT, ada_temalar.THEMES)
        # Kullanıcının seçtiği eski temalar kaybolmadı
        for old in ("deniz", "gece", "gunbatimi", "orman"):
            self.assertIn(old, ada_temalar.THEMES)
        # tatlıdan havalıya: her grupta en az üç tema; kullanıcının istediği bulut ve sis var
        for g in ada_temalar.GROUPS:
            self.assertGreaterEqual(sum(t["group"] == g for t in ada_temalar.THEMES.values()), 3, g)
        used = {fx["type"] for t in ada_temalar.THEMES.values() for fx in t["fx"]}
        self.assertTrue({"clouds", "fog"} <= used)

    def test_every_fx_type_drawn_on_both_sides(self):
        js = SAHNE_JS.read_text(encoding="utf-8")
        py = (Path(ada_sahne.__file__)).read_text(encoding="utf-8")
        for kind in ada_temalar.FX_TYPES:
            self.assertIn(f"case '{kind}':", js, kind)
            self.assertIn(f'kind == "{kind}"', py, kind)
        self.assertEqual(len(re.findall(r"^    case '", js, re.M)), len(ada_temalar.FX_TYPES))

    def test_no_method_defined_twice(self):
        """JS'te aynı adlı ikinci yöntem ilkini sessizce ezer (Sky eklenirken _motion böyle bozulmuştu)."""
        src = (GNOME_ADA / "src" / "extension.js").read_text(encoding="utf-8")
        for cls in re.split(r"^class ", src, flags=re.M)[1:]:
            names = re.findall(r"^    (?:static )?(\w+)\(.*\) \{$", cls, re.M)
            dup = {n for n in names if names.count(n) > 1}
            self.assertEqual(dup, set(), cls.split("\n", 1)[0])

    def test_build_puts_scene_into_extension(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ada_build", GNOME_ADA / "build.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        src = build.source()
        self.assertEqual(src.count("function sahnePaint("), 1)
        self.assertNotIn(build.SAHNE_MARK, src)


def cases():
    """Her tema için birkaç an (şimşek ve parıltı gibi ara ara çıkanlar dahil) ve iki ölçek."""
    out = []
    for key, th in ada_temalar.THEMES.items():
        if not th["fx"]:
            continue
        for i, (t, w, h, sc, r) in enumerate(((8.0, 300, 29, 1.0, 14.5), (11.37, 340, 150, 1.0, 22.0),
                                              (45.03, 236, 39, 1.35, 19.5), (27.5, 34, 22, 0.5, 5.0))):
            out.append({"name": f"{key}-{i}", "w": w, "h": h, "t": t, "scale": sc, "radius": r,
                        "colors": th["colors"], "fx": th["fx"]})
    return out


def py_render(c):
    cairo = ada_sahne.cairo
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, c["w"], c["h"])
    cr = cairo.Context(surf)
    ada_sahne.background(cr, c["w"], c["h"], c["colors"], c["radius"])
    ada_sahne.paint(cr, c["w"], c["h"], c["t"], c["fx"], scale=c["scale"], radius=c["radius"])
    surf.flush()
    return surf


def diff(a, b):
    """(farklı piksel oranı, en büyük kanal farkı)"""
    da, db = bytes(a.get_data()), bytes(b.get_data())
    assert len(da) == len(db)
    big = 0
    changed = 0
    for i in range(0, len(da), 4):
        d = max(abs(da[i + k] - db[i + k]) for k in range(4))
        if d:
            changed += 1
            big = max(big, d)
    return changed / (len(da) // 4), big


@unittest.skipUnless(HAVE_CAIRO and GJS, "pycairo ya da gjs yok")
class SameDrawingTest(unittest.TestCase):
    """Önizleme = ada: aynı tema, aynı an → aynı resim."""

    def test_preview_matches_island(self):
        tmp = Path(tempfile.mkdtemp())
        cs = cases()
        (tmp / "cases.json").write_text(json.dumps(cs))
        r = subprocess.run([GJS, str(GNOME_ADA / "test" / "sahne_ciz.js"), str(SAHNE_JS), str(tmp / "cases.json"),
                            str(tmp)], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        cairo = ada_sahne.cairo
        worst = []
        for c in cs:
            js = cairo.ImageSurface.create_from_png(str(tmp / f"{c['name']}.png"))
            frac, big = diff(py_render(c), js)
            worst.append((frac, big, c["name"]))
            # Kenar yumuşatmada en fazla bir iki ton fark (iki dilin sin() son hanesi): resim aynı.
            self.assertLess(frac, 0.01, c["name"])
            self.assertLessEqual(big, 3, c["name"])
        print("en farklı:", max(worst))

    def test_effects_move_and_are_visible(self):
        """Süs gerçekten çiziliyor (zemin değişiyor) ve zamanla yer değiştiriyor (donuk değil)."""
        for key, th in ada_temalar.THEMES.items():
            if not th["fx"]:
                continue
            base = {"w": 300, "h": 40, "scale": 1.0, "radius": 18, "colors": th["colors"], "fx": []}
            plain = py_render(dict(base, t=8.0))
            frames = [py_render(dict(base, fx=th["fx"], t=t)) for t in (8.0, 9.5, 10.6, 13.0, 18.03)]
            self.assertGreater(max(diff(plain, f)[0] for f in frames), 0.01, f"{key}: süs görünmüyor")
            self.assertGreater(max(diff(frames[0], f)[0] for f in frames[1:]), 0.01, f"{key}: süs kıpırdamıyor")


@unittest.skipUnless(HAVE_CAIRO, "pycairo yok")
class CardTest(unittest.TestCase):
    def test_cards_draw_and_cost(self):
        """Her kart çizilir; bütün galerinin bir karesi ne kadar sürüyor (Ada sekmesi açıkken saniyede 20 kare)."""
        from talkto.ui import ada_place
        cairo = ada_sahne.cairo
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, ada_place.CARD_W, ada_place.CARD_H)
        t0 = time.perf_counter()
        frames = 5
        for i in range(frames):
            for th in ada_temalar.THEMES.values():
                ada_place.draw_card(cairo.Context(surf), ada_place.CARD_W, ada_place.CARD_H, th, 8 + i * 0.05)
        per_frame = (time.perf_counter() - t0) / frames
        print(f"galeri karesi: {per_frame * 1000:.1f} ms ({len(ada_temalar.THEMES)} kart)")
        self.assertLess(per_frame, 0.2)


try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib, Gtk
    HAVE_GTK = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check()
except (ImportError, ValueError):
    HAVE_GTK = False


@unittest.skipUnless(HAVE_GTK, "GTK4/libadwaita ya da ekran yok")
class GalleryTest(unittest.TestCase):
    def test_pick_and_select(self):
        from gi.repository import Adw
        from talkto.ui import ada_place
        Adw.init()
        picked = []
        place = ada_place.AdaPlace("gece", picked.append)
        self.assertEqual(set(place.cards), set(ada_temalar.THEMES))
        self.assertTrue(place.cards["gece"].check.get_visible())
        self.assertFalse(place.cards["kuzey"].check.get_visible())
        place.cards["kuzey"].emit("clicked")
        self.assertEqual(picked, ["kuzey"])
        place.select("kuzey")
        self.assertTrue(place.cards["kuzey"].has_css_class("secili"))
        self.assertFalse(place.cards["gece"].has_css_class("secili"))
        # Görünürken canlanır, gizlenince durur (sekme değişince boşuna çizmesin).
        win = Gtk.Window()
        sw = Gtk.ScrolledWindow(child=place)
        win.set_child(sw)
        win.present()
        ctx = GLib.MainContext.default()
        end = time.monotonic() + 2
        while time.monotonic() < end and not place._timer:
            ctx.iteration(False)
        if Gtk.Settings.get_default().get_property("gtk-enable-animations") and ada_place.HAVE_CAIRO:
            self.assertTrue(place._timer)
        win.set_visible(False)
        while ctx.pending():
            ctx.iteration(False)
        self.assertFalse(place._timer)
        win.destroy()

    def test_without_cairo_plain_cards(self):
        """python3-gi-cairo yoksa: canlı önizleme yok, renkli kartlar ve bir not; seçim yine çalışır."""
        from gi.repository import Adw
        from talkto.ui import ada_place
        Adw.init()
        old = ada_place.HAVE_CAIRO
        ada_place.HAVE_CAIRO = False
        try:
            picked = []
            place = ada_place.AdaPlace("deniz", picked.append)
            self.assertTrue(all(c.area is None for c in place.cards.values()))
            place.cards["sis"].emit("clicked")
            self.assertEqual(picked, ["sis"])
            self.assertIn(".ada-ornek-sis", ada_place._fallback_css(ada_temalar.THEMES))
        finally:
            ada_place.HAVE_CAIRO = old


if __name__ == "__main__":
    unittest.main()
