"""Telefondaki izinleri bilgisayardan, USB üzerinden (adb) tek seferde vermek.

Telefonda bu ayarlar farklı menülere dağılmış ve bazıları (Android 13+'ta dışarıdan
kurulan uygulamaya bildirim erişimi: "kısıtlanmış ayar") kullanıcıyı bilerek zorlar.
USB hata ayıklama açıkken adb aynı ayarları doğrudan yapabilir. Yalnızca Talk To
Linux'un kendi izinlerine dokunulur; başka uygulamaya ya da sistem ayarına değil.
"""

import asyncio
import re

from .usb import PHONE_PACKAGE, _adb

LISTENER = f"{PHONE_PACKAGE}/{PHONE_PACKAGE}.service.NotificationListener"

# Bazı üreticilerde (Xiaomi/MIUI, Oppo/ColorOS) adb'nin izin vermesi ayrı bir anahtar ister.
LOCKED = ("İzin verilemedi: bu telefon adb'nin izin vermesini engelliyor. Xiaomi'de Geliştirici seçenekleri → "
          "“USB hata ayıklama (Güvenlik ayarları)”nı aç; diğerlerinde bu adımı telefonda elle yap.")


def _item(key, title, ok, message=""):
    return {"key": key, "title": title, "ok": ok, "message": message}


def _explain(out: str) -> str:
    text = out.strip()
    if "SecurityException" in text or "GRANT_RUNTIME_PERMISSIONS" in text or "not allowed" in text.lower():
        return LOCKED
    if "Unknown package" in text or "not installed" in text.lower():
        return "Talk To Linux telefonda kurulu değil."
    return text.splitlines()[-1][:200] if text else "bilinmeyen hata"


async def _sh(serial: str, *args, timeout=15.0) -> tuple[int, str]:
    return await _adb("-s", serial, "shell", *args, timeout=timeout)


async def setup_phone(serial: str) -> list[dict]:
    """İzinleri verir ve her adımın sonucunu döndürür: ok True (yapıldı), False (olmadı), None (gerekmiyor)."""
    rc, out = await _sh(serial, "getprop", "ro.build.version.sdk")
    try:
        sdk = int(out.strip())
    except ValueError:
        return [_item("adb", "Telefona ulaşılamadı", False, _explain(out) if rc else "Android sürümü okunamadı")]
    rc, out = await _sh(serial, "pm", "path", PHONE_PACKAGE)
    if rc != 0 or "package:" not in out:
        return [_item("app", "Talk To Linux telefonda yok", False, "Önce “Talk To Linux'u kur” ile kur.")]
    rc, out = await _sh(serial, "dumpsys", "package", PHONE_PACKAGE)
    full = "service.NotificationListener" in out  # hafif sürümde bildirim dinleyicisi yok
    granted = {k: bool(re.search(rf"android\.permission\.{k}: granted=true", out))
               for k in ("POST_NOTIFICATIONS", "BLUETOOTH_CONNECT")}

    # Telefonda elle verilmiş olanlara dokunulmaz ("zaten açık"): bazı telefonlar (Xiaomi) adb'nin izin
    # vermesini engelliyor, verilmiş izni yeniden vermeye çalışıp "olmadı" demek yanıltıcıydı.
    items = []
    if sdk >= 33:
        # Dışarıdan kurulan uygulamada bildirim erişimini açan "kısıtlanmış ayarlara izin ver" anahtarı.
        await _sh(serial, "appops", "set", PHONE_PACKAGE, "ACCESS_RESTRICTED_SETTINGS", "allow")
        if granted["POST_NOTIFICATIONS"]:
            items.append(_item("post", "Bildirim gösterme izni", True, "zaten açık"))
        else:
            rc, out = await _sh(serial, "pm", "grant", PHONE_PACKAGE, "android.permission.POST_NOTIFICATIONS")
            items.append(_item("post", "Bildirim gösterme izni", rc == 0, "" if rc == 0 else (
                "telefon bilgisayarın vermesine izin vermedi; telefonda Talk To Linux açılınca çıkan soruya "
                "“İzin ver” de" if _explain(out) == LOCKED else _explain(out))))
    else:
        items.append(_item("post", "Bildirim gösterme izni", None, "Bu Android sürümünde gerekmiyor."))

    if full:
        _, now = await _sh(serial, "settings", "get", "secure", "enabled_notification_listeners")
        if _listener_on(now):
            items.append(_item("listener", "Bildirim erişimi (bildirimler ve müzik)", True, "zaten açık"))
        else:
            rc, out = await _sh(serial, "cmd", "notification", "allow_listener", LISTENER)
            # Android ayarı bir an geç yazabiliyor: hemen okuyunca verilmemiş sanılıyordu ("bilinmeyen hata").
            ok = False
            for _ in range(8):
                _, now = await _sh(serial, "settings", "get", "secure", "enabled_notification_listeners")
                ok = _listener_on(now)
                if ok or (rc != 0 and out.strip()):
                    break
                await asyncio.sleep(0.5)
            items.append(_item("listener", "Bildirim erişimi (bildirimler ve müzik)", ok,
                               "" if ok else (_explain(out) if out.strip() else
                                              "telefon onaylamadı; telefonda Bildirim erişimi'nden elle aç")))
    else:
        items.append(_item("listener", "Bildirim erişimi", None, "Hafif sürümde bu özellik yok."))

    _, now = await _sh(serial, "dumpsys", "deviceidle", "whitelist")
    if PHONE_PACKAGE in now:
        items.append(_item("battery", "Pil kısıtlaması kaldırıldı", True, "zaten kaldırılmış"))
    else:
        rc, out = await _sh(serial, "dumpsys", "deviceidle", "whitelist", f"+{PHONE_PACKAGE}")
        await _sh(serial, "cmd", "appops", "set", PHONE_PACKAGE, "RUN_ANY_IN_BACKGROUND", "allow")
        _, now = await _sh(serial, "dumpsys", "deviceidle", "whitelist")
        ok = PHONE_PACKAGE in now
        items.append(_item("battery", "Pil kısıtlaması kaldırıldı", ok, "" if ok else _explain(out)))

    if sdk >= 31:
        if granted["BLUETOOTH_CONNECT"]:
            items.append(_item("bluetooth", "Bluetooth izni", True, "zaten açık"))
        else:
            rc, out = await _sh(serial, "pm", "grant", PHONE_PACKAGE, "android.permission.BLUETOOTH_CONNECT")
            # Yalnızca Bluetooth ile bağlanmak için; verilemezse eksik sayılmaz (telefon gerekince kendisi sorar).
            items.append(_item("bluetooth", "Bluetooth izni", True if rc == 0 else None,
                               "" if rc == 0 else "verilemedi; Bluetooth kullanırsan telefon gerektiğinde sorar"))
    return items


def _listener_on(enabled: str) -> bool:
    return LISTENER in enabled or f"{PHONE_PACKAGE}/.service.NotificationListener" in enabled


def summary(items: list[dict]) -> str:
    failed = [i for i in items if i["ok"] is False]
    if not failed:
        return "Telefon ayarlandı: izinler verildi."
    return "Bazı adımlar olmadı: " + "; ".join(f"{i['title']} ({i['message']})" for i in failed)
