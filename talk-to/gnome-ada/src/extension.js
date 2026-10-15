// Talk To · Üst ada: ekranın üst ortasında, üst çubuktan aşağı sarkan küçük bir "ada".
//
// Hep küçük durur (çalan şarkı, dalga); arama, şarkı değişimi ya da bildirim olunca büyür. Basılı tutup yana
// sürükleyince sayfa değişir: arama ← çalan → bildirimler → zamanlayıcı. Yukarı kaydırınca (tekerlek, dokunmatik
// yüzey ya da yukarı sürükleme) bir kademe küçülür: büyük → normal → ince şerit. İnce şeridin üstüne gelince normal
// hâli görünür, tıklayınca normale döner. İnce şeritteyken yalnızca arama adayı büyütür. Veriyi Talk To'dan D-Bus ile
// alır (lab.crucible.TalkToAndroid, /lab/crucible/TalkToAndroid/Ada): bu eklenti yalnızca gösterir ve düğmeleri
// Talk To'ya iletir; telefonla kendisi konuşmaz. Talk To kapalıyken görünmez.
//
// Dalga gerçek sesten gelmez (telefon ses verisi göndermiyor): çalarken akan dalga, duraklayınca durgun su.
//
// Bu dosya GNOME 45+ biçiminde (ES modülleri) yazılır; build.py GNOME 42–44 sürümünü (imports.*) üretir.
// IMPORTS-BASLA
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import Cairo from 'cairo';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
// IMPORTS-BITTI

const BUS_NAME = 'lab.crucible.TalkToAndroid';
const OBJECT_PATH = '/lab/crucible/TalkToAndroid/Ada';
const IFACE = `<node><interface name="lab.crucible.TalkToAndroid.Ada">
  <method name="GetState"><arg type="s" direction="out"/></method>
  <method name="Action"><arg type="s" direction="in"/></method>
  <signal name="Changed"><arg type="s"/></signal>
</interface></node>`;
const AdaProxy = Gio.DBusProxy.makeProxyWrapper(IFACE);

const DRAG_PAGE = 40;      // bu kadar piksel yana çekince sayfa değişir
const DRAG_UP = 24;        // bu kadar yukarı çekince küçülür
const SPILL_PAD = 12;      // yan akıntı için adanın iki yanında bırakılan yer
const SPILL_H = 22;      // alt çizgideki dalgalı şeridin en çok yüksekliği (aşağı sarkmaz)
const SCROLL_COOLDOWN_MS = 350; // dokunmatik yüzeyin tek kaydırması birden çok kademe atlamasın
const PEEK_LEAVE_MS = 450;      // ince şeritten fare ayrılınca normal hâlin kalma süresi
const SHOW_EVENT_MS = 5000; // şarkı/bildirim olunca büyük kalma süresi
const BATTERY_EVENT_MS = 10000; // telefonun pili azalınca büyük kalma süresi
const IDLE_COLLAPSE_MS = 6000;
// Canlandırma saati: dalga ve süsler aynı karede çizilir. Kare sayısı neye gerekiyorsa o kadar: dalga 15, hızlı
// düşen süsler (kar, yağmur, yaprak...) 15, ağır süzülenler (sis, bulut, yıldız, deniz...) 6–10. "Yavaş"ta yarısı.
// Eski ekran kartlarında kabuk her karede bütün ekranı yeniden çizebiliyor: maliyeti kare sayısı belirler
// (kullanıcının makinesinde müzik + Kuzey ışıkları %15–33 ölçüldü).
const WAVE_FPS = 15;
const SWATCH_FPS = 10;
const FX_FPS = {clouds: 8, fog: 6, stars: 8, aurora: 10, fireflies: 10, neon: 8, glint: 12, lightning: 12,
    snow: 15, petals: 15, bubbles: 15, hearts: 15, rain: 15, sea: 4, prism: 10, shards: 10};
const LIVE_MS = 8000; // "Olaylarda": şarkı değişince, üstüne gelince, büyüyünce bu kadar canlanır
const IDLE_PAUSE_S = 60; // kullanıcı bu kadar dokunmazsa (fare, klavye) canlandırma durur; dokununca sürer
const DEFAULT_THEME = {bg1: '#0a2342', bg2: '#12436b', wave1: '#2ec4b6', wave2: '#8de4ff', text: '#eaf6ff',
    dim: '#9cc3dd', accent: '#2ec4b6'};

function rgba(hex, alpha) {
    const h = (hex || '#000000').replace('#', '');
    const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255, alpha];
}

// Aramadaki aç/kapa düğmeleri (hoparlör, sessiz): yazı yerine simge. Düğmenin yazısı yapılacak işi söyler
// ("Hoparlörü kapat" = şu an açık); durum anlaşılmazsa kapalı sayılır.
function callToggle(title) {
    const t = (title || '').toLocaleLowerCase('tr');
    if (/hoparl|speaker/.test(t))
        return {icon: 'audio-speakers-symbolic', on: /kapat|off|devre dışı/.test(t)};
    if (/sessiz|mute|mikrofon|microphone/.test(t)) {
        const muted = /unmute|sesi aç|sessizden|sessizliği kaldır|mikrofonu aç/.test(t);
        return {icon: muted ? 'microphone-sensitivity-muted-symbolic' : 'audio-input-microphone-symbolic', on: muted};
    }
    return null;
}

// Olayın geldiği öğe: GNOME 45+ sahneye sorar, 42–44 olayın kendisine.
function eventActor(event) {
    try {
        if (global.stage.get_event_actor)
            return global.stage.get_event_actor(event);
    } catch (e) {
        // eski kabuk
    }
    return event.get_source ? event.get_source() : null;
}

// Bildirim ne zaman geldi: "şimdi", "3 dk önce", "2 sa önce", "1 gün önce".
function ago(t) {
    const sec = Math.max(0, Date.now() / 1000 - (t || 0));
    if (sec < 60)
        return 'şimdi';
    if (sec < 3600)
        return `${Math.floor(sec / 60)} dk önce`;
    if (sec < 86400)
        return `${Math.floor(sec / 3600)} sa önce`;
    return `${Math.floor(sec / 86400)} gün önce`;
}

function mmss(sec) {
    sec = Math.max(0, Math.round(sec));
    const h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60, s = sec % 60;
    const pad = v => String(v).padStart(2, '0');
    return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

// "Taşan dalgalar" kipi: adanın altından taşan su. Çalarken çalkalanır, ara ara damlar; gerçek sesten gelmez
// (telefon ses verisi göndermiyor), süstür. Fareyi engellemez (girdi bölgesine katılmaz).
class Spill {
    constructor(ada) {
        this.ada = ada;
        this.actor = new St.DrawingArea({reactive: false, visible: false, style_class: 'ada-tasan'});
        this.actor.connect('repaint', area => this._paint(area));
    }

    // Su adanın üst kenarından taşar, iki yanından aşağı akar, alt köşeleri sarıp adanın alt çizgisinde
    // dalgalı bir şeride dönüşür. Adanın genişliğini aşmaz, aşağı sarkmaz (dikkat dağıtmasın).
    // Çizim adanın üstüne değil çevresine yapılır; tıklamaları almaz.
    _paint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        const t = Date.now() / 1000;
        const th = this.ada.theme;
        const energy = Math.max(0, Math.min(1, (this.ada.amp - 0.05) / 0.17));
        // Süs "vurgu": birkaç yavaş sinüsün bileşimi; çalarken çalkalanır, duraklayınca durulur.
        const beat = 0.55 + 0.45 * Math.pow(Math.abs(Math.sin(t * 2.3)), 3) * (0.6 + 0.4 * Math.sin(t * 0.7));
        const pad = SPILL_PAD;
        const left = pad, right = w - pad;
        const bh = Math.max(6, Math.min(h - 6, this.bh || 30));  // adanın yüksekliği (bu çizimde)
        const [r1, g1, b1] = rgba(th.wave1, 1);
        const [r2, g2, b2] = rgba(th.wave2, 1);
        const sw = 1.5 + 3 * energy * beat;  // yan akıntının kalınlığı
        // Adanın alt köşeleri yuvarlak: su köşeyi sarıp alt çizgiye iner.
        const R = Math.min(18, bh / 2);
        const hug = y => y <= bh - R ? 0 : R - Math.sqrt(Math.max(0, R * R - Math.pow(y - (bh - R), 2)));

        // 1) Yanlardan inen su: üstte ince, aşağı indikçe kalınlaşır, köşeyi sarar.
        for (const side of [-1, 1]) {
            const x0 = side < 0 ? left : right;
            const ys = [];
            for (let y = 0; y < bh; y += 2)
                ys.push(y);
            ys.push(bh);
            cr.moveTo(x0, 0);
            for (const y of ys) {
                const wob = Math.sin(y / 6 + t * 7 + side) * (0.3 + 0.6 * energy);
                const k = y > bh - R ? (bh - y) / R : 1;  // köşede alt çizgiye yatar
                cr.lineTo(x0 + side * (Math.max(0.5, (sw * (0.45 + 0.55 * y / bh) + wob) * k) - hug(y)),
                    y + (1 - k) * sw * 0.8);
            }
            for (const y of ys.reverse())
                cr.lineTo(x0 - side * hug(y), y);
            cr.closePath();
            // Yumuşak akıntı (kalem çizgisi gibi sert kenar yok): yukarıda belirir, aşağı indikçe dolgunlaşır;
            // asıl suyun çevresinde geniş ve çok saydam bir hâle.
            const g = new Cairo.LinearGradient(0, 0, 0, bh);
            g.addColorStopRGBA(0, r1, g1, b1, 0);
            g.addColorStopRGBA(0.35, r1, g1, b1, 0.25);
            g.addColorStopRGBA(1, r2, g2, b2, 0.5);
            cr.setSource(g);
            cr.fillPreserve();
            const halo = new Cairo.LinearGradient(0, 0, 0, bh);
            halo.addColorStopRGBA(0, r2, g2, b2, 0);
            halo.addColorStopRGBA(1, r2, g2, b2, 0.12);
            cr.setSource(halo);
            cr.setLineWidth(3);
            cr.setLineJoin(Cairo.LineJoin.ROUND);
            cr.stroke();
        }

        // 2) Alt çizgi: köşeden köşeye dalgalı şerit (köşelerde yan akıntılarla birleşir, ortası biraz kabarık).
        const base = bh - 2;
        const room = h - base;
        const x1 = left + R * 0.5, x2 = right - R * 0.5;
        const prof = x => {
            const u = (x - x1) / Math.max(1, x2 - x1);
            const ends = Math.min(1, Math.min(x - x1, x2 - x) / 6);  // uçlarda yumuşak biter
            return ends * (0.45 + 0.55 * Math.pow(Math.sin(Math.PI * u), 1.5));
        };
        const layers = [[th.wave2, 0.5, 1.0, 0.0, 1.0], [th.wave1, 0.85, 1.5, 1.9, 0.7]];
        for (const [color, alpha, speed, shift, scale] of layers) {
            const max = room * scale * (0.25 + 0.6 * energy * beat);
            cr.moveTo(x1, base);
            for (let x = x1; x <= x2; x += 3) {
                const ripple = 0.7 + 0.3 * Math.sin(x / w * Math.PI * 8 + t * 3 * speed + shift);
                cr.lineTo(x, base + max * prof(x) * ripple);
            }
            cr.lineTo(x2, base);
            cr.closePath();
            const g = new Cairo.LinearGradient(0, base, 0, base + Math.max(1, max));
            const [r, gg, b] = rgba(color, 1);
            g.addColorStopRGBA(0, r, gg, b, alpha);
            g.addColorStopRGBA(1, r, gg, b, alpha * 0.35);
            cr.setSource(g);
            cr.fill();
        }
        cr.$dispose();
    }

    repaint() {
        this.actor.queue_repaint();
    }
}

// SAHNE: build.py buraya src/sahne.js'i koyar (temaların süsleri: sahnePaint).

// Adanın zemini: renk geçişi ve (temada varsa) süsler (bulut, sis, yıldız...) adanın tam altındaki bu katmanda
// çizilir, ada saydamdır; su ve yazılar üstünde net kalır. Tıklamaları almaz. Süsler büyükken soluklaşır, aramada
// ve ince şeritte çekilir (zemin kalır).
class Sky {
    constructor(ada) {
        this.ada = ada;
        this.radius = 18;
        this.actor = new St.DrawingArea({reactive: false, visible: false, style_class: 'ada-gok'});
        this.actor.connect('repaint', area => this._paint(area));
    }

    _paint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        sahneBackground(cr, w, h, this.ada.theme, this.radius);
        if (this.ada.skyOn) {
            const fx = this.ada.theme.fx || [], A = this.ada.skyAlpha();
            if (this.ada.scene.ready)  // kıpırdayanlar kendi katmanlarında (Scene)
                sceneBack(cr, w, h, fx, this.radius, A);
            else
                sahnePaint(cr, w, h, this.ada.fxTime(), fx, {radius: this.radius, alpha: A});
        }
        cr.$dispose();
    }

    repaint() {
        this.actor.queue_repaint();
    }
}

