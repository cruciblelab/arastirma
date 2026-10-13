"""Üst adanın temaları (Ada Place): renkler ve süsler, tatlıdan havalıya.

Renkler: bg1/bg2 (yukarıdan aşağı zemin), wave1/wave2 (dalga), text (yazı ve simgeler).
Gün döngüsü temasında (cycle) renkler ve süsler saate göre değişir: resolve(tema, saat).
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
    # Deniz, Orman ve Kar isteğe bağlı saate göre değişir (cycle_optional; Ada sekmesindeki "Saate göre değişsin").
    # Gündüz hâlleri temanın kendi renkleri; akşam, gece ve şafak ona uygun.
    "deniz": dict(_theme("Deniz", "sakin", "Sade deniz; saate göre gün batımı ve yıldızlı gece",
                         "#0a2342", "#12436b", "#2ec4b6", "#8de4ff", "#eaf6ff"),
                  cycle_optional=True,
                  cycle=[(5.5, 6.5, {"bg1": "#1d2b53", "bg2": "#9e4f6a", "wave1": "#f67280", "wave2": "#f8b195"},
                          [_fx("stars", "#ffffff", 0.3, count=5, size=0.9, speed=8)]),
                         (8.0, 17.0, {"bg1": "#0a2342", "bg2": "#12436b", "wave1": "#2ec4b6", "wave2": "#8de4ff"}, []),
                         (18.5, 19.5, {"bg1": "#2b1055", "bg2": "#a4471f", "wave1": "#ff9e5e", "wave2": "#ffd166"}, []),
                         (21.0, 4.5, {"bg1": "#020b1c", "bg2": "#0a2342", "wave1": "#2ec4b6", "wave2": "#5390d9"},
                          [_fx("stars", "#ffffff", 0.7, count=10, size=1, speed=10)])]),
    "orman": dict(_theme("Orman", "sakin", "Sade orman; saate göre akşam ve ateş böcekli gece",
                         "#0b2b1c", "#154734", "#52b788", "#b7e4c7", "#eefaf2"),
                  cycle_optional=True,
                  cycle=[(5.5, 6.5, {"bg1": "#1b2f26", "bg2": "#7a5233", "wave1": "#95d5b2", "wave2": "#f2cc8f"},
                          [_fx("fog", "#ffffff", 0.2, count=2, speed=4)]),
                         (8.0, 17.0, {"bg1": "#0b2b1c", "bg2": "#154734", "wave1": "#52b788", "wave2": "#b7e4c7"}, []),
                         (18.5, 19.5, {"bg1": "#2b1d0e", "bg2": "#6b3e1f", "wave1": "#fb8500", "wave2": "#ffb703"}, []),
                         (21.0, 4.5, {"bg1": "#03120c", "bg2": "#0b2b1c", "wave1": "#2d6a4f", "wave2": "#52b788"},
                          [_fx("fireflies", "#ffe66d", 0.85, count=5, size=2.5, speed=10)])]),
    "gunbatimi": _theme("Gün batımı", "sakin", "Süssüz, sade", "#2b1055", "#7a2e5c", "#ff9e5e", "#ffd166", "#fff4e6"),
    "gece": _theme("Gece", "sakin", "Süssüz, sade", "#0f0f14", "#1d1b2e", "#7f5af0", "#2cb67d", "#f2f0ff"),
    "sis": _theme("Sisli sabah", "sakin", "Adanın üstünden ağır ağır geçen sis",
                  "#2f3e46", "#52796f", "#cad2c5", "#84a98c", "#f4f7f2",
                  _fx("fog", "#ffffff", 0.3, count=3, speed=6)),
    "dongu": dict(_theme("Gün döngüsü", "sakin", "Saate göre: şafak, gündüz, gün batımı, gece",
                         "#8ecae6", "#d8f1ff", "#219ebc", "#ffffff", "#0b2545"),
                  # (başlangıç, bitiş saati, renkler, süsler): arada renkler yavaşça geçer, süsler biri solarken
                  # öteki belirir
                  cycle=[(5.5, 6.5, {"bg1": "#2b2d55", "bg2": "#b5523b", "wave1": "#f2cc8f", "wave2": "#ffe8d6"},
                          [_fx("fog", "#ffffff", 0.22, count=2, speed=5),
                           _fx("stars", "#ffffff", 0.35, count=6, size=0.9, speed=8)]),
                         (8.0, 16.5, {"bg1": "#8ecae6", "bg2": "#d8f1ff", "wave1": "#219ebc", "wave2": "#ffffff"},
                          [_fx("clouds", "#ffffff", 0.75, count=3, size=8, speed=8)]),
                         (18.0, 19.0, {"bg1": "#3a0ca3", "bg2": "#c2410c", "wave1": "#fcbf49", "wave2": "#ffd6a5"},
                          [_fx("clouds", "#ffd6a5", 0.3, count=2, size=10, speed=8)]),
                         (21.0, 4.5, {"bg1": "#03045e", "bg2": "#0b132b", "wave1": "#48cae4", "wave2": "#90e0ef"},
                          [_fx("stars", "#ffffff", 0.8, count=12, size=1, speed=12, shoot=True)])]),
    "atesbocegi": _theme("Ateş böceği", "sakin", "Karanlıkta yanıp sönen ışıklar",
                         "#081c15", "#1b4332", "#95d5b2", "#d8f3dc", "#effaf3",
                         _fx("fireflies", "#ffe66d", 0.9, count=5, size=2.5, speed=10)),
    "kar": dict(_theme("Kar", "sakin", "Yavaşça yağan kar; saate göre pembe akşam ve yıldızlı gece",
                       "#1b263b", "#415a77", "#e0e1dd", "#adb5bd", "#f8f9fa",
                       _fx("snow", "#ffffff", 0.8, count=14, size=1.6, speed=10)),
                cycle_optional=True,
                cycle=[(5.5, 6.5, {"bg1": "#3d3a5c", "bg2": "#8e5a6e", "wave1": "#e0e1dd", "wave2": "#ffc8dd"},
                        [_fx("snow", "#ffffff", 0.8, count=12, size=1.6, speed=10)]),
                       (8.0, 17.0, {"bg1": "#1b263b", "bg2": "#415a77", "wave1": "#e0e1dd", "wave2": "#adb5bd"},
                        [_fx("snow", "#ffffff", 0.8, count=14, size=1.6, speed=10)]),
                       (18.5, 19.5, {"bg1": "#2e2a4f", "bg2": "#7d4e6d", "wave1": "#e0e1dd", "wave2": "#ffafcc"},
                        [_fx("snow", "#ffffff", 0.8, count=12, size=1.6, speed=10)]),
                       (21.0, 4.5, {"bg1": "#0b1320", "bg2": "#1b263b", "wave1": "#adb5bd", "wave2": "#e0e1dd"},
                        [_fx("snow", "#ffffff", 0.7, count=12, size=1.5, speed=9),
                         _fx("stars", "#ffffff", 0.6, count=8, size=0.9, speed=10)])]),
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

MOTIONS = {  # dalga ve süsler birlikte
    "canli": ("Canlı", "Dalga ve süsler akıcı hareket eder."),
    "yavas": ("Yavaş", "Yarı hızda ve yarı yarıya seyrek çizilir (daha az iş)."),
    "durgun": ("Durgun", "Hiç kıpırdamaz (resim gibi); çalarken dalga yüksek durur."),
}


LIGHT_TEXT, DARK_TEXT = "#f4f8ff", "#0b2545"


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _hex(c):
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)


def mix(a, b, u):
    return _hex(x + (y - x) * u for x, y in zip(_rgb(a), _rgb(b)))


def luminance(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def middle(colors) -> str:
    """Zeminin ortası (yazı adanın ortasında durur)."""
    return mix(colors["bg1"], colors["bg2"], 0.5)


def _in(h, a, b):
    """h saati [a, b] aralığında mı (gece yarısını aşan aralıklar dahil)."""
    return a <= h <= b if a <= b else h >= a or h <= b


def _since(h, a):
    return (h - a) % 24


def resolve(theme: dict, hour: float, cycle_on: bool = True) -> dict:
    """Saate göre değişen temanın o saatteki hâli (renkler ve süsler); öteki temalar olduğu gibi. Deniz, Orman ve
    Kar'da değişim isteğe bağlı (cycle_on: Ada sekmesindeki "Saate göre değişsin")."""
    cycle = theme.get("cycle")
    if not cycle or (theme.get("cycle_optional") and not cycle_on):
        return theme
    hour %= 24
    n = len(cycle)
    for i, (start, end, colors, fx) in enumerate(cycle):
        if _in(hour, start, end):
            c, fxs = dict(colors), list(fx)
            break
        nxt = cycle[(i + 1) % n]
        gap = _since(nxt[0], end)
        if 0 < _since(hour, end) < gap:  # bu duraktan sonrakine geçiş
            u = _since(hour, end) / gap
            c = {k: mix(colors[k], nxt[2][k], u) for k in colors}
            fxs = [dict(f, alpha=f["alpha"] * (1 - u)) for f in fx] + [dict(f, alpha=f["alpha"] * u) for f in nxt[3]]
            fxs = [f for f in fxs if f["alpha"] >= 0.02]
            break
    # Yazı: o anki zeminde (yazının durduğu orta renk) en okunur olan, açık ya da koyu
    c["text"] = max((LIGHT_TEXT, DARK_TEXT), key=lambda t: contrast(t, middle(c)))
    return dict(theme, colors=c, fx=fxs)


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
