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
LOCKED = ("İzin verilemedi: bu telefon adb'nin izin vermesini engelliyor. Geliştirici seçeneklerinde Xiaomi'de "
          "“USB hata ayıklama (Güvenlik ayarları)”nı, Oppo/Realme/OnePlus'ta “İzin izlemeyi devre dışı bırak”ı aç; "
          "diğerlerinde bu adımı telefonda elle yap.")


def _item(key, title, ok, message=""):
    return {"key": key, "title": title, "ok": ok, "message": message}


def _explain(out: str) -> str:
    text = out.strip()
    if "SecurityException" in text or "GRANT_RUNTIME_PERMISSIONS" in text or "not allowed" in text.lower():
        return LOCKED
    if "Unknown package" in text or "not installed" in text.lower():
        return "Talk To telefonda kurulu değil."
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
        return [_item("app", "Talk To telefonda yok", False, "Önce telefona Talk To'yu kur.")]
    rc, out = await _sh(serial, "dumpsys", "package", PHONE_PACKAGE)
    full = "service.NotificationListener" in out  # hafif sürümde bildirim dinleyicisi yok
    # Play sürümü "diğer uygulamaların üzerinde göster" iznini istemiyor: verilemez, sorulmaz da.
    overlay = "android.permission.SYSTEM_ALERT_WINDOW" in out
    granted = {k: bool(re.search(rf"android\.permission\.{k}: granted=true", out))
               for k in ("POST_NOTIFICATIONS", "BLUETOOTH_CONNECT", "ANSWER_PHONE_CALLS")}

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
                "telefon bilgisayarın vermesine izin vermedi; telefonda Talk To açılınca çıkan soruya "
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

    if full:
        items += await _answer_items(serial, granted["ANSWER_PHONE_CALLS"], overlay)

    # Xiaomi/HyperOS: "Otomatik başlatma" kapalıyken telefon açılınca uygulamaya haber verilmez; telefon yeniden
    # başlayınca bilgisayara kendiliğinden bağlanamaz.
    _, maker = await _sh(serial, "getprop", "ro.product.manufacturer")
    if maker.strip().lower() in XIAOMI:
        ok, why = await _appop(serial, "10008")
        items.append(_item("xiaomi_autostart", "Otomatik başlatma (Xiaomi)", ok,
                           "zaten açık" if why == "zaten" else "" if ok else
                           f"verilemedi ({why}); telefonda Ayarlar → Uygulamalar → Talk To → Otomatik başlatma'yı "
                           "aç, yoksa telefon yeniden başlayınca bağlanmak için uygulamayı açman gerekir"))

    if sdk >= 31:
        if granted["BLUETOOTH_CONNECT"]:
            items.append(_item("bluetooth", "Bluetooth izni", True, "zaten açık"))
        else:
            rc, out = await _sh(serial, "pm", "grant", PHONE_PACKAGE, "android.permission.BLUETOOTH_CONNECT")
            # Yalnızca Bluetooth ile bağlanmak için; verilemezse eksik sayılmaz (telefon gerekince kendisi sorar).
            items.append(_item("bluetooth", "Bluetooth izni", True if rc == 0 else None,
                               "" if rc == 0 else "verilemedi; Bluetooth kullanırsan telefon gerektiğinde sorar"))
    return items


ANSWER_HINT = "olmazsa aramayı telefondan cevaplarsın"
XIAOMI = ("xiaomi", "redmi", "poco")


async def _answer_items(serial: str, answer_granted: bool, overlay: bool = True) -> list[dict]:
    """Aramayı bilgisayardan cevaplamak için gerekenler. Telefonda yeni bir ayar satırı yok: hepsi buradan
    sessizce verilir, verilemeyen olursa nedeniyle söylenir (ok False).

    - ANSWER_PHONE_CALLS: Android'in resmi yolu (TelecomManager.acceptRingingCall), SIM aramaları için.
    - "Diğer uygulamaların üzerinde göster": arama uygulamasının "Cevapla"sı çoğunlukla arama ekranını açar;
      Android arka plandaki uygulamanın ekran açmasını engelliyor, bu izinle telefon basarken görünmez bir
      nokta açıp engele takılmaz (WhatsApp, Instagram aramaları).
    - Xiaomi/HyperOS: ayrıca "Arka planda açılır pencereler" izni (kendi izin numarası 10021).
    """
    items = []
    if answer_granted:
        items.append(_item("answer", "Aramayı bilgisayardan cevaplama izni", True, "zaten açık"))
    else:
        rc, out = await _sh(serial, "pm", "grant", PHONE_PACKAGE, "android.permission.ANSWER_PHONE_CALLS")
        items.append(_item("answer", "Aramayı bilgisayardan cevaplama izni", rc == 0, "" if rc == 0 else (
            f"telefon bilgisayarın vermesine izin vermedi; {ANSWER_HINT}" if _explain(out) == LOCKED else
            f"verilemedi ({_explain(out)}); {ANSWER_HINT}")))

    if overlay:
        ok, why = await _appop(serial, "SYSTEM_ALERT_WINDOW")
        items.append(_item("overlay", "Arama ekranını açabilme (üstte gösterme izni)", ok,
                           "zaten açık" if why == "zaten" else "" if ok else f"verilemedi ({why}); {ANSWER_HINT}"))

    _, maker = await _sh(serial, "getprop", "ro.product.manufacturer")
    if maker.strip().lower() in XIAOMI:
        ok, why = await _appop(serial, "10021")
        items.append(_item("xiaomi_popup", "Arka planda açılır pencereler (Xiaomi)", ok,
                           "zaten açık" if why == "zaten" else "" if ok else
                           f"verilemedi ({why}); telefonda Ayarlar → Uygulamalar → Talk To → Diğer izinler'den "
                           f"açılabilir, {ANSWER_HINT}"))
    return items


async def _appop(serial: str, op: str) -> tuple[bool, str]:
    """appops ile izin verir: (oldu mu, "zaten" ya da hata nedeni)."""
    _, now = await _sh(serial, "appops", "get", PHONE_PACKAGE, op)
    if _allowed(now):
        return True, "zaten"
    rc, out = await _sh(serial, "appops", "set", PHONE_PACKAGE, op, "allow")
    if rc != 0 or "Error" in out or "Exception" in out or "Unknown" in out:
        return False, "telefon izin vermedi" if _explain(out) == LOCKED else _explain(out)
    _, now = await _sh(serial, "appops", "get", PHONE_PACKAGE, op)
    if _allowed(now) or not now.strip() or "No operations" in now:  # bazı telefonlar okumayı göstermiyor
        return True, ""
    return False, "telefon izni geri aldı"


def _allowed(out: str) -> bool:
    return bool(re.search(r":\s*allow\b", out))


def _listener_on(enabled: str) -> bool:
    return LISTENER in enabled or f"{PHONE_PACKAGE}/.service.NotificationListener" in enabled


def summary(items: list[dict]) -> str:
    failed = [i for i in items if i["ok"] is False]
    if not failed:
        return "Telefon ayarlandı: izinler verildi."
    return "Bazı adımlar olmadı: " + "; ".join(f"{i['title']} ({i['message']})" for i in failed)
