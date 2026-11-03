"""Download every dataset and write data/series/<key>.csv.

    python -m enso.fetch            # all datasets
    python -m enso.fetch callao     # some of them

A dataset whose new record would end earlier than the committed one is held
(the old file stays), so a partial server response never moves the site
back in time. Other datasets are still updated.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from enso import download, series
from enso.config import ROOT, SERIES_DIR, Config, Dataset, load_config

LEGACY_SST_FILE = ROOT / "data" / "sst1950_1981.txt"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def fetch_noaa_sst(ds: Dataset, cfg: Config) -> series.Record:
    raw = download.load_sst(local_file=str(LEGACY_SST_FILE), ano_inicio=cfg.filter.base_year)
    col = ds.source["column"]
    return series.Record(
        key=ds.key,
        year=raw["IYR"],
        month=raw["MES"],
        value=raw[col],
        gap_filled=np.zeros(len(raw[col]), dtype=bool),
        source=f"NOAA CPC sstoi.indices, column {col}",
        fetched=_today(),
    )


def fetch_uhslc(ds: Dataset, cfg: Config) -> series.Record:
    src = ds.source
    raw = download.load_sea_level(
        station_id=src["station"],
        station_name=ds.label,
        start_date=src["start_date"],
        rqd_url=src.get("rqd_url"),
    )
    gaps = raw.get("GAP")
    if gaps is None:
        gaps = np.zeros(len(raw["SL0"]), dtype=bool)
    return series.Record(
        key=ds.key,
        year=raw["IYR"],
        month=raw["MES"],
        value=raw["SL0"],
        gap_filled=np.asarray(gaps, dtype=bool),
        source=f"UHSLC station {src['station']} ({raw.get('source') or 'erddap'})",
        fetched=_today(),
    )


# Source type (config.yaml datasets[].source.type) -> fetcher.
SOURCES = {
    "noaa_sst": fetch_noaa_sst,
    "uhslc": fetch_uhslc,
}


def fetch_one(ds: Dataset, cfg: Config, directory: Path = SERIES_DIR) -> str:
    """Fetch one dataset; return a one-line status."""
    record = SOURCES[ds.source["type"]](ds, cfg)
    if series.path_for(ds.key, directory).exists():
        old = series.read(ds.key, directory)
        if record.last_period < old.last_period:
            return (f"HELD   {ds.key}: new record ends {record.last_period}, "
                    f"committed one ends {old.last_period}")
    series.write(record, directory)
    return f"OK     {ds.key}: {len(record)} months through {record.last_period}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("keys", nargs="*", help="dataset keys (default: all)")
    args = parser.parse_args(argv)
    cfg = load_config()
    wanted = args.keys or [d.key for d in cfg.datasets]
    failed = 0
    for key in wanted:
        ds = cfg.dataset(key)
        try:
            print(fetch_one(ds, cfg), flush=True)
        except Exception as exc:  # one bad source must not stop the others
            failed += 1
            print(f"FAILED {key}: {exc}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
