"""Açık uygulamayı bulup kapatma (calisan.py): gerçek oturum veriyolunda gerçek bir GApplication ile.

Ayrı bir veriyolu (dbus-run-session) içinde küçük bir uygulama başlatılır; Paket Güncelleyici onu
açık görmeli, "quit" eylemini bulmalı ve kapatabilmeli.
"""

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


@unittest.skipUnless(shutil.which("dbus-run-session"), "dbus-run-session yok")
class CalisanTest(unittest.TestCase):
    def test_find_and_quit_running_app(self):
        res = subprocess.run(["dbus-run-session", "--", sys.executable, "-c", CHECK, str(ROOT), "", APP],
                             capture_output=True, text=True, timeout=60)
        self.assertIn("tamam", res.stdout, res.stderr[-2000:])

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
