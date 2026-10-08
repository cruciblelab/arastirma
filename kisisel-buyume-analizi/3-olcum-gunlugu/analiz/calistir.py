"""
Ölçüm günlüğünden gelen araştırma dosyasının ön kayıtlı analizi (README "Yöntem"). Tek komut:

    python calistir.py                         # uydurma örnek dosyayla (ciktilar/ornek/)
    python calistir.py yol/boy-olcum-arastirma.json [--girdi yol/girdi.json]
    python calistir.py ciktilar/ornek/ornek_arastirma.json --girdi ../../1-belirsiz-olcumlerle-tahmin/simulasyon/ornek_girdi.json
                                               # adım 4'ün uydurma veriyle çalışma testi (çıktı .kisisel/ altına)

Gerçek dosya verildiğinde çıktılar .kisisel/ altına yazılır (repoya girmez).

Adımlar (önceden sabit)
  1  Kalite: ana analiz yalnız koşulu uygun (uyarısız) seanslarla; bütün seanslar duyarlılık analizi olarak
  2  Eğilim: boy, oturma (gövde) ve bacak için seans ortalamalarına doğrusal regresyon; eğim cm/yıl, %95 aralık (t)
  3  Karar: K1 boy eğiminin alt sınırı > 0 → "hâlâ uzuyor"; üst sınırı < 0.3 cm/yıl → "uzama durmuş ya da çok yavaş";
     ikisi de değilse "belirsiz". K2 gövde ve bacak için aynı kural ayrı ayrı.
  4  (--girdi verilirse ve dosyada yaş varsa) kişisel analiz sürüm 1'in sonsalı yeni sabah ölçümleriyle güncellenir:
     kalan büyüme (25 yaşa) önce ve sonra
  5  Süre tablosu (veriden bağımsız, örnek modunda): seans ortalamasının gün-gün oynaklığı (SD) 0.2-0.5 cm iken,
     haftada/2 haftada/ayda bir ölçümle boy eğiminin %95 aralığının yarı genişliği kaç ayda 0.3 cm/yıl altına iner
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

KOK = Path(__file__).resolve().parent
VAKA = KOK.parents[1] / "1-belirsiz-olcumlerle-tahmin" / "simulasyon"
DURDU = 0.3       # cm/yıl: K1 "durmuş ya da çok yavaş" eşiği (omurga sürüm 1: geç dönem bacak ~0.3 cm/yıl)


def ornek_dosya():
    """Uydurma: 12 seans, ~40 günde bir; gövde +0.5 cm/yıl, bacak 0; ölçüm gürültüsü SD 0.25 cm; 2 seans koşul dışı."""
    rng = np.random.default_rng(20261010)
    sat = []
    for i in range(12):
        gun = i * 40
        y = gun / 365.25
        gov = 92.0 + 0.5 * y + rng.normal(0, 0.25)
        bac = 83.0 + rng.normal(0, 0.25)
        aksam = i in (4, 9)
        kay = -1.0 if aksam else 0.0                            # akşam ölçümü: gün içi kısalma
        sat.append(dict(gun=gun, yas=round(17.3 + y, 1), saat=19 if aksam else 7, uyanma_dk=600 if aksam else 15,
                        boy_ort=round(gov + bac + kay, 2), oturma_ort=round(gov + kay * 0.8, 2),
                        bacak_ort=round(bac + kay * 0.2, 2), uyari="sabah değil; kalkıştan 1 saatten fazla sonra" if aksam else ""))
    return dict(bicim="boy-olcum-gunlugu/arastirma/v1", seans=len(sat), satirlar=sat)


def egim(x, y):
    r = stats.linregress(x, y)
    t = stats.t.ppf(0.975, len(x) - 2)
    artik = y - (r.intercept + r.slope * x)
    return dict(egim=r.slope, lo=r.slope - t * r.stderr, hi=r.slope + t * r.stderr, n=len(x), kesisim=r.intercept,
                artik_sd=float(np.sqrt((artik ** 2).sum() / (len(x) - 2))))


def sure_tablosu():
    """Beklenen %95 yarı genişlik < DURDU olana kadar geçen ay (eşit aralıklı seanslar; gerçek eğimden bağımsız)."""
    tablo = {}
    for sd in (0.2, 0.3, 0.4, 0.5):
        for gun_ara, ad in ((7, "haftada bir"), (14, "2 haftada bir"), (30, "ayda bir")):
            for ay in range(2, 61):
                x = np.arange(0, ay * 30.44 + 1e-9, gun_ara) / 365.25
                if len(x) < 4:
                    continue
                yari = stats.t.ppf(0.975, len(x) - 2) * sd / np.sqrt(((x - x.mean()) ** 2).sum())
                if yari < DURDU:
                    tablo[f"SD {sd} cm, {ad}"] = dict(ay=ay, seans=len(x))
                    break
    return tablo


def karar(e):
    if e["lo"] > 0:
        return "hâlâ uzuyor"
    if e["hi"] < DURDU:
        return "durmuş ya da çok yavaş"
    return "belirsiz (daha çok veri gerekli)"


def main(argv):
    girdi_yolu = None
    if "--girdi" in argv:
        i = argv.index("--girdi")
        girdi_yolu = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if argv:
        veri = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        cikti = KOK.parent / ".kisisel"
    else:
        veri = ornek_dosya()
        cikti = KOK / "ciktilar" / "ornek"
    cikti.mkdir(parents=True, exist_ok=True)
    if not argv:
        (cikti / "ornek_arastirma.json").write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
        (cikti / "sure.json").write_text(json.dumps(sure_tablosu(), ensure_ascii=False, indent=1), encoding="utf-8")
    assert veri.get("bicim") == "boy-olcum-gunlugu/arastirma/v1", "araştırma dosyası biçimi tanınmadı"
    d = pd.DataFrame(veri["satirlar"])
    d["yil"] = d.gun / 365.25
    d["temiz"] = d.uyari.fillna("").eq("")

    sonuc = {"seans": len(d), "sure_ay": float(d.gun.max() / 30.44), "uyarili_seans": int((~d.temiz).sum())}
    for etiket, alt in (("ana", d[d.temiz]), ("duyarlilik_butun_seanslar", d)):
        sonuc[etiket] = {}
        if len(alt) < 4:
            continue
        for k, sutun in (("boy", "boy_ort"), ("govde", "oturma_ort"), ("bacak", "bacak_ort")):
            e = egim(alt.yil.to_numpy(), alt[sutun].to_numpy())
            e["karar"] = karar(e)
            sonuc[etiket][k] = e

    # İsteğe bağlı: kişisel sonsalın güncellenmesi
    if girdi_yolu and d.yas.notna().all():
        sys.path.insert(0, str(VAKA))
        import vaka
        girdi = json.loads(girdi_yolu.read_text(encoding="utf-8"))
        on = vaka.Onsel(girdi["cinsiyet"], 1_200_000, 20261007)
        s0 = vaka.sonsal(on, girdi, vaka.Ayar(), tohum=20261007)
        yeni = dict(girdi)
        yeni["olcumler"] = list(girdi["olcumler"]) + [
            dict(ad=f"günlük {int(r.gun)}", yas=[r.yas - 0.05, r.yas + 0.05], deger=float(r.boy_ort),
                 saat="sabah" if r.temiz else "bilinmiyor", ayakkabi="yok", hata_sd=0.4) for r in d.itertuples()]
        yeni["simdiki_yas"] = float(d.yas.max())
        s1 = vaka.sonsal(on, yeni, vaka.Ayar(), tohum=20261007)
        q = lambda s: [float(v) for v in vaka.yuzdelik(s["kalan"], s["w"], [10, 50, 90])]
        sonuc["sonsal"] = dict(once_kalan_p10_p50_p90=q(s0), sonra_kalan_p10_p50_p90=q(s1), ESS_sonra=s1["ess"],
                               not_="Kişisel analiz sürüm 1: aralıklar fazla dar (kalibrasyon testi T1 kaldı).")
        if s1["ess"] < 100:
            sonuc["sonsal"]["uyari"] = (f"Etkin örneklem {s1['ess']:.0f} < 100: yeni ölçümler önseli çok daralttı, "
                                        "sonsal güvenilir değil (önsel örneklemi büyütülmeli).")

    (cikti / "analiz.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1, default=float), encoding="utf-8")

    fig, axs = plt.subplots(1, 2, figsize=(11, 4), facecolor="#fcfcfb")
    ax = axs[0]
    ax.plot(d.gun[d.temiz], d.boy_ort[d.temiz], "o", color="#0b0b0b", label="sabah, koşul uygun")
    ax.plot(d.gun[~d.temiz], d.boy_ort[~d.temiz], "o", mfc="none", color="#eb6834", label="koşul uyarılı")
    e = sonuc["ana"].get("boy")
    if e:
        xx = np.array([0, d.gun.max()])
        ax.plot(xx, e["kesisim"] + e["egim"] * xx / 365.25, "--", color="#8a8984",
                label=f"eğilim {e['egim']:+.2f} cm/yıl ({e['lo']:+.2f} … {e['hi']:+.2f})")
    ax.set_xlabel("İlk seanstan bu yana gün")
    ax.set_ylabel("Boy (cm)")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    ax = axs[1]
    for sut, renk, ad in (("oturma_ort", "#1baf7a", "gövde"), ("bacak_ort", "#2a78d6", "bacak")):
        deg = d[sut] - d[sut][d.temiz].iloc[0]
        ax.plot(d.gun, deg, "-", color=renk, lw=1.5, label=ad)
        ax.plot(d.gun[d.temiz], deg[d.temiz], "o", color=renk, ms=4)
        ax.plot(d.gun[~d.temiz], deg[~d.temiz], "o", mfc="white", color=renk, ms=5)
    ax.axhline(0, color="#e4e3df")
    ax.set_xlabel("İlk seanstan bu yana gün")
    ax.set_ylabel("İlk uyarısız seansa göre değişim (cm)")
    ax.set_title("içi boş: koşul uyarılı seans", fontsize=9, loc="left", color="#555")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(cikti / "analiz.png", dpi=140)
    print(json.dumps(sonuc, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1:])
