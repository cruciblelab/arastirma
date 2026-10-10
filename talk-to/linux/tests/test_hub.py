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
from pathlib import Path

from sahte_telefon import FakePhone

from talkto import auth
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
        await asyncio.sleep(0.1)
        self.assertNotIn(p.device_id, self.hub.sessions)
        self.assertNotIn(p.device_id, self.cfg.trusted())
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

    def fake(self, name, body):
        f = self.bin / name
        f.write_text(f"#!/bin/sh\necho \"{name} $*\" >> {self.log}\n{body}\n")
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
        self.assertIn("adb -s ABC123 shell am start -n lab.crucible.talktolinux/.ui.MainActivity", self.calls())

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
        for v in vec["frames"]:
            from talkto.protocol import encode_binary, encode_json
            if "json" in v:
                self.assertEqual(encode_json(v["json"]).hex(), v["hex"])
            else:
                self.assertEqual(encode_binary(v["tid"], bytes.fromhex(v["data"])).hex(), v["hex"])

    def test_token_hash(self):
        self.assertEqual(auth.token_hash("abc"), hashlib.sha256(b"abc").hexdigest())


if __name__ == "__main__":
    unittest.main()


class MirrorTest(_Base):
    """Telefonun ekranını bilgisayarda açma (scrcpy): sahte adb ve scrcpy ile."""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "cagrilar.txt"
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{self.bin}:{self.old_path}"
        self.hub.usb.available = staticmethod(lambda: True)
        self.fake("scrcpy", "exit 0")

    async def asyncTearDown(self):
        os.environ["PATH"] = self.old_path
        await super().asyncTearDown()

    def fake(self, name, body):
        f = self.bin / name
        f.write_text(f"#!/bin/sh\necho \"{name} $*\" >> {self.log}\n{body}\n")
        f.chmod(0o755)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    async def wait_call(self, prefix):
        for _ in range(50):
            if any(c.startswith(prefix) for c in self.calls()):
                return
            await asyncio.sleep(0.05)
        self.fail(f"{prefix} çağrılmadı: {self.calls()}")

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
        self.assertIn("scrcpy -s ABC123 --window-title Test Telefonu · Talk To Android --stay-awake", self.calls())
        ok, msg = await self.hub.mirror_session(p.device_id)  # açıkken ikinci pencere açılmaz
        self.assertTrue(ok)
        from talkto import ipc  # terminalden: talk-to-android ekran
        r = await ipc.IpcServer(self.hub, Path(self.tmp.name) / "k.sock").handle({"cmd": "mirror"})
        self.assertEqual((r["ok"], r["device"]), (True, "Test Telefonu"))
        await p.close()

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
