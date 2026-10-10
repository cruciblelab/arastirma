"""Kurulum yardımcısının denetimleri (arayüzden bağımsız, test edilebilir).

Her adım bir başlık, açıklama ve satırlardan oluşur. Satırın durumu True (tamam),
False (yapılmalı) ya da None (yalnızca bilgi); "action" arayüzün çalıştıracağı işin adı.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import UDP_PORT, mirror

UFW_CONF = Path("/etc/ufw/ufw.conf")


@dataclass
class Item:
    title: str
    text: str
    ok: bool | None
    action: str | None = None        # ör. "install_adb", "install_phone_app:SERIAL"
    action_label: str | None = None
    optional: bool = False


@dataclass
class Step:
    key: str
    title: str
    text: str
    icon: str
    items: list[Item] = field(default_factory=list)


def ufw_enabled(conf: Path = UFW_CONF) -> bool:
    """Ubuntu'nun güvenlik duvarı açık mı (yapılandırma herkesçe okunabilir; durum komutu root ister)."""
    try:
        return any(line.strip().lower() == "enabled=yes" for line in conf.read_text().splitlines())
    except OSError:
        return False


def firewall_command(port: int) -> list[str] | None:
    if not shutil.which("pkexec") or not shutil.which("ufw"):
        return None
    return ["pkexec", "sh", "-c", f"ufw allow {int(port)}/tcp && ufw allow {UDP_PORT}/udp"]


def _usb_phone(usb: dict) -> Item:
    devices = usb.get("devices", [])
    ready = [d for d in devices if d.get("state") == "device"]
    if ready:
        return Item("Telefon USB'de görünüyor", f"{ready[0].get('model') or ready[0]['serial']} bağlı ve onaylı.", True)
    if any(d.get("state") == "unauthorized" for d in devices):
        return Item("Telefon onay bekliyor", "Telefonda çıkan “USB hata ayıklamaya izin ver” sorusunu onayla "
                    "(“Bu bilgisayara her zaman izin ver”i işaretle).", False)
    if any(d.get("state") == "no" for d in devices):
        return Item("Bilgisayarın telefona erişim izni yok", "Kabloyu çıkarıp tak; düzelmezse "
                    "“android-sdk-platform-tools-common” paketini kur.", False)
    if usb.get("unseen"):
        name = usb["unseen"][0].get("name") or "Telefon"
        return Item(f"{name} takılı ama USB hata ayıklama kapalı",
                    "Telefonda: Ayarlar → Telefon hakkında → “Yapım numarası”na 7 kez dokun; sonra Geliştirici "
                    "seçenekleri → “USB hata ayıklama”yı aç. Telefondaki Talk To Linux'un kurulum sihirbazı da "
                    "bu adımları gösterir.", False)
    return Item("Telefon takılı değil", "Telefonu USB kablosuyla tak. Yalnızca şarj eden kablolar veri taşımaz; "
                "telefonla gelen kabloyu kullan.", False)


