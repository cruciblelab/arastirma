"""Ada temalarının süsleri (bulut, sis, yıldız, ...): Ada Place önizlemesi için.

Adadaki çizimin (gnome-ada/src/sahne.js) birebir Python karşılığı; ikisi aynı resmi çizmeli (test_ada_place
karşılaştırır). Birini değiştirirsen ötekini de değiştir. pycairo (python3-gi-cairo) yoksa çizim yok:
Ada Place renkli kartlar gösterir.
"""

import math

try:
    import cairo
except ImportError:  # python3-gi-cairo kurulu değil
    cairo = None

PUFFS = ((-1.0, 0.25, 0.7), (-0.35, -0.15, 0.95), (0.45, -0.05, 0.85), (1.1, 0.25, 0.6))
TAU = math.pi * 2


def rnd(i, k):
    x = math.sin(i * 12.9898 + k * 78.233) * 43758.5453
    return x - math.floor(x)


def wrap(v, m):
    return ((v % m) + m) % m


def rgb(hexcolor):
    h = (hexcolor or "#ffffff").lstrip("#")
    if len(h) == 3:
        h = "".join(c + c for c in h)
    n = int(h, 16)
    return ((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255


def shape(cr, w, h, r):
    """Adanın biçimi: üstü düz (üst çubuktan sarkar), alt köşeleri yuvarlak."""
    r = max(0, min(r, h / 2, w / 2))
    cr.move_to(0, 0)
    cr.line_to(w, 0)
    cr.line_to(w, h - r)
    cr.arc(w - r, h - r, r, 0, math.pi / 2)
    cr.line_to(r, h)
    cr.arc(r, h - r, r, math.pi / 2, math.pi)
    cr.close_path()


def blob(cr, cx, cy, rx, ry, c, a):
    if rx <= 0 or ry <= 0 or a <= 0:
        return
    cr.save()
    cr.translate(cx, cy)
    cr.scale(rx, ry)
    g = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
    g.add_color_stop_rgba(0, *c, a)
    g.add_color_stop_rgba(0.55, *c, a * 0.5)
    g.add_color_stop_rgba(1, *c, 0)
    cr.set_source(g)
    cr.arc(0, 0, 1, 0, TAU)
    cr.fill()
    cr.restore()


def heart(cr, x, y, r):
    cr.save()
    cr.translate(x, y)
    cr.scale(r, r)
    cr.move_to(0, 0.85)
    cr.curve_to(-0.6, 0.45, -1.0, 0.05, -0.75, -0.45)
    cr.curve_to(-0.5, -0.9, 0, -0.75, 0, -0.35)
    cr.curve_to(0, -0.75, 0.5, -0.9, 0.75, -0.45)
    cr.curve_to(1.0, 0.05, 0.6, 0.45, 0, 0.85)
    cr.close_path()
    cr.restore()


def background(cr, w, h, colors, r):
    shape(cr, w, h, r)
    g = cairo.LinearGradient(0, 0, 0, h)
    g.add_color_stop_rgba(0, *rgb(colors["bg1"]), 1)
    g.add_color_stop_rgba(1, *rgb(colors["bg2"]), 1)
    cr.set_source(g)
    cr.fill()


def clamp(v, a, b):
    return max(a, min(b, v))


def mix(a, b, u):
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)


def hsl(h, s, l):  # noqa: E741
    h = wrap(h, 360) / 360
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q

    def f(x):
        x = wrap(x, 1)
        if x < 1 / 6:
            return p + (q - p) * 6 * x
        if x < 1 / 2:
            return q
        if x < 2 / 3:
            return p + (q - p) * (2 / 3 - x) * 6
        return p
    return f(h + 1 / 3), f(h), f(h - 1 / 3)


def night_of(hour):
    if hour < 5.5 or hour >= 20.5:
        return 1
    if hour < 7:
        return (7 - hour) / 1.5
    if hour > 19:
        return (hour - 19) / 1.5
    return 0


def sea(cr, w, h, t, fx, sc, A):
    """Deniz manzarası (sahne.js sahneSea)."""
    hour = 13 if fx.get("hour") is None else fx["hour"]
    hz = round(h * (0.42 if h < 60 else 0.38))
    far, near = rgb(fx.get("color")), rgb(fx.get("color2") or fx.get("color"))
    night = night_of(hour)
    if night > 0:
        n = 9 if h < 60 else 26
        for i in range(n):
            x, y = rnd(i, 11) * w, rnd(i, 12) * hz * 0.92
            tw = 0.5 + 0.5 * math.sin(t * (0.6 + rnd(i, 13)) + rnd(i, 14) * TAU)
            cr.set_source_rgba(1, 1, 1, A * night * (0.25 + 0.55 * tw))
            cr.arc(x, y, sc * (0.45 + 0.5 * rnd(i, 15)), 0, TAU)
            cr.fill()
    day = 6 <= hour < 19
    p = (hour - 6) / 13 if day else wrap(hour - 19, 24) / 11
    bx = w * (0.12 + 0.76 * p)
    by = hz - hz * (0.55 if h < 60 else 0.6) * math.sin(math.pi * p) + max(1.5, hz * 0.08)
    br = clamp(h * 0.17, 3.2 * sc, 14 * sc)
    body = mix((1, 0.62, 0.3), (1, 0.93, 0.66), clamp(math.sin(math.pi * p) * 1.6, 0, 1)) if day \
        else (0.91, 0.94, 0.98)
    gr = br * (3.4 if day else 2.6)
    glow = cairo.RadialGradient(bx, by, 0, bx, by, gr)
    glow.add_color_stop_rgba(0, *body, A * (0.45 if day else 0.25))
    glow.add_color_stop_rgba(1, *body, 0)
    cr.set_source(glow)
    cr.arc(bx, by, gr, 0, TAU)
    cr.fill()
    cr.push_group()
    cr.set_source_rgba(*body, 1)
    cr.arc(bx, by, br, 0, TAU)
    cr.fill()
    if not day:
        cr.set_operator(cairo.OPERATOR_DEST_OUT)
        cr.arc(bx + br * 0.45, by - br * 0.18, br * 0.92, 0, TAU)
        cr.fill()
        cr.set_operator(cairo.OPERATOR_OVER)
    cr.pop_group_to_source()
    cr.paint_with_alpha(A * (0.75 if h < 60 else 1))
    if day and h >= 60:
        cr.set_line_width(1.1 * sc)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        for i in range(2):
            gx = wrap(w * (0.25 + 0.35 * i) + t * 4 * sc * (1 + 0.3 * i), w + 40) - 20
            gy = hz * (0.35 + 0.18 * i) + math.sin(t * 0.8 + i) * 3 * sc
            s2, flap = (4 + 1.5 * i) * sc, 0.35 + 0.25 * math.sin(t * 5 + i * 2)
            cr.set_source_rgba(0.12, 0.16, 0.22, A * 0.55)
            cr.move_to(gx - s2, gy - s2 * flap)
            cr.curve_to(gx - s2 * 0.5, gy - s2 * flap * 1.2, gx - s2 * 0.2, gy, gx, gy + s2 * 0.15)
            cr.curve_to(gx + s2 * 0.2, gy, gx + s2 * 0.5, gy - s2 * flap * 1.2, gx + s2, gy - s2 * flap)
            cr.stroke()
    g = cairo.LinearGradient(0, hz, 0, h)
    g.add_color_stop_rgba(0, *far, A)
    g.add_color_stop_rgba(1, *near, A)
    cr.set_source(g)
    cr.rectangle(0, hz, w, h - hz)
    cr.fill()
    hb = max(1.5 * sc, h * 0.05)
    haze = cairo.LinearGradient(0, hz - hb, 0, hz + hb)
    haze.add_color_stop_rgba(0, 1, 1, 1, 0)
    haze.add_color_stop_rgba(0.5, 1, 1, 1, A * (0.22 - 0.1 * night))
    haze.add_color_stop_rgba(1, 1, 1, 1, 0)
    cr.set_source(haze)
    cr.rectangle(0, hz - hb, w, 2 * hb)
    cr.fill()
    m = 3 if h < 60 else 9
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for j in range(1, m + 1):
        u = j / (m + 1)
        y0 = hz + (h - hz) * u ** 1.6
        amp, length, ph = (0.35 + 2.2 * u) * sc, (16 + 60 * u) * sc, t * (0.25 + 0.6 * u) + j * 1.7
        x = 0
        while x <= w + 4:
            y = y0 + amp * math.sin(x / length * TAU + ph)
            if x == 0:
                cr.move_to(x, y)
            else:
                cr.line_to(x, y)
            x += 4
        cr.set_line_width((0.5 + 1.1 * u) * sc)
        cr.set_source_rgba(1, 1, 1, A * (0.05 + 0.13 * u) * (1 - 0.5 * night))
        cr.stroke()
    up = clamp((hz - by) / max(1, hz * 0.25), 0, 1)
    if up > 0:
        n = 6 if h < 60 else 22
        for i in range(n):
            u = (i + 1) / n
            y = hz + (h - hz) * u ** 1.5
            spread = br * (0.4 + 2.4 * u)
            k = 1 + (1 if u > 0.35 else 0) + (1 if u > 0.7 else 0)
            cr.set_line_width(max(0.5 * sc, (h - hz) * 0.012 * (1 + 2 * u)))
            for j in range(k):
                q = i * 3 + j
                length = spread * (0.25 + 0.45 * rnd(q, 41))
                x = bx + (rnd(q, 42) * 2 - 1) * spread * 0.75 + math.sin(t * (0.6 + rnd(q, 43)) + i) * br * 0.3 * u
                a = A * up * (0.6 if day else 0.5) * (1 - 0.4 * u) * \
                    (0.35 + 0.65 * max(0, math.sin(t * (1.4 + rnd(q, 44) * 1.6) + i * 1.9 + j)))
                cr.set_source_rgba(*body, a)
                cr.move_to(x - length / 2, y)
                cr.line_to(x + length / 2, y)
                cr.stroke()


def prism(cr, w, h, t, fx, sc, A):
    """Prizma (destekçi teması): dönen hologram renkleri ve ışık demetleri (sahne.js sahnePrism)."""
    a = fx.get("alpha", 0.35) * A
    h0 = t * 12 * (fx.get("speed") or 10) / 10
    g = cairo.LinearGradient(0, 0, w, h * 0.6)
    for i in range(7):
        c = hsl(h0 + i * 55, 0.85, 0.62)
        g.add_color_stop_rgba(i / 6, *c, a * (0.55 + 0.45 * math.sin(t * 0.7 + i)))
    cr.set_source(g)
    cr.rectangle(0, 0, w, h)
    cr.fill()
    for i in range(3):
        x = wrap(rnd(i, 21) * w * 1.6 + t * (6 + 4 * i) * sc, w * 1.6) - w * 0.3
        bw = (8 + 10 * rnd(i, 22)) * sc
        beam = cairo.LinearGradient(x - bw, 0, x + bw, 0)
        beam.add_color_stop_rgba(0, 1, 1, 1, 0)
        beam.add_color_stop_rgba(0.5, 1, 1, 1, a * 0.5)
        beam.add_color_stop_rgba(1, 1, 1, 1, 0)
        k = 0.45 * h
        cr.move_to(x - bw, 0)
        cr.line_to(x + bw, 0)
        cr.line_to(x + bw - k, h)
        cr.line_to(x - bw - k, h)
        cr.close_path()
        cr.set_source(beam)
        cr.fill()


def shards(cr, w, h, t, fx, sc, A):
    """Kristal parçaları (sahne.js sahneShards)."""
    n, s, v = fx.get("count") or 0, (fx.get("size") or 4) * sc, (fx.get("speed") or 10) * sc
    a = fx.get("alpha", 0.6) * A
    for i in range(n):
        r = s * (0.7 + 0.8 * rnd(i, 31))
        span = h + 4 * r
        y = h + 2 * r - wrap(rnd(i, 32) * span + t * v * (0.5 + 0.6 * rnd(i, 33)), span)
        x = rnd(i, 34) * w + math.sin(t * 0.9 + i * 1.7) * s
        c = hsl(t * 30 + i * 47, 0.8, 0.7)
        cr.save()
        cr.translate(x, y)
        cr.rotate(t * (0.6 + rnd(i, 35)) * (1 if rnd(i, 36) > 0.5 else -1) + i)
        cr.move_to(0, -r)
        cr.line_to(r * 0.55, 0)
        cr.line_to(0, r)
        cr.line_to(-r * 0.55, 0)
        cr.close_path()
        g = cairo.LinearGradient(-r * 0.55, -r, r * 0.55, r)
        g.add_color_stop_rgba(0, 1, 1, 1, a)
        g.add_color_stop_rgba(1, *c, a * 0.5)
        cr.set_source(g)
        cr.fill_preserve()
        cr.set_line_width(0.7 * sc)
        cr.set_source_rgba(1, 1, 1, a * 0.9)
        cr.stroke()
        cr.restore()


def _fx(cr, w, h, t, fx, sc, A, R):  # noqa: C901 (her süs bir dal)
    c = rgb(fx.get("color"))
    c2 = rgb(fx.get("color2") or fx.get("color"))
    n = fx.get("count") or 0
    s = (fx.get("size") or 4) * sc
    v = (fx.get("speed") or 10) * sc
    a = fx.get("alpha", 0.5) * A
    kind = fx.get("type")
    if kind == "clouds":
        for i in range(n):
            span = w + 6 * s
            x = wrap(rnd(i, 1) * span + t * v * (0.6 + 0.8 * rnd(i, 2)), span) - 3 * s
            y = h * (0.2 + 0.6 * rnd(i, 3))
            r = s * (0.75 + 0.5 * rnd(i, 4))
            for dx, dy, k in PUFFS:
                blob(cr, x + dx * r, y + dy * r, k * r * 1.25, k * r, c, a)
    elif kind == "fog":
        for i in range(n):
            L = w * (0.55 + 0.5 * rnd(i, 1))
            H = h * 0.35 * (0.7 + 0.6 * rnd(i, 2))
            span = w + L
            x = wrap(rnd(i, 3) * span + t * v * (0.7 + 0.6 * rnd(i, 4)), span) - L / 2
            y = h * (0.2 + 0.6 * rnd(i, 5)) + math.sin(t * 0.3 + i * 1.7) * h * 0.08
            breathe = 0.65 + 0.35 * math.sin(t * 0.4 + i * 2.1)
            blob(cr, x, y, L / 2, H, c, a * breathe)
    elif kind == "stars":
        for i in range(n):
            x, y = rnd(i, 1) * w, rnd(i, 2) * h
            r = s * (0.4 + 0.6 * rnd(i, 3))
            tw = 0.5 + 0.5 * math.sin(t * (fx.get("speed") or 10) * 0.1 * (0.5 + rnd(i, 4)) + rnd(i, 5) * TAU)
            aa = a * (0.25 + 0.75 * tw)
            cr.set_source_rgba(*c, aa)
            cr.arc(x, y, r, 0, TAU)
            cr.fill()
            if rnd(i, 6) > 0.7:
                L = r * 3 * tw
                cr.set_line_width(max(0.5, r * 0.35))
                cr.set_source_rgba(*c, aa * 0.7)
                cr.move_to(x - L, y)
                cr.line_to(x + L, y)
                cr.move_to(x, y - L)
                cr.line_to(x, y + L)
                cr.stroke()
        if fx.get("shoot"):
            P = 7
            k = math.floor(t / P)
            p = t - k * P
            if p < 1 and rnd(k, 7) > 0.3:
                hx = rnd(k, 8) * w * 0.6 + p * w * 0.4
                hy = h * 0.15 * rnd(k, 9) + p * w * 0.14
                L = 18 * sc
                g = cairo.LinearGradient(hx - L, hy - L * 0.35, hx, hy)
                g.add_color_stop_rgba(0, *c, 0)
                g.add_color_stop_rgba(1, *c, a * (1 - p))
                cr.set_source(g)
                cr.set_line_width(1.2 * sc)
                cr.move_to(hx - L, hy - L * 0.35)
                cr.line_to(hx, hy)
                cr.stroke()
    elif kind == "snow":
        for i in range(n):
            r = s * (0.5 + 0.6 * rnd(i, 1))
            span = h + 4 * r
            y = wrap(rnd(i, 3) * span + t * v * (0.6 + 0.8 * rnd(i, 2)), span) - 2 * r
            x = rnd(i, 4) * w + math.sin(t * 0.9 * (0.5 + rnd(i, 5)) + i) * s * 2
            blob(cr, x, y, r * 1.6, r * 1.6, c, a)
    elif kind == "petals":
        for i in range(n):
            r = s * (0.6 + 0.6 * rnd(i, 1))
            vi = v * (0.5 + 0.7 * rnd(i, 2))
            span_y, span_x = h + 4 * r, w + 4 * r
            y = wrap(rnd(i, 3) * span_y + t * vi, span_y) - 2 * r
            x = wrap(rnd(i, 4) * span_x + t * vi * 0.6 + math.sin(t * 1.3 + i) * s * 1.5, span_x) - 2 * r
            cr.save()
            cr.translate(x, y)
            cr.rotate(t * (0.8 + rnd(i, 5)) * (1 if rnd(i, 6) > 0.5 else -1) + i)
            cr.scale(1, 0.5 + 0.25 * math.sin(t * 2 + i))
            cr.set_source_rgba(*c, a)
            cr.arc(0, 0, r, 0, TAU)
            cr.fill()
            cr.restore()
    elif kind == "bubbles":
        for i in range(n):
            r = s * (0.5 + 0.7 * rnd(i, 1))
            span = h + 4 * r
            y = h + 2 * r - wrap(rnd(i, 3) * span + t * v * (0.6 + 0.8 * rnd(i, 2)), span)
            x = rnd(i, 4) * w + math.sin(t * 1.4 * (0.6 + rnd(i, 5)) + i * 1.3) * s
            cr.set_line_width(max(0.6 * sc, r * 0.18))
            cr.set_source_rgba(*c, a)
            cr.arc(x, y, r, 0, TAU)
            cr.stroke()
            cr.set_source_rgba(*c, a * 0.9)
            cr.arc(x - r * 0.35, y - r * 0.35, r * 0.22, 0, TAU)
            cr.fill()
    elif kind == "hearts":
        for i in range(n):
            r = s * (0.6 + 0.6 * rnd(i, 1))
            span = h + 4 * r
            y = h + 2 * r - wrap(rnd(i, 3) * span + t * v * (0.6 + 0.8 * rnd(i, 2)), span)
            x = rnd(i, 4) * w + math.sin(t * 1.2 * (0.6 + rnd(i, 5)) + i * 1.3) * s
            fade = max(0, min(1, y / (h * 0.5) + 0.2))
            heart(cr, x, y, r)
            cr.set_source_rgba(*c, a * fade)
            cr.fill()
    elif kind == "fireflies":
        for i in range(n):
            p = 0.5 + 0.5 * math.sin(t * (1.5 + 1.5 * rnd(i, 1)) + i * 2.3)
            x = w * (0.5 + 0.46 * math.sin(t * v * 0.01 * (0.5 + rnd(i, 2)) + rnd(i, 3) * TAU))
            y = h * (0.5 + 0.38 * math.sin(t * v * 0.013 * (0.5 + rnd(i, 4)) + rnd(i, 5) * TAU))
            g = s * (1.6 + 1.4 * p)
            blob(cr, x, y, g, g, c, a * 0.5 * p)
            cr.set_source_rgba(*c, a * (0.4 + 0.6 * p))
            cr.arc(x, y, s * 0.45, 0, TAU)
            cr.fill()
    elif kind == "aurora":
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        step = max(2, 4 * sc)
        hh = min(h, 48 * sc)  # büyük adada da üst şeritte kalır (yazıların üstünden geçmesin)
        for i in range(n):
            base = hh * (0.3 + 0.35 * rnd(i, 1))
            amp, f = hh * 0.2, 1.2 + 1.2 * rnd(i, 2)
            ph = t * v * 0.03 * (0.6 + 0.8 * rnd(i, 3)) + i * 2
            for lw, k in ((1.0, 0.22), (0.5, 0.4), (0.18, 0.85)):
                x = 0
                while x <= w + step:
                    u = x / w * math.pi * f
                    y = base + amp * math.sin(u + ph) + amp * 0.4 * math.sin(u * 2.3 - ph * 1.3)
                    if x == 0:
                        cr.move_to(x, y)
                    else:
                        cr.line_to(x, y)
                    x += step
                g = cairo.LinearGradient(0, 0, w, 0)
                g.add_color_stop_rgba(0, *c, a * k)
                g.add_color_stop_rgba(0.5, *c2, a * k)
                g.add_color_stop_rgba(1, *c, a * k)
                cr.set_source(g)
                cr.set_line_width(s * lw)
                cr.stroke()
    elif kind == "rain":
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_width(max(0.6, 0.8 * sc))
        for i in range(n):
            L = s * (1.5 + 1.5 * rnd(i, 1))
            span = h + 2 * L
            y = wrap(rnd(i, 3) * span + t * v * (0.8 + 0.4 * rnd(i, 2)), span) - L
            x = rnd(i, 4) * (w + h * 0.3) - y * 0.25
            cr.set_source_rgba(*c, a * (0.5 + 0.5 * rnd(i, 5)))
            cr.move_to(x, y)
            cr.line_to(x - L * 0.25, y + L)
            cr.stroke()
    elif kind == "neon":
        pulse = 0.65 + 0.35 * math.sin(t * (fx.get("speed") or 10) * 0.15)
        if rnd(math.floor(t * 8), 9) > 0.97:
            pulse *= 0.4
        for lw, k in ((6, 0.15), (3, 0.35), (1.2, 0.95)):
            d = lw * sc / 2
            r = max(0, min(R, h / 2) - d)
            cr.move_to(d, 0)
            cr.line_to(d, h - d - r)
            cr.arc_negative(d + r, h - d - r, r, math.pi, math.pi / 2)
            cr.line_to(w - d - r, h - d)
            cr.arc_negative(w - d - r, h - d - r, r, math.pi / 2, 0)
            cr.line_to(w - d, 0)
            cr.set_line_width(lw * sc)
            cr.set_source_rgba(*c, a * k * pulse)
            cr.stroke()
    elif kind == "glint":
        P = max(2, fx.get("speed") or 5)
        p = wrap(t, P) / 1.4
        if p < 1:
            x, bw = -w * 0.3 + p * w * 1.6, w * 0.18
            g = cairo.LinearGradient(x - bw, 0, x + bw, h * 0.6)
            g.add_color_stop_rgba(0, *c, 0)
            g.add_color_stop_rgba(0.5, *c, a)
            g.add_color_stop_rgba(1, *c, 0)
            cr.set_source(g)
            cr.rectangle(0, 0, w, h)
            cr.fill()
    elif kind == "sea":
        sea(cr, w, h, t, fx, sc, A)
    elif kind == "prism":
        prism(cr, w, h, t, fx, sc, A)
    elif kind == "shards":
        shards(cr, w, h, t, fx, sc, A)
    elif kind == "lightning":
        P = max(3, fx.get("speed") or 9)
        k = math.floor(t / P)
        p = t - k * P
        if rnd(k, 3) > 0.35:
            f = 0
            if p < 0.08:
                f = 1 - p / 0.08
            elif 0.18 <= p < 0.26:
                f = 0.7 * (1 - (p - 0.18) / 0.08)
            if f > 0:
                cr.set_source_rgba(*c, a * f)
                cr.paint()


def paint(cr, w, h, t, fx_list, scale=1.0, alpha=1.0, radius=None):
    """Bütün süsler, adanın biçimine kırpılmış (sahne.js sahnePaint)."""
    if cairo is None or not fx_list or alpha <= 0:
        return
    R = 18 * scale if radius is None else radius
    cr.save()
    shape(cr, w, h, R)
    cr.clip()
    for fx in fx_list:
        _fx(cr, w, h, t, fx, scale, alpha, R)
    cr.restore()
