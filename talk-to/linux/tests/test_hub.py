"""Çekirdeğin uçtan uca testleri: gerçek TLS sunucusu + sahte telefon.

    cd talk-to/linux && python3 -m unittest discover -s tests -v
"""

import asyncio
import hashlib
import json
import os
import socket
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from sahte_telefon import FakePhone

from talkto import auth, mirror
from talkto.config import Config
from talkto.hub import Hub
from talkto.transfers import safe_name

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Base(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["TALKTO_CACHE_DIR"] = str(Path(self.tmp.name) / "cache")
        self.cfg = Config(Path(self.tmp.name) / "cfg")
        self.cfg.set("port", free_port())
        self.cfg.set("receive_dir", str(Path(self.tmp.name) / "gelen"))
        self.cfg.set("usb", True)       # 127.0.0.1 dinlenir, bağlantı "usb" sayılır
        self.cfg.set("wireless", False)
        self.events = []
        self.hub = Hub(self.cfg, emit=self._on_event, enable_media=False, enable_discovery=False)
        self.hub.usb.available = staticmethod(lambda: False)
        await self.hub.start()

    async def asyncTearDown(self):
        await self.hub.stop()
        self.tmp.cleanup()

    def _on_event(self, event, data):
        self.events.append((event, data))
        if event == "ask" and getattr(self, "answer", None) is not None:
            asyncio.get_running_loop().create_task(self.hub.answer(data["id"], self.answer))

    def of(self, event):
        return [d for e, d in self.events if e == event]

    async def paired_phone(self):
        self.answer = True
        p = FakePhone()
        self.assertEqual(await p.connect(port=self.cfg["port"]), "welcome")
        await asyncio.sleep(0.05)
        return p


class HubTest(_Base):
    async def test_usb_approval_shows_same_code_on_both_sides(self):
        self.answer = True
        p = FakePhone()
        self.assertEqual(await p.connect(port=self.cfg["port"]), "welcome")
        ask = self.of("ask")[0]
        self.assertEqual(ask["kind"], "pair")
        self.assertEqual(ask["transport"], "usb")
        self.assertEqual(ask["code"], p.code)
        self.assertIn(p.device_id, self.cfg.trusted())
        self.assertNotEqual(self.cfg.trusted()[p.device_id]["token_hash"], p.token)  # belirteç düz saklanmaz
        await p.close()

    async def test_rejected_approval(self):
        self.answer = False
        p = FakePhone()
        self.assertEqual(await p.connect(port=self.cfg["port"]), "rejected")
        self.assertNotIn(p.device_id, self.cfg.trusted())
        await p.close()

    async def test_token_reconnect_needs_no_approval(self):
        p = await self.paired_phone()
        token = p.token
        await p.close()
        self.answer = None  # artık soru sorulursa test zaman aşımına düşer
        asks = len(self.of("ask"))
        p2 = FakePhone()
        self.assertEqual(await p2.connect(port=self.cfg["port"], token=token), "welcome")
        self.assertEqual(len(self.of("ask")), asks)
        await p2.close()

    async def test_wrong_token_falls_back_to_approval(self):
        p = await self.paired_phone()
        await p.close()
        self.answer = False
        p2 = FakePhone()
        self.assertEqual(await p2.connect(port=self.cfg["port"], token="0" * 64), "rejected")
        await p2.close()

    async def test_qr_pairs_without_asking_once(self):
        """Karekod: anahtarı bilen telefon onay sorulmadan (şifre de sorulmadan) eşleşir; anahtar bir kez geçer."""
        from urllib.parse import parse_qs, urlsplit
        self.cfg.set("password", "şifre")
        self.answer = None  # soru sorulursa test zaman aşımına düşer
        info = await self.hub.qr_start()
        self.assertTrue(info["wireless_turned_on"])  # karekod Wi-Fi içindir: kapalıysa açılır
        self.assertTrue(self.cfg["wireless"])
        q = {k: v[0] for k, v in parse_qs(urlsplit(info["link"]).query).items()}
        self.assertTrue(info["link"].startswith("talkto://pair?v=1&"))
        self.assertEqual((q["fp"], int(q["p"])), (self.hub.identity.fingerprint, self.cfg["port"]))
        p = FakePhone()
        self.assertEqual(await p.connect(port=self.cfg["port"], qr_key=q["k"]), "welcome")
        self.assertEqual(self.of("ask"), [])
        self.assertEqual([e["name"] for e in self.of("paired_by_qr")], ["Test Telefonu"])
        self.assertIn(p.device_id, self.cfg.trusted())
        await p.close()
        again = FakePhone("telefon-test-0002")  # aynı karekod ikinci kez geçmez
        self.assertEqual(await again.connect(port=self.cfg["port"], qr_key=q["k"]), "qr_expired")
        await again.close()
        self.assertNotIn("telefon-test-0002", self.cfg.trusted())

    async def test_qr_wrong_or_expired_key(self):
        self.answer = None
        none = FakePhone("telefon-test-0003")  # karekod gösterilmiyor
        self.assertEqual(await none.connect(port=self.cfg["port"], qr_key="0" * 32), "qr_expired")
        await none.close()
        await self.hub.qr_start()
        bad = FakePhone("telefon-test-0004")
        self.assertEqual(await bad.connect(port=self.cfg["port"], qr_key="0" * 32), "wrong_qr")
        await bad.close()
        self.hub.qr["until"] = 0  # süresi doldu
        self.assertIsNone(self.hub.qr_key())
        self.assertEqual(self.cfg.trusted(), {})

    async def test_wifi_password(self):
        self.cfg.set("password", "doğru-şifre")
        sess_kind = {}
        orig = self.hub._on_connection

        async def as_wifi(reader, writer):  # testte gerçek Wi-Fi yok; bağlantıyı Wi-Fi say
            from talkto.hub import Session
            sess_kind["k"] = "wifi"
            await Session(self.hub, reader, writer, "wifi", "10.0.0.5").run()
        self.hub.server.close()
        self.hub.server = await asyncio.start_server(as_wifi, "127.0.0.1", self.cfg["port"],
                                                     ssl=self.hub.identity.server_context())
        bad = FakePhone()
        self.assertEqual(await bad.connect(port=self.cfg["port"], password="yanlış"), "wrong_password")
        await bad.close()
        good = FakePhone("telefon-test-0002")
        self.assertEqual(await good.connect(port=self.cfg["port"], password="doğru-şifre"), "welcome")
        self.assertEqual(self.of("ask"), [])  # şifre doğruysa ekranda onay sorulmaz
        await good.close()
        for _ in range(4):
            b = FakePhone()
            await b.connect(port=self.cfg["port"], password="yanlış")
            await b.close()
        blocked = FakePhone("telefon-test-0003")
        self.assertEqual(await blocked.connect(port=self.cfg["port"], password="doğru-şifre"),
                         "too_many_attempts")
        await blocked.close()
        del orig

    async def _as_wifi_server(self):
        async def as_wifi(reader, writer):
            from talkto.hub import Session
            await Session(self.hub, reader, writer, "wifi", "10.0.0.5").run()
        self.hub.server.close()
        self.hub.server = await asyncio.start_server(as_wifi, "127.0.0.1", self.cfg["port"],
                                                     ssl=self.hub.identity.server_context())

    async def test_legacy_phone_still_pairs(self):
        """0.4 ve öncesi telefon: taahhütsüz onay kodu ve eski şifre kanıtı kabul edilir."""
        self.answer = True
        p = FakePhone(legacy=True)
        self.assertEqual(await p.connect(port=self.cfg["port"]), "welcome")
        self.assertEqual(self.of("ask")[0]["code"], p.code)
        await p.close()
        self.cfg.set("password", "gizli-şifre")
        await self._as_wifi_server()
        q = FakePhone("telefon-eski-0002", legacy=True)
        self.assertEqual(await q.connect(port=self.cfg["port"], password="gizli-şifre"), "welcome")
        await q.close()

    async def test_new_phone_uses_committed_code(self):
        self.answer = True
        p = FakePhone()
        self.assertEqual(await p.connect(port=self.cfg["port"]), "welcome")
        self.assertIn("pair2", p.server_features)
        self.assertEqual(self.of("ask")[0]["code"], p.code)
        await p.close()

    async def test_reveal_must_match_commit(self):
        self.answer = True

        class Cheater(FakePhone):  # nonce'u gördükten sonra başka bir değer açıklıyor
            async def send(self, msg):
                if msg.get("type") == "pair_reveal":
                    msg = dict(msg, secret="0" * 64)
                await super().send(msg)
        p = Cheater()
        self.assertEqual(await p.connect(port=self.cfg["port"]), "protocol")
        self.assertEqual(self.of("ask"), [])  # bilgisayarda onay penceresi hiç açılmadı
        await p.close()

    async def test_concurrent_password_guesses_are_limited(self):
        self.cfg.set("password", "doğru-şifre")
        await self._as_wifi_server()
        phones = [FakePhone(f"telefon-kaba-{i:04d}") for i in range(10)]
        results = await asyncio.gather(*(ph.connect(port=self.cfg["port"], password="yanlış") for ph in phones))
        self.assertLessEqual(results.count("wrong_password"), 5)
        self.assertGreaterEqual(results.count("too_many_attempts"), 5)
        for ph in phones:
            await ph.close()

    async def test_abandoned_pairing_counts_as_failure(self):
        self.answer = None  # soru açık kalsın
        await self._as_wifi_server()
        for i in range(5):
            p = FakePhone(f"telefon-vazgec-{i:03d}")
            task = asyncio.create_task(p.connect(port=self.cfg["port"]))
            for _ in range(50):
                if len(self.of("ask")) > i:
                    break
                await asyncio.sleep(0.05)
            task.cancel()
            await p.close()
            await asyncio.sleep(0.1)
        self.assertTrue(self.hub.blocked("10.0.0.5"))

    async def test_huge_frame_before_auth_is_rejected(self):
        import ssl as _ssl
        from talkto.protocol import encode_json
        ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        reader, writer = await asyncio.open_connection("127.0.0.1", self.cfg["port"], ssl=ctx)
        writer.write(encode_json({"type": "hello", "pad": "x" * 200_000}))
        await writer.drain()
        data = await asyncio.wait_for(reader.read(), 5)  # sunucu bağlantıyı kapatır
        self.assertEqual(data, b"")
        writer.close()

    async def test_receive_file_into_folder(self):
        p = await self.paired_phone()
        data = os.urandom(700_000)
        res = await p.send_file(5, "../../tatil.jpg", data)
        self.assertTrue(res["ok"], res)
        files = list(Path(self.cfg["receive_dir"]).iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].parent, Path(self.cfg["receive_dir"]))
        self.assertEqual(files[0].read_bytes(), data)
        self.assertEqual(self.of("transfer")[-1]["state"], "done")
        # Aynı ad ikinci kez gelirse üzerine yazılmaz.
        res = await p.send_file(6, "../../tatil.jpg", b"ikinci")
        self.assertTrue(res["ok"])
        self.assertEqual(len(list(Path(self.cfg["receive_dir"]).iterdir())), 2)
        await p.close()

    async def test_corrupt_file_is_discarded(self):
        p = await self.paired_phone()
        res = await p.send_file(7, "bozuk.bin", b"veri" * 1000, sha="0" * 64)
        self.assertFalse(res["ok"])
        self.assertEqual(list(Path(self.cfg["receive_dir"]).iterdir()), [])
        await p.close()

    async def test_send_file_to_phone(self):
        p = await self.paired_phone()
        src = Path(self.tmp.name) / "belge.pdf"
        src.write_bytes(os.urandom(600_000))
        task = asyncio.create_task(self.hub.send_file(p.device_id, str(src)))
        name, data = await p.receive_file()
        await task
        self.assertEqual(name, "belge.pdf")
        self.assertEqual(data, src.read_bytes())
        self.assertEqual(self.of("transfer")[-1]["state"], "done")
        await p.close()

    async def test_notification_battery_clipboard_url(self):
        p = await self.paired_phone()
        await p.send({"type": "battery", "level": 64, "charging": False})
        await p.send({"type": "notification", "key": "0|com.whatsapp|1", "package": "com.whatsapp",
                      "app": "WhatsApp", "title": "Ali", "text": "Geliyor musun?"})
        await p.send({"type": "clipboard", "text": "panodaki yazı"})
        await p.send({"type": "open_url", "url": "https://youtube.com/watch?v=x"})
        await p.send({"type": "open_url", "url": "file:///etc/passwd"})
        await asyncio.sleep(0.2)
        self.assertEqual(self.of("notification")[0]["title"], "Ali")
        self.assertEqual(self.hub.sessions[p.device_id].battery, {"level": 64, "charging": False})
        self.assertEqual(self.of("clipboard")[0]["text"], "panodaki yazı")
        self.assertEqual([d["url"] for d in self.of("open_url")], ["https://youtube.com/watch?v=x"])
        await p.close()

    async def test_media_control_is_forwarded_to_phone(self):
        p = await self.paired_phone()
        await p.send({"type": "media_state", "active": True, "player": "Spotify", "title": "Şarkı",
                      "artist": "Sanatçı", "playing": True, "position_ms": 1000, "duration_ms": 200000})
        await asyncio.sleep(0.1)
        self.assertEqual(self.of("media")[-1]["state"]["title"], "Şarkı")
        await self.hub.media_control(p.device_id, "next")
        self.assertEqual((await p.recv_type("media_control"))["action"], "next")
        await p.close()

    async def test_phone_info(self):
        """Telefonun sistem bilgileri durumda görünür; bilgisayar tazesini isteyebilir."""
        p = await self.paired_phone()
        await p.send({"type": "phone_info", "manufacturer": "Xiaomi", "model": "2311DRK48G", "android": "14",
                      "battery": {"level": 80, "charging": False, "temp_c": 30.0}})
        await asyncio.sleep(0.2)
        info = self.hub.status()["sessions"][0]["info"]
        self.assertEqual((info["model"], info["battery"]["level"]), ("2311DRK48G", 80))
        await self.hub.request_phone_info(p.device_id)
        self.assertEqual((await p.recv_type("phone_info_request"))["type"], "phone_info_request")
        await p.close()

    async def test_calls_with_their_buttons(self):
        """WhatsApp/Instagram araması bilgisayarda görünür; düğmeler ve görüşme sesi telefona gider."""
        p = await self.paired_phone()
        call = {"type": "call", "key": "0|com.whatsapp|7", "package": "com.whatsapp", "app": "WhatsApp",
                "caller": "Ayşe", "text": "Gelen sesli arama", "state": "ringing",
                "actions": [{"i": 0, "title": "Reddet"}, {"i": 1, "title": "Cevapla"}, {"i": 2, "title": ""},
                            "bozuk", {"i": 3, "title": "x" * 500}]}
        await p.send(call)
        await asyncio.sleep(0.2)
        c = self.of("call")[-1]
        self.assertEqual((c["caller"], c["state"], c["app"]), ("Ayşe", "ringing", "WhatsApp"))
        self.assertEqual([a["title"] for a in c["actions"]][:2], ["Reddet", "Cevapla"])
        self.assertEqual(len(c["actions"]), 3)  # boş başlık ve bozuk girdi atlanır
        self.assertEqual(len(c["actions"][2]["title"]), 40)
        await self.hub.call_action(p.device_id, c["key"], 1)
        self.assertEqual(await p.recv_type("call_action"), {"type": "call_action", "key": "0|com.whatsapp|7",
                                                             "action": 1})
        await p.send(dict(call, state="sürüyor?", actions=[{"i": 0, "title": "Kapat"}]))
        await self.hub.call_volume(p.device_id, False)
        self.assertEqual((await p.recv_type("call_volume"))["dir"], -1)
        # Telefon sonucu bildirir: ses kaçtan kaça, düğmeye basılamadıysa neden (günlüğe ve ekrana).
        await p.send({"type": "call_result", "kind": "volume", "before": 4, "after": 3, "max": 5,
                      "mode": "internet araması", "error": None})
        await p.send({"type": "call_result", "kind": "action", "title": "Kapat", "error": "CanceledException: x"})
        await asyncio.sleep(0.2)
        vol, act = self.of("call_result")[-2:]
        self.assertEqual((vol["kind"], vol["before"], vol["after"], vol["mode"]), ("volume", 4, 3, "internet araması"))
        self.assertEqual((act["kind"], act["title"], act["error"]), ("action", "Kapat", "CanceledException: x"))
        await p.send({"type": "call_ended", "key": "0|com.whatsapp|7"})
        await asyncio.sleep(0.2)
        self.assertEqual(self.of("call")[-1]["state"], "ongoing")  # bilinmeyen durum: süren sayılır
        self.assertEqual(self.of("call_ended")[-1]["key"], "0|com.whatsapp|7")
        # Arama biterken uygulama bildirimi önce düğmesiz günceller, sonra kaldırır; eski telefon uygulaması bunu
        # "bildirim kalktı" diye gönderiyordu: bilgisayar yine "arama bitti" saymalı (yoksa arama hep sürüyor görünür).
        await p.send(dict(call, key="0|com.android.dialer|1", state="ongoing", actions=[]))
        await p.send({"type": "notification_removed", "key": "0|com.android.dialer|1"})
        await p.send({"type": "notification_removed", "key": "0|com.whatsapp|99"})  # sıradan bildirim
        await asyncio.sleep(0.2)
        self.assertEqual(self.of("call_ended")[-1]["key"], "0|com.android.dialer|1")
        self.assertEqual([e["key"] for e in self.of("notification_removed")], ["0|com.whatsapp|99"])
        # Bildirimleri göstermesi kapalıysa aramalar da gelmez.
        self.hub.config.set("show_notifications", False)
        n = len(self.of("call"))
        await p.send(call)
        await asyncio.sleep(0.2)
        self.assertEqual(len(self.of("call")), n)
        await p.close()

    async def test_phone_crash_report_is_saved_once(self):
        p = await self.paired_phone()
        await p.send({"type": "crash_report", "text": "java.lang.IllegalStateException: deneme\n\tat X.y(X.kt:1)"})
        await p.send({"type": "crash_report", "text": "ikinci rapor yok sayılır"})
        await asyncio.sleep(0.2)
        crashes = self.of("phone_crash")
        self.assertEqual(len(crashes), 1)
        self.assertIn("IllegalStateException", Path(crashes[0]["path"]).read_text())
        await p.close()

    async def _stalled_phone(self, size=48 * 1024 * 1024):
        """Bilgisayardan büyük dosya gelirken okumayı bırakan telefon (TCP tamponları dolar)."""
        p = await self.paired_phone()
        f = Path(self.tmp.name) / "buyuk.bin"
        with f.open("wb") as fh:
            fh.truncate(size)
        sending = asyncio.create_task(self.hub.send_file(p.device_id, str(f)))
        offer = await p.recv_type("file_offer")
        await p.send({"type": "file_accept", "transfer_id": offer["transfer_id"]})
        await asyncio.sleep(1.0)  # tamponlar dolsun; telefon bundan sonra hiç okumuyor
        return p, sending

    async def test_reader_never_blocks_on_writes(self):
        """Bilgisayar yazarken takılı kalsa da gelen iletiler işlenmeli (ping/pong kilitlenmesi)."""
        p, sending = await self._stalled_phone()
        await p.send({"type": "ping"})  # eskiden okuyucu burada pong'u yazmak için takılıyordu
        await p.send({"type": "notification", "key": "k1", "package": "x", "app": "X", "title": "Hâlâ", "text": "okunuyor"})
        for _ in range(30):
            if self.of("notification"):
                break
            await asyncio.sleep(0.1)
        self.assertEqual(self.of("notification")[0]["title"], "Hâlâ")
        sending.cancel()
        await p.close()

    async def test_peer_that_stops_reading_is_dropped(self):
        import talkto.hub as hubmod
        old = hubmod.WRITE_TIMEOUT
        hubmod.WRITE_TIMEOUT = 1
        try:
            p, sending = await self._stalled_phone()
            result = await asyncio.wait_for(sending, 10)
            self.assertEqual(result["state"], "failed")
            for _ in range(50):
                if p.device_id not in self.hub.sessions:
                    break
                await asyncio.sleep(0.1)
            self.assertNotIn(p.device_id, self.hub.sessions)
        finally:
            hubmod.WRITE_TIMEOUT = old

    async def test_failing_message_does_not_drop_session(self):
        class Broken:
            def control(self, *a):
                raise RuntimeError("oynatıcı bu komutu desteklemiyor")

            def state(self):
                return {"active": False}
        self.hub.media = Broken()
        p = await self.paired_phone()
        await p.send({"type": "media_control", "action": "next"})
        await p.send({"type": "battery", "level": 50, "charging": True})
        await asyncio.sleep(0.3)
        self.assertIn(p.device_id, self.hub.sessions)
        self.assertEqual(self.hub.sessions[p.device_id].battery["level"], 50)
        await p.close()

    async def test_cancel_only_hits_the_named_direction(self):
        """Telefonun gönderdiği 1 numaralı aktarımın iptali, bilgisayarın gönderdiği 1 numarayı bozmamalı."""
        p = await self.paired_phone()
        f = Path(self.tmp.name) / "giden.bin"
        f.write_bytes(b"x" * 1000)
        sending = asyncio.create_task(self.hub.send_file(p.device_id, str(f)))
        offer = await p.recv_type("file_offer")
        tid = offer["transfer_id"]
        # Telefon kendi giden aktarımını (aynı numara) iptal ediyor: bilgisayar için yön "in".
        await p.send({"type": "file_offer", "transfer_id": tid, "name": "telefondan.txt", "size": 10})
        await p.send({"type": "file_cancel", "transfer_id": tid, "direction": "in"})
        await asyncio.sleep(0.2)
        self.assertFalse(sending.done())  # bilgisayarın gönderimi hâlâ kabul bekliyor
        await p.send({"type": "file_accept", "transfer_id": tid})
        from talkto.protocol import read_frame  # gönderim iptal edilmeden tamamlanmalı
        got = b""
        while True:
            kind, msg = await asyncio.wait_for(read_frame(p.reader), 10)
            if kind == "binary":
                got += msg[1]
            elif msg["type"] == "file_done":
                await p.send({"type": "file_result", "transfer_id": tid, "ok": True})
                break
        self.assertEqual(got, b"x" * 1000)
        self.assertEqual((await asyncio.wait_for(sending, 5))["state"], "done")
        await p.close()

    async def test_phone_status_explains_missing_notifications(self):
        p = await self.paired_phone()
        await p.send({"type": "phone_status", "flavor": "tam", "sdk": 34, "notif_access": True,
                      "listener": False, "player": None, "notifications_sent": 0})
        await asyncio.sleep(0.1)
        info = self.hub.status()["sessions"][0]
        self.assertFalse(info["phone"]["listener"])
        self.assertEqual(len(info["problems"]), 1)
        self.assertIn("dinleyici", info["problems"][0])
        await p.send({"type": "phone_status", "flavor": "tam", "notif_access": True, "listener": True})
        await asyncio.sleep(0.1)
        self.assertEqual(self.hub.status()["sessions"][0]["problems"], [])
        await p.close()

    def test_phone_problems(self):
        from talkto.hub import phone_problems
        allow = {"notifications": True, "media": True}
        self.assertEqual(phone_problems({}, allow), [])  # eski telefon sürümü durum göndermez: uyarı yok
        self.assertIn("hafif", phone_problems({"flavor": "hafif"}, allow)[0])
        self.assertIn("erişimi kapalı", phone_problems({"flavor": "tam", "notif_access": False}, allow)[0])
        self.assertEqual(len(phone_problems({}, {"notifications": False, "media": False})), 2)
        self.assertIn("gösterme kapalı", phone_problems({}, allow, show_notifications=False)[0])

    async def test_disconnect_and_forget(self):
        p = await self.paired_phone()
        self.assertIn(p.device_id, self.hub.sessions)
        await self.hub.forget(p.device_id)
        # Telefon kapanmadan önce nedeni öğrenir: kendiliğinden yeniden bağlanmasın, belirteci silsin.
        self.assertEqual((await p.recv_type("bye"))["reason"], "forgotten")
        await asyncio.sleep(0.1)
        self.assertNotIn(p.device_id, self.hub.sessions)
        self.assertNotIn(p.device_id, self.cfg.trusted())
        await p.close()

        q = await self.paired_phone()
        await self.hub.disconnect(q.device_id)
        self.assertEqual((await q.recv_type("bye"))["reason"], "disconnected")
        await q.close()


