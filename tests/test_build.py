"""The built site: files, figures, readout, registry. (Model runs: test_model.py.)"""

import json
import re
from dataclasses import replace

import numpy as np
import pytest

from enso import model, series, weekly
from enso.build import build
from enso.config import load_config
from enso.phasespace import compute
from enso.site.pages import all_pages, phase
from enso.site.registry import Control, Option

CFG = load_config()
P = CFG.filter.provisional_months
PW = weekly.provisional_weeks(CFG.filter)      # the same span in weeks: 43


def _p(key):
    """Samples in the provisional zone, and in a year, of dataset ``key``."""
    return (PW, 52) if CFG.dataset(key).is_weekly else (P, 12)
ROLES_LOOP = {"history", "highlight", "trace", "tail", "head", "recent", "now", "cursor", "hover"}
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
    prov, year = _p(key)
    assert len(paths) == -(-(len(data["periods"]) - prov) // year)   # one per 12 months (52 weeks)
    assert all(t["line"]["width"] <= 1.0 for t in paths)


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_provisional_end_is_dashed_and_shaded(site, key):
    data = _phase(site, key)
    n, k = len(data["periods"]), data["ndots"]
    p = data["provisional_from"]
    prov, _ = _p(key)
    assert p == n - prov and data["provisional_samples"] == prov and data["provisional_months"] == P
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
    months = [p[:7] for p in data["periods"]]          # a week belongs to its month
    for ev, cfg_ev in zip(data["events"], CFG.events):
        assert months[ev["i0"]] == cfg_ev.start and (ev["i0"] == 0 or months[ev["i0"] - 1] < cfg_ev.start)
        end = cfg_ev.end or months[-1]
        assert months[ev["i1"]] == end and (ev["i1"] == len(months) - 1 or months[ev["i1"] + 1] > end)


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


# ---- the weekly dataset -----------------------------------------------------

def test_weekly_dataset_sits_after_nino12_in_the_sst_group(site):
    keys = [d.key for d in CFG.datasets]
    assert keys[:2] == ["nino12", "nino12w"] and CFG.dataset("nino12w").group.key == "sst"
    assert CFG.datasets[0].key == "nino12" == CFG.current_event.dataset       # monthly stays the default
    assert 'value="nino12" selected' in _html(site) or re.search(r'<option value="nino12" selected', _html(site))
    assert "NINO1+2 weekly" in _html(site)


def test_weekly_phase_data_is_in_weeks_with_a_43_week_provisional_zone(site):
    data = _phase(site, "nino12w")
    n = len(data["periods"])
    assert (data["ndots"], data["play"]["unit"], data["play"]["step"], data["play"]["tail"]) == (1, 1, 1, 52)
    assert data["periods"][0] == "1981-11-04" and data["periods"][-1] == str(weekly.read().week[-1])
    assert PW == 43 and data["provisional_from"] == n - 43 and data["provisional_span"] == "43 weeks"
    assert len(data["loop"]["x"]) == n and data["window"].endswith(f"{n} weeks")
    # weekly dates, one Wednesday per week
    d = np.array(data["periods"], dtype="datetime64[D]")
    assert (np.diff(d).astype(int) == 7).all()
    # speeds are in weeks per second, with a default that is one of them
    play = data["play"]
    assert play["unit_name"] == "week" and play["speed_default"] in [o["value"] for o in play["speeds"]]
    assert all(o["label"].endswith("weeks/s") for o in play["speeds"])
    assert _phase(site, "nino12")["play"]["speeds"][1] == {"value": "6", "label": "6 months/s"}
    # the shaded zone and the dashed loop start at the same week
    shade = next(s for s in data["figures"]["time"]["layout"]["shapes"] if s.get("name") == "provisional")
    assert shade["x0"] == data["periods"][-43]


def test_weekly_readout_names_the_week_and_the_provisional_zone(site):
    now = _phase(site, "nino12w")["now"]
    rec = weekly.read()
    assert now["month"].startswith("Week centred on ") and now["through"].startswith(str(int(str(rec.week[-1])[8:10])))
    assert now["observed"] == f"{rec.values['nino12'][-1]:.2f} °C" and "43 weeks" in now["note"]
    assert now["rate"].endswith("°C/month") and now["checked"] and now["checked"] != "never recorded"
    assert now["source_name"] == "NOAA CPC"


def test_weekly_events_cover_the_same_months_as_monthly(site):
    w, m = _phase(site, "nino12w"), _phase(site, "nino12")
    assert [e["label"] for e in w["events"]] == [e["label"] for e in m["events"]]
    assert [e["range"] for e in w["events"]] == [e["range"] for e in m["events"]]
    for e in w["events"]:           # about 4.35 weeks per month
        assert e["i1"] > e["i0"]


def test_weekly_time_hover_shows_the_date(site):
    traces = _phase(site, "nino12w")["figures"]["time"]["data"]
    assert all("%d %b %Y" in t["hovertemplate"] for t in traces if t["meta"]["role"] in ("anomaly",))


def test_compare_weekly_record_has_a_calendar_map(site):
    w, f = _load(site, "data/compare/nino12w.json"), _load(site, "data/compare/frame.json")
    k = f["play"]["step"]
    m = _load(site, "data/compare/nino12.json")
    assert w["weekly"] is True and m["cal_last"] == (len(f["calendar"]) - 1) * k    # monthly ends with its month
    # The weekly record ends a little after the middle of the last month: the calendar's points
    # run on to the one that shows its last week, and no further.
    assert w["cal_last"] > m["cal_last"] and w["cal_last"] - m["cal_last"] < k
    assert len(w["cal_map"]) == w["cal_last"] + 1
    cal = np.array(w["cal_map"])
    assert cal[0] == -1 and (np.diff(cal) >= 0).all() and cal[-1] == len(w["periods"]) - 1
    assert cal[-2] < cal[-1] or cal[-2] == cal[-1]
    assert _load(site, "data/compare/model.json")["cal_last"] is None
    # each calendar point (k per month, the first at mid-month) shows the week nearest its date
    for i in (len(cal) // 3, len(cal) // 2 + 2):
        day = np.datetime64(f["calendar"][i // k] + "-15") + np.timedelta64(round((i % k) * 30.4375 / k), "D")
        assert abs((np.datetime64(w["periods"][cal[i]]) - day).astype(int)) <= 4
    assert w["play"] == {"step": 1, "tail": 52}
    assert _load(site, "data/compare/nino12.json")["cal_map"] is None            # monthly: unchanged
    assert f["calendar"][0] == "1975-11" and f["calendar"][-1] == _phase(site, "nino12")["periods"][-1]


def test_compare_weekly_and_monthly_nino12_share_the_normalised_plane(site):
    w, m = _load(site, "data/compare/nino12w.json"), _load(site, "data/compare/nino12.json")
    xw, xm = np.array(w["loop"]["x"]), np.array(m["loop"]["x"])
    assert abs(xw.mean()) < 1e-3 and xw.std(ddof=1) == pytest.approx(1, abs=1e-3)
    assert abs(xm.mean()) < 1e-3
    assert w["extent"]["x"][0] < 0 < w["extent"]["x"][1]


def test_compare_weekly_section_has_one_dot_per_year(site):
    w = _load(site, "data/compare/nino12w.json")
    for m in range(12):
        (trace,) = w["traces"]["section"][m]
        years = trace["customdata"]
        assert len(years) == len(set(years))              # one week per year, not one per week of the month


def test_footer_and_checked_dates_cover_the_weekly_file(site):
    html = _html(site)
    assert "Sea surface temperature" in html
    from enso import status
    assert status.checked_label("noaa_sst", "nino12w")


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
    series_t = callao["traces"]["time"][0]
    y = np.array(series_t["y"])
    assert abs(y.mean()) < 0.05 and y.std(ddof=1) == pytest.approx(1, abs=1e-3)
    ps = phase.phase_series(CFG, "callao")
    np.testing.assert_allclose(y, ps.anomaly / ps.anomaly.std(ddof=1), atol=1e-3)
    model_rec = _load(site, "data/compare/model.json")
    assert model_rec["traces"]["time"] == [] and model_rec["calendar"] is False


# ---- animation --------------------------------------------------------------

def _play(fig):
    return [t for t in fig["data"] if t["meta"].get("play")]


def _play_kinds(fig):
    return sorted((t["meta"]["role"], str(t["meta"].get("provisional")), bool(t["meta"].get("dots")))
                  for t in _play(fig))


@pytest.mark.parametrize("key", [d.key for d in CFG.datasets])
def test_phase_loop_has_an_empty_play_layer_above_the_record(site, key):
    """Path so far, tail (solid and dashed), tail months and dot: empty until
    the browser fills them by slicing data.loop."""
    data = _phase(site, key)
    fig = data["figures"]["phase"]
    assert _play_kinds(fig) == sorted([("trace", "False", False), ("trace", "True", False),
                                       ("tail", "False", False), ("tail", "True", False),
                                       ("tail", "None", True), ("head", "None", False)])
    assert all(t["x"] == [] and t["y"] == [] for t in _play(fig))
    assert all("dash" in t["line"] for t in _play(fig) if t["meta"].get("provisional"))
    roles = [t["meta"]["role"] for t in fig["data"]]
    first_play = next(i for i, t in enumerate(fig["data"]) if t["meta"].get("play"))
    assert roles.index("history") < first_play < roles.index("cursor")
    k = data["ndots"]
    year = 52 if CFG.dataset(key).is_weekly else 12              # the 12-month tail, in samples
    assert {n: data["play"][n] for n in ("unit", "step", "tail")} == {"unit": k, "step": k, "tail": year * k}
    # The "now" label is named, so playing can hide it.
    assert [a.get("name") for a in fig["layout"]["annotations"]].count("now") == 1


def test_duffing_trajectory_has_a_play_layer_and_one_joinable_path(site):
    m = CFG.models["duffing"]
    for preset in m["presets"]:
        st = model.settings(CFG, preset)
        data = _load(site, f"data/duffing/trajectory/{preset}/1.json")
        fig = data["figures"]["phase"]
        assert _play_kinds(fig) == sorted([("trace", "False", False), ("tail", "False", False),
                                           ("head", "None", False)])
        per_cycle = st["samples_per_cycle"] * st["ndots"]
        assert data["play"] == {"unit": per_cycle, "step": st["ndots"], "tail": per_cycle}
        # site.js joins the per-cycle history paths into the trajectory it plays.
        paths = [t for t in fig["data"] if t["meta"]["role"] == "history"]
        joined = paths[0]["x"] + [v for t in paths[1:] for v in t["x"][1:]]
        run = model.load(CFG, preset, 1.0)
        assert len(joined) == len(run.traj_x)
        assert joined[::st["ndots"]] == next(t for t in fig["data"] if t["meta"]["role"] == "hover")["x"]


def test_compare_plays_observed_records_on_one_calendar(site):
    frame = _load(site, "data/compare/frame.json")
    cal = frame["calendar"]
    assert len(cal) == len(frame["calendar_labels"])
    assert all(phase.month_label(q) == lab for q, lab in zip(cal, frame["calendar_labels"]))
    # Consecutive months, from the earliest observed month to the latest.
    for a, b in zip(cal, cal[1:]):
        y, m = map(int, a.split("-"))
        assert b == (f"{y}-{m + 1:02d}" if m < 12 else f"{y + 1}-01")
    k = CFG.filter.NDOTS
    assert frame["play"] == {"unit": k, "step": k, "tail": 12 * k}
    for d in CFG.datasets:
        rec = _load(site, f"data/compare/{d.key}.json")
        assert rec["periods"][0][:7] in cal and rec["periods"][-1][:7] in cal
        assert len([t for t in rec["traces"]["loop"] if t["meta"].get("play")]) == 6
        assert [t["meta"]["role"] for t in rec["traces"]["time"]] == ["series", "highlight", "cursor"]
    assert cal[0] == min(_load(site, f"data/compare/{d.key}.json")["periods"][0][:7] for d in CFG.datasets)
    # The model has no calendar: nothing of it plays.
    rec = _load(site, "data/compare/model.json")
    assert not [t for t in rec["traces"]["loop"] if t["meta"].get("play")]


@pytest.mark.parametrize("name,default", [("index.html", "6"), ("compare.html", "6"), ("duffing.html", "1")])
def test_pages_with_a_loop_have_a_player(site, name, default):
    html = _html(site, name)
    assert html.count("data-player-toggle") == 1
    for attr in ("data-player-reset", "data-player-scrub", "data-player-speed", "data-player-stamp"):
        assert attr in html
    speed = re.search(r"<select data-player-speed.*?</select>", html, re.S).group(0)
    assert re.search(rf'value="{re.escape(default)}" selected', speed)
    assert "data-control" not in speed        # not a data choice, not in the URL


# ---- last checked ------------------------------------------------------------

@pytest.mark.parametrize("key", ["nino12", "callao"])
def test_readout_names_the_source_and_when_it_was_last_checked(site, key):
    from enso import status
    now = _phase(site, key)["now"]
    ds = CFG.dataset(key)
    assert now["source_name"] == {"noaa_sst": "NOAA CPC", "uhslc": "UHSLC"}[ds.source["type"]]
    day = status.read(ds.source["type"])["datasets"][key]["checked"]
    d = __import__("datetime").date.fromisoformat(day)
    assert now["checked"] == f"{d.day} {d:%b %Y}"
    assert 'data-field="now.checked"' in _html(site)


def test_footer_shows_when_each_source_was_last_checked(site):
    footer = re.search(r'<footer class="site-footer">.*?</footer>', _html(site), re.S).group(0)
    assert "last checked for new data: Sea surface temperature " in footer
    assert ", sea level " in footer
    assert "never recorded" not in footer


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
        # Red means "latest 12 months": the playing tail and dot are never red.
        assert t["roles"]["tail"]["line"] == t["roles"]["head"]["marker"]
        assert t["roles"]["tail"]["line"] not in (t["roles"]["recent"]["line"], t["roles"]["highlight"]["line"])


def test_build_is_deterministic(site, tmp_path):
    build(tmp_path)
    for path in site.rglob("*"):
        if path.is_file():
            assert (tmp_path / path.relative_to(site)).read_bytes() == path.read_bytes(), path


def test_data_files_stay_small(site):
    for path in (site / "data").rglob("*.json"):
        # a weekly record has about 4.35 times the samples of a monthly one (a point per week, not 5 per month)
        assert path.stat().st_size < (400_000 if path.stem == "nino12w" else 250_000), path.name


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
