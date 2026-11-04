"""Weekly against monthly NINO1+2 on the same window: figure and numbers.

    python scripts/weekly_vs_monthly.py [--out data/weekly/weekly-vs-monthly.png]

Both records are analysed on the same span, the weekly record's first whole
year to its latest week (4 Nov 1981 to 28 Oct 2026 with the data of
4 Nov 2026; monthly: Nov 1981 to Oct 2026). Prints, for METHODS.md
("Weekly SST"):

* RMS difference of T and dT/dt at common times (the weekly series
  interpolated to mid-month), over the window and without the provisional
  end;
* peak date and value of the filtered and observed anomaly per event;
* SIGMA30 of each record;
* the cross-check of the fitted weekly seasonal cycle against NOAA's SSTA;
* a replay of 2025: when each record, as published at the time, first
  showed the current event (latest anomaly >= current_event.threshold; the
  filtered anomaly ends exactly on the latest observation, so the observed
  value is the test).

Needs matplotlib (pip install -e ".[scripts]").
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np

from enso import fourier, phasespace, series, weekly
from enso.config import ROOT, load_config

KEY = "nino12"
EVENTS = ("1997-98", "2015-16", "2023-24", "2025-26")
# When a value becomes public. Monthly: sstoi.indices gains month m around the
# 3rd of month m+1 (the CI runs on the 4th). Weekly: the week centred on
# Wednesday W (Sunday to Saturday) is in wksst9120.for by the next Wednesday
# (the file of 4 Nov 2026 ends with the week centred on 28 Oct).
MONTHLY_LAG = np.timedelta64(3, "D")    # after the first day of the next month
WEEKLY_LAG = np.timedelta64(7, "D")     # after the week's centre


def mid_month(periods: list[str]) -> np.ndarray:
    m = np.array(periods, dtype="datetime64[M]")
    first = m.astype("datetime64[D]")
    return first + ((m + np.timedelta64(1, "M")).astype("datetime64[D]") - first) / 2


def run_monthly(rec, cfg, start, end=None):
    params = replace(cfg.filter, window_start=start, window_end=end)
    return phasespace.compute(rec, cfg.dataset(KEY), params)


def run_weekly(rec, cfg, end=None, not_before=None):
    return weekly.compute(rec, KEY, "absolute", cfg.filter, cfg.weekly.get("harmonics", 4),
                          end=end, not_before=not_before)


def peak(dates, values, start, end):
    sel = (dates >= start) & (dates <= end)
    i = int(np.argmax(np.where(sel, values, -np.inf)))
    return dates[i], float(values[i])


def replay(mrec, wrec, cfg, threshold, since="2024-07-01"):
    """For each publication date since ``since``: did the latest monthly /
    weekly anomaly (observed, and filtered) reach the threshold?"""
    first_week = str(wrec.week[0])
    out = {"monthly": [], "weekly": []}
    months = np.array([f"{y:04d}-{m:02d}" for y, m in zip(mrec.year, mrec.month)], dtype="datetime64[M]")
    for m in months[months >= np.datetime64(since[:7], "M")]:
        published = (m + np.timedelta64(1, "M")).astype("datetime64[D]") + MONTHLY_LAG
        end = str(m)
        # Same start rule as the comparison: first whole-cycle start in the weekly era.
        start_month = int(str(m)[5:7]) % 12 + 1
        start = f"1981-{start_month:02d}" if start_month >= 9 else f"1982-{start_month:02d}"
        ps = run_monthly(mrec, cfg, start, end)
        out["monthly"].append((published, str(m), ps.observed_anomaly[-1], ps.anomaly[-1]))
    for w in wrec.week[wrec.week >= np.datetime64(since)]:
        wp = run_weekly(wrec, cfg, end=w, not_before=first_week)
        out["weekly"].append((w + WEEKLY_LAG, str(w), wp.observed_anomaly[-1], wp.anomaly[-1]))
    return out


def first_signal(rows, col, threshold, sustained):
    """Publication date and data date of the first row at or above the
    threshold; with ``sustained``, the first one from which every later row
    stays at or above it."""
    hit = [r[col] >= threshold for r in rows]
    if sustained:
        idx = next((i for i in range(len(rows)) if all(hit[i:])), None)
    else:
        idx = next((i for i, h in enumerate(hit) if h), None)
    return None if idx is None else rows[idx]


def plot(ps, wp, mdates, path: Path, cfg) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdt
    import matplotlib.pyplot as plt

    from enso.site.theme import TOKENS

    t = TOKENS["light"]
    cm, cw = t["slot-a"], t["slot-b"]
    plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": t["muted"],
                         "axes.labelcolor": t["text"], "xtick.color": t["text-2"],
                         "ytick.color": t["text-2"], "axes.spines.top": False,
                         "axes.spines.right": False, "axes.titlesize": 10,
                         "axes.titleweight": "bold", "axes.titlecolor": t["text"],
                         "legend.frameon": False})
    fig = plt.figure(figsize=(12, 7.2), dpi=150, layout="constrained")
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.35])
    ax_p = fig.add_subplot(gs[:, 0])
    ax_t = fig.add_subplot(gs[0, 1])
    ax_z = fig.add_subplot(gs[1, 1])
    wdates = wp.week.astype("datetime64[D]").astype(object)
    md = mdates.astype(object)
    fine = np.arange(len(ps.T)) / ps.ndots
    mfine = (mdates[0] + (fine * 30.4375).astype(int).astype("timedelta64[D]"))

    # Phase diagram: the whole window thin, the running event bold.
    ev = np.datetime64("2025-02-01")
    ax_p.plot(ps.T, ps.V, color=cm, lw=0.5, alpha=0.35)
    ax_p.plot(wp.T, wp.V, color=cw, lw=0.5, alpha=0.35)
    sm, sw = mfine >= ev, wp.week >= ev
    ax_p.plot(ps.T[sm], ps.V[sm], color=cm, lw=2, label="Monthly (sstoi.indices)")
    ax_p.plot(wp.T[sw], wp.V[sw], color=cw, lw=2, label="Weekly (wksst9120.for)")
    for T, V, c in ((ps.T, ps.V, cm), (wp.T, wp.V, cw)):
        ax_p.plot(T[-1], V[-1], "o", ms=8, color=c, mec=t["bg"] if "bg" in t else "white", mew=2)
    ax_p.axhline(0, color=t["muted"], lw=0.6, zorder=0)
    ax_p.set_xlabel("T, filtered NINO1+2 SST (°C)")
    ax_p.set_ylabel("dT/dt (°C/month)")
    ax_p.set_title("Phase diagram, Nov 1981 to Oct 2026 (bold: Feb 2025 on)", loc="left")
    ax_p.legend(loc="upper left")

    # Filtered anomaly, whole window.
    ax_t.plot(md, ps.anomaly, color=cm, lw=1.2, label="Monthly")
    ax_t.plot(wdates, wp.anomaly, color=cw, lw=1.2, label="Weekly")
    ax_t.axhline(0, color=t["muted"], lw=0.6, zorder=0)
    ax_t.set_ylabel("Filtered anomaly (°C)")
    ax_t.set_title("Filtered anomaly (seasonal cycle removed)", loc="left")
    ax_t.legend(loc="upper left", ncols=2)

    # Zoom: 2022 on, observed and filtered, provisional zone shaded.
    z0 = np.datetime64("2022-01-01")
    zm, zw = mdates >= z0, wp.week >= z0
    prov = (wp.week[-1] - np.timedelta64(weekly.months_to_weeks(cfg.filter.provisional_months) * 7, "D"))
    ax_z.axvspan(prov.astype(object), wdates[-1], color=t["muted"], alpha=0.12, lw=0)
    ax_z.text(prov.astype(object), 0.97, " provisional", transform=ax_z.get_xaxis_transform(),
              va="top", color=t["text-2"], fontsize=8.5)
    ax_z.plot(wdates[zw], wp.observed_anomaly[zw], color=cw, lw=0.7, alpha=0.6)
    ax_z.plot(md[zm], ps.observed_anomaly[zm], "o", ms=3.5, color=cm, alpha=0.8)
    ax_z.plot(md[zm], ps.anomaly[zm], color=cm, lw=2, label="Monthly: filtered; dots observed")
    ax_z.plot(wdates[zw], wp.anomaly[zw], color=cw, lw=2, label="Weekly: filtered; thin observed")
    ax_z.axhline(cfg.current_event.threshold, color=t["muted"], lw=0.8, ls=":")
    ax_z.axhline(0, color=t["muted"], lw=0.6, zorder=0)
    ax_z.set_ylabel("Anomaly (°C)")
    ax_z.set_title("Since 2022: observed and filtered", loc="left")
    ax_z.xaxis.set_major_formatter(mdt.DateFormatter("%Y"))
    ax_z.legend(loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "weekly" / "weekly-vs-monthly.png")
    args = ap.parse_args(argv)
    cfg = load_config()
    mrec, wrec = series.read(KEY), weekly.read()

    wp = run_weekly(wrec, cfg)
    start = str(wp.week[0])[:7]
    ps = run_monthly(mrec, cfg, start)
    mdates = mid_month(ps.periods)
    print(f"window: weekly {wp.window['start']} to {wp.window['end']} ({wp.window['n_weeks']} weeks, "
          f"{wp.window['n_years']} years); monthly {ps.window['start']} to {ps.window['end']} "
          f"({ps.window['n_months']} months)")

    x = (mdates - wp.week[0]).astype(float)
    xw = (wp.week - wp.week[0]).astype(float)
    ok = (x >= 0) & (x <= xw[-1])
    settled = ok & (np.arange(len(x)) < len(x) - cfg.filter.provisional_months)
    at = lambda v: np.interp(x, xw, v)
    for name, a, b in (("T", at(wp.T), ps.T_month), ("dT/dt", at(wp.V), ps.V_month),
                       ("filtered anomaly", at(wp.anomaly), ps.anomaly)):
        r_all = np.sqrt(np.mean((a - b)[ok] ** 2))
        r_set = np.sqrt(np.mean((a - b)[settled] ** 2))
        print(f"RMS weekly - monthly, {name}: {r_all:.3f} (window), {r_set:.3f} (without the "
              f"provisional end); monthly std {np.std(b):.3f}; corr {np.corrcoef(a[ok], b[ok])[0, 1]:.4f}")
    # Where the difference sits: the seasonal cycle (12 monthly means against
    # a 4-harmonic fit) or the anomaly's rate.
    _, va_m, _ = fourier.deri_fourier(ps.ndots, ps.anomaly)
    _, va_w, _ = fourier.deri_fourier(1, wp.anomaly)
    d_rate = at(va_w * weekly.WEEKS_PER_MONTH) - va_m[:: ps.ndots]
    d_cycle = at(wp.cycle) - (ps.T_month - ps.anomaly)
    print(f"  of which seasonal cycle (T): {np.sqrt(np.mean(d_cycle[ok] ** 2)):.3f}; "
          f"rate of the anomaly alone: {np.sqrt(np.mean(d_rate[ok] ** 2)):.3f} "
          f"(its monthly std {np.std(va_m):.3f})")
    print(f"SIGMA30: monthly {ps.sigma_filter:.3f}, weekly {wp.sigma_filter:.3f} °C")

    i0 = int(np.searchsorted(wrec.week, wp.week[0]))
    noaa = wrec.values["nino12_anom"][i0:i0 + len(wp.week)]
    d = wp.observed_anomaly - noaa
    print(f"weekly anomaly vs NOAA SSTA: mean offset {d.mean():+.3f} °C (base period), "
          f"RMS after removing it {np.std(d):.3f} °C")

    ev = {e.label: e for e in cfg.events}
    last = str(wp.week[-1])
    print("\nevent    record   filtered peak          observed peak")
    for label in EVENTS:
        e = ev[label]
        s = np.datetime64(e.start + "-01")
        end = np.datetime64(last) if e.end is None else (np.datetime64(e.end, "M") + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D")
        for name, dates, filt, obs in (("monthly", mdates, ps.anomaly, ps.observed_anomaly),
                                       ("weekly", wp.week, wp.anomaly, wp.observed_anomaly)):
            fd, fv = peak(dates, filt, s, end)
            od, ov = peak(dates, obs, s, end)
            fmt = (lambda d: str(d)[:7]) if name == "monthly" else str
            print(f"{label}  {name:<8} {fmt(fd):<10} {fv:+.2f}       {fmt(od):<10} {ov:+.2f}")

    thr = cfg.current_event.threshold
    rows = replay(mrec, wrec, cfg, thr)
    print(f"\nreplay since mid-2024, threshold {thr} °C (date public, data date):")
    for col, what in ((2, "latest anomaly"),):
        for sustained in (False, True):
            tag = "stays above from" if sustained else "first above"
            mo = first_signal(rows["monthly"], col, thr, sustained)
            wk = first_signal(rows["weekly"], col, thr, sustained)
            lead = (mo[0] - wk[0]).astype(int) if mo and wk else None
            print(f"  {what:<28} {tag:<17} monthly {mo[0] if mo else '-'} ({mo[1] if mo else ''}), "
                  f"weekly {wk[0] if wk else '-'} ({wk[1] if wk else ''}); weekly earlier by {lead} days")
    plot(ps, wp, mdates, args.out, cfg)
    print(f"\nfigure: {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")


if __name__ == "__main__":
    main()