class TransferEdgeTest(_Base):
    """Bekleyen teklifler, eşzamanlı sınır ve UTF-8 olmayan dosya adları."""

    async def test_phone_cancels_offer_while_pc_asks(self):
        p = await self.paired_phone()
        self.cfg.set("auto_accept", False)
        self.answer = None  # bilgisayardaki soru cevapsız kalsın
        await p.send({"type": "file_offer", "transfer_id": 7, "name": "a.txt", "size": 3})
        for _ in range(50):
            if any(a["kind"] == "file" for a in self.of("ask")):
                break
            await asyncio.sleep(0.02)
        rid = next(a["id"] for a in self.of("ask") if a["kind"] == "file")
        await p.send({"type": "file_cancel", "transfer_id": 7, "direction": "in"})
        await asyncio.sleep(0.2)
        self.assertIn(rid, [d["id"] for d in self.of("ask_closed")])  # soru penceresi kapandı
        self.assertEqual(self.of("transfer")[-1]["state"], "cancelled")
        self.assertFalse(list((Path(self.tmp.name) / "gelen").glob(".*talkto-part")))
        await p.close()

    async def test_concurrent_incoming_limit(self):
        p = await self.paired_phone()
        for tid in range(1, 6):
            await p.send({"type": "file_offer", "transfer_id": tid, "name": f"{tid}.bin", "size": 10})
        replies = [await p.recv_type("file_accept", "file_reject") for _ in range(5)]
        self.assertEqual([r["type"] for r in replies].count("file_accept"), 4)
        self.assertIn("meşgul", next(r for r in replies if r["type"] == "file_reject")["reason"])
        await p.close()

    async def test_send_file_with_non_utf8_name(self):
        p = await self.paired_phone()
        path = Path(os.fsdecode(Path(self.tmp.name).as_posix().encode() + b"/eski-\xe7al\xfd\xfe.txt"))
        path.write_bytes(b"merhaba")
        task = asyncio.create_task(self.hub.send_file(p.device_id, str(path)))
        offer = await p.recv_type("file_offer")
        self.assertIn("\ufffd", offer["name"])
        await p.send({"type": "file_reject", "transfer_id": offer["transfer_id"], "reason": "deneme"})
        self.assertEqual((await asyncio.wait_for(task, 5))["state"], "rejected")
        await p.close()