// Adanın alt kenarı su (normal hâlde ve ince şeritte): çalarken dalgalanır, çalmazken sakin bir çizgi. Ayrı bir
// kutu değil; adanın biçimine (yuvarlak alt köşeler) göre kırpılır, zeminle yazıların arasında durur.
class Water {
    constructor(ada) {
        this.ada = ada;
        this.bh = 29;  // adanın o anki yüksekliği (şerit adanın altına yaslı)
        this.actor = new St.DrawingArea({reactive: false, visible: false, style_class: 'ada-su'});
        this.actor.connect('repaint', area => this._paint(area));
    }

    _paint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        const ada = this.ada, t = ada.theme;
        // Adanın biçimi, bu şeridin yerine göre kaydırılmış: su köşelerden taşmaz.
        cr.save();
        cr.translate(0, h - this.bh);
        sahneShape(cr, w, this.bh, ada.sky.radius || 18);
        cr.restore();
        cr.clip();
        const thin = ada.thin && !ada.peek && !ada.expanded;
        const base = thin ? h * 0.3 : h * 0.6;  // su seviyesi
        const amp = (thin ? h * 0.6 : h * 1.6) * ada.amp;  // çalarken yüksek, çalmazken neredeyse düz
        for (const [color, alpha, speed, shift] of [[t.wave2, 0.45, 1.0, 0.0], [t.wave1, 0.8, 1.6, 1.7]]) {
            cr.moveTo(0, h);
            for (let x = 0; x <= w + 3; x += 3) {
                cr.lineTo(x, base + amp * (Math.sin(x / 22 + ada.phase * speed + shift) +
                    0.35 * Math.sin(x / 9.5 - ada.phase * speed * 1.3)));
            }
            cr.lineTo(w, h);
            cr.closePath();
            cr.setSourceRGBA(...rgba(color, alpha));
            cr.fill();
        }
        if (ada.loading) {  // şarkılar arası: suyun üstünde kayan parıltı ("yükleniyor")
            const span = w * 0.35;
            const x = ((Date.now() / 1100) % 1.6 - 0.3) * w;
            const g = new Cairo.LinearGradient(x - span / 2, 0, x + span / 2, 0);
            g.addColorStopRGBA(0, 1, 1, 1, 0);
            g.addColorStopRGBA(0.5, 1, 1, 1, 0.45);
            g.addColorStopRGBA(1, 1, 1, 1, 0);
            cr.rectangle(0, 0, w, h);
            cr.setSource(g);
            cr.fill();
        }
        cr.$dispose();
    }

    repaint() {
        this.actor.queue_repaint();
    }
}

// Katmanlı sahne (Deniz, Prizma): ağır çizim bir kez yapılır (Deniz'de gök cismi ve deniz zeminde, Sky); kıpırdayan
// parçalar (dalga sıraları, pırıltılar, yıldızlar, martılar; Prizma'da renk geçişleri, ışık demetleri, kristaller,
// parıltı) ayrı küçük katmanlardır. Her karede yeniden çizilmezler: ekran kartı yerlerini, saydamlıklarını, açılarını
// değiştirir; kabuğa düşen iş birkaç sayı. Dalgayla aynı karede, saniyede 15 kare (eskiden Deniz 4, büyükken 2 kare
// çiziliyordu: takılıyor, duruyor gibi görünüyordu).
// Dokununca (temanın "touch" alanı): Deniz'de suda halkalar, Prizma'da ışık patlaması.
const SCENE_FPS = 15;
const SCENE_IDLE_FPS = 10;  // bir şey çalmazken (dalga durgun) sahne daha seyrek
const SCENE_TYPES = ['sea', 'prism', 'shards', 'glint'];
const SCENE_ALPHA_BIG = 0.85;  // büyük adada manzara az soluk (öteki temaların süsleri 0.55)

function sceneTheme(theme) {  // bütün süsleri katman olarak çizilebiliyor mu
    const fx = (theme && theme.fx) || [];
    return fx.length > 0 && fx.every(f => SCENE_TYPES.includes(f.type));
}

// Sahnenin zemine (Sky) bir kez çizilen kısmı.
function sceneBack(cr, w, h, fxList, R, A) {
    cr.save();
    sahneShape(cr, w, h, R);
    cr.clip();
    for (const fx of fxList) {
        if (fx.type === 'sea') {
            const g = sahneSeaGeo(w, h, fx, 1);
            sahneSeaBody(cr, h, g, A);
            sahneSeaWater(cr, w, h, g, fx, 1, A);
        }
    }
    cr.restore();
}

// Bir kez çizilen katman (Cairo); boyutu değişmedikçe yeniden çizilmez.
function sceneLayer(parent, x, y, w, h, paint, cls) {
    const a = new St.DrawingArea({x: Math.round(x), y: Math.round(y), width: Math.max(1, Math.ceil(w)),
        height: Math.max(1, Math.ceil(h)), reactive: false});
    if (cls)
        a.add_style_class_name(cls);
    a.connect('repaint', area => {
        const cr = area.get_context();
        paint(cr);
        cr.$dispose();
    });
    parent.add_child(a);
    return a;
}

// Alt kenarı yuvarlaktan yumuşakça silinen katman (yalnızca yana kayanlar için: köşelerden taşmasın).
function sceneFadeBottom(cr, h, R, draw) {
    cr.pushGroup();
    draw();
    cr.popGroupToSource();
    const m = new Cairo.LinearGradient(0, h - R, 0, h);
    m.addColorStopRGBA(0, 0, 0, 0, 1);
    m.addColorStopRGBA(0.6, 0, 0, 0, 0.15);
    m.addColorStopRGBA(1, 0, 0, 0, 0);
    cr.mask(m);
}

class Scene {
    constructor(ada) {
        this.ada = ada;
        this.actor = new St.Widget({reactive: false, visible: false, clip_to_allocation: true,
            style_class: 'ada-sahne'});
        this.parts = new St.Widget();    // kıpırdayan katmanlar
        this.touches = new St.Widget();  // dokunma izleri
        this.actor.add_child(this.parts);
        this.actor.add_child(this.touches);
        this.steps = [];
        this.effects = [];   // süren dokunma izleri
        this.key = '';
        this.on = false;     // tema katmanlı ve ada süslü hâlde
        this.ready = false;  // katmanlar kuruldu (kurulana dek zemin bütün resmi çizer)
    }

    destroy() {
        this.ada._cancel('scene');
        if (this._fxTimer)
            GLib.source_remove(this._fxTimer);
        this._fxTimer = 0;
        this.actor.destroy();
    }

