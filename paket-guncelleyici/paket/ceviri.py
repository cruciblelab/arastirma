#!/usr/bin/env python3
"""Çeviri dosyaları için araç (gettext kurulu olmasa da çalışır).

  python3 paket/ceviri.py sablon           koddaki _t / _tn / N_ yazılarından guncelleyici/diller/sablon.pot üretir
  python3 paket/ceviri.py guncelle         her <kod>.po'yu şablona göre günceller (yeni yazılar boş eklenir,
                                           kalkanlar silinir, var olan çeviriler korunur)
  python3 paket/ceviri.py yeni de Deutsch  yeni dil dosyası açar (her yazının İngilizcesi not olarak yanında)
  python3 paket/ceviri.py denetle          eksik çevirileri ve {yer tutucu} hatalarını listeler

Kaynak dil Türkçe; Türkçe bilmeyen çevirmen için her kaydın üstünde "#. English:" notu bulunur.
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "guncelleyici"
DIR = SRC / "diller"
POT = DIR / "sablon.pot"
sys.path.insert(0, str(ROOT))
from guncelleyici.dil import header, parse_po  # noqa: E402

PLACEHOLDER = re.compile(r"\{(\w*)\}")
HEADER = {
    "Project-Id-Version": "paket-guncelleyici",
    "MIME-Version": "1.0",
    "Content-Type": "text/plain; charset=UTF-8",
    "Content-Transfer-Encoding": "8bit",
    "Language": "",
    "X-Language-Name": "",
    "Plural-Forms": "nplurals=2; plural=(n != 1);",
}


def extract() -> list[dict]:
    """Koddaki çevrilecek yazılar, ilk görüldükleri sırayla: [{"msgid", "plural"?, "refs"}]."""
    found: dict[str, dict] = {}
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("_t", "_tn", "N_") and node.args):
                continue
            arg = node.args[0]
            if isinstance(arg, (ast.JoinedStr, ast.BinOp)):  # f"..." ya da "..." + x: çeviri bulunamaz
                raise SystemExit(f"{path.name}:{node.lineno}: {node.func.id}() içine düz yazı verilmeli "
                                 "(değişkenler için {ad} ve .format)")
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                continue  # N_ ile işaretlenmiş bir yazının sonradan çevrilmesi
            e = found.setdefault(arg.value, {"msgid": arg.value, "refs": []})
            if node.func.id == "_tn":
                e["plural"] = True
            ref = f"guncelleyici/{path.name}:{node.lineno}"
            if ref not in e["refs"]:
                e["refs"].append(ref)
    return sorted(found.values(), key=lambda e: e["refs"][0].split(":")[0] + f":{int(e['refs'][0].split(':')[1]):06d}")


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


def _header_text(fields: dict) -> str:
    out = ['msgid ""', 'msgstr ""']
    out += [_q(f"{k}: {v}\n") for k, v in fields.items()]
    return "\n".join(out)


def write(path: Path, fields: dict, items: list[dict], translations=None, hints=None, top=""):
    """translations: {msgid: ([msgstr...], fuzzy)}; hints: {msgid: İngilizcesi}."""
    translations, hints = translations or {}, hints or {}
    nplurals = 2
    m = re.search(r"nplurals\s*=\s*(\d+)", fields.get("Plural-Forms", ""))
    if m:
        nplurals = int(m.group(1))
    blocks = [top + _header_text(fields)]
    for e in items:
        lines = []
        if e["msgid"] in hints and hints[e["msgid"]]:
            lines.append("#. English: " + hints[e["msgid"]].replace("\n", " "))
        lines.append("#: " + " ".join(e["refs"][:3]))
        strs, fuzzy = translations.get(e["msgid"], ([], False))
        if fuzzy:
            lines.append("#, fuzzy")
        if e.get("plural"):
            lines.append(f"msgid {_q(e['msgid'])}")
            lines.append(f"msgid_plural {_q(e['msgid'])}")
            for i in range(nplurals):
                lines.append(f"msgstr[{i}] {_q(strs[i] if i < len(strs) else '')}")
        else:
            lines.append(f"msgid {_q(e['msgid'])}")
            lines.append(f"msgstr {_q(strs[0] if strs else '')}")
        blocks.append("\n".join(lines))
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def read(path: Path):
    entries = parse_po(path.read_text(encoding="utf-8"))
    fields = header(entries)
    tr = {e["msgid"]: (e["msgstr"], e["fuzzy"]) for e in entries if e["msgid"]}
    return fields, tr


def english() -> dict:
    p = DIR / "en.po"
    if not p.exists():
        return {}
    _, tr = read(p)
    return {k: v[0][0] for k, v in tr.items() if v[0] and v[0][0] and not v[1]}


TOP = ("# Package Updater (Paket Güncelleyici) — {name} translation.\n"
       "# Source language is Turkish; the “English:” note above each entry gives the meaning.\n"
       "# To pick up new strings: python3 paket/ceviri.py guncelle — see guncelleyici/diller/README.md\n")


def cmd_sablon():
    items = extract()
    write(POT, HEADER, items, top="# Paket Güncelleyici çeviri şablonu (python3 paket/ceviri.py sablon ile üretilir).\n")
    print(f"{POT.relative_to(ROOT)}: {len(items)} yazı")


def cmd_guncelle():
    cmd_sablon()
    items = extract()
    hints = english()
    for p in sorted(DIR.glob("*.po")):
        fields, tr = read(p)
        gone = sorted(set(tr) - {e["msgid"] for e in items})
        write(p, {**HEADER, **fields}, items, tr, None if p.stem == "en" else hints,
              top=TOP.format(name=fields.get("X-Language-Name") or p.stem))
        missing = sum(1 for e in items if not any(tr.get(e["msgid"], ([], False))[0]))
        print(f"{p.name}: {missing} eksik, {len(gone)} kalktı")


def cmd_yeni(code: str, name: str):
    p = DIR / f"{code}.po"
    if p.exists():
        raise SystemExit(f"{p.name} zaten var")
    if not re.fullmatch(r"[a-z]{2,3}(_[A-Z]{2})?", code):
        raise SystemExit("dil kodu ör. de, fr, pt_BR")
    write(p, {**HEADER, "Language": code, "X-Language-Name": name}, extract(), None, english(),
          top=TOP.format(name=name))
    print(f"{p.relative_to(ROOT)} açıldı: msgstr \"\" satırlarını doldur (Poedit de olur), sonra "
          f"python3 paket/ceviri.py denetle")


def problems(path: Path) -> list[str]:
    """Yer tutucusu tutmayan çeviriler ({ad} çeviride de aynı olmalı)."""
    out = []
    _, tr = read(path)
    for msgid, (strs, fuzzy) in tr.items():
        want = sorted(set(PLACEHOLDER.findall(msgid)))
        for s in strs:
            if s and sorted(set(PLACEHOLDER.findall(s))) != want:
                out.append(f"{path.name}: “{msgid[:50]}”: yer tutucular {want} olmalı")
    return out


def cmd_denetle() -> int:
    items = extract()
    bad = 0
    for p in sorted(DIR.glob("*.po")):
        _, tr = read(p)
        missing = [e["msgid"] for e in items if not any(tr.get(e["msgid"], ([], False))[0])]
        probs = problems(p)
        print(f"{p.name}: {len(items) - len(missing)}/{len(items)} çevrilmiş")
        for m in missing[:10]:
            print(f"  eksik: {m[:70]}")
        for x in probs:
            print("  " + x)
        bad += len(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["sablon"]:
        cmd_sablon()
    elif a[:1] == ["guncelle"]:
        cmd_guncelle()
    elif a[:1] == ["yeni"] and len(a) == 3:
        cmd_yeni(a[1], a[2])
    elif a[:1] == ["denetle"]:
        sys.exit(cmd_denetle())
    else:
        print(__doc__)
        sys.exit(2)
