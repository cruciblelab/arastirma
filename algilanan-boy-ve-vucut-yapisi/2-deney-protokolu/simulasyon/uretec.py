"""
Sentetik deney verisi üreteci (PLAN 3-4). Analiz kodundan (deney.py) bağımsızdır: gerçek dünyayı taklit eder.

Hedefler: ANSUR II 17-24 yaş erkeklerinden çekilir (omuz ve kilo artıkları gerçek), boy Türk referansına ölçeklenir.
Yanıtlar: D = ΔH + (β + u_r)·Δz + Δt + ε, ε ~ N(0, σ_r²); "sol uzun" ⇔ D > 0.
"""

import hashlib
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
ANSUR = dict(url="https://tools.openlab.psu.edu/publicData/ANSUR_II_MALE_Public.csv",
             sha256="0547aea0170e5293de519389981135e75803f02e6d40c77ace740decc0caac64",
             dosya=REPO / ".veri" / "ansur2" / "ANSUR_II_MALE_Public.csv")
TR_ORT, TR_SD = 175.8, 6.3


def ansur():
    """17-24 yaş erkek; boy, omuz (bideltoid), kilo; regresyon doğruları ve referans SD'ler."""
    if not ANSUR["dosya"].exists():
        ANSUR["dosya"].parent.mkdir(parents=True, exist_ok=True)
        istek = urllib.request.Request(ANSUR["url"], headers={"User-Agent": "arastirma/1.0 (github.com/cruciblelab/arastirma)"})
        with urllib.request.urlopen(istek, timeout=120) as r:
            ANSUR["dosya"].write_bytes(r.read())
    ozet = hashlib.sha256(ANSUR["dosya"].read_bytes()).hexdigest()
    assert ozet == ANSUR["sha256"], f"ANSUR SHA-256 uyuşmuyor: {ozet}"
    d = pd.read_csv(ANSUR["dosya"], encoding="latin-1")
    d = d[d.Age <= 24]
    boy = d.stature.to_numpy(float) / 10
    omuz = d.bideltoidbreadth.to_numpy(float) / 10
    kilo = d.weightkg.to_numpy(float) / 10
    bo, bk = np.polyfit(boy, omuz, 1), np.polyfit(boy, kilo, 1)
    eo, ek = omuz - np.polyval(bo, boy), kilo - np.polyval(bk, boy)
    so, sk = eo.std(), ek.std()
    ort = (eo / so + ek / sk) / 2
    ref = dict(omuz_artik_sd_cm=float(so), kilo_artik_sd_kg=float(sk), ortalama_sd=float(ort.std()),
               r_omuz_kilo_artik=float(np.corrcoef(eo, ek)[0, 1]), n=int(len(d)), sha256=ozet)
    z = ort / ort.std()
    return dict(ref=ref, eo=eo, ek=ek, z=z, bo=bo, bk=bk)


def hedefler(N, secim, rng, A, boy_aralik=(170.0, 182.0), tau=1.0):
    """N hedef. secim: 'amacli' (yapının alt ve üst %30'undan eşit; boy aralığı sınırlı) ya da 'rastgele'."""
    if secim == "amacli":
        alt, ust = np.percentile(A["z"], [30, 70])
        havuz = {"alt": np.flatnonzero(A["z"] <= alt), "ust": np.flatnonzero(A["z"] >= ust)}
        i = np.concatenate([rng.choice(havuz["alt"], N // 2, replace=False),
                            rng.choice(havuz["ust"], N - N // 2, replace=False)])
        boy = np.empty(N)
        for j in range(N):                                     # kesik normal (ret örneklemesi)
            while True:
                b = rng.normal(TR_ORT, TR_SD)
                if boy_aralik[0] <= b <= boy_aralik[1]:
                    boy[j] = round(b * 2) / 2
                    break
    else:
        i = rng.choice(len(A["z"]), N, replace=False)
        boy = np.round(rng.normal(TR_ORT, TR_SD, N) * 2) / 2
    omuz = np.polyval(A["bo"], boy) + A["eo"][i]
    kilo = np.polyval(A["bk"], boy) + A["ek"][i]
    return pd.DataFrame(dict(id=[f"H{j + 1:02d}" for j in range(N)], boy_cm=boy, omuz_cm=np.round(omuz, 1),
                             kilo_kg=np.round(kilo, 1), z_gercek=A["z"][i], t=rng.normal(0, tau, N)))


def yanitlar(h, tasarim, pse2, rng, u_sd=0.25, sigma=(2.0, 4.0)):
    """Her değerlendirici için σ_r ~ U(sigma), u_r ~ N(0, u_sd²). Döner: tasarım + secilen."""
    R = int(tasarim.degerlendirici.max()) + 1
    sig = rng.uniform(*sigma, R)
    u = rng.normal(0, u_sd, R)
    H = dict(zip(h.id, h.boy_cm))
    Z = dict(zip(h.id, h.z_gercek))
    T = dict(zip(h.id, h.t))
    sol, sag, r = tasarim.sol.to_numpy(), tasarim.sag.to_numpy(), tasarim.degerlendirici.to_numpy()
    dH = np.array([H[a] - H[b] for a, b in zip(sol, sag)])
    dZ = np.array([Z[a] - Z[b] for a, b in zip(sol, sag)])
    dT = np.array([T[a] - T[b] for a, b in zip(sol, sag)])
    D = dH + (pse2 / 2 + u[r]) * dZ + dT + rng.normal(0, 1, len(r)) * sig[r]
    out = tasarim.copy()
    out["secilen"] = np.where(D > 0, sol, sag)
    return out