    // Tema ya da boyut değişti: katmanları yeniden kur. Ada büyüyüp küçülürken boyut her karede değişir: durulunca
    // kurulur (o arada zemin bütün resmi çizer).
    update() {
        const ada = this.ada;
        const w = Math.round(this.actor.width), h = Math.round(this.actor.height);
        this.on = !!ada.skyOn && sceneTheme(ada.theme);
        const key = this.on ? JSON.stringify([ada.theme.fx, w, h, ada.sky.radius, ada.skyAlpha()]) : '';
        if (key === this.key)
            return;
        this.key = key;
        const was = this.ready;
        this.ready = false;
        this.steps = [];
        this.parts.destroy_all_children();
        ada._cancel('scene');
        if (was)
            ada.sky.repaint();
        if (!this.on || w < 8 || h < 8)
            return;
        ada._timers.scene = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 180, () => {
            delete ada._timers.scene;
            this._build(w, h);
            return GLib.SOURCE_REMOVE;
        });
    }

    _build(w, h) {
        const ada = this.ada;
        const R = Math.max(0, Math.min(ada.sky.radius || 18, h / 2, w / 2));
        const A = ada.skyAlpha();
        this.parts.set_size(w, h);
        this.touches.set_size(w, h);
        this.hz = 0;
        for (const fx of ada.theme.fx || []) {
            if (fx.type === 'sea')
                this._sea(w, h, R, fx, A);
            else if (fx.type === 'prism')
                this._prism(w, h, R, fx, A);
            else if (fx.type === 'shards')
                this._shards(w, h, R, fx, A);
            else if (fx.type === 'glint')
                this._glint(w, h, R, fx, A);
        }
        this.ready = true;
        this.step(ada.fxTime());
        ada.sky.repaint();  // zemin artık yalnızca kıpırdamayan kısmı çizer
        log(`Talk To ada: sahne kuruldu (${(ada.theme.fx || []).map(f => f.type).join(', ')}; ` +
            `${this.parts.get_n_children()} katman, ${w}×${h})`);
        ada._anim();
    }

    step(t) {
        if (!this.ready)
            return;
        for (const f of this.steps)
            f(t);
    }

    _layer(x, y, w, h, paint, parent = this.parts) {
        return sceneLayer(parent, x, y, w, h, paint);
    }

    // Alt köşeler yuvarlak: y yüksekliğinde kenardan ne kadar içeride kalınmalı.
    _inset(y, h, R) {
        const d = y - (h - R);
        return d <= 0 ? 0 : R - Math.sqrt(Math.max(0, R * R - d * d));
    }

    _sea(w, h, R, fx, A) {
        const g = sahneSeaGeo(w, h, fx, 1);
        this.hz = g.hz;
        // Yıldızlar (gece): üç küme ayrı ayrı yanıp söner; ayın/güneşin üstüne düşenler yok
        if (g.night > 0) {
            for (let k = 0; k < 3; k++) {
                const a = this._layer(0, 0, w, g.hz + 2, cr => {
                    for (let i = k; i < g.stars; i += 3) {
                        const dx = sahneRnd(i, 11) * w - g.bx, dy = sahneRnd(i, 12) * g.hz * 0.92 - g.by;
                        if (Math.hypot(dx, dy) > g.br * 1.4)
                            sahneSeaStar(cr, w, g, i, 1, A, 1);
                    }
                });
                this.steps.push(t => {
                    a.opacity = Math.round(255 * (0.25 + 0.55 * sahneSeaStarTw(k * 5 + 2, t)) / 0.8);
                });
            }
        }
        // Martılar (gündüz, büyük adada): uçar, kanat çırpar
        if (g.day && h >= 60) {
            for (let i = 0; i < 2; i++) {
                const s = Math.ceil(2 * (4 + 1.5 * i) + 6);
                const a = this._layer(0, 0, s, s, cr => sahneSeaGull(cr, s / 2, s / 2, i, 0.45, 1, A));
                a.set_pivot_point(0.5, 0.5);
                this.steps.push(t => {
                    const [gx, gy, flap] = sahneSeaGullAt(w, g, i, t, 1);
                    a.translation_x = gx - s / 2;
                    a.translation_y = gy - s / 2;
                    a.scale_y = flap / 0.45;
                });
            }
        }
        // Dalga sıraları: her biri kendi hızında kayar (yakındakiler hızlı, ufuktakiler ağır: derinlik)
        for (let j = 1; j <= g.rows; j++) {
            const r = sahneSeaRowGeo(h, g, j, 1);
            const top = Math.floor(r.y0 - r.amp - r.lw - 1), bot = Math.ceil(r.y0 + r.amp + r.lw + 1);
            const ins = Math.ceil(this._inset(bot, h, R));
            const W = w - 2 * ins, L = r.len;
            if (W < 4 || bot - top < 2)
                continue;
            const box = new St.Widget({x: ins, y: top, width: W, height: bot - top, clip_to_allocation: true});
            this.parts.add_child(box);
            const tex = this._layer(0, 0, W + L + 6, bot - top, cr => {
                cr.translate(-ins, -top);
                sahneSeaRow(cr, r, ins, ins + W + L + 6, j * 1.7, A);
            }, box);
            this.steps.push(t => {
                tex.translation_x = -sahneWrap(t * r.speed * L / SAHNE_TAU, L);
            });
        }
        // Yansıma yolu: dört küme ayrı ayrı yanıp söner, hafifçe yana salınır
        if (g.up > 0) {
            const half = g.br * 2.8 * 1.15 + 3;
            const x0 = Math.max(0, Math.floor(g.bx - half)), x1 = Math.min(w, Math.ceil(g.bx + half));
            const y0 = Math.max(0, Math.floor(g.hz - 2));
            for (let k = 0; k < 4; k++) {
                const a = this._layer(x0, y0, x1 - x0, h - y0, cr => {
                    cr.translate(-x0, -y0);
                    sahneShape(cr, w, h, R);
                    cr.clip();
                    for (let i = 0; i < g.glints; i++) {
                        for (let j = 0, n = sahneSeaGlintCount(g, i); j < n; j++) {
                            if ((i * 3 + j) % 4 === k)
                                sahneSeaGlint(cr, h, g, i, j, 0, 1, 1, A);
                        }
                    }
                });
                this.steps.push(t => {
                    a.opacity = Math.round(255 * (0.35 + 0.65 * Math.max(0, Math.sin(t * (1.4 + 0.45 * k) + k * 1.9))));
                    a.translation_x = Math.sin(t * (0.6 + 0.25 * k) + k) * g.br * 0.12;
                });
            }
        }
    }

    _prism(w, h, R, fx, A) {
        const a = (fx.alpha === undefined ? 0.35 : fx.alpha) * A;
        const K = 6, deg = 12 * (fx.speed || 10) / 10;  // renkler saniyede kaç derece döner
        // Renk geçişleri: altı hazır resim sırayla birbirine karışır (renkler akıyor gibi)
        const frames = [];
        for (let k = 0; k < K; k++) {
            frames.push(this._layer(0, 0, w, h, cr => {
                sahneShape(cr, w, h, R);
                cr.clip();
                sahnePrismWash(cr, w, h, k * 360 / K, 0, a, false);
            }));
        }
        let top = -1;
        this.steps.push(t => {
            const q = sahneWrap(t * deg / (360 / K), K), i0 = Math.floor(q) % K, i1 = (i0 + 1) % K;
            if (top !== i1) {
                top = i1;
                this.parts.set_child_above_sibling(frames[i1], frames[i0]);
                frames.forEach((f, i) => {
                    f.visible = i === i0 || i === i1;
                });
            }
            frames[i0].opacity = 255;
            frames[i1].opacity = Math.round(255 * (q - Math.floor(q)));
        });
        // Işık demetleri: çapraz, ağır ağır kayar
        for (let i = 0; i < 3; i++) {
            const bw = sahnePrismBeamAt(w, i, 0, 1)[1], k = 0.45 * h, cx = k + bw + 2;
            const b = this._layer(0, 0, 2 * bw + k + 4, h, cr => {
                sceneFadeBottom(cr, h, R, () => sahnePrismBeam(cr, cx, bw, k, h, a));
            });
            this.steps.push(t => {
                b.translation_x = sahnePrismBeamAt(w, i, t, 1)[0] - cx;
            });
        }
    }

    _shards(w, h, R, fx, A) {
        const n = fx.count || 0, s = fx.size || 4, v = fx.speed || 10;
        const a = (fx.alpha === undefined ? 0.6 : fx.alpha) * A;
        for (let i = 0; i < n; i++) {
            const r = s * (0.7 + 0.8 * sahneRnd(i, 31)), z = Math.ceil(2 * r + 4);
            const lo = R + r + s, room = Math.max(0, w - 2 * lo);
            const x0 = lo + sahneRnd(i, 34) * room;  // yuvarlak köşelere değmesin
            const c = sahneHsl(i * 47 + 200, 0.8, 0.7);
            const d = this._layer(0, 0, z, z, cr => {
                cr.translate(z / 2, z / 2);
                sahneShard(cr, r, c, a, 1);
            });
            d.set_pivot_point(0.5, 0.5);
            const dir = sahneRnd(i, 36) > 0.5 ? 1 : -1, spin = 0.6 + sahneRnd(i, 35);
            this.steps.push(t => {
                const span = h + 4 * r;
                const y = h + 2 * r - sahneWrap(sahneRnd(i, 32) * span + t * v * (0.5 + 0.6 * sahneRnd(i, 33)), span);
                d.translation_x = x0 + Math.sin(t * 0.9 + i * 1.7) * s - z / 2;
                d.translation_y = y - z / 2;
                d.rotation_angle_z = (t * spin * dir + i) * 180 / Math.PI;
            });
        }
    }

    _glint(w, h, R, fx, A) {
        const P = Math.max(2, fx.speed || 5), bw = w * 0.18, rgb = sahneRgb(fx.color);
        const a = (fx.alpha === undefined ? 0.5 : fx.alpha) * A;
        const left = bw + 0.3 * h * h / bw + 1, W = 2 * bw + 0.48 * h * h / bw + 2;
        const gl = this._layer(0, 0, W, h, cr => {
            sceneFadeBottom(cr, h, R, () => sahneGlint(cr, W, h, left, bw, rgb, a));
        });
        this.steps.push(t => {
            const p = sahneWrap(t, P) / 1.4;
            gl.visible = p < 1;
            if (p < 1)
                gl.translation_x = -w * 0.3 + p * w * 1.6 - left;
        });
    }

    // ---- dokunma izi ----

    // x, y sahnenin içinde. Adanın biçiminden taşmaz: kenara ya da yuvarlak köşeye yakınsa küçülür.
    touch(x, y) {
        const kind = this.ada.theme.touch;
        if (!kind || !this.actor.visible || !this.on)
            return;
        const w = this.actor.width, h = this.actor.height;
        const R = Math.max(0, Math.min(this.ada.sky.radius || 18, h / 2, w / 2));
        let corner = Infinity;
        if (y > h - R && (x < R || x > w - R))
            corner = R - Math.hypot(x - (x < R ? R : w - R), y - (h - R));
        const room = {x: Math.min(x, w - x) - 1, y: h - y - 1, c: corner - 1};
        if (kind === 'ripple')
            this._ripple(x, y, room, h);
        else if (kind === 'burst')
            this._burst(x, y, room);
    }

    _spawn(x, y, s, paint) {
        const a = sceneLayer(this.touches, x - s / 2, y - s / 2, s, s, paint, 'ada-dokunma');
        a.set_pivot_point(0.5, 0.5);
        return a;
    }

    // İzin canlandırması kendi kısa saatiyle (saniyede 40 kare, iz bitince durur). GNOME'un ease'i yeni eklenen
    // katmanda kimi zaman hiç başlamıyordu: iz ya hemen siliniyor ya da yarıda kalıp ekranda asılı duruyordu.
    // step(u): u 0'dan 1'e; bitince katman silinir.
    _play(actor, ms, delay, step) {
        step(0);
        this.effects.push({actor, step, ms, t0: GLib.get_monotonic_time() / 1000 + delay});
        if (!this._fxTimer)
            this._fxTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 25, () => this._effectsTick());
    }

    _effectsTick() {
        const now = GLib.get_monotonic_time() / 1000;
        this.effects = this.effects.filter(e => {
            const u = Math.max(0, Math.min(1, (now - e.t0) / e.ms));
            e.step(u);
            if (u < 1)
                return true;
            e.actor.destroy();
            return false;
        });
        if (this.effects.length)
            return GLib.SOURCE_CONTINUE;
        this._fxTimer = 0;
        return GLib.SOURCE_REMOVE;
    }

    // Deniz: dokunulan yerde suda genişleyip sönen halkalar (gökte yuvarlak, suda yassı: perspektif)
    _ripple(x, y, room, h) {
        const flat = y > (this.hz || h * 0.38) ? 0.42 : 1;
        const rx = Math.min(34, room.x, room.y / flat, room.c);
        if (rx < 4)
            return;
        const ry = rx * flat, s = Math.ceil(2 * rx + 6);
        for (let k = 0; k < 3; k++) {
            const ring = this._spawn(x, y, s, cr => {
                cr.save();
                cr.translate(s / 2, s / 2);
                cr.scale(rx, ry);
                cr.arc(0, 0, 1, 0, SAHNE_TAU);
                cr.restore();
                cr.setLineWidth(2.2 - k * 0.4);
                cr.setSourceRGBA(1, 1, 1, 0.95 - k * 0.2);
                cr.strokePreserve();
                cr.setSourceRGBA(1, 1, 1, 0.07);  // halkanın içi hafifçe parlar
                cr.fill();
            });
            this._play(ring, 1100, k * 170, u => {
                const e = 1 - (1 - u) * (1 - u), sc = 0.12 + 0.88 * e;
                ring.set_scale(sc, sc);
                ring.opacity = Math.round(255 * (1 - u));
            });
        }
        const dot = this._spawn(x, y, 10, cr => {
            const g = new Cairo.RadialGradient(5, 5, 0, 5, 5, 5);
            g.addColorStopRGBA(0, 1, 1, 1, 0.9);
            g.addColorStopRGBA(1, 1, 1, 1, 0);
            cr.setSource(g);
            cr.paint();
        });
        this._play(dot, 380, 0, u => {
            dot.set_scale(1 + 0.6 * u, (1 + 0.6 * u) * flat);
            dot.opacity = Math.round(255 * (1 - u));
        });
    }

    // Prizma: dokunulan yerde dönerek açılan gökkuşağı halkalı ışık ve dört yana saçılan kristaller
    _burst(x, y, room) {
        const lim = Math.min(room.x, room.y, room.c);
        const F = Math.min(22, lim);
        if (F < 5)
            return;
        const s = Math.ceil(2 * F + 4);
        const flare = this._spawn(x, y, s, cr => {
            const c0 = s / 2;
            const core = new Cairo.RadialGradient(c0, c0, 0, c0, c0, F * 0.5);
            core.addColorStopRGBA(0, 1, 1, 1, 0.95);
            core.addColorStopRGBA(1, 1, 1, 1, 0);
            cr.setSource(core);
            cr.paint();
            cr.setLineWidth(F * 0.16);
            for (let i = 0; i < 6; i++) {
                const c = sahneHsl(i * 60, 0.9, 0.65);
                cr.setSourceRGBA(c[0], c[1], c[2], 0.75);
                cr.arc(c0, c0, F * 0.72, i * Math.PI / 3, (i + 1) * Math.PI / 3);
                cr.stroke();
            }
            cr.setLineWidth(1);
            cr.setSourceRGBA(1, 1, 1, 0.6);
            for (let i = 0; i < 4; i++) {
                const q = i * Math.PI / 2 + Math.PI / 4;
                cr.moveTo(c0 + Math.cos(q) * F * 0.15, c0 + Math.sin(q) * F * 0.15);
                cr.lineTo(c0 + Math.cos(q) * F, c0 + Math.sin(q) * F);
                cr.stroke();
            }
        });
        this._play(flare, 720, 0, u => {
            const e = 1 - Math.pow(1 - u, 3), sc = 0.2 + 0.8 * e;
            flare.set_scale(sc, sc);
            flare.rotation_angle_z = 70 * e;
            flare.opacity = Math.round(255 * (1 - u * u));
        });
        const D = Math.max(0, Math.min(30, lim - 4));
        for (let i = 0; i < 6; i++) {
            const q = (i * 60 + 20) * Math.PI / 180, c = sahneHsl(i * 60, 0.85, 0.7);
            const sp = this._spawn(x, y, 10, cr => {
                cr.translate(5, 5);
                sahneShard(cr, 3.4, c, 0.95, 1);
            });
            this._play(sp, 680, 0, u => {
                const e = 1 - (1 - u) * (1 - u);
                sp.translation_x = Math.cos(q) * D * e;
                sp.translation_y = Math.sin(q) * D * e;
                sp.rotation_angle_z = 200 * e;
                sp.opacity = Math.round(255 * (1 - u));
            });
        }
    }
}

// Deniz: iki katlı dalga; çalarken akar, duraklayınca neredeyse durgun.
class Wave {
    constructor(width, height, ada) {
        this.ada = ada;
        this.actor = new St.DrawingArea({width, height, style_class: 'ada-wave'});
        this.actor.connect('repaint', area => this._paint(area));
    }

    _paint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        const t = this.ada.theme;
        const amp = h * this.ada.amp;
  // çalarken 0.22, duraklayınca 0.05; arada yumuşak geçer
        const phase = this.ada.phase;
        const layers = [[t.wave2, 0.55, 1.0, 0.0], [t.wave1, 0.95, 1.6, 1.7]];
        for (const [color, alpha, speed, shift] of layers) {
            cr.moveTo(0, h);
            for (let x = 0; x <= w; x += 2) {
                const y = h * 0.52 + amp * Math.sin(x / w * Math.PI * 3 + phase * speed + shift) +
                    amp * 0.35 * Math.sin(x / w * Math.PI * 7 - phase * speed * 1.3);
                cr.lineTo(x, y);
            }
            cr.lineTo(w, h);
            cr.closePath();
            cr.setSourceRGBA(...rgba(color, alpha));
            cr.fill();
        }
        if (this.ada.loading) {  // şarkılar arası: suyun üstünde kayan hafif bir parıltı ("yükleniyor")
            const span = w * 0.35;
            const x = ((Date.now() / 1100) % 1.6 - 0.3) * w;  // ~1,1 sn'de bir geçer
            const g = new Cairo.LinearGradient(x - span / 2, 0, x + span / 2, 0);
            g.addColorStopRGBA(0, 1, 1, 1, 0);
            g.addColorStopRGBA(0.5, 1, 1, 1, 0.45);
            g.addColorStopRGBA(1, 1, 1, 1, 0);
            cr.rectangle(0, 0, w, h);
            cr.setSource(g);
            cr.fill();
        }
        cr.$dispose();
    }

    repaint() {
        this.actor.queue_repaint();
    }
}

