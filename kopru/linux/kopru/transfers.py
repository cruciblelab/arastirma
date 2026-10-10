"""Dosya aktarımları: gelen dosyalar önce gizli '.part' dosyasına yazılır,
SHA-256 doğrulanınca asıl adına taşınır."""

import hashlib
import os
import re
import shutil
from pathlib import Path

MAX_FILE = 64 * 1024 ** 3
_BAD = re.compile(r"[\x00-\x1f/\\]")


def safe_name(name) -> str:
    """Telefondan gelen adı klasör dışına çıkamayan tek bir dosya adına indirger.

    Eğik çizgi ve kontrol karakterleri '_' olur, baştaki noktalar atılır
    ('../../.bashrc' -> '_.._.bashrc').
    """
    name = _BAD.sub("_", str(name or "")).strip().lstrip(".").strip()
    if not name:
        name = "dosya"
    if len(name.encode("utf-8")) > 200:
        stem, dot, ext = name.rpartition(".")
        ext = ext if dot and len(ext) <= 10 else ""
        name = (stem if dot else name).encode("utf-8")[:180].decode("utf-8", "ignore") + (f".{ext}" if ext else "")
    return name


def unique_path(directory: Path, name: str) -> Path:
    p = directory / name
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    for i in range(1, 10_000):
        q = directory / f"{stem} ({i}){suffix}"
        if not q.exists():
            return q
    raise OSError("benzersiz dosya adı bulunamadı")


class Incoming:
    def __init__(self, tid: int, name: str, size: int, directory: Path):
        if not isinstance(size, int) or size < 0 or size > MAX_FILE:
            raise ValueError("geçersiz boyut")
        directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(directory).free < size + 50 * 1024 ** 2:
            raise OSError("diskte yer yok")
        self.tid = tid
        self.name = safe_name(name)
        self.size = size
        self.directory = directory
        self.received = 0
        self.part = directory / f".{self.name}.{tid}.kopru-part"
        self._f = open(self.part, "wb")
        self._sha = hashlib.sha256()

    def write(self, data: bytes):
        if self.received + len(data) > self.size:
            raise ValueError("bildirilen boyuttan fazla veri geldi")
        self._f.write(data)
        self._sha.update(data)
        self.received += len(data)

    def finish(self, sha256: str) -> Path:
        self._f.close()
        if self.received != self.size:
            self.abort()
            raise ValueError(f"eksik veri: {self.received}/{self.size}")
        if self._sha.hexdigest() != str(sha256).lower():
            self.abort()
            raise ValueError("SHA-256 tutmadı")
        final = unique_path(self.directory, self.name)
        os.replace(self.part, final)
        return final

    def abort(self):
        try:
            self._f.close()
        except OSError:
            pass
        try:
            self.part.unlink()
        except FileNotFoundError:
            pass
