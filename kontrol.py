"""
Depo kurallarını denetler (README.md, "Kurallar" bölümü).

    python kontrol.py

Hata varsa çıkış kodu 1. Yalnızca standart kütüphane kullanır.
"""

import re
import sys
from pathlib import Path

KOK = Path(__file__).parent
AD = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SURUM_AD = re.compile(r"^(\d+)-([a-z0-9]+(-[a-z0-9]+)*)$")
ZORUNLU = ["Soru ve kapsam", "Yöntem", "Bulgular", "Sonuçlar", "Sınırlamalar", "Kaynaklar", "En basit özet"]
ETIKET = re.compile(r"\((?:[ABCDV](?:-[ABCDV])?)(?:\s*\+\s*[ABCDV](?:-[ABCDV])?)*\)")
ATLA = {".git", ".github"}

hatalar: list[str] = []


def hata(yer, mesaj):
    hatalar.append(f"{yer}: {mesaj}")


def bolumler(metin):
    """'## Başlık' -> içerik sözlüğü (sıralı)."""
    parcalar = re.split(r"^## +(.+?)\s*$", metin, flags=re.M)
    return {parcalar[i].strip(): parcalar[i + 1] for i in range(1, len(parcalar), 2)}


def surum_denetle(yol: Path, n: int):
    rd = yol / "README.md"
    if not rd.exists():
        hata(yol, "README.md yok")
        return
    metin = rd.read_text(encoding="utf-8")
    b = bolumler(metin)
    basliklar = list(b)
    gerekli = ZORUNLU + (["Önceki sürümden değişenler"] if n >= 2 else [])
    for z in gerekli:
        if z not in b:
            hata(rd, f"zorunlu bölüm eksik: '## {z}'")
    if basliklar and basliklar[-1] != "En basit özet":
        hata(rd, f"son bölüm 'En basit özet' olmalı (şu an: '{basliklar[-1]}')")
    if "**Sürüm:**" not in metin:
        hata(rd, "'**Sürüm:**' satırı yok")
    if "Kanıt seviyeleri" not in metin:
        hata(rd, "kanıt seviyeleri tablosu yok")
    if "tıbbi tavsiye değil" not in metin.lower():
        hata(rd, "'tıbbi tavsiye değildir' uyarısı yok (sağlık konusu değilse bu kuralı README'de muaf tut)")

    sonuc = b.get("Sonuçlar", "")
    maddeler = [s for s in sonuc.splitlines() if re.match(r"^\d+\.\s", s)]
    if "Sonuçlar" in b and not maddeler:
        hata(rd, "Sonuçlar bölümünde numaralı madde yok")
    for m in maddeler:
        if not ETIKET.search(m):
            hata(rd, f"kanıt etiketi olmayan sonuç: '{m[:70]}...'")
    if "[doğrulanmadı]" in sonuc:
        hata(rd, "Sonuçlar bölümü doğrulanmamış kaynağa dayanıyor")

    kay = b.get("Kaynaklar", "")
    if "Kaynaklar" in b and not re.search(r"\]\(https?://", kay):
        hata(rd, "Kaynaklar bölümünde bağlantı yok")

    ozet = b.get("En basit özet", "")
    if "En basit özet" in b and len([s for s in ozet.splitlines() if s.strip().startswith("- ")]) < 3:
        hata(rd, "En basit özet en az 3 madde olmalı")

    for alt in ("analiz", "simulasyon"):
        a = yol / alt
        if a.is_dir():
            for dosya in ("requirements.txt", "calistir.py"):
                if not (a / dosya).exists():
                    hata(a, f"{dosya} yok")

    # Göreli bağlantılar (resimler dahil) gerçekten var mı?
    for hedef in re.findall(r"\]\((?!https?://|#)([^)\s]+)\)", metin):
        if not (yol / hedef).exists():
            hata(rd, f"kırık göreli bağlantı: {hedef}")


PLAN_BOLUMLERI = ["Simülasyon kuralları", "Ön kayıtlı testler", "Plandan sapmalar"]


def taslak_mi(yol: Path) -> bool:
    rd = yol / "README.md"
    return rd.exists() and "**Durum:** taslak" in rd.read_text(encoding="utf-8")


