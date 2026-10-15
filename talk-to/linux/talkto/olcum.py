"""GNOME Shell'in işlemci kullanımı: üst adanın kabuğa getirdiği yükü kullanıcının kendi makinesinde ölçmek için.

top anlık değer gösterir ve çok oynar (kullanıcı: "en düşük 4,1 en yüksek 33"). Burada aynı süreç aynı süre
ölçülür, önce seçili hareketle sonra Durgun'da: aradaki fark adanın payıdır (geri kalanı masaüstünün kendisi).
Yüzde, top'taki gibi tek çekirdeğe göre.
"""

import os
import time


def shell_pid() -> int | None:
    """Bu kullanıcının GNOME Shell süreci (giriş ekranınınki başka kullanıcıda)."""
    uid = os.getuid()
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/comm") as f:
                if f.read().strip() != "gnome-shell":
                    continue
            if os.stat(f"/proc/{d}").st_uid == uid:
                return int(d)
        except OSError:
            continue
    return None


def cpu_seconds(pid: int) -> float | None:
    """Sürecin şimdiye dek harcadığı işlemci süresi (sn); okunamazsa None."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            fields = f.read().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, IndexError, ValueError):
        return None


class Sampler:
    """Başladığından beri ortalama işlemci kullanımı (%)."""

    def __init__(self, pid: int):
        self.pid = pid
        self.cpu0, self.t0 = cpu_seconds(pid), time.monotonic()

    def percent(self) -> float | None:
        cpu, dt = cpu_seconds(self.pid), time.monotonic() - self.t0
        if cpu is None or self.cpu0 is None or dt <= 0:
            return None
        return 100 * (cpu - self.cpu0) / dt


def summary(name: str, moving: float | None, still: float | None) -> str:
    """Ölçümün sonucu, kullanıcıya."""
    if moving is None or still is None:
        return "Ölçülemedi (GNOME Shell'in işlemci süresi okunamadı)."
    share = max(0.0, moving - still)
    fmt = lambda v: f"%{v:.1f}".replace(".", ",")  # noqa: E731
    return (f"{name}: {fmt(moving)} · Durgun: {fmt(still)} → adanın payı ≈ {fmt(share)} "
            f"(GNOME Shell, tek çekirdeğe göre; geri kalanı masaüstünün kendisi)")
