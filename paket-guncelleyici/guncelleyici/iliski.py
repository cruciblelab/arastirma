""".deb dosyalarıyla ilişki: sağ tık → "Başka uygulamayla aç" listesinde görünmek, istenirse varsayılan olmak.

GNOME o listeyi sistemin dosya türü önbelleğinden (/usr/share/applications/mimeinfo.cache) alır; önbelleği
desktop-file-utils günceller. O paket yoksa ya da önbellek güncellenmediyse uygulama listede hiç çıkmıyordu.
Bu yüzden açılışta bakılır: listede değilse kullanıcının kendi ayarına (~/.config/mimeapps.list, "Added
Associations") ".deb açabilir" diye eklenir. Bu varsayılan uygulamayı değiştirmez; varsayılan yapmak
(çift tıklayınca açılsın) yalnızca kullanıcı düğmeye basınca.
"""

import logging

from gi.repository import Gio, GLib

from . import APP_ID

log = logging.getLogger("guncelleyici.iliski")
TYPES = ("application/vnd.debian.binary-package", "application/x-deb")
DESKTOP_ID = APP_ID + ".desktop"


def app_info():
    try:
        return Gio.DesktopAppInfo.new(DESKTOP_ID)
    except TypeError:  # kurulu değil (kaynaktan çalışıyor)
        return None


def listed(content_type: str = TYPES[0]) -> bool:
    return DESKTOP_ID in [a.get_id() for a in Gio.AppInfo.get_recommended_for_type(content_type)]


def ensure_listed() -> bool:
    """Sağ tık listesinde yoksa ekler; bir şey eklendiyse True."""
    info = app_info()
    if info is None:
        return False
    changed = False
    for t in TYPES:
        if listed(t):
            continue
        # GLib'de açık bir varsayılan yoksa eklenen ilişki çift tıklamayı da bize çevirir: önceki varsayılan
        # (ör. App Center) korunur; varsayılan yalnızca kullanıcı isteyince değişir (make_default).
        before = Gio.AppInfo.get_default_for_type(t, False)
        try:
            info.add_supports_type(t)
            changed = True
            after = Gio.AppInfo.get_default_for_type(t, False)
            if before and before.get_id() != DESKTOP_ID and (not after or after.get_id() != before.get_id()):
                before.set_as_default_for_type(t)
        except GLib.Error as e:
            log.warning("%s için ilişki eklenemedi: %s", t, e.message)
    return changed


def is_default() -> bool:
    d = Gio.AppInfo.get_default_for_type(TYPES[0], False)
    return bool(d and d.get_id() == DESKTOP_ID)


def make_default() -> bool:
    info = app_info()
    if info is None:
        return False
    try:
        for t in TYPES:
            info.set_as_default_for_type(t)
    except GLib.Error as e:
        log.warning("varsayılan yapılamadı: %s", e.message)
        return False
    return True