class FeatureTest(_Base):
    """Profiller, komutlar, sistem bilgisi, komut satırı ve Bluetooth yolu."""

    async def test_profile_is_sent_and_recognized_on_connect(self):
        p = await self.paired_phone()
        prof = await p.recv_type("profile")
        self.assertEqual(prof["name"], "Benim telefonum")
        self.assertTrue(prof["permissions"]["commands"])
        cmds = await p.recv_type("commands")
        self.assertIn("kilitle", [c["id"] for c in cmds["items"]])
        # "Telefonda titreşim" (varsayılan kapalı) profil iletisiyle gider; değişince yeniden gönderilir.
        self.assertFalse(prof["vibrate"])
        await self.hub.set_option("phone_vibrate", True)
        self.assertTrue((await p.recv_type("profile"))["vibrate"])
        await p.close()

    async def test_choose_profile_in_approval_and_guest_limits(self):
        self.answer = "misafir"  # onay penceresinde "Misafir" profili seçildi
        p = FakePhone()
        self.assertEqual(await p.connect(port=self.cfg["port"]), "welcome")
        self.assertEqual(self.cfg.trusted()[p.device_id]["profile"], "misafir")
        prof = await p.recv_type("profile")
        self.assertEqual(prof["name"], "Misafir")
        self.assertEqual((await p.recv_type("commands"))["items"], [])
        await p.send({"type": "clipboard", "text": "olmamalı"})
        await p.send({"type": "open_url", "url": "https://example.com"})
        await p.send({"type": "run_command", "id": "kilitle"})
        res = await p.recv_type("command_result")
        self.assertFalse(res["ok"])
        self.assertEqual(self.of("clipboard"), [])
        self.assertEqual(self.of("open_url"), [])
        # Misafir dosya gönderebilir.
        self.assertTrue((await p.send_file(9, "not.txt", b"merhaba"))["ok"])
        await p.close()

    async def test_profile_change_applies_immediately(self):
        p = await self.paired_phone()
        await p.recv_type("commands")
        await self.hub.save_profile("benim", {"clipboard": False, "name": "Kısıtlı"})
        prof = await p.recv_type("profile")
        self.assertEqual(prof["name"], "Kısıtlı")
        self.assertFalse(prof["permissions"]["clipboard"])
        await p.send({"type": "clipboard", "text": "olmamalı"})
        await asyncio.sleep(0.1)
        self.assertEqual(self.of("clipboard"), [])
        await self.hub.assign_profile(p.device_id, "misafir")
        self.assertEqual((await p.recv_type("profile"))["name"], "Misafir")
        await p.close()

    async def test_custom_command_runs_and_returns_output(self):
        await self.hub.save_command(None, "Selam", "echo merhaba-$((2+3))")
        p = await self.paired_phone()
        items = (await p.recv_type("commands"))["items"]
        cid = next(c["id"] for c in items if c["name"] == "Selam")
        await p.send({"type": "run_command", "id": cid})
        res = await p.recv_type("command_result")
        self.assertTrue(res["ok"])
        self.assertEqual(res["output"].strip(), "merhaba-5")
        self.assertEqual(self.of("command_run")[0]["name"], "Selam")
        await p.send({"type": "run_command", "id": "yok-boyle-bir-sey"})
        self.assertFalse((await p.recv_type("command_result"))["ok"])
        await p.close()

    async def test_power_commands_need_permission(self):
        await self.hub.save_profile("benim", {"power": False})
        p = await self.paired_phone()
        ids = [c["id"] for c in (await p.recv_type("commands"))["items"]]
        self.assertIn("kilitle", ids)
        self.assertNotIn("kapat", ids)
        await p.send({"type": "run_command", "id": "kapat"})  # gerçek systemctl çalışmamalı
        res = await p.recv_type("command_result")
        self.assertFalse(res["ok"])
        self.assertIn("güç", res["output"])
        await p.close()

    async def test_sysinfo(self):
        p = await self.paired_phone()
        await p.send({"type": "sysinfo_request"})
        info = await p.recv_type("sysinfo")
        for k in ("host", "os", "mem_total", "disk_total", "uptime", "cores"):
            self.assertIn(k, info)
        self.assertGreater(info["mem_total"], 0)
        await p.close()

    async def test_command_line_tool(self):
        from talkto import cli, ipc
        sock = Path(self.tmp.name) / "komut.sock"
        server = ipc.IpcServer(self.hub, sock)
        await server.start()
        self.assertEqual(oct(sock.stat().st_mode & 0o777), "0o600")
        orig = ipc.socket_path
        cli.socket_path = lambda: sock
        try:
            run = lambda *a: asyncio.to_thread(cli.main, list(a))  # noqa: E731
            p = await self.paired_phone()
            self.assertEqual(await run("durum"), 0)
            self.assertEqual(await run("bildirim", "Derleme bitti", "0 hata"), 0)
            n = await p.recv_type("notify")
            self.assertEqual((n["title"], n["text"]), ("Derleme bitti", "0 hata"))
            self.assertEqual(await run("pano", "terminalden"), 0)
            self.assertEqual((await p.recv_type("clipboard"))["text"], "terminalden")
            f = Path(self.tmp.name) / "rapor.txt"
            f.write_bytes(b"rapor" * 5000)
            send = asyncio.create_task(run("gonder", str(f)))
            name, data = await p.receive_file()
            self.assertEqual(await send, 0)
            self.assertEqual((name, data), ("rapor.txt", f.read_bytes()))
            self.assertEqual(await run("bildirim", "x", "-c", "olmayan-telefon"), 1)
            await p.close()
        finally:
            cli.socket_path = orig
            await server.stop()

    async def test_bluetooth_style_socket_needs_approval(self):
        """BlueZ'in verdiği bağlı soket yerine kabul edilmiş bir TCP soketi: aynı TLS + onay akışı."""
        lst = socket.socket()
        lst.bind(("127.0.0.1", 0))
        lst.listen(1)
        lst.setblocking(False)
        port = lst.getsockname()[1]
        loop = asyncio.get_running_loop()

        async def accept():
            conn, _ = await loop.sock_accept(lst)
            await self.hub.accept_socket(conn, "bluetooth", "AA:BB:CC:DD:EE:FF")
        task = asyncio.create_task(accept())
        self.answer = True
        p = FakePhone("telefon-bt-0001")
        self.assertEqual(await p.connect(port=port), "welcome")
        self.assertEqual(self.of("ask")[0]["transport"], "bluetooth")
        await asyncio.sleep(0.05)
        self.assertEqual(self.hub.sessions[p.device_id].kind, "bluetooth")
        await p.close()
        await asyncio.wait_for(task, 5)
        lst.close()


