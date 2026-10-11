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


def _usb_phone(usb: dict, optional: bool) -> Item:
    """USB'de hazır telefon yokken neden: onay, izin, hata ayıklama kapalı ya da hiç takılı değil."""
    devices = usb.get("devices", [])
    if any(d.get("state") == "unauthorized" for d in devices):
        return Item("Telefon onay bekliyor", "Telefonda çıkan “USB hata ayıklamaya izin ver” sorusunu onayla "
                    "(“Bu bilgisayara her zaman izin ver”i işaretle).", False, optional=optional)
    if any(d.get("state") == "no" for d in devices):
        return Item("Bilgisayarın telefona erişim izni yok", "Kabloyu çıkarıp tak; düzelmezse "
                    "“android-sdk-platform-tools-common” paketini kur.", False, optional=optional)
    if any(d.get("state") == "offline" for d in devices):
        return Item("Telefon yanıt vermiyor", "Kabloyu çıkarıp tekrar tak.", False, optional=optional)
    if usb.get("unseen"):
        name = usb["unseen"][0].get("name") or "Telefon"
        return Item(f"{name} takılı ama USB hata ayıklama kapalı",
                    "Telefonda: Ayarlar → Telefon hakkında → “Yapım numarası”na 7 kez dokun; sonra Geliştirici "
                    "seçenekleri → “USB hata ayıklama”yı aç. Açınca burası kendiliğinden güncellenir.", False,
                    optional=optional)
    return Item("USB ile: telefon takılı değil", "Telefonu USB kablosuyla tak (telefonla gelen kablo; yalnızca şarj "
                "eden kablolar veri taşımaz). Takınca burası kendiliğinden güncellenir.", None)


XIAOMI_PERMISSIONS = ("Ayarlar → Ek ayarlar → Geliştirici seçenekleri → “USB hata ayıklama (Güvenlik ayarları)”nı aç. "
                      "Xiaomi bunun için telefonda SIM kart takılı olmasını ve Mi hesabına giriş yapılmasını istiyor. "
                      "Kapalıyken bilgisayar telefondaki izinleri veremez; istersen izinleri telefonda elle ver.")
XIAOMI_INSTALL = ("Geliştirici seçenekleri → “USB üzerinden yükle”yi aç (Mi hesabı ister). Kapalıyken bilgisayar "
                  "Talk To Linux'u kuramaz ya da güncelleyemez.")
PERM_NAMES = {"listener": "bildirim erişimi", "battery": "pil kısıtlamasının kaldırılması", "post": "bildirim izni"}


def app_outdated(d: dict, usb: dict) -> bool:
    """Telefondaki uygulama bu bilgisayardaki APK'dan eski mi?"""
    return bool(d.get("app") and d.get("app_version") and usb.get("apk_version")
                and version_tuple(d["app_version"]) < version_tuple(usb["apk_version"]))


def xiaomi(d: dict) -> bool:
    return (d.get("maker") or "").casefold() in XIAOMI


def display_name(d: dict) -> str:
    return d.get("name") or d.get("model") or d["serial"]


def session_of(d: dict, sessions: list[dict]) -> dict | None:
    """USB'deki telefonun bağlı oturumu (bağlantı USB'den ya da Wi-Fi'den olabilir)."""
    return next((s for s in sessions if s.get("adb_serial") == d["serial"]), None)


def perms_missing(d: dict | None, session: dict | None) -> list[str] | None:
    """Telefondaki izinlerden eksik olanlar; telefonda elle verilenler de sayılır (tekrar istenmez).

    Kaynak: adb'nin okuduğu ayarlar (bağlantı gerekmez) ya da bağlı telefonun bildirdiği durum.
    None: bilinmiyor (ne USB'den okunabildi ne telefon bağlı).
    """
    perms = dict((d or {}).get("perms") or {})
    phone = (session or {}).get("phone") or {}
    if phone.get("flavor") == "hafif":
        perms["listener"] = None  # hafif sürümde bildirim erişimi yok
    elif phone.get("notif_access") is not None:
        perms["listener"] = phone["notif_access"]  # telefonun kendi söylediği daha güncel
    known = [k for k in PERM_NAMES if perms.get(k) is not None]
    if not known:
        return None
    return [PERM_NAMES[k] for k in PERM_NAMES if perms.get(k) is False]


