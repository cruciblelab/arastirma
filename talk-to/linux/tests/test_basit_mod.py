"""Basit mod (talkto.features), çalanın izi (talkto.nowplaying) ve bunların penceredeki etkisi.

Pencere testi ekran ister; ekran yoksa atlanır (CI'da TALKTO_TEST_STRICT=1 iken atlanmaz).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from talkto import features  # noqa: E402
from talkto.config import Config  # noqa: E402
from talkto.nowplaying import NowPlaying  # noqa: E402


def song(title, playing=True, artist="Sezen Aksu"):
    return {"active": True, "playing": playing, "title": title, "artist": artist, "player": "Spotify"}


class FeaturesTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(tempfile.mkdtemp())

    def test_new_install_is_simple(self):
        self.assertTrue(self.cfg["simple_mode"])
        self.assertEqual(features.enabled(self.cfg), set(features.CORE))
        self.assertFalse(features.shown(self.cfg, "files"))

    def test_extras_added_one_by_one(self):
        self.cfg.set("extras", ["files", "bilinmeyen"])
        self.assertEqual(features.enabled(self.cfg), set(features.CORE) | {"files"})

    def test_full_mode_shows_all(self):
        self.cfg.set("simple_mode", False)
        self.assertEqual(features.enabled(self.cfg), set(features.CORE) | set(features.EXTRAS))

    def test_old_config_gets_defaults(self):
        d = tempfile.mkdtemp()
        Path(d, "ayarlar.json").write_text('{"wireless": false}')
        cfg = Config(d)
        self.assertTrue(cfg["simple_mode"])
        self.assertFalse(cfg["mini_player_pinned"])
        self.assertTrue(cfg["track_popup"])


class NowPlayingTest(unittest.TestCase):
    def test_start_track_stop(self):
        n = NowPlaying()
        ev = n.update("a", song("Gesi Bağları"))
        self.assertTrue(ev["started"] and ev["track"])
        self.assertEqual(n.shown()[0], "a")
        # Konum güncellemesi: yeni bir şey yok.
        ev = n.update("a", song("Gesi Bağları"))
        self.assertFalse(ev["started"] or ev["track"] or ev["stopped"])
        ev = n.update("a", song("Firuze"))
        self.assertTrue(ev["track"])
        self.assertFalse(ev["started"])
        ev = n.update("a", {"active": False})
        self.assertTrue(ev["stopped"])
        self.assertIsNone(n.shown()[0])

    def test_pause_resume_does_not_reopen(self):
        n = NowPlaying()
        n.update("a", song("Firuze"))
        ev = n.update("a", song("Firuze", playing=False))
        self.assertFalse(ev["track"] or ev["stopped"])
        ev = n.update("a", song("Firuze"))
        self.assertFalse(ev["started"] or ev["track"])
        self.assertEqual(n.shown()[0], "a")  # duraklatılmış parça da gösterilir

    def test_paused_new_track_is_quiet(self):
        n = NowPlaying()
        ev = n.update("a", song("Firuze", playing=False))
        self.assertFalse(ev["started"] or ev["track"])

    def test_two_phones_playing_one_wins(self):
        n = NowPlaying()
        n.update("a", song("Firuze", playing=False))
        n.update("b", song("Kaybolan Yıllar"))
        self.assertEqual(n.shown()[0], "b")
        n.update("b", {"active": False})
        self.assertEqual(n.shown()[0], "a")
        n.keep_only({"b"})
        self.assertIsNone(n.shown()[0])


try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import GLib, Gtk
    HAVE = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and Gtk.init_check()
except (ImportError, ValueError):
    HAVE = False

if not HAVE and os.environ.get("TALKTO_TEST_STRICT"):
    raise RuntimeError("arayüz testleri çalıştırılamıyor: GTK4/libadwaita ya da ekran yok")


@unittest.skipUnless(HAVE, "GTK4/libadwaita ya da ekran yok")
class WindowTest(unittest.TestCase):
    """Gerçek pencere: basit mod sayfaları ve düğmeleri gizler, kapatınca hepsi görünür."""

    def test_simple_mode_toggles_pages(self):
        tmp = tempfile.mkdtemp()
        os.environ["TALKTO_CONFIG_DIR"] = tmp + "/cfg"
        os.environ["TALKTO_CACHE_DIR"] = tmp + "/cache"
        from talkto.hub import Hub
        from talkto.ui.app import App

        def factory(config, emit):
            config.set("port", 47691)
            config.set("setup_done", True)
            config.set("wireless", False)
            config.set("usb", False)
            config.set("bluetooth", False)
            config.set("run_in_background", False)
            return Hub(config, emit, enable_media=False, enable_discovery=False)

        app = App(hub_factory=factory)
        seen = {}

        def check():
            try:
                w = app.window
                seen["simple"] = {n: p.get_visible() for n, p in w.pages.items()}
                seen["profiles"] = w.profile_group.get_visible()
                w.sw_simple.set_active(False)
                seen["full"] = {n: p.get_visible() for n, p in w.pages.items()}
                seen["saved"] = app.config["simple_mode"]
                w.sw_simple.set_active(True)
                w.sw_extras["commands"].set_active(True)
                seen["extra"] = {n: p.get_visible() for n, p in w.pages.items()}
                seen["extras"] = list(app.config["extras"])
                # Müzik başlayınca sabitlenmiş mini oynatıcı kendiliğinden açılır.
                # Mini oynatıcı boşken ve çalarken aynı yeri kaplar (Wayland'de boyut zıplaması uygulamayı kapatıyordu).
                from talkto.ui.miniplayer import MiniPlayer
                probe = MiniPlayer(app)
                empty_h = probe.get_content().measure(Gtk.Orientation.VERTICAL, 440)[1]
                probe.show_state("p", "Pixel", song("Çok çok uzun bir şarkı adı " * 4), None)
                seen["mini_heights"] = (empty_h, probe.get_content().measure(Gtk.Orientation.VERTICAL, 440)[1])
                seen["mini_resizable"] = probe.get_resizable()
                # ⋮ menüsü: boyut ön ayarı pencereyi büyütüp küçültür; tepecik ince şerittir.
                probe.present()
                sizes = {}
                for key in ("kucuk", "buyuk"):
                    probe.activate_action("mini.size", GLib.Variant("s", key))
                    sizes[key] = probe.get_default_size()
                probe.activate_action("mini.compact", None)
                sizes["tepecik"] = probe.get_default_size()
                seen["mini_sizes"] = sizes
                seen["mini_cfg"] = (app.config["mini_size"], app.config["mini_compact"])
                probe.activate_action("mini.compact", None)
                # Masaüstü pencereyi büyütmek isterse (ekranın üstüne sürükleme) tam ekran olmaz, tepeciğe döner.
                probe.is_maximized = lambda: True
                probe._on_maximized()
                probe.is_maximized = lambda: False
                ctx = GLib.MainContext.default()
                while ctx.pending():
                    ctx.iteration(False)
                seen["mini_snap"] = probe.compact
                probe.set_compact(False)
                # Üstte tut: X11'de (sanal ekran) pencere yöneticisinden istenir, ayar açık kalır;
                # üstte tutulabilecek ekran yoksa (XWayland'siz Wayland) ayar kapanır, nasıl yapılacağı söylenir.
                app.mini = probe
                probe.activate_action("mini.top", None)
                seen["pin_x11"] = (app.config["mini_on_top"], probe.a_top.get_state().get_boolean())
                probe.activate_action("mini.top", None)
                from talkto.ui import ustte
                real = ustte.x11_display
                ustte.x11_display = lambda: None
                probe.activate_action("mini.top", None)
                seen["pin_wayland"] = (app.config["mini_on_top"], probe.a_top.get_state().get_boolean())
                ustte.x11_display = real
                probe.close()
                app.set_pinned(True)
                app.on_event("status", {**app.hub.status(), "sessions": [
                    {"device_id": "p", "name": "Pixel", "kind": "wifi", "ip": "1.2.3.4", "media": {"active": False},
                     "problems": [], "profile_name": "Benim telefonum"}]})
                app.on_event("media", {"device_id": "p", "state": song("Firuze")})
                # Üst karttaki baloncuk: telefonun sistem bilgileri; açılınca tazesi istenir.
                asked = []
                real_call = app.call
                app.call = lambda *a: asked.append(a)
                st = app.hub.status()
                st["sessions"] = [{"device_id": "p", "name": "Pixel", "kind": "usb", "ip": "", "problems": [],
                                   "media": {"active": False}, "profile_name": "Benim telefonum",
                                   "battery": {"level": 76, "charging": True},
                                   "info": {"manufacturer": "Google", "model": "Pixel 8", "android": "14",
                                            "sdk": 34}}]
                app.on_event("status", st)
                chip = w.hero_chips.get_first_child()
                chip.popup()
                grid = chip.get_popover().get_child()
                labels = []
                child = grid.get_first_child()
                while child:
                    labels.append(child.get_label())
                    child = child.get_next_sibling()
                seen["chip"] = (chip.get_label(), labels, asked)
                chip.popdown()
                app.call = real_call
                # Aynı telefon tek satırda: Wi-Fi'den bağlı ve USB'de takılı telefon ayrıca "USB'de" grubunda
                # görünmez; eşleşmiş telefonlar tek, katlanmış satırdır.
                st = app.hub.status()
                st["sessions"] = [{"device_id": "p", "name": "Pixel", "kind": "wifi", "ip": "1.2.3.4", "problems": [],
                                   "media": {"active": False}, "profile_name": "Benim telefonum", "adb_serial": "S1"}]
                st["trusted"] = [{"device_id": d, "name": n, "model": "", "paired_at": 1, "profile": "benim"}
                                 for d, n in (("p", "Pixel"), ("q", "Eski telefon"))]
                app.on_event("status", st)
                w.update_usb({"devices": [{"serial": "S1", "state": "device", "model": "Pixel", "app": True}]})
                rows = w.phones_group.rows
                seen["phones"] = ([type(r).__name__ for r in rows], rows[0].get_subtitle(),
                                  rows[-1].get_subtitle() if rows else "")
                seen["mini"] = bool(app.mini and app.mini.get_visible())
                seen["mini_shows"] = app.mini.device_id if app.mini else None
                seen["pin_switch"] = w.sw_pin.get_active()
                # Şarkı bildirimi: mini oynatıcı açıkken çıkmaz (aynı bilgi ekranda), kapalıyken çıkar.
                shown = []
                app.notifier.show = lambda title, body="", **kw: shown.append((title, body, kw))
                app._track_popup("p")
                seen["popup_with_mini"] = len(shown)
                app.mini.close()
                app._track_popup("p")
                seen["popup"] = shown
                # Arama: çalarken acil ve uygulamanın düğmeleri; sürerken kalıcı, Kapat + görüşme sesi.
                calls = []
                app.notifier.show = lambda title, body="", **kw: calls.append((title, kw))
                sent = []
                app.call = lambda *a: sent.append(a)
                base = {"device_id": "p", "device": "Pixel", "key": "k", "app": "WhatsApp", "caller": "Ayşe",
                        "text": "Gelen sesli arama", "icon": None}
                app.on_event("call", dict(base, state="ringing", actions=[{"i": 0, "title": "Reddet"},
                                                                         {"i": 1, "title": "Cevapla"}]))
                app.on_event("call", dict(base, state="ongoing", text="Sesli arama",
                                          actions=[{"i": 0, "title": "Kapat"}]))
                seen["calls"] = [(t, kw["urgent"], kw["resident"], {k: v[0] for k, v in kw["actions"].items()})
                                 for t, kw in calls]
                app.on_event("call", dict(base, state="ongoing", key="k2",
                                          actions=[{"i": 0, "title": "Hang up"}, {"i": 1, "title": "Turn speaker off"}]))
                seen["call_two"] = {k: v[0] for k, v in calls[-1][1]["actions"].items()}
                calls[0][1]["actions"]["a1"][1]()
                calls[1][1]["actions"]["ses_artir"][1]()
                seen["call_sent"] = sent
            finally:
                app._quit()
            return False

        app.connect("activate", lambda *_: GLib.idle_add(check))
        app.run([])
        self.assertEqual(seen["simple"], {"telefonlar": True, "medya": True, "dosyalar": False,
                                          "bildirimler": True, "komutlar": False})
        self.assertFalse(seen["profiles"])
        self.assertTrue(all(seen["full"].values()))
        self.assertFalse(seen["saved"])
        self.assertTrue(seen["extra"]["komutlar"])
        self.assertFalse(seen["extra"]["dosyalar"])
        self.assertEqual(seen["extras"], ["commands"])
        label, info_labels, asked = seen["chip"]
        self.assertEqual(label, "USB · %76 ⚡")
        self.assertIn("Google Pixel 8", info_labels)
        self.assertIn("Android 14 (API 34)", info_labels)
        self.assertEqual(asked, [("request_phone_info", "p")])
        self.assertTrue(seen["mini"])
        self.assertEqual(seen["mini_shows"], "p")
        self.assertTrue(seen["pin_switch"])
        self.assertEqual(seen["mini_heights"][0], seen["mini_heights"][1])
        self.assertTrue(seen["mini_resizable"])
        kinds, sub, trusted_sub = seen["phones"]
        self.assertEqual(kinds, ["ActionRow", "ExpanderRow"])
        self.assertIn("USB'de takılı", sub)
        self.assertIn("Eski telefon", trusted_sub)
        self.assertEqual(seen["pin_x11"], (True, True))
        self.assertEqual(seen["pin_wayland"], (False, False))
        sz = seen["mini_sizes"]
        self.assertLess(sz["kucuk"][0], sz["buyuk"][0])
        self.assertLess(sz["kucuk"][1], sz["buyuk"][1])
        self.assertLess(sz["tepecik"][1], 80)  # ince şerit
        self.assertEqual(seen["mini_cfg"], ("buyuk", True))
        self.assertTrue(seen["mini_snap"])
        self.assertEqual(seen["popup_with_mini"], 0)
        (title, body, kw), = seen["popup"]
        self.assertEqual(title, "Firuze")
        self.assertIn("Sezen Aksu", body)
        self.assertEqual(set(kw["actions"]), {"default", "play_pause", "next"})
        ring, ongoing = seen["calls"]
        self.assertEqual(ring, ("WhatsApp araması: Ayşe", True, False, {"a0": "Reddet", "a1": "Cevapla"}))
        self.assertEqual(ongoing, ("WhatsApp görüşmesi: Ayşe", False, True,
                                   {"a0": "Kapat", "ses_azalt": "Ses −", "ses_artir": "Ses +"}))
        # Uygulama iki düğme koyarsa (Kapat, Hoparlör) ses düğmeleri sığmaz: yarım "Ses −" çıkmaz.
        self.assertEqual(seen["call_two"], {"a0": "Hang up", "a1": "Turn speaker off"})
        self.assertEqual(seen["call_sent"], [("call_action", "p", "k", 1), ("call_volume", "p", True)])


if __name__ == "__main__":
    unittest.main()