class InstallTest(unittest.IsolatedAsyncioTestCase):
    """Terminalsiz kurulum: telefona USB'den APK, bilgisayara eksik GTK paketleri."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "cagrilar.txt"
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{self.bin}:{self.old_path}"

    def tearDown(self):
        os.environ["PATH"] = self.old_path
        os.environ.pop("TALKTO_APK", None)
        self.tmp.cleanup()

    def fake(self, name, body, version="3.1"):
        f = self.bin / name
        # scrcpy sürümü sorulunca (yeni sürüm denetimi) çağrı kaydına yazılmaz.
        ver = f'[ "$1" = "--version" ] && {{ echo "scrcpy {version} <x>"; exit 0; }}\n' if name == "scrcpy" else ""
        f.write_text(f"#!/bin/sh\n{ver}echo \"{name} $*\" >> {self.log}\n{body}\n")
        f.chmod(0o755)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    async def test_install_phone_app_over_usb(self):
        apk = Path(self.tmp.name) / "talk-to-linux.apk"
        apk.write_bytes(b"PK sahte apk")
        os.environ["TALKTO_APK"] = str(apk)
        installed = Path(self.tmp.name) / "kurulu"
        self.fake("adb", f"""case "$*" in
  devices) printf 'List of devices attached\\nABC123\\tdevice\\n' ;;
  *"getprop"*) echo "Pixel 8" ;;
  *"pm path"*) [ -f {installed} ] && echo "package:/data/app/base.apk" ;;
  *"install -r"*) touch {installed}; echo Success ;;
