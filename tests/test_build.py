"""The built site: files, figures, readout, registry. (Model runs: test_model.py.)"""

import json
import re
from dataclasses import replace

import numpy as np
import pytest

from enso import model, series
from enso.build import build
from enso.config import load_config
from enso.phasespace import compute
from enso.site.pages import all_pages, phase
from enso.site.registry import Control, Option

CFG = load_config()
P = CFG.filter.provisional_months
ROLES_LOOP = {"history", "highlight", "recent", "now", "cursor", "hover"}
ROLES_TIME = {"series", "anomaly", "highlight", "recent", "now", "cursor"}


def _load(site, rel):
    return json.loads((site / rel).read_text(encoding="utf-8"))


def _phase(site, key):
    return _load(site, f"data/phase/{key}.json")


def _html(site, name="index.html"):
    return (site / name).read_text(encoding="utf-8")


# ---- pages and navigation -------------------------------------------------

def test_three_pages_in_navigation_order(site):
    for name in ("index.html", "compare.html", "duffing.html"):
        nav = re.findall(r'<nav class="site-nav".*?</nav>', _html(site, name), re.S)[0]
        assert re.findall(r'href="([^"]+)"', nav) == ["index.html", "compare.html", "duffing.html"]
        assert nav.count('aria-current="page"') == 1


def test_selector_lists_all_datasets_grouped(site):
    groups = re.findall(r'<optgroup label="([^"]+)">(.*?)</optgroup>', _html(site), re.S)
    assert [g for g, _ in groups] == ["Sea surface temperature", "Sea level"]
    values = [v for _, body in groups for v in re.findall(r'value="([^"]+)"', body)]
    assert values == [d.key for d in CFG.datasets]


def test_event_buttons_come_from_config(site):
    assert re.findall(r'data-event="([^"]+)"', _html(site)) == [e.label for e in CFG.events]
    assert "2025-26" in [e.label for e in CFG.events]


def test_running_event_is_selected_when_past_threshold(site):
    latest = float(phase.phase_series(CFG, CFG.current_event.dataset).observed_anomaly[-1])
    expected = latest >= CFG.current_event.threshold
    assert ('data-default-event="2025-26"' in _html(site)) == expected
    # and not when the threshold is above the latest anomaly
    high = replace(CFG, current_event=replace(CFG.current_event, threshold=latest + 1))
    assert phase.default_event(high) == {}


# ---- phase page data --------------------------------------------------------

