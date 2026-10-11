"""Emülatör testi: son aramada adı verilen düğmeye basma komutu (bilgisayardaki bildirim düğmesi gibi).

    python3 emulator_dugme.py olaylar.jsonl "decline|reddet"  →  komut satırı (JSON)
"""

import json
import sys

ev = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
call = [e["data"] for e in ev if e["event"] == "call"][-1]
names = [n.lower() for n in sys.argv[2].split("|")]
action = next((a for a in call["actions"] if any(n in a["title"].lower() for n in names)), None)
if action is None:
    print(f"düğme yok: {[a['title'] for a in call['actions']]}", file=sys.stderr)
    sys.exit(1)
print(json.dumps({"method": "call_action", "args": [call["device_id"], call["key"], action["i"]]}))