esac
exit 0""")
        from talkto.usb import AdbWatcher
        snaps = []
        w = AdbWatcher(47600, snaps.append)
        await w._poll()
        dev = w.snapshot()["devices"][0]
        self.assertEqual((dev["model"], dev["tunnel"], dev["app"]), ("Pixel 8", True, False))
        self.assertEqual(w.snapshot()["apk"], str(apk))
        ok, msg = await w.install_app("ABC123")
        self.assertTrue(ok, msg)
        self.assertTrue(w.devices["ABC123"]["app"])
        self.assertIn(f"adb -s ABC123 install -r {apk}", self.calls())
        # Kurulunca açılır ve bilgisayardan bağlanır (telefonda "USB kablosu"na dokunmak gerekmez).
        self.assertIn("adb -s ABC123 shell am start -n lab.crucible.talktolinux/.ui.UsbBaglan", self.calls())

    async def test_install_reports_signature_conflict(self):
        apk = Path(self.tmp.name) / "a.apk"
        apk.write_bytes(b"x")
        os.environ["TALKTO_APK"] = str(apk)
        self.fake("adb", """case "$*" in
  devices) printf 'List of devices attached\\nABC123\\tdevice\\n' ;;
  *"install -r"*) echo "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: imza farklı]"; exit 1 ;;
