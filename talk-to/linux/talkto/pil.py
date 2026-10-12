"""Telefonun pili azalınca uyarı: %15, %10 ve %5'e inince birer kez (şarja takılınca baştan).

Telefon pil yüzdesi her değiştiğinde bildirir; burada yalnızca eşik geçişleri uyarıya dönüşür. Bağlanırken pil
zaten düşükse (ör. %12) bir kez uyarılır. Şarj kablosu takılınca sayaç sıfırlanır; çıkarılıp yeniden düşerse
yeniden uyarır.
"""

THRESHOLDS = (15, 10, 5)
LOW = THRESHOLDS[0]


def is_low(battery) -> bool:
    """Şu an düşük pil mi (şarjda değil ve %15 ya da altı)."""
    return bool(battery) and not battery.get("charging") and 0 <= battery.get("level", -1) <= LOW


class Takip:
    def __init__(self):
        self.warned: dict[str, int] = {}  # cihaz → en son uyarılan eşik

    def check(self, device_id: str, battery) -> int | None:
        """Yeni bir eşiğe inildiyse o eşik, yoksa None."""
        if not battery or battery.get("level", -1) < 0:
            return None
        level = battery["level"]
        if battery.get("charging"):
            self.warned.pop(device_id, None)
            return None
        hit = min((t for t in THRESHOLDS if level <= t), default=None)
        if hit is None:
            if device_id in self.warned and level > self.warned[device_id] + 3:
                self.warned.pop(device_id)  # şarj bilgisi gelmeden yükseldi
            return None
        if self.warned.get(device_id, 101) <= hit:
            return None
        self.warned[device_id] = hit
        return hit

    def keep_only(self, live):
        for d in [d for d in self.warned if d not in live]:
            self.warned.pop(d)