def plan_denetle(yol: Path):
    """Simülasyon klasörü varsa önceden kayıtlı plan zorunlu."""
    sim = yol / "simulasyon"
    if not sim.is_dir():
        return
    plan = sim / "PLAN.md"
    if not plan.exists():
        hata(sim, "PLAN.md yok (simülasyon önceden kayıtlı plan olmadan yazılamaz)")
        return
    metin = plan.read_text(encoding="utf-8")
    for b in PLAN_BOLUMLERI:
        if not re.search(rf"^## +(\d+\. +)?{re.escape(b)}", metin, flags=re.M):
            hata(plan, f"plan bölümü eksik: '{b}'")


def konu_denetle(konu: Path):
    if not AD.match(konu.name):
        hata(konu, "klasör adı küçük harf/rakam/tire olmalı")
    if not (konu / "README.md").exists():
        hata(konu, "konu dizini README.md yok")
        return
    dizin = (konu / "README.md").read_text(encoding="utf-8")
    surumler = {}
    for alt in konu.iterdir():
        if alt.is_dir():
            m = SURUM_AD.match(alt.name)
            if not m:
                hata(alt, "sürüm klasörü '<n>-<ad>' biçiminde olmalı")
                continue
            surumler[int(m.group(1))] = alt
    if not surumler:
        hata(konu, "hiç sürüm yok")
        return
    if sorted(surumler) != list(range(1, max(surumler) + 1)):
        hata(konu, f"sürüm numaraları boşluksuz olmalı: {sorted(surumler)}")
    taslaklar = [n for n, y in surumler.items() if taslak_mi(y)]
    if taslaklar and max(taslaklar) != max(surumler):
        hata(konu, "taslak yalnızca en yüksek numaralı sürüm olabilir")
    if len(taslaklar) > 1:
        hata(konu, "aynı anda birden fazla taslak sürüm olamaz")
    yayinda = [n for n in surumler if n not in taslaklar]
    if not yayinda:
        # Yeni konu: tek sürümü taslak olabilir (ön kayıt için). Yalnızca taslak denetimi.
        if sorted(surumler) == [1] and taslaklar == [1]:
            yol = surumler[1]
            if yol.name not in dizin:
                hata(konu / "README.md", f"sürüm listede yok: {yol.name}")
            if "**Sürüm:**" not in (yol / "README.md").read_text(encoding="utf-8"):
                hata(yol / "README.md", "'**Sürüm:**' satırı yok")
            plan_denetle(yol)
            if konu.name not in (KOK / "README.md").read_text(encoding="utf-8"):
                hata(KOK / "README.md", f"araştırma tabloda yok: {konu.name}")
        else:
            hata(konu, "yayınlanmış (taslak olmayan) sürüm yok")
        return
    guncel = max(yayinda)
    for n, yol in sorted(surumler.items()):
        if yol.name not in dizin:
            hata(konu / "README.md", f"sürüm listede yok: {yol.name}")
        rd = yol / "README.md"
        if not rd.exists():
            hata(yol, "README.md yok")
            continue
        if n in taslaklar:
            if "**Sürüm:**" not in rd.read_text(encoding="utf-8"):
                hata(rd, "'**Sürüm:**' satırı yok")
            plan_denetle(yol)
        elif n == guncel:
            surum_denetle(yol, n)
            plan_denetle(yol)
        elif surumler[guncel].name not in rd.read_text(encoding="utf-8"):
            hata(rd, f"eski sürüm en üstte güncel sürüme ({surumler[guncel].name}) bağlantı vermeli")
    kok_readme = (KOK / "README.md").read_text(encoding="utf-8")
    if konu.name not in kok_readme:
        hata(KOK / "README.md", f"araştırma tabloda yok: {konu.name}")


def main():
    konular = [p for p in KOK.iterdir() if p.is_dir() and p.name not in ATLA and not p.name.startswith(".")]
    for k in sorted(konular):
        konu_denetle(k)
    if hatalar:
        print(f"DENETİM BAŞARISIZ ({len(hatalar)} sorun):")
        for h in hatalar:
            print("  -", h)
        sys.exit(1)
    print(f"Denetim geçti: {len(konular)} araştırma.")


if __name__ == "__main__":
    main()
