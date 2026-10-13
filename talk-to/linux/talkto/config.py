"""Ayarlar ve güvenilen cihazlar: ~/.config/talk-to-android/ayarlar.json (izin 600)."""

import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path

from . import TCP_PORT


def config_dir() -> Path:
    if os.environ.get("TALKTO_CONFIG_DIR"):
        return Path(os.environ["TALKTO_CONFIG_DIR"])
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "talk-to-android"


def cache_dir() -> Path:
    if os.environ.get("TALKTO_CACHE_DIR"):
        return Path(os.environ["TALKTO_CACHE_DIR"])
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "talk-to-android"


def default_receive_dir() -> Path:
    try:
        import subprocess
        out = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=2)
        base = Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        base = None
    if not base or base == Path.home():
        base = Path.home() / "Downloads"
    return base / "TalkToAndroid"


class Config:
    """Basit, iş parçacığı güvenli JSON ayar deposu."""

    DEFAULTS = {
        "port": TCP_PORT,
        "wireless": True,  # yeni kurulumda Wi-Fi açık: kablo ve geliştirici ayarı gerekmeden bağlanılır
        "usb": True,
        "password": "",
        "receive_dir": "",
        "auto_accept": True,
        "show_notifications": True,
        "share_media": True,
        "run_in_background": True,
        "bluetooth": True,
        "default_profile": "benim",
        "setup_done": False,  # ilk açılıştaki kurulum yardımcısı bitirildi ya da atlandı
        "firewall_port": None,  # kurulum yardımcısından ufw izni eklenen port
        "autostart_default_done": False,  # "oturum açılınca başlat" bir kez kendiliğinden açıldı (sonra kullanıcının)
        # Basit mod (talkto.features): yalnızca bildirimler, çalan müzik ve telefonu bul görünür.
        "simple_mode": True,
        "extras": [],  # basit modda yine de görünsün diye eklenen özellikler
        "mini_player_pinned": False,  # müzik başlayınca mini oynatıcı kendiliğinden açılır
        "mini_on_top": False,  # mini oynatıcı diğer pencerelerin üstünde (Wayland'de XWayland ile)
        "mini_compact": False,  # mini oynatıcı tepecik (ince şerit) hâlinde
        "mini_size": "orta",  # kucuk / orta / buyuk
        "ada_enabled": True,  # üst ada (GNOME eklentisi kuruluysa) görünsün
        "ada_theme": "deniz",  # talkto.ui.ada.THEMES
        "ada_mode": "sakin",  # talkto.ui.ada.MODES: sakin | tasan (taşan dalgalar)
        "ada_offset": 0,  # üst adanın ortadan yana kaydırılması (px; "Konumu değiştir")
        "ada_track_popup": False,
        # Ada ekrandayken telefon bildirimleri ve aramalar masaüstü bildirimi olarak da çıksın mı. Kapalı: yalnızca
        # adada (GNOME'un bildirimi ekranın üst ortasında, adanın üstünü kapatıyordu; kullanıcı ikisini birden gördü).
        "ada_notif_popup": False,  # üst ada ekrandayken şarkı bildirimi de çıksın mı (ada zaten gösteriyor)
        "ada_click_sound": False,  # adada düğmeye basınca / sayfa değişince kısa ses
        "phone_vibrate": False,  # bilgisayar telefonda bir şey yapınca telefon kısaca titresin
        "mirror_preset": "akici",  # telefonun ekranı: akici / hizli / hafif (talkto.mirror.PRESETS)
        "mirror_audio": True,  # telefonun sesi ekran açıkken bilgisayardan çalsın (Android 11+)
        "track_popup": True,  # şarkı değişince masaüstü bildirimi
    }

    # Profil izinleri: bir telefon bilgisayarda neleri yapabilir.
    PERMISSIONS = {
        "notifications": "Bildirimlerini göster",
        "media": "Medya kontrolü (iki yön)",
        "files": "Dosya gönderebilir",
        "clipboard": "Pano paylaşımı",
        "open_url": "Bağlantıyı tarayıcıda açabilir",
        "commands": "Bilgisayar komutlarını çalıştırabilir",
        "power": "Uyku / kapat / yeniden başlat",
        "screenshot": "Ekran görüntüsü alabilir",
    }
    DEFAULT_PROFILES = {
        "benim": {"name": "Benim telefonum", "receive_dir": "", **{k: True for k in PERMISSIONS}},
        "misafir": {"name": "Misafir", "receive_dir": "",
                    **{k: k in ("notifications", "files", "media") for k in PERMISSIONS}},
    }

    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory) if directory else config_dir()
        self.path = self.dir / "ayarlar.json"
        self._lock = threading.RLock()
        self.data: dict = {}
        self._on_disk = False  # ayar dosyası bir kez yazıldı/okundu: sonradan yok olursa dışarıdan silinmiştir
        self.load()
        self._on_disk = self.path.exists()

    def load(self):
        with self._lock:
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}
            changed = False
            for k, v in self.DEFAULTS.items():
                if k not in self.data:
                    self.data[k] = v
                    changed = True
            if not self.data.get("device_id"):
                self.data["device_id"] = uuid.uuid4().hex
                changed = True
            if not self.data.get("name"):
                self.data["name"] = socket.gethostname() or "Linux"
                changed = True
            if not self.data.get("receive_dir"):
                self.data["receive_dir"] = str(default_receive_dir())
                changed = True
            self.data.setdefault("trusted", {})
            self.data.setdefault("commands", [])
            if not self.data.get("profiles"):
                self.data["profiles"] = {k: dict(v) for k, v in self.DEFAULT_PROFILES.items()}
                changed = True
            for prof in self.data["profiles"].values():
                for k in self.PERMISSIONS:
                    prof.setdefault(k, False)
                prof.setdefault("receive_dir", "")
            if self.data["default_profile"] not in self.data["profiles"]:
                self.data["default_profile"] = next(iter(self.data["profiles"]))
                changed = True
            if changed:
                self.save()

    def wiped(self) -> bool:
        """Ayarlar uygulama çalışırken dışarıdan silindi (ör. Paket Güncelleyici'de "verileri temizle")."""
        return self._on_disk and not self.path.exists()

    def save(self):
        with self._lock:
            if self.wiped():
                return  # bellekteki eski ayarları geri yazıp temizliği boşa çıkarmasın; uygulama sıfırdan başlar
            self.dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.dir, 0o700)
            tmp = self.path.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            self._on_disk = True

    def __getitem__(self, key):
        with self._lock:
            return self.data[key]

    def set(self, key, value):
        with self._lock:
            missing = object()
            old = self.data.get(key, missing)
            self.data[key] = value
            try:
                self.save()
            except OSError:
                # Disk dolu ya da yazılamıyor: bellekteki ayar diskteki ile ayrışmasın.
                if old is missing:
                    self.data.pop(key, None)
                else:
                    self.data[key] = old
                raise

    # Güvenilen cihazlar: belirtecin kendisi değil, SHA-256'sı saklanır.
    def trusted(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self.data["trusted"].items()}

    def trust(self, device_id: str, name: str, model: str, token_hash: str, profile: str | None = None):
        with self._lock:
            old = self.data["trusted"].get(device_id, {})
            self.data["trusted"][device_id] = {
                "name": name, "model": model, "token_hash": token_hash,
                "paired_at": int(time.time()),
                "profile": profile or old.get("profile") or self.data["default_profile"],
            }
            self.save()

    # ---- profiller ----------------------------------------------------------

    def profiles(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self.data["profiles"].items()}

    def profile_of(self, device_id: str | None) -> tuple[str, dict]:
        """Cihazın profili; tanınmayan cihaz için varsayılan profil."""
        with self._lock:
            pid = self.data["trusted"].get(device_id, {}).get("profile")
            if pid not in self.data["profiles"]:
                pid = self.data["default_profile"]
            return pid, dict(self.data["profiles"][pid])

    def save_profile(self, pid: str | None, values: dict) -> str:
        with self._lock:
            if not pid:
                pid = uuid.uuid4().hex[:8]
                base = dict(self.data["profiles"][self.data["default_profile"]])
                base["name"] = "Yeni profil"
                self.data["profiles"][pid] = base
            prof = self.data["profiles"][pid]
            for k, v in values.items():
                if k in self.PERMISSIONS:
                    prof[k] = bool(v)
                elif k == "name":
                    prof["name"] = str(v).strip()[:40] or prof["name"]
                elif k == "receive_dir":
                    prof["receive_dir"] = str(v)
            self.save()
            return pid

    def delete_profile(self, pid: str):
        with self._lock:
            if pid not in self.data["profiles"] or len(self.data["profiles"]) == 1:
                return
            del self.data["profiles"][pid]
            if self.data["default_profile"] == pid:
                self.data["default_profile"] = next(iter(self.data["profiles"]))
            for t in self.data["trusted"].values():
                if t.get("profile") == pid:
                    t["profile"] = self.data["default_profile"]
            self.save()

    def assign_profile(self, device_id: str, pid: str):
        with self._lock:
            if device_id in self.data["trusted"] and pid in self.data["profiles"]:
                self.data["trusted"][device_id]["profile"] = pid
                self.save()

    # ---- özel komutlar ---------------------------------------------------------

    def commands(self) -> list[dict]:
        with self._lock:
            return [dict(c) for c in self.data["commands"]]

    def save_command(self, cid: str | None, name: str, command: str) -> str:
        with self._lock:
            name, command = name.strip()[:60], command.strip()
            for c in self.data["commands"]:
                if c["id"] == cid:
                    c.update(name=name, command=command)
                    break
            else:
                cid = "ozel-" + uuid.uuid4().hex[:8]
                self.data["commands"].append({"id": cid, "name": name, "command": command})
            self.save()
            return cid

    def delete_command(self, cid: str):
        with self._lock:
            self.data["commands"] = [c for c in self.data["commands"] if c["id"] != cid]
            self.save()

    def forget(self, device_id: str):
        with self._lock:
            if self.data["trusted"].pop(device_id, None) is not None:
                self.save()
