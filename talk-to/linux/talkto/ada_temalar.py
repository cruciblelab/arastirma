"""Üst adanın temaları (Ada Place): renkler ve süsler, tatlıdan havalıya.

Renkler: bg1/bg2 (yukarıdan aşağı zemin), wave1/wave2 (dalga), text (yazı ve simgeler).
Süsler (fx) adanın üstünden geçen saydam katmandır; çizimi gnome-ada/src/sahne.js (adada) ve
talkto/ui/ada_sahne.py (önizlemede). Süs alanları: type, color, color2 (yalnızca aurora), alpha (0–1), count,
size (px), speed (px/sn; glint ve lightning'de kaç saniyede bir), shoot (stars: kayan yıldız).
"""

GROUPS = {"tatli": "Tatlı", "sakin": "Sakin", "havali": "Havalı"}
FX_TYPES = ("clouds", "fog", "stars", "snow", "petals", "bubbles", "hearts", "fireflies", "aurora", "rain", "neon",
            "glint", "lightning")
COLOR_KEYS = ("bg1", "bg2", "wave1", "wave2", "text")


def _theme(name, group, desc, bg1, bg2, wave1, wave2, text, *fx):
    return {"name": name, "group": group, "desc": desc,
            "colors": {"bg1": bg1, "bg2": bg2, "wave1": wave1, "wave2": wave2, "text": text}, "fx": list(fx)}


def _fx(type, color, alpha, count=0, size=4, speed=10, **extra):  # noqa: A002 (alan adı "type")
    return dict({"type": type, "color": color, "alpha": alpha, "count": count, "size": size, "speed": speed}, **extra)


