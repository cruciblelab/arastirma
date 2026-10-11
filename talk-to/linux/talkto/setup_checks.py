"""Kurulum yardımcısının denetimleri (arayüzden bağımsız, test edilebilir).

Her adım bir başlık, açıklama ve satırlardan oluşur. Satırın durumu True (tamam),
False (yapılmalı) ya da None (yalnızca bilgi); "action" arayüzün çalıştıracağı işin adı.
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import UDP_PORT, mirror
from .usb import XIAOMI, version_tuple

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


XIAOMI_PERMISSIONS = ("Ayarlar → Ek ayarlar → Geliştirici seçenekleri → “USB hata ayıklama (Güvenlik ayarları)”nı aç. "
                      "Xiaomi bunun için telefonda SIM kart takılı olmasını ve Mi hesabına giriş yapılmasını istiyor. "
                      "Kapalıyken bilgisayar telefondaki izinleri veremez; istersen izinleri telefonda elle ver.")
XIAOMI_INSTALL = ("Geliştirici seçenekleri → “USB üzerinden yükle”yi aç (Mi hesabı ister). Kapalıyken bilgisayar "
                  "Talk To Linux'u kuramaz ya da güncelleyemez.")


def app_outdated(d: dict, usb: dict) -> bool:
    """Telefondaki uygulama bu bilgisayardaki APK'dan eski mi?"""
    return bool(d.get("app") and d.get("app_version") and usb.get("apk_version")
                and version_tuple(d["app_version"]) < version_tuple(usb["apk_version"]))


def xiaomi(d: dict) -> bool:
    return (d.get("maker") or "").casefold() in XIAOMI


def _permissions_done(sessions: list[dict]) -> bool:
    phone = next((s.get("phone") or {} for s in sessions if s.get("kind") == "usb"), {})
    return phone.get("notif_access") is True and phone.get("listener") is not False


def _phone_permissions(d: dict, sessions: list[dict]) -> Item:
    """Bildirim erişimi, pil kısıtlaması gibi telefon ayarları: bilgisayardan tek tıkla."""
    if d.get("setting_up"):
        return Item("Telefon ayarlanıyor…", "Telefonda bir şey yapman gerekmiyor.", None)
    done = _permissions_done(sessions)
    if not done and xiaomi(d) and d.get("xiaomi_permissions") is False:
        return Item("Telefondaki izinler", "Önce yukarıdaki Xiaomi ayarını aç; sonra “Kontrol et”.", False)
    text = ("Bildirim erişimi açık." if done else
            "Bildirim erişimi, pil kısıtlaması, bildirim ve Bluetooth izni telefonun ayar menülerinde dağınık. "
            "“Telefonu ayarla” hepsini USB'den bir kerede yapar; telefonda bir şey seçmen gerekmez.")
    return Item("Telefondaki izinler", text, done, None if done else f"phone_setup:{d['serial']}", "Telefonu ayarla")


