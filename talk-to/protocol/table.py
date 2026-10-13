"""Writes the message table of PROTOCOL.md from messages.json.

    python3 protocol/table.py          # update PROTOCOL.md
    python3 protocol/table.py --check  # exit 1 if PROTOCOL.md is out of date (the tests run this)
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parent / "PROTOCOL.md"
START = "<!-- messages: generated from protocol/messages.json by protocol/table.py; do not edit by hand -->"
END = "<!-- /messages -->"
ARROW = {"phone": "phone → pc", "pc": "pc → phone", "both": "both"}


def table() -> str:
    spec = json.loads((HERE / "messages.json").read_text(encoding="utf-8"))
    rows = ["| Type | Direction | Fields | Meaning |", "|---|---|---|---|"]
    for name, m in spec["messages"].items():
        if m.get("section") != "messages":
            continue
        fields = ", ".join(f"`{k}` {v}".replace("|", "\\|") for k, v in m.get("fields", {}).items()) or "—"
        rows.append(f"| `{name}` | {ARROW[m['from']]} | {fields} | {m.get('doc', '')} |")
    return "\n".join(rows)


def render(text: str) -> str:
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{table()}\n{END}{tail}"


if __name__ == "__main__":
    old = DOC.read_text(encoding="utf-8")
    new = render(old)
    if "--check" in sys.argv:
        sys.exit(0 if new == old else "PROTOCOL.md is out of date: python3 protocol/table.py")
    DOC.write_text(new, encoding="utf-8")
