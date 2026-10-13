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
// Canlandırma saati: dalga ve süsler aynı karede çizilir. Kare sayısı neye gerekiyorsa o kadar: dalga 20, hızlı
// düşen süsler (kar, yağmur, yaprak...) 20, ağır süzülenler (sis, bulut, yıldız...) daha az. "Yavaş"ta yarısı.
const WAVE_FPS = 20;
const SWATCH_FPS = 12;
const FX_FPS = {clouds: 12, fog: 10, stars: 12, aurora: 15, fireflies: 15, neon: 10, glint: 15, lightning: 15,
    snow: 20, petals: 20, bubbles: 20, hearts: 20, rain: 20};
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
            const g = new Cairo.LinearGradient(0, 0, 0, bh);
            g.addColorStopRGBA(0, r1, g1, b1, 0.9);
            g.addColorStopRGBA(1, r2, g2, b2, 0.8);
            cr.setSource(g);
            cr.fill();
            // Akan parıltılar: yan akıntıdan aşağı kayar.
            for (let i = 0; i < 2; i++) {
                const p = (t * (0.9 + 0.35 * i) + i * 0.5) % 1;
                const y = p * (bh - R);
                cr.moveTo(x0 + side * sw * 0.45, y);
                cr.lineTo(x0 + side * sw * 0.45, y + 4 + 3 * energy);
                cr.setLineWidth(1);
                cr.setSourceRGBA(1, 1, 1, 0.4 * energy * (1 - p * 0.7));
                cr.stroke();
            }
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

// Süslü temalarda adanın zemini: renk geçişi ve süsler (bulut, sis, yıldız...) adanın tam altındaki bu katmanda
// çizilir, ada saydamdır; yazılar ve düğmeler süslerin üstünde net kalır. Tıklamaları almaz. Süsler büyükken
// soluklaşır, aramada ve ince şeritte çekilir (zemin kalır).
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
            sahnePaint(cr, w, h, this.ada.fxTime(), this.ada.theme.fx || [],
                {radius: this.radius, alpha: this.ada.expanded ? 0.55 : 1});
        }
        cr.$dispose();
    }

    repaint() {
        this.actor.queue_repaint();
    }
}

// Deniz: iki katlı dalga; çalarken akar, duraklayınca neredeyse durgun.
class Wave {
    // edge: adanın sol ucunda; sol alt köşesi adanınki gibi yuvarlak kırpılır, su ucu doldurur.
    constructor(width, height, ada, edge = false) {
        this.ada = ada;
        this.edge = edge;
        this.actor = new St.DrawingArea({width, height, style_class: 'ada-wave'});
        this.actor.connect('repaint', area => this._paint(area));
    }

