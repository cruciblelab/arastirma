"""Yayıncı kartı ve site doğrulaması (gerçek HTTPS sunucusu ve gerçek imzalı paketle)."""

import json
import os
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from yardimci import build_deb, make_key

from guncelleyici import imza, paket, yayinci

FPR = "68E78B0A596A2E518DA0526BCFBF9E598C96C9F4"


class KartTest(unittest.TestCase):
    def test_parse(self):
        k = yayinci.parse(json.dumps({"yayinci": "Crucible\n ekibi", "web": "https://example.org",
                                      "iletisim": "biri@example.org", "dogrulama": "http://example.org/x",
                                      "kurum": 5, "bilinmeyen": "x"}).encode())
        self.assertEqual(k.yayinci, "Crucible ekibi")
        self.assertEqual((k.web, k.iletisim, k.dogrulama, k.kurum), ("https://example.org", "biri@example.org", "", ""))
        self.assertIsNone(yayinci.parse(b'{"web": "https://example.org"}'))  # adsız
        self.assertIsNone(yayinci.parse(b"[1]"))
        self.assertIsNone(yayinci.parse(b"\xff"))
        self.assertIsNone(yayinci.parse(b" " * (yayinci.EN_COK_KART + 1)))
        self.assertEqual(yayinci.parse(b'{"yayinci": "a", "iletisim": "javascript:x"}').iletisim, "")
        self.assertEqual(yayinci.parse(b'{"yayinci": "a", "web": "https://u:p@x.org"}').web, "")

    def test_same_site(self):
        gh = "https://github.com/cruciblelab/arastirma"
        self.assertTrue(yayinci.same_site(gh, "https://raw.githubusercontent.com/cruciblelab/arastirma/x/YAYINCI.txt"))
        self.assertTrue(yayinci.same_site(gh, "https://cruciblelab.github.io/YAYINCI.txt"))
        self.assertFalse(yayinci.same_site(gh, "https://raw.githubusercontent.com/baskasi/arastirma/YAYINCI.txt"))
        self.assertTrue(yayinci.same_site("https://www.example.org", "https://example.org/a"))
        self.assertTrue(yayinci.same_site("https://example.org", "https://dl.example.org/a"))
        self.assertFalse(yayinci.same_site("https://example.org", "https://example.org.evil.com/a"))
        self.assertFalse(yayinci.same_site("https://mozilla.org", "https://evil.com/a"))
        self.assertFalse(yayinci.same_site("", "https://evil.com/a"))

    def test_lists(self):
        self.assertTrue(yayinci.lists("Parmak izi: 68E7 8B0A 596A 2E51 8DA0  526B CFBF 9E59 8C96 C9F4\n", FPR))
        self.assertTrue(yayinci.lists(FPR.lower(), FPR))
        self.assertFalse(yayinci.lists("68E7 8B0A 596A 2E51", FPR))
        self.assertFalse(yayinci.lists("bir şey", ""))

    def test_changed(self):
        a = yayinci.Kart("A", web="https://a.org")
        self.assertEqual(yayinci.changed(a, yayinci.Kart("A", web="https://a.org", kurum="x")), [])
        self.assertEqual(yayinci.changed(a, yayinci.Kart("B", web="https://b.org")), ["ad", "web sitesi"])
        self.assertEqual(yayinci.changed(None, a), [])

    def test_card_read_from_signed_package(self):
        d = Path(tempfile.mkdtemp())
        secret, public, fpr = make_key(d, "kart")
        deb = build_deb(d, key=public, secret=secret, publisher={"yayinci": "Deneme Ekibi", "web": "https://x.org"})
        p = paket.read(str(deb))
        self.assertEqual(yayinci.parse(p.publisher).yayinci, "Deneme Ekibi")
        # Kart veri arşivinde: imza onu da kapsar (kartı değiştirmek imzayı bozar).
        sig = imza.check(str(deb), p.package, p.keyring, [])
        self.assertEqual((sig.state, sig.fingerprint), (imza.ILK, fpr))


