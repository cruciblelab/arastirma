"""Adanın işlemci ölçümü (Ada sekmesindeki "Ölç"): GNOME Shell'in süresi okunur, önce seçili hareketle sonra
geçici olarak Durgun'da; ayar değişmez."""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib  # noqa: E402

from talkto import olcum  # noqa: E402


class Row:
    def __init__(self):
        self.subtitles = []
        self.sensitive = True

    def set_subtitle(self, text):
        self.subtitles.append(text)

    def set_sensitive(self, on):
        self.sensitive = on


class OlcumTest(unittest.TestCase):
    def test_reads_own_process(self):
        a = olcum.cpu_seconds(os.getpid())
        self.assertIsNotNone(a)
        s = olcum.Sampler(os.getpid())
        x = 0
        for i in range(300000):  # biraz iş
            x += i * i
        self.assertGreater(s.percent(), 0)
        self.assertIsNone(olcum.cpu_seconds(10 ** 9))
        pid = olcum.shell_pid()
        self.assertTrue(pid is None or isinstance(pid, int))

    def test_summary(self):
        t = olcum.summary("Canlı", 12.34, 3.0)
        self.assertIn("Canlı: %12,3", t)
        self.assertIn("Durgun: %3,0", t)
        self.assertIn("adanın payı ≈ %9,3", t)
        self.assertIn("payı ≈ %0,0", olcum.summary("Yavaş", 2.0, 2.5))  # eksiye düşmez
        self.assertIn("Ölçülemedi", olcum.summary("Canlı", None, 1.0))

    def test_measure_switches_motion_temporarily(self):
        from talkto.ui.window import Window
        changed = []
        service = SimpleNamespace(motion_override=None)
        service.changed = lambda: changed.append(service.motion_override)
        fake = SimpleNamespace(app=SimpleNamespace(ada=service, config={"ada_motion": "canli"}),
                               ada_olc=Row(), ada_olc_btn=Row())
        loop = GLib.MainLoop()
        with mock.patch.object(olcum, "shell_pid", return_value=os.getpid()):
            Window._ada_measure(fake, seconds=0.2)
            self.assertFalse(fake.ada_olc_btn.sensitive)
            GLib.timeout_add(700, loop.quit)
            loop.run()
        self.assertEqual(changed, ["durgun", None])  # önce Durgun, sonra eski hâline (ayar hiç yazılmadı)
        self.assertTrue(fake.ada_olc_btn.sensitive)
        self.assertIn("adanın payı", fake.ada_olc.subtitles[-1])
        self.assertEqual(fake.app.config["ada_motion"], "canli")
        # Durgun'da ya da GNOME dışında ölçülmez
        fake.app.config["ada_motion"] = "durgun"
        Window._ada_measure(fake)
        self.assertIn("Durgun", fake.ada_olc.subtitles[-1])
        fake.app.config["ada_motion"] = "canli"
        with mock.patch.object(olcum, "shell_pid", return_value=None):
            Window._ada_measure(fake)
        self.assertIn("GNOME Shell bulunamadı", fake.ada_olc.subtitles[-1])


if __name__ == "__main__":
    unittest.main()
