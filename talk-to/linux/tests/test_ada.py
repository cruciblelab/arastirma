"""Üst ada: Talk To tarafındaki durum/eylem köprüsü (D-Bus dahil), zamanlayıcı ve eklentinin kurulumu.
Eklentinin kendisi gerçek GNOME Shell'de gnome-ada/test/uctan_uca.sh ile sınanır."""

import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("GSETTINGS_BACKEND", "memory")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib  # noqa: E402

from talkto.config import Config  # noqa: E402
from talkto.nowplaying import NowPlaying  # noqa: E402
from talkto.ui import ada  # noqa: E402

GNOME_ADA = Path(__file__).resolve().parents[2] / "gnome-ada"


def load_build():
    spec = importlib.util.spec_from_file_location("ada_build", GNOME_ADA / "build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeNotifier:
    def __init__(self):
        self.shown = []

    def show(self, *a, **kw):
        self.shown.append((a, kw))


class FakeApp:
    def __init__(self, conn=None):
        self.config = Config(Path(tempfile.mkdtemp()))
        self.now = NowPlaying()
        self.art_paths = {}
        self.calls = []
        self.notifier = FakeNotifier()
        self.presented = 0
        self.conn = conn

    def get_dbus_connection(self):
        return self.conn

    def call(self, *a):
        self.calls.append(a)

    def present(self):
        self.presented += 1


SESS = {"device_id": "p", "name": "POCO", "battery": {"level": 64}}
CALL = {"device_id": "p", "key": "k1", "app": "WhatsApp", "caller": "Babam", "state": "ringing",
        "actions": [{"i": 0, "title": "Reddet"}, {"i": 1, "title": "Yanıtla"}]}


class StateTest(unittest.TestCase):
    def setUp(self):
        self.app = FakeApp()
        self.ada = ada.AdaService(self.app)

    def tearDown(self):
        self.ada.cancel_timer(quiet=True)

    def test_defaults_and_theme(self):
        st = self.ada.state()
        self.assertTrue(st["enabled"])
        self.assertEqual(st["theme"], ada.THEMES["deniz"][1])
        self.assertIsNone(st["phone"])
        self.assertIsNone(st["media"])
        self.app.config.set("ada_theme", "gece")
        self.app.config.set("ada_enabled", False)
        st = self.ada.state()
        self.assertEqual(st["theme"]["bg1"], ada.THEMES["gece"][1]["bg1"])
        self.assertFalse(st["enabled"])
        self.app.config.set("ada_theme", "yok-boyle-tema")
        self.assertEqual(self.ada.state()["theme"], ada.THEMES["deniz"][1])

    def test_phone_and_media(self):
        self.ada.on_event("status", {"sessions": [SESS]})
        art = Path(tempfile.mkdtemp()) / "k.png"
        art.write_bytes(b"x")
        self.app.art_paths["a1"] = str(art)
        self.app.now.update("p", {"active": True, "title": "Firuze", "artist": "Sezen Aksu", "playing": True,
                                  "art_id": "a1"})
        st = self.ada.state()
        self.assertEqual((st["phone"], st["battery"]), ("POCO", 64))
        self.assertEqual(st["media"]["title"], "Firuze")
        self.assertEqual(st["media"]["art"], str(art))
        self.assertEqual(st["media"]["device_id"], "p")
        json.dumps(st)  # D-Bus'a JSON olarak gider

    def test_events_bump_seq_and_kind(self):
        seq = self.ada.state()["event"]["seq"]
        self.ada.on_track()
        self.assertEqual(self.ada.state()["event"], {"kind": "track", "seq": seq + 1})
        self.ada.on_event("status", {"sessions": [SESS]})  # olay değil: ada büyümez
        self.assertEqual(self.ada.state()["event"]["seq"], seq + 1)

    def test_call_lifecycle(self):
        self.ada.on_event("status", {"sessions": [SESS]})
        self.ada.on_event("call", CALL)
        st = self.ada.state()
        self.assertEqual(st["event"]["kind"], "call")
        self.assertEqual(st["call"]["caller"], "Babam")
        self.assertIsNone(st["call"]["since"])
        seq = st["event"]["seq"]
        self.ada.on_event("call", dict(CALL, state="active"))  # cevaplandı: süre başlar
        st = self.ada.state()
        self.assertIsNotNone(st["call"]["since"])
        since = st["call"]["since"]
        self.ada.on_event("call", dict(CALL, state="active"))  # aynı durum: yeni olay değil, süre korunur
        self.assertEqual(self.ada.state()["event"]["seq"], seq + 1)
        self.assertEqual(self.ada.state()["call"]["since"], since)
        self.ada.on_event("call_ended", {"device_id": "p", "key": "k1"})
        self.assertIsNone(self.ada.state()["call"])

    def test_call_cleared_when_phone_leaves(self):
        self.ada.on_event("status", {"sessions": [SESS]})
        self.ada.on_event("call", CALL)
        self.ada.on_event("status", {"sessions": []})
        self.assertIsNone(self.ada.state()["call"])

    def test_notifications_grouped_by_app(self):
        for key, app, text in (("1", "WhatsApp", "a"), ("2", "WhatsApp", "b"), ("3", "Gmail", "c")):
            self.ada.on_event("notification", {"device_id": "p", "key": key, "app": app, "title": "T", "text": text})
            time.sleep(0.002)
        st = self.ada.state()
        self.assertEqual(st["event"]["kind"], "notification")
        self.assertEqual([(n["app"], n["count"]) for n in st["notifications"]], [("Gmail", 1), ("WhatsApp", 2)])
        self.assertEqual(st["notifications"][1]["last"], "T: b")
        self.ada.on_event("notification_removed", {"device_id": "p", "key": "3"})
        self.assertEqual([n["app"] for n in self.ada.state()["notifications"]], ["WhatsApp"])
        self.ada.notifs["WhatsApp"]["time"] -= ada.NOTIF_KEEP + 1  # bir saatten eski: gösterilmez
        self.assertEqual(self.ada.state()["notifications"], [])

    def test_notification_icon(self):
        icon = Path(tempfile.mkdtemp()) / "wa.png"
        icon.write_bytes(b"x")
        self.ada.on_event("notification", {"device_id": "p", "key": "1", "app": "WhatsApp", "text": "a",
                                           "icon": str(icon)})
        self.ada.on_event("notification", {"device_id": "p", "key": "2", "app": "Gmail", "text": "b",
                                           "icon": "/yok/boyle.png"})  # silinmiş önbellek: gösterilmez
        icons = {n["app"]: n["icon"] for n in self.ada.state()["notifications"]}
        self.assertEqual(icons, {"WhatsApp": str(icon), "Gmail": None})

    def test_track_change_does_not_drop_to_empty(self):
        """Şarkı değişirken telefon bir an "çalmıyor" derse ada boşa düşmez; süre dolunca gerçekten kapanır."""
        self.app.now.update("p", {"active": True, "title": "Firuze", "playing": True})
        self.assertEqual(self.ada.state()["media"]["title"], "Firuze")
        self.app.now.update("p", {"active": False})
        m = self.ada.state()["media"]
        self.assertEqual((m["title"], m["playing"]), ("Firuze", False))
        self.ada._last_media_t -= ada.MEDIA_GRACE + 0.1
        self.assertIsNone(self.ada.state()["media"])
        self.ada.stop()

    def test_cover_arrival_refreshes(self):
        seq = self.ada.seq
        self.ada._emit_id = 0
        self.ada.on_event("media_art", {"device_id": "p", "art_id": "a", "path": "/x"})
        self.assertTrue(self.ada._emit_id)  # eklentiye "değişti" gidecek (olay değil: ada büyümez)
        self.assertEqual(self.ada.seq, seq)

    def test_actions(self):
        self.ada.on_event("status", {"sessions": [SESS]})
        self.app.now.update("p", {"active": True, "title": "x", "playing": True})
        self.ada.action({"do": "media", "action": "play_pause"})
        self.ada.action({"do": "media", "action": "rm -rf"})  # bilinmeyen eylem gönderilmez
        self.ada.action({"do": "call", "key": "k1", "i": 1})  # arama yokken yok sayılır
        self.ada.on_event("call", CALL)
        self.ada.action({"do": "call", "key": "baska", "i": 1})  # başka aramanın düğmesi: yok sayılır
        self.ada.action({"do": "call", "key": "k1", "i": 1})
        self.ada.action({"do": "call_volume", "up": True})
        self.ada.action({"do": "open"})
        self.assertEqual(self.app.calls, [("media_control", "p", "play_pause", None), ("call_action", "p", "k1", 1),
                                          ("call_volume", "p", True)])
        self.assertEqual(self.app.presented, 1)

    def test_timer_on_phone_and_cancel(self):
        self.ada.on_event("status", {"sessions": [SESS]})
        self.ada.action({"do": "timer", "seconds": 300, "phone": True})
        st = self.ada.state()["timer"]
        self.assertEqual((st["total"], st["phone"]), (300, True))
        self.assertAlmostEqual(st["ends_at"], time.time() + 300, delta=2)
        self.assertEqual(self.app.calls, [("phone_timer", "p", 300, "Zamanlayıcı · 5 dk")])
        self.ada.action({"do": "timer_cancel"})
        self.assertIsNone(self.ada.state()["timer"])
        self.assertEqual(self.app.calls[-1], ("phone_timer", "p", 0, ""))

    def test_timer_local_only(self):
        self.ada.action({"do": "timer", "seconds": 60, "phone": True})  # telefon yok: yalnızca bilgisayarda
        self.assertFalse(self.ada.state()["timer"]["phone"])
        self.ada.on_event("status", {"sessions": [SESS]})
        self.ada.action({"do": "timer", "seconds": 90, "phone": False})  # yenisi eskisinin yerine geçer
        self.assertEqual(self.ada.state()["timer"]["total"], 90)
        self.assertEqual(self.app.calls, [])
        for bad in (0, -5, 10 ** 9):
            self.ada.action({"do": "timer", "seconds": bad})
            self.assertEqual(self.ada.state()["timer"]["total"], 90)

    def test_timer_done_notifies(self):
        self.ada.action({"do": "timer", "seconds": 60})
        self.ada.timer["source"] and GLib.source_remove(self.ada.timer["source"])
        self.ada.timer["source"] = 0
        self.ada._timer_done()
        self.assertIsNone(self.ada.timer)
        (title, _), kw = self.app.notifier.shown[0]
        self.assertEqual(title, "Süre doldu")
        self.assertTrue(kw["urgent"])
        self.assertEqual(self.ada.state()["event"]["kind"], "timer")


class DBusTest(unittest.TestCase):
    """Eklentinin kullandığı arayüz: GetState, Action, Changed (gerçek oturum veriyolunda)."""

    def setUp(self):
        try:
            self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            self.skipTest("oturum veriyolu yok")
        self.app = FakeApp(self.conn)
        self.ada = ada.AdaService(self.app)
        self.client = Gio.DBusConnection.new_for_address_sync(
            Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None),
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)

    def tearDown(self):
        self.ada.stop()
        self.client.close_sync(None)

    def _call(self, method, args=None):
        # Hizmet de bu iş parçacığının ana döngüsünde yanıtlar: eşzamanlı çağrı kendini bekler, döngüyü döndür.
        box = []
        self.client.call(self.conn.get_unique_name(), ada.PATH, ada.IFACE, method, args, None,
                         Gio.DBusCallFlags.NONE, 3000, None, lambda c, r: box.append(c.call_finish(r)))
        self._spin(lambda: box)
        return box[0].unpack()

    @staticmethod
    def _spin(done, seconds=3):
        ctx = GLib.MainContext.default()
        end = time.monotonic() + seconds
        while not done() and time.monotonic() < end:
            ctx.iteration(False)
            time.sleep(0.005)

    def test_get_state_action_and_signal(self):
        self.ada.on_event("status", {"sessions": [SESS]})
        st = json.loads(self._call("GetState")[0])
        self.assertEqual(st["phone"], "POCO")
        got = []
        self.client.signal_subscribe(None, ada.IFACE, "Changed", ada.PATH, None, Gio.DBusSignalFlags.NONE,
                                     lambda *a: got.append(json.loads(a[5].unpack()[0])))
        self.ada.on_event("call", CALL)
        self._call("Action", GLib.Variant("(s)", (json.dumps({"do": "call", "key": "k1", "i": 0}),)))
        self._call("Action", GLib.Variant("(s)", ("bu json değil",)))  # bozuk istek: yanıt döner, çökmez
        self._spin(lambda: got)
        self.assertEqual(self.app.calls, [("call_action", "p", "k1", 0)])
        self.assertTrue(got)
        self.assertEqual(got[-1]["call"]["caller"], "Babam")
        self.assertEqual(got[-1]["event"]["kind"], "call")


class BuildAndInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.build = load_build()
        self.out = self.build.build(self.tmp / "build")

    def test_two_variants(self):
        for name, versions in (("45", ["45", "46", "47", "48"]), ("42", ["42", "43", "44"])):
            d = self.out / name
            meta = json.loads((d / "metadata.json").read_text())
            self.assertEqual(meta["uuid"], ada.UUID)
            self.assertEqual(meta["shell-version"], versions)
            self.assertIsInstance(meta["version"], int)
            self.assertTrue((d / "stylesheet.css").is_file())
        new = (self.out / "45" / "extension.js").read_text()
        old = (self.out / "42" / "extension.js").read_text()
        self.assertIn("export default class AdaExtension extends Extension", new)
        self.assertNotRegex(old, r"(?m)^\s*(import|export) ")
        self.assertIn("imports.gi", old)
        self.assertIn("function init()", old)
        # Talk To ile eklenti aynı adı ve yolu kullanmalı
        for text in (new, old):
            self.assertIn("'lab.crucible.TalkToAndroid'", text)
            self.assertIn(ada.PATH, text)
            self.assertIn(ada.IFACE, text)

    def test_install_refresh_uninstall(self):
        data = self.tmp / "data"
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(data)}), \
                mock.patch.object(ada, "shell_version", return_value=42), \
                mock.patch.object(ada, "source_dir", side_effect=lambda v: self.out / ("45" if v >= 45 else "42")), \
                mock.patch.object(ada, "_shell_settings", return_value=None):
            self.assertEqual(ada.running_state(), "absent")
            self.assertTrue(ada.install()[0])
            dest = data / "gnome-shell" / "extensions" / ada.UUID
            self.assertIn("function init()", (dest / "extension.js").read_text())
            self.assertEqual(ada.installed_version(), self.build.META["version"])
            # paket güncellendi (sürüm büyüdü): kopya yenilenir
            meta = json.loads((dest / "metadata.json").read_text())
            (dest / "metadata.json").write_text(json.dumps(dict(meta, version=0)))
            ada.refresh_if_outdated()
            self.assertEqual(ada.installed_version(), self.build.META["version"])
            self.assertTrue(ada.uninstall()[0])
            self.assertFalse(dest.exists())
            self.assertEqual(ada.running_state(), "absent")

    def test_install_without_gnome(self):
        with mock.patch.object(ada, "shell_version", return_value=None):
            ok, msg = ada.install()
        self.assertFalse(ok)
        self.assertIn("GNOME", msg)
        with mock.patch.object(ada, "shell_version", return_value=40):
            self.assertFalse(ada.install()[0])


if __name__ == "__main__":
    unittest.main()