esac
exit 0""")
        from talkto.usb import AdbWatcher
        w = AdbWatcher(47600, lambda s: None)
        await w._poll()
        ok, msg = await w.install_app("ABC123")
        self.assertFalse(ok)
        self.assertIn("kaldırıp", msg)
        self.assertFalse(w.devices["ABC123"]["installing"])
        self.assertFalse(any("uninstall" in c for c in self.calls()))
        # Kullanıcı "Kaldır ve kur" derse önce kaldırılır (sahte adb ikinci kurulumda da reddeder).
        await w.install_app("ABC123", replace=True)
        self.assertIn("adb -s ABC123 uninstall lab.crucible.talktolinux", self.calls())

    def test_first_run_installs_missing_gui_packages(self):
        from talkto import bootstrap
        self.fake("zenity", "exit 0")       # "Kurulsun mu?" → Kur
        self.fake("pkexec", "exit 0")       # şifre penceresi → onaylandı
        self.fake("apt-get", "exit 0")
        for t in ("dnf", "pacman", "zypper"):
            (self.bin / t).unlink(missing_ok=True)
        state = {"n": 0}

        def fake_check():
            state["n"] += 1
            return (state["n"] > 1, "No module named 'gi'")
        orig, bootstrap.gui_available = bootstrap.gui_available, fake_check
        os.environ.setdefault("DISPLAY", ":0")
        try:
            self.assertTrue(bootstrap.ensure_gui())
        finally:
            bootstrap.gui_available = orig
        pk = [c for c in self.calls() if c.startswith("pkexec")]
        self.assertEqual(len(pk), 1)
        self.assertIn("install -y python3-gi gir1.2-gtk-4.0 gir1.2-adw-1", pk[0])

    def test_first_run_cancelled(self):
        from talkto import bootstrap
        self.fake("zenity", 'case "$*" in *--question*) exit 1 ;; esac; exit 0')
        self.fake("pkexec", "exit 0")
        self.fake("apt-get", "exit 0")
        orig, bootstrap.gui_available = bootstrap.gui_available, lambda: (False, "No module named 'gi'")
        os.environ.setdefault("DISPLAY", ":0")
        try:
            self.assertFalse(bootstrap.ensure_gui())
        finally:
            bootstrap.gui_available = orig
        self.assertFalse([c for c in self.calls() if c.startswith("pkexec")])


class UnitTest(unittest.TestCase):
    def test_safe_name(self):
        for bad in ["../../.bashrc", "/etc/passwd", "a/../b", "..", "", "\x00x", "..\\..\\win"]:
            n = safe_name(bad)
            self.assertNotIn("/", n)
            self.assertFalse(n.startswith("."))
            self.assertTrue(n)
        self.assertEqual(safe_name("tatil fotoğrafı.jpg"), "tatil fotoğrafı.jpg")

    def test_shared_vectors(self):
        """Android (net/Auth.kt) aynı vektörleri kendi testinde kontrol eder."""
        vec = json.loads((ROOT / "protokol-test-vektorleri.json").read_text(encoding="utf-8"))
        for v in vec["password_proof"]:
            self.assertEqual(auth.password_proof(v["password"], v["nonce"], v["fp"]), v["proof"])
        for v in vec["pairing_code"]:
            self.assertEqual(auth.pairing_code(v["nonce"], v["fp"], v["device_id"]), v["code"])
        for v in vec["password_proof2"]:
            self.assertEqual(auth.password_proof2(v["password"], v["nonce"], v["fp"]), v["proof"])
        for v in vec["pairing_code2"]:
            self.assertEqual(auth.commit_of(v["secret"]), v["commit"])
            self.assertEqual(auth.pairing_code2(v["nonce"], v["secret"], v["fp"], v["device_id"]), v["code"])
        for v in vec["qr_proof"]:
            self.assertEqual(auth.qr_proof(v["key"], v["nonce"], v["fp"], v["device_id"]), v["proof"])
        for v in vec["frames"]:
            from talkto.protocol import encode_binary, encode_json
            if "json" in v:
                self.assertEqual(encode_json(v["json"]).hex(), v["hex"])
            else:
                self.assertEqual(encode_binary(v["tid"], bytes.fromhex(v["data"])).hex(), v["hex"])

    def test_token_hash(self):
        self.assertEqual(auth.token_hash("abc"), hashlib.sha256(b"abc").hexdigest())




class _AdbBase(_Base):
    """Sahte adb ve scrcpy ile çalışan testlerin ortak kurulumu."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "cagrilar.txt"
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{self.bin}:{self.old_path}"
        self.hub.usb.available = staticmethod(lambda: True)
        os.environ["TALKTO_DATA_DIR"] = str(Path(self.tmp.name) / "veri")  # indirilmiş scrcpy yok
        self.fake("scrcpy", "exit 0")

    async def asyncTearDown(self):
        await super().asyncTearDown()  # hub kapanırken sahte adb'yi hâlâ çağırır
        os.environ["PATH"] = self.old_path

    def fake(self, name, body, version="3.1"):
        f = self.bin / name
        # scrcpy sürümü sorulunca (yeni sürüm denetimi) çağrı kaydına yazılmaz.
        ver = f'[ "$1" = "--version" ] && {{ echo "scrcpy {version} <x>"; exit 0; }}\n' if name == "scrcpy" else ""
        f.write_text(f"#!/bin/sh\n{ver}echo \"{name} $*\" >> {self.log}\n{body}\n")
        f.chmod(0o755)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    async def wait_call(self, prefix):
        for _ in range(50):
            if any(c.startswith(prefix) for c in self.calls()):
                return
            await asyncio.sleep(0.05)
        self.fail(f"{prefix} çağrılmadı: {self.calls()}")


class UsbDetailsTest(_AdbBase):
    async def test_xiaomi_switches_and_app_version(self):
        self.fake("adb", """case "$*" in
  devices) printf 'List of devices attached\\nR1\\tdevice\\n' ;;
  *"ro.product.model"*) echo "Redmi Note 12" ;;
  *"ro.product.manufacturer"*) echo "Xiaomi" ;;
  *"adbinput"*) echo "0" ;;
  *"adbinstall"*) echo "1" ;;
  *"pm path"*) echo "package:/data/app/x/base.apk" ;;
  *"dumpsys package"*) printf '    versionCode=10 minSdk=26\\n    versionName=0.6.0\\n' ;;
esac
exit 0""")
        await self.hub.usb._poll()
        d = self.hub.usb.devices["R1"]
        self.assertEqual((d["maker"], d["xiaomi_permissions"], d["xiaomi_install"], d["app_version"]),
                         ("Xiaomi", False, True, "0.6.0"))
        self.fake("adb", """case "$*" in
  devices) printf 'List of devices attached\\nR1\\tdevice\\n' ;;
  *"ro.product.manufacturer"*) echo "Xiaomi" ;;
  *"adbinput"*) echo "1" ;;
  *"adbinstall"*) echo "1" ;;
  *"pm path"*) echo "package:/data/app/x/base.apk" ;;
  *"dumpsys package"*) echo "    versionName=0.7.1" ;;
esac
exit 0""")
        await self.hub.refresh_usb()  # kurulumdaki "Kontrol et"
        self.assertTrue(d["xiaomi_permissions"])
        self.assertEqual(d["app_version"], "0.7.1")

    async def test_outdated_phone_is_reported(self):
        p = await self.paired_phone()
        await p.send({"type": "phone_status", "flavor": "tam", "notif_access": True, "listener": True,
                      "version": "0.6.0"})
        await asyncio.sleep(0.1)
        problems = self.hub.status()["sessions"][0]["problems"]
        self.assertTrue(any("eski (0.6.0" in t for t in problems), problems)
        await p.close()


