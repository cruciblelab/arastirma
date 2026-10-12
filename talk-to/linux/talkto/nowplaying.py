"""Telefonlarda çalanın izi: mini oynatıcı hangi telefonu göstersin, şarkı bildirimi ne zaman çıksın.

Arayüzden bağımsızdır (test edilebilir). Kararlar:
- "started": telefonda çalan bir şey yokken müzik başladı (sabitlenmiş mini oynatıcı bununla açılır;
  duraklatıp devam etmek pencereyi yeniden açmaz, kullanıcı kapattıysa kapalı kalır).
- "track": çalarken parça değişti ya da ilk kez göründü (masaüstünde kısa bildirim).
- "stopped": çalan bir şey kalmadı (şarkı bildirimi kaldırılır).

Telefon şarkı değişirken (ya da kendiliğinden) bir an "çalmıyor" deyip hemen geri dönebiliyor. Bu kısa boşluk
(REJOIN sn) "durdu, yeniden başladı" sayılmaz: yoksa kullanıcının kapattığı mini oynatıcı yeniden açılıyor, aynı
şarkı için yeniden bildirim çıkıyor ve ada yeniden büyüyordu.
"""

import time

REJOIN = 3.0
SKIP_WAIT = 4.0  # "sonraki/önceki"ye basılınca yeni şarkı en çok bu kadar beklenir (o arada "yükleniyor")
END_GAP_MS = 3000  # şarkı bitmeye bu kadar kala duraklama: kendiliğinden sıradakine geçiş


def _key(st: dict):
    return st.get("title") or "", st.get("artist") or ""


class NowPlaying:
    def __init__(self):
        self.states: dict[str, dict] = {}
        self.current: str | None = None
        self.gone: dict[str, tuple[float, dict]] = {}  # az önce "çalmıyor" diyen telefon: (an, son durum)
        self.skips: dict[str, tuple[float, tuple]] = {}  # sonraki/önceki istendi: (an, o anki şarkı)
        self.paused_at: dict[str, float] = {}  # çalarken duraklama anı
        self.last_device: str | None = None  # en son çalan telefon (boşlukta "yükleniyor" kimin için)
        self.clock = time.monotonic

    def update(self, device_id: str, state: dict) -> dict:
        old = self.states.get(device_id) or {}
        active, playing = bool(state.get("active")), bool(state.get("playing"))
        if not active and old.get("active"):
            self.gone[device_id] = (self.clock(), old)
        elif active and not old.get("active") and device_id in self.gone:
            at, prev = self.gone.pop(device_id)
            if self.clock() - at < REJOIN:
                old = prev  # kısa boşluk: hiç durmamış gibi
        was_active = bool(old.get("active"))
        if old.get("playing") and not playing:
            self.paused_at[device_id] = self.clock()
        if active and device_id in self.skips and _key(state) != self.skips[device_id][1]:
            del self.skips[device_id]  # yeni şarkı geldi
        self.states[device_id] = dict(state) if active else {"active": False}
        events = {
            "started": active and playing and not was_active,
            "track": active and playing and bool(state.get("title")) and (
                not was_active or _key(state) != _key(old)),
            "stopped": was_active and not active,
        }
        if active and playing:
            self.current = device_id
            self.last_device = device_id
        elif self.current == device_id and not active:
            self.current = None
        if self.current is None:
            self.current = self._pick()
        return events

    def expect_change(self, device_id: str):
        """Kullanıcı sonraki/önceki istedi: yeni şarkı gelene kadar "yükleniyor"."""
        st = self.states.get(device_id) or {}
        self.skips[device_id] = (self.clock(), _key(st))

    def loading(self, device_id: str | None) -> bool:
        """Şarkılar arası geçişte mi: çalmıyor gibi görünmek yerine hafif bir "yükleniyor" gösterilir.
        - sonraki/önceki istendi, yeni şarkı henüz gelmedi (en çok SKIP_WAIT sn),
        - telefon bir an "çalmıyor" dedi (REJOIN sn içinde; geri dönerse durma sayılmaz),
        - şarkı bitmek üzereyken durakladı (kendiliğinden sıradakine geçiyor; en çok REJOIN sn)."""
        if not device_id:
            return False
        now = self.clock()
        skip = self.skips.get(device_id)
        if skip and now - skip[0] < SKIP_WAIT:
            return True
        gone = self.gone.get(device_id)
        st = self.states.get(device_id) or {}
        if gone and not st.get("active") and now - gone[0] < REJOIN:
            return True
        dur, pos = st.get("duration_ms") or 0, st.get("position_ms") or 0
        paused = self.paused_at.get(device_id)
        return bool(st.get("active") and not st.get("playing") and dur and dur - pos < END_GAP_MS
                    and paused and now - paused < REJOIN)

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
