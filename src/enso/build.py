"""Build the static site into docs/ from data/series/*.csv.

    python -m enso.build              # writes docs/
    python -m enso.build --out DIR    # somewhere else (tests use this)

No network access: everything comes from the committed series files, and
the same files always give the same output (CI checks docs/ is current).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from enso import series
from enso.config import DOCS_DIR, Config, load_config
from enso.site import theme
from enso.site.pages import all_pages

SITE_DIR = Path(__file__).resolve().parent / "site"
PLOTLY_JS = "https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@4.1.1/plotly-basic.min.js"
GENERATED = ("data", "assets", ".nojekyll")  # removed and rewritten on every build


def _write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    path.write_text(text, encoding="utf-8", newline="\n")
    return len(text.encode("utf-8"))


def _footer(cfg: Config) -> dict:
    fetched = sorted({series.read(d.key).fetched for d in cfg.datasets})
    f = cfg.filter
    return {
        "filter": f"Fourier low-pass, HN1 = {f.HN1:g}, HN2 = {f.HN2:g} "
                  f"(full periods under about {2 * f.HN2:g} to {2 * f.HN1:g} months removed)",
        "fetched": fetched[-1] if fetched else "",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DOCS_DIR)
    args = parser.parse_args(argv)
    sizes = build(args.out)
    for rel, n in sorted(sizes.items()):
        print(f"{n / 1024:8.1f} KB  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
