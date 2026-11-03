"""The built site: files, figures, readout, registry."""

import json
import re

import numpy as np
import pytest

from enso import series
from enso.build import build
from enso.config import load_config
from enso.phasespace import compute
from enso.site.pages import all_pages
from enso.site.registry import Control, Option

CFG = load_config()
ROLES_LOOP = {"history", "highlight", "recent", "now", "cursor", "hover"}
ROLES_TIME = {"series", "highlight", "recent", "now", "cursor"}


def _load(site, key):
    return json.loads((site / f"data/phase/{key}.json").read_text(encoding="utf-8"))


def test_every_dataset_gets_one_data_file(site):
    files = sorted(p.stem for p in (site / "data/phase").glob("*.json"))
    assert files == sorted(d.key for d in CFG.datasets)


def test_landing_page_is_the_phase_page(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert "<h1>Phase diagrams</h1>" in html
    assert 'aria-current="page"' in html


def test_selector_lists_all_datasets_grouped(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    groups = re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', html, re.S)
    assert [g for g, _ in groups] == ["Sea surface temperature", "Sea level"]
    values = [v for _, body in groups for v in re.findall(r'value="([^"]+)"', body)]
    assert values == [d.key for d in CFG.datasets]


def test_event_buttons_come_from_config(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert re.findall(r'data-event="([^"]+)"', html) == [e.label for e in CFG.events]


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_figures_carry_roles_and_no_colours(site, key):
    data = _load(site, key)
    loop, time = data["figures"]["phase"], data["figures"]["time"]
    assert {t["meta"]["role"] for t in loop["data"]} == ROLES_LOOP
    assert {t["meta"]["role"] for t in time["data"]} == ROLES_TIME
    for fig in (loop, time):
        text = json.dumps(fig["layout"])
        assert "color" not in text, "colours belong to theme.json, not the figure"
        assert "template" not in fig["layout"]


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_loop_plot_area_is_square_and_arrays_line_up(site, key):
    data = _load(site, key)
    loop = data["figures"]["phase"]
    m = loop["layout"]["margin"]
    assert m["l"] + m["r"] == m["t"] + m["b"]
    n, k = len(data["periods"]), data["ndots"]
    by_role = {t["meta"]["role"]: t for t in loop["data"]}
    assert len(by_role["history"]["x"]) == (n - 1) * k + 1
    assert len(by_role["hover"]["x"]) == n
    # hover targets sit on the monthly points of the loop
    assert by_role["hover"]["x"] == by_role["history"]["x"][::k]
    series_T = [t for t in data["figures"]["time"]["data"]
                if t["meta"] == {"role": "series", "row": "T"}][0]
    assert series_T["x"] == data["periods"]


@pytest.mark.parametrize("key", ["nino12", "callao"])
def test_readout_matches_the_last_point(site, key):
    data = _load(site, key)
    ps = compute(series.read(key), CFG.dataset(key), CFG.filter)
    now = data["now"]
    unit = CFG.dataset(key).unit
    decimals = 2 if unit == "°C" else 0
    assert now["value"] == f"{ps.T[-1]:.{decimals}f} {unit}".replace("-", "−")
    assert now["rising"] == bool(ps.V[-1] >= 0)
    assert now["state"] in {"Warming", "Cooling", "Rising", "Falling"}


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_event_indices_point_at_the_event_months(site, key):
    data = _load(site, key)
    for ev, cfg_ev in zip(data["events"], CFG.events):
        assert data["periods"][ev["i0"]] == cfg_ev.start
        assert data["periods"][ev["i1"]] == cfg_ev.end


def test_no_dashes_in_generated_text(site):
    """House style: no em or en dashes anywhere a reader can see."""
    for path in site.rglob("*"):
        if path.suffix in {".html", ".json", ".css", ".js"}:
            text = path.read_text(encoding="utf-8")
            assert chr(0x2014) not in text and chr(0x2013) not in text, path.name


def test_theme_json_has_both_themes_and_every_role(site):
    theme = json.loads((site / "data/theme.json").read_text(encoding="utf-8"))
    assert set(theme) == {"light", "dark"}
    for t in theme.values():
        assert ROLES_LOOP | ROLES_TIME <= set(t["roles"])
        assert t["template"]["layout"]["xaxis"]["showgrid"] is False


def test_build_is_deterministic(site, tmp_path):
    build(tmp_path)
    for path in site.rglob("*"):
        if path.is_file():
            assert (tmp_path / path.relative_to(site)).read_bytes() == path.read_bytes(), path


def test_data_files_stay_small(site):
    for path in (site / "data/phase").glob("*.json"):
        assert path.stat().st_size < 200_000, path.name


def test_a_new_option_is_one_registry_entry():
    """Adding e.g. a weekly NINO1+2 is one more Option: the panel then yields
    one more choice, and so one more data file."""
    panel = all_pages(CFG)[0].panels[0]
    before = list(panel.choices())
    ctrl = panel.controls[0]
    panel.controls[0] = Control(ctrl.name, ctrl.label,
                                ctrl.options + [Option("nino12_weekly", "NINO1+2 weekly", "Sea surface temperature")],
                                ctrl.default)
    after = list(panel.choices())
    assert len(after) == len(before) + 1
    assert panel.path_for(after[-1]) == "data/phase/nino12_weekly.json"
    groups = dict(panel.controls[0].groups())
    assert groups["Sea surface temperature"][-1].value == "nino12_weekly"


def test_control_rejects_duplicates_and_unknown_default():
    with pytest.raises(ValueError):
        Control("ds", "Dataset", [Option("a", "A"), Option("a", "A2")], "a")
    with pytest.raises(ValueError):
        Control("ds", "Dataset", [Option("a", "A")], "b")
