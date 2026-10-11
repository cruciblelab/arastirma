"""Açık uygulamayı bulup kapatma (calisan.py): gerçek oturum veriyolunda gerçek bir GApplication ile.

Ayrı bir veriyolu (dbus-run-session) içinde küçük bir uygulama başlatılır; Paket Güncelleyici onu
açık görmeli, "quit" eylemini bulmalı ve kapatabilmeli.
"""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

APP = r'''
import sys
from gi.repository import Gio, GLib
app = Gio.Application(application_id=sys.argv[1], flags=Gio.ApplicationFlags.FLAGS_NONE)
if sys.argv[2] == "evet":
    a = Gio.SimpleAction.new("quit", None)
    a.connect("activate", lambda *_: app.quit())
    app.add_action(a)
app.connect("activate", lambda *_: (app.hold(), print("hazir", flush=True)))
app.run([])
'''

CHECK = r'''
import subprocess, sys, time
sys.path.insert(0, sys.argv[1])
from guncelleyici import calisan
app = sys.argv[2]

def start(name, quit):
    p = subprocess.Popen([sys.executable, "-c", sys.argv[3], name, quit], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "hazir"
    return p

assert not calisan.running("lab.deneme.Calisan")
p = start("lab.deneme.Calisan", "evet")
assert calisan.running(calisan.bus_name("lab.deneme.Calisan.desktop"))
assert calisan.can_quit("lab.deneme.Calisan")
assert calisan.quit_app("lab.deneme.Calisan")
p.wait(10)
assert not calisan.running("lab.deneme.Calisan")
q = start("lab.deneme.Kapanmaz", "hayir")
assert calisan.running("lab.deneme.Kapanmaz") and not calisan.can_quit("lab.deneme.Kapanmaz")
q.terminate()
print("tamam")
'''

# Sonuç sayfası, gerçek pencerede: (1) açık uygulama kurulumdan sonra kendini yeniler → "yeniden başladı";
# (2) yenilemez (eski sürüm bunu bilmiyor) → beklenen süre dolunca "Yeniden başlat"; tıklanınca kapanıp yeniden açılır.
WINDOW = r'''
import os, subprocess, sys, time
sys.path.insert(0, sys.argv[1])
os.environ["XDG_DATA_HOME"] = data = sys.argv[3]  # GLib bunu ilk kullanımda önbelleğe alır: içe aktarmalardan önce
import gi
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")
from gi.repository import GLib
from guncelleyici import calisan, paket
from guncelleyici.ui import App, Window
APP, NAME = sys.argv[2], "lab.deneme.Yenilenen"
os.makedirs(data + "/applications", exist_ok=True)
open(data + "/uygulama.py", "w").write(APP)
with open(data + "/applications/" + NAME + ".desktop", "w") as f:
    f.write("[Desktop Entry]\nType=Application\nName=Yenilenen\nX-Guncellenince-Yeniden-Baslar=true\n"
            f"Exec={sys.executable} {data}/uygulama.py {NAME} evet\n")

def start():
    p = subprocess.Popen([sys.executable, "-c", APP, NAME, "evet"], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "hazir"
    return p

def wait(cond, secs):
    loop, end = GLib.MainLoop(), time.monotonic() + secs
    def check():
        if cond() or time.monotonic() > end:
            loop.quit(); return False
        return True
    if not cond():
        GLib.timeout_add(50, check); loop.run()
    return cond()

app = App(); app.register(None)
Window.RESTART_WAIT = 3

def finished(win):
    win.pkg = paket.Paket(path="", package="yenilenen", version="2.0", arch="all", summary="", name="Yenilenen",
                          desktop_ids=[NAME + ".desktop"])
    win._owners_before = {NAME + ".desktop": calisan.owner(NAME)}
    return win

# 1) Kendini yeniler: eski süreç kapanır, yenisi gelir.
p = start()
win = finished(Window(app)); win.present()
p.terminate(); p.wait(); p = start()
win._finished(True)
assert wait(lambda: "yeniden başladı" in win.result_page.get_description(), 10), win.result_page.get_description()
win.destroy()

# 2) Yenilemez: süre dolunca "Yeniden başlat"; tıklanınca kapanır ve masaüstü dosyasıyla yeniden açılır.
win = finished(Window(app)); win.present()
before = win._owners_before[NAME + ".desktop"]
win._finished(True)
assert wait(lambda: "kendiliğinden yeniden başlamadı" in win.result_page.get_description(), 10)
btn = win.result_buttons.get_first_child()
assert btn.get_label() == "Yeniden başlat", btn.get_label()
btn.emit("clicked")
assert wait(lambda: p.poll() is not None, 10), "uygulama kapanmadı"
assert wait(lambda: calisan.owner(NAME) not in (None, before), 15), "yeniden açılmadı"
calisan.quit_app(NAME)
print("tamam")
'''


@unittest.skipUnless(shutil.which("dbus-run-session"), "dbus-run-session yok")
class CalisanTest(unittest.TestCase):
    def test_find_and_quit_running_app(self):
        res = subprocess.run(["dbus-run-session", "--", sys.executable, "-c", CHECK, str(ROOT), "", APP],
                             capture_output=True, text=True, timeout=60)
        self.assertIn("tamam", res.stdout, res.stderr[-2000:])

    @unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "ekran yok")
    def test_result_page_restart(self):
        import tempfile
        res = subprocess.run(["dbus-run-session", "--", sys.executable, "-c", WINDOW, str(ROOT), APP,
                              tempfile.mkdtemp()], capture_output=True, text=True, timeout=120)
        self.assertIn("tamam", res.stdout, res.stdout[-1000:] + res.stderr[-3000:])

    def test_names(self):
        sys.path.insert(0, str(ROOT))
        from guncelleyici import calisan
        self.assertEqual(calisan.bus_name("lab.crucible.TalkToAndroid.desktop"), "lab.crucible.TalkToAndroid")
        self.assertEqual(calisan.object_path("org.gnome.Text-Editor"), "/org/gnome/Text_Editor")

    def test_restarts_itself_from_desktop_file(self):
        import tempfile

        from gi.repository import Gio
        sys.path.insert(0, str(ROOT))
        from guncelleyici import calisan
        d = Path(tempfile.mkdtemp())
        for name, extra in (("evet", "X-Guncellenince-Yeniden-Baslar=true\n"), ("hayir", "")):
            (d / f"{name}.desktop").write_text(f"[Desktop Entry]\nType=Application\nName=A\nExec=true\n{extra}")
        self.assertTrue(calisan.restarts_itself(Gio.DesktopAppInfo.new_from_filename(str(d / "evet.desktop"))))
        self.assertFalse(calisan.restarts_itself(Gio.DesktopAppInfo.new_from_filename(str(d / "hayir.desktop"))))
        self.assertFalse(calisan.restarts_itself(None))


if __name__ == "__main__":
    unittest.main()
