"""Telefonlarda çalanın izi: mini oynatıcı hangi telefonu göstersin, şarkı bildirimi ne zaman çıksın.

Arayüzden bağımsızdır (test edilebilir). Kararlar:
- "started": telefonda çalan bir şey yokken müzik başladı (sabitlenmiş mini oynatıcı bununla açılır;
  duraklatıp devam etmek pencereyi yeniden açmaz, kullanıcı kapattıysa kapalı kalır).
- "track": çalarken parça değişti ya da ilk kez göründü (masaüstünde kısa bildirim).
- "stopped": çalan bir şey kalmadı (şarkı bildirimi kaldırılır).
"""


def _key(st: dict):
    return st.get("title") or "", st.get("artist") or ""


class NowPlaying:
    def __init__(self):
        self.states: dict[str, dict] = {}
        self.current: str | None = None

    def update(self, device_id: str, state: dict) -> dict:
        old = self.states.get(device_id) or {}
        active, playing = bool(state.get("active")), bool(state.get("playing"))
        was_active = bool(old.get("active"))
        self.states[device_id] = dict(state) if active else {"active": False}
        events = {
            "started": active and playing and not was_active,
            "track": active and playing and bool(state.get("title")) and (
                not was_active or _key(state) != _key(old)),
            "stopped": was_active and not active,
        }
        if active and playing:
            self.current = device_id
        elif self.current == device_id and not active:
            self.current = None
        if self.current is None:
            self.current = self._pick()
        return events

    def _pick(self) -> str | None:
        active = [d for d, s in self.states.items() if s.get("active")]
        playing = [d for d in active if self.states[d].get("playing")]
        return (playing or active or [None])[0]

    def keep_only(self, device_ids):
        for d in list(self.states):
            if d not in device_ids:
                del self.states[d]
        if self.current not in self.states or not self.states[self.current].get("active"):
            self.current = self._pick()

    def shown(self) -> tuple[str | None, dict]:
        """Mini oynatıcıda gösterilecek telefon ve durumu."""
        if not self.current:
            return None, {"active": False}
        return self.current, self.states.get(self.current) or {"active": False}
