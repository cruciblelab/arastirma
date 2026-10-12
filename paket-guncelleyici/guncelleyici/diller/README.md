# Translations / Çeviriler

**English** — Package Updater's strings are written in Turkish in the code and translated through standard
gettext `.po` files in this folder. Every entry carries an `English:` note, so you don't need to know Turkish.
No compiling is needed: the app reads `.po` files directly.

Add a language (example: German):

1. `python3 paket/ceviri.py yeni de Deutsch` creates `guncelleyici/diller/de.po`.
   Arguments: the language code (`de`, `fr`, `pt_BR`…) and the language's own name.
2. Fill in the `msgstr ""` lines, with a text editor or [Poedit](https://poedit.net/).
   - Keep `{name}`-style placeholders exactly as they are (you may move them).
   - Entries with `msgstr[0]` / `msgstr[1]` depend on a number: set `Plural-Forms` in the header for your
     language (the [gettext manual](https://www.gnu.org/software/gettext/manual/html_node/Plural-forms.html)
     lists them).
   - `translator-credits`: your name(s), shown in About.
   - `,` is the decimal separator (`1,5 MB` in Turkish, `1.5 MB` in English).
3. `python3 paket/ceviri.py denetle` lists what's missing and any placeholder mistakes.
4. Try it: `PAKET_GUNCELLEYICI_DIL=de python3 -m guncelleyici` (or Menu → Language).
5. Send a pull request. The tests check placeholders and that the file can be read.

When the code changes, `python3 paket/ceviri.py guncelle` adds new strings (empty) to every `.po` and drops
removed ones; existing translations are kept.

Which language is used: the `PAKET_GUNCELLEYICI_DIL` environment variable, else the one picked in Menu →
Language, else the system language. If there's no translation for the system language, English is used.

---

**Türkçe** — Yazılar kodda Türkçe yazılır (`_t("...")`), başka diller bu klasördeki `.po` dosyalarından gelir.
Yeni dil: `python3 paket/ceviri.py yeni <kod> <dilin kendi adı>`, `msgstr` satırlarını doldur, `denetle` ile
bak. Kodda yeni yazı eklerken: `_t("…")`, değişken için `_t("{ad} kuruldu").format(ad=…)` (f-string değil;
çeviri bulunamaz), sayıya göre değişen için `_tn("{n} paket", n)`. Sonra `python3 paket/ceviri.py guncelle` ve
`en.po`'daki yeni boş kayıtları doldur (test eksik İngilizce çeviride kırmızı yanar).
