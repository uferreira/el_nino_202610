"""Build the static site into docs/ from data/series/*.csv.

    python -m enso.build              # writes docs/
    python -m enso.build --out DIR    # somewhere else (tests use this)

    python -m enso.build --check      # is docs/ what the committed code and data give?

No network access: everything comes from the committed series files.

Platform stability: the same files give the same output on any machine up to
float noise (about 1e-15: OpenBLAS picks its kernels by CPU, which changes the
order of sums in the filter). Every float is rounded to ``DECIMALS`` places
just before it is written, which is coarser than any series needs (they use
1 to 4) and far above the noise, and ``--check`` compares the parsed JSON
within one step of that last place, so a value that falls on a rounding
boundary cannot fail it.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from enso import series, status, weekly
from enso.config import DOCS_DIR, Config, load_config
from enso.site import theme
from enso.site.pages import all_pages

SITE_DIR = Path(__file__).resolve().parent / "site"
PLOTLY_JS = "https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@4.1.1/plotly-basic.min.js"
GENERATED = ("data", "assets", ".nojekyll")  # removed and rewritten on every build
DECIMALS = 4                  # every float in the JSON output
TOLERANCE = 1.5 * 10.0 ** -DECIMALS   # --check: one step of the last place, plus slack


def stable(obj):
    """``obj`` with every float rounded to DECIMALS places (and -0.0 as 0.0),
    so float noise between machines does not reach the output."""
    if isinstance(obj, float):
        return round(obj, DECIMALS) + 0.0
    if isinstance(obj, dict):
        return {k: stable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [stable(v) for v in obj]
    return obj


def _write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(stable(obj), separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    path.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%b %Y}"


def _footer(cfg: Config) -> dict:
    fetched = sorted({(weekly.read() if d.is_weekly else series.read(d.key)).fetched
                      for d in cfg.datasets})
    # Per group, the oldest "last checked" date of its datasets (data/status).
    days: dict[str, list[str]] = {}
    for d in cfg.datasets:
        day = status.read(d.source["type"])["datasets"].get(d.key, {}).get("checked", "")
        days.setdefault(d.group.label, []).append(day)
    parts = []
    for i, (label, group_days) in enumerate(days.items()):
        name = label if i == 0 else label[0].lower() + label[1:]
        oldest = min(group_days)          # "" (never recorded) sorts first
        parts.append(f"{name} {_day(oldest) if oldest else 'never recorded'}")
    f = cfg.filter
    return {
        "filter": f"Fourier low-pass, HN1 = {f.HN1:g}, HN2 = {f.HN2:g} "
                  f"(full periods under about {2 * f.HN2:g} to {2 * f.HN1:g} months removed)",
        "fetched": _day(fetched[-1]) if fetched else "unknown",
        "checked": ", ".join(parts),
    }


def build(out: Path = DOCS_DIR, cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in GENERATED:
        p = out / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    for old in out.glob("*.html"):
        old.unlink()

    pages = all_pages(cfg)
    sizes: dict[str, int] = {}

    # Data: the JSON files each panel declares.
    written: dict[str, int] = {}
    for page in pages:
        for panel in page.panels:
            for rel, make in panel.outputs(page.controls).items():
                if rel in written:      # shared by two panels: build once
                    continue
                written[rel] = sizes[rel] = _write_json(out / rel, make())

    # Assets.
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for f in (SITE_DIR / "static").iterdir():
        shutil.copyfile(f, assets / f.name)
    (assets / "tokens.css").write_text(theme.tokens_css(), encoding="utf-8", newline="\n")
    (out / "data" / "theme.json").write_text(theme.theme_json(), encoding="utf-8", newline="\n")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    # Pages.
    env = Environment(loader=FileSystemLoader(SITE_DIR / "templates"),
                      autoescape=True, undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True)
    footer = _footer(cfg)
    for page in pages:
        nav = [{"label": p.nav_label, "href": p.filename, "current": p is page} for p in pages]
        html = env.get_template(page.template).render(
            site=cfg.site, cfg=cfg, page=page, nav=nav, footer=footer, plotly_js=PLOTLY_JS,
        )
        (out / page.filename).write_text(html, encoding="utf-8", newline="\n")
        sizes[page.filename] = len(html.encode("utf-8"))
    return sizes


def json_differences(a, b, path: str = "", tol: float = TOLERANCE) -> list[str]:
    """Where two parsed JSON values differ, numbers compared within ``tol``."""
    if isinstance(a, bool) or isinstance(b, bool):
        return [] if a is b else [f"{path}: {a!r} != {b!r}"]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return [] if math.isclose(a, b, rel_tol=0.0, abs_tol=tol) else [f"{path}: {a!r} != {b!r}"]
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return [f"{path}: keys {sorted(a.keys() ^ b.keys())} in one only"]
        return [d for k in a for d in json_differences(a[k], b[k], f"{path}/{k}", tol)]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [d for i, (u, v) in enumerate(zip(a, b)) for d in json_differences(u, v, f"{path}[{i}]", tol)]
    return [] if a == b else [f"{path}: {str(a)[:60]!r} != {str(b)[:60]!r}"]


def check(docs: Path = DOCS_DIR) -> list[str]:
    """Build into a temporary folder and compare with ``docs``: JSON by
    value (within TOLERANCE), every other file byte for byte."""
    docs = Path(docs)
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        build(fresh)
        files = lambda root: {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
        have, want = files(docs), files(fresh)
        problems += [f"{f}: not in a fresh build" for f in sorted(have - want)]
        problems += [f"{f}: missing (run python -m enso.build)" for f in sorted(want - have)]
        for f in sorted(have & want):
            a, b = (docs / f).read_bytes(), (fresh / f).read_bytes()
            if a == b:
                continue
            if f.endswith(".json"):
                diffs = json_differences(json.loads(a), json.loads(b))
                problems += [f"{f}{d}" for d in diffs[:5]]
                if len(diffs) > 5:
                    problems.append(f"{f}: and {len(diffs) - 5} more")
            else:
                problems.append(f"{f}: differs")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DOCS_DIR)
    parser.add_argument("--check", action="store_true",
                        help="compare --out with a fresh build instead of writing it")
    args = parser.parse_args(argv)
    if args.check:
        problems = check(args.out)
        for p in problems:
            print(p)
        print(f"{args.out}: {'differs from' if problems else 'matches'} a fresh build "
              f"(JSON numbers within {TOLERANCE:g})")
        return 1 if problems else 0
    sizes = build(args.out)
    for rel, n in sorted(sizes.items()):
        print(f"{n / 1024:8.1f} KB  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
