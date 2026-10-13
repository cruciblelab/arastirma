// Talk To · Üst ada: temaların süsleri (bulut, sis, yıldız, kar, yaprak, baloncuk, ateş böceği, kuzey ışıkları,
// yağmur, neon, parıltı, kalp, şimşek). Adanın üstünden geçen saydam katman; tıklamaları almaz.
//
// Bu dosya build.py ile extension.js'in içine konur (SAHNE işaretinin yerine). Aynı çizim Talk To'daki
// Ada Place önizlemesinde de var (linux/talkto/ui/ada_sahne.py); ikisi aynı resmi çizmeli (test/sahne_ciz.js ile
// karşılaştırılır). Birini değiştirirsen ötekini de değiştir.
//
// Süs = {type, color, color2?, alpha, count, size, speed}. Konumlar rastgele değil, sıraya bağlı (sahneRnd): her
// çizimde aynı yerden devam eder. t saniye; size ve speed ölçeğe (opt.scale) göre büyür.

const SAHNE_PUFFS = [[-1.0, 0.25, 0.7], [-0.35, -0.15, 0.95], [0.45, -0.05, 0.85], [1.1, 0.25, 0.6]];
const SAHNE_TAU = Math.PI * 2;

function sahneRnd(i, k) {
    const x = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453;
    return x - Math.floor(x);
}

function sahneWrap(v, m) {
    return ((v % m) + m) % m;
}

