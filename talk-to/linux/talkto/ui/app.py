"""GTK4 + libadwaita uygulaması: Hub'ı arka planda çalıştırır, olayları pencereye
ve masaüstü bildirimlerine dağıtır."""

import logging
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import APP_ID, __version__  # noqa: E402
from ..config import Config  # noqa: E402
from ..hub import Hub, HubThread  # noqa: E402
from ..ipc import socket_path  # noqa: E402
from ..usb import CONFLICT  # noqa: E402
from . import compat, system  # noqa: E402
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
        self.dialogs = {}
        self.hub = None
        self._hidden_hint_shown = False
        self.installing_adb = False

    # ---- yaşam döngüsü --------------------------------------------------------

    def do_startup(self):
        Adw.Application.do_startup(self)
        icons = Path(__file__).resolve().parents[2] / "data" / "icons"
        if icons.is_dir():  # kurulmadan, kaynak klasöründen çalıştırılırken
            Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(str(icons))
        Gtk.Window.set_default_icon_name(APP_ID)
        css = Gtk.CssProvider()
        css.load_from_path(str(Path(__file__).with_name("style.css")))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        for name, cb in (("quit", self._quit), ("about", self._about), ("show", lambda *_: self.present())):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            self.add_action(a)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        self.config = Config()
        self.notifier = Notifier()
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

    def do_activate(self):
        if not self.window:
            self.window = Window(self)
            self.window.connect("close-request", self._on_close)
            self.window.update_status(self.hub.status())
            self.window.update_usb(self.hub.usb.snapshot())
            if self.start_hidden:
                self.start_hidden = False
                return
        self.window.present()

    def present(self):
        self.activate()

    def _on_close(self, win):
        if self.config["run_in_background"]:
            win.set_visible(False)
            if not self._hidden_hint_shown:
                self._hidden_hint_shown = True
                self.notifier.show("Talk To Android arka planda çalışıyor",
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

    def _quit(self, *_):
        if self.bt:
            self.bt.stop()
        self.thread.stop()
        if self.config["run_in_background"]:
            self.release()
        self.quit()

    def _about(self, *_):
        compat.about(self.window, application_name="Talk To Android", application_icon=APP_ID,
                     version=__version__, developer_name="Crucible ekibi",
                     website="https://github.com/cruciblelab/arastirma",
                     comments="Linux bilgisayar ile Android telefonu USB, Wi-Fi ya da Bluetooth üzerinden bağlar.")

    # ---- hub'a komut ----------------------------------------------------------

    def call(self, method, *args):
        self.hub.submit(getattr(self.hub, method)(*args))

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
        """adb'yi dağıtımın paket yöneticisiyle kurar; şifre pkexec penceresinde sorulur."""
        cmd = system.adb_install_command()
        if not cmd or self.installing_adb:
            return
        self.installing_adb = True
        self.window.update_usb(self.hub.usb.snapshot())
        try:
            proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        except GLib.Error as e:
            self._adb_done(False, e.message)
            return

        def done(p, res):
            try:
                _ok, out, _err = p.communicate_utf8_finish(res)
            except GLib.Error as e:
                self._adb_done(False, e.message)
                return
            status = p.get_exit_status()
            # pkexec: 126 = şifre penceresi kapatıldı, 127 = yetki verilmedi
            msg = {126: "Kurulum iptal edildi", 127: "Yetki verilmedi"}.get(status, (out or "").strip()[-200:])
            self._adb_done(status == 0, msg)
        proc.communicate_utf8_async(None, None, done)

    def _adb_done(self, ok, msg):
        self.installing_adb = False
        if self.window:
            self.window.toast("adb kuruldu; telefonu USB ile takabilirsin" if ok else f"adb kurulamadı: {msg}")
            self.window.update_usb(self.hub.usb.snapshot())

    def install_phone_app(self, serial, replace=False):
        fut = self.hub.submit(self.hub.install_phone_app(serial, replace))

        def show(ok, msg):
            if msg == CONFLICT and self.window:
                self._ask_replace(serial)
            elif self.window:
                self.window.toast(msg)
            return False

        fut.add_done_callback(lambda f: GLib.idle_add(show, *f.result()))

    def _ask_replace(self, serial):
        d = compat.Dialog(self.window, "Telefondaki uygulama kaldırılıp yeniden kurulsun mu?",
                          CONFLICT + " Kurulumdan sonra telefonda bildirim erişimini yeniden vermen gerekir.")
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
        w = self.window
        if event == "status":
            self.device_names = {x["device_id"]: x["name"] for x in d.get("sessions", [])}
            self.phone_players.keep_only(self.device_names)
            if w:
                w.update_status(d)
        elif event == "usb":
            if w:
                w.update_usb(d)
        elif event == "ask":
            self._ask(d)
        elif event == "ask_closed":
            dlg = self.dialogs.pop(d["id"], None)
            if dlg:
                dlg.close()
        elif event == "notification":
            self.notifier.show(d["title"] or d["app"], d["text"], key=f"{d['device_id']}|{d['key']}",
                               app_name=f"{d['app']} · {d['device']}", icon=d.get("icon"))
            if w:
                w.add_notification(d)
        elif event == "notification_removed":
            self.notifier.close(f"{d['device_id']}|{d['key']}")
        elif event == "media":
            self.phone_players.update(d["device_id"], self.device_names.get(d["device_id"], "Telefon"), d["state"])
            if w:
                w.update_media(d["device_id"], d["state"])
        elif event == "media_art":
            self.phone_players.art(d["device_id"], d["art_id"])
            if w:
                w.update_media_art(d["device_id"], d["art_id"], d["path"])
        elif event == "transfer":
            if w:
                w.update_transfer(d)
            self._transfer_notice(d)
        elif event == "clipboard":
            Gdk.Display.get_default().get_clipboard().set_content(Gdk.ContentProvider.new_for_value(d["text"]))
            preview = d["text"] if len(d["text"]) < 120 else d["text"][:117] + "…"
            self.notifier.show(f"{d['device']} panosu kopyalandı", preview, key="pano")
        elif event == "open_url":
            Gio.AppInfo.launch_default_for_uri(d["url"], None)
        elif event == "connected":
            text = f"{d['name']} bağlandı ({KIND.get(d['kind'], d['kind'])})"
            if w and w.get_visible():
                w.toast(text)
            else:
                self.notifier.show(text, "Bildirimler ve medya artık bu bilgisayarda.", key="baglanti")
        elif event == "screenshot":
            self._screenshot(d["device_id"])
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

    def _dialog(self, heading, body, extra=None):
        return compat.Dialog(self.window, heading, body, extra)

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

    def _screenshot(self, device_id):
        def done(path, err):
            if path:
                self.call("send_file", device_id, path)
            else:
                # Portal yoksa ya da izin verilmediyse komut satırı araçlarını dene.
                s = self.hub.sessions.get(device_id)
                if s:
                    self.hub.submit(s._screenshot_headless())
        take_screenshot(done)

    def _ask(self, d):
        self.activate()
        rid = d["id"]
        pids = []
        if d["kind"] == "pair":
            via = {"usb": "USB kablosu", "bluetooth": f"Bluetooth ({d['ip']})"}.get(d["transport"], f"Wi-Fi ({d['ip']})")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.append(Gtk.Label(label="Telefondaki kod", css_classes=["dim-label"]))
            code = d["code"]
            box.append(Gtk.Label(label=f"{code[:3]} {code[3:]}", css_classes=["pair-code"]))
            pids = list(d.get("profiles") or {})
            if pids:
                prof_row = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, margin_top=10)
                prof_row.append(Gtk.Label(label="Profil"))
                chooser = Gtk.DropDown.new_from_strings([d["profiles"][p] for p in pids])
                if d.get("default_profile") in pids:
                    chooser.set_selected(pids.index(d["default_profile"]))
                prof_row.append(chooser)
                box.append(prof_row)
            dlg = self._dialog(
                "Telefon bağlanmak istiyor",
                f"{d['name']}" + (f" ({d['model']})" if d.get("model") else "") + f" · {via}\n\n"
                "Yalnızca telefonda da aynı kod görünüyorsa bağlan. "
                "Telefonun neler yapabileceğini seçtiğin profil belirler (Cihazlar → Profiller).",
                box)
            dlg.add_response("reject", "Reddet")
            dlg.add_response("accept", "Bağlan")
            dlg.set_appearance("accept", compat.SUGGESTED)
            self.notifier.show("Telefon bağlanmak istiyor", f"{d['name']} · kod {code}", key=f"ask{rid}",
                               urgent=True, actions={"default": ("Göster", self.present)})
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")
    hidden = "--arka-planda" in argv
    argv = [a for a in argv if a != "--arka-planda"]
    return App(start_hidden=hidden).run(argv)


if __name__ == "__main__":
    sys.exit(run(sys.argv))
