"""Paket kilidini tutan işlemi durmaya zorlamak ("Durmaya zorla").

İki parça:
- risk(): yetki istemeden şu an ne yapıldığına bakar (/proc). Arayüz bunu gösterir ve karar kullanıcıda kalır;
  yalnızca çekirdek ya da önyükleyici kurulurken durdurmaya hiç izin verilmez (bilgisayar açılmayabilir).
- Bu dosya yönetici olarak çalıştırılınca (pkexec python3 -I durdur.py PID) asıl işi yapar: süreç gerçekten
  paket kilidini tutuyor ve bir paket aracıysa önce kibarca (SIGTERM: Ubuntu'nun otomatik güncellemesi o anki
  paketi bitirip durur), olmazsa zorla durdurur; ardından yarım kalan işi tamamlar (dpkg --configure -a).

Tek başına çalışır (paketin geri kalanını içe aktarmaz): yönetici olarak yalnızca bu dosya çalışır.
Çıkış kodları: 0 durdu, 2 yanlış kullanım, 3 kilit artık onda değil / bir paket aracı değil, 4 çekirdek kuruluyor,
5 durmadı.
"""

import os
import re
import signal
import subprocess
import sys
import time

LOCKS = ("/var/lib/dpkg/lock-frontend", "/var/lib/dpkg/lock", "/var/lib/apt/lists/lock",
         "/var/cache/apt/archives/lock")
# Kilidi tutabilecek paket araçları (/proc/PID/comm, en çok 15 karakter).
TOOLS = {"unattended-upgr", "apt", "apt-get", "aptd", "packagekitd", "dpkg", "synaptic", "aptitude",
         "aptitude-curses", "update-manager", "mintupdate-auto"}
_BOOT = re.compile(r"(?:^|/)(?:update-initramfs|mkinitramfs|update-grub2?|grub-install|grub-mkconfig|dkms|"
                   r"zz-update-grub|kernel-install|update-secureboot-policy)\b")
_BOOT_PKG = re.compile(r"(?:^|/)(?:linux-(?:image|modules|firmware|signed)|grub|shim|initramfs-tools)[\w.+-]*")
TERM_WAIT = 90  # sn: otomatik güncelleme o anki paketi bitirip durur; büyük bir paket biraz sürebilir
KILL_WAIT = 10

# risk() sonucu
GUVENLI = "guvenli"      # henüz bir şey kurulmuyor (indiriyor, hazırlanıyor)
KURUYOR = "kuruyor"      # dpkg şu an paket kuruyor: durdurmak yarım paket bırakabilir (sonra tamamlanır)
CEKIRDEK = "cekirdek"    # çekirdek / önyükleyici: durdurulmaz


