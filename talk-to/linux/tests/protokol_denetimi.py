"""Testlerde gidip gelen gerçek iletileri protokol tanımına göre denetler (protocol/messages.json).

    with protokol_denetimi.izle() as sorunlar: ...      # bilgisayarın gönderdikleri ve telefondan gelenler
"""

import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "protocol"))

import check  # noqa: E402
from talkto import hub  # noqa: E402


class Found(list):
    def __init__(self, on_problem=None):
        super().__init__()
        self.on_problem = on_problem

    def extend(self, items):
        for x in items:
            self.append(x)
            if self.on_problem:
                self.on_problem(x)


@contextlib.contextmanager
def izle(phone=True, on_problem=None):
    """Session.send (bilgisayar → telefon) ve Session._dispatch / _read_json (telefon → bilgisayar) izlenir.
    phone=False: telefon tarafı denetlenmez (sahte telefonun bilerek bozuk gönderdiği testler).
    on_problem: her sorunda çağrılır (ör. olay dosyasına yazmak için)."""
    found = Found(on_problem)
    send, dispatch, read = hub.Session.send, hub.Session._dispatch, hub.Session._read_json

    async def checked_send(self, msg):
        found.extend(check.problems(msg, "pc"))
        return await send(self, msg)

    async def checked_dispatch(self, msg):
        if phone:
            found.extend(check.problems(msg, "phone"))
        return await dispatch(self, msg)

    async def checked_read(self, timeout):
        msg = await read(self, timeout)
        if phone:
            found.extend(check.problems(msg, "phone"))
        return msg

    hub.Session.send, hub.Session._dispatch, hub.Session._read_json = checked_send, checked_dispatch, checked_read
    try:
        yield found
    finally:
        hub.Session.send, hub.Session._dispatch, hub.Session._read_json = send, dispatch, read
