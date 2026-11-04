"""When was each dataset last downloaded successfully, and is the site behind its source?

    python -m enso.status --check uhslc --max-age-days 15
    python -m enso.status --behind noaa_sst

data/status/<source type>.json is written by an update run that asks for it
(``python -m enso.publish --status``; the sea-level task on the PC does). For
each dataset it keeps the date of the last successful download (``checked``:
the server answered and the record was written or found unchanged), and the
result and date of the last attempt.

``--check`` exits 1, naming the datasets, when any of them has not been
checked for more than ``--max-age-days`` days, or was never checked. The SST
workflow runs it, so a PC that stopped updating sea level turns a GitHub run
red. The build reads ``checked`` for the "last checked" date in each
page's readout and footer, so a source that stopped updating shows on the site.

``--behind`` downloads the source's latest month (NOAA CPC: the last row of
sstoi.indices) and exits 1, naming the datasets, when the source has a later
month than the site serves (docs/data/phase/<key>.json). The SST workflow
runs it after every update, so a month NOAA has and the site lacks turns
that run red.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from enso.config import DOCS_DIR, ROOT, load_config

STATUS_DIR = ROOT / "data" / "status"
SUCCESS = ("OK", "SAME")      # a HELD record (server behind us) is not fresh


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def path_for(source_type: str, directory: Path = STATUS_DIR) -> Path:
    return Path(directory) / f"{source_type}.json"


def read(source_type: str, directory: Path = STATUS_DIR) -> dict:
    path = path_for(source_type, directory)
    if not path.exists():
        return {"source_type": source_type, "datasets": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def record(source_type: str, results: list[tuple[str, str]], day: str | None = None,
           directory: Path = STATUS_DIR) -> Path:
    """Update the status file from fetch results ((key, status line) pairs)."""
    day = day or today()
    data = read(source_type, directory)
    for key, line in results:
        word = line.split()[0] if line.strip() else "FAILED"
        entry = data["datasets"].get(key, {})
        entry["last_attempt"] = day
        entry["last_result"] = word
        if word in SUCCESS:
            entry["checked"] = day
        data["datasets"][key] = entry
    data["datasets"] = dict(sorted(data["datasets"].items()))
    path = path_for(source_type, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    return path


def stale(source_type: str, keys: list[str], max_age_days: int, day: str | None = None,
          directory: Path = STATUS_DIR) -> list[str]:
    """One line per dataset not checked within ``max_age_days``."""
    now = date.fromisoformat(day or today())
    entries = read(source_type, directory)["datasets"]
    problems = []
    for key in keys:
        e = entries.get(key, {})
        if "checked" not in e:
            problems.append(f"{key}: never downloaded by an update with --status")
            continue
        age = (now - date.fromisoformat(e["checked"])).days
        if age > max_age_days:
            problems.append(f"{key}: last downloaded {e['checked']} ({age} days ago); "
                            f"last attempt {e.get('last_attempt', '?')}: {e.get('last_result', '?')}")
    return problems


def checked_label(source_type: str, key: str, directory: Path = STATUS_DIR) -> str | None:
    """'4 Nov 2026': the last successful download of ``key``, or None if never recorded."""
    day = read(source_type, directory)["datasets"].get(key, {}).get("checked")
    if not day:
        return None
    d = date.fromisoformat(day)
    return f"{d.day} {d:%b %Y}"


# ---- Is the site behind its source? ------------------------------------------

def noaa_sst_latest() -> str:
    """Latest month in NOAA CPC's sstoi.indices, as 'YYYY-MM'."""
    from enso import download
    text = download._fetch(download.NOAA_SST_URL, "NOAA SST indices (sstoi.indices)").text
    return latest_in_sstoi(text)


def latest_in_sstoi(text: str) -> str:
    months = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            months.append((int(parts[0]), int(parts[1])))
    if not months:
        raise ValueError("no data rows in sstoi.indices")
    y, m = max(months)
    return f"{y:04d}-{m:02d}"


UPSTREAM = {"noaa_sst": noaa_sst_latest}   # source type -> latest month at the source


def site_latest(key: str, docs: Path = DOCS_DIR) -> str | None:
    """Last month the site serves for ``key`` (docs/data/phase/<key>.json)."""
    path = Path(docs) / "data" / "phase" / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["periods"][-1]


def behind(source_latest: str, keys: list[str], docs: Path = DOCS_DIR) -> list[str]:
    """One line per dataset whose site record ends before ``source_latest``."""
    problems = []
    for key in keys:
        have = site_latest(key, docs)
        if have is None or have < source_latest:
            problems.append(f"{key}: the source has {source_latest}, the site ends {have or 'nowhere'}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--check", metavar="SOURCE_TYPE",
                      help="exit 1 when a dataset was not downloaded within --max-age-days")
    what.add_argument("--behind", metavar="SOURCE_TYPE", choices=sorted(UPSTREAM),
                      help="exit 1 when the source has a later month than the site")
    ap.add_argument("--max-age-days", type=int, default=15)
    args = ap.parse_args(argv)
    cfg = load_config()
    gha = "GITHUB_ACTIONS" in os.environ
    source = args.check or args.behind
    keys = [d.key for d in cfg.datasets if d.source["type"] == source]
    if args.behind:
        latest = UPSTREAM[source]()
        problems = behind(latest, keys)
        for p in problems:
            print(f"::error::site behind {p}" if gha else f"BEHIND {p}")
        if not problems:
            print(f"{source}: the site has the source's latest month ({latest}) for all {len(keys)} datasets")
        return 1 if problems else 0
    problems = stale(source, keys, args.max_age_days)
    for p in problems:
        print(f"::error::stale {p}" if gha else f"STALE  {p}")
    if not problems:
        print(f"{source}: all {len(keys)} datasets downloaded within {args.max_age_days} days")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