def test_every_dataset_gets_one_data_file(site):
    files = sorted(p.stem for p in (site / "data/phase").glob("*.json"))
    assert files == sorted(d.key for d in CFG.datasets)


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_figures_carry_roles_and_no_colours(site, key):
    data = _phase(site, key)
    loop, time = data["figures"]["phase"], data["figures"]["time"]
    assert {t["meta"]["role"] for t in loop["data"]} == ROLES_LOOP
    assert {t["meta"]["role"] for t in time["data"]} == ROLES_TIME
    for fig in (loop, time):
        assert "color" not in json.dumps(fig["layout"]), "colours belong to theme.json"
        assert "template" not in fig["layout"]


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_loop_is_square_and_arrays_line_up(site, key):
    data = _phase(site, key)
    loop = data["figures"]["phase"]
    m = loop["layout"]["margin"]
    assert m["l"] + m["r"] == m["t"] + m["b"]
    n, k = len(data["periods"]), data["ndots"]
    assert len(data["loop"]["x"]) == (n - 1) * k + 1
    hover = next(t for t in loop["data"] if t["meta"]["role"] == "hover")
    assert hover["x"] == data["loop"]["x"][::k]
    anomaly = next(t for t in data["figures"]["time"]["data"] if t["meta"]["role"] == "anomaly")
    assert anomaly["x"] == data["periods"]


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_history_is_drawn_in_yearly_paths_for_density(site, key):
    data = _phase(site, key)
    paths = [t for t in data["figures"]["phase"]["data"]
             if t["meta"]["role"] == "history" and not t["meta"].get("provisional")]
    assert len(paths) == -(-(len(data["periods"]) - P) // 12)   # one per 12 months
    assert all(t["line"]["width"] <= 1.0 for t in paths)


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_provisional_end_is_dashed_and_shaded(site, key):
    data = _phase(site, key)
    n, k = len(data["periods"]), data["ndots"]
    p = data["provisional_from"]
    assert p == n - P and data["provisional_months"] == P
    prov = [t for t in data["figures"]["phase"]["data"] if t["meta"].get("provisional")]
    assert prov and all("dash" in t["line"] for t in prov)
    hist_prov = next(t for t in prov if t["meta"]["role"] == "history")
    assert hist_prov["x"] == data["loop"]["x"][p * k:]
    shade = next(s for s in data["figures"]["time"]["layout"]["shapes"] if s.get("name") == "provisional")
    assert shade["x0"] == data["periods"][p]
    labels = [a["text"] for a in data["figures"]["time"]["layout"]["annotations"]]
    assert any("provisional" in t for t in labels)


@pytest.mark.parametrize("key", ["nino12", "callao", "nino34"])
def test_anomaly_axis_has_the_same_scale_as_the_series(site, key):
    layout = _phase(site, key)["figures"]["time"]["layout"]
    cycle = CFG.dataset(key).quantity != "anomaly"
    if cycle:
        left, right = layout["yaxis"]["range"], layout["yaxis2"]["range"]
        assert left[1] - left[0] == pytest.approx(right[1] - right[0])
        assert layout["yaxis"]["dtick"] == layout["yaxis2"]["dtick"]
        assert layout["yaxis2"]["overlaying"] == "y"
    else:
        assert "overlaying" not in json.dumps(layout)


@pytest.mark.parametrize("key", ["nino12", "callao", "nino34"])
def test_readout_shows_the_observation_and_a_provisional_rate(site, key):
    data = _phase(site, key)
    ds = CFG.dataset(key)
    ps = compute(series.read(key), ds, CFG.filter)
    now = data["now"]
    decimals = 2 if ds.unit == "°C" else 0
    assert now["observed"] == f"{ps.observed[-1]:.{decimals}f} {ds.unit}".replace("-", "−")
    assert ps.T[-1] == pytest.approx(ps.observed[-1])        # the filter's end is the observation
    assert "provisional" in now["note"]
    assert (now["anomaly"] is None) == (ds.quantity == "anomaly")
    assert now["state"] in {"Warming", "Cooling", "Rising", "Falling"}


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_event_indices_point_at_the_event_months(site, key):
    data = _phase(site, key)
    for ev, cfg_ev in zip(data["events"], CFG.events):
        assert data["periods"][ev["i0"]] == cfg_ev.start
        end = cfg_ev.end or data["periods"][-1]
        assert data["periods"][ev["i1"]] == end


# ---- compare --------------------------------------------------------------

def test_compare_has_one_file_per_record_and_a_frame(site):
    files = sorted(p.stem for p in (site / "data/compare").glob("*.json"))
    assert files == sorted([d.key for d in CFG.datasets] + ["model", "frame"])


@pytest.mark.parametrize("key", ["nino12", "callao", "model"])
def test_compare_uses_y_over_sigma_x(site, key):
    data = _load(site, f"data/compare/{key}.json")
    x, y = np.array(data["loop"]["x"]), np.array(data["loop"]["y"])
    assert abs(x.mean()) < 1e-3 and x.std(ddof=1) == pytest.approx(1, abs=1e-3)
    if key != "model":
        ps = phase.phase_series(CFG, key)
        sigma = ps.T.std(ddof=1)
        np.testing.assert_allclose(y, ps.V / sigma, atol=1e-4)
    for t in data["traces"]["loop"] + data["traces"]["time"]:
        assert "color" not in json.dumps(t)          # coloured by slot in the browser


def test_compare_section_has_one_dot_per_year_and_month(site):
    data = _load(site, "data/compare/callao.json")
    months = [int(p[5:7]) for p in data["periods"]]
    for m in range(12):
        (trace,) = data["traces"]["section"][m]
        assert len(trace["x"]) == months.count(m + 1)


def test_compare_model_has_no_provisional_part(site):
    data = _load(site, "data/compare/model.json")
    assert data["provisional_from"] is None
    assert not any(t["meta"].get("provisional") and t["x"] for t in data["traces"]["loop"])


def test_compare_slots_and_defaults(site):
    html = _html(site, "compare.html")
    for name in ("a", "b", "c"):
        assert f'name="{name}" data-control' in html
    assert re.search(r'name="c" data-control>\s*<option value="none" selected', html)


# ---- duffing --------------------------------------------------------------

def test_duffing_writes_every_run_and_phase(site):
    m = CFG.models["duffing"]
    trajectories = list((site / "data/duffing/trajectory").rglob("*.json"))
    sections = list((site / "data/duffing/section").rglob("*.json"))
    assert len(trajectories) == len(m["presets"]) * len(m["fa_factors"])
    assert len(sections) == len(trajectories) * m["phases"]


@pytest.mark.parametrize("preset", ["alado", "chaos"])
def test_duffing_section_is_one_dot_per_cycle(site, preset):
    data = _load(site, f"data/duffing/section/{preset}/1/0.json")
    (trace,) = data["figure"]["data"]
    assert len(trace["x"]) == model.settings(CFG, preset)["section_cycles"]
    assert "one trajectory" in data["count"]


def test_duffing_section_axes_do_not_move_between_phases(site):
    ranges = {json.dumps(_load(site, f"data/duffing/section/chaos/1/{j}.json")["figure"]["layout"]["xaxis"]["range"])
              for j in range(12)}
    assert len(ranges) == 1


def test_duffing_reports_the_lyapunov_class_and_its_convergence(site):
    data = _load(site, "data/duffing/trajectory/alado/1.5.json")
    assert data["facts"]["regime"]["class"] == "periodic"
    assert data["facts"]["lambda"].startswith("\u2212")
    data = _load(site, "data/duffing/trajectory/chaos/1.json")
    assert data["facts"]["regime"]["class"] == "chaotic"
    assert data["facts"]["lambda"].startswith("+")
    assert "Running estimate" in data["facts"]["convergence"]
    assert "DOP853" in data["facts"]["convergence"]
    assert 1.5 < float(data["facts"]["dimension"].split()[0]) < 2.0
    assert _load(site, "data/duffing/trajectory/alado/1.5.json")["facts"]["dimension"] == "0"
    sec = _load(site, "data/duffing/section/chaos/1/0.json")
    assert sec["regime"]["class"] == "chaotic"


def test_duffing_section_axes_are_the_union_of_all_phases(site):
    import numpy as np
    run = model.load(CFG, "alado", 1.0, compute_missing=False)
    lo, hi = run.section[..., 0].min(), run.section[..., 0].max()
    xr = _load(site, "data/duffing/section/alado/1/0.json")["figure"]["layout"]["xaxis"]["range"]
    span = hi - lo
    assert xr == pytest.approx([lo - 0.04 * span, hi + 0.04 * span], abs=1e-4)   # 4 decimals


def test_compare_time_strip_is_the_normalised_anomaly_without_the_model(site):
    import numpy as np
    callao = _load(site, "data/compare/callao.json")
    (series_t, _) = callao["traces"]["time"]
    y = np.array(series_t["y"])
    assert abs(y.mean()) < 0.05 and y.std(ddof=1) == pytest.approx(1, abs=1e-3)
    ps = phase.phase_series(CFG, "callao")
    np.testing.assert_allclose(y, ps.anomaly / ps.anomaly.std(ddof=1), atol=1e-3)
    model_rec = _load(site, "data/compare/model.json")
    assert model_rec["traces"]["time"] == [] and model_rec["calendar"] is False


# ---- whole site -----------------------------------------------------------

def test_no_dashes_in_generated_text(site):
    """House style: no em or en dashes anywhere a reader can see."""
    for path in site.rglob("*"):
        if path.suffix in {".html", ".json", ".css", ".js"}:
            text = path.read_text(encoding="utf-8")
            assert chr(0x2014) not in text and chr(0x2013) not in text, path.name


def test_theme_json_has_both_themes_and_every_role(site):
    theme = _load(site, "data/theme.json")
    assert set(theme) == {"light", "dark"}
    for t in theme.values():
        assert ROLES_LOOP | ROLES_TIME | {"points", "dot"} <= set(t["roles"])
        assert set(t["slots"]) == {"A", "B", "C"}
        assert t["template"]["layout"]["xaxis"]["showgrid"] is False


def test_build_is_deterministic(site, tmp_path):
    build(tmp_path)
    for path in site.rglob("*"):
        if path.is_file():
            assert (tmp_path / path.relative_to(site)).read_bytes() == path.read_bytes(), path


def test_data_files_stay_small(site):
    for path in (site / "data").rglob("*.json"):
        assert path.stat().st_size < 250_000, path.name


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
    assert dict(panel.controls[0].groups())["Sea surface temperature"][-1].value == "nino12_weekly"


def test_page_level_controls_reach_the_panels():
    duffing = next(p for p in all_pages(CFG) if p.slug == "duffing")
    sec = duffing.panels[1]
    choices = list(sec.choices(duffing.controls))
    m = CFG.models["duffing"]
    assert len(choices) == len(m["presets"]) * len(m["fa_factors"]) * m["phases"]
    assert set(choices[0]) == {"preset", "fa", "phase"}


def test_control_rejects_duplicates_and_unknown_default():
    with pytest.raises(ValueError):
        Control("ds", "Dataset", [Option("a", "A"), Option("a", "A2")], "a")
    with pytest.raises(ValueError):
        Control("ds", "Dataset", [Option("a", "A")], "b")


def test_float_noise_does_not_reach_the_output():
    from enso.build import stable
    assert stable({"a": [0.1 + 0.2, -1e-17, 2], "b": (1.23456789,), "c": True, "d": "x"}) == \
        {"a": [0.3, 0.0, 2], "b": [1.2346], "c": True, "d": "x"}
    assert str(stable(-1e-17)) == "0.0"          # no "-0.0"
    assert stable(0.1235) == 0.1235              # values already at 4 decimals stay put


def test_docs_check_compares_numbers_within_the_tolerance():
    from enso.build import TOLERANCE, json_differences
    a = {"x": [1.0, 2.0], "s": "t", "n": 3}
    assert json_differences(a, {"x": [1.0001, 2.0], "s": "t", "n": 3}) == []   # a boundary flip
    assert json_differences(a, {"x": [1.001, 2.0], "s": "t", "n": 3}) == ["/x[0]: 1.0 != 1.001"]
    assert json_differences(a, {"x": [1.0], "s": "t", "n": 3}) == ["/x: length 2 != 1"]
    assert json_differences(a, {"x": [1.0, 2.0], "s": "u", "n": 3}) == ["/s: 't' != 'u'"]
    assert TOLERANCE < 1e-3


def test_installed_versions_match_constraints():
    """docs/ must be built on the pinned versions (constraints.txt)."""
    import sys
    from importlib.metadata import version
    from pathlib import Path
    if sys.version_info < (3, 11):
        pytest.skip("the pins need Python 3.11 or newer")
    lines = (Path(__file__).resolve().parents[1] / "constraints.txt").read_text().splitlines()
    pins = [ln.split(";")[0].strip().split("==") for ln in lines if "==" in ln and not ln.startswith("#")]
    wrong = [f"{n} {version(n)} (pinned {v})" for n, v in pins if version(n) != v]
    assert not wrong, "pip install -e '.[test]' -c constraints.txt: " + ", ".join(wrong)
