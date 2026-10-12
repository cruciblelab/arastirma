"""apt ve dpkg hatalarını anlaşılır Türkçeye çevirir: ne oldu, ne yapmalı, varsa tek tıkla onarım.

Terminaldeki "E: Sub-process /usr/bin/dpkg returned an error code (1)" gibi satırlar kullanıcıya bir şey
söylemez. Burada çıktıdaki bilinen kalıplar aranır (apt İngilizce ya da Türkçe konuşabilir) ve en anlamlı
açıklama seçilir. Ham çıktı yine "Ayrıntılar"da durur; açıklama onun yerine değil, önüne geçer.

Onarımlar (fix):
  "yarim"      → dpkg --configure -a   (yarıda kalmış kurulumu tamamlar)
  "bagimlilik" → apt-get -f install     (eksik/bozuk bağımlılıkları düzeltir)
"""

import re
from dataclasses import dataclass

from .dil import _t


@dataclass
class Aciklama:
    title: str
    text: str
    fix: str | None = None  # "yarim" ya da "bagimlilik"
    detail: str = ""  # ham çıktının sonu (Ayrıntılar)

    @property
    def fix_label(self) -> str | None:
        return {"yarim": _t("Yarım kalan işi tamamla"), "bagimlilik": _t("Bağımlılıkları onar")}.get(self.fix or "")


def _find(pattern, text):
    return re.search(pattern, text, re.I | re.S)