def _phone_permissions(d: dict | None, session: dict | None) -> Item | None:
    """Bildirim erişimi, pil kısıtlaması, bildirim izni: eksik varsa USB'den tek tıkla."""
    if d and d.get("setting_up"):
        return Item("Telefon ayarlanıyor…", "Telefonda bir şey yapman gerekmiyor.", None)
    missing = perms_missing(d, session)
    if missing is None:
        return None
    if not missing:
        return Item("Telefondaki izinler tamam", "Bildirim erişimi ve diğer izinler verilmiş.", True)
    text = "Eksik: " + ", ".join(missing) + "."
    if d is None:
        return Item("Telefondaki izinler", text + " Telefonda Talk To Linux → İzinler ve yetkiler'den ver; ya da "
                    "telefonu USB ile takınca buradan tek tıkla tamamlanır.", False)
    if xiaomi(d) and d.get("xiaomi_permissions") is False:
        return Item("Telefondaki izinler", text + " Bilgisayarın verebilmesi için yukarıdaki Xiaomi ayarını aç ya da "
                    "telefonda Talk To Linux → İzinler ve yetkiler'den kendin ver.", False)
    return Item("Telefondaki izinler", text + " “Tamamla” eksikleri USB'den bir kerede verir; telefonda menü "
                "aramana gerek yok.", False, f"phone_setup:{d['serial']}", "Tamamla")


def _usb_device_items(d: dict, usb: dict, sessions: list[dict]) -> list[Item]:
    name, serial = display_name(d), d["serial"]
    session = session_of(d, sessions)
    if d.get("installing"):
        return [Item(f"{name}: Talk To Linux kuruluyor…", "Telefonda bir soru çıkarsa onayla; bitince kendiliğinden "
                     "açılır ve bağlanır.", None)]
    items = []
    needs_install = (d.get("app") is False or app_outdated(d, usb)) and usb.get("apk")
    if xiaomi(d) and needs_install and d.get("xiaomi_install") is False:
        items.append(Item("Xiaomi: “USB üzerinden yükle” kapalı", XIAOMI_INSTALL, False))
    if d.get("app") is False and usb.get("apk"):
        items.append(Item(f"{name}: Talk To Linux yok", "Tek tıkla USB'den kurulur, açılır ve bağlanır.", False,
                          f"install_phone_app:{serial}", "Kur ve bağlan"))
        return items
    if d.get("app") is False:
        items.append(Item(f"{name}: Talk To Linux yok", "Bu pakette telefon uygulaması yok; GitHub'daki sürümler "
                          "sayfasından indirip telefona kur.", False))
        return items
    if app_outdated(d, usb):
        items.append(Item(f"{name}: Talk To Linux eski ({d['app_version']})",
                          f"Bu bilgisayardaki sürüm {usb['apk_version']}. Tek tıkla USB'den güncellenir ve bağlanır; "
                          "eşleşme ve ayarlar korunur.", False, f"install_phone_app:{serial}", "Güncelle"))
    elif session:
        via = {"usb": "USB", "wifi": "Wi-Fi", "bluetooth": "Bluetooth"}.get(session.get("kind"), session.get("kind"))
        items.append(Item(f"{session.get('name') or name} bağlı ({via})",
                          "Bundan sonra kablo takılınca ya da aynı ağdayken kendiliğinden bağlanır.", True))
    elif d.get("app"):
        items.append(Item(f"{name} USB'de, bağlanmaya hazır",
                          "“Bağlan”a bas: telefonda Talk To Linux açılır ve bağlanır, telefonda bir şey seçmen "
                          "gerekmez. İlk seferde burada iki ekrandaki numarayı karşılaştırırsın.", False,
                          f"connect_usb:{serial}", "Bağlan"))
    missing = perms_missing(d, session)
    if xiaomi(d) and d.get("xiaomi_permissions") is False and missing:
        items.append(Item("Xiaomi: “USB hata ayıklama (Güvenlik ayarları)” kapalı", XIAOMI_PERMISSIONS, False,
                          optional=True))
    perms = _phone_permissions(d, session)
    if perms:
        items.append(perms)
    return items


