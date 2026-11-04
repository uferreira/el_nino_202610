"""How much do filtered values move when more months arrive?

    python scripts/hindcast.py [dataset ...]
    python scripts/hindcast.py --weekly [nino12 nino34 ...]

Re-runs the analysis on the record cut at many past end months (every 3
months, from 3 to 18 years ago) and compares each run's filtered value at L
months before its end with the value the full record gives for that month.
Prints the RMS revision, as a fraction of the series' standard deviation,
by L. This is the evidence for filter.provisional_months (METHODS.md).

--weekly does the same for the weekly record (enso.weekly): cuts every 13
weeks over the same 3 to 18 years, lags converted to weeks, and the lag
still printed in months, so the two tables line up.
"""

from __future__ import annotations

import sys

import numpy as np

from enso import series, weekly
from enso.config import load_config
from enso.phasespace import compute

LAGS = range(0, 25, 2)


def revisions(key: str, cfg) -> tuple[np.ndarray, np.ndarray]:
    ds, rec = cfg.dataset(key), series.read(key)
    full = compute(rec, ds, cfg.filter)
    fT = dict(zip(full.periods, full.T_month))
    fV = dict(zip(full.periods, full.V_month))
    eT = {L: [] for L in LAGS}
    eV = {L: [] for L in LAGS}
    for cut in range(36, 36 + 12 * 15, 3):
        r = series.Record(rec.key, rec.year[:-cut], rec.month[:-cut], rec.value[:-cut],
                          rec.gap_filled[:-cut], "", "")
        ps = compute(r, ds, cfg.filter)
        for L in LAGS:
            p = ps.periods[-1 - L]
            eT[L].append(ps.T_month[-1 - L] - fT[p])
            eV[L].append(ps.V_month[-1 - L] - fV[p])
    rms = lambda e, sd: np.array([np.sqrt(np.mean(np.square(e[L]))) / sd for L in LAGS])
    return rms(eT, np.std(full.T_month)), rms(eV, np.std(full.V_month))


def weekly_revisions(key: str, cfg) -> tuple[np.ndarray, np.ndarray]:
    rec = weekly.read()
    quantity = cfg.dataset(key).quantity
    harmonics = cfg.weekly.get("harmonics", 4)
    run = lambda end: weekly.compute(rec, key, quantity, cfg.filter, harmonics, end=end)
    full = run(None)
    fT = dict(zip(full.week.tolist(), full.T))
    fV = dict(zip(full.week.tolist(), full.V))
    lags = [weekly.months_to_weeks(L) for L in LAGS]
    eT = {L: [] for L in lags}
    eV = {L: [] for L in lags}
    for cut in range(weekly.months_to_weeks(36), weekly.months_to_weeks(36 + 12 * 15), 13):
        ps = run(rec.week[-1 - cut])
        for L in lags:
            w = ps.week[-1 - L].tolist()
            eT[L].append(ps.T[-1 - L] - fT[w])
            eV[L].append(ps.V[-1 - L] - fV[w])
    rms = lambda e, sd: np.array([np.sqrt(np.mean(np.square(e[L]))) / sd for L in lags])
    return rms(eT, np.std(full.T)), rms(eV, np.std(full.V))


def main(keys: list[str]) -> None:
    cfg = load_config()
    use_weekly = "--weekly" in keys
    keys = [k for k in keys if k != "--weekly"]
    if use_weekly:
        keys = keys or ["nino12", "nino34"]
        print("weekly record; lags in months (weeks = months x 30.4375 / 7, rounded)")
        print("months before end:   " + " ".join(f"{L:5d}" for L in LAGS))
        for key in keys:
            t, v = weekly_revisions(key, cfg)
            print(f"{key:<12} value    " + " ".join(f"{x:5.2f}" for x in t))
            print(f"{'':<12} rate     " + " ".join(f"{x:5.2f}" for x in v))
        return
    keys = keys or ["nino12", "nino34", "callao"]
    print("months before end:   " + " ".join(f"{L:5d}" for L in LAGS))
    for key in keys:
        t, v = revisions(key, cfg)
        print(f"{key:<12} value    " + " ".join(f"{x:5.2f}" for x in t))
        print(f"{'':<12} rate     " + " ".join(f"{x:5.2f}" for x in v))


if __name__ == "__main__":
    main(sys.argv[1:])