    _paint(area) {
        const cr = area.get_context();
        const [w, h] = area.get_surface_size();
        const t = this.ada.theme;
        const amp = h * this.ada.amp;
        if (this.edge) {
            const r = Math.min(h / 2, this.ada.sky.radius || 18);
            cr.moveTo(0, 0);
            cr.lineTo(w, 0);
            cr.lineTo(w, h);
            cr.lineTo(r, h);
            cr.arc(r, h - r, r, Math.PI / 2, Math.PI);
            cr.closePath();
            cr.clip();
        }  // çalarken 0.22, duraklayınca 0.05; arada yumuşak geçer
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
            if (this.edge) {  // uçtaki su sağa doğru erir: adaya eklenmiş değil, adanın içinde gibi
                const [r, g, b] = rgba(color, 1);
                const grad = new Cairo.LinearGradient(0, 0, w, 0);
                grad.addColorStopRGBA(0, r, g, b, alpha);
                grad.addColorStopRGBA(0.55, r, g, b, alpha * 0.75);
                grad.addColorStopRGBA(1, r, g, b, 0);
                cr.setSource(grad);
            } else {
                cr.setSourceRGBA(...rgba(color, alpha));
            }
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
        // GNOME bildirimleri de ekranın üst ortasında çıkar: adanın altında kalmasınlar, üstünde görünsünler.
        // Sıra (alttan): taşan su, süslü zemin, ada, bildirimler.
        for (const actor of [this.spill.actor, this.sky.actor, this.box])
            this._belowTray(actor);
        this._sigs = [
            [this.box, this.box.connect('notify::width', () => this._place())],
            [this.box, this.box.connect('notify::height', () => this._place())],
            [this.box, this.box.connect('notify::scale-x', () => this._place())],
            [this.box, this.box.connect('notify::opacity', () => {
                this.sky.actor.opacity = this.box.opacity;
            })],
            [this.box, this.box.connect('notify::translation-x', () => {  // sallanınca zemin de sallansın
                this.sky.actor.translation_x = this.box.translation_x;
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
        if ((this.theme.fx || []).length) {  // zemini alttaki katman çizer (süsler yazının altında kalsın)
            this.box.set_style(`background-color: transparent; color: ${this.theme.text};`);
        } else {
            this.box.set_style(`background-gradient-direction: vertical; background-color: ${this.theme.bg1};` +
                `background-gradient-start: ${this.theme.bg1}; background-gradient-end: ${this.theme.bg2};` +
                `color: ${this.theme.text};`);
        }
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
        this._skyUpdate();
    }

    _onEvent(kind) {
        const page = {call: 'arama', track: 'calan', notification: 'bildirim', pil: 'pil'}[kind];
        if (!page)
            return;
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
        return st.motion || 'canli';
    }

    fxTime() {
        const m = this._fxMotion();
        if (m === 'durgun')
            return 8;  // süsler dağılmış hâlde durur
        const t = GLib.get_monotonic_time() / 1e6 - this._fx0;
        return 8 + (m === 'yavas' ? t * 0.5 : t);
    }

    // Süslü temada zemin katmanı ada görünürken hep görünür; süsler aramada ve ince şeritte çekilir (dikkat
    // dağıtmasın), zemin kalır.
    _skyUpdate() {
        const st = this.state || {};
        const fx = (this.theme && this.theme.fx) || [];
        const thinShown = this.thin && !this.peek && !this.expanded;
        this.sky.actor.visible = fx.length > 0 && this.box.visible;
        this.skyOn = this.sky.actor.visible && !st.call && !thinShown;
        this.sky.actor.opacity = this.box.opacity;
        this.sky.repaint();
        this._anim();
    }

    // ---- canlandırma saati --------------------------------------------------------------

    // Tek saat: dalga, taşan su, süsler ve Özelleştir'deki mini adalar aynı karede çizilir (ayrı saatler kabuğu
    // saniyede daha çok kare çizmeye zorlar). Saniyede kaç kare: o an gereken en çok (bkz. WAVE_FPS, FX_FPS).
    // Kimse bakmıyorsa hiç çalışmaz: ada görünmüyor (tam ekran), ekran kilitli, kullanıcı bir süredir dokunmuyor,
    // Durgun / güç tasarrufu (dalga yerinde durur, süsler resim gibi).
    _fps() {
        if (!this.box.visible || !this.box.mapped || Main.sessionMode.isLocked || this.idle)
            return 0;
        const motion = this._fxMotion();
        if (motion === 'durgun')
            return 0;
        const target = this.loading ? 0.1 : this.waveOn ? 0.22 : 0.05;
        const wave = this.waveOn || Math.abs(this.amp - target) > 0.002 ? WAVE_FPS : 0;
        let fx = 0;
        if (this.skyOn) {
            for (const f of this.theme.fx || [])
                fx = Math.max(fx, FX_FPS[f.type] || 12);
            if (this.expanded)  // büyükken süslerin alanı büyük, kendileri soluk: daha seyrek çizilir
                fx = Math.round(fx / 2);
        }
        const swatch = this.custom && this.expanded && this.swatches.length ? SWATCH_FPS : 0;
        const fps = Math.max(wave, fx, swatch);
        return motion === 'yavas' ? Math.round(fps / 2) : fps;
    }

    _anim() {
        const fps = this._fps();
        if (this._timers.anim && fps === this._animFps)
            return;
        if (this._timers.anim) {
            GLib.source_remove(this._timers.anim);
            delete this._timers.anim;
        }
        this._animFps = fps;
        if (!fps) {
            this._settleWave();
            return;
        }
        this._animLast = GLib.get_monotonic_time() / 1e6;
        this._timers.anim = GLib.timeout_add(GLib.PRIORITY_DEFAULT, Math.round(1000 / fps), () => this._frame());
    }

    _frame() {
        const now = GLib.get_monotonic_time() / 1e6;
        const k = Math.min(6, (now - this._animLast) / 0.04);  // eski 40 ms'lik adımlara göre
        this._animLast = now;
        const target = this.loading ? 0.1 : this.waveOn ? 0.22 : 0.05;
        if (this.waveOn || Math.abs(this.amp - target) > 0.002) {
            // Çalarken dalga akar; duraklayınca yavaşlayıp durulur (birden donmaz).
            this.amp += (target - this.amp) * (1 - Math.pow(0.92, k));
            this.phase += (0.03 + 0.09 * ((this.amp - 0.05) / 0.17)) * k;
            if (!this.waveOn && Math.abs(this.amp - target) <= 0.002)
                this.amp = target;
            for (const w of this.waves)
                w.repaint();
            this._spillUpdate();
        }
        if (this.skyOn)
            this.sky.repaint();
        for (const a of this.swatches)
            a.queue_repaint();
        if (this._fps() !== this._animFps) {
            delete this._timers.anim;
            this._animFps = -1;
            this._anim();
            return GLib.SOURCE_REMOVE;
        }
        return GLib.SOURCE_CONTINUE;
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

    _wave(width, height, edge = false) {
        const w = new Wave(width, height, this, edge);
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
        this.box.remove_style_class_name('ada-sol-su');
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
                const low = st.low_battery ? ' ada-pil-az' : '';
                this.compact.add_child(new St.Icon({icon_name: `battery-level-${lvl}${st.charging
                    ? '-charging' : ''}-symbolic`, icon_size: 14, style_class: low.trim()}));
                this.compact.add_child(this._label(`%${st.battery}`, `ada-soluk${low}`));
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
            this.compact.add_child(new St.Icon({icon_name: 'battery-caution-symbolic', icon_size: 13,
                style_class: 'ada-pil-az'}));
            this.compact.add_child(this._label(`%${st.low_battery.level}`, 'ada-pil-az ada-kucuk-metin'));
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
            this.compact.add_child(this._wave(44, 14));
            this.compact.add_child(this._button(media.playing ? 'media-playback-pause-symbolic'
                : 'media-playback-start-symbolic', () => this.act({do: 'media', action: 'play_pause'})));
            lowTag();
            return;
        }
        // Bir şey çalmıyor: dalga adanın sol ucunda, kenara yaslı; ucu dolduran durgun su gibi (adanın parçası).
        this.box.add_style_class_name('ada-sol-su');
        this.compact.add_child(this._wave(30, 29, true));
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
                    sahnePaint(cr, w, h, this.fxTime(), t.fx, {scale: 0.5, radius: 5});
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
