// Talk To · Üst ada: ekranın üst ortasında, üst çubuktan aşağı sarkan küçük bir "ada".
//
// Hep küçük durur (çalan şarkı, dalga); arama, şarkı değişimi ya da bildirim olunca büyür. Basılı tutup yana
// sürükleyince sayfa değişir: arama ← çalan → bildirimler → zamanlayıcı. Yukarı kaydırınca (tekerlek, dokunmatik
// yüzey ya da yukarı sürükleme) bir kademe küçülür: büyük → normal → ince şerit. İnce şeridin üstüne gelince normal
// hâli görünür, tıklayınca normale döner. İnce şeritteyken yalnızca arama adayı büyütür. Veriyi Talk To Android'den D-Bus ile
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
const SPILL_PAD = 26;      // taşan su adanın iki yanından bu kadar dışarı taşar
const SPILL_H = 60;
const SCROLL_COOLDOWN_MS = 350; // dokunmatik yüzeyin tek kaydırması birden çok kademe atlamasın
const PEEK_LEAVE_MS = 450;      // ince şeritten fare ayrılınca normal hâlin kalma süresi
const SHOW_EVENT_MS = 5000; // şarkı/bildirim olunca büyük kalma süresi
const IDLE_COLLAPSE_MS = 6000;
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

    _paint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        const t = Date.now() / 1000;
        const th = this.ada.theme;
        const energy = Math.max(0, Math.min(1, (this.ada.amp - 0.05) / 0.17));
        // Süs "vurgu": birkaç yavaş sinüsün bileşimi; çalarken çalkalanır, duraklayınca durulur.
        const beat = 0.55 + 0.45 * Math.pow(Math.abs(Math.sin(t * 2.3)), 3) * (0.6 + 0.4 * Math.sin(t * 0.7));
        const pad = SPILL_PAD;
        const bell = x => {
            const u = Math.max(0, Math.min(1, (x - pad * 0.4) / (w - pad * 0.8)));
            return Math.pow(Math.sin(Math.PI * u), 1.3);
        };
        const layers = [[th.wave2, 0.5, 1.0, 0.0, 1.0], [th.wave1, 0.85, 1.5, 1.9, 0.72]];
        for (const [color, alpha, speed, shift, scale] of layers) {
            const max = h * scale * (0.2 + 0.65 * energy * beat);
            cr.moveTo(0, 0);
            for (let x = 0; x <= w; x += 3) {
                const ripple = 0.75 + 0.25 * Math.sin(x / w * Math.PI * 6 + t * 3 * speed + shift);
                cr.lineTo(x, max * bell(x) * ripple);
            }
            cr.lineTo(w, 0);
            cr.closePath();
            const g = new Cairo.LinearGradient(0, 0, 0, Math.max(1, max));
            const [r, gg, b] = rgba(color, 1);
            g.addColorStopRGBA(0, r, gg, b, alpha);
            g.addColorStopRGBA(1, r, gg, b, alpha * 0.25);
            cr.setSource(g);
            cr.fill();
        }
        if (energy > 0.3) {  // taşan sudan düşen birkaç damla
            const [r, gg, b] = rgba(th.wave2, 1);
            for (let i = 0; i < 3; i++) {
                const p = (t * (0.55 + i * 0.17) + i * 0.37) % 1;
                const x = pad + (w - 2 * pad) * (0.2 + 0.3 * i) + Math.sin(t + i) * 6;
                cr.arc(x, h * 0.35 + p * h * 0.65, 1.6 + energy, 0, 2 * Math.PI);
                cr.setSourceRGBA(r, gg, b, 0.7 * (1 - p) * energy);
                cr.fill();
            }
        }
        cr.$dispose();
    }

    repaint() {
        this.actor.queue_repaint();
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
        const amp = h * this.ada.amp;  // çalarken 0.22, duraklayınca 0.05; arada yumuşak geçer
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
        // GNOME bildirimleri de ekranın üst ortasında çıkar: adanın altında kalmasınlar, üstünde görünsünler.
        for (const actor of [this.spill.actor, this.box])
            this._belowTray(actor);
        this._sigs = [
            [this.box, this.box.connect('notify::width', () => this._place())],
            [this.box, this.box.connect('notify::height', () => this._place())],
            [this.box, this.box.connect('notify::scale-x', () => this._place())],
            [Main.layoutManager, Main.layoutManager.connect('monitors-changed', () => this._place())],
            // Olaylar düğmelerden önce görülür: sürükleme bir düğmenin üstünden başlasa da sayfa değişsin.
            [this.box, this.box.connect('captured-event', (a, e) => this._captured(e))],
            [this.box, this.box.connect('button-release-event', (a, e) => this._release(e))],
            [this.box, this.box.connect('notify::hover', () => this._hoverChanged())],
            [this.box, this.box.connect('scroll-event', (a, e) => this._scroll(e))],
        ];

        this._watch = Gio.bus_watch_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameWatcherFlags.NONE,
            () => this._connect(), () => this._lost());
    }

    destroy() {
        Gio.bus_unwatch_name(this._watch);
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
            proxy.GetStateRemote(([json], err) => {
                if (!err)
                    this._update(json);
            });
        });
    }

    _lost() {
        this._proxy = null;
        this.state = null;
        this.box.visible = false;
        this._animate(false);
    }

    act(obj) {
        if (this._proxy)
            this._proxy.ActionRemote(JSON.stringify(obj), () => {});
    }

    _update(json) {
        let st;
        try {
            st = JSON.parse(json);
        } catch (e) {
            return;
        }
        const prev = this.state && this.state.media;
        this.state = st;
        this.theme = Object.assign({}, DEFAULT_THEME, st.theme || {});
        if (!this.moving)  // sürüklerken Talk To'nun eski değeri araya girmesin
            this.offset = st.offset || 0;
        this.playing = !!(st.media && st.media.active && st.media.playing);
        this.loading = !!(st.media && st.media.active && st.media.loading);
        this.box.set_style(`background-gradient-direction: vertical; background-color: ${this.theme.bg1};` +
            `background-gradient-start: ${this.theme.bg1}; background-gradient-end: ${this.theme.bg2};` +
            `color: ${this.theme.text};`);
        this.box.visible = st.enabled !== false;
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
        if (newTrack)  // yeni şarkı: yazılar hafifçe kayarak belirir (hiç boş görünmeden)
            this._fadeIn(this.compact, -3, 110);
        this._animate((this.playing || this.loading) && this.box.visible);
        this._spillUpdate();
    }

    _onEvent(kind) {
        const page = {call: 'arama', track: 'calan', notification: 'bildirim'}[kind];
        if (!page)
            return;
        if (this.thin && kind !== 'call')
            return; // ince şeritte yalnızca arama büyütür
        if (this.custom || this.moving) {  // özelleştirirken / konum değiştirirken yalnızca arama araya girer
            if (kind !== 'call')
                return;
            this.custom = false;
            this.moving = false;
        }
        this.pageName = page;
        this._expand(true);
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
        const s = this.spill.actor;
        s.set_size(Math.round(this.box.width * this.box.scale_x) + 2 * SPILL_PAD, SPILL_H);
        s.set_position(Math.round(cx - s.width / 2),
            m.y + top + Math.round(this.box.height * this.box.scale_y) - 3);
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
        const list = this.state && this.state.call ? ['arama'] : [];
        return list.concat(['calan', 'bildirim', 'zamanlayici', 'diger']);
    }

    _setClass() {
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
        this._morph(() => {
            this.expanded = on;
            if (!on)
                this.custom = false;
            this.page.visible = on;
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
        // Üstüne gelince hafifçe kabarır.
        this.box.ease({scale_x: this.box.hover ? 1.02 : 1, scale_y: this.box.hover ? 1.02 : 1, duration: 160,
            mode: Clutter.AnimationMode.EASE_OUT_QUAD});
        if (this.box.hover)
            this._cancel('collapse');
        else if (this.expanded)
            this._collapseLater(IDLE_COLLAPSE_MS);
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
        let up = false;
        const dir = event.get_scroll_direction();
        if (dir === Clutter.ScrollDirection.UP) {
            up = true;
        } else if (dir === Clutter.ScrollDirection.SMOOTH) {
            const [, dy] = event.get_scroll_delta();
            this._scrollSum = dy < 0 ? this._scrollSum + dy : 0;
            up = this._scrollSum <= -1;
        }
        if (!up)
            return Clutter.EVENT_PROPAGATE;
        const now = GLib.get_monotonic_time() / 1000;
        if (now - this._scrollAt > SCROLL_COOLDOWN_MS) {
            this._scrollAt = now;
            this._scrollSum = 0;
            this._shrink();
        }
        return Clutter.EVENT_STOP;
    }

    // ---- dalga canlandırması -----------------------------------------------------------

    // Çalarken dalga akar; duraklayınca yavaşlayıp durulur (birden donmaz), sonra çizim durur.
    _animate(on) {
        this.waveOn = on;
        if (this._timers.wave)
            return;
        this._timers.wave = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 40, () => {
            const target = this.loading ? 0.1 : this.waveOn ? 0.22 : 0.05;
            this.amp += (target - this.amp) * 0.08;
            this.phase += 0.03 + 0.09 * ((this.amp - 0.05) / 0.17);
            for (const w of this.waves)
                w.repaint();
            this._spillUpdate();
            if (!this.waveOn && Math.abs(this.amp - target) < 0.002) {
                this.amp = target;
                this._spillUpdate();
                delete this._timers.wave;
                return GLib.SOURCE_REMOVE;
            }
            return GLib.SOURCE_CONTINUE;
        });
    }

    // ---- canlandırmalar ----------------------------------------------------------------

    // Boyut değişimi (büyüme, küçülme, ince şerit, sayfa) yumuşak olsun: önce eski boyutta sabitlenir,
    // içerik yenilenir, sonra yeni doğal boyuta kayar.
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
            }
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
        } else if (this.custom) {  // özelleştirme panelinde boş yere tıklama/sürükleme bir şey yapmaz
            this._springBack();
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
            this.compact.add_child(this._wave(64, 6));
            return;
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
                this.compact.add_child(new St.Icon({icon_name: `battery-level-${lvl}${st.charging
                    ? '-charging' : ''}-symbolic`, icon_size: 14}));
                this.compact.add_child(this._label(`%${st.battery}`, 'ada-soluk'));
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
        if (st.timer && !media.playing) {
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
            this.compact.add_child(this._wave(44, 14));
            this.compact.add_child(this._button(media.playing ? 'media-playback-pause-symbolic'
                : 'media-playback-start-symbolic', () => this.act({do: 'media', action: 'play_pause'})));
            return;
        }
        this.compact.add_child(new St.Icon({icon_name: st.phone ? 'phone-symbolic' : 'phone-disabled-symbolic',
            icon_size: 14}));
        this.compact.add_child(this._label(st.phone ? st.phone + (st.battery !== undefined && st.battery !== null
            ? ` · %${st.battery}` : '') : 'Telefon bağlı değil', 'ada-soluk'));
        this.compact.add_child(this._wave(34, 12));
    }

    _buildPage() {
        this._clear(this.page);
        if (this.custom) {
            this._customPage();
            return;
        }
        const builders = {arama: () => this._callPage(), calan: () => this._musicPage(),
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

    // Özelleştirme: tema ve kip; seçim Talk To'ya gider, ayarlara yazılır, ada hemen değişir. ✕ ile kapanır.
    _customPage() {
        const st = this.state || {};
        const head = this._row(this._label('Adayı özelleştir', 'ada-baslik'));
        const spacer = new St.Widget({x_expand: true});
        head.add_child(spacer);
        head.add_child(this._button('window-close-symbolic', () => this._setCustom(false), 'ada-kapat-ozel'));
        this.page.add_child(head);

        this.page.add_child(this._label('Tema', 'ada-soluk'));
        const themes = this._row();
        themes.x_align = Clutter.ActorAlign.CENTER;
        for (const t of st.themes || []) {
            const box = new St.BoxLayout({vertical: true, style_class: 'ada-tema-kutu'});
            const swatch = new St.Button({style_class: `ada-tema ada-tema-${t.id} ${t.id === st.theme_id ? 'ada-tema-secili' : ''}`,
                can_focus: true, width: 46, height: 30});
            swatch.set_style(`background-gradient-direction: vertical; background-color: ${t.bg1};` +
                `background-gradient-start: ${t.bg1}; background-gradient-end: ${t.bg2};` +
                `border-bottom: 5px solid ${t.wave1};`);
            swatch.connect('clicked', () => this.act({do: 'set', key: 'ada_theme', value: t.id}));
            box.add_child(swatch);
            const name = this._label(t.name, 'ada-tema-ad');
            name.x_align = Clutter.ActorAlign.CENTER;
            box.add_child(name);
            themes.add_child(box);
        }
        this.page.add_child(themes);

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

        // Sık değiştirilenler; gerisi "Tüm ayarlar"da (Talk To'nun Tercihler penceresi).
        this.page.add_child(this._toggle('Şarkı değişince masaüstü bildirimi de', 'ada_track_popup'));
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
            this.page.add_child(this._row(icon, line, last));
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