THEMES = {
    # --- tatlı ---
    "pamuk": _theme("Pamuk şeker", "tatli", "Pembe gökte üstünden süzülen bulutlar",
                    "#f8a5c2", "#a5bfff", "#ff6f9c", "#ffffff", "#2b1b3a",
                    _fx("clouds", "#ffffff", 0.85, count=4, size=8, speed=9)),
    "sakura": _theme("Sakura", "tatli", "Rüzgârda savrulan kiraz yaprakları",
                     "#2d1b33", "#5c2a4d", "#ff8fab", "#ffc2d1", "#fff0f5",
                     _fx("petals", "#ffc2d1", 0.9, count=10, size=3.5, speed=12)),
    "baloncuk": _theme("Baloncuk", "tatli", "Yukarı süzülen sabun köpükleri",
                       "#023e8a", "#0096c7", "#90e0ef", "#caf0f8", "#f0fbff",
                       _fx("bubbles", "#ffffff", 0.5, count=7, size=3, speed=9)),
    "kalpler": _theme("Kalpler", "tatli", "Usulca yükselen minik kalpler",
                      "#590d22", "#a4133c", "#ff758f", "#ffb3c1", "#fff0f3",
                      _fx("hearts", "#ffccd5", 0.7, count=5, size=4, speed=7)),
    # --- sakin ---
    "deniz": _theme("Deniz", "sakin", "Süssüz, sade", "#0a2342", "#12436b", "#2ec4b6", "#8de4ff", "#eaf6ff"),
    "orman": _theme("Orman", "sakin", "Süssüz, sade", "#0b2b1c", "#154734", "#52b788", "#b7e4c7", "#eefaf2"),
    "gunbatimi": _theme("Gün batımı", "sakin", "Süssüz, sade", "#2b1055", "#7a2e5c", "#ff9e5e", "#ffd166", "#fff4e6"),
    "gece": _theme("Gece", "sakin", "Süssüz, sade", "#0f0f14", "#1d1b2e", "#7f5af0", "#2cb67d", "#f2f0ff"),
    "sis": _theme("Sisli sabah", "sakin", "Adanın üstünden ağır ağır geçen sis",
                  "#2f3e46", "#52796f", "#cad2c5", "#84a98c", "#f4f7f2",
                  _fx("fog", "#ffffff", 0.3, count=3, speed=6)),
    "atesbocegi": _theme("Ateş böceği", "sakin", "Karanlıkta yanıp sönen ışıklar",
                         "#081c15", "#1b4332", "#95d5b2", "#d8f3dc", "#effaf3",
                         _fx("fireflies", "#ffe66d", 0.9, count=5, size=2.5, speed=10)),
    "kar": _theme("Kar", "sakin", "Yavaşça yağan kar",
                  "#1b263b", "#415a77", "#e0e1dd", "#adb5bd", "#f8f9fa",
                  _fx("snow", "#ffffff", 0.8, count=14, size=1.6, speed=10)),
    # --- havalı ---
    "kuzey": _theme("Kuzey ışıkları", "havali", "Yıldızların altında dalgalanan ışık perdeleri",
                    "#03071e", "#0b132b", "#64dfdf", "#80ffdb", "#e8fffb",
                    _fx("stars", "#ffffff", 0.7, count=10, size=1, speed=10),
                    _fx("aurora", "#72efdd", 0.42, count=2, size=10, speed=10, color2="#b388eb")),
    "galaksi": _theme("Galaksi", "havali", "Bulutsu, ışıldayan yıldızlar ve kayan yıldız",
                      "#10002b", "#3c096c", "#c77dff", "#e0aaff", "#f6ecff",
                      _fx("fog", "#c77dff", 0.22, count=2, speed=4),
                      _fx("stars", "#ffffff", 0.8, count=16, size=1, speed=12, shoot=True)),
    "neon": _theme("Neon", "havali", "Parlayan kenarlar, ince yağmur",
                   "#0d0221", "#1b0b3b", "#ff2a6d", "#05d9e8", "#f2fbff",
                   _fx("rain", "#05d9e8", 0.3, count=10, size=4, speed=90),
                   _fx("neon", "#ff2a6d", 0.9, speed=10)),
    "firtina": _theme("Fırtına", "havali", "Kara bulutlar, yağmur ve ara ara şimşek",
                      "#0b0c10", "#1f2833", "#66fcf1", "#45a29e", "#eefcfb",
                      _fx("clouds", "#c5c6c7", 0.16, count=2, size=12, speed=14),
                      _fx("rain", "#c5c6c7", 0.4, count=14, size=5, speed=160),
                      _fx("lightning", "#ffffff", 0.35, speed=9)),
    "altin": _theme("Altın", "havali", "Siyah üstüne altın; ara ara parıltı geçer",
                    "#141414", "#2b2b2b", "#d4af37", "#f9e79f", "#fff8e1",
                    _fx("stars", "#f9e79f", 0.7, count=8, size=1.2, speed=8),
                    _fx("glint", "#fff3c4", 0.35, speed=5)),
}
DEFAULT = "deniz"

MOTIONS = {
    "canli": ("Canlı", "Süsler akıcı hareket eder."),
    "yavas": ("Yavaş", "Süsler yarı hızda ve daha seyrek çizilir (daha az iş)."),
    "durgun": ("Durgun", "Süsler durur (resim gibi); hiç canlandırma yok."),
}


def problems():
    """Tema tablosundaki yanlışlar (testler için)."""
    out = []
    for key, th in THEMES.items():
        if th["group"] not in GROUPS:
            out.append(f"{key}: grup {th['group']}")
        for c in COLOR_KEYS:
            v = th["colors"].get(c, "")
            if not (isinstance(v, str) and len(v) == 7 and v[0] == "#" and all(ch in "0123456789abcdef" for ch in v[1:])):
                out.append(f"{key}: renk {c}={v!r}")
        for fx in th["fx"]:
            if fx["type"] not in FX_TYPES:
                out.append(f"{key}: süs {fx['type']}")
            if not 0 < fx["alpha"] <= 1 or not 0 <= fx["count"] <= 24 or not 0 < fx["size"] <= 16:
                out.append(f"{key}: süs ölçüsü {fx}")
    return out