class _Handler(BaseHTTPRequestHandler):
    pages: dict = {}

    def do_GET(self):  # noqa: N802
        code, headers, body = self.pages.get(self.path, (404, {}, b"yok"))
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class SiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp())
        cls.cert, key = d / "sertifika.pem", d / "anahtar.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj",
                        "/CN=localhost", "-addext", "subjectAltName=DNS:localhost", "-keyout", str(key),
                        "-out", str(cls.cert)], check=True, capture_output=True)
        _Handler.pages = {
            "/YAYINCI.txt": (200, {}, f"Yayıncı: Deneme\nParmak izi: {imza.grouped(FPR)}\n".encode()),
            "/eski.txt": (200, {}, b"Parmak izi: 0000 1111\n"),
            "/buyuk.txt": (200, {}, b"x" * (yayinci.EN_COK_SAYFA + 10)),
            "/yonlendir-http": (302, {"Location": "http://localhost/YAYINCI.txt"}, b""),
        }
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cls.cert, key)
        cls.server.socket = ctx.wrap_socket(cls.server.socket, server_side=True)
        cls.base = f"https://localhost:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        os.environ["no_proxy"] = os.environ["NO_PROXY"] = "localhost,127.0.0.1"
        cls.ctx = ssl.create_default_context(cafile=str(cls.cert))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def verify(self, path, web=None):
        return yayinci.verify(self.base + path, FPR, self.base if web is None else web, timeout=5, context=self.ctx)

    def test_verified(self):
        r = self.verify("/YAYINCI.txt")
        self.assertEqual((r.state, r.same_site), (yayinci.DOGRULANDI, True))
        r = self.verify("/YAYINCI.txt", web="https://example.org")
        self.assertEqual((r.state, r.same_site), (yayinci.DOGRULANDI, False))

    def test_not_listed(self):
        self.assertEqual(self.verify("/eski.txt").state, yayinci.LISTEDE_YOK)

    def test_unreachable(self):
        r = self.verify("/yok.txt")
        self.assertEqual(r.state, yayinci.ULASILAMADI)
        self.assertIn("404", r.detail)
        self.assertEqual(self.verify("/buyuk.txt").state, yayinci.ULASILAMADI)
        self.assertEqual(self.verify("/yonlendir-http").state, yayinci.ULASILAMADI)
        # Sertifikası tanınmayan site: doğrulanmış sayılmaz.
        r = yayinci.verify(self.base + "/YAYINCI.txt", FPR, self.base, timeout=5)
        self.assertEqual(r.state, yayinci.ULASILAMADI)
        self.assertEqual(yayinci.verify("http://localhost/x", FPR).state, yayinci.ULASILAMADI)


HAVE_UI = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@unittest.skipUnless(HAVE_UI, "ekran yok")
class WindowTest(SiteTest):
    """Gerçek pencere: imzalı paketin kartı gösterilir, site doğrulaması arka planda yapılıp satıra yazılır."""

    test_verified = test_not_listed = test_unreachable = None

    def test_card_and_site_in_window(self):
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import GLib

        from guncelleyici.ui import App, Window

        d = Path(tempfile.mkdtemp())
        secret, public, fpr = make_key(d, "pencere")
        _Handler.pages["/pencere.txt"] = (200, {}, f"Parmak izi: {imza.grouped(fpr)}\n".encode())
        deb = build_deb(d, package="kart-deneme", key=public, secret=secret, publisher={
            "yayinci": "Deneme Ekibi", "kurum": "Deneme Derneği", "web": self.base,
            "iletisim": self.base + "/sorunlar", "dogrulama": self.base + "/pencere.txt"})
        old = os.environ.get("SSL_CERT_FILE")
        os.environ["SSL_CERT_FILE"] = str(self.cert)  # doğrulama varsayılan sertifika deposunu kullanır
        try:
            app = App()
            app.register(None)
            win = Window(app)
            win.present()
            win.load(str(deb))
            loop, end = GLib.MainLoop(), GLib.get_monotonic_time() + 60_000_000

            def check():
                if win.site is not None or GLib.get_monotonic_time() > end:
                    loop.quit()
                    return False
                return True
            GLib.timeout_add(50, check)
            loop.run()
        finally:
            if old is None:
                os.environ.pop("SSL_CERT_FILE", None)
            else:
                os.environ["SSL_CERT_FILE"] = old
        self.assertEqual(win.card.yayinci, "Deneme Ekibi")
        self.assertIsNotNone(win.site, "doğrulama bitmedi")
        self.assertEqual(win.site.state, yayinci.DOGRULANDI)
        self.assertEqual(win.site_row.get_title(), "Site doğruladı")
        win.destroy()


if __name__ == "__main__":
    unittest.main()