function sahneRgb(hex) {
    const h = (hex || '#ffffff').replace('#', '');
    const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

// Adanın biçimi: üstü düz (üst çubuktan sarkar), alt köşeleri yuvarlak.
function sahneShape(cr, w, h, r) {
    r = Math.max(0, Math.min(r, h / 2, w / 2));
    cr.moveTo(0, 0);
    cr.lineTo(w, 0);
    cr.lineTo(w, h - r);
    cr.arc(w - r, h - r, r, 0, Math.PI / 2);
    cr.lineTo(r, h);
    cr.arc(r, h - r, r, Math.PI / 2, Math.PI);
    cr.closePath();
}

// Yumuşak kenarlı elips: bulut, sis, ışıltı.
function sahneBlob(cr, cx, cy, rx, ry, rgb, a) {
    if (rx <= 0 || ry <= 0 || a <= 0)
        return;
    cr.save();
    cr.translate(cx, cy);
    cr.scale(rx, ry);
    const g = new Cairo.RadialGradient(0, 0, 0, 0, 0, 1);
    g.addColorStopRGBA(0, rgb[0], rgb[1], rgb[2], a);
    g.addColorStopRGBA(0.55, rgb[0], rgb[1], rgb[2], a * 0.5);
    g.addColorStopRGBA(1, rgb[0], rgb[1], rgb[2], 0);
    cr.setSource(g);
    cr.arc(0, 0, 1, 0, SAHNE_TAU);
    cr.fill();
    cr.restore();
}

function sahneHeart(cr, x, y, r) {
    cr.save();
    cr.translate(x, y);
    cr.scale(r, r);
    cr.moveTo(0, 0.85);
    cr.curveTo(-0.6, 0.45, -1.0, 0.05, -0.75, -0.45);
    cr.curveTo(-0.5, -0.9, 0, -0.75, 0, -0.35);
    cr.curveTo(0, -0.75, 0.5, -0.9, 0.75, -0.45);
    cr.curveTo(1.0, 0.05, 0.6, 0.45, 0, 0.85);
    cr.closePath();
    cr.restore();
}

// Tema önizlemesi için adanın zemini (adada zemini kendi stili çizer).
function sahneBackground(cr, w, h, theme, r) {
    sahneShape(cr, w, h, r);
    const g = new Cairo.LinearGradient(0, 0, 0, h);
    const a = sahneRgb(theme.bg1), b = sahneRgb(theme.bg2);
    g.addColorStopRGBA(0, a[0], a[1], a[2], 1);
    g.addColorStopRGBA(1, b[0], b[1], b[2], 1);
    cr.setSource(g);
    cr.fill();
}

function sahneFx(cr, w, h, t, fx, sc, A, R) {
    const rgb = sahneRgb(fx.color);
    const rgb2 = sahneRgb(fx.color2 || fx.color);
    const n = fx.count || 0;
    const s = (fx.size || 4) * sc;
    const v = (fx.speed || 10) * sc;
    const a = (fx.alpha === undefined ? 0.5 : fx.alpha) * A;
    switch (fx.type) {
    case 'clouds':
        for (let i = 0; i < n; i++) {
            const span = w + 6 * s;
            const x = sahneWrap(sahneRnd(i, 1) * span + t * v * (0.6 + 0.8 * sahneRnd(i, 2)), span) - 3 * s;
            const y = h * (0.2 + 0.6 * sahneRnd(i, 3));
            const r = s * (0.75 + 0.5 * sahneRnd(i, 4));
            for (const [dx, dy, k] of SAHNE_PUFFS)
                sahneBlob(cr, x + dx * r, y + dy * r, k * r * 1.25, k * r, rgb, a);
        }
        break;
    case 'fog':
        for (let i = 0; i < n; i++) {
            const L = w * (0.55 + 0.5 * sahneRnd(i, 1));
            const H = h * 0.35 * (0.7 + 0.6 * sahneRnd(i, 2));
            const span = w + L;
            const x = sahneWrap(sahneRnd(i, 3) * span + t * v * (0.7 + 0.6 * sahneRnd(i, 4)), span) - L / 2;
            const y = h * (0.2 + 0.6 * sahneRnd(i, 5)) + Math.sin(t * 0.3 + i * 1.7) * h * 0.08;
            const breathe = 0.65 + 0.35 * Math.sin(t * 0.4 + i * 2.1);
            sahneBlob(cr, x, y, L / 2, H, rgb, a * breathe);
        }
        break;
    case 'stars': {
        for (let i = 0; i < n; i++) {
            const x = sahneRnd(i, 1) * w, y = sahneRnd(i, 2) * h;
            const r = s * (0.4 + 0.6 * sahneRnd(i, 3));
            const tw = 0.5 + 0.5 * Math.sin(t * (fx.speed || 10) * 0.1 * (0.5 + sahneRnd(i, 4)) + sahneRnd(i, 5) * SAHNE_TAU);
            const aa = a * (0.25 + 0.75 * tw);
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], aa);
            cr.arc(x, y, r, 0, SAHNE_TAU);
            cr.fill();
            if (sahneRnd(i, 6) > 0.7) {  // büyükçe yıldızlar ışıldar
                const L = r * 3 * tw;
                cr.setLineWidth(Math.max(0.5, r * 0.35));
                cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], aa * 0.7);
                cr.moveTo(x - L, y);
                cr.lineTo(x + L, y);
                cr.moveTo(x, y - L);
                cr.lineTo(x, y + L);
                cr.stroke();
            }
        }
        if (fx.shoot) {  // ara ara kayan yıldız
            const P = 7, k = Math.floor(t / P), p = t - k * P;
            if (p < 1 && sahneRnd(k, 7) > 0.3) {
                const hx = sahneRnd(k, 8) * w * 0.6 + p * w * 0.4, hy = h * 0.15 * sahneRnd(k, 9) + p * w * 0.14;
                const L = 18 * sc;
                const g = new Cairo.LinearGradient(hx - L, hy - L * 0.35, hx, hy);
                g.addColorStopRGBA(0, rgb[0], rgb[1], rgb[2], 0);
                g.addColorStopRGBA(1, rgb[0], rgb[1], rgb[2], a * (1 - p));
                cr.setSource(g);
                cr.setLineWidth(1.2 * sc);
                cr.moveTo(hx - L, hy - L * 0.35);
                cr.lineTo(hx, hy);
                cr.stroke();
            }
        }
        break;
    }
    case 'snow':
        for (let i = 0; i < n; i++) {
            const r = s * (0.5 + 0.6 * sahneRnd(i, 1));
            const span = h + 4 * r;
            const y = sahneWrap(sahneRnd(i, 3) * span + t * v * (0.6 + 0.8 * sahneRnd(i, 2)), span) - 2 * r;
            const x = sahneRnd(i, 4) * w + Math.sin(t * 0.9 * (0.5 + sahneRnd(i, 5)) + i) * s * 2;
            sahneBlob(cr, x, y, r * 1.6, r * 1.6, rgb, a);
        }
        break;
    case 'petals':
        for (let i = 0; i < n; i++) {
            const r = s * (0.6 + 0.6 * sahneRnd(i, 1));
            const vi = v * (0.5 + 0.7 * sahneRnd(i, 2));
            const spanY = h + 4 * r, spanX = w + 4 * r;
            const y = sahneWrap(sahneRnd(i, 3) * spanY + t * vi, spanY) - 2 * r;
            const x = sahneWrap(sahneRnd(i, 4) * spanX + t * vi * 0.6 + Math.sin(t * 1.3 + i) * s * 1.5, spanX) - 2 * r;
            cr.save();
            cr.translate(x, y);
            cr.rotate(t * (0.8 + sahneRnd(i, 5)) * (sahneRnd(i, 6) > 0.5 ? 1 : -1) + i);
            cr.scale(1, 0.5 + 0.25 * Math.sin(t * 2 + i));
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a);
            cr.arc(0, 0, r, 0, SAHNE_TAU);
            cr.fill();
            cr.restore();
        }
        break;
    case 'bubbles':
        for (let i = 0; i < n; i++) {
            const r = s * (0.5 + 0.7 * sahneRnd(i, 1));
            const span = h + 4 * r;
            const y = h + 2 * r - sahneWrap(sahneRnd(i, 3) * span + t * v * (0.6 + 0.8 * sahneRnd(i, 2)), span);
            const x = sahneRnd(i, 4) * w + Math.sin(t * 1.4 * (0.6 + sahneRnd(i, 5)) + i * 1.3) * s;
            cr.setLineWidth(Math.max(0.6 * sc, r * 0.18));
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a);
            cr.arc(x, y, r, 0, SAHNE_TAU);
            cr.stroke();
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a * 0.9);
            cr.arc(x - r * 0.35, y - r * 0.35, r * 0.22, 0, SAHNE_TAU);
            cr.fill();
        }
        break;
    case 'hearts':
        for (let i = 0; i < n; i++) {
            const r = s * (0.6 + 0.6 * sahneRnd(i, 1));
            const span = h + 4 * r;
            const y = h + 2 * r - sahneWrap(sahneRnd(i, 3) * span + t * v * (0.6 + 0.8 * sahneRnd(i, 2)), span);
            const x = sahneRnd(i, 4) * w + Math.sin(t * 1.2 * (0.6 + sahneRnd(i, 5)) + i * 1.3) * s;
            const fade = Math.max(0, Math.min(1, y / (h * 0.5) + 0.2));  // yukarı çıktıkça solar
            sahneHeart(cr, x, y, r);
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a * fade);
            cr.fill();
        }
        break;
    case 'fireflies':
        for (let i = 0; i < n; i++) {
            const p = 0.5 + 0.5 * Math.sin(t * (1.5 + 1.5 * sahneRnd(i, 1)) + i * 2.3);
            const x = w * (0.5 + 0.46 * Math.sin(t * v * 0.01 * (0.5 + sahneRnd(i, 2)) + sahneRnd(i, 3) * SAHNE_TAU));
            const y = h * (0.5 + 0.38 * Math.sin(t * v * 0.013 * (0.5 + sahneRnd(i, 4)) + sahneRnd(i, 5) * SAHNE_TAU));
            const g = s * (1.6 + 1.4 * p);
            sahneBlob(cr, x, y, g, g, rgb, a * 0.5 * p);
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a * (0.4 + 0.6 * p));
            cr.arc(x, y, s * 0.45, 0, SAHNE_TAU);
            cr.fill();
        }
        break;
    case 'aurora': {
        cr.setLineCap(Cairo.LineCap.ROUND);
        const step = Math.max(2, 4 * sc);
        const hh = Math.min(h, 48 * sc);  // büyük adada da üst şeritte kalır (yazıların üstünden geçmesin)
        for (let i = 0; i < n; i++) {
            const base = hh * (0.3 + 0.35 * sahneRnd(i, 1));
            const amp = hh * 0.2, f = 1.2 + 1.2 * sahneRnd(i, 2);
            const ph = t * v * 0.03 * (0.6 + 0.8 * sahneRnd(i, 3)) + i * 2;
            for (const [lw, k] of [[1.0, 0.22], [0.5, 0.4], [0.18, 0.85]]) {
                for (let x = 0; x <= w + step; x += step) {
                    const u = x / w * Math.PI * f;
                    const y = base + amp * Math.sin(u + ph) + amp * 0.4 * Math.sin(u * 2.3 - ph * 1.3);
                    if (x === 0)
                        cr.moveTo(x, y);
                    else
                        cr.lineTo(x, y);
                }
                const g = new Cairo.LinearGradient(0, 0, w, 0);
                g.addColorStopRGBA(0, rgb[0], rgb[1], rgb[2], a * k);
                g.addColorStopRGBA(0.5, rgb2[0], rgb2[1], rgb2[2], a * k);
                g.addColorStopRGBA(1, rgb[0], rgb[1], rgb[2], a * k);
                cr.setSource(g);
                cr.setLineWidth(s * lw);
                cr.stroke();
            }
        }
        break;
    }
    case 'rain':
        cr.setLineCap(Cairo.LineCap.ROUND);
        cr.setLineWidth(Math.max(0.6, 0.8 * sc));
        for (let i = 0; i < n; i++) {
            const L = s * (1.5 + 1.5 * sahneRnd(i, 1));
            const span = h + 2 * L;
            const y = sahneWrap(sahneRnd(i, 3) * span + t * v * (0.8 + 0.4 * sahneRnd(i, 2)), span) - L;
            const x = sahneRnd(i, 4) * (w + h * 0.3) - y * 0.25;
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a * (0.5 + 0.5 * sahneRnd(i, 5)));
            cr.moveTo(x, y);
            cr.lineTo(x - L * 0.25, y + L);
            cr.stroke();
        }
        break;
    case 'neon': {  // yanlarda ve altta parlayan çizgi; ara ara kısa bir titreme
        let pulse = 0.65 + 0.35 * Math.sin(t * (fx.speed || 10) * 0.15);
        if (sahneRnd(Math.floor(t * 8), 9) > 0.97)
            pulse *= 0.4;
        for (const [lw, k] of [[6, 0.15], [3, 0.35], [1.2, 0.95]]) {
            const d = lw * sc / 2, r = Math.max(0, Math.min(R, h / 2) - d);
            cr.moveTo(d, 0);
            cr.lineTo(d, h - d - r);
            cr.arcNegative(d + r, h - d - r, r, Math.PI, Math.PI / 2);
            cr.lineTo(w - d - r, h - d);
            cr.arcNegative(w - d - r, h - d - r, r, Math.PI / 2, 0);
            cr.lineTo(w - d, 0);
            cr.setLineWidth(lw * sc);
            cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a * k * pulse);
            cr.stroke();
        }
        break;
    }
    case 'glint': {  // birkaç saniyede bir çapraz parıltı geçer (speed: kaç saniyede bir)
        const P = Math.max(2, fx.speed || 5), p = sahneWrap(t, P) / 1.4;
        if (p < 1) {
            const x = -w * 0.3 + p * w * 1.6, bw = w * 0.18;
            const g = new Cairo.LinearGradient(x - bw, 0, x + bw, h * 0.6);
            g.addColorStopRGBA(0, rgb[0], rgb[1], rgb[2], 0);
            g.addColorStopRGBA(0.5, rgb[0], rgb[1], rgb[2], a);
            g.addColorStopRGBA(1, rgb[0], rgb[1], rgb[2], 0);
            cr.setSource(g);
            cr.rectangle(0, 0, w, h);
            cr.fill();
        }
        break;
    }
    case 'lightning': {  // speed: kaç saniyede bir (her seferinde değil); iki kısa çakma
        const P = Math.max(3, fx.speed || 9), k = Math.floor(t / P), p = t - k * P;
        if (sahneRnd(k, 3) > 0.35) {
            let f = 0;
            if (p < 0.08)
                f = 1 - p / 0.08;
            else if (p >= 0.18 && p < 0.26)
                f = 0.7 * (1 - (p - 0.18) / 0.08);
            if (f > 0) {
                cr.setSourceRGBA(rgb[0], rgb[1], rgb[2], a * f);
                cr.paint();
            }
        }
        break;
    }
    }
}

// Bütün süsler, adanın biçimine kırpılmış. opt: {scale, alpha, radius}.
function sahnePaint(cr, w, h, t, fxList, opt) {
    const sc = opt.scale || 1;
    const A = opt.alpha === undefined ? 1 : opt.alpha;
    if (!fxList || !fxList.length || A <= 0)
        return;
    const R = opt.radius === undefined ? 18 * sc : opt.radius;
    cr.save();
    sahneShape(cr, w, h, R);
    cr.clip();
    for (const fx of fxList)
        sahneFx(cr, w, h, t, fx, sc, A, R);
    cr.restore();
}