def steps(status: dict, usb: dict, *, autostart: bool = False, ufw: bool | None = None,
          firewall_port: int | None = None, simple: bool = False) -> list[Step]:
    """firewall_port: güvenlik duvarına bu uygulamadan izin eklenen port (yoksa None).

    simple: basit mod. Wi-Fi öne geçer (kablo ve geliştirici ayarı gerekmez), USB isteğe bağlı olur.
    """
    sessions = status.get("sessions", [])
    ready = [d for d in usb.get("devices", []) if d.get("state") == "device"]
    if simple:
        welcome = ("Telefon bildirimleri bu bilgisayarda görünür, telefonda çalan müzik buradan kontrol edilir, "
                   "kaybolan telefon tek tıkla çaldırılır. Dosya, komut gibi diğer özellikler gizli; istediğinde "
                   "Menü → Tercihler → Özellikler'den eklenir. Birkaç adımda hazırlayalım.")
    else:
        welcome = ("Bu bilgisayarı Android telefonuna bağlar: telefon bildirimleri burada görünür, müzik iki yönden "
                   "kontrol edilir, dosya ve pano gider gelir, telefon bu bilgisayara komut verir. Birkaç adımda "
                   "hazırlayalım; her adımda “Kontrol et” ile durumu yeniden okuyabilirsin. İstediğin zaman "
                   "menüdeki “Kurulum yardımcısı”ndan geri dönebilirsin.")
    out = [Step("hos-geldin", "Talk To Android'e hoş geldin", welcome, "lab.crucible.TalkToAndroid")]

    phone = Step("telefon", "Telefondaki uygulama",
                 "Telefona Talk To Linux uygulaması kurulmalı. En kolayı: telefonu USB ile takıp USB adımından "
                 "tek tıkla kurmak (Play Protect bu yolla engellemez).", "phone-symbolic")
    phone.items.append(Item("Telefon uygulaması bu pakette", "Kurulum için dosya hazır." if usb.get("apk") else
                            "Paket içinde APK yok; GitHub'daki sürümler sayfasından indir.", bool(usb.get("apk"))))
    phone.items.append(Item("Bağlı telefon", ", ".join(s["name"] for s in sessions) + " bağlı." if sessions else
                            "Henüz bağlı telefon yok. Telefonda Talk To Linux'u açınca bu bilgisayar listede görünür.",
                            bool(sessions)))
    out.append(phone)

    if simple:
        u = Step("usb", "USB kablosu (isteğe bağlı)",
                 "Wi-Fi yetiyorsa geçebilirsin. Kablo, telefona uygulamayı kurmak ve telefondaki izinleri tek tıkla "
                 "ayarlamak için işe yarar; telefonda USB hata ayıklama açık olmalı.", "media-removable-symbolic")
    else:
        u = Step("usb", "USB kablosu", "En hızlı ve en kolay yol. Telefonda USB hata ayıklama açık olmalı.",
                 "media-removable-symbolic")
    u.items.append(Item("adb kurulu", "USB bağlantısı için gereken araç." if usb.get("adb") else
                        "USB bağlantısı için gerekli; “Kur”a basınca bilgisayarın şifresi sorulur.",
                        bool(usb.get("adb")), None if usb.get("adb") else "install_adb", "Kur"))
    u.items.append(Item("USB bağlantısı açık", "Menü → Tercihler'deki “USB bağlantısı” anahtarı.",
                        bool(status.get("usb")), None if status.get("usb") else "enable_usb", "Aç"))
    if usb.get("adb"):
        u.items.append(_usb_phone(usb))
        if not ready and not usb.get("unseen") and usb.get("usb_devices"):
            # Telefon hiç tanınmadıysa bilgisayarın ne gördüğü (kablo mu, telefon mu, mod mu: ayırt etmek için).
            u.items.append(Item("Bu bilgisayarın gördüğü USB aygıtları", ", ".join(usb["usb_devices"][:8]), None))
        for d in ready:
            if d.get("installing"):
                u.items.append(Item("Telefona kuruluyor…", "Telefonda bir soru çıkarsa onayla; bitince uygulama açılır.",
                                    None))
                continue
            needs_install = (d.get("app") is False or app_outdated(d, usb)) and usb.get("apk")
            if xiaomi(d) and needs_install and d.get("xiaomi_install") is False:
                u.items.append(Item("Xiaomi: “USB üzerinden yükle” kapalı", XIAOMI_INSTALL, False))
            if xiaomi(d) and d.get("xiaomi_permissions") is False and not _permissions_done(sessions):
                u.items.append(Item("Xiaomi: “USB hata ayıklama (Güvenlik ayarları)” kapalı", XIAOMI_PERMISSIONS,
                                    False))
            if d.get("app") is False and usb.get("apk"):
                u.items.append(Item("Telefonda Talk To Linux yok", "Tek tıkla USB'den kurulur ve açılır.", False,
                                    f"install_phone_app:{d['serial']}", "Telefona kur"))
            elif app_outdated(d, usb):
                u.items.append(Item(f"Telefondaki Talk To Linux eski ({d['app_version']})",
                                    f"Bu bilgisayardaki sürüm {usb['apk_version']}. Tek tıkla USB'den güncellenir; "
                                    "eşleşme ve ayarlar korunur.", False, f"install_phone_app:{d['serial']}",
                                    "Güncelle"))
                u.items.append(_phone_permissions(d, sessions))
            elif d.get("app"):
                version = f" ({d['app_version']})" if d.get("app_version") else ""
                u.items.append(Item(f"Telefonda Talk To Linux kurulu{version}",
                                    "Telefondaki uygulamada “USB kablosu”nu seç; ilk seferde burada onay çıkar.", True))
                u.items.append(_phone_permissions(d, sessions))
    if simple:
        for i in u.items:
            i.optional = True

    w = Step("wifi", "Wi-Fi (kablosuz)",
             "En kolay yol: kablo ve geliştirici ayarı gerekmez. Telefon ve bilgisayar aynı Wi-Fi ağında olmalı; "
             "ilk bağlantıda iki ekrandaki numarayı karşılaştırırsın." if simple else
             "Kablo olmadan, aynı ağdaki telefon bağlanır. İsteğe bağlı.", "network-wireless-symbolic")
    w.items.append(Item("Kablosuz bağlantı açık", "Açıkken bu bilgisayar yerel ağda görünür.",
                        bool(status.get("wireless")), None if status.get("wireless") else "enable_wireless", "Aç",
                        optional=not simple))
    addrs = status.get("addresses") or []
    w.items.append(Item("Ağ adresi", "Adres: " + ", ".join(f"{a}:{status.get('port')}" for a in addrs) if addrs else
                        "Bilgisayar bir ağa bağlı görünmüyor.", bool(addrs), optional=True))
    if ufw is None:
        ufw = ufw_enabled()
    if ufw and firewall_port == status.get("port"):
        w.items.append(Item("Güvenlik duvarı (ufw)", f"{status.get('port')}/tcp ve {UDP_PORT}/udp için izin eklendi.",
                            True, optional=True))
    elif ufw:
        w.items.append(Item("Güvenlik duvarı (ufw) açık",
                            f"Telefonun bağlanabilmesi için {status.get('port')}/tcp ve {UDP_PORT}/udp portlarına izin "
                            "verilmeli. “İzin ver” bunu yapar (şifre sorulur). Zaten izin verdiysen geç.",
                            False, "allow_firewall", "İzin ver", optional=True))
    w.items.append(Item("Şifre (isteğe bağlı)", "Şifre koymazsan her yeni telefon için onay penceresi çıkar; "
                        "koyarsan telefon şifreyle bağlanır. Menü → Tercihler'den ayarlanır.", None))
    out += [w, u] if simple else [u, w]

    bt = status.get("bt") or {}
    x = Step("ekler", "Bluetooth ve diğerleri", "Hepsi isteğe bağlı.", "applications-system-symbolic")
    x.items.append(Item("Bluetooth", bt.get("message") or "Ağ olmadan bağlanmak için; önce telefonla sistem "
                        "ayarlarından eşleştir.", bool(status.get("bluetooth") and bt.get("available")),
                        None if status.get("bluetooth") else "enable_bluetooth", "Aç", optional=True))
    old = mirror.outdated_system()
    scr_text = "Telefonun ekranını bu bilgisayarda açıp fare ve klavyeyle kullanmak için."
    if old and not mirror.available():
        scr_text = (f"Sistemdeki scrcpy {'.'.join(map(str, old))} yeni Android sürümlerinde açılmıyor. "
                    + (f"Resmi {mirror.SCRCPY_VERSION} sürümü indirilir (şifre gerekmez)." if mirror.can_download()
                       else "Daha yeni bir sürüm kur."))
    x.items.append(Item("Telefonun ekranı (scrcpy)", scr_text, mirror.available(),
                        None if mirror.available() else "install_scrcpy",
                        "İndir" if mirror.can_download() else "Kur", optional=True))
    x.items.append(Item("Oturum açılınca başlat", "Bilgisayar açılınca arka planda hazır bekler; telefon "
                        "kendiliğinden bağlanır.", autostart, None if autostart else "enable_autostart", "Aç",
                        optional=True))
    out.append(x)
    return out
