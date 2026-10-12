"""Dil desteği: .po okuma, dil seçimi, çeviri dosyalarının koda uygunluğu ve arayüzün İngilizcesi.

Başkası yeni bir dil eklediğinde de bu testler çalışır: dosya okunabilmeli, {yer tutucular} tutmalı.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from guncelleyici import dil  # noqa: E402

spec = importlib.util.spec_from_file_location("ceviri", ROOT / "paket" / "ceviri.py")
ceviri = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ceviri)


class PoTest(unittest.TestCase):
    def tearDown(self):
        dil.setup(dil.SOURCE)

    def test_parse_multiline_escapes_fuzzy_plural(self):
        text = ('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Plural-Forms: nplurals=2; '
                'plural=(n != 1);\\n"\n\n#, fuzzy\nmsgid "Kur"\nmsgstr "Yanlış"\n\n'
                'msgid "İki\\n"\n"satır \\"tırnak\\""\nmsgstr ""\n"Two\\n"\n"lines \\"quote\\""\n\n'
                'msgid "{n} paket"\nmsgid_plural "{n} paket"\nmsgstr[0] "{n} package"\nmsgstr[1] "{n} packages"\n')
        entries = dil.parse_po(text)
        self.assertEqual(entries[2]["msgid"], 'İki\nsatır "tırnak"')
        self.assertEqual(entries[2]["msgstr"], ['Two\nlines "quote"'])
        self.assertTrue(entries[1]["fuzzy"])
        import gettext
        import io
        t = gettext.GNUTranslations(io.BytesIO(dil._mo(entries)))
        self.assertEqual(t.gettext("Kur"), "Kur")  # bulanık (fuzzy) çeviri kullanılmaz
        self.assertEqual(t.gettext('İki\nsatır "tırnak"'), 'Two\nlines "quote"')
        self.assertEqual(t.ngettext("{n} paket", "{n} paket", 1), "{n} package")
        self.assertEqual(t.ngettext("{n} paket", "{n} paket", 5), "{n} packages")

    def test_english(self):
        dil.setup("en")
        self.assertEqual(dil._t("Kur"), "Install")
        self.assertEqual(dil._tn("{n} paket kaldırılacak", 1).format(n=1), "1 package will be removed")
        self.assertEqual(dil._tn("{n} paket kaldırılacak", 4).format(n=4), "4 packages will be removed")
        self.assertEqual(dil._t("bilinmeyen yazı"), "bilinmeyen yazı")  # çevirisi yoksa kendisi
        from guncelleyici import hatalar
        self.assertEqual(hatalar.explain(["E: Could not get lock /var/lib/dpkg/lock"], 100).title,
                         "The package system stayed busy")
        dil.setup("tr")
        self.assertEqual(dil._t("Kur"), "Kur")

    def test_system_language(self):
        self.assertEqual(dil.system_language({"LANG": "tr_TR.UTF-8"}), "tr")
        self.assertEqual(dil.system_language({"LANG": "en_GB.UTF-8"}), "en")
        self.assertEqual(dil.system_language({"LANG": "de_DE.UTF-8"}), "en")  # çevirisi yok: İngilizce
        self.assertEqual(dil.system_language({"LANGUAGE": "fr:tr", "LANG": "fr_FR.UTF-8"}), "tr")
        self.assertEqual(dil.system_language({"LANG": "C.UTF-8"}), "en")
        self.assertEqual(dil.system_language({}), "en")

    def test_choice_is_saved_and_env_wins(self):
        old = dict(os.environ)
        try:
            os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
            os.environ.pop(dil.ENV, None)
            os.environ["LANG"] = "tr_TR.UTF-8"
            os.environ.pop("LANGUAGE", None)
            os.environ.pop("LC_ALL", None)
            os.environ.pop("LC_MESSAGES", None)
            self.assertEqual(dil.chosen(), dil.SYSTEM)
            self.assertEqual(dil.setup(), "tr")
            dil.choose("en")
            self.assertEqual(dil.chosen(), "en")
            self.assertEqual(dil.setup(), "en")
            os.environ[dil.ENV] = "tr"
            self.assertEqual(dil.setup(), "tr")
            dil.choose("xx")  # dosyası olmayan dil: sistemin diline düşer
            os.environ.pop(dil.ENV)
            self.assertEqual(dil.setup(), "tr")
        finally:
            os.environ.clear()
            os.environ.update(old)


class TranslationFilesTest(unittest.TestCase):
    """Koddaki yazılar ile .po dosyaları uyumlu mu (yeni dil eklenince de geçerli)."""

    def test_template_is_up_to_date(self):
        want = {(e["msgid"], bool(e.get("plural"))) for e in ceviri.extract()}
        have = {(e["msgid"], "msgid_plural" in e) for e in dil.parse_po(ceviri.POT.read_text()) if e["msgid"]}
        self.assertEqual(have, want, "şablon eski: python3 paket/ceviri.py guncelle")

    def test_every_language_file_is_usable(self):
        files = sorted(dil.DIR.glob("*.po"))
        self.assertIn("en", [p.stem for p in files])
        for p in files:
            with self.subTest(p.name):
                entries = dil.parse_po(p.read_text(encoding="utf-8"))
                h = dil.header(entries)
                self.assertIn("charset=UTF-8", h.get("Content-Type", ""))
                self.assertIn("nplurals", h.get("Plural-Forms", ""))
                self.assertTrue(h.get("X-Language-Name"), "menüde görünen ad")
                self.assertEqual(ceviri.problems(p), [])
                dil.load(p.stem).gettext("Kur")  # gettext okuyabiliyor

    def test_english_is_complete(self):
        _, tr = ceviri.read(dil.DIR / "en.po")
        missing = [e["msgid"] for e in ceviri.extract()
                   if not all(tr.get(e["msgid"], ([""], False))[0]) or tr[e["msgid"]][1]]
        self.assertEqual(missing, [], "en.po'da eksik çeviri: python3 paket/ceviri.py denetle")

    def test_no_untranslated_ui_text(self):
        """Arayüzde _t'den geçmeyen Türkçe yazı kalmasın (başlık, düğme, açıklama)."""
        import re
        src = (ROOT / "guncelleyici" / "ui.py").read_text(encoding="utf-8")
        bad = re.findall(r'(?:label|title|description|subtitle|tooltip_text|placeholder_text)=f?"[^"]*[A-Za-zçğıöşü]',
                         src)
        bad += re.findall(r'(?:toast|set_label|set_title|set_description)\(f?"[^"]*[A-Za-zçğıöşü]', src)
        self.assertEqual(bad, [])


