"""The observed records, one small CSV per dataset in data/series/.

These files are the hand-off between fetching (network, slow, flaky) and
building the site (offline, fast, tested). They are committed, so any
checkout can rebuild the site without downloading anything.

Format::

    # dataset: callao
    # source: UHSLC station 093 (erddap)
    # fetched: 2026-11-03
    period,value,gap_filled
    1970-01,1101.36,0

``period`` is "YYYY-MM" for monthly data. ``gap_filled`` is 1 when the
value was reconstructed from neighbouring months.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from enso.config import SERIES_DIR


@dataclass
class Record:
    key: str
    year: np.ndarray        # int
    month: np.ndarray       # int, 1..12
    value: np.ndarray       # float
    gap_filled: np.ndarray  # bool
    source: str
    fetched: str            # ISO date of the download

    @property
    def last_period(self) -> str:
        return f"{int(self.year[-1]):04d}-{int(self.month[-1]):02d}"

    def __len__(self) -> int:
        return len(self.value)


def path_for(key: str, directory: Path = SERIES_DIR) -> Path:
    return Path(directory) / f"{key}.csv"


def write(record: Record, directory: Path = SERIES_DIR) -> Path:
    path = path_for(record.key, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# dataset: {record.key}",
        f"# source: {record.source}",
        f"# fetched: {record.fetched}",
        "period,value,gap_filled",
    ]
    for y, m, v, g in zip(record.year, record.month, record.value, record.gap_filled):
        lines.append(f"{int(y):04d}-{int(m):02d},{float(v):.4f},{int(bool(g))}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def read(key: str, directory: Path = SERIES_DIR) -> Record:
    path = path_for(key, directory)
    meta: dict[str, str] = {}
    years, months, values, gaps = [], [], [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            name, _, val = line[1:].partition(":")
            meta[name.strip()] = val.strip()
            continue
        if not line.strip() or line.startswith("period"):
            continue
        period, value, gap = line.split(",")
        y, m = period.split("-")
        years.append(int(y))
        months.append(int(m))
        values.append(float(value))
        gaps.append(gap.strip() == "1")
    if not values:
        raise ValueError(f"{path} holds no observations")
    return Record(
        key=meta.get("dataset", key),
        year=np.array(years, dtype=np.int32),
        month=np.array(months, dtype=np.int32),
        value=np.array(values, dtype=np.float64),
        gap_filled=np.array(gaps, dtype=bool),
        source=meta.get("source", ""),
        fetched=meta.get("fetched", ""),
    )
