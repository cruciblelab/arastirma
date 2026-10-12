"""Üst ada: GNOME Shell eklentisine (gnome-ada) köprü, zamanlayıcı ve eklentinin kurulumu.

Eklenti ekranın üst ortasında, üst çubuktan sarkan küçük bir "ada" çizer; veriyi buradan alır. Uygulamanın kendi
D-Bus adında (lab.crucible.TalkToAndroid) bir nesne yayımlanır:

    /lab/crucible/TalkToAndroid/Ada  lab.crucible.TalkToAndroid.Ada
        GetState() → s     durum (JSON)
        Action(s)           eklentideki düğme (JSON: {"do": "media" | "call" | "call_volume" | "timer" | ...})
        Changed(s)          durum değişti (JSON)

Durum: tema, telefon ve pil, çalan (kapak dosyası dahil), süren arama, uygulamalara göre bildirimler, zamanlayıcı
ve "olay" (track / call / notification: eklenti büyüyüp o sayfayı gösterir). Eklenti yalnızca gösterir.

Neden eklenti: Wayland'de uygulama penceresi kendini ekranın bir yerine sabitleyemez ve her şeyin üstünde
tutamaz; GNOME'un kendi kabuğuna eklenen eklenti tutabilir. Bedeli: ilk kurulumda bir kez oturumu kapatıp açmak.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from gi.repository import Gio, GLib

from .. import arama, pil

log = logging.getLogger("talkto.ada")

UUID = "talkto-ada@crucible.lab"
PATH = "/lab/crucible/TalkToAndroid/Ada"
IFACE = "lab.crucible.TalkToAndroid.Ada"
XML = f"""<node><interface name="{IFACE}">
  <method name="GetState"><arg type="s" direction="out"/></method>
  <method name="Action"><arg type="s" direction="in"/></method>
  <signal name="Changed"><arg type="s"/></signal>