class MirrorTest(_AdbBase):
    """Telefonun ekranını bilgisayarda açma (scrcpy)."""

    def test_old_system_scrcpy_is_not_used(self):
        self.fake("scrcpy", "exit 0", version="1.21")
        self.assertFalse(mirror.available())
        self.assertEqual(mirror.outdated_system(), (1, 21))
        self.fake("scrcpy", "exit 0", version="2.4")
        self.assertTrue(mirror.available())
        self.assertIsNone(mirror.outdated_system())

    def test_quality_presets(self):
        q = mirror.quality_args
        self.assertEqual(q("ABC"), ["--video-bit-rate=16M", "--max-size=1920", "--max-fps=60", "--video-buffer=60",
                                    "--print-fps"])
        self.assertIn("--video-buffer=120", q("1.2.3.4:5555"))  # Wi-Fi daha çok dalgalanır
        self.assertNotIn("--video-buffer", " ".join(q("ABC", "hizli")))
        self.assertIn("--max-size=1280", q("ABC", "hafif"))
        self.assertIn("--no-audio", q("ABC", audio=False))
        self.assertIn("--display-buffer=60", q("ABC", version=(2, 4)))  # eski adı

    def _release(self, sha=None):
        """Resmi sürümün düzeninde küçük bir arşiv; indirme adresi ve özeti ona çevrilir."""
        import hashlib
        import tarfile
        src = Path(self.tmp.name) / "kaynak" / f"scrcpy-linux-x86_64-v{mirror.SCRCPY_VERSION}"
        src.mkdir(parents=True)
        (src / "scrcpy").write_text("#!/bin/sh\necho scrcpy 5.0.1\n")
        (src / "scrcpy").chmod(0o755)
        (src / "scrcpy-server").write_bytes(b"x")
        arc = Path(self.tmp.name) / "surum.tar.gz"
        with tarfile.open(arc, "w:gz") as t:
            t.add(src, arcname=src.name)
        data = arc.read_bytes()
        patch = mock.patch.multiple(mirror, SCRCPY_URL=arc.as_uri(), SCRCPY_SIZE=len(data),
                                    SCRCPY_SHA256=sha or hashlib.sha256(data).hexdigest())
        patch.start()
        self.addCleanup(patch.stop)

    def test_download_verifies_and_installs(self):
        self._release()
        seen = []
        path = mirror.download(lambda d, t, st: seen.append(st))
        self.assertTrue(os.access(path, os.X_OK))
        self.assertEqual(mirror.binary(), str(path))
        self.assertIn("doğrulanıyor", seen)

    def test_download_rejects_wrong_checksum(self):
        self._release(sha="0" * 64)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            mirror.download()
        self.assertFalse(mirror.managed_path().exists())

    def test_download_can_be_cancelled(self):
        import threading
        self._release()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(InterruptedError):
            mirror.download(cancel=stop)
        self.assertFalse(mirror.managed_path().exists())

    async def test_usb_phone_screen_opens(self):
        self.fake("adb", """case "$*" in
  devices) printf 'List of devices attached\\nABC123\\tdevice\\n' ;;
  *"getprop"*) echo "Pixel 8" ;;
esac
exit 0""")
        await self.hub.usb._poll()
        p = await self.paired_phone()
        ok, msg = await self.hub.mirror_session(p.device_id)
        self.assertTrue(ok, msg)
        await self.wait_call("scrcpy")
        self.assertIn("scrcpy -s ABC123 --window-title Test Telefonu · Talk To --stay-awake "
                      "--video-bit-rate=16M --max-size=1920 --max-fps=60 --video-buffer=60 --print-fps", self.calls())
        ok, msg = await self.hub.mirror_session(p.device_id)  # açıkken ikinci pencere açılmaz
        self.assertTrue(ok)
        from talkto import ipc  # terminalden: talk-to-android ekran
        r = await ipc.IpcServer(self.hub, Path(self.tmp.name) / "k.sock").handle({"cmd": "mirror"})
        self.assertEqual((r["ok"], r["device"]), (True, "Test Telefonu"))
        await p.close()

    async def test_scrcpy_crash_is_reported(self):
        self.fake("adb", """case "$*" in
  devices) printf 'List of devices attached\\nABC123\\tdevice\\n' ;;
esac
exit 0""")
        self.fake("scrcpy", "echo 'ERROR: Device disconnected' >&2; exit 1")
        await self.hub.usb._poll()
        ok, msg = await self.hub.mirror_device("ABC123")
        self.assertFalse(ok)
        self.assertIn("Device disconnected", msg)

    async def test_without_scrcpy_or_adb_device(self):
        self.fake("adb", "printf 'List of devices attached\\n'; exit 0")
        await self.hub.usb._poll()
        p = await self.paired_phone()
        ok, msg = await self.hub.mirror_session(p.device_id)
        self.assertFalse(ok)
        self.assertIn("adb'de görünmüyor", msg)
        (self.bin / "scrcpy").unlink()
        os.environ["PATH"] = str(self.bin)  # gerçek scrcpy kuruluysa da bulunmasın
        ok, msg = await self.hub.mirror_session(p.device_id)
        os.environ["PATH"] = f"{self.bin}:{self.old_path}"
        self.assertEqual((ok, msg), (False, "scrcpy kurulu değil"))
        await p.close()

    async def test_adb_removed_while_running(self):
        """adb uygulama açıkken kaldırılırsa kapanış ve yoklama çökmemeli."""
        from talkto.usb import _adb
        empty = Path(self.tmp.name) / "bos"
        empty.mkdir()
        os.environ["PATH"] = str(empty)
        try:
            rc, msg = await _adb("devices")
        finally:
            os.environ["PATH"] = f"{self.bin}:{self.old_path}"
        self.assertEqual(rc, 127)
        self.assertIn("adb çalıştırılamadı", msg)

    async def test_wireless(self):
        from talkto import mirror
        self.fake("adb", """case "$*" in
  "connect 192.168.1.50:5555") echo "connected to 192.168.1.50:5555" ;;
  *"get-state"*) echo device ;;
  "connect 192.168.1.60:5555") echo "failed to connect to 192.168.1.60:5555"; exit 1 ;;
esac
exit 0""")
        ok, _ = await mirror.enable_wireless("ABC123")
        self.assertTrue(ok)
        self.assertIn("adb -s ABC123 tcpip 5555", self.calls())
        self.assertEqual((await mirror.connect_wireless("192.168.1.50"))[0], "192.168.1.50:5555")
        serial, msg = await mirror.connect_wireless("192.168.1.60")
        self.assertIsNone(serial)
        self.assertIn("USB ile takıp", msg)


