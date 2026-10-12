"""Dil desteği.

Arayüzdeki yazılar kodda Türkçe yazılır ve _t("...") içinden geçer; başka diller guncelleyici/diller/<kod>.po
dosyalarından gelir (standart gettext .po: Poedit gibi araçlarla düzenlenir, derlemeye gerek yok — dosya
çalışırken okunur). Yeni dil eklemek: diller/README.md.

Hangi dil: PAKET_GUNCELLEYICI_DIL ortam değişkeni → menüden seçilen (ayarlar.json) → sistemin dili (LANGUAGE,
LC_ALL, LC_MESSAGES, LANG). Sistemin dili için çeviri yoksa İngilizce: Türkçe bilmeyen biri için daha anlaşılır.
"""

import gettext
import io
import json
import os
import struct
from pathlib import Path

DIR = Path(__file__).with_name("diller")
SOURCE = "tr"  # kodda yazılan dil
FALLBACK = "en"
ENV = "PAKET_GUNCELLEYICI_DIL"
SYSTEM = "sistem"  # menüde "Sistem dili"

_trans: gettext.NullTranslations = gettext.NullTranslations()
current = SOURCE


def _t(text: str) -> str:
    """Çeviri (yoksa Türkçesi)."""
    return _trans.gettext(text)


def N_(text: str) -> str:
    """Yalnızca işaret: yazı burada çevrilmez (sonra _t ile çevrilir), ama çeviri listesine girer."""
    return text


def _tn(text: str, n: int) -> str:
    """Sayıya göre değişen çeviri (İngilizce "1 package" / "2 packages"). Türkçede tek biçim: text."""
    return _trans.ngettext(text, text, n)


# ---- .po okuma ------------------------------------------------------------------------------------

def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) < 2 or s[0] != '"' or s[-1] != '"':
        raise ValueError(f"tırnak bekleniyordu: {s}")
    out, i, body = [], 0, s[1:-1]
    esc = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "r": "\r"}
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            out.append(esc.get(body[i + 1], body[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_po(text: str) -> list[dict]:
    """[{"msgid", "msgid_plural", "msgstr": [..], "fuzzy", "comments"}]; ilk kayıt başlıktır (msgid "")."""
    entries, cur, key = [], None, None

    def finish():
        if cur is not None and "msgid" in cur:
            entries.append(cur)

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            finish()
            cur, key = None, None
            continue
        if cur is None:
            cur = {"msgstr": [], "fuzzy": False, "comments": []}
        if line.startswith("#,"):
            cur["fuzzy"] = cur["fuzzy"] or "fuzzy" in line
            continue
        if line.startswith("#~"):  # eski (artık kodda olmayan) kayıt
            continue
        if line.startswith("#"):
            cur["comments"].append(raw)
            continue
        if line.startswith('"'):
            if key is None:
                raise ValueError(f"beklenmeyen satır: {raw}")
            if isinstance(key, int):
                cur["msgstr"][key] += _unquote(line)
            else:
                cur[key] += _unquote(line)
            continue
        word, _, rest = line.partition(" ")
        if word in ("msgid", "msgid_plural", "msgctxt"):
            if word == "msgid" and "msgid" in cur:  # boş satırsız yeni kayıt
                finish()
                cur = {"msgstr": [], "fuzzy": False, "comments": []}
            cur[word] = _unquote(rest)
            key = word
        elif word == "msgstr":
            cur["msgstr"] = [_unquote(rest)]
            key = 0
        elif word.startswith("msgstr["):
            n = int(word[7:-1])
            while len(cur["msgstr"]) <= n:
                cur["msgstr"].append("")
            cur["msgstr"][n] = _unquote(rest)
            key = n
        else:
            raise ValueError(f"anlaşılmayan satır: {raw}")
    finish()
    return entries


def header(entries: list[dict]) -> dict[str, str]:
    for e in entries:
        if e["msgid"] == "" and e["msgstr"]:
            return {k.strip(): v.strip() for k, _, v in
                    (ln.partition(":") for ln in e["msgstr"][0].splitlines() if ":" in ln)}
    return {}


def _mo(entries: list[dict]) -> bytes:
    """Bellekte .mo (gettext'in okuduğu biçim): standart kütüphanenin çoğul kuralları da çalışsın."""
    table = {}
    for e in entries:
        if e["fuzzy"] and e["msgid"]:
            continue
        strs = e["msgstr"]
        if not any(strs):
            continue
        key = e["msgid"] if "msgid_plural" not in e else e["msgid"] + "\0" + e["msgid_plural"]
        if "msgctxt" in e:
            key = e["msgctxt"] + "\x04" + key
        table[key.encode()] = "\0".join(strs).encode()
    keys = sorted(table)
    ids = b"".join(k + b"\0" for k in keys)
    strs = b"".join(table[k] + b"\0" for k in keys)
    n = len(keys)
    start = 7 * 4 + n * 16
    koff, voff, pos = [], [], 0
    for k in keys:
        koff += [len(k), start + pos]
        pos += len(k) + 1
    pos = 0
    for k in keys:
        voff += [len(table[k]), start + len(ids) + pos]
        pos += len(table[k]) + 1
    head = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    return head + struct.pack(f"{2 * n}i", *koff) + struct.pack(f"{2 * n}i", *voff) + ids + strs


def load(code: str) -> gettext.NullTranslations:
    path = DIR / f"{code}.po"
    if code == SOURCE or not path.is_file():
        return gettext.NullTranslations()
    return gettext.GNUTranslations(io.BytesIO(_mo(parse_po(path.read_text(encoding="utf-8")))))


# ---- seçim ----------------------------------------------------------------------------------------

def available() -> list[tuple[str, str]]:
    """[(kod, kendi dilindeki adı)]: Türkçe ve diller/ klasöründeki her .po."""
    out = [(SOURCE, "Türkçe")]
    for p in sorted(DIR.glob("*.po")):
        try:
            name = header(parse_po(p.read_text(encoding="utf-8"))).get("X-Language-Name") or p.stem
        except (OSError, ValueError):
            continue
        out.append((p.stem, name))
    return out


def _settings_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "paket-guncelleyici" / "ayarlar.json"


def chosen() -> str:
    """Menüde seçilen dil kodu ya da SYSTEM."""
    try:
        v = json.loads(_settings_file().read_text()).get("dil")
    except (OSError, ValueError, AttributeError):
        return SYSTEM
    return v if isinstance(v, str) and v else SYSTEM


def choose(code: str):
    f = _settings_file()
    try:
        data = json.loads(f.read_text())
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    data["dil"] = code
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(f)


def system_language(env=None) -> str:
    """Sistemin dili için kullanılacak kod: çevirisi olan ilk dil, yoksa İngilizce."""
    env = os.environ if env is None else env
    have = {c for c, _ in available()}
    wanted = []
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        v = env.get(var)
        if v:
            wanted = v.split(":")
            break
    for w in wanted:
        code = w.split(".")[0].split("@")[0]
        for c in (code, code.split("_")[0]):
            if c in have:
                return c
    return FALLBACK if FALLBACK in have else SOURCE


def setup(code: str | None = None) -> str:
    """Dili seç ve yükle; seçilen kodu döndürür."""
    global _trans, current
    if code is None:
        code = os.environ.get(ENV) or chosen()
    if code == SYSTEM or code not in {c for c, _ in available()}:
        code = system_language()
    _trans, current = load(code), code
    return code
