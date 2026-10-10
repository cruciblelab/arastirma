"""Ayarlar ve güvenilen cihazlar: ~/.config/kopru/ayarlar.json (izin 600)."""

import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path

from . import TCP_PORT


def config_dir() -> Path:
    if os.environ.get("KOPRU_CONFIG_DIR"):
        return Path(os.environ["KOPRU_CONFIG_DIR"])
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "kopru"


def cache_dir() -> Path:
    if os.environ.get("KOPRU_CACHE_DIR"):
        return Path(os.environ["KOPRU_CACHE_DIR"])
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "kopru"


def default_receive_dir() -> Path:
    try:
        import subprocess
        out = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=2)
        base = Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        base = None
    if not base or base == Path.home():
        base = Path.home() / "Downloads"
    return base / "Kopru"


class Config:
    """Basit, iş parçacığı güvenli JSON ayar deposu."""

    DEFAULTS = {
        "port": TCP_PORT,
        "wireless": False,
        "usb": True,
        "password": "",
        "receive_dir": "",
        "auto_accept": True,
        "show_notifications": True,
        "share_media": True,
        "run_in_background": True,
    }

    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory) if directory else config_dir()
        self.path = self.dir / "ayarlar.json"
        self._lock = threading.RLock()
        self.data: dict = {}
        self.load()

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
            if changed:
                self.save()

    def save(self):
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.dir, 0o700)
            tmp = self.path.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)

    def __getitem__(self, key):
        with self._lock:
            return self.data[key]

    def set(self, key, value):
        with self._lock:
            self.data[key] = value
            self.save()

    # Güvenilen cihazlar: belirtecin kendisi değil, SHA-256'sı saklanır.
    def trusted(self) -> dict:
        with self._lock:
            return {k: dict(v) for k, v in self.data["trusted"].items()}

    def trust(self, device_id: str, name: str, model: str, token_hash: str):
        with self._lock:
            self.data["trusted"][device_id] = {
                "name": name, "model": model, "token_hash": token_hash,
                "paired_at": int(time.time()),
            }
            self.save()

    def forget(self, device_id: str):
        with self._lock:
            if self.data["trusted"].pop(device_id, None) is not None:
                self.save()
