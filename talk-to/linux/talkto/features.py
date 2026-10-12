"""Basit mod: arayüzde yalnızca temel özellikler görünür, gerisi Tercihler'den tek tek eklenir.

Temel olanlar: telefon bildirimleri, çalan müzik (mini oynatıcı ve şarkı bildirimi) ve telefonu bul.
Bu yalnızca görünüm ayarıdır; bir telefonun bu bilgisayarda neye izinli olduğunu profil belirler.
Hafif APK'dan farklıdır: hafif sürümde bildirim özelliği telefonda hiç yoktur, basit mod ise yalnızca
ekranı sadeleştirir.
"""

CORE = ("notifications", "media", "find")

# anahtar: (başlık, açıklama)
EXTRAS = {
    "files": ("Dosya ve pano", "Dosyalar sayfası; telefona dosya ve pano gönderme düğmeleri"),
    "commands": ("Bilgisayar komutları", "Telefondan kilitleme, ekran görüntüsü, özel komutlar (Tercihler → Araçlar)"),
    "mirror": ("Telefonun ekranı", "Telefonun ekranını bu bilgisayarda açıp fare ve klavyeyle kullanma (scrcpy)"),
    "profiles": ("Profiller", "Birden çok telefona ayrı izinler (ör. misafir telefonu)"),
}


def enabled(config) -> set[str]:
    """Arayüzde görünecek özellikler."""
    if not config["simple_mode"]:
        return set(CORE) | set(EXTRAS)
    return set(CORE) | {k for k in config["extras"] if k in EXTRAS}


def shown(config, key: str) -> bool:
    return key in enabled(config)
