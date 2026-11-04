"""Observed record -> filtered phase-space trajectory (T, dT/dt).

Steps (as in el_nino/src/el_nino/pipeline.py and the old site):

1. Cut the record to the analysis window (enso.window).
2. ``absolute`` and ``record_mean``: remove the monthly climatology, low-pass
   filter the anomaly, add the climatology back. ``anomaly``: the source
   already removed the seasonal cycle, so filter the values directly.
3. Fourier-interpolate to NDOTS points per month and differentiate.
4. ``record_mean``: subtract the window mean of the interpolated series, so
   sea level is shown relative to its own mean.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from enso.config import Dataset, FilterParams
from enso.fourier import compute_sigma, deri_fourier, passa_baixa
from enso.series import Record
from enso.window import select_fourier_window

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


@dataclass
class PhaseSeries:
    dataset: Dataset
    ndots: int
    periods: list[str]        # "YYYY-MM", one per month in the window
    T: np.ndarray             # fine grid, (n_months - 1) * ndots + 1 points
    V: np.ndarray             # dT/dt on the fine grid, unit per month
    observed: np.ndarray      # monthly observations, same offset as T
    anomaly: np.ndarray       # monthly filtered anomaly (before the climatology is re-added)
    observed_anomaly: np.ndarray  # monthly observations minus the window climatology
    gap_filled: np.ndarray    # monthly, bool
    window: dict
    offset: float             # value subtracted from the observations (record_mean)
    sigma_filter: float       # RMS(filtered - observed)
    fetched: str
    source: str
    cadence: str = "monthly"  # weekly: periods are "YYYY-MM-DD" (a Wednesday), ndots is 1

    @property
    def n_months(self) -> int:
        """Samples in the window (months, or weeks for a weekly record)."""
        return len(self.periods)

    @property
    def weekly(self) -> bool:
        return self.cadence == "weekly"

    @property
    def year_points(self) -> int:
        """Loop points in one year: the length of a history path."""
        return 52 * self.ndots if self.weekly else 12 * self.ndots

    @property
    def recent(self) -> int:
        """Samples in the latest 12 months (52 weeks)."""
        return 52 if self.weekly else 12

    @property
    def has_seasonal_cycle(self) -> bool:
        return self.dataset.quantity != "anomaly"

    @property
    def T_month(self) -> np.ndarray:
        return self.T[:: self.ndots]

    @property
    def V_month(self) -> np.ndarray:
        return self.V[:: self.ndots]

    def month_index(self, period: str) -> int | None:
        try:
            return self.periods.index(period)
        except ValueError:
            return None


def climatology(month: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Mean of each calendar month, indexed 0..11."""
    present = set(np.unique(month).tolist())
    missing = sorted(set(range(1, 13)) - present)
    if missing:
        raise ValueError(f"climatology requires all 12 calendar months; missing {missing}")
    return np.array([values[month == m].mean() for m in range(1, 13)])


def compute(record: Record, ds: Dataset, params: FilterParams) -> PhaseSeries:
    year, month, values, window = select_fourier_window(
        record.year, record.month, record.value,
        params.window_start, params.window_end, params.base_year,
    )
    keep = np.isin(record.year * 12 + record.month, year * 12 + month)
    gaps = record.gap_filled[keep]

    if ds.quantity == "anomaly":
        clim = np.zeros_like(values)
    else:
        clim = climatology(month, values)[month - 1]
    filtered_anomaly = passa_baixa(params.HN1, params.HN2, values - clim)
    filtered = filtered_anomaly + clim

    T, V, _accel = deri_fourier(params.NDOTS, filtered)
    sigma_filter, _ = compute_sigma(values, filtered, T, params.NDOTS)

    offset = float(T.mean()) if ds.quantity == "record_mean" else 0.0
    return PhaseSeries(
        dataset=ds,
        ndots=params.NDOTS,
        periods=[f"{y:04d}-{m:02d}" for y, m in zip(year.tolist(), month.tolist())],
        T=T - offset,
        V=V,
        observed=values - offset,
        anomaly=filtered_anomaly,
        observed_anomaly=values - clim,
        gap_filled=gaps,
        window=window,
        offset=offset,
        sigma_filter=float(sigma_filter),
        fetched=record.fetched,
        source=record.source,
    )


def month_label(period: str, short: bool = True) -> str:
    """"Oct 2026" for a month, "28 Oct 2026" for a week's date."""
    y, m, *d = period.split("-")
    name = MONTH_NAMES[int(m) - 1]
    day = f"{int(d[0])} " if d else ""
    return f"{day}{name[:3] if short else name} {y}"
