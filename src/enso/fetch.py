"""Download every dataset and write data/series/<key>.csv.

    python -m enso.fetch            # all datasets
    python -m enso.fetch callao     # some of them

    python -m enso.fetch --source-type noaa_sst     # by source (the CI SST update)

A dataset whose new record would end earlier than the committed one is held
(the old file stays), so a partial server response never moves the site
back in time. A download with the same values leaves the file untouched, so
its "fetched" date is when the data last changed and an update with nothing
new commits nothing. Other datasets are always tried. Exit code 1 if any
download failed.
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
        if series.data_lines(record) == series.data_lines(old):
            return f"SAME   {ds.key}: no change, still through {old.last_period}"
    series.write(record, directory)
    return f"OK     {ds.key}: {len(record)} months through {record.last_period}"


def keys_for(cfg: Config, source_type: str | None) -> list[str]:
    return [d.key for d in cfg.datasets if source_type in (None, d.source["type"])]


def fetch_many(keys: list[str], cfg: Config) -> list[tuple[str, str]]:
    """Fetch each dataset; one failure never stops the others. Returns
    (key, status line) pairs; the line starts with OK, SAME, HELD or FAILED."""
    results = []
    for key in keys:
        ds = cfg.dataset(key)
        try:
            line = fetch_one(ds, cfg)
        except Exception as exc:  # one bad source must not stop the others
            line = f"FAILED {key}: {exc}"
        print(line, flush=True)
        results.append((key, line))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("keys", nargs="*", help="dataset keys (default: all)")
    parser.add_argument("--source-type", choices=sorted(SOURCES),
                        help="only the datasets with this source type")
    args = parser.parse_args(argv)
    cfg = load_config()
    results = fetch_many(args.keys or keys_for(cfg, args.source_type), cfg)
    return 1 if any(line.startswith("FAILED") for _, line in results) else 0


if __name__ == "__main__":
    sys.exit(main())
