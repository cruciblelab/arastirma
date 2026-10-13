"""GTK4 + libadwaita uygulaması: Hub'ı arka planda çalıştırır, olayları pencereye
ve masaüstü bildirimlerine dağıtır."""

import logging
import os
import shutil
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import APP_ID, __version__  # noqa: E402
# Güncelleme denetimi dpkg dosyaları değiştirirken çalışır: o an diskten içe aktarmak yarım pakete
# denk gelip ImportError verebiliyordu (yeniden başlama hiç olmuyordu). Baştan yüklenir.
from .. import gunluk, surum_izleyici  # noqa: E402
from ..config import Config  # noqa: E402
from ..hub import Hub, HubThread  # noqa: E402
from ..ipc import socket_path  # noqa: E402
from ..nowplaying import NowPlaying  # noqa: E402
from .. import arama, mirror, pil  # noqa: E402
from ..usb import CONFLICT  # noqa: E402
from . import compat, progress, system  # noqa: E402
from .screenshot import take_screenshot  # noqa: E402
from .notifier import Notifier  # noqa: E402
from .phone_mpris import PhonePlayers  # noqa: E402
from .window import KIND, Window, human_size  # noqa: E402

log = logging.getLogger("talkto.arayuz")


class App(Adw.Application):
    def __init__(self, start_hidden=False, hub_factory=None):
        # DEFAULT_FLAGS GLib 2.74'te geldi; Ubuntu 22.04'te (GLib 2.72) yalnızca FLAGS_NONE var.
        super().__init__(application_id=APP_ID,
                         flags=getattr(Gio.ApplicationFlags, "DEFAULT_FLAGS", Gio.ApplicationFlags.FLAGS_NONE))
        self.start_hidden = start_hidden
        self.hub_factory = hub_factory
        self.window = None
        self.setup_window = None
        self.qr_window = None
        self.dialogs = {}
        self.hub = None
        self._hidden_hint_shown = False
        self.installing_adb = False
        self.installing_scrcpy = False
        self.pending_clip = None  # Wayland'da pencere odakta değilken gelen pano metni
        self.mini = None  # mini oynatıcı penceresi
        self.ada = None  # üst ada köprüsü (do_startup'ta)
        self.now = NowPlaying()
        self.art_paths: dict[str, str] = {}
        self._popup_timers: dict[str, int] = {}
        self._usb_told: set[str] = set()  # hata ayıklaması kapalı takılı telefon için bildirim (bir kez)
        self._ringing: dict[tuple, dict] = {}  # (cihaz, anahtar) → çalan aramanın son bilgisi
        self.pil = pil.Takip()  # telefonun pili %15 / %10 / %5'e inince uyarı

    # ---- yaşam döngüsü --------------------------------------------------------

    def do_startup(self):
        Adw.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(APP_ID)
        self._css = Gtk.CssProvider()
        self._css.load_from_path(str(Path(__file__).with_name("style.css")))
        self._styled = set()
        self._style_display(Gdk.Display.get_default())
        for name, cb in (("quit", self._quit), ("about", self._about), ("show", lambda *_: self.present()),
                         ("setup", lambda *_: self.open_setup()), ("preferences", lambda *_: self.open_preferences()),
                         ("mini-player", lambda *_: self.open_mini_player()),
                         ("report", lambda *_: self.report_problem())):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            self.add_action(a)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.preferences", ["<Control>comma"])
        self.set_accels_for_action("window.close", ["<Control>w"])

        self.config = Config()
        self._default_autostart()
        GLib.timeout_add_seconds(2, self._check_wiped)
        self._setup_offered = False  # kurulum yardımcısı bu çalışmada kendiliğinden bir kez açılır
        self.notifier = Notifier()
        from . import ada
        self.ada = ada.AdaService(self)  # üst ada (GNOME eklentisi) için D-Bus köprüsü
        GLib.idle_add(lambda: ada.refresh_if_outdated() and False)
        # Donma bekçisi ve terminalden teşhis (talk-to-android teshis → SIGUSR1).
        self.bekci = gunluk.Bekci()
        GLib.timeout_add(500, self.bekci.beat)
        self.bekci.start()
        import signal
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGUSR1, self._diagnose)
        self.phone_players = PhonePlayers(
            lambda did, action, value: self.call("media_control", did, action, value))
        self.device_names: dict[str, str] = {}
        emit = lambda ev, data: GLib.idle_add(self.on_event, ev, data)  # noqa: E731
        self.hub = (self.hub_factory(self.config, emit) if self.hub_factory
                    else Hub(self.config, emit, ipc_path=socket_path()))
        self.hub.ui_screenshot = True
        self.bt = None
        self.thread = HubThread(self.hub)
        self.thread.start()
        if self.config["bluetooth"]:
            self._start_bluetooth()
        if self.config["run_in_background"]:
            self.hold()
        self._watch_own_version()

    # ---- güncellenince yeniden başla -------------------------------------------------

    def _watch_own_version(self):
        import talkto
        self._version_file = Path(talkto.__file__)
        updated = os.environ.pop("TALKTO_GUNCELLENDI", None)
        if updated:  # önceki süreç güncelleme yüzünden yeniden başlattı
            self.notifier.show(f"Talk To {updated} sürümüne güncellendi",
                               "Yeni sürümle yeniden başlatıldı; telefon birkaç saniye içinde yeniden bağlanır.",
                               key="guncellendi")
        reset = os.environ.pop("TALKTO_SIFIRLANDI", None)
        if reset:
            self.notifier.show("Talk To sıfırlandı",
                               "Ayarlar başka bir uygulamayla temizlendi; Talk To sıfırdan başladı." if reset == "dis"
                               else "Eski ayarlar ve eşleşmeler çöp kutusunda; gerekirse oradan geri alınır.",
                               key="sifirlandi")
        self._update_timer = None
        try:
            self._version_monitor = Gio.File.new_for_path(str(self._version_file)).monitor_file(
                Gio.FileMonitorFlags.NONE, None)
            self._version_monitor.connect("changed", lambda *_: self._schedule_update_check())
        except GLib.Error as e:
            log.info("sürüm dosyası izlenemiyor: %s", e.message)

    def _schedule_update_check(self, delay=3):
        # dpkg dosyaları birkaç adımda yazar: son değişiklikten birkaç saniye sonra bakılır.
        if self._update_timer:
            GLib.source_remove(self._update_timer)
        self._update_timer = GLib.timeout_add_seconds(delay, self._check_update)

    def _check_update(self):
        self._update_timer = None
        try:
            new = surum_izleyici.version_in(self._version_file)
        except Exception:  # noqa: BLE001 — paket yarı yazılmışken: biraz sonra yeniden bakılır
            log.exception("sürüm dosyası okunamadı; yeniden denenecek")
            self._schedule_update_check(10)
            return False
        if not new or new == __version__:
            return False
        busy = self.window and any(t["state"] in ("active", "waiting") for t in self.window.transfers.values())
        if busy:
            log.info("%s kuruldu; aktarım bitince yeniden başlanacak", new)
            self._schedule_update_check(30)
            return False
        log.info("%s kuruldu, yeni sürümle yeniden başlanıyor", new)
        self.restart_for_update(new)
        return False

    def restart_for_update(self, new_version):
        args = surum_izleyici.restart_argv(sys.argv, bool(self.window and self.window.get_visible()))
        os.environ["TALKTO_GUNCELLENDI"] = new_version  # bildirimi yeni süreç gösterir
        self._restart(args)

    def _restart(self, args, before=None):
        if self.bt:
            self.bt.stop()
        self.thread.stop()  # bağlantılar ve yerel soket temiz kapansın
        if before:
            before()  # ör. sıfırlama: ayarlar hub durduktan sonra taşınır (yoksa yeniden yazardı)
        logging.shutdown()
        # Aynı süreç yeni sürümün koduyla değişir (D-Bus adı ve soketler exec ile bırakılır).
        os.execv(sys.executable, [sys.executable, "-m", "talkto", *args])

    def reset_app(self, identity=False):
        """Eşleşmeleri, profilleri, komutları ve ayarları sıfırlar (çöp kutusuna), yeniden başlar; kurulum açılır."""
        from .. import veriler
        os.environ["TALKTO_SIFIRLANDI"] = "1"
        self._restart([], before=lambda: veriler.reset(identity))

    def windows_report(self) -> str:
        """Açık pencereler: takılan arayüzde görünmeyen bir modal pencere girdiyi tutuyor olabilir."""
        lines = []
        for w in Gtk.Window.list_toplevels():
            parent = w.get_transient_for()
            lines.append(f"{type(w).__name__} “{w.get_title() or ''}” görünür={w.get_visible()} "
                         f"eşlenmiş={w.get_mapped()} modal={w.get_modal()} etkin={w.is_active()} "
                         f"sahibi={type(parent).__name__ if parent else '-'}"
                         f"{'(görünmez)' if parent and not parent.get_visible() else ''} "
                         f"ekran={w.get_display().get_name()}")
        return "\n".join(lines)

    def _diagnose(self, *_):
        log.warning("pencereler:\n%s", self.windows_report())
        return True

    def _surface_modals(self):
        """Ana pencere öne gelince ona bağlı açık modal pencereler de gelsin: arkada kalan bir soru penceresi
        ana pencereyi tıklanamaz bırakıyordu (ne olduğu görünmeden)."""
        for w in Gtk.Window.list_toplevels():
            if w is not self.window and w.get_modal() and w.get_visible() and w.get_transient_for() is self.window:
                log.info("ana pencereye bağlı açık pencere öne alınıyor: %s", w.get_title() or type(w).__name__)
                w.present()

    def do_activate(self):
        if not self.window:
            self.window = Window(self)
            self.window.connect("close-request", self._on_close)
            self.window.connect("notify::is-active",
                                lambda w, _: w.is_active() and self.apply_pending_clipboard())
            self.window.update_status(self.hub.status())
            self.window.update_usb(self.hub.usb.snapshot())
            if self.start_hidden:
                self.start_hidden = False
                return
            self.window.present()
            self._offer_setup()
            return
        self.window.present()
        self._surface_modals()
        # Arka planda başladıysa (oturum açılışı, güncelleme sonrası) kurulum ilk görünüşte açılır.
        self._offer_setup()

    def _offer_setup(self):
        if not self.config["setup_done"] and not self._setup_offered and self.setup_window is None:
            self._setup_offered = True
            self.open_setup()

    def _check_wiped(self):
        """Ayarlar çalışırken dışarıdan silindiyse (Paket Güncelleyici'de "verileri temizle", elle silme) eski
        ayarlarla sürmek yerine sıfırdan başlar: kurulum yardımcısı açılır."""
        if not self.config.wiped():
            return True
        log.warning("ayarlar dışarıdan silinmiş: uygulama sıfırdan başlatılıyor")
        os.environ["TALKTO_SIFIRLANDI"] = "dis"
        self._restart([])
        return False

    def open_setup(self, step=None):
        """Kurulum yardımcısı (ilk açılışta kendiliğinden, sonra menüden; telefon takılınca telefon adımında)."""
        from .setup import SetupAssistant
        self.present()
        if self.setup_window is None:
            self.setup_window = SetupAssistant(self, self.window)
            self.setup_window.connect("close-request", lambda *_: setattr(self, "setup_window", None) or False)
        if step:
            self.setup_window.goto(step)
        self.setup_window.present()

    def _usb_hint(self, snap):
        """Telefon takıldı ama USB hata ayıklaması kapalı ve telefon başka yoldan da bağlı değil: bir kez söyle,
        tıklanınca kurulum yardımcısı markaya göre adımlarla açılır."""
        if not (snap.get("running") and self.config["usb"]) or self.device_names:
            return
        for ph in snap.get("unseen", []):
            key = ph.get("serial") or ph.get("name") or "?"
            if ph.get("adb") or key in self._usb_told:
                continue
            self._usb_told.add(key)
            show = lambda: self.open_setup("telefon")  # noqa: E731
            self.notifier.show(f"{ph.get('name') or 'Telefon'} takıldı",
                               "USB ile bağlamak için telefonda USB hata ayıklama gerekiyor. Adımları göstermek "
                               "için tıkla.", key="usb-rehber",
                               actions={"default": ("Adımları göster", show), "goster": ("Adımları göster", show)})
            log.info("hata ayıklaması kapalı telefon takıldı: %s", ph.get("name"))

    def report_problem(self):
        """GitHub'da sorun sayfası (sürüm ve sistem bilgisi yazılı); hiçbir şey kendiliğinden gönderilmez."""
        from .. import sorun
        phones = sorted(set(self.device_names.values()))
        try:
            Gio.AppInfo.launch_default_for_uri(sorun.report_url(phones), None)
        except GLib.Error as e:
            log.warning("tarayıcı açılamadı: %s", e.message)
            self.toast("Tarayıcı açılamadı: " + sorun.ISSUES)

    def present(self):
        self.activate()

    def _style_display(self, display):
        """Simgeler ve stil her ekrana ayrı eklenir (mini oynatıcı Wayland'de XWayland ekranında açılabilir)."""
        if display is None or display.get_name() in self._styled:
            return
        self._styled.add(display.get_name())
        icons = Path(__file__).resolve().parents[2] / "data" / "icons"
        if icons.is_dir():  # kurulmadan, kaynak klasöründen çalıştırılırken
            Gtk.IconTheme.get_for_display(display).add_search_path(str(icons))
        Gtk.StyleContext.add_provider_for_display(display, self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def open_preferences(self, page=None):
        self.activate()
        if self.window:
            self.window.open_preferences(page)

    # ---- mini oynatıcı ve şarkı bildirimi ---------------------------------------------

    def open_mini_player(self):
        from . import ustte
        from .miniplayer import MiniPlayer
        if self.mini is None:
            # Üstte tutulacaksa pencere baştan üstte tutulabilen ekranda açılır (Wayland'de XWayland).
            display = ustte.x11_display() if self.config["mini_on_top"] else None
            self._style_display(display)
            self.mini = MiniPlayer(self, display)
            log.info("mini oynatıcı açıldı (%s)", type(self.mini.get_display()).__name__)
        self._refresh_mini()
        self.mini.present()

    def set_mini_on_top(self, on):
        """Mini oynatıcı üstte dursun mu. X11'de yerinde değişir; Wayland'de pencere XWayland'de yeniden açılır."""
        from . import ustte
        on = bool(on)
        target = ustte.x11_display() if on else Gdk.Display.get_default()
        if on and target is None:  # XWayland da yok: yalnızca pencere menüsünden yapılabilir
            self.config.set("mini_on_top", False)
            if self.mini:
                self.mini.sync_actions()
                self.mini.toast(ustte.WAYLAND_HINT, 8)
            return
        self.config.set("mini_on_top", on)
        mini = self.mini
        if mini is None:
            return
        mini.sync_actions()
        if mini.get_display() == target:  # aynı ekranda kalır (X11 oturumu)
            if mini.apply_top(on):
                mini.toast("Diğer pencerelerin üstünde" if on else "Artık üstte tutulmuyor")
            return
        mini.close()
        self.mini = None
        self.open_mini_player()

    def set_pinned(self, on):
        if bool(on) == bool(self.config["mini_player_pinned"]):
            return  # anahtar ↔ menü eşitlenirken aynı değer geri gelir: döngüye girmesin
        self.config.set("mini_player_pinned", bool(on))
        if self.window:
            self.window.sync_pin()
        if self.mini:
            self.mini.sync_actions()

    def _refresh_mini(self):
        if not self.mini:
            return
        did, st = self.now.shown()
        self.mini.show_state(did, self.device_names.get(did, "Telefon"), st,
                             self.art_paths.get(st.get("art_id") or ""))
        self.mini.set_loading(self.now.loading(did or self.mini.device_id or self.now.last_device))

    def _on_media(self, did, state):
        ev = self.now.update(did, state)
        if ev["stopped"]:
            self._cancel_popup(did)
            self.notifier.close(f"calan|{did}")
        # Üst ada ekrandayken çalanı o gösterir: mini oynatıcı ayrıca kendiliğinden açılmaz (elle açılabilir).
        if (ev["started"] and self.config["mini_player_pinned"] and self.mini is None
                and not (self.ada and self.ada.showing())):
            self.open_mini_player()
        if ev["track"] and self.ada:
            self.ada.on_track()
        if self.now.loading(did):
            self._loading_changed()
        # Üst ada ekrandayken şarkı değişimini o gösterir: masaüstü bildirimi ayrıca çıkmaz (Özelleştir'den açılır).
        ada_shows = self.ada is not None and self.ada.showing() and not self.config["ada_track_popup"]
        if ev["track"] and self.config["track_popup"] and not ada_shows:
            # Kapak birkaç yüz ms sonra gelir; hızlı atlamada da her parça için bildirim çıkmasın.
            self._cancel_popup(did)
            self._popup_timers[did] = GLib.timeout_add(900, self._track_popup, did)
        self._refresh_mini()

    def _cancel_popup(self, did):
        t = self._popup_timers.pop(did, None)
        if t:
            GLib.source_remove(t)

    def _track_popup(self, did):
        self._popup_timers.pop(did, None)
        st = self.now.states.get(did) or {}
        # Mini oynatıcı açıksa aynı bilgi zaten ekranda.
        if not st.get("playing") or (self.mini and self.mini.get_visible()):
            return False
        name = self.device_names.get(did, "Telefon")
        body = " · ".join(x for x in (st.get("artist"), f"{st.get('player') or 'Medya'} ({name})") if x)
        self.notifier.show(
            st.get("title") or "Bilinmeyen parça", body, key=f"calan|{did}", app_name="Telefonda çalan",
            icon=self.art_paths.get(st.get("art_id") or "") or "audio-x-generic",
            actions={"default": ("Mini oynatıcı", self.open_mini_player),
                     "play_pause": ("Duraklat", lambda: self.call("media_control", did, "play_pause", None)),
                     "next": ("Sonraki", lambda: self.call("media_control", did, "next", None))})
        return False

    def _on_close(self, win):
        if self.config["run_in_background"]:
            win.set_visible(False)
            if not self._hidden_hint_shown:
                self._hidden_hint_shown = True
                self.notifier.show("Talk To arka planda çalışıyor",
                                   "Telefon bağlı kalır. Tamamen kapatmak için menüden “Tamamen kapat”.",
                                   actions={"default": ("Aç", self.present)})
            return True
        self._quit()
        return False

    # ---- Bluetooth --------------------------------------------------------------

    def _start_bluetooth(self):
        try:
            from ..bluetooth import BluetoothServer
        except ImportError as e:
            self.call("set_bt_state", {"available": False, "message": f"Bluetooth kullanılamıyor: {e}"})
            return
        self.bt = BluetoothServer(
            on_socket=lambda sock, addr, name: self.hub.submit(self.hub.accept_socket(sock, "bluetooth", addr)),
            on_state=lambda st: self.call("set_bt_state", st))
        self.bt.start()

    def set_bluetooth(self, on):
        self.call("set_option", "bluetooth", on)
        self.call("apply")
        if on and not self.bt:
            self._start_bluetooth()
        elif not on and self.bt:
            self.bt.stop()
            self.bt = None

    def do_shutdown(self):
        if self.ada:
            self.ada.stop()  # D-Bus nesnesi bırakılsın (aynı süreçte yeniden başlayan uygulama için)
        Adw.Application.do_shutdown(self)

    def _quit(self, *_):
        if self.bt:
            self.bt.stop()
        self.thread.stop()
        if self.config["run_in_background"]:
            self.release()
        self.quit()

    def _about(self, *_):
        compat.about(self.window, application_name="Talk To", application_icon=APP_ID,
                     version=__version__, developer_name="Crucible ekibi",
                     website="https://github.com/cruciblelab/arastirma",
                     license_type=Gtk.License.GPL_3_0,
                     comments="Linux bilgisayar ile Android telefonu USB, Wi-Fi ya da Bluetooth üzerinden bağlar.\n\n"
                              "Açık kaynak ve tamamen yerel: telefonla bilgisayar doğrudan ve şifreli konuşur; sunucu, "
                              "hesap, reklam ya da izleme yok. İnternete yalnızca sen istersen çıkılır (telefon "
                              "ekranı aracını indirmek, Sorun bildir sayfasını açmak).")

    # ---- hub'a komut ----------------------------------------------------------

    def call(self, method, *args):
        if method == "media_control" and len(args) > 1 and args[1] in ("next", "previous"):
            self.now.expect_change(args[0])  # yeni şarkı gelene kadar "yükleniyor"
            self._loading_changed()
        if method == "call_action":
            self._watch_answer(*args)
        self.hub.submit(getattr(self.hub, method)(*args))

    def _watch_answer(self, did, key, index):
        """Bilgisayardan "Cevapla"ya basıldı: arama birkaç saniye sonra hâlâ çalıyorsa telefon cevaplayamamıştır."""
        d = self._ringing.get((did, key))
        if d and any(a["i"] == index and arama.is_answer(a["title"]) for a in d["actions"]):
            GLib.timeout_add(arama.WAIT_MS, self._answer_check, did, key)

    def _answer_check(self, did, key):
        d = self._ringing.get((did, key))
        if d and not d.get("answer_failed"):
            log.info("arama bilgisayardan cevaplanamadı (%s)", did[:8])
            self._call(dict(d, answer_failed=True))
            if self.ada:
                self.ada.answer_failed(did, key)
        return False

    def _loading_changed(self):
        """Şarkılar arası "yükleniyor" durumu başladı ya da bitebilir: mini oynatıcı ve ada güncellensin; sürdükçe
        yarım saniyede bir yeniden bakılır (bitince kendiliğinden kalkar)."""
        self._refresh_mini()
        if self.ada:
            self.ada.changed()
        if not getattr(self, "_loading_timer", 0):
            self._loading_timer = GLib.timeout_add(500, self._loading_tick)

    def _loading_tick(self):
        did = self.now.shown()[0] or (self.mini.device_id if self.mini else None) or self.now.last_device
        if self.now.loading(did):
            return True
        self._loading_timer = 0
        self._refresh_mini()
        if self.ada:
            self.ada.changed()
        return False

    def toast(self, text):
        """Kurulum yardımcısı açıksa sonuç onun üstünde görünsün (ana pencere arkasında kalır)."""
        target = self.setup_window if self.setup_window and self.setup_window.get_visible() else self.window
        if target:
            target.toast(text)

    def send_clipboard(self, device_id):
        cb = Gdk.Display.get_default().get_clipboard()

        def done(c, res):
            try:
                text = c.read_text_finish(res)
            except GLib.Error:
                text = None
            if text:
                self.call("send_clipboard", device_id, text)
                self.window.toast("Pano telefona gönderildi")
            else:
                self.window.toast("Panoda metin yok")
        cb.read_text_async(None, done)

    def install_adb(self):
        """adb'yi dağıtımın paket yöneticisiyle kurar; şifre pkexec penceresinde sorulur, ilerleme pencerede."""
        cmd = system.adb_install_command()
        if not cmd or self.installing_adb:
            return
        self.installing_adb = True
        self.window.update_usb(self.hub.usb.snapshot())
        parent = self.setup_window if self.setup_window and self.setup_window.get_visible() else self.window

        def done(ok, msg):
            self.installing_adb = False
            win.finish(ok, "adb kuruldu" if ok else "adb kurulamadı",
                       "Telefonu USB ile takabilirsin; telefonda “USB hata ayıklamaya izin ver” sorusunu onayla."
                       if ok else msg)
            if self.window:
                self.window.update_usb(self.hub.usb.snapshot())
            if self.setup_window:
                self.setup_window.refresh()
        win = progress.run_privileged(parent, "adb kuruluyor", cmd, done)

    # ---- telefonun ekranı (scrcpy) ---------------------------------------------

    def _after(self, coro, on_done=None):
        """Hub'da çalıştır, sonucu (ok, mesaj) ana iş parçacığında bildir."""
        fut = self.hub.submit(coro)

        def show(ok, msg):
            if on_done:
                on_done(ok, msg)
            else:
                self.toast(msg)
            return False
        fut.add_done_callback(lambda f: GLib.idle_add(show, *f.result()))

    def _with_scrcpy(self, then):
        """scrcpy yoksa (ya da sistemdeki çok eskiyse) resmi sürümü indirmeyi önerir, hazır olunca devam eder."""
        if mirror.available():
            then()
            return
        if self.installing_scrcpy:
            self.toast("scrcpy hazırlanıyor…")
            return
        parent = self.setup_window if self.setup_window and self.setup_window.get_visible() else self.window
        old = mirror.outdated_system()
        if mirror.can_download():
            body = (f"Telefonun ekranını açmak için scrcpy gerekiyor. Resmi {mirror.SCRCPY_VERSION} sürümü "
                    f"GitHub'dan indirilir (~{mirror.SCRCPY_SIZE // 1_000_000} MB), doğrulanır ve yalnızca senin "
                    "kullanıcı klasörüne konur; şifre gerekmez.")
            if old:
                body += (f" Sistemdeki scrcpy {'.'.join(map(str, old))} yeni Android sürümlerinde açılmıyor; "
                         "ona dokunulmaz.")
            label, start = "İndir", lambda: self._download_scrcpy(parent, then)
        else:
            cmd = mirror.install_command()
            if not cmd:
                self.toast("scrcpy kurulu değil; dağıtımının paket yöneticisinden “scrcpy” paketini kur")
                return
            body = ("Telefonun ekranını açmak için scrcpy gerekiyor. Dağıtımının paket deposundan kurulur; "
                    "bilgisayarın şifresi sorulur.")
            label, start = "Kur", lambda: self._install_scrcpy_pkg(parent, cmd, then)
        d = compat.Dialog(parent, "scrcpy hazırlansın mı?", body)
        d.add_response("cancel", "Vazgeç")
        d.add_response("go", label)
        d.set_appearance("go", compat.SUGGESTED)
        d.set_close_response("cancel")
        d.on_response(lambda r: r == "go" and start())
        d.present()

    def _download_scrcpy(self, parent, then):
        import threading
        self.installing_scrcpy = True
        cancel = threading.Event()
        win = progress.ProgressWindow(parent, f"scrcpy {mirror.SCRCPY_VERSION} indiriliyor", "Bağlanılıyor…",
                                      cancel=cancel.set)
        win.present()

        def report(done, total, stage):
            def ui():
                if stage == "doğrulanıyor":
                    win.set_fraction(None)
                    win.set_text("İndirilen dosya doğrulanıyor (SHA-256)…")
                else:
                    win.set_fraction(done / total if total else None)
                    win.set_text(f"{human_size(done)} / {human_size(total)}")
                return False
            GLib.idle_add(ui)

        def work():
            try:
                mirror.download(report, cancel)
                GLib.idle_add(finish, True, "")
            except InterruptedError:
                GLib.idle_add(finish, False, "İndirme durduruldu; hiçbir şey kurulmadı.")
            except Exception as e:  # noqa: BLE001 — ağ/doğrulama hatası pencerede gösterilir
                log.warning("scrcpy indirilemedi: %s", e)
                GLib.idle_add(finish, False, str(e))

        def finish(ok, msg):
            self.installing_scrcpy = False
            win.finish(ok, f"scrcpy {mirror.SCRCPY_VERSION} hazır" if ok else "scrcpy indirilemedi",
                       "Telefonun ekranı açılıyor…" if ok else msg)
            if self.setup_window:
                self.setup_window.refresh()
            if ok:
                then()
                GLib.timeout_add_seconds(2, lambda: (win.close(), False)[-1])
            return False
        threading.Thread(target=work, daemon=True).start()

    def _install_scrcpy_pkg(self, parent, cmd, then):
        self.installing_scrcpy = True

        def done(ok, msg):
            self.installing_scrcpy = False
            ok = ok and mirror.available()
            win.finish(ok, "scrcpy kuruldu" if ok else "scrcpy kurulamadı",
                       "Telefonun ekranı açılıyor…" if ok else (msg or "Kurulan sürüm çok eski olabilir."))
            if self.setup_window:
                self.setup_window.refresh()
            if ok:
                then()
        win = progress.run_privileged(parent, "scrcpy kuruluyor", cmd, done)

    def mirror_usb(self, serial, model=None):
        self._with_scrcpy(lambda: self._after(self.hub.mirror_device(serial, model)))

    def mirror_session(self, device_id):
        self._with_scrcpy(lambda: self._after(self.hub.mirror_session(device_id)))

    def prepare_wireless(self, serial):
        self._after(self.hub.mirror_prepare_wireless(serial))

    def install_phone_app(self, serial, replace=False):
        fut = self.hub.submit(self.hub.install_phone_app(serial, replace))

        def show(ok, msg):
            if msg == CONFLICT and self.window:
                self._ask_replace(serial)
            else:
                self.toast(msg)
            return False

        fut.add_done_callback(lambda f: GLib.idle_add(show, *f.result()))

    def connect_phone(self, serial):
        """Telefona gitmeden bağlan: telefondaki uygulama USB'den bağlanacak şekilde açılır; ilk seferde
        eşleşme numarası burada (kurulum yardımcısı açıksa onun üstünde) sorulur."""
        self.toast("Telefonda Talk To açılıyor…")
        self._after(self.hub.connect_phone(serial), lambda ok, msg: None if ok else self.toast(msg))

    def show_qr(self, renew=False):
        """Karekodla telefon ekle: yeni tek kullanımlık karekod (açık pencere varsa onu yeniler)."""
        if self.qr_window and not renew:
            self.qr_window.present()
            return
        fut = self.hub.submit(self.hub.qr_start())

        def show(info):
            from .karekod import QrWindow
            if self.qr_window:
                self.qr_window.update(info)
            else:
                parent = self.setup_window if self.setup_window and self.setup_window.get_visible() else self.window
                self.qr_window = QrWindow(self, parent, info)
            self.qr_window.present()
            return False
        fut.add_done_callback(lambda f: GLib.idle_add(show, f.result()))

    def qr_closed(self, win):
        if self.qr_window is win:
            self.qr_window = None
            self.hub.submit(self._qr_stop())

    async def _qr_stop(self):
        self.hub.qr_stop()

    def phone_setup(self, serial):
        """Telefondaki izinleri USB'den verir (bildirim erişimi, pil, bildirim ve Bluetooth izni)."""
        self.toast("Telefon ayarlanıyor…")
        self._after(self.hub.phone_setup(serial))

    def _ask_replace(self, serial):
        d = compat.Dialog(self.window, "Telefondaki uygulama kaldırılıp yeniden kurulsun mu?",
                          CONFLICT + " Kurulumdan sonra izinler bilgisayardan yeniden verilir; telefon engellerse bildirim "
                          "erişimini telefonda elle açman gerekir.")
        d.add_response("cancel", "Vazgeç")
        d.add_response("replace", "Kaldır ve kur")
        d.set_appearance("replace", compat.DESTRUCTIVE)
        d.set_close_response("cancel")
        d.on_response(lambda r: r == "replace" and self.install_phone_app(serial, replace=True))
        d.present()

    def open_path(self, path):
        compat.open_path(self.window, path)

    def show_in_folder(self, path):
        compat.show_in_folder(self.window, path)

    # ---- hub'dan gelen olaylar (ana iş parçacığı) ---------------------------------

    def on_event(self, event, d):
        self._on_event(event, d)
        if self.ada:
            try:
                self.ada.on_event(event, d)
            except Exception:  # noqa: BLE001 — üst ada asıl arayüzü bozmasın
                log.exception("üst ada güncellenemedi")

    def _on_event(self, event, d):
        w = self.window
        if event == "status":
            self.device_names = {x["device_id"]: x["name"] for x in d.get("sessions", [])}
            self._check_battery(d.get("sessions", []))
            self.phone_players.keep_only(self.device_names)
            for did in [x for x in self.now.states if x not in self.device_names]:
                self._cancel_popup(did)
                self.notifier.close(f"calan|{did}")
            self.now.keep_only(self.device_names)
            self._refresh_mini()
            if w:
                w.update_status(d)
            if self.setup_window:
                self.setup_window.refresh()
        elif event == "usb":
            self._usb_hint(d)
            if w:
                w.update_usb(d)
            if self.setup_window:
                self.setup_window.refresh()
        elif event == "ask":
            log.info("soru: %s (%s)", d.get("kind"), d.get("name") or d.get("device"))
            self._ask(d)
        elif event == "ask_closed":
            # Süre doldu ya da telefon vazgeçti (kullanıcı cevapladıysa pencere zaten kapanmıştı).
            self.notifier.close(f"ask{d['id']}")
            dlg = self.dialogs.pop(d["id"], None)
            if dlg:
                dlg.close()
                self.toast("İsteğin süresi doldu ya da telefon vazgeçti")
        elif event == "notification":
            self.notifier.show(d["title"] or d["app"], d["text"], key=f"{d['device_id']}|{d['key']}",
                               app_name=f"{d['app']} · {d['device']}", icon=d.get("icon"))
            if w:
                w.add_notification(d)
        elif event == "call":
            self._call(d)
        elif event == "call_result":
            self._call_result(d)
        elif event == "call_ended":
            log.info("arama bitti (%s)", d["device_id"][:8])
            self._ringing.pop((d["device_id"], d["key"]), None)
            self.notifier.close(f"call|{d['device_id']}|{d['key']}")
        elif event == "notification_removed":
            self.notifier.close(f"{d['device_id']}|{d['key']}")
        elif event == "media":
            try:
                self.phone_players.update(d["device_id"], self.device_names.get(d["device_id"], "Telefon"), d["state"])
            except GLib.Error:
                log.exception("telefon oynatıcısı güncellenemedi")  # penceredeki kart yine güncellensin
            if w:
                w.update_media(d["device_id"], d["state"])
            self._on_media(d["device_id"], d["state"])
        elif event == "media_art":
            self.art_paths[d["art_id"]] = d["path"]
            if len(self.art_paths) > 64:
                self.art_paths = dict(list(self.art_paths.items())[-32:])
            self._refresh_mini()
            self.phone_players.art(d["device_id"], d["art_id"])
            if w:
                w.update_media_art(d["device_id"], d["art_id"], d["path"])
        elif event == "transfer":
            if w:
                w.update_transfer(d)
            self._transfer_notice(d)
        elif event == "clipboard":
            self._incoming_clipboard(d)
        elif event == "open_url":
            Gio.AppInfo.launch_default_for_uri(d["url"], None)
        elif event == "paired_by_qr":
            if self.qr_window:
                self.qr_window.close()
            self.toast(f"{d['name']} karekodla eşleşti")
        elif event == "paired_by_password":
            # Şifre doğru olunca onay penceresi çıkmaz; yine de kullanıcı haberdar olsun.
            self.notifier.show("Yeni telefon şifreyle eşleşti",
                               f"{d['name']} ({d['ip']}). İstemediysen Telefonlar sayfasından unut ve şifreyi değiştir.",
                               key="sifre-esleme", urgent=True)
        elif event == "connected":
            text = f"{d['name']} bağlandı ({KIND.get(d['kind'], d['kind'])})"
            if w and w.get_visible():
                w.toast(text)
            else:
                self.notifier.show(text, "Bildirimler ve medya artık bu bilgisayarda.", key="baglanti")
        elif event == "screenshot":
            self._screenshot(d["device_id"])
        elif event == "phone_setup":
            self.toast(f"{d['device']} izinlerini ayarlamamı istedi; ayarlanıyor…")
        elif event == "phone_crash":
            path = d["path"]
            self.notifier.show(f"{d['device']}: Talk To son seferde çökmüştü",
                               "Nedeni bir dosyaya kaydedildi; geliştiriciye göndermek için klasörde göster.",
                               key="telefon-cokme", actions={"default": ("Klasörde göster",
                                                                         lambda: self.show_in_folder(path))})
        elif event == "screenshot_taken":
            self._screenshot_taken(d["device_id"])
        elif event == "command_run":
            self.notifier.show(f"{d['device']}: {d['name']}", "Telefondan çalıştırıldı", key=f"komut{d['id']}")
            if w:
                w.add_command_log(d)
        elif event == "disconnected":
            if w and w.get_visible():
                w.toast(f"{d['name']} bağlantısı kesildi")
        return False

    def _transfer_notice(self, d):
        if d["direction"] == "in" and d["state"] == "done":
            p = d["path"]
            self.notifier.show(f"Dosya alındı: {d['name']}", f"{d['device']} · {human_size(d['size'])}",
                               actions={"default": ("Aç", lambda: self.open_path(p)),
                                        "folder": ("Klasörde göster", lambda: self.show_in_folder(p))})
        elif d["state"] == "failed" and self.window:
            self.window.toast(f"{d['name']}: {d.get('error') or 'aktarım başarısız'}")
        elif d["direction"] == "out" and d["state"] == "rejected" and self.window:
            self.window.toast(f"{d['name']} telefonda reddedildi")

    # ---- diyaloglar -----------------------------------------------------------

    def _front(self):
        """Soru pencerelerinin sahibi: kurulum yardımcısı ya da öndeki Tercihler penceresi (soru ana pencereye bağlanırsa
        onların arkasında kalıp görünmeden ana pencereyi kilitleyebilir), yoksa ana pencere."""
        prefs = getattr(self.window, "prefs_window", None) if self.window else None
        for w in (self.setup_window, prefs):
            if w and w.get_visible() and w.is_active():
                return w
        return self.setup_window if self.setup_window and self.setup_window.get_visible() else self.window

    def _dialog(self, heading, body, extra=None):
        return compat.Dialog(self._front(), heading, body, extra)

    def _show(self, dlg):
        dlg.present()

    def confirm(self, heading, body, label, on_ok, destructive=False, extra=None):
        self.activate()
        dlg = self._dialog(heading, body, extra)
        dlg.add_response("cancel", "Vazgeç")
        dlg.add_response("ok", label)
        dlg.set_appearance("ok", compat.DESTRUCTIVE if destructive else compat.SUGGESTED)
        dlg.set_close_response("cancel")
        dlg.on_response(lambda r: on_ok() if r == "ok" else None)
        self._show(dlg)

    def show_output(self, title, res):
        text = (res.get("output") or "").strip() or ("Tamamlandı (çıktı yok)" if res.get("ok") else "Başarısız")
        label = Gtk.Label(label=text, xalign=0, selectable=True, wrap=True, css_classes=["monospace"])
        scroll = Gtk.ScrolledWindow(child=label, min_content_height=80, max_content_height=320,
                                    propagate_natural_height=True)
        dlg = self._dialog(title, "Başarılı" if res.get("ok") else f"Hata (çıkış kodu {res.get('code', '-')})", scroll)
        dlg.add_response("ok", "Tamam")
        self._show(dlg)
        return True

    # ---- telefondan gelen pano ---------------------------------------------------

    @staticmethod
    def _wayland():
        display = Gdk.Display.get_default()
        return "Wayland" in type(display).__name__ or (
            os.environ.get("XDG_SESSION_TYPE") == "wayland" and os.environ.get("GDK_BACKEND") != "x11")

    def _incoming_clipboard(self, d):
        text = d["text"]
        preview = text if len(text) < 120 else text[:117] + "…"
        title = f"{d['device']} panosu kopyalandı"
        # Wayland'da (GNOME) odakta olmayan pencere panoyu değiştiremez: GTK hata vermez ama pano değişmez.
        if not self._wayland() or (self.window and self.window.is_active()):
            Gdk.Display.get_default().get_clipboard().set_content(Gdk.ContentProvider.new_for_value(text))
            self.notifier.show(title, preview, key="pano")
            return
        if shutil.which("wl-copy"):
            try:
                proc = Gio.Subprocess.new(["wl-copy", "--type", "text/plain;charset=utf-8"],
                                          Gio.SubprocessFlags.STDIN_PIPE)
            except GLib.Error:
                proc = None
            if proc:
                def done(p, res):
                    try:
                        p.communicate_utf8_finish(res)
                        ok = p.get_exit_status() == 0
                    except GLib.Error:
                        ok = False
                    if ok:
                        self.notifier.show(title, preview, key="pano")
                    else:
                        self._clipboard_later(d, preview)
                proc.communicate_utf8_async(text, None, done)
                return
        self._clipboard_later(d, preview)

    def _clipboard_later(self, d, preview):
        self.pending_clip = d["text"]
        self.notifier.show(f"{d['device']} panosu geldi", "Talk To'ya geçince panoya kopyalanır: " + preview,
                           key="pano", actions={"default": ("Kopyala", self.present)})

    def apply_pending_clipboard(self):
        """Pencere odağa gelince (Wayland) bekleyen pano metnini uygular."""
        if self.pending_clip is None:
            return
        Gdk.Display.get_default().get_clipboard().set_content(Gdk.ContentProvider.new_for_value(self.pending_clip))
        self.pending_clip = None
        self.notifier.close("pano")
        if self.window:
            self.window.toast("Telefonun panosu kopyalandı")

    def _screenshot(self, device_id):
        def done(path, err):
            s = self.hub.sessions.get(device_id)
            if path:
                self._screenshot_taken(device_id)
                self.call("send_file", device_id, path)
            elif err and err.startswith("unavailable"):
                # Portal hiç yok: komut satırı araçları (gnome-screenshot, grim...).
                if s:
                    self.hub.submit(s._screenshot_headless())
            elif s:
                # Masaüstünün reddi geçerli: başka yoldan arkadan ekran alınmaz.
                text = ("Bilgisayardaki izin penceresi cevaplanmadı." if err == "timeout" else
                        "Bilgisayarda izin verilmedi ya da masaüstü ekran görüntüsü vermedi.")
                self.hub.submit(s.send({"type": "command_result", "id": "ekran", "name": "Ekran görüntüsü",
                                        "ok": False, "output": text}))
        take_screenshot(done)

    def _call(self, d):
        """Telefondaki arama: çalarken acil bildirim (uygulamanın Cevapla/Reddet düğmeleri), sürerken kalıcı
        bildirim (Kapat ve görüşme sesi). Bildirim en çok 3 düğme gösterir; önce uygulamanınkiler."""
        did, key = d["device_id"], d["key"]
        ringing = d["state"] == "ringing"
        who = d["caller"] or "Bilinmeyen"
        failed = False
        if ringing:
            failed = d.get("answer_failed") or (self._ringing.get((did, key)) or {}).get("answer_failed", False)
            self._ringing[(did, key)] = dict(d, answer_failed=failed)
        else:
            self._ringing.pop((did, key), None)
        actions = {}
        for a in d["actions"][:3]:
            if failed and arama.is_answer(a["title"]):
                continue  # işe yaramadığı görüldü: yerine "telefondan cevapla" yazar
            actions[f"a{a['i']}"] = (a["title"], lambda i=a["i"]: self.call("call_action", did, key, i))
        if not ringing and len(actions) <= 1:  # bildirim en çok 3 düğme: ses ancak ikisi birden sığarsa
            for k, label, up in (("ses_azalt", "Ses −", False), ("ses_artir", "Ses +", True)):
                actions[k] = (label, lambda up=up: self.call("call_volume", did, up))
        self.notifier.show(f"{d['app']} {'araması' if ringing else 'görüşmesi'}: {who}",
                           " · ".join(x for x in (arama.FAILED if failed else d["text"], d["device"]) if x),
                           key=f"call|{did}|{key}",
                           app_name=f"{d['app']} · {d['device']}", icon=d.get("icon"), actions=actions,
                           urgent=ringing, resident=not ringing)

    def _default_autostart(self):
        """Oturum açılınca arka planda başlasın: bilgisayar yeniden başlayınca telefon kendiliğinden bağlansın. Bir
        kez açılır; kullanıcı Tercihler'den kapatırsa öyle kalır. (Testlerin ayar klasörü ayrıyken gerçek oturumun
        otomatik başlatmasına dokunulmaz.)"""
        if self.config["autostart_default_done"] or os.environ.get("TALKTO_CONFIG_DIR"):
            return
        self.config.set("autostart_default_done", True)
        if not system.autostart_enabled():
            try:
                system.set_autostart(True)
                log.info("oturum açılınca başlatma açıldı")
            except OSError as e:
                log.warning("otomatik başlatma açılamadı: %s", e)

    def _check_battery(self, sessions):
        """Telefonun pili bir eşiğe indiyse uyar: üst ada ekrandaysa ada belirir, değilse masaüstü bildirimi.
        Şarja takılınca bildirim kalkar."""
        self.pil.keep_only({s["device_id"] for s in sessions})
        for s in sessions:
            did, b = s["device_id"], s.get("battery")
            hit = self.pil.check(did, b)
            weak = self.pil.weak(did)
            if b and b.get("charging") and not weak:
                self.notifier.close(f"pil|{did}")
            if hit is None:
                continue
            level = b["level"]
            log.info("telefonun pili azaldı: %%%d%s (%s)", level, " (takılı ama şarj yetmiyor)" if weak else "",
                     did[:8])
            if self.ada and self.ada.showing():
                self.ada.battery_alert(did)
                continue
            name = s.get("name") or "Telefon"
            if weak:
                title = f"{name}: pil %{level}, şarj yetmiyor"
                body = ("Kabloya takılı ama pil düşüyor (bilgisayarın USB'si yetmeyebilir). Duvar şarjına tak "
                        "ya da ekranı kapat.")
            else:
                title = f"{name}: pil %{level}"
                body = "Şarja tak; telefon birazdan kapanabilir." if hit <= 5 else "Şarja tak."
            self.notifier.show(title, body, key=f"pil|{did}", icon="battery-caution-symbolic", urgent=hit <= 5)

    def _call_result(self, d):
        """Telefon düğmeye basamadıysa ya da ses değişmediyse nedenini söyle (sessizce çalışmıyor gibi kalmasın)."""
        if d["kind"] == "volume":
            if d["error"]:
                self.toast(f"Görüşme sesi değiştirilemedi: {d['error']}")
            elif d["before"] == d["after"]:
                edge = d["after"] in (0, d["max"])
                self.toast("Görüşme sesi zaten en uçta" if edge else
                           f"Telefon görüşme sesini değiştirmedi (kip: {d['mode']})")
        elif d["error"]:
            self.toast(f"Telefon “{d['title'] or 'düğme'}” düğmesine basamadı: {d['error']}")

    def _screenshot_taken(self, device_id):
        # Ubuntu 22.04'teki portal sormadan veriyor: en azından kullanıcı haberdar olsun.
        name = self.device_names.get(device_id, "Telefon")
        self.notifier.show(f"{name} ekran görüntüsü aldı", "Bu bilgisayarın ekranı telefona gönderildi. "
                           "İstemiyorsan profilinden “Ekran görüntüsü” iznini kapat.", key="ekran")

    def _ask(self, d):
        if self._front() is self.window:
            self.activate()
        else:
            self.setup_window.present()
        rid = d["id"]
        pids = []
        if d["kind"] == "pair":
            via = {"usb": "USB kablosu", "bluetooth": f"Bluetooth ({d['ip']})"}.get(d["transport"], f"Wi-Fi ({d['ip']})")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.append(Gtk.Label(label="Eşleşme numarası", css_classes=["dim-label"]))
            code = d["code"]
            box.append(Gtk.Label(label=f"{code[:3]} {code[3:]}", css_classes=["pair-code", "numeric"]))
            pids = list(d.get("profiles") or {})
            if pids:
                prof_row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, margin_top=10)
                prof_row.append(Gtk.Label(label="Profil"))
                chooser = Gtk.DropDown.new_from_strings([d["profiles"][p] for p in pids])
                if d.get("default_profile") in pids:
                    chooser.set_selected(pids.index(d["default_profile"]))
                prof_row.append(chooser)
                box.append(prof_row)
            # Uzun ve ark. 2007: "Evet/Hayır" ile %20 eşleşmeyen kod onaylandı; "aynı/farklı" etiketleri ve
            # güvenli varsayılanla %0. Enter, Esc ve pencereyi kapatmak "farklı" sayılır.
            dlg = self._dialog(
                "Numaraları karşılaştır",
                f"{d['name']}" + (f" ({d['model']})" if d.get("model") else "") + f" · {via}\n\n"
                "Telefonda da aynı numara görünüyor mu? Aynıysa eşleşir ve telefon seçtiğin profille bağlanır. "
                "Bu numarayı bir yere yazmana gerek yok.",
                box)
            dlg.add_response("reject", "Numaralar farklı")
            dlg.add_response("accept", "Numaralar aynı")
            dlg.set_default("reject")
            self.notifier.show("Telefon eşleşmek istiyor", f"{d['name']} · numara {code[:3]} {code[3:]}",
                               key=f"ask{rid}", urgent=True, actions={"default": ("Göster", self.present)})
        else:
            dlg = self._dialog("Dosya kabul edilsin mi?",
                               f"{d['device']} şu dosyayı göndermek istiyor:\n{d['name']} ({human_size(d['size'])})")
            dlg.add_response("reject", "Reddet")
            dlg.add_response("accept", "Kabul et")
            dlg.set_appearance("accept", compat.SUGGESTED)
        # Enter'a yanlışlıkla basmak onay olmasın.
        dlg.set_close_response("reject")

        def respond(response):
            self.dialogs.pop(rid, None)
            self.notifier.close(f"ask{rid}")
            ok = response == "accept"
            if ok and d["kind"] == "pair" and pids:
                ok = pids[chooser.get_selected()]  # onay + seçilen profil
            self.call("answer", rid, ok)
        dlg.on_response(respond)
        self.dialogs[rid] = dlg
        self._show(dlg)


def run(argv) -> int:
    from .. import gunluk
    gunluk.setup()
    hidden = "--arka-planda" in argv
    argv = [a for a in argv if a != "--arka-planda"]
    return App(start_hidden=hidden).run(argv)


if __name__ == "__main__":
    sys.exit(run(sys.argv))
