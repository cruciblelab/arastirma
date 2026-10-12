"""Telefonun pili azalınca uyarı: %15, %10 ve %5'e inince birer kez (şarja takılınca baştan).

Telefon pil yüzdesi her değiştiğinde bildirir; burada yalnızca eşik geçişleri uyarıya dönüşür. Bağlanırken pil
zaten düşükse (ör. %12) bir kez uyarılır. Şarj kablosu takılınca sayaç sıfırlanır; çıkarılıp yeniden düşerse
yeniden uyarır.

Şarj yetmiyorsa: bilgisayarın USB'si çoğu zaman 0,5–0,9 A verir; ekran açıkken telefon bundan fazlasını harcar,
"şarj oluyor" der ama pil düşer. Takılıyken pil en yüksek gördüğümüzden WEAK_DROP kadar düşerse şarj yetmiyor
sayılır: eşik uyarıları takılı değilmiş gibi sürer (ayrı bir mesajla). Tek yüzdelik oynama yetmez (boşuna
uyarmasın).
"""

THRESHOLDS = (15, 10, 5)
LOW = THRESHOLDS[0]
WEAK_DROP = 2


def is_low(battery, weak=False) -> bool:
    """Şu an düşük pil mi: %15 ya da altı ve şarjda değil (ya da takılı ama şarj yetmiyor)."""
    return bool(battery) and (not battery.get("charging") or weak) and 0 <= battery.get("level", -1) <= LOW


class Takip:
    def __init__(self):
        self.warned: dict[str, int] = {}  # cihaz → en son uyarılan eşik
        self.peak: dict[str, int] = {}  # takılıyken görülen en yüksek seviye
        self.last: dict[str, int] = {}  # son bildirilen seviye

    def weak(self, device_id: str) -> bool:
        """Takılı ama pil düşüyor mu (şarj yetmiyor)."""
        return device_id in self.peak and 0 <= self.last.get(device_id, -1) <= self.peak[device_id] - WEAK_DROP

    def check(self, device_id: str, battery) -> int | None:
        """Yeni bir eşiğe inildiyse o eşik, yoksa None."""
        if not battery or battery.get("level", -1) < 0:
            return None
        level = battery["level"]
        self.last[device_id] = level
        if battery.get("charging"):
            if device_id not in self.peak:  # yeni takıldı: baştan
                self.peak[device_id] = level
                self.warned.pop(device_id, None)
                return None
            self.peak[device_id] = max(self.peak[device_id], level)
            if not self.weak(device_id):
                return None
        else:
            self.peak.pop(device_id, None)
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
        for table in (self.warned, self.peak, self.last):
            for d in [d for d in table if d not in live]:
                table.pop(d)