class Ada {
    constructor() {
        this.state = null;
        this.theme = DEFAULT_THEME;
        this.playing = false;
        this.phase = 0;
        this.amp = 0.05;
        this.expanded = false;
        this.custom = false;  // "Diğer → Özelleştir": ada büyüyüp tema ve kip seçimini gösterir
        this.thin = false;   // ince şerit (yukarı kaydırıldı)
        this.peek = false;   // ince şeritteyken fare üstünde: normal hâl görünür
        this.moving = false; // "Konumu değiştir": kilit açık, ada üst kenar boyunca sağa-sola sürüklenir
        this.offset = 0;     // ortadan yana kaydırma (px); Talk To'da saklanır
        this._scrollAt = 0;
        this._scrollSum = 0;
        this.pageIndex = 0;
        this.pageName = 'calan';
        this.lastEvent = 0;
        this.waves = [];
        this.live = []; // [etiket, metni veren işlev]: her saniye güncellenir (sayaç, görüşme süresi)
        this.swatches = []; // Özelleştir'deki küçük tema önizlemeleri (süsleri canlı)
        this.waveOn = false;
        this.idle = false;   // kullanıcı bir süredir dokunmuyor: canlandırma durur
        this._animFps = 0;
        this._fx0 = GLib.get_monotonic_time() / 1e6;
        this._timers = {};

        this.box = new St.BoxLayout({style_class: 'ada', vertical: true, reactive: true, track_hover: true,
            visible: false, clip_to_allocation: true});
        this.box.set_pivot_point(0.5, 0);
        this.compact = new St.BoxLayout({style_class: 'ada-compact'});
        this.box.add_child(this.compact);
        this.page = new St.BoxLayout({style_class: 'ada-page', vertical: true, visible: false,
            clip_to_allocation: true});
        this.box.add_child(this.page);

        Main.layoutManager.addTopChrome(this.box, {affectsInputRegion: true, trackFullscreen: true});
        this.spill = new Spill(this);
        this.waves.push(this.spill);
        Main.layoutManager.addTopChrome(this.spill.actor, {affectsInputRegion: false, trackFullscreen: true});
        this.sky = new Sky(this);
        Main.layoutManager.addTopChrome(this.sky.actor, {affectsInputRegion: false, trackFullscreen: true});
        this.scene = new Scene(this);
        Main.layoutManager.addTopChrome(this.scene.actor, {affectsInputRegion: false, trackFullscreen: true});
        this.water = new Water(this);
        this.waves.push(this.water);
        Main.layoutManager.addTopChrome(this.water.actor, {affectsInputRegion: false, trackFullscreen: true});
        // GNOME bildirimleri de ekranın üst ortasında çıkar: adanın altında kalmasınlar, üstünde görünsünler.
        // Sıra (alttan): taşan su, zemin (süsler), sahnenin katmanları, adanın suyu, ada (yazılar), bildirimler.
        for (const actor of [this.spill.actor, this.sky.actor, this.scene.actor, this.water.actor, this.box])
            this._belowTray(actor);
        this._sigs = [
            [this.box, this.box.connect('notify::width', () => this._place())],
            [this.box, this.box.connect('notify::height', () => this._place())],
            [this.box, this.box.connect('notify::scale-x', () => this._place())],
            [this.box, this.box.connect('notify::opacity', () => {
                this.sky.actor.opacity = this.scene.actor.opacity = this.water.actor.opacity = this.box.opacity;
            })],
            [this.box, this.box.connect('notify::translation-x', () => {  // sallanınca zemin ve su da sallansın
                this.sky.actor.translation_x = this.scene.actor.translation_x = this.water.actor.translation_x =
                    this.box.translation_x;
            })],
            // Tam ekran uygulamada ada gizlenir (görünmez): saat durur. Kilitlenince de.
            [this.box, this.box.connect('notify::mapped', () => this._anim())],
            [Main.sessionMode, Main.sessionMode.connect('updated', () => this._anim())],
            [Main.layoutManager, Main.layoutManager.connect('monitors-changed', () => this._place())],
            // Olaylar düğmelerden önce görülür: sürükleme bir düğmenin üstünden başlasa da sayfa değişsin.
            [this.box, this.box.connect('captured-event', (a, e) => this._captured(e))],
            [this.box, this.box.connect('button-release-event', (a, e) => this._release(e))],
            [this.box, this.box.connect('notify::hover', () => this._hoverChanged())],
            [this.box, this.box.connect('scroll-event', (a, e) => this._scroll(e))],
        ];

        this._watch = Gio.bus_watch_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameWatcherFlags.NONE,
            () => this._connect(), () => this._lost());
        this._idleSetup();
        this._powerSetup();
        this._batterySetup();
    }

    destroy() {
        Gio.bus_unwatch_name(this._watch);
        this._outsideWatch(false);
        if (this._idleMon) {
            for (const id of [this._idleWatch, this._activeWatch]) {
                if (id)
                    this._idleMon.remove_watch(id);
            }
        }
        if (this._power && this._powerSig)
            this._power.disconnect(this._powerSig);
        this._power = null;
        if (this._upower && this._upowerSig)
            this._upower.disconnect(this._upowerSig);
        this._upower = null;
        this._clockStop();
        for (const id of Object.values(this._timers))
            GLib.source_remove(id);
        this._timers = {};
        this._ungrab();
        if (this._proxy && this._sigId)
            this._proxy.disconnectSignal(this._sigId);
        this._proxy = null;
        for (const [obj, id] of this._sigs)
            obj.disconnect(id);
        Main.layoutManager.removeChrome(this.spill.actor);
        this.spill.actor.destroy();
        Main.layoutManager.removeChrome(this.sky.actor);
        this.sky.actor.destroy();
        Main.layoutManager.removeChrome(this.scene.actor);
        this.scene.destroy();
        Main.layoutManager.removeChrome(this.water.actor);
        this.water.actor.destroy();
        Main.layoutManager.removeChrome(this.box);
        this.box.destroy();
    }

    _belowTray(actor) {
        const tray = Main.messageTray;
        const parent = actor.get_parent();
        if (tray && parent && tray.get_parent() === parent)
            parent.set_child_below_sibling(actor, tray);
    }

    // ---- Talk To ile bağlantı ---------------------------------------------------------

    _connect() {
        new AdaProxy(Gio.DBus.session, BUS_NAME, OBJECT_PATH, (proxy, error) => {
            if (error) {
                log(`Talk To ada: ${error}`);
                return;
            }
            this._proxy = proxy;
            this._sigId = proxy.connectSignal('Changed', (_p, _s, [json]) => this._update(json));
            this._getState(proxy, 0);
        });
    }

    // Talk To adını alır almaz ada nesnesini henüz kaydetmemiş olabilir: ilk istek boşa giderse yeniden dene.
    // (Durumu istemek Talk To'ya "ada ekranda" der; söylenmezse mini oynatıcı ve pil uyarısı yanlış karar verir.)
    _getState(proxy, tries) {
        proxy.GetStateRemote(([json], err) => {
            if (!err) {
                this._update(json);
                return;
            }
            if (tries < 10 && this._proxy === proxy) {
                this._timers.state = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500 + tries * 500, () => {
                    delete this._timers.state;
                    if (this._proxy === proxy)
                        this._getState(proxy, tries + 1);
                    return GLib.SOURCE_REMOVE;
                });
            }
        });
    }

    _lost() {
        this._lastJson = null;
        this._proxy = null;
        this.state = null;
        this.box.visible = false;
        this._skyUpdate();
        this._animate(false);
    }

    act(obj) {
        if (this._proxy)
            this._proxy.ActionRemote(JSON.stringify(obj), () => {});
    }

    _update(json) {
        // Aynı durum yeniden geldiyse adayı baştan kurmaya gerek yok (kabuğa boşuna iş).
        if (json === this._lastJson)
            return;
        this._lastJson = json;
        let st;
        try {
            st = JSON.parse(json);
        } catch (e) {
            return;
        }
        const prev = this.state && this.state.media;
        this.state = st;
        this.theme = Object.assign({}, DEFAULT_THEME, st.theme || {});
        if (st.idle_pause !== undefined && st.idle_pause !== this._idlePause) {
            this._idlePause = st.idle_pause;
            this._armIdle();
        }
        if (!this.moving)  // sürüklerken Talk To'nun eski değeri araya girmesin
            this.offset = st.offset || 0;
        this.playing = !!(st.media && st.media.active && st.media.playing);
        this.loading = !!(st.media && st.media.active && st.media.loading);
        // Zemini alttaki katman çizer (süsler ve su yazıların altında kalsın): ada saydam.
        this.box.set_style(`background-color: transparent; color: ${this.theme.text};`);
        this.box.visible = st.enabled !== false;
        // Açık zeminli tema (yazı koyu): uyarı kırmızısı koyulaşır, okunsun.
        const [tr, tg, tb] = rgba(this.theme.text, 1);
        if (0.2126 * tr + 0.7152 * tg + 0.0722 * tb < 0.4)
            this.box.add_style_class_name('ada-acik-tema');
        else
            this.box.remove_style_class_name('ada-acik-tema');
        const media = st.media;
        const newTrack = !!(prev && media && prev.title && media.title !== prev.title);
        this._morph(() => {
            const ev = st.event || {};
            if (ev.seq && ev.seq !== this.lastEvent) {
                const first = this.lastEvent === 0;
                this.lastEvent = ev.seq;
                if (!first)
                    this._onEvent(ev.kind);
            }
            if (!st.call && this.pageName === 'arama')
                this.pageName = 'calan';
            this._buildCompact();
            if (this.expanded)
                this._buildPage();
        });
        if (newTrack || (this.playing && !this._wasPlaying))  // "Olaylarda": yeni şarkı ya da çalmaya başladı
            this._wake();
        this._wasPlaying = this.playing;
        if (newTrack)  // yeni şarkı: yazılar hafifçe kayarak belirir (hiç boş görünmeden)
            this._fadeIn(this.compact, -3, 110);
        this._animate((this.playing || this.loading) && this.box.visible);
        this._spillUpdate();
        this._skyUpdate();
    }

    _onEvent(kind) {
        const page = {call: 'arama', track: 'calan', notification: 'bildirim', pil: 'pil'}[kind];
        if (!page)
            return;
        this._wake();
        if (this.thin && kind !== 'call' && kind !== 'pil')
            return; // ince şeritte yalnızca arama ve azalan pil büyütür
        if (kind === 'pil' && this.state && this.state.call && this.pageName === 'arama')
            return; // görüşme sayfası açıkken araya girmez (küçükken kırmızı pil yine görünür)
        if (this.custom || this.moving) {  // özelleştirirken / konum değiştirirken yalnızca arama araya girer
            if (kind !== 'call')
                return;
            this.custom = false;
            this.moving = false;
        }
        if (kind === 'pil' && this.thin)
            this._unthin();
        this.pageName = page;
        this._expand(true);
        if (kind === 'pil') {
            this._shake();
            this._collapseLater(BATTERY_EVENT_MS);
            return;
        }
        this._bump();
        if (kind !== 'call')
            this._collapseLater(SHOW_EVENT_MS);
    }

    // ---- yerleşim ---------------------------------------------------------------------

    _place() {
        const m = Main.layoutManager.primaryMonitor;
        if (!m)
            return;
        const top = Main.panel ? Main.panel.height : 0;
        // Ortadan yana kaydırılmış olabilir ("Konumu değiştir"); hiçbir zaman ekranın dışına taşmaz.
        const room = Math.max(0, (m.width - this.box.width) / 2);
        const off = Math.max(-room, Math.min(room, this.offset));
        const cx = m.x + m.width / 2 + off;
        this.box.set_position(Math.round(cx - this.box.width / 2), m.y + top);
        // Taşan su adanın üst kenarından başlar (yanlardan dökülür) ve altına SPILL_H kadar iner.
        const s = this.spill.actor;
        const bh = Math.round(this.box.height * this.box.scale_y);
        this.spill.bh = bh;
        s.set_size(Math.round(this.box.width * this.box.scale_x) + 2 * SPILL_PAD, bh + SPILL_H);
        s.set_position(Math.round(cx - s.width / 2), m.y + top);
        // Süsler adanın tam üstünde, aynı biçimde (alt köşeler yuvarlak).
        const k = this.sky.actor;
        k.set_size(Math.round(this.box.width * this.box.scale_x), bh);
        k.set_position(Math.round(cx - k.width / 2), m.y + top);
        const node = this.box.peek_theme_node();  // ilk çizimden önce yok: varsayılan kalır
        if (node)
            this.sky.radius = node.get_border_radius(St.Corner.BOTTOMLEFT) * this.box.scale_x;
        this.sky.repaint();
        const sa = this.scene.actor;
        sa.set_size(k.width, k.height);
        sa.set_position(k.x, k.y);
        this.scene.update();
        // Su: adanın alt kenarında bir şerit (ince şeritte şeridin tamamı)
        const thin = this.thin && !this.peek && !this.expanded;
        const wh = thin ? bh : Math.min(11, Math.round(bh * 0.4));
        const wa = this.water.actor;
        this.water.bh = bh;
        wa.set_size(k.width, Math.max(1, wh));
        wa.set_position(k.x, m.y + top + bh - wh);
        this.water.repaint();
    }

    // ---- temanın süsleri ----------------------------------------------------------------

    // Süslerin hareketi: Talk To'daki ayar (canli / yavas / durgun) ve GNOME'un "Canlandırmalar" ayarı.
    _fxMotion() {
        const st = this.state || {};
        let anim = true;
        try {
            anim = St.Settings.get().enable_animations;
        } catch (e) {
            // eski kabuk: açık say
        }
        if (!anim || this._powerSaver())
            return 'durgun';  // GNOME'da canlandırmalar kapalı ya da güç tasarrufu kipi: ada kıpırdamaz
        const motion = st.motion || 'canli';
        // Dizüstü pildeyken Canlı kendiliğinden Yavaş olur (prize takılınca döner); Talk To'dan kapatılabilir.
        if (motion === 'canli' && st.battery_slow !== false && this._onBattery())
            return 'yavas';
        return motion;
    }

    // Büyük adada süsler soluk (yazılar okunsun); katmanlı manzara (Deniz, Prizma) az soluk.
    skyAlpha() {
        if (!this.expanded)
            return 1;
        return sceneTheme(this.theme) ? SCENE_ALPHA_BIG : 0.55;
    }

    fxTime() {
        const m = this._fxMotion();
        if (m === 'durgun')
            return 8;  // süsler dağılmış hâlde durur
        const t = GLib.get_monotonic_time() / 1e6 - this._fx0;
        return 8 + (m === 'yavas' ? t * 0.5 : t);
    }

    // Zemin katmanı ada görünürken hep görünür; süsler aramada ve ince şeritte çekilir (dikkat dağıtmasın).
    _skyUpdate() {
        const st = this.state || {};
        const fx = (this.theme && this.theme.fx) || [];
        const thinShown = this.thin && !this.peek && !this.expanded;
        this.sky.actor.visible = this.scene.actor.visible = this.box.visible;
        this.skyOn = fx.length > 0 && this.box.visible && !st.call && !thinShown;
        this.sky.actor.opacity = this.scene.actor.opacity = this.water.actor.opacity = this.box.opacity;
        this.scene.update();
        this.sky.repaint();
        // Su normal hâlde ve ince şeritte (büyükken çalan sayfasının kendi dalgası var)
        this.water.actor.visible = this.box.visible && !this.expanded && !this.moving;
        this._place();
        this._anim();
    }

    // ---- canlandırma saati --------------------------------------------------------------

    // Tek saat: dalga, taşan su, süsler ve Özelleştir'deki mini adalar aynı karede çizilir (ayrı saatler kabuğu
    // saniyede daha çok kare çizmeye zorlar). Saniyede kaç kare: o an gereken en çok (bkz. WAVE_FPS, FX_FPS).
    // Kimse bakmıyorsa hiç çalışmaz: ada görünmüyor (tam ekran), ekran kilitli, kullanıcı bir süredir dokunmuyor,
    // Durgun / güç tasarrufu (dalga yerinde durur, süsler resim gibi).
    _fps() {
        const stop = why => {
            this._why = why;
            return 0;
        };
        if (!this.box.visible || !this.box.mapped)
            return stop('ada görünmüyor (tam ekran ya da kapalı)');
        if (Main.sessionMode.isLocked)
            return stop('ekran kilitli');
        if (this.idle)
            return stop(`kullanıcı ${this._idlePause === undefined ? IDLE_PAUSE_S : this._idlePause} sn dokunmadı`);
        const motion = this._fxMotion();
        if (motion === 'durgun')
            return stop(this._powerSaver() ? 'güç tasarrufu kipi' : 'Durgun');
        if (motion === 'olaylarda' && GLib.get_monotonic_time() / 1000 > (this._liveUntil || 0))
            return stop('Olaylarda: olay bekleniyor');
        const target = this.loading ? 0.1 : this.waveOn ? 0.22 : 0.05;
        const wave = this.waveOn || Math.abs(this.amp - target) > 0.002 ? WAVE_FPS : 0;
        let fx = 0;
        const scene = this.scene.on && this.scene.ready ? (wave ? SCENE_FPS : SCENE_IDLE_FPS) : 0;
        if (this.skyOn && !this.scene.on) {
            for (const f of this.theme.fx || [])
                fx = Math.max(fx, FX_FPS[f.type] || 12);
            if (this.expanded)  // büyükken süslerin alanı büyük, kendileri soluk: daha seyrek çizilir
                fx = Math.round(fx / 2);
        }
        const swatch = this.custom && this.expanded && this.swatches.length ? SWATCH_FPS : 0;
        const fps = Math.max(wave, fx, swatch, scene);
        this._slow = motion === 'yavas' ? 2 : 1;
        // Zemin (süsler, manzara) kendi hızında çizilir: dalga 15 kare isterken deniz manzarası 4 karede kalır
        this._skyEvery = fx ? 1 / (motion === 'yavas' ? Math.max(1, fx / 2) : fx) : 0;
        this._why = `${motion}${wave ? ', dalga' : ''}${fx ? ', süsler' : ''}${scene ? ', sahne' : ''}` +
            `${swatch ? ', mini adalar' : ''}`;
        if (!fps)
            this._why = 'canlanacak bir şey yok';
        return motion === 'yavas' ? Math.round(fps / 2) : fps;
    }

    // "Olaylarda" kipinde kısa süre canlan (şarkı değişti, üstüne gelindi, büyüdü...).
    _wake() {
        this._liveUntil = GLib.get_monotonic_time() / 1000 + LIVE_MS;
        this._cancel('live');
        this._timers.live = GLib.timeout_add(GLib.PRIORITY_DEFAULT, LIVE_MS + 50, () => {
            delete this._timers.live;
            this._anim();
            return GLib.SOURCE_REMOVE;
        });
        this._anim();
    }

    _anim() {
        const fps = this._fps();
        if (fps !== this._logged) {  // sorun ararken: saat her değiştiğinde GNOME kaydına bir satır (journalctl)
            this._logged = fps;
            log(`Talk To ada: canlandırma ${fps ? `${fps} kare/sn` : 'durdu'} (${this._why})`);
        }
        if (this._timers.anim && fps === this._animFps)
            return;
        this._clockStop();
        this._animFps = fps;
        if (!fps) {
            this._settleWave();
            this.scene.step(this.fxTime());
            return;
        }
        // Tek zamanlayıcı: dalga, zemin, sahne aynı karede güncellenir; kabuk her karede bir kez çizer. (Ekranın
        // kendi kare saatine, Clutter.Timeline'a bağlamak denendi: kabuk durmadan çizdi, sanal ekranda işlemci
        // %7'den %80'e çıktı.)
        this._last = {};
        this._waveLast = GLib.get_monotonic_time() / 1e6;
        this._timers.anim = GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.round(1000 / fps), () => {
            this._tick();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _clockStop() {
        this._cancel('anim');
    }

    // Parçanın sırası geldi mi (every saniyede bir); gecikse de tempo kaymaz.
    _due(name, every, now) {
        const last = this._last[name];
        if (last !== undefined && now - last < every - 0.01)
            return false;
        this._last[name] = last !== undefined && now - last < 2 * every ? last + every : now;
        return true;
    }

    _tick() {
        const now = GLib.get_monotonic_time() / 1e6;
        const slow = this._slow || 1;
        let ran = false;
        const target = this.loading ? 0.1 : this.waveOn ? 0.22 : 0.05;
        const waving = this.waveOn || Math.abs(this.amp - target) > 0.002;
        if (waving && this._due('wave', slow / WAVE_FPS, now)) {
            const dt = now - this._waveLast;
            const k = Math.min(6, (dt > 0.25 ? 1 / WAVE_FPS : dt) / 0.04);  // eski 40 ms'lik adımlara göre
            this._waveLast = now;
            // Çalarken dalga akar; duraklayınca yavaşlayıp durulur (birden donmaz).
            this.amp += (target - this.amp) * (1 - Math.pow(0.92, k));
            this.phase += (0.03 + 0.09 * ((this.amp - 0.05) / 0.17)) * k;
            if (!this.waveOn && Math.abs(this.amp - target) <= 0.002)
                this.amp = target;
            for (const w of this.waves)
                w.repaint();
            this._spillUpdate();
            ran = true;
        }
        if (this.skyOn && this._skyEvery && this._due('sky', this._skyEvery, now)) {
            this.sky.repaint();
            ran = true;
        }
        const sceneEvery = slow / (waving ? SCENE_FPS : SCENE_IDLE_FPS);
        if (this.scene.on && this.scene.ready && this._due('scene', sceneEvery, now)) {
            this.scene.step(this.fxTime());
            ran = true;
        }
        if (this.custom && this.expanded && this.swatches.length && this._due('swatch', 1 / SWATCH_FPS, now)) {
            for (const a of this.swatches)
                a.queue_repaint();
            ran = true;
        }
        if (ran && this._fps() !== this._animFps)
            this._anim();
    }

    // Saat durunca (Durgun, boşta...) dalga bulunduğu yerde değil, çalıp çalmamasına uygun yükseklikte durur.
    _settleWave() {
        const target = this.loading ? 0.1 : this.waveOn ? 0.22 : 0.05;
        if (this.amp !== target) {
            this.amp = target;
            for (const w of this.waves)
                w.repaint();
            this._spillUpdate();
        }
    }

    // Kullanıcı dokunmuyor mu (fare, klavye, dokunmatik): GNOME'un boşta izleyicisi.
    _idleSetup() {
        try {
            this._idleMon = global.backend.get_core_idle_monitor();
        } catch (e) {
            try {
                this._idleMon = Meta.IdleMonitor.get_core();  // GNOME 42–43
            } catch (e2) {
                this._idleMon = null;
            }
        }
        this._armIdle();
    }

    _armIdle() {
        if (!this._idleMon)
            return;
        if (this._idleWatch)
            this._idleMon.remove_watch(this._idleWatch);
        const sec = this._idlePause === undefined ? IDLE_PAUSE_S : this._idlePause;
        this._idleWatch = this._idleMon.add_idle_watch(Math.max(1, sec) * 1000, () => {
            this.idle = true;
            this._anim();
            if (!this._activeWatch) {
                this._activeWatch = this._idleMon.add_user_active_watch(() => {
                    this._activeWatch = 0;
                    this.idle = false;
                    this._anim();
                });
            }
        });
    }

    // GNOME'un güç kipi (Güç tasarrufu: ada kıpırdamaz). power-profiles-daemon yoksa hiç sorulmaz.
    _powerSetup() {
        Gio.DBusProxy.new_for_bus(Gio.BusType.SYSTEM, Gio.DBusProxyFlags.DO_NOT_AUTO_START, null,
            'net.hadess.PowerProfiles', '/net/hadess/PowerProfiles', 'net.hadess.PowerProfiles', null,
            (_o, res) => {
                try {
                    this._power = Gio.DBusProxy.new_for_bus_finish(res);
                    this._powerSig = this._power.connect('g-properties-changed', () => this._skyUpdate());
                    this._skyUpdate();
                } catch (e) {
                    this._power = null;
                }
            });
    }

    // Bilgisayar pilde mi (UPower). Masaüstünde ya da UPower yoksa hiç pilde sayılmaz.
    _batterySetup() {
        Gio.DBusProxy.new_for_bus(Gio.BusType.SYSTEM, Gio.DBusProxyFlags.DO_NOT_AUTO_START, null,
            'org.freedesktop.UPower', '/org/freedesktop/UPower', 'org.freedesktop.UPower', null,
            (_o, res) => {
                try {
                    this._upower = Gio.DBusProxy.new_for_bus_finish(res);
                    this._upowerSig = this._upower.connect('g-properties-changed', () => this._skyUpdate());
                    this._skyUpdate();
                } catch (e) {
                    this._upower = null;
                }
            });
    }

    _onBattery() {
        const v = this._upower ? this._upower.get_cached_property('OnBattery') : null;
        return v ? v.unpack() === true : false;
    }

    _powerSaver() {
        const v = this._power ? this._power.get_cached_property('ActiveProfile') : null;
        return v ? v.unpack() === 'power-saver' : false;
    }

    // Taşan su: "Taşan dalgalar" kipinde, ada görünürken ve çalarken (ya da şarkılar arasında).
    _spillUpdate() {
        const st = this.state || {};
        const on = st.mode === 'tasan' && this.box.visible && (this.playing || this.loading || this.amp > 0.06);
        if (on && !this.spill.actor.visible) {
            this.spill.actor.opacity = 0;
            this.spill.actor.show();
            this.spill.actor.ease({opacity: 255, duration: 400, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
        } else if (!on && this.spill.actor.visible) {
            this.spill.actor.ease({opacity: 0, duration: 400, mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                onComplete: () => this.spill.actor.hide()});
        }
    }

    _pages() {
        const st = this.state || {};
        const list = st.call ? ['arama'] : [];
        // Zamanlayıcı isteğe bağlı (Özelleştir / Talk To'nun Ada sekmesi); kuruluysa sayfası yine görünür.
        const timer = (st.prefs && st.prefs.ada_timer_page) || st.timer ? ['zamanlayici'] : [];
        return list.concat(['calan', 'bildirim'], timer, ['diger']);
    }

    _setClass() {
        if (this.sky)
            this._skyUpdate();
        const thin = this.thin && !this.peek && !this.expanded;
        const peek = this.thin && this.peek && !this.expanded;
        // Üstüne gelince görünen normal hâl geçicidir: hafif saydam (tıklayınca büyür, ayrılınca ince şerit).
        this.box.ease({opacity: peek ? 205 : 255, duration: 160, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
        for (const [cls, on] of [['ada-buyuk', this.expanded], ['ada-ince', thin],
            ['ada-ozel', this.custom && this.expanded], ['ada-kilitsiz', this.moving]]) {
            if (on)
                this.box.add_style_class_name(cls);
            else
                this.box.remove_style_class_name(cls);
        }
    }

    _expand(on) {
        if (on)
            this._wake();
        this._morph(() => {
            this.expanded = on;
            if (!on)
                this.custom = false;
            this.page.visible = on;
            if (!on && this.pageName === 'pil')  // uyarı geçici: sonra açılınca çalan görünür
                this.pageName = 'calan';
            this._setClass();
            if (on) {
                this._buildPage();
                this._fadeIn(this.page, -6);
            } else {
                this._cancel('collapse');
            }
            this._buildCompact();
        });
    }

    _collapseLater(ms) {
        this._cancel('collapse');
        this._timers.collapse = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            delete this._timers.collapse;
            const callActive = this.state && this.state.call;
            if (!this.box.hover && !this.custom && !(callActive && this.pageName === 'arama'))
                this._expand(false);
            return GLib.SOURCE_REMOVE;
        });
    }

    _refreshLater(name, ms) {
        this._cancel(name);
        this._timers[name] = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            delete this._timers[name];
            this._buildCompact();
            if (this.expanded)
                this._buildPage();
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancel(name) {
        if (this._timers[name]) {
            GLib.source_remove(this._timers[name]);
            delete this._timers[name];
        }
    }

    _hoverChanged() {
        // (Üstüne gelince büyümez: ölçeklenen yazı bulanık görünüyordu.)
        if (this.box.hover) {
            this._cancel('collapse');
            this._wake();  // "Olaylarda": üstüne gelince canlanır
        } else if (this.expanded) {
            this._collapseLater(IDLE_COLLAPSE_MS);
        }
        if (!this.thin)
            return;
        this._cancel('peek');
        if (this.box.hover) {
            this._setPeek(true);
        } else {
            this._timers.peek = GLib.timeout_add(GLib.PRIORITY_DEFAULT, PEEK_LEAVE_MS, () => {
                delete this._timers.peek;
                this._setPeek(false);
                return GLib.SOURCE_REMOVE;
            });
        }
    }

    _setPeek(on) {
        if (this.peek === on)
            return;
        this._morph(() => {
            this.peek = on;
            this._setClass();
            this._buildCompact();
        });
        this._fadeIn(this.compact);
    }

    // Bir kademe küçült (yukarı kaydırma) ya da ince şeritten normale dön (tıklama).
    _shrink() {
        if (this.expanded) {
            this._expand(false);
        } else if (!this.thin) {
            this._morph(() => {
                this.thin = true;
                this.peek = false;
                this._setClass();
                this._buildCompact();
            });
        }
    }

    _unthin() {
        this._cancel('peek');
        this._morph(() => {
            this.thin = false;
            this.peek = false;
            this._setClass();
            this._buildCompact();
        });
        this._fadeIn(this.compact);
    }

    _scroll(event) {
        if (this.moving)
            return Clutter.EVENT_STOP;
        // Yukarı: büyük → normal → ince şerit. Aşağı: ince şerit → normal → büyük (tersi).
        let step = 0;
        const dir = event.get_scroll_direction();
        if (dir === Clutter.ScrollDirection.UP) {
            step = -1;
        } else if (dir === Clutter.ScrollDirection.DOWN) {
            step = 1;
        } else if (dir === Clutter.ScrollDirection.SMOOTH) {  // dokunmatik yüzey: küçük adımlar birikir
            const [, dy] = event.get_scroll_delta();
            this._scrollSum = Math.sign(dy) === Math.sign(this._scrollSum) ? this._scrollSum + dy : dy;
            step = this._scrollSum <= -1 ? -1 : this._scrollSum >= 1 ? 1 : 0;
        }
        if (!step)
            return Clutter.EVENT_STOP;
        const now = GLib.get_monotonic_time() / 1000;
        if (now - this._scrollAt > SCROLL_COOLDOWN_MS) {
            this._scrollAt = now;
            this._scrollSum = 0;
            if (step < 0)
                this._shrink();
            else
                this._grow();
        }
        return Clutter.EVENT_STOP;
    }

    _grow() {
        if (this.thin)
            this._unthin();
        else if (!this.expanded)
            this._expand(true);
    }

    // ---- dalga canlandırması -----------------------------------------------------------

    // Çalarken dalga akar; duraklayınca yavaşlayıp durulur (birden donmaz), sonra çizim durur.
    _animate(on) {
        this.waveOn = on;
        this._anim();
    }

    // ---- canlandırmalar ----------------------------------------------------------------

    // Boyut değişimi (büyüme, küçülme, ince şerit, sayfa) yumuşak olsun: önce eski boyutta sabitlenir,
    // içerik yenilenir, sonra yeni doğal boyuta kayar.
    // Temanın dokunma izi (Deniz: suda halkalar, Prizma: ışık patlaması). Durgun'da ve canlandırmalar kapalıyken yok.
    _touchFx(x, y) {
        if (!this.theme.touch || this._fxMotion() === 'durgun')
            return;
        const [ok, lx, ly] = this.scene.actor.transform_stage_point(x, y);
        if (ok)
            this.scene.touch(lx, ly);
    }

    _morph(fn) {
        if (this._morphing)  // iç içe çağrıda dıştaki canlandırır
            return fn();
        const [w0, h0] = this.box.get_size();
        this._morphing = true;
        try {
            fn();
        } finally {
            this._morphing = false;
        }
        if (!this.box.visible || !this.box.mapped || w0 <= 0)
            return;
        this.box.remove_transition('width');
        this.box.remove_transition('height');
        this.box.set_size(-1, -1);
        const [, w1] = this.box.get_preferred_width(-1);
        const [, h1] = this.box.get_preferred_height(w1);
        if (Math.abs(w1 - w0) < 2 && Math.abs(h1 - h0) < 2)
            return;
        this.box.set_size(w0, h0);
        this.box.ease({width: w1, height: h1, duration: 240, mode: Clutter.AnimationMode.EASE_OUT_CUBIC,
            onComplete: () => this.box.set_size(-1, -1)});
    }

    // Bir şey olunca (arama, şarkı, bildirim) hafif bir sıçrama.
    _bump() {
        this.box.remove_transition('scale-x');
        this.box.remove_transition('scale-y');
        this.box.ease({scale_x: 1.04, scale_y: 1.04, duration: 110, mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onComplete: () => this.box.ease({scale_x: 1, scale_y: 1, duration: 260,
                mode: Clutter.AnimationMode.EASE_OUT_BACK})});
    }

    // Pil azalınca: ada birkaç kez hafifçe sağa sola sallanır (göz ucuyla fark edilsin).
    _shake() {
        const steps = [7, -7, 5, -5, 3, 0];
        const next = i => {
            if (i >= steps.length)
                return;
            this.box.ease({translation_x: steps[i], duration: 70, mode: Clutter.AnimationMode.EASE_IN_OUT_QUAD,
                onComplete: () => next(i + 1)});
        };
        this.box.remove_transition('translation-x');
        next(0);
    }

    _fadeIn(actor, dy = 0, from = 0) {
        actor.opacity = from;
        actor.translation_y = dy;
        actor.ease({opacity: 255, translation_y: 0, duration: 220, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
    }

    _wave(width, height) {
        const w = new Wave(width, height, this);
        this.waves.push(w);
        w.actor.connect('destroy', () => {
            this.waves = this.waves.filter(x => x !== w);
        });
        return w.actor;
    }

    // ---- sürükleyerek sayfa değiştirme -------------------------------------------------

    // Basma her zaman kaydedilir ve düğmeye de gider. Fare 8 pikselden fazla kayarsa sürüklemedir: düğmenin
    // basışı iptal edilir (bırakınca tıklama sayılmaz), olaylar adaya kalır. Kaymazsa düğme normal tıklanır;
    // düğme olmayan yere bırakma ise adanın kendi "button-release-event"ine düşer (büyüt/küçült).
    _captured(event) {
        const type = event.type();
        if (type === Clutter.EventType.BUTTON_PRESS) {
            if (event.get_button() === 1) {
                [this._dragX, this._dragY] = event.get_coords();
                this._dragged = false;
                this._touchFx(this._dragX, this._dragY);
            }
            return Clutter.EVENT_PROPAGATE;
        }
        if (type === Clutter.EventType.TOUCH_BEGIN) {
            this._touchFx(...event.get_coords());
            return Clutter.EVENT_PROPAGATE;
        }
        if (type === Clutter.EventType.MOTION) {
            const wasDragged = this._dragged;
            const r = this._motion(event);
            if (this._dragged && !wasDragged)
                this._cancelButtons(this.box);
            return r;
        }
        if (type === Clutter.EventType.BUTTON_RELEASE && this._dragged)
            return this._release(event);
        return Clutter.EVENT_PROPAGATE;
    }

    _cancelButtons(actor) {
        for (const c of actor.get_children()) {
            if (c instanceof St.Button && c.pressed)
                c.fake_release();
            this._cancelButtons(c);
        }
    }

    // Sürükleme başlayınca fare adaya bağlanır: GNOME 42'de bağlanmazsa fare adanın dışında bırakıldığında
    // bırakma olayı adaya hiç gelmiyor, sürükleme "takılı" kalıyordu (sayfa kayıyor ama değişmiyordu).
    // Basılınca değil, sürükleme başlayınca bağlanır: yoksa düğmeler tıklamayı alamaz.
    _grabPointer() {
        if (this._grab)
            return;
        try {
            if (global.stage.grab)
                this._grab = global.stage.grab(this.box);
        } catch (e) {
            this._grab = null;
        }
    }

    _ungrab() {
        if (this._grab) {
            this._grab.dismiss();
            this._grab = null;
        }
    }

    _endDrag() {
        this._dragX = undefined;
        this._ungrab();
        this.page.ease({translation_x: 0, duration: 150, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
    }

    _motion(event) {
        if (this._dragX === undefined)
            return Clutter.EVENT_PROPAGATE;
        if (!(event.get_state() & Clutter.ModifierType.BUTTON1_MASK)) {  // bırakma kaçırıldı: sürüklemeyi bitir
            this._endDrag();
            return Clutter.EVENT_PROPAGATE;
        }
        const [x, y] = event.get_coords();
        const dx = x - this._dragX, dy = y - this._dragY;
        if (!this._dragged && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
            this._dragged = true;
            this._offStart = this.offset;
            this._grabPointer();
        }
        if (!this._dragged)
            return Clutter.EVENT_PROPAGATE;
        if (this.moving) {  // kilit açık: ada üst kenar boyunca kayar (_place ekranın içinde tutar)
            this.offset = this._offStart + dx;
            this._place();
        } else if (this.expanded && !this.custom && Math.abs(dx) > Math.abs(dy)) {
            // Sayfa fareyi bire bir izler; gidecek sayfa yoksa lastik gibi az esner.
            const pages = this._pages();
            const i = pages.indexOf(this.pageName);
            const edge = (dx > 0 && i <= 0) || (dx < 0 && i >= pages.length - 1);
            this.page.translation_x = edge ? dx * 0.3 : dx;
            this.page.opacity = 255 - Math.min(110, Math.abs(dx) * 0.5);
        }
        return Clutter.EVENT_STOP;
    }

    _release(event) {
        if (this._dragX === undefined)
            return Clutter.EVENT_PROPAGATE;
        const [x, y] = event.get_coords();
        const dx = x - this._dragX, dy = y - this._dragY;
        this._dragX = undefined;
        this._ungrab();
        if (this.moving) {
            if (this._dragged) {
                const m = Main.layoutManager.primaryMonitor;
                const room = m ? Math.max(0, (m.width - this.box.width) / 2) : 0;
                this.offset = Math.round(Math.max(-room, Math.min(room, this.offset)));
                this.act({do: 'set', key: 'ada_offset', value: this.offset});
            }
        } else if (this._dragged && -dy >= DRAG_UP && -dy > Math.abs(dx)) {  // yukarı sürükleme: küçül
            this._springBack();
            this._shrink();
        } else if (this.custom) {  // özelleştirmede boş yere tıklama kapatır (✕'e gerek yok); sürükleme bir şey yapmaz
            if (this._dragged)
                this._springBack();
            else if (!this._onControl(eventActor(event)))  // düğmeye (tema, ayar) basıldıysa kapanmaz
                this._setCustom(false);
        } else if (this.thin && !this.expanded && !this._dragged) {
            // İnce şeritteki (üstüne gelince görünen) adaya tıklama: doğrudan büyür; kapanınca normal kalır.
            this._unthin();
            this._expand(true);
        } else if (this._dragged && Math.abs(dx) >= DRAG_PAGE && Math.abs(dx) > Math.abs(dy)) {
            if (!this.expanded)
                this._expand(true);
            this._turn(dx > 0 ? -1 : 1);
        } else if (!this._dragged) {
            this._expand(!this.expanded);
        } else {
            this._springBack();
        }
        return Clutter.EVENT_STOP;
    }

    _springBack() {
        this.page.ease({translation_x: 0, opacity: 255, duration: 220, mode: Clutter.AnimationMode.EASE_OUT_BACK});
    }

    // Sayfa değişimi: eskisi gittiği yöne kayıp söner, yenisi öbür yandan kayarak gelir; boy yeni sayfayla
    // birlikte yumuşakça değişir.
    _turn(dir) {
        const pages = this._pages();
        let i = pages.indexOf(this.pageName);
        if (i < 0)
            i = pages.indexOf('calan');
        const next = Math.max(0, Math.min(pages.length - 1, i + dir));
        if (next === i) {
            this._springBack();
            return;
        }
        this._cancel('collapse');
        this._click();
        const w = Math.max(120, this.page.width);
        this.page.remove_all_transitions();
        this.page.ease({translation_x: -dir * w * 0.45, opacity: 0, duration: 110,
            mode: Clutter.AnimationMode.EASE_IN_QUAD,
            onComplete: () => {
                this.pageName = pages[next];
                this._morph(() => this._buildPage());
                this.page.translation_x = dir * w * 0.35;
                this.page.opacity = 0;
                this.page.ease({translation_x: 0, opacity: 255, duration: 260,
                    mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
            }});
    }

    // Adada düğmeye basınca / sayfa değişince kısa ses (Özelleştir → Dokunma sesi; varsayılan kapalı).
    _click() {
        const prefs = (this.state && this.state.prefs) || {};
        if (!prefs.ada_click_sound)
            return;
        try {
            global.display.get_sound_player().play_from_theme('audio-volume-change', 'Talk To ada', null);
        } catch (e) {
            // ses teması yoksa sessiz geç
        }
    }

    // ---- içerik --------------------------------------------------------------------------

    _clear(actor) {
        actor.destroy_all_children();
    }

    _liveLabel(fn, cls) {
        const l = this._label(fn(), cls);
        const item = [l, fn];
        this.live.push(item);
        l.connect('destroy', () => {
            this.live = this.live.filter(x => x !== item);
        });
        this._clock();
        return l;
    }

    _clock() {
        if (this._timers.clock)
            return;
        this._timers.clock = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            if (!this.live.length) {
                delete this._timers.clock;
                return GLib.SOURCE_REMOVE;
            }
            for (const [l, fn] of this.live)
                l.text = fn();
            return GLib.SOURCE_CONTINUE;
        });
    }

    // Pil azken: kırmızı zemin üstünde beyaz simge ve yüzde, bitişik (açık ya da koyu her temada okunur).
    _batteryBadge(icon, level) {
        const b = new St.BoxLayout({style_class: 'ada-pil-rozet', y_align: Clutter.ActorAlign.CENTER});
        b.add_child(new St.Icon({icon_name: icon, icon_size: 12, y_align: Clutter.ActorAlign.CENTER}));
        b.add_child(this._label(`%${level}`, 'ada-pil-rozet-yazi'));
        return b;
    }

    _label(text, cls) {
        return new St.Label({text: text || '', style_class: cls || '', y_align: Clutter.ActorAlign.CENTER});
    }

    _button(icon, cb, cls) {
        const b = new St.Button({style_class: `ada-dugme ${cls || ''}`, can_focus: true,
            child: new St.Icon({icon_name: icon, icon_size: 14})});
        b.connect('clicked', () => {
            this._click();
            cb();
            this._cancel('collapse');
        });
        return b;
    }

    _textButton(text, cb, cls) {
        const b = new St.Button({style_class: `ada-metin ${cls || ''}`, label: text, can_focus: true});
        b.connect('clicked', () => {
            this._click();
            cb();
        });
        return b;
    }

    // Şarkı değişince yeni kapak telefondan biraz sonra gelir: o arada boş simgeye düşmek yerine eski kapak
    // soluk durur, yenisi gelince belirerek yerine geçer.
    _cover(size) {
        const media = this.state && this.state.media;
        let art = media && media.active && media.art;
        let stale = false;
        if (media && media.title !== this._artTitle) {  // yeni şarkı: kapağının gelmesi beklenir (en çok 4 sn)
            this._artTitle = media.title;
            this._artWaitUntil = Date.now() + 4000;
            if (!art)
                this._refreshLater('art', 4100);
        }
        if (art) {
            this._lastArt = art;
        } else if (media && media.active && this._lastArt && Date.now() < this._artWaitUntil) {
            art = this._lastArt;
            stale = true;
        }
        const bin = new St.Bin({style_class: 'ada-kapak', width: size, height: size});
        if (art) {
            bin.set_style(`background-image: url("file://${art}"); background-size: cover;` +
                `border-radius: ${Math.round(size / 4)}px;`);
            if (stale)
                bin.opacity = 110;
            else if (this._artShown && this._artShown !== art)
                this._fadeIn(bin);
            if (!stale)
                this._artShown = art;
        } else {
            bin.set_child(new St.Icon({icon_name: 'audio-x-generic-symbolic', icon_size: Math.round(size * 0.6)}));
        }
        return bin;
    }

    _buildCompact() {
        this._clear(this.compact);
        const st = this.state || {};
        const media = st.media || {};
        const call = st.call;
        if (this.thin && !this.peek && !this.expanded) {  // ince şerit: yalnızca su (arama sürerken yeşil nokta)
            if (call)
                this.compact.add_child(new St.Icon({icon_name: 'call-start-symbolic', icon_size: 8,
                    style_class: 'ada-yesil'}));
            if (st.low_battery)  // pil azken şeritte de kırmızı pil
                this.compact.add_child(new St.Icon({icon_name: 'battery-caution-symbolic', icon_size: 8,
                    style_class: 'ada-pil-az'}));
            return;  // şerit suyun kendisi (Water)
        }
        if (this.moving) {  // kilit açık: sürükleyerek kaydır, ortala, bitti
            this.compact.add_child(new St.Icon({icon_name: 'object-flip-horizontal-symbolic', icon_size: 14}));
            this.compact.add_child(this._label('Sağa-sola sürükle', 'ada-baslik'));
            this.compact.add_child(this._textButton('Ortala', () => {
                this.offset = 0;
                this._place();
                this.act({do: 'set', key: 'ada_offset', value: 0});
            }, 'ada-kucuk-metin'));
            this.compact.add_child(this._textButton('Bitti', () => this._setMoving(false),
                'ada-kucuk-metin ada-secili ada-bitti'));
            return;
        }
        if (this.expanded) {  // büyükken üst satır: saat, tarih, telefonun pili (çalan zaten aşağıda)
            const clock = this._liveLabel(() => GLib.DateTime.new_now_local().format('%H:%M'), 'ada-baslik');
            this.compact.add_child(clock);
            this.compact.add_child(this._label(GLib.DateTime.new_now_local().format('%-d %b %a'), 'ada-soluk'));
            this.compact.add_child(new St.Widget({x_expand: true}));
            if (call && this.pageName !== 'arama') {
                this.compact.add_child(new St.Icon({icon_name: 'call-start-symbolic', icon_size: 12,
                    style_class: 'ada-yesil'}));
            }
            if (st.phone && st.battery !== undefined && st.battery !== null) {
                const lvl = Math.max(0, Math.min(100, Math.round(st.battery / 10) * 10));
                const icon = `battery-level-${lvl}${st.charging ? '-charging' : ''}-symbolic`;
                if (st.low_battery) {  // azsa kırmızı rozet (her temada okunur)
                    this.compact.add_child(this._batteryBadge(icon, st.battery));
                } else {
                    this.compact.add_child(new St.Icon({icon_name: icon, icon_size: 14}));
                    this.compact.add_child(this._label(`%${st.battery}`, 'ada-soluk'));
                }
            }
            return;
        }
        if (call) {
            this.compact.add_child(new St.Icon({icon_name: 'call-start-symbolic', icon_size: 14,
                style_class: 'ada-yesil'}));
            this.compact.add_child(this._label(call.caller || 'Arama', 'ada-baslik'));
            this.compact.add_child(call.hint ? this._label('telefondan cevapla', 'ada-uyari')
                : call.state === 'ringing' ? this._label('arıyor', 'ada-soluk')
                : this._liveLabel(() => mmss(Date.now() / 1000 - (call.since || Date.now() / 1000)), 'ada-soluk'));
            return;
        }
        const lowTag = () => {  // pil azken küçük adanın sonunda kırmızı pil ve yüzde (şarja takılınca kalkar)
            if (!st.low_battery)
                return;
            this.compact.add_child(this._batteryBadge('battery-caution-symbolic', st.low_battery.level));
        };
        if (st.timer && !media.playing) {
            lowTag();
            this.compact.add_child(new St.Icon({icon_name: 'alarm-symbolic', icon_size: 14}));
            this.compact.add_child(this._liveLabel(() => mmss(st.timer.ends_at - Date.now() / 1000), 'ada-baslik'));
            return;
        }
        if (media.active) {
            this.compact.add_child(this._cover(18));
            const title = this._label(media.title, 'ada-baslik');
            title.clutter_text.ellipsize = 3; // Pango.EllipsizeMode.END
            if (this.loading)  // sıradaki şarkı bekleniyor: yazı hafifçe söner, parıltı dalgada
                title.opacity = 150;
            this.compact.add_child(title);
            this.compact.add_child(this._button(media.playing ? 'media-playback-pause-symbolic'
                : 'media-playback-start-symbolic', () => this.act({do: 'media', action: 'play_pause'})));
            lowTag();
            return;
        }
        this.compact.add_child(new St.Icon({icon_name: st.phone ? 'phone-symbolic' : 'phone-disabled-symbolic',
            icon_size: 14}));
        const pct = st.battery !== undefined && st.battery !== null && !st.low_battery  // azsa sonda kırmızı yazar
            ? ` · %${st.battery}` : '';
        this.compact.add_child(this._label(st.phone ? st.phone + pct : 'Telefon bağlı değil', 'ada-soluk'));
        lowTag();
    }

    _buildPage() {
        this.swatches = [];
        this._clear(this.page);
        if (this.custom) {
            this._customPage();
            return;
        }
        const builders = {arama: () => this._callPage(), calan: () => this._musicPage(), pil: () => this._batteryPage(),
            bildirim: () => this._notifPage(), zamanlayici: () => this._timerPage(), diger: () => this._otherPage()};
        (builders[this.pageName] || builders.calan)();
    }

    _row(...children) {
        const r = new St.BoxLayout({style_class: 'ada-satir'});
        for (const c of children)
            r.add_child(c);
        return r;
    }

    _musicPage() {
        const media = (this.state && this.state.media) || {};
        if (!media.active) {
            this.page.add_child(this._label('Telefonda bir şey çalmıyor', 'ada-soluk'));
            return;
        }
        const texts = new St.BoxLayout({vertical: true, x_expand: true, y_align: Clutter.ActorAlign.CENTER});
        texts.add_child(this._label(media.title, 'ada-baslik'));
        texts.add_child(this._label([media.artist, media.player].filter(Boolean).join(' · '), 'ada-soluk'));
        this.page.add_child(this._row(this._cover(46), texts));
        this.page.add_child(this._wave(310, 20));
        const ctl = this._row(
            this._button('media-skip-backward-symbolic', () => this.act({do: 'media', action: 'previous'})),
            this._button(media.playing ? 'media-playback-pause-symbolic' : 'media-playback-start-symbolic',
                () => this.act({do: 'media', action: 'play_pause'}), 'ada-buyuk-dugme'),
            this._button('media-skip-forward-symbolic', () => this.act({do: 'media', action: 'next'})));
        ctl.x_align = Clutter.ActorAlign.CENTER;
        this.page.add_child(ctl);
    }

    // Telefonun pili azaldı (%15, %10, %5): büyük kırmızı pil, yüzde ve ne yapılacağı.
    _batteryPage() {
        const low = this.state && this.state.low_battery;
        if (!low) {  // bu arada şarja takıldı
            this.pageName = 'calan';
            this._musicPage();
            return;
        }
        const texts = new St.BoxLayout({vertical: true, x_expand: true, y_align: Clutter.ActorAlign.CENTER});
        texts.add_child(this._label(`Telefonun pili %${low.level}`, 'ada-baslik ada-iri ada-pil-az'));
        texts.add_child(this._label(low.weak ? `${low.name} takılı ama şarj yetmiyor · duvar şarjına tak`
            : low.level <= 5 ? `${low.name} birazdan kapanabilir · şarja tak`
            : `${low.name} · şarja tak`, 'ada-soluk'));
        const icon = new St.Icon({icon_name: low.level <= 5 ? 'battery-empty-symbolic' : 'battery-caution-symbolic',
            icon_size: 30, style_class: 'ada-pil-az ada-pil-simge'});
        const r = this._row(icon, texts);
        r.add_style_class_name('ada-pil');
        this.page.add_child(r);
        // Simge yavaşça yanıp söner (sayfa açık kaldıkça). Zamanlayıcıyla: canlandırma anında biterse
        // (ada gizli, "canlandırmaları azalt" açık) bitince yeniden başlatmak sonsuz döngü olurdu.
        this._cancel('pilPulse');
        let bright = true;
        let gone = false;
        icon.connect('destroy', () => {
            gone = true;
        });
        this._timers.pilPulse = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 650, () => {
            if (gone || !icon.get_stage() || this.pageName !== 'pil') {
                delete this._timers.pilPulse;
                return GLib.SOURCE_REMOVE;
            }
            bright = !bright;
            icon.ease({opacity: bright ? 255 : 110, duration: 600, mode: Clutter.AnimationMode.EASE_IN_OUT_SINE});
            return GLib.SOURCE_CONTINUE;
        });
    }

    _callPage() {
        const call = this.state && this.state.call;
        if (!call)
            return;
        const ringing = call.state === 'ringing';
        const texts = new St.BoxLayout({vertical: true, x_expand: true});
        texts.add_child(this._label(call.caller || 'Bilinmeyen', 'ada-baslik ada-iri'));
        texts.add_child(this._label(`${call.app}${ringing ? ' araması' : ' görüşmesi'}`, 'ada-soluk'));
        if (call.hint)  // bilgisayardan basılan "Cevapla"yı telefon yok saydı: dürüstçe söyle
            texts.add_child(this._label(call.hint, 'ada-uyari'));
        this.page.add_child(this._row(new St.Icon({icon_name: 'call-start-symbolic', icon_size: 24,
            style_class: 'ada-yesil'}), texts));
        const btns = this._row();
        btns.x_align = Clutter.ActorAlign.CENTER;
        for (const a of call.actions || []) {
            const press = () => this.act({do: 'call', key: call.key, i: a.i});
            const toggle = callToggle(a.title);
            if (toggle) {  // hoparlör / sessiz: yazı yerine simge; açıkken parlak
                btns.add_child(this._button(toggle.icon, press, toggle.on ? 'ada-acik' : 'ada-kapali'));
                continue;
            }
            const bad = /reddet|kapat|decline|hang|end|sonlandır/i.test(a.title);
            btns.add_child(this._textButton(a.title, press, bad ? 'ada-kirmizi' : 'ada-yesil-dugme'));
        }
        if (!ringing) {
            btns.add_child(this._button('audio-volume-low-symbolic', () => this.act({do: 'call_volume', up: false})));
            btns.add_child(this._button('audio-volume-high-symbolic', () => this.act({do: 'call_volume', up: true})));
        }
        this.page.add_child(btns);
    }

    _otherPage() {
        this.page.add_child(this._label('Diğer', 'ada-baslik'));
        const r = this._row(this._textButton('Özelleştir', () => this._setCustom(true), 'ada-ozellestir'),
            this._textButton('Sorun bildir', () => this.act({do: 'report'}), 'ada-sorun'));
        r.x_align = Clutter.ActorAlign.CENTER;
        this.page.add_child(r);
    }

    // "Konumu değiştir": kilit açılır, ada normal boyda; sağa-sola sürüklenir, "Bitti" ile kilitlenir.
    _setMoving(on) {
        this._morph(() => {
            this.moving = on;
            if (on) {
                this.custom = false;
                this.expanded = false;
                this.thin = false;
                this.peek = false;
                this.page.visible = false;
                this._cancel('collapse');
            }
            this._setClass();
            this._buildCompact();
        });
    }

    _toggle(label, key) {
        const prefs = (this.state && this.state.prefs) || {};
        const on = !!prefs[key];
        const name = this._label(label, 'ada-ayar-ad');
        name.x_expand = true;
        return this._row(name, this._textButton(on ? 'Açık' : 'Kapalı',
            () => this.act({do: 'set', key, value: !on}), `ada-kucuk-metin ada-ayar-${key} ${on ? 'ada-secili' : ''}`));
    }

    _setCustom(on) {
        this._outsideWatch(on);
        this._morph(() => {
            this.custom = on;
            if (on)
                this.expanded = true;
            this.page.visible = this.expanded;
            this._setClass();
            this._buildPage();
            this._buildCompact();
        });
        this._fadeIn(this.page, on ? -6 : 0);
        this._cancel('collapse');
        if (!on && !this.box.hover)
            this._collapseLater(IDLE_COLLAPSE_MS);
    }

    // Tıklanan yer bir düğme ya da düğmenin içi mi (adanın boş yeri değil)?
    _onControl(actor) {
        for (let a = actor; a && a !== this.box; a = a.get_parent()) {
            if (a instanceof St.Button || (a.reactive && a !== this.page && a !== this.compact))
                return true;
        }
        return false;
    }

    // Özelleştir açıkken ekranda adanın dışında bir yere tıklanırsa kapanır (tıklama yerine de ulaşır).
    _outsideWatch(on) {
        if (this._outsideId) {
            global.stage.disconnect(this._outsideId);
            this._outsideId = 0;
        }
        if (!on)
            return;
        this._outsideId = global.stage.connect('captured-event', (_s, e) => {
            if (!this.custom) {  // başka yoldan kapandı (ada küçüldü, arama geldi): izlemeye gerek yok
                this._outsideWatch(false);
                return Clutter.EVENT_PROPAGATE;
            }
            if (e.type() === Clutter.EventType.BUTTON_PRESS) {
                const src = eventActor(e);
                if (!src || !this.box.contains(src))
                    this._setCustom(false);
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    // Özelleştirme: tema ve kip; seçim Talk To'ya gider, ayarlara yazılır, ada hemen değişir. ✕ ile kapanır.
    _customPage() {
        const st = this.state || {};
        const head = this._row(this._label('Adayı özelleştir', 'ada-baslik'));
        const spacer = new St.Widget({x_expand: true});
        head.add_child(spacer);
        head.add_child(this._button('window-close-symbolic', () => this._setCustom(false), 'ada-kapat-ozel'));
        this.page.add_child(head);

        // Temalar: her biri küçük bir ada (süsleri canlı); üstüne gelince adı yazar. Büyük önizlemeler Talk To'da
        // (Ada sekmesi → Ada Place).
        const themes = st.themes || [];
        const current = themes.find(t => t.id === st.theme_id);
        const name = this._label(current ? current.name : '', 'ada-tema-ad');
        const grid = new St.BoxLayout({vertical: true, style_class: 'ada-tema-izgara'});
        grid.x_align = Clutter.ActorAlign.CENTER;
        let row = null;
        themes.forEach((t, i) => {
            if (i % 9 === 0) {
                row = this._row();
                row.add_style_class_name('ada-tema-sira');
                row.x_align = Clutter.ActorAlign.CENTER;
                grid.add_child(row);
            }
            const swatch = new St.Button({style_class: `ada-tema ada-tema-${t.id} ${t.id === st.theme_id ? 'ada-tema-secili' : ''}`,
                can_focus: true, track_hover: true, width: 34, height: 22});
            swatch.set_style(`background-gradient-direction: vertical; background-color: ${t.bg1};` +
                `background-gradient-start: ${t.bg1}; background-gradient-end: ${t.bg2};` +
                `border-bottom: 3px solid ${t.wave1};`);
            if (t.fx && t.fx.length) {
                const area = new St.DrawingArea({x_expand: true, y_expand: true});
                area.connect('repaint', a => {
                    const cr = a.get_context();
                    const [w, h] = a.get_surface_size();
                    // küçük örnekte süsler soluk (yoksa sis gibileri o boyda leke gibi duruyordu)
                    sahnePaint(cr, w, h, this.fxTime(), t.fx, {scale: 0.5, radius: 5, alpha: 0.6});
                    cr.$dispose();
                });
                swatch.set_child(area);
                this.swatches.push(area);
            }
            swatch.connect('notify::hover', () => {
                name.text = swatch.hover ? t.name : current ? current.name : '';
            });
            swatch.connect('clicked', () => this.act({do: 'set', key: 'ada_theme', value: t.id}));
            row.add_child(swatch);
        });
        const head2 = this._row(this._label('Tema', 'ada-soluk'), name);
        head2.add_child(new St.Widget({x_expand: true}));
        head2.add_child(this._textButton('Ada Place', () => this.act({do: 'prefs'}), 'ada-kucuk-metin ada-place'));
        this.page.add_child(head2);
        this.page.add_child(grid);

        this.page.add_child(this._label('Kip', 'ada-soluk'));
        const modes = this._row();
        modes.x_align = Clutter.ActorAlign.CENTER;
        for (const m of st.modes || []) {
            modes.add_child(this._textButton(m.name, () => this.act({do: 'set', key: 'ada_mode', value: m.id}),
                `ada-kip-${m.id} ${m.id === st.mode ? 'ada-secili' : ''}`));
        }
        this.page.add_child(modes);
        const mode = (st.modes || []).find(m => m.id === st.mode);
        if (mode && mode.hint) {
            const hint = this._label(mode.hint, 'ada-soluk ada-ipucu');
            hint.x_align = Clutter.ActorAlign.CENTER;
            this.page.add_child(hint);
        }
        // Hareket: adadan da açılıp kapanır (eski ekran kartlarında Olaylarda ya da Durgun daha az iş yapar)
        this.page.add_child(this._label('Hareket', 'ada-soluk'));
        const motions = this._row();
        motions.x_align = Clutter.ActorAlign.CENTER;
        for (const m of st.motions || []) {
            motions.add_child(this._textButton(m.name, () => this.act({do: 'set', key: 'ada_motion', value: m.id}),
                `ada-kucuk-metin ada-hareket-${m.id} ${m.id === (st.motion || 'canli') ? 'ada-secili' : ''}`));
        }
        this.page.add_child(motions);

        // Sık değiştirilenler; gerisi "Tüm ayarlar"da (Talk To'nun Tercihler penceresi).
        this.page.add_child(this._toggle('Şarkı değişince masaüstü bildirimi de', 'ada_track_popup'));
        this.page.add_child(this._toggle('Zamanlayıcı sayfası', 'ada_timer_page'));
        this.page.add_child(this._label('Geri bildirim', 'ada-soluk'));
        this.page.add_child(this._toggle('Dokunma sesi', 'ada_click_sound'));
        this.page.add_child(this._toggle('Telefonda titreşim', 'phone_vibrate'));
        const end = this._row(this._textButton('Konumu değiştir', () => this._setMoving(true), 'ada-konum'),
            this._textButton('Tüm ayarlar', () => this.act({do: 'prefs'}), 'ada-tum-ayarlar'));
        end.x_align = Clutter.ActorAlign.CENTER;
        this.page.add_child(end);
    }

    _notifPage() {
        const apps = (this.state && this.state.notifications) || [];
        const head = this._row(this._label('Bildirimler', 'ada-baslik'));
        head.add_child(new St.Widget({x_expand: true}));
        if (apps.length)  // adadaki listeyi boşaltır (telefondaki bildirimlere dokunmaz)
            head.add_child(this._textButton('Temizle', () => this.act({do: 'notif_clear'}), 'ada-kucuk-metin ada-temizle'));
        this.page.add_child(head);
        if (!apps.length) {
            this.page.add_child(this._label('Yeni bildirim yok', 'ada-soluk'));
            return;
        }
        for (const n of apps.slice(0, 4)) {
            const icon = n.icon
                ? new St.Icon({gicon: Gio.FileIcon.new(Gio.File.new_for_path(n.icon)), icon_size: 16,
                    style_class: 'ada-uygulama-simge'})
                : new St.Icon({icon_name: 'mail-unread-symbolic', icon_size: 14, style_class: 'ada-uygulama-simge'});
            icon.y_align = Clutter.ActorAlign.CENTER;
            const line = this._label(`${n.app}${n.count > 1 ? ` (${n.count})` : ''}`, 'ada-uygulama');
            const last = this._label(n.last || '', 'ada-soluk');
            last.clutter_text.ellipsize = 3;
            last.x_expand = true;
            // Ne kadar önce geldiği (her saniye yenilenir; dakikada bir değişir).
            const when = this._liveLabel(() => ago(n.time), 'ada-soluk ada-zaman');
            this.page.add_child(this._row(icon, line, last, when));
        }
    }

    _timerPage() {
        const st = this.state || {};
        const timer = st.timer;
        if (timer) {
            const big = this._liveLabel(() => mmss(timer.ends_at - Date.now() / 1000), 'ada-sayac');
            big.x_align = Clutter.ActorAlign.CENTER;
            this.page.add_child(big);
            const where = this._label(timer.phone ? 'Telefonda da kuruldu' : 'Bu bilgisayarda', 'ada-soluk');
            where.x_align = Clutter.ActorAlign.CENTER;
            this.page.add_child(where);
            const r = this._row(this._textButton('İptal', () => this.act({do: 'timer_cancel'}), 'ada-kirmizi'));
            r.x_align = Clutter.ActorAlign.CENTER;
            this.page.add_child(r);
            return;
        }
        this.page.add_child(this._label('Zamanlayıcı', 'ada-baslik'));
        // Telefon bağlıysa varsayılan açık; kullanıcı bir kez değiştirince onun seçimi kalır.
        const onPhone = !!st.phone && this.timerPhone !== false;
        const presets = this._row();
        presets.x_align = Clutter.ActorAlign.CENTER;
        for (const min of [1, 5, 10, 25, 60]) {
            presets.add_child(this._textButton(`${min} dk`, () => this.act({do: 'timer', seconds: min * 60,
                phone: onPhone}), 'ada-sure'));
        }
        this.page.add_child(presets);
        const toggle = this._textButton(onPhone ? '✓ Telefonda da kur' : 'Telefonda da kur', () => {
            this.timerPhone = !onPhone;
            this._buildPage();
        }, onPhone ? 'ada-secili' : '');
        toggle.reactive = !!st.phone;
        const r = this._row(toggle);
        r.x_align = Clutter.ActorAlign.CENTER;
        this.page.add_child(r);
    }

}

export default class AdaExtension extends Extension {
    enable() {
        this._ada = new Ada();
    }

    disable() {
        this._ada.destroy();
        this._ada = null;
    }
}
