"""Weekly SST (enso.weekly): the parser, the units, and agreement with the
monthly analysis on the same signal sampled both ways."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from enso import phasespace, publish, series, weekly
from enso.config import load_config

# The first lines of wksst9120.for as published (downloaded 4 Nov 2026), plus
# a later row whose negative anomalies touch the SST before them.
REAL_HEAD = """\
 Weekly SST data starts week centered on 2Sept1981

                Nino1+2      Nino3        Nino34        Nino4
 Week          SST SSTA     SST SSTA     SST SSTA     SST SSTA
 02SEP1981     20.6-0.1     24.8-0.1     26.5-0.2     28.3-0.3
 09SEP1981     20.1-0.6     24.7-0.2     26.5-0.2     28.4-0.2
 16SEP1981     19.7-0.9     24.6-0.3     26.5-0.2     28.4-0.3
"""
NEGATIVE_ROW = " 23SEP1981     20.3-0.4     24.3-0.6     26.1-0.5     28.2-0.5\n"
POSITIVE_ROW = " 30SEP1981     26.0 5.3     29.0 4.1     29.9 3.2     29.9 1.3\n"


def test_parser_reads_the_real_header_and_fixed_width_columns():
    rec = weekly.parse(REAL_HEAD + NEGATIVE_ROW + POSITIVE_ROW)
    assert len(rec) == 5
    assert rec.week[0] == np.datetime64("1981-09-02")
    assert rec.last_week == "1981-09-30"
    assert all(w.astype(object).weekday() == 2 for w in rec.week)          # Wednesdays
    # "20.3-0.4": SST 20.3 and SSTA -0.4, not one token.
    assert [rec.values[c][3] for c in weekly.COLUMNS] == \
        [20.3, -0.4, 24.3, -0.6, 26.1, -0.5, 28.2, -0.5]
    assert [rec.values[c][4] for c in weekly.COLUMNS] == \
        [26.0, 5.3, 29.0, 4.1, 29.9, 3.2, 29.9, 1.3]


@pytest.mark.parametrize("text, message", [
    (REAL_HEAD.replace("SST SSTA     SST SSTA", "SST ANOM     SST SSTA"), "header"),
    (REAL_HEAD + " 07OCT1981     20.3-0.4\n", "62 characters"),
    (REAL_HEAD + NEGATIVE_ROW.replace("23SEP", "30SEP"), "not by the next week"),
])
def test_parser_stops_on_a_changed_layout(text, message):
    with pytest.raises(ValueError, match=message):
        weekly.parse(text)


def test_csv_round_trip(tmp_path):
    rec = weekly.parse(REAL_HEAD + NEGATIVE_ROW)
    rec.fetched = "2026-11-04"
    path = weekly.write(rec, tmp_path / "w.csv")
    back = weekly.read(path)
    assert weekly.data_lines(back) == weekly.data_lines(rec)
    assert back.fetched == "2026-11-04"


def test_cutoffs_and_rate_are_converted_to_weeks_and_per_month():
    params = load_config().filter
    hn1, hn2 = weekly.weekly_cutoffs(params)
    assert hn1 == pytest.approx(10 * 30.4375 / 7) == pytest.approx(43.48, abs=0.005)
    assert hn2 == pytest.approx(9 * 30.4375 / 7) == pytest.approx(39.13, abs=0.005)
    assert weekly.months_to_weeks(10) == 43
    # A slow sine of known period: dT/dt must come out in degrees per MONTH.
    week = np.arange(np.datetime64("1990-01-03"), np.datetime64("2020-01-01"), np.timedelta64(7, "D"))
    t_months = (week - week[0]).astype(float) / weekly.DAYS_PER_MONTH
    P = 60.0
    values = np.sin(2 * np.pi * t_months / P)
    rec = weekly.WeeklyRecord(week, {c: values for c in weekly.COLUMNS})
    wp = weekly.compute(rec, "nino34", "anomaly", params)
    t = (wp.week - week[0]).astype(float) / weekly.DAYS_PER_MONTH
    inner = slice(100, -100)
    assert np.allclose(wp.V[inner], (2 * np.pi / P) * np.cos(2 * np.pi * t / P)[inner], atol=0.01)


def test_window_spans_whole_years_from_the_same_seasonal_phase():
    week = np.arange(np.datetime64("1981-09-02"), np.datetime64("2026-10-29"), np.timedelta64(7, "D"))
    i0, i1, w = weekly.whole_year_window(week)
    assert (w["start"], w["end"], w["n_years"]) == ("1981-11-04", "2026-10-28", 45)
    span = (week[i1] - week[i0]).astype(int) + 7
    assert abs(span - 45 * weekly.DAYS_PER_YEAR) <= 3.5
    assert weekly.whole_year_window(week, not_before="1990-01-01")[2]["n_years"] == 36


def _signal(day):
    """A synthetic NINO1+2: two slow ENSO modes, a seasonal cycle and a fast wiggle."""
    t = (day - np.datetime64("2000-01-01")).astype(float)
    yr = t / weekly.DAYS_PER_YEAR
    enso = np.sin(2 * np.pi * t / (48 * 30.4375)) + 0.6 * np.sin(2 * np.pi * t / (31 * 30.4375) + 1)
    seasonal = 2.5 * np.cos(2 * np.pi * yr) + 0.7 * np.sin(4 * np.pi * yr)
    fast = 0.3 * np.sin(2 * np.pi * t / (4.3 * 30.4375))
    return 22 + enso + seasonal + fast


def test_weekly_and_monthly_agree_on_the_same_signal():
    cfg = load_config()
    months = np.arange(np.datetime64("1990-01"), np.datetime64("2020-01"))
    first = months.astype("datetime64[D]")
    mid = first + ((months + np.timedelta64(1, "M")).astype("datetime64[D]") - first) / 2
    ym = months.astype(int)
    rec = series.Record("nino12", 1970 + ym // 12, ym % 12 + 1, _signal(mid),
                        np.zeros(len(mid), bool), "", "")
    ps = phasespace.compute(rec, cfg.dataset("nino12"),
                            replace(cfg.filter, window_start="1990-01", window_end="2019-12"))

    week = np.arange(np.datetime64("1989-12-27"), np.datetime64("2020-01-01"), np.timedelta64(7, "D"))
    wrec = weekly.WeeklyRecord(week, {c: _signal(week) for c in weekly.COLUMNS})
    wp = weekly.compute(wrec, "nino12", "absolute", cfg.filter)
    assert wp.window["n_years"] == 30

    x = (mid - week[0]).astype(float)
    xw = (wp.week - week[0]).astype(float)
    ok = (x >= xw[0]) & (x <= xw[-1])
    rms = lambda a, b: float(np.sqrt(np.mean((a - b)[ok] ** 2)))
    # About 0.03 deg C and 0.025 deg C/month in practice (2% of the rate's spread).
    assert rms(np.interp(x, xw, wp.T), ps.T_month) < 0.06
    assert rms(np.interp(x, xw, wp.V), ps.V_month) < 0.05 * ps.V_month.std()


def test_the_sst_writer_owns_the_weekly_file():
    cfg = load_config()
    pub = publish.Publisher(cfg, "noaa_sst", push=False)
    assert "data/weekly/wksst.csv" in pub.data_paths
    assert "data/weekly/wksst.csv" not in publish.Publisher(cfg, "uhslc", push=False).data_paths


def test_committed_weekly_file_parses_and_matches_noaa_anomaly_closely():
    """The committed record, and the cross-check of the fitted seasonal cycle
    against NOAA's own SSTA (METHODS.md, "Weekly SST")."""
    rec = weekly.read()
    assert rec.week[0] == np.datetime64("1981-09-02")
    assert np.all(np.diff(rec.week).astype(int) == 7)
    wp = weekly.compute(rec, "nino12", "absolute", load_config().filter)
    i0 = int(np.searchsorted(rec.week, wp.week[0]))
    noaa = rec.values["nino12_anom"][i0:i0 + len(wp.week)]
    ours = wp.observed_anomaly
    # Different base periods (window vs 1991 to 2020): compare after removing each mean.
    assert np.sqrt(np.mean(((ours - ours.mean()) - (noaa - noaa.mean())) ** 2)) < 0.12