def _display():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check()
    except (ImportError, ValueError):
        return False


@unittest.skipUnless(_display(), "ekran yok")
class WindowLanguageTest(unittest.TestCase):
    def tearDown(self):
        dil.setup(dil.SOURCE)

    def test_window_in_english_and_menu_switch(self):
        from yardimci import shared_app
        from gi.repository import GLib
        from guncelleyici.ui import Window
        app = shared_app()
        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
        try:
            dil.setup("en")
            w = Window(app)
            self.assertEqual(w.title.get_title(), "Package Updater")
            self.assertEqual(w.force_btn.get_label(), "Stop it and install…")
            w.destroy()
            dil.setup("tr")
            w = Window(app)
            w.present()
            # Menü → Dil → English: açık pencere İngilizce yeniden kurulur, seçim saklanır.
            app.activate_action("dil", GLib.Variant("s", "en"))
            wins = [x for x in app.get_windows() if isinstance(x, Window)]
            self.assertEqual([x.title.get_title() for x in wins], ["Package Updater"])
            self.assertEqual(dil.chosen(), "en")
            app.activate_action("dil", GLib.Variant("s", "tr"))
            wins = [x for x in app.get_windows() if isinstance(x, Window)]
            self.assertEqual([x.title.get_title() for x in wins], ["Paket Güncelleyici"])
            for x in wins:
                x.destroy()
        finally:
            if old is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = old


if __name__ == "__main__":
    unittest.main()
