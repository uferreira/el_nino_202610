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
data/status/*.json     date of each dataset's last successful download (sea level)
src/enso/
  download.py          NOAA and UHSLC downloads (ported from el_nino)
  fourier.py           Fourier low-pass filter and derivative (ported)
  window.py            analysis window (ported)
  phasespace.py        record -> filtered (T, dT/dt)
  model.py             python -m enso.model: Duffing runs -> data/model
  fetch.py             python -m enso.fetch: download -> data/series
  publish.py           python -m enso.publish: fetch, build, test, commit, push (both updaters)
  status.py            python -m enso.status: is a source being updated?
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
python scripts/lyapunov_sweep.py           # lambda1 against FA, El Niño fit (5 min; pip install -e ".[scripts]")
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

Two writers share `main`, every 5 days each:

| Records | Where | How |
|---|---|---|
| SST (NOAA CPC) | GitHub Actions, `.github/workflows/update-sst.yml`, 06:00 UTC on days 1, 6, 11, 16, 21, 26 and 31, and on demand | `python -m enso.publish --source-type noaa_sst` |
| Sea level (UHSLC) | this PC, Windows Task Scheduler (UHSLC drops connections from GitHub-hosted runners) | `scripts\update_sea_level.ps1`, which runs `python -m enso.publish --source-type uhslc --status` |

`enso.publish` pulls, downloads its own source, rebuilds `docs/`, runs the
non-browser tests, and commits only its own files: its
`data/series/*.csv`, its `data/status/*.json` and `docs/` (rebuilt from scratch, so
either writer can regenerate it). Any other change stops the run. It then
does `git pull --rebase`, rebuilds, and pushes; if the rebase conflicts or the
push is rejected, it resets to the remote, puts its own data back, rebuilds
and pushes once more, and otherwise stops with exit code 2 and
`PUBLISH FAILED` in the log. A failed download keeps the committed record
(exit code 1; the rest is still published).

**Staleness check.** Every sea-level run writes `data/status/uhslc.json`
(the date each station was last downloaded), so it commits every 5 days
even with no new data. The SST workflow runs
`python -m enso.status --check uhslc --max-age-days 15` and turns red when
any station is older than 15 days: the PC has not run, or a station keeps
failing.

### Sea-level task: setup

Once, in a normal PowerShell in the repository folder:

```powershell
py -3.12 -m venv .venv                       # or any Python >= 3.10
.venv\Scripts\python.exe -m pip install -e ".[test]"
git config user.name; git push --dry-run     # git identity set, push works without a prompt

powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\install_sea_level_task.ps1
```

The task runs every 5 days at 07:30, and **as soon as possible after a
missed start**, so a PC that was off catches up when it is next on. It needs
a network connection and runs as you, only while you are logged on (git
uses your stored credentials). Options: `-At 08:00`, `-WakeToRun` (wake from
sleep), `-Python C:\path\to\python.exe` (another interpreter; the
`ENSO_PYTHON` environment variable works too; the default is `.venv`),
`-Remove` (uninstall).

### Sea-level task: by hand and recovery

```powershell
Start-ScheduledTask -TaskName 'el_nino_202610 sea level update'     # run the task now
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\update_sea_level.ps1           # same, in this window
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\update_sea_level.ps1 -NoPush   # commit locally only
Get-Content logs\update-sea-level.log -Tail 40                       # what happened
Get-ScheduledTaskInfo -TaskName 'el_nino_202610 sea level update'    # last and next run, last result
```

Without PowerShell: `python -m enso.publish --source-type uhslc --status`.

- **"uncommitted changes"**: the run never starts on a dirty tree. Commit or
  stash your own work, then run it again.
- **"git pull --rebase failed before the update"**: a local commit conflicts
  with the remote. Inspect with `git status` and `git log @{u}..`; usually
  `git reset --hard @{u}` (drops the local commit) and run again.
- **"git push failed twice"**: the commit is kept locally; the next run
  pulls, rebuilds and pushes it. Check that `git push` works by hand.
- **"the tests failed on the new data"**: nothing was committed and the tree
  was restored; the log shows the failing test.
- **SST run red at "Check that sea level is being updated"**: the PC task has
  not succeeded for 15 days. Check `Get-ScheduledTaskInfo` and the log, then
  run it by hand.
