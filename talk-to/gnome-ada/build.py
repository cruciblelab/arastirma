#!/usr/bin/env python3
"""Üst ada eklentisinin iki sürümünü üretir:

  build/45/  GNOME 45 ve sonrası (Ubuntu 24.04: GNOME 46): ES modülleri, kaynak olduğu gibi
  build/42/  GNOME 42–44 (Ubuntu 22.04: GNOME 42): imports.* ve init()

Kaynak tek (src/extension.js); 42 sürümü içe aktarma satırları ve sınıf bildirimi değiştirilerek üretilir.
    python3 build.py [hedef_klasör]
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UUID = "talkto-ada@crucible.lab"
META = {"uuid": UUID, "name": "Talk To · Üst ada",
        "description": "Telefonda çalan, gelen arama, bildirimler ve zamanlayıcı ekranın üst ortasında. "
                       "Talk To Android ile çalışır.",
        "url": "https://github.com/cruciblelab/arastirma", "version": 2}
LEGACY_IMPORTS = """const {GLib, Gio, St, Clutter} = imports.gi;
const Main = imports.ui.main;"""


def legacy(source: str) -> str:
    head, rest = source.split("// IMPORTS-BASLA\n", 1)
    _, body = rest.split("// IMPORTS-BITTI\n", 1)
    body = body.replace("export default class AdaExtension extends Extension {", "class AdaExtension {")
    assert "export " not in body and "import " not in body, "42 sürümünde ES modülü sözdizimi kaldı"
    return head + LEGACY_IMPORTS + "\n" + body + "\nfunction init() {\n    return new AdaExtension();\n}\n"


def build(out: Path):
    src = (HERE / "src" / "extension.js").read_text(encoding="utf-8")
    for name, versions, code in (("45", ["45", "46", "47", "48"], src), ("42", ["42", "43", "44"], legacy(src))):
        d = out / name
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        (d / "extension.js").write_text(code, encoding="utf-8")
        shutil.copy(HERE / "src" / "stylesheet.css", d / "stylesheet.css")
        (d / "metadata.json").write_text(json.dumps(dict(META, **{"shell-version": versions}), ensure_ascii=False,
                                                    indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "build"))
