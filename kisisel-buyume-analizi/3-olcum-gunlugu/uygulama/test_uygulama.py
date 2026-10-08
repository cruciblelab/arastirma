"""
Uygulamanın otomatik tarayıcı testi (Chromium, Playwright). Uydurma veriyle çalışır; gerçek veri kullanmaz.

    pip install playwright && python test_uygulama.py

Sınar:
  U1  Sayfa ağa bağlanamıyor (CSP): fetch ve resim istekleri engelleniyor
  U2  Ayarlar ve 10 seans girişi; oturma boyundan tabure çıkarılıyor
  U3  Eğilim: uydurma veride gövde +0.6 cm/yıl, bacak 0 → uygulamanın eğimi ±0.15 içinde
  U4  Kalıcılık: sayfa yeniden açılınca seanslar duruyor
  U5  Yedek dosyası: bütün seanslar ve ayarlar var; geri yükleme tekrar eklemiyor
  U6  Araştırma dosyası kimliksiz: tarih ve doğum ayı yok; "notları ekle" kaldırılınca not da yok; gün ve 1 ondalık yaş var
  U7  Ekran görüntüleri: açık ve koyu tema (ciktilar/)
  U8  Uyarılı seans (akşam, −1 cm) eğilime katılmıyor ve grafikte içi boş çiziliyor
  U10 Düzenleme: seans formda açılıyor, değişiklik aynı seansa yazılıyor (sayı artmıyor); araştırma dosyasında
      notlar varsayılan olarak var ve düzeltilen seans "sonradan_duzeltildi = 1"
  U9  Gereken süre hesabı analiz/calistir.py'nin süre tablosuyla aynı (SD 0.3: haftada bir 12, ayda bir 19 ay)
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

KOK = Path(__file__).resolve().parent
HTML = (KOK / "boy-olcum-gunlugu.html").as_uri()
CIKTI = KOK / "ciktilar"
CIKTI.mkdir(exist_ok=True)
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"      # yoksa Playwright'ın kendi Chromium'u
CHROME = CHROME if Path(CHROME).exists() else None
SONUC = []


def test(ad, gecti, deger):
    SONUC.append(dict(test=ad, sonuc="GEÇTİ" if gecti else "KALDI", deger=deger))
    print(f"{ad}: {'GEÇTİ' if gecti else 'KALDI'} ({deger})")


# Uydurma veri: 10 seans, ~45 günde bir; boy = 175.0 + 0.6·yıl (yalnız gövde uzuyor), küçük ölçüm gürültüsü
TABURE = 45.0
SEANS = []
for i in range(10):
    gun = i * 45
    yil = gun / 365.25
    govde = 92.0 + 0.6 * yil
    bacak = 83.0
    g = [(-0.2, 0.1, 0.1), (0.1, -0.1, 0.0), (0.0, 0.2, -0.2), (0.1, 0.0, -0.1), (-0.1, 0.1, 0.0),
         (0.2, -0.2, 0.0), (0.0, 0.0, 0.1), (-0.1, 0.0, 0.1), (0.1, 0.1, -0.2), (0.0, -0.1, 0.1)][i]
    SEANS.append(dict(gun=gun, boy=[round(govde + bacak + e, 1) for e in g],
                      oturma=[round(govde + TABURE + e, 1) for e in g[::-1]]))


def tarih(gun):
    import datetime as dt
    return (dt.date(2026, 10, 10) + dt.timedelta(days=gun)).isoformat()


with sync_playwright() as p:
    tarayici = p.chromium.launch(executable_path=CHROME)
    bag = tarayici.new_context(accept_downloads=True, viewport={"width": 1100, "height": 900})
    s = bag.new_page()
    s.goto(HTML)

    # U1: ağ engeli
    ag = s.evaluate("""async () => {
        let f = 'izin verildi';
        try { await fetch('https://example.com/'); } catch (e) { f = 'engellendi'; }
        const r = await new Promise(ok => { const i = new Image(); i.onload = () => ok('izin verildi');
            i.onerror = () => ok('engellendi'); i.src = 'https://example.com/a.png'; });
        return {fetch: f, resim: r};
    }""")
    test("U1", ag == {"fetch": "engellendi", "resim": "engellendi"}, json.dumps(ag, ensure_ascii=False))

    # U2: ayarlar ve giriş
    s.click("nav button[data-panel=veri]")
    s.fill("#tabure", str(TABURE))
    s.fill("#dogum", "2004-03")
    s.click("#ayarKaydet")
    s.click("nav button[data-panel=olcum]")
    for k, x in enumerate(SEANS):
        s.fill("#tarih", tarih(x["gun"]))
        s.fill("#saat", "07:30")
        s.fill("#uyanma", "15")
        for j in range(3):
            s.fill(f"#b{j + 1}", str(x["boy"][j]))
            s.fill(f"#o{j + 1}", str(x["oturma"][j]))
        s.fill("#kilo", "63")
        s.fill("#not", "GİZLİ-NOT-" + str(k))
        s.click("#kaydet")
    durum = s.evaluate("JSON.parse(localStorage.getItem('boyOlcumGunlugu.v1'))")
    n = len(durum["seanslar"])
    otur0 = s.evaluate("turet(sirali()[0]).oturma")
    test("U2", n == 10 and abs(otur0 - 92.0) < 0.15, f"{n} seans; ilk oturma boyu {otur0:.2f} cm (beklenen ~92.0)")

    # U3: eğilim
    s.click("nav button[data-panel=grafik]")
    e = s.evaluate("""(() => { const q = sirali(), ilk = q[0].tarih;
        const y = q.map(x => gunFarki(ilk, x.tarih) / 365.25), T = q.map(turet);
        return {govde: egim(y, T.map(t => t.oturma)).b, bacak: egim(y, T.map(t => t.bacak)).b,
                boy: egim(y, T.map(t => t.boy)).b}; })()""")
    test("U3", abs(e["govde"] - 0.6) < 0.15 and abs(e["bacak"]) < 0.15,
         f"gövde {e['govde']:+.2f}, bacak {e['bacak']:+.2f}, boy {e['boy']:+.2f} cm/yıl")
    s.screenshot(path=str(CIKTI / "ekran_grafikler_acik.png"), full_page=True)

    # U4: kalıcılık
    s.reload()
    n2 = s.evaluate("durum.seanslar.length")
    test("U4", n2 == 10, f"yeniden açılışta {n2} seans")

    # U5: yedek ve geri yükleme
    s.click("nav button[data-panel=veri]")
    with s.expect_download() as d:
        s.click("#yedekAl")
    yol = CIKTI / "_yedek_test.json"
    d.value.save_as(yol)
    yedek = json.loads(yol.read_text(encoding="utf-8"))
    s.once("dialog", lambda dlg: dlg.accept())
    s.set_input_files("#yedekYukle", str(yol))
    s.wait_for_timeout(500)
    n3 = s.evaluate("durum.seanslar.length")
    test("U5", len(yedek["seanslar"]) == 10 and yedek["ayarlar"]["tabure"] == TABURE and n3 == 10,
         f"yedekte {len(yedek['seanslar'])} seans; geri yüklemeden sonra {n3} (tekrar yok)")
    yol.unlink()

    # U6: araştırma dosyası (notlar kaldırılarak)
    s.uncheck("#xNot")
    with s.expect_download() as d1:
        s.click("#arastirmaDosyasi")
    ar = json.loads(Path(d1.value.path()).read_text(encoding="utf-8"))
    metin = json.dumps(ar, ensure_ascii=False)
    satir = ar["satirlar"]
    yok = ["2026-", "2004-03", "GİZLİ-NOT", "tarih", "dogum"]
    temiz = not any(k in metin for k in yok)
    yaslar = [r["yas"] for r in satir]
    test("U6", temiz and satir[0]["gun"] == 0 and satir[-1]["gun"] == 405 and
         all(abs(y * 10 - round(y * 10)) < 1e-9 for y in yaslar),
         f"yasak içerik yok: {temiz}; gün {satir[0]['gun']}…{satir[-1]['gun']}; yaş {yaslar[0]}…{yaslar[-1]}")

    # U10: geçmiş seansı düzenleme ve notlu araştırma dosyası
    s.check("#xNot")
    s.click("nav button[data-panel=liste]")
    hedef = s.evaluate("sirali()[2].id")
    s.click(f"[data-duzenle='{hedef}']")
    b1_once = s.input_value("#b1")
    s.fill("#b1", str(round(float(b1_once) + 0.3, 1)))
    s.fill("#not", "duvar değişti")
    s.click("#kaydet")
    sonra = s.evaluate(f"durum.seanslar.find(z => z.id === '{hedef}')")
    n4 = s.evaluate("durum.seanslar.length")
    s.click("nav button[data-panel=veri]")
    with s.expect_download() as d2:
        s.click("#arastirmaDosyasi")
    ar2 = json.loads(Path(d2.value.path()).read_text(encoding="utf-8"))["satirlar"]
    test("U10", n4 == 10 and abs(sonra["boy"][0] - float(b1_once) - 0.3) < 1e-9 and ar2[2]["not"] == "duvar değişti"
         and ar2[2]["sonradan_duzeltildi"] == 1 and sum(r["sonradan_duzeltildi"] for r in ar2) == 1
         and ar2[0]["not"].startswith("GİZLİ-NOT"),
         f"seans sayısı {n4}; boy_1 {b1_once} → {sonra['boy'][0]}; not '{ar2[2]['not']}'; düzeltildi işareti {ar2[2]['sonradan_duzeltildi']}")

    # U8: uyarılı seans
    s.click("nav button[data-panel=olcum]")
    s.fill("#tarih", tarih(200))
    s.fill("#saat", "20:00")
    s.fill("#uyanma", "700")
    for j in range(3):
        s.fill(f"#b{j + 1}", "174.3")
        s.fill(f"#o{j + 1}", "136.2")
    s.click("#kaydet")
    s.click("nav button[data-panel=grafik]")
    bos = s.locator("#g-boy circle[fill='var(--yuzey)']").count()
    msj = s.inner_text("#egilimMesaj")
    e2 = s.evaluate("""(() => { const q = sirali(), ilk = q[0].tarih, t = q.filter(x => bayraklar(x).length === 0);
        return egim(t.map(x => gunFarki(ilk, x.tarih) / 365.25), t.map(x => turet(x).oturma)).b; })()""")
    test("U8", bos == 1 and "1 uyarılı seans" in msj and abs(e2 - e["govde"]) < 1e-9,
         f"içi boş nokta {bos}; gövde eğimi {e2:+.2f} (uyarılı seans öncesi {e['govde']:+.2f})")
    s.screenshot(path=str(CIKTI / "ekran_grafikler_acik.png"), full_page=True)

    # U9: gereken süre
    ga = s.evaluate("[gerekenAy(0.3, 7), gerekenAy(0.3, 30), gerekenAy(0.2, 7), gerekenAy(0.5, 30)]")
    test("U9", ga == [12, 19, 9, 27], f"SD 0.3 haftada {ga[0]}, ayda {ga[1]}; SD 0.2 haftada {ga[2]}; SD 0.5 ayda {ga[3]} ay")

    # U7: koyu tema ve mobil genişlik ekran görüntüleri
    s.emulate_media(color_scheme="dark")
    s.click("nav button[data-panel=grafik]")
    s.screenshot(path=str(CIKTI / "ekran_grafikler_koyu.png"), full_page=True)
    s.emulate_media(color_scheme="light")
    s.click("nav button[data-panel=liste]")
    s.screenshot(path=str(CIKTI / "ekran_olcumler.png"), full_page=True)
    s.set_viewport_size({"width": 390, "height": 900})
    s.emulate_media(color_scheme="light")
    s.click("nav button[data-panel=olcum]")
    s.screenshot(path=str(CIKTI / "ekran_olcum_mobil.png"), full_page=True)
    test("U7", True, "ekran görüntüleri ciktilar/ altında")
    tarayici.close()

(CIKTI / "testler.json").write_text(json.dumps(SONUC, ensure_ascii=False, indent=1), encoding="utf-8")
sys.exit(0 if all(r["sonuc"] == "GEÇTİ" for r in SONUC) else 1)