def steps(status: dict, usb: dict, *, autostart: bool = False, ufw: bool | None = None) -> list[Step]:
    sessions = status.get("sessions", [])
    ready = [d for d in usb.get("devices", []) if d.get("state") == "device"]
    out = [Step("hos-geldin", "Talk To Android'e hoş geldin",
                "Bu bilgisayarı Android telefonuna bağlar: telefon bildirimleri burada görünür, müzik iki yönden "
                "kontrol edilir, dosya ve pano gider gelir, telefon bu bilgisayara komut verir. Birkaç adımda "
                "hazırlayalım; her adımda “Kontrol et” ile durumu yeniden okuyabilirsin. İstediğin zaman "
                "menüdeki “Kurulum yardımcısı”ndan geri dönebilirsin.", "lab.crucible.TalkToAndroid")]

    phone = Step("telefon", "Telefondaki uygulama",
                 "Telefona Talk To Linux uygulaması kurulmalı. En kolayı: telefonu USB ile takıp bir sonraki adımdan "
                 "tek tıkla kurmak (Play Protect bu yolla engellemez).", "phone-symbolic")
    phone.items.append(Item("Telefon uygulaması bu pakette", "Kurulum için dosya hazır." if usb.get("apk") else
                            "Paket içinde APK yok; GitHub'daki sürümler sayfasından indir.", bool(usb.get("apk"))))
    phone.items.append(Item("Bağlı telefon", ", ".join(s["name"] for s in sessions) + " bağlı." if sessions else
                            "Henüz bağlı telefon yok. Telefonda Talk To Linux'u açınca bu bilgisayar listede görünür.",
                            bool(sessions)))
    out.append(phone)

    u = Step("usb", "USB kablosu", "En hızlı ve en kolay yol. Telefonda USB hata ayıklama açık olmalı.",
             "media-removable-symbolic")
    u.items.append(Item("adb kurulu", "USB bağlantısı için gereken araç." if usb.get("adb") else
                        "USB bağlantısı için gerekli; “Kur”a basınca bilgisayarın şifresi sorulur.",
                        bool(usb.get("adb")), None if usb.get("adb") else "install_adb", "Kur"))
    u.items.append(Item("USB bağlantısı açık", "Bağlantı sayfasındaki “USB bağlantısı” anahtarı.",
                        bool(status.get("usb")), None if status.get("usb") else "enable_usb", "Aç"))
    if usb.get("adb"):
        u.items.append(_usb_phone(usb))
        for d in ready:
            if d.get("app") is False and usb.get("apk"):
                u.items.append(Item("Telefonda Talk To Linux yok", "Tek tıkla USB'den kurulur ve açılır.", False,
                                    f"install_phone_app:{d['serial']}", "Telefona kur"))
            elif d.get("app"):
                u.items.append(Item("Telefonda Talk To Linux kurulu",
                                    "Telefondaki uygulamada “USB kablosu”nu seç; ilk seferde burada onay çıkar.", True))
    out.append(u)

    w = Step("wifi", "Wi-Fi (kablosuz)", "Kablo olmadan, aynı ağdaki telefon bağlanır. İsteğe bağlı.",
             "network-wireless-symbolic")
    w.items.append(Item("Kablosuz bağlantı açık", "Açıkken bu bilgisayar yerel ağda görünür.",
                        bool(status.get("wireless")), None if status.get("wireless") else "enable_wireless", "Aç",
                        optional=True))
    addrs = status.get("addresses") or []
    w.items.append(Item("Ağ adresi", "Adres: " + ", ".join(f"{a}:{status.get('port')}" for a in addrs) if addrs else
                        "Bilgisayar bir ağa bağlı görünmüyor.", bool(addrs), optional=True))
    if ufw is None:
        ufw = ufw_enabled()
    if ufw:
        w.items.append(Item("Güvenlik duvarı (ufw) açık",
                            f"Telefonun bağlanabilmesi için {status.get('port')}/tcp ve {UDP_PORT}/udp portlarına izin "
                            "verilmeli. “İzin ver” bunu yapar (şifre sorulur). Zaten izin verdiysen geç.",
                            False, "allow_firewall", "İzin ver", optional=True))
    w.items.append(Item("Şifre (isteğe bağlı)", "Şifre koymazsan her yeni telefon için onay penceresi çıkar; "
                        "koyarsan telefon şifreyle bağlanır. Bağlantı sayfasından ayarlanır.", None))
    out.append(w)

    bt = status.get("bt") or {}
    x = Step("ekler", "Bluetooth ve diğerleri", "Hepsi isteğe bağlı.", "applications-system-symbolic")
    x.items.append(Item("Bluetooth", bt.get("message") or "Ağ olmadan bağlanmak için; önce telefonla sistem "
                        "ayarlarından eşleştir.", bool(status.get("bluetooth") and bt.get("available")),
                        None if status.get("bluetooth") else "enable_bluetooth", "Aç", optional=True))
    x.items.append(Item("Telefonun ekranı (scrcpy)", "Telefonun ekranını bu bilgisayarda açıp fare ve klavyeyle "
                        "kullanmak için.", mirror.available(), None if mirror.available() else "install_scrcpy",
                        "Kur", optional=True))
    x.items.append(Item("Oturum açılınca başlat", "Bilgisayar açılınca arka planda hazır bekler; telefon "
                        "kendiliğinden bağlanır.", autostart, None if autostart else "enable_autostart", "Aç",
                        optional=True))
    out.append(x)
    return out
