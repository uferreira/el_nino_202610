"""Weekly SST indices (NOAA CPC ``wksst9120.for``) and their phase-space analysis.

    python -m enso.weekly            # download and write data/weekly/wksst.csv

The source
----------
https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for: OISST v2 weekly
means for NINO1+2, NINO3, NINO3.4 and NINO4, each as SST and SSTA (anomaly
against 1991 to 2020), one row per week from the week centred on
2 September 1981. Every date is a Wednesday, the centre of a Sunday to
Saturday week. The layout is fixed width and a negative SSTA touches the SST
before it (``20.6-0.1``), so the rows are cut by column, never split on
blanks::

     Week          SST SSTA     SST SSTA     SST SSTA     SST SSTA
     02SEP1981     20.6-0.1     24.8-0.1     26.5-0.2     28.3-0.3
    ^ date [1:10], then per region i = 0..3: SST [10+13i : 19+13i],
                                             SSTA [19+13i : 23+13i]

The analysis
------------
The same method as the monthly records (enso.phasespace), in weekly units:

1. The window spans whole years and starts at the same seasonal phase as
   its last week (:func:`whole_year_window`), as a monthly window starts in
   the month after its end month.
2. ``absolute`` (NINO1+2 SST): the window's seasonal cycle is removed, the
   anomaly is low-pass filtered and the cycle is added back. The weekly
   seasonal cycle is a least-squares fit of a mean plus ``harmonics``
   annual harmonics on the day of the year (:func:`seasonal_cycle`), the
   counterpart of the monthly climatology. NOAA's own SSTA is used only to
   cross-check it. ``anomaly``: NOAA's SSTA column is filtered directly.
3. passa_baixa and deri_fourier count in samples, so the cutoffs become
   weeks: HN1 = 10 x 30.4375 / 7 = 43.48, HN2 = 9 x 30.4375 / 7 = 39.13.
   NDOTS = 1 (a week is already finer than the monthly 5 points per month).
   deri_fourier returns a rate per week; it is multiplied by 30.4375 / 7 to
   give the same unit as the monthly record, unit per month.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from enso.config import ROOT, FilterParams
from enso.fourier import compute_sigma, deri_fourier, passa_baixa

URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
WEEKLY_FILE = ROOT / "data" / "weekly" / "wksst.csv"

DAYS_PER_MONTH = 30.4375          # 365.25 / 12
DAYS_PER_YEAR = 365.2425          # mean Gregorian year
WEEKS_PER_MONTH = DAYS_PER_MONTH / 7.0

# Column order of the source file, and the names used here and in the CSV.
REGIONS = ("nino12", "nino3", "nino34", "nino4")
COLUMNS = tuple(name for r in REGIONS for name in (r, f"{r}_anom"))
# Monthly dataset key (config.yaml) -> weekly columns (value, anomaly).
DATASET_COLUMNS = {r: (r, f"{r}_anom") for r in REGIONS}

_HEADER = "Week          SST SSTA     SST SSTA     SST SSTA     SST SSTA"
_ROW_LEN = 62


# -- the file -------------------------------------------------------------

@dataclass
class WeeklyRecord:
    week: np.ndarray            # datetime64[D], the Wednesday each week is centred on
    values: dict[str, np.ndarray]
    source: str = URL
    fetched: str = ""

    @property
    def last_week(self) -> str:
        return str(self.week[-1])

    def __len__(self) -> int:
        return len(self.week)


def parse(text: str) -> WeeklyRecord:
    """Parse ``wksst9120.for``. Raises ValueError on any surprise in the layout
    (a changed header, a short row, a skipped or repeated week), so a format
    change stops the update instead of writing wrong numbers."""
    lines = [ln.rstrip("\r") for ln in text.splitlines()]
    try:
        h = next(i for i, ln in enumerate(lines) if ln.split()[:1] == ["Week"])
    except StopIteration:
        raise ValueError("weekly SST file: no 'Week  SST SSTA ...' header line") from None
    if " ".join(lines[h].split()) != " ".join(_HEADER.split()):
        raise ValueError(f"weekly SST file: unexpected header {lines[h]!r}")
    weeks, rows = [], []
    for n, ln in enumerate(lines[h + 1:], start=h + 2):
        if not ln.strip():
            continue
        if len(ln.rstrip()) != _ROW_LEN:
            raise ValueError(f"weekly SST file line {n}: expected {_ROW_LEN} characters, "
                             f"got {len(ln.rstrip())}: {ln!r}")
        weeks.append(datetime.strptime(ln[1:10], "%d%b%Y").date())
        rows.append([float(ln[a:b]) for i in range(4)
                     for a, b in ((10 + 13 * i, 19 + 13 * i), (19 + 13 * i, 23 + 13 * i))])
    if not rows:
        raise ValueError("weekly SST file holds no weeks")
    week = np.array(weeks, dtype="datetime64[D]")
    step = np.diff(week).astype(int)
    if np.any(step != 7):
        bad = int(np.argmax(step != 7))
        raise ValueError(f"weekly SST file: {week[bad]} is followed by {week[bad + 1]}, "
                         "not by the next week")
    data = np.array(rows)
    return WeeklyRecord(week, {c: data[:, i] for i, c in enumerate(COLUMNS)})


def data_lines(rec: WeeklyRecord) -> list[str]:
    return [",".join([str(w), *(f"{rec.values[c][i]:.1f}" for c in COLUMNS)])
            for i, w in enumerate(rec.week)]


def write(rec: WeeklyRecord, path: Path = WEEKLY_FILE) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# source: {rec.source} (week = the Wednesday each week is centred on; "
             "anomalies against 1991 to 2020)",
             f"# fetched: {rec.fetched}",
             ",".join(["week", *COLUMNS]),
             *data_lines(rec)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def read(path: Path = WEEKLY_FILE) -> WeeklyRecord:
    meta, weeks, rows = {}, [], []
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        if ln.startswith("#"):
            k, _, v = ln[1:].partition(":")
            meta[k.strip()] = v.strip()
        elif ln.strip() and not ln.startswith("week"):
            first, *rest = ln.split(",")
            weeks.append(first)
            rows.append([float(x) for x in rest])
    data = np.array(rows)
    return WeeklyRecord(np.array(weeks, dtype="datetime64[D]"),
                        {c: data[:, i] for i, c in enumerate(COLUMNS)},
                        URL, meta.get("fetched", ""))


def fetch(path: Path = WEEKLY_FILE) -> str:
    """Download, parse and write the weekly file; return a status line that
    starts with OK, SAME or HELD, as enso.fetch does for the monthly records."""
    from enso import download
    resp = download._fetch(URL, "NOAA weekly SST indices (wksst9120.for)")
    rec = parse(resp.text)
    rec.fetched = datetime.now(timezone.utc).date().isoformat()
    path = Path(path)
    if path.exists():
        old = read(path)
        if rec.last_week < old.last_week:
            return f"HELD   weekly: new record ends {rec.last_week}, committed one ends {old.last_week}"
        if data_lines(rec) == data_lines(old):
            return f"SAME   weekly: no change, still through {old.last_week}"
    write(rec, path)
    return f"OK     weekly: {len(rec)} weeks through {rec.last_week}"


# -- the analysis ---------------------------------------------------------

def weekly_cutoffs(params: FilterParams) -> tuple[float, float]:
    """The monthly HN1, HN2 (months) in weeks."""
    return params.HN1 * WEEKS_PER_MONTH, params.HN2 * WEEKS_PER_MONTH


def months_to_weeks(months: float) -> int:
    return int(round(months * WEEKS_PER_MONTH))


def whole_year_window(week: np.ndarray, end=None, not_before=None) -> tuple[int, int, dict]:
    """Indices [i0, i1] of the longest whole-year window ending at ``end``
    (default: the last week) and starting no earlier than ``not_before``.

    A window of N years ends at week E and starts at the week nearest to
    E + 7 days - N mean years, so its first week has the same seasonal phase
    as the week after its last one (the monthly rule "start in the month
    after the end month"). Weeks do not divide a year, so the span is a whole
    number of years to within half a week.
    """
    week = np.asarray(week, dtype="datetime64[D]")
    i1 = len(week) - 1 if end is None else int(np.searchsorted(week, np.datetime64(end, "D"), "right")) - 1
    if i1 < 0:
        raise ValueError(f"no week at or before {end}")
    first = week[0] if not_before is None else max(week[0], np.datetime64(not_before, "D"))
    e = week[i1].astype(np.int64)
    n_years = int((e + 7 - first.astype(np.int64)) // DAYS_PER_YEAR)
    while n_years >= 1:
        target = e + 7 - n_years * DAYS_PER_YEAR
        i0 = int(np.argmin(np.abs(week.astype(np.int64) - target)))
        if week[i0] >= first:
            break
        n_years -= 1
    else:
        raise ValueError("the weekly window must span at least one year")
    return i0, i1, {"start": str(week[i0]), "end": str(week[i1]), "n_weeks": i1 - i0 + 1,
                    "n_years": n_years}


def year_phase(week: np.ndarray) -> np.ndarray:
    """Day of the year as a fraction of the mean year (0 at 1 January 2000).
    Measured on the 365.2425-day mean year, so leap days add no jump."""
    days = (np.asarray(week, dtype="datetime64[D]") - np.datetime64("2000-01-01")).astype(float)
    return days / DAYS_PER_YEAR


def seasonal_cycle(week: np.ndarray, values: np.ndarray, harmonics: int,
                   at: np.ndarray | None = None) -> np.ndarray:
    """Least-squares mean plus ``harmonics`` annual harmonics of ``values``,
    evaluated at ``at`` (default: at ``week``). The weekly counterpart of
    the monthly climatology: both are the window's mean seasonal cycle."""
    def design(w):
        p = 2 * np.pi * year_phase(w)
        cols = [np.ones_like(p)]
        for k in range(1, harmonics + 1):
            cols += [np.cos(k * p), np.sin(k * p)]
        return np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(design(week), np.asarray(values, float), rcond=None)
    return design(week if at is None else at) @ coef


@dataclass
class WeeklyPhase:
    week: np.ndarray              # datetime64[D], one per sample in the window
    T: np.ndarray                 # filtered value (seasonal cycle kept for absolute)
    V: np.ndarray                 # dT/dt, unit per MONTH
    observed: np.ndarray
    anomaly: np.ndarray           # filtered anomaly (before the cycle is re-added)
    observed_anomaly: np.ndarray  # observed minus the window's seasonal cycle
    cycle: np.ndarray             # the seasonal cycle removed (zeros for anomaly)
    sigma_filter: float           # SIGMA30: RMS(filtered - observed)
    window: dict


def compute(rec: WeeklyRecord, dataset: str, quantity: str, params: FilterParams,
            harmonics: int = 4, end=None, not_before=None) -> WeeklyPhase:
    """Weekly counterpart of enso.phasespace.compute for one region.

    ``dataset`` is a monthly key (nino12, nino3, nino34, nino4); ``quantity``
    is ``absolute`` (filter the SST around the window's fitted seasonal
    cycle) or ``anomaly`` (filter NOAA's SSTA directly)."""
    col_value, col_anom = DATASET_COLUMNS[dataset]
    i0, i1, window = whole_year_window(rec.week, end, not_before)
    week = rec.week[i0:i1 + 1]
    if quantity == "absolute":
        values = rec.values[col_value][i0:i1 + 1]
        cycle = seasonal_cycle(week, values, harmonics)
    elif quantity == "anomaly":
        values = rec.values[col_anom][i0:i1 + 1]
        cycle = np.zeros_like(values)
    else:
        raise ValueError(f"weekly analysis supports absolute and anomaly, not {quantity!r}")
    hn1, hn2 = weekly_cutoffs(params)
    anomaly = passa_baixa(hn1, hn2, values - cycle)
    filtered = anomaly + cycle
    T, V_week, _ = deri_fourier(1, filtered)
    sigma, _ = compute_sigma(values, filtered, T, 1)
    window["harmonics"] = harmonics if quantity == "absolute" else 0
    return WeeklyPhase(week, T, V_week * WEEKS_PER_MONTH, values, anomaly,
                       values - cycle, cycle, float(sigma), window)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", type=Path, default=WEEKLY_FILE)
    args = ap.parse_args(argv)
    try:
        print(fetch(args.file))
    except Exception as exc:
        print(f"FAILED weekly: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
