# El Niño phase space

ENSO records (NOAA CPC sea surface temperature indices and UHSLC tide gauges)
drawn as phase diagrams: each filtered record against its own rate of change.

Pages: **Phase diagrams** (one record, loop linked to its time series),
**Compare** (up to three records on one normalised plane) and **Duffing**
(precomputed runs of a forced double-well model). How every number is made:
[METHODS.md](METHODS.md).

Successor to [el_nino](https://github.com/uferreira/el_nino), with a simpler
design: **all calculations and figures are made in Python**; the pages only
draw the JSON that Python writes, with a small `site.js`.

## How it fits together

```
config.yaml            filter, datasets, events: the only settings file
data/series/*.csv      monthly records, committed (fetch writes, build reads)
data/model/*.npz       Duffing runs, committed (python -m enso.model writes, build reads)
src/enso/
  download.py          NOAA and UHSLC downloads (ported from el_nino)
  fourier.py           Fourier low-pass filter and derivative (ported)
  window.py            analysis window (ported)
  phasespace.py        record -> filtered (T, dT/dt)
  model.py             python -m enso.model: Duffing runs -> data/model
  fetch.py             python -m enso.fetch: download -> data/series
  build.py             python -m enso.build: data/series -> docs/
  site/
    theme.py           the palette: tokens.css and Plotly templates, light and dark
    registry.py        Page, Panel, Control, Option
    pages/phase.py     Phase diagrams (figures, readout, events, provisional end)
    pages/compare.py   Compare (normalised records, combined by slot in the browser)
    pages/duffing.py   Duffing (trajectory and Poincaré section per run)
    templates/         Jinja2 HTML
    static/            site.css, site.js
docs/                  the published site (generated; do not edit by hand)
tests/                 pytest, including a Playwright browser test
```

## Commands

```bash
pip install -e ".[test]"
python -m playwright install chromium     # for the browser tests and screenshots

python -m enso.fetch                       # download all datasets (UHSLC takes minutes)
python -m enso.fetch callao                # or some of them
python -m enso.model                       # Duffing runs whose cache is missing or stale (about 1 min)
python -m enso.build                       # rebuild docs/ (offline, deterministic)
python scripts/hindcast.py                 # evidence for the provisional zone (METHODS.md)
python -m pytest                           # tests
python scripts/screenshots.py screenshots  # desktop/phone x light/dark PNGs
```

A dataset whose new download would end earlier than the committed record is
held, and the other datasets still update.

## Extending

- **A dataset**: add an entry under `datasets:` in `config.yaml`. If its
  `source.type` is new, add a fetcher to `SOURCES` in `src/enso/fetch.py`.
  It then appears in the selector, under its group, with its own data file.
- **A panel**: add a `Panel` to a page in `src/enso/site/pages/`. A panel of an
  existing `kind` needs no JavaScript; a new kind needs one renderer in `site.js`.
- **A page**: add a module to `src/enso/site/pages/` with a `page(cfg)` function
  and list it in `PAGE_MODULES`; it joins the navigation.

## Publishing

GitHub Pages serves `docs/` from `main`. CI fails if `docs/` differs from a fresh
build of the committed code and data.

## Updates

- **SST** (NOAA CPC): `.github/workflows/update-sst.yml` runs at 06:00 UTC every
  5 days (days 1, 6, 11, 16, 21, 26 and 31 of each month) and on demand. It
  fetches the SST datasets, rebuilds the site, runs the analysis and build
  tests, and commits `data/series` and `docs` only if a record changed.
  A failed download keeps the committed record and turns the run red.
- **Sea level** (UHSLC): not automated yet. UHSLC drops connections from
  GitHub-hosted runners, so it needs another route (to be decided). Until
  then: `python -m enso.fetch --source-type uhslc && python -m enso.build`,
  then commit `data/series` and `docs`.
