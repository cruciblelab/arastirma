"""
Keşifsel (ön kayıtlı değil; PLAN 7, sapma 2): kişiye özgü görünüş farkı büyükse (τ = 2 cm) kaç kişi gerekir?

    python kesifsel_tau.py      (önce calistir.py)

Çıktı: ciktilar/kesifsel_tau.csv
"""

import os

for _d in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_d, "1")
import pandas as pd  # noqa: E402

import calistir as c  # noqa: E402

if __name__ == "__main__":
    isler = []
    for i, N in enumerate((10, 20, 30, 40)):
        for p in (0.0, 1.0, 2.0):
            isler += [(N, 30, "amacli", p, c.TOHUM + 13_000_000 + i * 100_000 + int(p) * 10_000 + k, 2.0)
                      for k in range(300)]
    d = c.paralel(isler)
    t = d.groupby(["N", "pse2_gercek"]).agg(guc_ya_da_yanlis_alarm=("red", "mean"), kapsama=("kapsar", "mean")).reset_index()
    t.insert(0, "tau", 2.0)
    t.insert(1, "R", 30)
    t.to_csv(c.CIKTI / "kesifsel_tau.csv", index=False, float_format="%.3f")
    print(t.to_string(index=False))
