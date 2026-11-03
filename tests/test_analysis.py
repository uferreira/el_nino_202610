"""Window, series files and phase-space analysis."""

import numpy as np
import pytest

from enso import fetch, series
from enso.config import CADENCES, load_config
from enso.fourier import deri_fourier, passa_baixa
from enso.phasespace import compute, month_label
from enso.window import resolve_fourier_window, select_fourier_window

CFG = load_config()


def _record(key="synthetic", start=(1970, 1), n=600, values=None, gaps=None):
    y0, m0 = start
    serial = np.arange(n) + y0 * 12 + (m0 - 1)
    t = np.arange(n)
    if values is None:
        values = 20 + 2 * np.sin(2 * np.pi * t / 12) + np.sin(2 * np.pi * t / 48)
    return series.Record(
        key=key,
        year=(serial // 12).astype(np.int32),
        month=(serial % 12 + 1).astype(np.int32),
        value=np.asarray(values, float),
        gap_filled=np.zeros(n, bool) if gaps is None else gaps,
        source="test",
        fetched="2026-11-03",
    )


# ---- window -------------------------------------------------------------

def test_default_window_spans_whole_cycles_from_base_year():
    rec = _record(start=(1970, 1), n=12 * 56 + 9)        # ends 2026-09
    w = resolve_fourier_window(rec.year, rec.month, base_year=1975)
    assert (w["start"], w["end"]) == ("1975-10", "2026-09")
    assert w["whole_cycles"] and w["n_months"] % 12 == 0


def test_window_rejects_a_calendar_gap():
    rec = _record(n=48)
    year, month = rec.year.copy(), rec.month.copy()
    year[20:], month[20:] = year[21:].tolist() + [2100], month[21:].tolist() + [1]
    with pytest.raises(ValueError, match="continuous"):
        select_fourier_window(year, month, rec.value)


# ---- series files -------------------------------------------------------

def test_series_file_round_trip(tmp_path):
    rec = _record(n=30, gaps=np.arange(30) % 7 == 0)
    series.write(rec, tmp_path)
    back = series.read("synthetic", tmp_path)
    assert back.last_period == rec.last_period
    np.testing.assert_allclose(back.value, rec.value, atol=5e-5)
    assert (back.gap_filled == rec.gap_filled).all()
    assert (back.source, back.fetched) == ("test", "2026-11-03")


def test_fetch_holds_a_record_that_would_move_back(tmp_path, monkeypatch):
    ds = CFG.dataset("nino12")
    series.write(_record("nino12", n=100), tmp_path)
    monkeypatch.setitem(fetch.SOURCES, "noaa_sst", lambda ds, cfg: _record("nino12", n=90))
    assert fetch.fetch_one(ds, CFG, tmp_path).startswith("HELD")
    assert len(series.read("nino12", tmp_path)) == 100

    monkeypatch.setitem(fetch.SOURCES, "noaa_sst", lambda ds, cfg: _record("nino12", n=101))
    assert fetch.fetch_one(ds, CFG, tmp_path).startswith("OK")
    assert len(series.read("nino12", tmp_path)) == 101


def test_fetch_leaves_an_unchanged_record_alone(tmp_path, monkeypatch):
    """Same values: the file (and its fetched date) is not rewritten."""
    ds = CFG.dataset("nino12")
    old = _record("nino12", n=100)
    old.fetched = "2026-01-01"
    series.write(old, tmp_path)
    monkeypatch.setitem(fetch.SOURCES, "noaa_sst", lambda ds, cfg: _record("nino12", n=100))
    assert fetch.fetch_one(ds, CFG, tmp_path).startswith("SAME")
    assert series.read("nino12", tmp_path).fetched == "2026-01-01"


def test_fetch_can_select_by_source_type(monkeypatch):
    seen = []
    monkeypatch.setattr(fetch, "fetch_one", lambda ds, cfg: seen.append(ds.key) or "OK")
    assert fetch.main(["--source-type", "noaa_sst"]) == 0
    assert seen == [d.key for d in CFG.datasets if d.source["type"] == "noaa_sst"]


# ---- committed data -----------------------------------------------------

@pytest.mark.parametrize("ds", CFG.datasets, ids=lambda d: d.key)
def test_committed_series_are_continuous_and_recent(ds):
    rec = series.read(ds.key)
    serial = rec.year.astype(int) * 12 + rec.month
    assert (np.diff(serial) == 1).all(), "months must be continuous"
    assert np.isfinite(rec.value).all()
    assert rec.year[0] <= CFG.filter.base_year
    assert ds.cadence in CADENCES


# ---- analysis -----------------------------------------------------------

def test_absolute_series_matches_the_reference_chain():
    """Climatology out, filter, climatology back, then interpolate: as the old pipeline."""
    rec = _record()
    ds = CFG.dataset("nino12")
    ps = compute(rec, ds, CFG.filter)
    year, month, values, _ = select_fourier_window(rec.year, rec.month, rec.value,
                                                   None, None, CFG.filter.base_year)
    clim = np.array([values[month == m].mean() for m in range(1, 13)])[month - 1]
    filtered = passa_baixa(CFG.filter.HN1, CFG.filter.HN2, values - clim) + clim
    T, V, _ = deri_fourier(CFG.filter.NDOTS, filtered)
    np.testing.assert_array_equal(ps.T, T)
    np.testing.assert_array_equal(ps.V, V)
    assert len(ps.T) == (ps.n_months - 1) * ps.ndots + 1


def test_anomaly_series_is_filtered_without_climatology():
    rec = _record(values=np.sin(2 * np.pi * np.arange(600) / 40))
    ps = compute(rec, CFG.dataset("nino34"), CFG.filter)
    year, month, values, _ = select_fourier_window(rec.year, rec.month, rec.value,
                                                   None, None, CFG.filter.base_year)
    T, _, _ = deri_fourier(CFG.filter.NDOTS, passa_baixa(CFG.filter.HN1, CFG.filter.HN2, values))
    np.testing.assert_array_equal(ps.T, T)


def test_sea_level_is_shown_relative_to_its_window_mean():
    rec = _record(values=1100 + 80 * np.sin(2 * np.pi * np.arange(600) / 50))
    ps = compute(rec, CFG.dataset("callao"), CFG.filter)
    assert abs(ps.T.mean()) < 1e-9
    assert ps.offset == pytest.approx(1100, abs=10)
    assert ps.observed.mean() == pytest.approx(rec.value[-ps.n_months:].mean() - ps.offset)


def test_month_label():
    assert month_label("1997-03") == "Mar 1997"
    assert month_label("2026-09", short=False) == "September 2026"