</interface></node>"""

THEMES = {
    "deniz": ("Deniz", {"bg1": "#0a2342", "bg2": "#12436b", "wave1": "#2ec4b6", "wave2": "#8de4ff", "text": "#eaf6ff"}),
    "gece": ("Gece", {"bg1": "#0f0f14", "bg2": "#1d1b2e", "wave1": "#7f5af0", "wave2": "#2cb67d", "text": "#f2f0ff"}),
    "gunbatimi": ("Gün batımı", {"bg1": "#2b1055", "bg2": "#7a2e5c", "wave1": "#ff9e5e", "wave2": "#ffd166",
                                 "text": "#fff4e6"}),
    "orman": ("Orman", {"bg1": "#0b2b1c", "bg2": "#154734", "wave1": "#52b788", "wave2": "#b7e4c7", "text": "#eefaf2"}),
}
MODES = {
    "sakin": ("Sakin", "Dalga yalnızca adanın içinde."),
    "tasan": ("Taşan dalgalar", "Çalarken su adadan taşar (süs, gerçek ses değil)."),
}
BOOL_PREFS = ("ada_track_popup", "ada_click_sound", "phone_vibrate")  # adadan açılıp kapanabilen ayarlar
HUB_PREFS = ("phone_vibrate",)  # telefona da gidenler
MAX_OFFSET = 4000
NOTIF_KEEP = 3600  # bildirim sayfasında son bir saatin bildirimleri
MEDIA_GRACE = 3.0  # şarkı değişirken telefon bir anlığına "çalmıyor" diyebilir: ada o arada boşa düşmesin


class AdaService:
    def __init__(self, app):
        self.app = app
        self.seq = 1
        self.event = "start"
        self.call = None
        self.notifs: dict[str, dict] = {}  # uygulama → {"keys": {anahtar: zaman}, "last": metin, "time": zaman}
        self.status: dict = {}
        self.timer = None  # {"ends_at", "total", "phone", "device_id", "source"}
        self._last_media = None  # son gösterilen çalan (şarkılar arası boşlukta gösterilir)
        self._grace_id = 0
        self.seen = False  # eklenti bu çalışmada Talk To'ya bağlandı (durumu istedi): ada ekranda
        self._emit_id = 0
        self._reg = 0
        self.conn = app.get_dbus_connection()
        if self.conn is None:
            return
        try:
            self._reg = self.conn.register_object(PATH, Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],
                                                  self._method, None, None)
        except GLib.Error as e:
            log.warning("ada D-Bus nesnesi yayımlanamadı: %s", e.message)

    def showing(self) -> bool:
        """Üst ada ekranda mı (eklenti bağlandı ve "Göster" açık): mini oynatıcı kendiliğinden açılmaz."""
        return self.seen and bool(self.app.config["ada_enabled"])

    def stop(self):
        if self._grace_id:
            GLib.source_remove(self._grace_id)
            self._grace_id = 0
        if self._reg and self.conn:
            self.conn.unregister_object(self._reg)
            self._reg = 0

    # ---- D-Bus ---------------------------------------------------------------------------

    def _method(self, _conn, _sender, _path, _iface, method, params, inv):
        if method == "GetState":
            self.seen = True
            inv.return_value(GLib.Variant("(s)", (json.dumps(self.state(), ensure_ascii=False),)))
            return
        self.seen = True  # eklenti bir düğmeye bastıysa ekrandadır
        try:
            self.action(json.loads(params.unpack()[0]))
        except (ValueError, TypeError, KeyError) as e:
            log.info("ada eylemi anlaşılmadı: %s", e)
        inv.return_value(None)

    def changed(self, event=None):
        """Durum değişti; olay varsa eklenti büyüyüp ilgili sayfayı açar. Sık güncellemeler birleştirilir."""
        if event:
            self.seq += 1
            self.event = event
        if not self._emit_id:
            self._emit_id = GLib.timeout_add(80, self._emit)

    def _emit(self):
        self._emit_id = 0
        if self._reg and self.conn:
            try:
                self.conn.emit_signal(None, PATH, IFACE, "Changed",
                                      GLib.Variant("(s)", (json.dumps(self.state(), ensure_ascii=False),)))
            except GLib.Error as e:
                log.info("ada sinyali gönderilemedi: %s", e.message)
        return False

    # ---- durum ------------------------------------------------------------------------------

    def state(self) -> dict:
        cfg = self.app.config
        sessions = self.status.get("sessions") or []
        phone = sessions[-1] if sessions else None
        did, media = self.app.now.shown()
        art = self.app.art_paths.get((media or {}).get("art_id") or "")
        m = None
        if did and media.get("active"):
            m = {k: media.get(k) for k in ("title", "artist", "player", "playing", "position_ms", "duration_ms")}
            m.update(active=True, art=art if art and os.path.exists(art) else None, device_id=did)
            self._last_media = m
        elif self._last_media and self._in_gap(self._last_media["device_id"]):
            m = dict(self._last_media)  # kısa boşlukta son şarkı kalır ("yükleniyor"); süre dolunca yeniden bakılır
            if not self._grace_id:
                self._grace_id = GLib.timeout_add(int(MEDIA_GRACE * 1000) + 100, self._grace_over)
        if m is not None:  # şarkılar arası geçiş: çalmıyor gibi değil, hafif "yükleniyor" görünsün
            m["loading"] = self.app.now.loading(m.get("device_id"))
        cutoff = time.time() - NOTIF_KEEP
        apps = [{"app": a, "count": len(v["keys"]), "last": v["last"],
                 "icon": v.get("icon") if v.get("icon") and os.path.exists(v["icon"]) else None} for a, v in
                sorted(self.notifs.items(), key=lambda kv: -kv[1]["time"]) if v["keys"] and v["time"] >= cutoff]
        timer = None
        if self.timer:
            timer = {k: self.timer[k] for k in ("ends_at", "total", "phone")}
        takip = getattr(self.app, "pil", None)  # takılı ama şarj yetmiyor mu (pil düşüyor)
        weak = {x["device_id"]: bool(takip and takip.weak(x["device_id"])) for x in self.status.get("sessions", [])}
        low = [x for x in self.status.get("sessions", []) if pil.is_low(x.get("battery"), weak[x["device_id"]])]
        low.sort(key=lambda x: x["battery"]["level"])
        return {
            "low_battery": {"device_id": low[0]["device_id"], "name": low[0].get("name") or "Telefon",
                            "level": low[0]["battery"]["level"], "weak": weak[low[0]["device_id"]]}
            if low else None,
            "enabled": bool(cfg["ada_enabled"]),
            "theme": THEMES.get(cfg["ada_theme"], THEMES["deniz"])[1],
            "theme_id": cfg["ada_theme"] if cfg["ada_theme"] in THEMES else "deniz",
            "themes": [dict(colors, id=k, name=name) for k, (name, colors) in THEMES.items()],
            "mode": cfg["ada_mode"] if cfg["ada_mode"] in MODES else "sakin",
            "modes": [{"id": k, "name": name, "hint": hint} for k, (name, hint) in MODES.items()],
            "prefs": {k: bool(cfg[k]) for k in BOOL_PREFS},
            "offset": int(cfg["ada_offset"] or 0),
            "phone": phone["name"] if phone else None,
            "battery": (phone.get("battery") or {}).get("level") if phone else None,
            "charging": bool((phone.get("battery") or {}).get("charging")) if phone else False,
            "media": m,
            "call": self.call,
            "notifications": apps,
            "timer": timer,
            "event": {"kind": self.event, "seq": self.seq},
        }

    def on_event(self, event, d):
        if event == "status":
            self.status = d
            live = {s["device_id"] for s in d.get("sessions", [])}
            if self.call and self.call["device_id"] not in live:
                self.call = None
            self.changed()
        elif event in ("media", "media_art"):  # kapak şarkıdan sonra gelir: gelince ada da yenilensin
            self.changed()
        elif event == "call":
            new = not self.call or self.call.get("key") != d["key"] or self.call.get("state") != d["state"]
            since = self.call.get("since") if self.call and self.call.get("key") == d["key"] else None
            if d["state"] != "ringing" and not since:
                since = time.time()
            hint = self.call.get("hint") if self.call and not new else None
            self.call = {"device_id": d["device_id"], "key": d["key"], "app": d.get("app"),
                         "caller": d.get("caller"), "state": d["state"], "since": since,
                         "actions": [{"i": a["i"], "title": a["title"]} for a in d.get("actions", [])[:3]]}
            self._hint(hint)
            self.changed("call" if new else None)
        elif event == "call_ended":
            if self.call and self.call.get("key") == d.get("key"):
                self.call = None
                self.changed()
        elif event == "notification":
            app = d.get("app") or "Bildirim"
            entry = self.notifs.setdefault(app, {"keys": {}, "last": "", "time": 0})
            now = time.time()
            entry["keys"][f"{d['device_id']}|{d['key']}"] = now
            entry["last"] = ": ".join(x for x in (d.get("title"), d.get("text")) if x)[:200]
            if d.get("icon"):
                entry["icon"] = d["icon"]  # uygulamanın simgesi (telefondan gelir, önbellekte dosya)
            entry["time"] = now
            self.changed("notification")
        elif event == "notification_removed":
            k = f"{d['device_id']}|{d['key']}"
            for entry in self.notifs.values():
                entry["keys"].pop(k, None)
            self.changed()

    def _in_gap(self, did) -> bool:
        """Telefon az önce (MEDIA_GRACE içinde) "çalmıyor" dedi: şarkılar arası boşluk olabilir."""
        gone = self.app.now.gone.get(did)
        return bool(gone) and self.app.now.clock() - gone[0] < MEDIA_GRACE

    def _grace_over(self):
        self._grace_id = 0
        self.changed()
        return False

    def answer_failed(self, did, key):
        """Bilgisayardan basılan "Cevapla" işe yaramadı: ada bunu söyler, düğmeyi kaldırır."""
        if self.call and self.call["device_id"] == did and self.call["key"] == key and self.call["state"] == "ringing":
            self._hint(arama.FAILED)
            self.changed("call")

    def _hint(self, hint):
        self.call["hint"] = hint
        if hint:
            self.call["actions"] = [a for a in self.call["actions"] if not arama.is_answer(a["title"])]

    def battery_alert(self, device_id):
        """Telefonun pili bir eşiğe indi (%15, %10, %5): ada belirir ve söyler."""
        self.changed("pil")

    def on_track(self):
        self.changed("track")

    # ---- eylemler ---------------------------------------------------------------------------

    def action(self, a: dict):
        what = a.get("do")
        did = (self.app.now.shown()[0]) if what == "media" else None
        if what == "media" and did and a.get("action") in ("play_pause", "next", "previous", "play", "pause"):
            self.app.call("media_control", did, a["action"], None)
        elif what == "call" and self.call and a.get("key") == self.call["key"]:
            self.app.call("call_action", self.call["device_id"], self.call["key"], int(a.get("i", -1)))
        elif what == "call_volume" and self.call:
            self.app.call("call_volume", self.call["device_id"], bool(a.get("up")))
        elif what == "timer":
            self.start_timer(int(a.get("seconds", 0)), bool(a.get("phone")))
        elif what == "timer_cancel":
            self.cancel_timer()
        elif what == "open":
            self.app.present()
        elif what == "set":  # adadaki özelleştirme: yalnızca bilinen ayarlar ve değerler
            key, value = a.get("key"), a.get("value")
            allowed = {"ada_theme": THEMES, "ada_mode": MODES}
            ok = ((key in allowed and isinstance(value, str) and value in allowed[key])
                  or (key in BOOL_PREFS and isinstance(value, bool))
                  or (key == "ada_offset" and isinstance(value, int) and not isinstance(value, bool)
                      and abs(value) <= MAX_OFFSET))
            if ok:
                if key in HUB_PREFS:
                    self.app.call("set_option", key, value)  # telefona da iletilir
                self.app.config.set(key, value)
                self.changed()
                w = getattr(self.app, "window", None)
                if w is not None and hasattr(w, "sync_ada_rows"):
                    w.sync_ada_rows()
        elif what == "notif_clear":  # adadaki bildirim listesini boşaltır (telefondakilere dokunmaz)
            self.notifs.clear()
            self.changed()
        elif what == "report":
            self.app.report_problem()
        elif what == "prefs":
            self.app.open_preferences()

    # ---- zamanlayıcı ------------------------------------------------------------------------

    def start_timer(self, seconds: int, phone: bool):
        if not 0 < seconds <= 24 * 3600:
            return
        self.cancel_timer(quiet=True)
        sessions = self.status.get("sessions") or []
        did = sessions[-1]["device_id"] if phone and sessions else None
        label = f"{seconds // 60} dk" if seconds % 60 == 0 else f"{seconds} sn"
        self.timer = {"ends_at": time.time() + seconds, "total": seconds, "phone": bool(did), "device_id": did,
                      "label": label, "source": GLib.timeout_add_seconds(seconds, self._timer_done)}
        if did:
            self.app.call("phone_timer", did, seconds, f"Zamanlayıcı · {label}")
        log.info("zamanlayıcı: %s%s", label, " (telefonda da)" if did else "")
        self.changed()

    def cancel_timer(self, quiet=False):
        t, self.timer = self.timer, None
        if not t:
            return
        GLib.source_remove(t["source"])
        if t["device_id"]:
            self.app.call("phone_timer", t["device_id"], 0, "")
        if not quiet:
            self.changed()

    def _timer_done(self):
        t, self.timer = self.timer, None
        if t:
            self.app.notifier.show("Süre doldu", f"{t['label']}lık zamanlayıcı", key="zamanlayici", urgent=True,
                                   icon="alarm-symbolic", sound="alarm-clock-elapsed")
            self.changed("timer")
        return False


# ---- eklentinin kurulumu ---------------------------------------------------------------

def shell_version() -> int | None:
    try:
        out = subprocess.run(["gnome-shell", "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"GNOME Shell (\d+)", out)
    return int(m.group(1)) if m else None


def source_dir(version: int) -> Path | None:
    """Paketteki (ya da kaynak klasöründeki) uygun sürüm: GNOME 45+ için "45", 42–44 için "42"."""
    variant = "45" if version >= 45 else "42"
    for base in (Path("/usr/share/talk-to-android/gnome-ada"), Path(__file__).resolve().parents[3] / "gnome-ada" / "build"):
        if (base / variant / "metadata.json").is_file():
            return base / variant
    src = Path(__file__).resolve().parents[3] / "gnome-ada"
    if (src / "build.py").is_file():  # kaynaktan çalışırken: üret
        subprocess.run(["python3", str(src / "build.py")], capture_output=True, timeout=30)
        if (src / "build" / variant / "metadata.json").is_file():
            return src / "build" / variant
    return None


def install_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "gnome-shell" / "extensions" / UUID


def _shell_settings():
    src = Gio.SettingsSchemaSource.get_default()
    if src is None or src.lookup("org.gnome.shell", True) is None:
        return None
    return Gio.Settings.new("org.gnome.shell")


def installed_version() -> int | None:
    try:
        return int(json.loads((install_dir() / "metadata.json").read_text())["version"])
    except (OSError, ValueError, KeyError):
        return None


def running_state() -> str:
    """"active" (kabukta çalışıyor), "pending" (kurulu ama oturum yenilenmeli), "absent" (kurulu değil)."""
    if installed_version() is None:
        return "absent"
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync("org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions", "org.gnome.Shell.Extensions",
                            "GetExtensionInfo", GLib.Variant("(s)", (UUID,)), GLib.VariantType("(a{sv})"),
                            Gio.DBusCallFlags.NONE, 2000, None)
        info = res.unpack()[0]
        return "active" if info.get("state") == 1 else "pending"
    except GLib.Error:
        return "pending"


def install() -> tuple[bool, str]:
    """Eklentiyi kullanıcının klasörüne kopyalar ve açık işaretler. Oturum yenilenince devreye girer."""
    version = shell_version()
    if version is None:
        return False, "GNOME Shell bulunamadı: üst ada yalnızca GNOME masaüstünde çalışır."
    if version < 42:
        return False, f"GNOME {version} çok eski (en az 42)."
    src = source_dir(version)
    if src is None:
        return False, "Eklenti dosyaları pakette bulunamadı."
    _copy(src)
    settings = _shell_settings()
    if settings is not None:
        enabled = list(settings.get_strv("enabled-extensions"))
        if UUID not in enabled:
            settings.set_strv("enabled-extensions", enabled + [UUID])
        disabled = [u for u in settings.get_strv("disabled-extensions") if u != UUID]
        settings.set_strv("disabled-extensions", disabled)
        if settings.get_boolean("disable-user-extensions"):
            settings.set_boolean("disable-user-extensions", False)
    try:  # kabuk eklentiyi zaten tanıyorsa (yeniden kurulum) hemen açılır
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync("org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions", "org.gnome.Shell.Extensions",
                      "EnableExtension", GLib.Variant("(s)", (UUID,)), None, Gio.DBusCallFlags.NONE, 2000, None)
    except GLib.Error:
        pass
    log.info("üst ada eklentisi kuruldu (GNOME %s)", version)
    return True, "Kuruldu"


def _copy(src: Path):
    dest = install_dir()
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)


def uninstall() -> tuple[bool, str]:
    settings = _shell_settings()
    if settings is not None:
        settings.set_strv("enabled-extensions", [u for u in settings.get_strv("enabled-extensions") if u != UUID])
    dest = install_dir()
    if dest.exists():
        shutil.rmtree(dest)
    return True, "Kaldırıldı"


def refresh_if_outdated():
    """Paket güncellenince kullanıcının klasöründeki kopya da yenilenir (bir sonraki oturumda devreye girer).
    Açık/kapalı ayarına dokunulmaz: kullanıcı Eklentiler uygulamasından kapattıysa kapalı kalır."""
    have = installed_version()
    if have is None:
        return
    version = shell_version()
    src = source_dir(version) if version else None
    if not src:
        return
    try:
        new = int(json.loads((src / "metadata.json").read_text())["version"])
    except (OSError, ValueError, KeyError):
        return
    if new > have:
        _copy(src)
        log.info("üst ada eklentisi güncellendi: %s → %s", have, new)