class PhoneSetupTest(_AdbBase):
    """Telefondaki izinlerin bilgisayardan (adb) verilmesi: sahte adb, gerçek komut dizisi."""

    ADB = """STATE=%(state)s
case "$*" in
  devices) printf 'List of devices attached\\nABC123\\tdevice\\n' ;;
  *"getprop ro.product.model"*) echo "Pixel 8" ;;
  *"getprop ro.build.version.sdk"*) echo 34 ;;
  *"pm path"*) echo "package:/data/app/base.apk" ;;
  *"dumpsys package"*) echo "      android.permission.SYSTEM_ALERT_WINDOW"; echo "  lab.crucible.talktolinux/.service.NotificationListener" ;;
  *"pm grant"*) %(grant)s ;;
  *"allow_listener"*) echo lab.crucible.talktolinux/lab.crucible.talktolinux.service.NotificationListener > $STATE ;;
  *"settings get secure enabled_notification_listeners"*) cat $STATE 2>/dev/null || echo null ;;
  *"deviceidle whitelist +"*) echo "Added: lab.crucible.talktolinux" ; touch $STATE.pil ;;
  *"deviceidle whitelist"*) [ -f $STATE.pil ] && echo "user,lab.crucible.talktolinux,10123" ;;
esac
exit 0"""

    def phone(self, grant="exit 0", dump="", first=""):
        """dump: `dumpsys package` çıktısına eklenecek satırlar; first: diğerlerinden önce denenecek case kolu."""
        body = self.ADB % {"state": Path(self.tmp.name) / "durum", "grant": grant}
        if dump:
            body = body.replace('NotificationListener" ;;', f'NotificationListener"; {dump} ;;', 1)
        if first:
            body = body.replace('case "$*" in', 'case "$*" in\n' + first, 1)
        self.fake("adb", body)

    async def test_all_permissions_given(self):
        self.phone()
        await self.hub.usb._poll()
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertTrue(ok, text)
        calls = "\n".join(self.calls())
        self.assertIn("appops set lab.crucible.talktolinux ACCESS_RESTRICTED_SETTINGS allow", calls)
        self.assertIn("pm grant lab.crucible.talktolinux android.permission.POST_NOTIFICATIONS", calls)
        self.assertIn("cmd notification allow_listener lab.crucible.talktolinux/lab.crucible.talktolinux"
                      ".service.NotificationListener", calls)
        self.assertIn("dumpsys deviceidle whitelist +lab.crucible.talktolinux", calls)
        # HyperOS'ta "Cevapla" bilgisayardan basılınca çalışmıyordu: aramayı cevaplama izni de verilir.
        self.assertIn("pm grant lab.crucible.talktolinux android.permission.ANSWER_PHONE_CALLS", calls)

    async def test_answer_needs_are_granted_silently(self):
        """Aramayı cevaplamak için: üstte gösterme izni (her telefonda) ve Xiaomi'nin "arka planda açılır pencereler"i
        (yalnızca Xiaomi'de) telefonda yeni bir ayar satırı olmadan buradan verilir."""
        ops = Path(self.tmp.name) / "ops"
        ops.mkdir()
        appops = (f'  *"appops get"*) op=$(echo "$*" | awk \'{{print $NF}}\'); [ -f {ops}/$op ] && echo "$op: allow" '
                  f'|| echo "$op: default" ;;\n'
                  f'  *"appops set"*) op=$(echo "$*" | awk \'{{print $(NF-1)}}\'); touch {ops}/$op ;;')
        self.phone(first=appops)
        await self.hub.usb._poll()
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertTrue(ok, text)
        calls = "\n".join(self.calls())
        self.assertIn("appops set lab.crucible.talktolinux SYSTEM_ALERT_WINDOW allow", calls)
        self.assertNotIn(" 10021 ", calls)  # Pixel: Xiaomi'ye özgü izinlere dokunulmaz
        self.assertNotIn(" 10008 ", calls)
        # Xiaomi: kendi izni de verilir; ikinci seferde "zaten açık" (yeniden verilmez).
        self.phone(first=appops + '\n  *"getprop ro.product.manufacturer"*) echo Xiaomi ;;')
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertTrue(ok, text)
        self.assertIn("appops set lab.crucible.talktolinux 10021 allow", "\n".join(self.calls()))
        # Xiaomi'de otomatik başlatma da (telefon yeniden başlayınca kendiliğinden bağlansın).
        self.assertIn("appops set lab.crucible.talktolinux 10008 allow", "\n".join(self.calls()))
        self.log.unlink()
        items = await __import__("talkto.phone_setup", fromlist=["x"]).setup_phone("ABC123")
        self.assertEqual({i["key"]: i["message"] for i in items if i["key"] in ("overlay", "xiaomi_popup",
                                                                                "xiaomi_autostart")},
                         {"overlay": "zaten açık", "xiaomi_popup": "zaten açık", "xiaomi_autostart": "zaten açık"})
        self.assertNotIn("appops set lab.crucible.talktolinux SYSTEM_ALERT_WINDOW", "\n".join(self.calls()))

    async def test_play_version_is_not_given_overlay(self):
        """Play sürümü "üstte gösterme" iznini istemiyor: verilmeye çalışılıp "olmadı" denmez; gerisi aynı."""
        self.phone(first='  *"dumpsys package"*) echo "    versionName=0.18.0-play"; '
                         'echo "  lab.crucible.talktolinux/.service.NotificationListener" ;;')
        await self.hub.usb._poll()
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertTrue(ok, text)
        calls = "\n".join(self.calls())
        self.assertNotIn("SYSTEM_ALERT_WINDOW", calls)
        self.assertIn("pm grant lab.crucible.talktolinux android.permission.ANSWER_PHONE_CALLS", calls)
        self.assertIn("allow_listener", calls)

    async def test_answer_permission_failure_is_told(self):
        """Bir izin verilemezse sessiz kalınmaz: hangisi ve sonucu (aramayı telefondan cevaplamak) söylenir."""
        self.phone(first='  *"getprop ro.product.manufacturer"*) echo Xiaomi ;;\n'
                         '  *"appops set"*"10021"*) echo "java.lang.SecurityException: uid 2000 not allowed"; exit 255 ;;\n'
                         '  *"appops get"*"10021"*) echo "MIUIOP(10021): default" ;;')
        await self.hub.usb._poll()
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertFalse(ok)
        self.assertIn("Arka planda açılır pencereler (Xiaomi)", text)
        self.assertIn("telefondan cevaplarsın", text)
        self.assertNotIn("üstte gösterme", text)  # o verildi

    async def test_install_then_permissions(self):
        """Telefon uygulaması USB'den kurulunca / güncellenince izinler kendiliğinden verilir (yeni sürümün yeni
        izinleri için kullanıcının "Bilgisayar ayarlasın"a yeniden basması gerekmez)."""
        apk = Path(self.tmp.name) / "t.apk"
        apk.write_bytes(b"PK")
        os.environ["TALKTO_APK"] = str(apk)
        self.phone(first='  *"install -r"*) echo Success ;;')
        await self.hub.usb._poll()
        ok, text = await self.hub.install_phone_app("ABC123")
        self.assertTrue(ok, text)
        calls = "\n".join(self.calls())
        self.assertLess(calls.index("install -r"), calls.index("pm grant lab.crucible.talktolinux "
                                                                "android.permission.ANSWER_PHONE_CALLS"))
        self.assertNotIn("olmadı", text)
        # İzin verilemezse kurulum yine başarılı, ama ne olmadığı söylenir.
        self.phone(first='  *"install -r"*) echo Success ;;',
                   grant='echo "java.lang.SecurityException: GRANT_RUNTIME_PERMISSIONS"; exit 255')
        ok, text = await self.hub.install_phone_app("ABC123")
        self.assertTrue(ok)
        self.assertIn("Bazı adımlar olmadı", text)

    async def test_listener_setting_written_late(self):
        """Android ayarı allow_listener'dan biraz sonra yazıyor: hemen "olmadı" denmemeli."""
        st = Path(self.tmp.name) / "durum"
        self.phone()
        late = self.ADB % {"state": st, "grant": "exit 0"}
        late = late.replace('cat $STATE 2>/dev/null || echo null', 'n=$(cat $STATE.n 2>/dev/null || echo 0); '
                            'echo $((n+1)) > $STATE.n; if [ "$n" -ge 2 ]; then cat $STATE; else echo null; fi')
        self.fake("adb", late)
        await self.hub.usb._poll()
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertTrue(ok, text)

    async def test_locked_phone_explains(self):
        self.phone(grant='echo "java.lang.SecurityException: grantRuntimePermission: Neither user 2000 nor '
                         'current process has android.permission.GRANT_RUNTIME_PERMISSIONS."; exit 255')
        await self.hub.usb._poll()
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertFalse(ok)
        # Bildirim izni telefonda verilebilir (uygulama açılınca sorar); Bluetooth izni eksik sayılmaz.
        self.assertIn("“İzin ver” de", text)
        self.assertNotIn("Bluetooth", text)

    async def test_already_granted_on_phone_is_not_redone(self):
        """Telefonda elle verilen izinler yeniden istenmez; Xiaomi'nin engeli de "olmadı" dedirtmez."""
        st = Path(self.tmp.name) / "durum"
        st.write_text("lab.crucible.talktolinux/lab.crucible.talktolinux.service.NotificationListener")
        Path(f"{st}.pil").touch()
        self.phone(grant='echo "java.lang.SecurityException: GRANT_RUNTIME_PERMISSIONS"; exit 255',
                   dump='echo "    android.permission.POST_NOTIFICATIONS: granted=true, flags=[ USER_SET ]"; '
                        'echo "    android.permission.BLUETOOTH_CONNECT: granted=true"; '
                        'echo "    android.permission.ANSWER_PHONE_CALLS: granted=true"')
        await self.hub.usb._poll()
        d = self.hub.usb.devices["ABC123"]
        self.assertEqual(d["perms"], {"post": True, "listener": True, "battery": True})
        ok, text = await self.hub.phone_setup("ABC123")
        self.assertTrue(ok, text)
        calls = "\n".join(self.calls())
        self.assertNotIn("pm grant", calls)
        self.assertNotIn("allow_listener", calls)
        self.assertNotIn("whitelist +", calls)

    async def test_connect_from_computer(self):
        """"Bağlan": tünel kurulur, telefondaki uygulama adb'nin açabildiği kapıdan USB'ye bağlanacak şekilde açılır."""
        self.phone()
        await self.hub.usb._poll()
        ok, text = await self.hub.connect_phone("ABC123")
        self.assertTrue(ok, text)
        self.assertIn("adb -s ABC123 shell am start -n lab.crucible.talktolinux/.ui.UsbBaglan", self.calls())
        # Eski telefon uygulamasında kapı yok: ne yapılacağı söylenir.
        self.phone(first='  *"am start"*) echo "Error type 3"; echo "Error: Activity class '
                         '{lab.crucible.talktolinux/lab.crucible.talktolinux.ui.UsbBaglan} does not exist." ;;')
        ok, text = await self.hub.connect_phone("ABC123")
        self.assertFalse(ok)
        self.assertIn("önce güncelle", text)
        ok, text = await self.hub.connect_phone("YOK")
        self.assertFalse(ok)

    async def test_phone_asks_computer(self):
        self.phone()
        await self.hub.usb._poll()
        p = await self.paired_phone()
        await p.send({"type": "setup_request"})
        res = await p.recv_type("setup_result", timeout=15)
        self.assertTrue(all(i["ok"] is not False for i in res["items"]), res)
        self.assertIn("ayarlandı", res["summary"])
        self.assertTrue(self.of("phone_setup"))
        await p.close()


if __name__ == "__main__":
    unittest.main()
