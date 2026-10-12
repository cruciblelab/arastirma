"""Aramanın "Cevapla" düğmesi. Bazı telefonlar (HyperOS) başka uygulamanın bastığı "Cevapla"yı sessizce yok
sayıyor; bilgisayardan basıldıktan sonra arama hâlâ çalıyorsa bu dürüstçe söylenir ("telefondan cevapla")."""

import re

ANSWER = re.compile(r"cevapla|yanıtla|yanitla|answer|accept|kabul", re.IGNORECASE)
WAIT_MS = 3000  # telefon cevaplarsa bu sürede arama "sürüyor"a geçer
FAILED = "Bilgisayardan cevaplanamadı · telefondan cevapla"


def is_answer(title) -> bool:
    return bool(title and ANSWER.search(title))