def explain(lines: list[str], code: int | None = None, op: str = "kurulum") -> Aciklama:
    """lines: apt/dpkg çıktısı (hata satırları ya da tamamı); code: çıkış kodu; op: "kurulum" / "kaldırma"."""
    text = "\n".join(lines)
    detail = "\n".join(lines[-40:]).strip()

    def a(title, body, fix=None):
        return Aciklama(title, body, fix, detail)

    if code == 126:
        return a(_t("Şifre penceresi kapatıldı"), _t("Hiçbir şey değişmedi. Yeniden denemek için düğmeye tekrar bas."))
    if code == 127:
        return a(_t("Yönetici izni verilmedi"), _t("Şifre doğrulanamadı ya da bu kullanıcının yönetici yetkisi yok; "
                                                  "hiçbir şey değişmedi."))
    if _find(r"dpkg --configure -a", text) and _find(r"interrupted|kesil|yarıda", text):
        return a(_t("Önceki bir kurulum yarıda kalmış"),
                 _t("Bir kurulum ya da güncelleme kesilmiş (bilgisayar kapanmış, pencere kapatılmış…). Paket sistemi "
                    "bu düzelmeden başka bir şey kurmaz ya da kaldırmaz. Aşağıdaki düğme yarım kalan işi tamamlar; "
                    "sonra yeniden dene."), "yarim")
    if m := (_find(r"trying to overwrite '([^']+)', which is also in package (\S+)", text)
             or _find(r"'([^']+)'[^\n]*üzerine yaz[^\n]*?(\S+) paket", text)):
        path, other = m.group(1), m.group(2).rstrip(",")
        return a(_t("Dosya çakışması"),
                 _t("Bu paket {path} dosyasını kurmak istiyor ama o dosya zaten kurulu “{other}” paketine ait. "
                    "İki paket aynı şeyi kuruyor olabilir (aynı uygulamanın başka bir sürümü ya da adı değişmiş "
                    "hâli). Önce “{other}” paketini kaldırıp yeniden dene.").format(path=path, other=other))
    if _find(r"Removing essential system-critical packages|potentially harmful|essential package|"
             r"temel sistem paket|zararlı olabilecek", text):
        return a(_t("Sistemin temel bir paketi"),
                 _t("Bu paket bilgisayarın çalışması için gerekli; apt güvenlik için kaldırmayı reddetti. "
                    "Kaldırılmamalı."))
    if _find(r"is not installed, so not removed|kurulu değil.{0,40}kaldırılmadı", text):
        return a(_t("Zaten kurulu değil"), _t("Bu paket şu an kurulu değil; kaldırılacak bir şey yok."))
    if m := (_find(r"Depends: (\S+)[^\n]*?but (?:it is not installable|it is not going to be installed|"
                   r"[\w.:~+-]+ is to be installed)", text)
             or _find(r"Bağımlı: (\S+)[^\n]*?ama", text)):
        dep = m.group(1)
        return a(_t("Gerekli bir paket bulunamadı"),
                 _t("Bu paket “{dep}” paketini istiyor ama bu bilgisayarın paket kaynaklarında uygun sürümü yok. "
                    "Paket başka bir Ubuntu/Debian sürümü için hazırlanmış olabilir ya da paket listeleri eski: "
                    "Yazılım Güncelleştirici'yi çalıştırıp yeniden dene. Olmazsa paketin bu Ubuntu sürümüne uygun "
                    "hâlini yayıncıdan iste.").format(dep=dep))
    if _find(r"unmet dependencies|Karşılanmamış bağımlılık|held broken packages|tutulan bozuk paket|"
             r"--fix-broken|-f install|dependency problems|bağımlılık sorunları", text):
        return a(_t("Paket sisteminde bozuk bağımlılıklar var"),
                 _t("Daha önceki bir kurulumdan kalan eksik ya da çakışan paketler var; apt bunlar düzelmeden yeni "
                    "bir şey yapmıyor. Aşağıdaki düğme eksikleri kurar ya da tamamlar (apt-get -f install); sonra "
                    "yeniden dene."), "bagimlilik")
    if _find(r"enough free space|No space left on device|yeterli boş alan|aygıtta yer kalmadı", text):
        return a(_t("Diskte yer kalmadı"),
                 _t("İşlem için yeterli boş yer yok. Gereksiz dosyaları sil ya da terminalde “sudo apt clean” ile "
                    "apt'nin indirdiği eski paketleri temizle, sonra yeniden dene."))
    if _find(r"(?:pre|post)-(?:installation|removal) script[^\n]*returned error exit status|"
             r"subprocess[^\n]*returned error exit status|betiği[^\n]*hata çıkış|alt süreci[^\n]*hata", text):
        return a(_t("Paketin kendi betiği hata verdi"),
                 ({"kaldırma": _t("Paketin kaldırma sırasında çalışan betiği hata verdi: bu, paketi hazırlayanın "
                                  "sorunu.")}.get(op) or
                  _t("Paketin kurulum sırasında çalışan betiği hata verdi: bu, paketi hazırlayanın sorunu.")) + " " +
                 _t("Aşağıdaki ayrıntıları yayıncıya ilet. Paket sistemi yarım kalmış olabilir; düğme tamamlamayı "
                    "dener."), "yarim")
    if _find(r"Temporary failure resolving|Could not resolve|Failed to fetch|Unable to fetch|"
             r"Geçici olarak çözülemedi|alınamadı|çözümlenemedi", text):
        return a(_t("İnternete ulaşılamadı"),
                 _t("Paketin istediği ek paketler indirilemedi. İnternet bağlantısını kontrol edip yeniden dene."))
    if m := _find(r"architecture \((\S+)\) does not match system \((\S+)\)", text):
        return a(_t("Bu bilgisayara uygun değil"),
                 _t("Paket {arch} işlemciler için, bu bilgisayar {mine}. Yayıncıdan doğru sürümü indir.").format(
                     arch=m.group(1), mine=m.group(2)))
    if _find(r"Unable to locate package|paket[^\n]*bulunamadı", text):
        return a(_t("Paket bulunamadı"), _t("apt bu adla bir paket bilmiyor."))
    if _find(r"Could not get lock|kilit[^\n]*alınamadı", text):
        return a(_t("Paket sistemi meşgul kaldı"),
                 _t("Başka bir paket işlemi kilidi uzun süre bırakmadı (otomatik güncelleme ya da açık bir Yazılım "
                    "penceresi). Biraz sonra yeniden dene."))
    last = next((ln[3:].strip() for ln in reversed(lines) if ln.startswith("E: ")), None)
    if last is None:
        last = next((ln.strip() for ln in reversed(lines) if ln.strip()), "")
    title = {"kurulum": _t("Kurulmadı"), "kaldırma": _t("Kaldırılmadı")}.get(op, _t("Olmadı"))
    return a(title, (last or _t("apt {code} koduyla bitti.").format(code=code)) +
             (" " + _t("(çıkış kodu {code})").format(code=code) if code not in (None, 0, 1) else ""))
