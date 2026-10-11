"""Telefondaki izinleri bilgisayardan, USB üzerinden (adb) tek seferde vermek.

Telefonda bu ayarlar farklı menülere dağılmış ve bazıları (Android 13+'ta dışarıdan
kurulan uygulamaya bildirim erişimi: "kısıtlanmış ayar") kullanıcıyı bilerek zorlar.
USB hata ayıklama açıkken adb aynı ayarları doğrudan yapabilir. Yalnızca Talk To
Linux'un kendi izinlerine dokunulur; başka uygulamaya ya da sistem ayarına değil.
"""

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

    items = []
    if sdk >= 33:
        # Dışarıdan kurulan uygulamada bildirim erişimini açan "kısıtlanmış ayarlara izin ver" anahtarı.
        await _sh(serial, "appops", "set", PHONE_PACKAGE, "ACCESS_RESTRICTED_SETTINGS", "allow")
        rc, out = await _sh(serial, "pm", "grant", PHONE_PACKAGE, "android.permission.POST_NOTIFICATIONS")
        items.append(_item("post", "Bildirim gösterme izni", rc == 0, "" if rc == 0 else _explain(out)))
    else:
        items.append(_item("post", "Bildirim gösterme izni", None, "Bu Android sürümünde gerekmiyor."))

    if full:
        rc, out = await _sh(serial, "cmd", "notification", "allow_listener", LISTENER)
        _, now = await _sh(serial, "settings", "get", "secure", "enabled_notification_listeners")
        ok = LISTENER in now or f"{PHONE_PACKAGE}/.service.NotificationListener" in now
        items.append(_item("listener", "Bildirim erişimi (bildirimler ve müzik)", ok,
                           "" if ok else _explain(out)))
    else:
        items.append(_item("listener", "Bildirim erişimi", None, "Hafif sürümde bu özellik yok."))

    rc, out = await _sh(serial, "dumpsys", "deviceidle", "whitelist", f"+{PHONE_PACKAGE}")
    await _sh(serial, "cmd", "appops", "set", PHONE_PACKAGE, "RUN_ANY_IN_BACKGROUND", "allow")
    _, now = await _sh(serial, "dumpsys", "deviceidle", "whitelist")
    ok = PHONE_PACKAGE in now
    items.append(_item("battery", "Pil kısıtlaması kaldırıldı", ok, "" if ok else _explain(out)))

    if sdk >= 31:
        rc, out = await _sh(serial, "pm", "grant", PHONE_PACKAGE, "android.permission.BLUETOOTH_CONNECT")
        items.append(_item("bluetooth", "Bluetooth izni", rc == 0, "" if rc == 0 else _explain(out)))
    return items


def summary(items: list[dict]) -> str:
    failed = [i for i in items if i["ok"] is False]
    if not failed:
        return "Telefon ayarlandı: izinler verildi."
    return "Bazı adımlar olmadı: " + "; ".join(f"{i['title']} ({i['message']})" for i in failed)