def _phone_step(status: dict, usb: dict, simple: bool) -> Step:
    """Telefonu bağla: USB'deki telefona tek tık ("Bağlan"), yoksa Wi-Fi; bağlanınca izinler."""
    sessions = status.get("sessions", [])
    ready = [d for d in usb.get("devices", []) if d.get("state") == "device"]
    host = status.get("name") or "bu bilgisayar"
    connected = bool(sessions)
    st = Step("telefon", "Telefonu bağla",
              "Telefon bağlı. Bundan sonra kendiliğinden bağlanır." if connected else
              "Telefon USB kablosuyla takılıysa “Bağlan” yeter, telefonda bir şey seçmen gerekmez. Kablo yoksa "
              "aynı Wi-Fi ağında telefondan bağlanılır.", "phone-symbolic")
    if not usb.get("apk"):
        st.items.append(Item("Telefon uygulaması bu pakette yok", "Talk To Linux'u GitHub'daki sürümler sayfasından "
                             "indirip telefona kur.", False, optional=True))
    usb_optional = simple or connected
    if not usb.get("adb"):
        st.items.append(Item("USB için adb gerekli", "Telefonu kabloyla bağlamak ve uygulamayı tek tıkla kurmak "
                             "için; “Kur”a basınca bilgisayarın şifresi sorulur.", False, "install_adb", "Kur",
                             optional=usb_optional))
    elif not status.get("usb"):
        st.items.append(Item("USB bağlantısı kapalı", "Menü → Tercihler'deki “USB bağlantısı” anahtarı.", False,
                             "enable_usb", "Aç", optional=usb_optional))
    elif ready:
        for d in ready:
            st.items += _usb_device_items(d, usb, sessions)
    elif not connected:
        st.items.append(_usb_phone(usb, usb_optional))
        if not usb.get("unseen") and usb.get("usb_devices") and usb.get("devices") == []:
            # Telefon hiç tanınmadıysa bilgisayarın ne gördüğü (kablo mu, telefon mu, mod mu: ayırt etmek için).
            st.items.append(Item("Bu bilgisayarın gördüğü USB aygıtları", ", ".join(usb["usb_devices"][:8]), None))
    # USB'de olmayan bağlı telefonlar (Wi-Fi, Bluetooth): bağlantı ve izinleri telefonun bildirdiğinden.
    on_usb = {d["serial"] for d in ready}
    for s in sessions:
        if s.get("adb_serial") in on_usb:
            continue
        via = {"usb": "USB", "wifi": "Wi-Fi", "bluetooth": "Bluetooth"}.get(s.get("kind"), s.get("kind"))
        st.items.append(Item(f"{s.get('name')} bağlı ({via})", "Bundan sonra kendiliğinden bağlanır.", True))
        perms = _phone_permissions(None, s)
        if perms:
            st.items.append(perms)
    if not connected:
        if status.get("wireless"):
            st.items.append(Item("Wi-Fi ile", f"Telefon aynı Wi-Fi ağındaysa: telefonda Talk To Linux'u aç, listede "
                                 f"“{host}”a dokun.", None))
        else:
            st.items.append(Item("Wi-Fi ile bağlanmak için kablosuz bağlantıyı aç", "Açınca bu bilgisayar yerel ağda "
                                 "görünür.", False, "enable_wireless", "Aç", optional=not simple))
    return st


def steps(status: dict, usb: dict, *, autostart: bool = False, ufw: bool | None = None,
          firewall_port: int | None = None, simple: bool = False) -> list[Step]:
    """firewall_port: güvenlik duvarına bu uygulamadan izin eklenen port (yoksa None).

    simple: basit mod. Wi-Fi zorunlu, USB isteğe bağlı sayılır (kablo ve geliştirici ayarı gerekmez).
    """
    if simple:
        welcome = ("Telefon bildirimleri bu bilgisayarda görünür, telefonda çalan müzik buradan kontrol edilir, "
                   "kaybolan telefon tek tıkla çaldırılır. Dosya, komut gibi diğer özellikler gizli; istediğinde "
                   "Menü → Tercihler → Özellikler'den eklenir. Birkaç adımda hazırlayalım.")
    else:
        welcome = ("Bu bilgisayarı Android telefonuna bağlar: telefon bildirimleri burada görünür, müzik iki yönden "
                   "kontrol edilir, dosya ve pano gider gelir, telefon bu bilgisayara komut verir. Birkaç adımda "
                   "hazırlayalım; adımlar telefonun durumuna göre kendiliğinden güncellenir. İstediğin zaman "
                   "menüdeki “Kurulum yardımcısı”ndan geri dönebilirsin.")
    out = [Step("hos-geldin", "Talk To Android'e hoş geldin", welcome, "lab.crucible.TalkToAndroid"),
           _phone_step(status, usb, simple)]

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
    out.append(w)

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