def _procs(proc="/proc"):
    """[(pid, komut adı, komut satırı)]"""
    out = []
    for name in os.listdir(proc):
        if not name.isdigit():
            continue
        try:
            with open(f"{proc}/{name}/comm") as f:
                comm = f.read().strip()
            with open(f"{proc}/{name}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        out.append((int(name), comm, cmd))
    return out


def risk(proc="/proc") -> tuple[str, list[str]]:
    """(GUVENLI | KURUYOR | CEKIRDEK, şu an kurulan paketler)."""
    packages, boot = [], False
    for _pid, comm, cmd in _procs(proc):
        if _BOOT.search(" ".join(cmd.split()[:2])):  # komutun kendisi ya da "sh betik" biçimi
            boot = True
        if comm == "dpkg":
            args = [a for a in cmd.split()[1:] if not a.startswith("-") and not a.isdigit()]
            for a in args:
                name = os.path.basename(a).split("_", 1)[0]
                if name and name not in packages:
                    packages.append(name)
            if _BOOT_PKG.search(" ".join("/" + os.path.basename(a) for a in args)):
                boot = True
    if boot:
        return CEKIRDEK, packages
    if any(comm == "dpkg" for _p, comm, _c in _procs(proc)):
        return KURUYOR, packages
    return GUVENLI, packages


def _lock_inodes() -> set[int]:
    out = set()
    for p in LOCKS:
        try:
            out.add(os.stat(p).st_ino)
        except OSError:
            pass
    return out


def holds_lock(pid: int, locks_file="/proc/locks", inodes=None) -> bool:
    """Bu süreç bir paket kilidini tutuyor mu (/proc/locks: "1: POSIX ADVISORY WRITE 1234 08:01:131090 0 EOF")."""
    inodes = _lock_inodes() if inodes is None else inodes
    try:
        with open(locks_file) as f:
            lines = f.read().splitlines()
    except OSError:
        return False
    for line in lines:
        parts = line.split()
        if len(parts) >= 6 and parts[4] == str(pid):
            try:
                if int(parts[5].rsplit(":", 1)[1]) in inodes:
                    return True
            except (IndexError, ValueError):
                continue
    return False


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # Ölmüş ama henüz toplanmamış (zombi) süreç de bitmiş sayılır.
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return False


def _wait_gone(pid: int, secs: float) -> bool:
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if not _alive(pid):
            return True
        time.sleep(0.3)
    return not _alive(pid)


def say(state, text=""):
    """Arayüz durumu kendi dilinde gösterir (durum: <ad>); metin yalnızca günlük/ayrıntı için."""
    print(f"durum: {state} {text}".rstrip(), flush=True)


def main(argv) -> int:
    if len(argv) != 2 or not argv[1].isdigit():
        print("kullanım: durdur.py PID", file=sys.stderr)
        return 2
    pid = int(argv[1])
    try:
        with open(f"/proc/{pid}/comm") as f:
            comm = f.read().strip()
    except OSError:
        say("bitmis", "süreç zaten bitmiş")
        return 0
    if comm not in TOOLS:
        say("arac-degil", f"{comm} bir paket aracı değil; dokunulmadı")
        return 3
    if not holds_lock(pid):
        say("kilit-yok", "paket kilidi artık bu süreçte değil; dokunulmadı")
        return 3
    level, _ = risk()
    if level == CEKIRDEK:
        say("cekirdek", "çekirdek ya da önyükleyici kuruluyor; durdurulmadı")
        return 4
    say("istendi", f"{comm} ({pid}) durması isteniyor")
    os.kill(pid, signal.SIGTERM)
    if not _wait_gone(pid, TERM_WAIT):
        say("zorla", f"{comm} kendiliğinden durmadı; zorla durduruluyor")
        os.kill(pid, signal.SIGKILL)
        if not _wait_gone(pid, KILL_WAIT):
            say("durmadi", "süreç durmadı")
            return 5
    # Yarım kalan işi başka bir apt (ör. sırada bekleyen kurulum) başlamadan tamamlamak için ön kilidi hemen al:
    # sıradaki apt saniyede bir dener, biz daha sık.
    front = _take_front_lock(20)
    try:
        # Geride çalışan dpkg kaldıysa bitmesini bekle (o anki paketi yarıda kesmemek için).
        say("dpkg-bekleniyor")
        end = time.monotonic() + 300
        while time.monotonic() < end and any(c == "dpkg" for _p, c, _cmd in _procs()):
            time.sleep(1)
        if interrupted():
            say("tamamlaniyor", "yarım kalan iş tamamlanıyor (dpkg --configure -a)")
            env = dict(os.environ, DEBIAN_FRONTEND="noninteractive", LC_ALL="C.UTF-8")
            if front is not None:
                env["DPKG_FRONTEND_LOCKED"] = "1"  # ön kilit bizde (apt'nin dpkg'yi çalıştırdığı gibi)
            subprocess.run(["/usr/bin/dpkg", "--force-confdef", "--force-confold", "--configure", "-a"], env=env,
                           stdin=subprocess.DEVNULL)
    finally:
        if front is not None:
            os.close(front)
    say("bitti", "durduruldu")
    return 0


def _take_front_lock(secs: float):
    import fcntl
    end = time.monotonic() + secs
    while time.monotonic() < end:
        try:
            fd = os.open(LOCKS[0], os.O_RDWR | os.O_CREAT, 0o640)
        except OSError:
            return None
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except OSError:
            os.close(fd)
            time.sleep(0.1)
    return None


def interrupted(updates_dir="/var/lib/dpkg/updates") -> bool:
    """Yarıda kalmış dpkg işi var mı."""
    try:
        if any(n.isdigit() for n in os.listdir(updates_dir)):
            return True
    except OSError:
        pass
    try:
        res = subprocess.run(["dpkg", "--audit"], capture_output=True, text=True, timeout=60,
                             env=dict(os.environ, LC_ALL="C.UTF-8"))
    except (OSError, subprocess.TimeoutExpired):
        return True  # bilinmiyorsa tamamlamayı dene (zararı yok)
    return bool(res.stdout.strip())


if __name__ == "__main__":
    sys.exit(main(sys.argv))
