"""Checks messages against protocol/messages.json (standard library only).

Used by the tests of every implementation: the Linux unit tests, the live Android test and the emulator
test record real messages and fail on any problem. Field specs:

    str int num bool obj list null b64 hex:N int:A..B enum:a|b|c list:{...}
    a|b    either type        x?    may be absent
"""

import base64
import binascii
import json
import re
from pathlib import Path

SPEC = json.loads(Path(__file__).with_name("messages.json").read_text(encoding="utf-8"))
MESSAGES = SPEC["messages"]


def _one(spec: str, value) -> bool:
    if spec == "null":
        return value is None
    if spec == "str":
        return isinstance(value, str)
    if spec == "bool":
        return isinstance(value, bool)
    if spec == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if spec == "num":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec == "obj":
        return isinstance(value, dict)
    if spec == "list" or spec.startswith("list:"):
        return isinstance(value, list)
    if spec == "b64":
        if not isinstance(value, str):
            return False
        try:
            base64.b64decode(value, validate=True)
            return True
        except (binascii.Error, ValueError):
            return False
    if spec.startswith("hex:"):
        return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{int(spec[4:])}}}", value) is not None
    if spec.startswith("int:"):
        lo, hi = (int(x) for x in spec[4:].split(".."))
        return _one("int", value) and lo <= value <= hi
    raise ValueError(f"unknown field spec {spec!r}")


def matches(spec: str, value) -> bool:
    spec = spec.rstrip("?")
    if spec.startswith("enum:"):
        allowed = spec[5:].split("|")
        return (value is None and "null" in allowed) or (isinstance(value, str) and value in allowed)
    if spec.startswith("list:"):  # a list of objects; the item fields are documentation only
        return isinstance(value, list)
    return any(_one(s, value) for s in spec.split("|"))


def problems(msg: dict, sender: str) -> list[str]:
    """What is wrong with this message from "phone" or "pc" (empty: nothing)."""
    t = msg.get("type") if isinstance(msg, dict) else None
    if not isinstance(t, str):
        return ["no type"]
    m = MESSAGES.get(t)
    if m is None:
        return [f"{t}: not in protocol/messages.json"]
    out = []
    if m["from"] not in (sender, "both"):
        out.append(f"{t}: sent by {sender}, the protocol says {m['from']}")
    fields = m.get("fields", {})
    for name, spec in fields.items():
        if name not in msg:
            if not spec.endswith("?"):
                out.append(f"{t}.{name}: missing")
        elif not matches(spec, msg[name]):
            out.append(f"{t}.{name}: {msg[name]!r} is not {spec}")
    for name in msg:
        if name != "type" and name not in fields and not (t in ("probe", "announce") and name == "talkto"):
            out.append(f"{t}.{name}: not in protocol/messages.json")
    return out
