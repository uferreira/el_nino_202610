"""When was each dataset last downloaded successfully?

    python -m enso.status --check uhslc --max-age-days 15

data/status/<source type>.json is written by an update run that asks for it
(``python -m enso.publish --status``; the sea-level task on the PC does). For
each dataset it keeps the date of the last successful download (``checked``:
the server answered and the record was written or found unchanged), and the
result and date of the last attempt.

``--check`` exits 1, naming the datasets, when any of them has not been
checked for more than ``--max-age-days`` days, or was never checked. The SST
workflow runs it, so a PC that stopped updating sea level turns a GitHub run
red. The build never reads these files: they change no page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from enso.config import ROOT, load_config

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", metavar="SOURCE_TYPE", required=True)
    ap.add_argument("--max-age-days", type=int, default=15)
    args = ap.parse_args(argv)
    cfg = load_config()
    keys = [d.key for d in cfg.datasets if d.source["type"] == args.check]
    problems = stale(args.check, keys, args.max_age_days)
    for p in problems:
        print(f"::error::stale {p}" if "GITHUB_ACTIONS" in os.environ else f"STALE  {p}")
    if not problems:
        print(f"{args.check}: all {len(keys)} datasets downloaded within {args.max_age_days} days")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
