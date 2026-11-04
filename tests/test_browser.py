"""The page in a real browser: loads, links views, switches theme.

Skipped when Playwright or its Chromium is not installed. ENSO_CPU_THROTTLE=6
runs them on a 6 times slower CPU, as a check that no test depends on speed.
"""

import functools
import http.server
import threading

import pytest

playwright = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.browser


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # Chromium not installed
            pytest.skip(f"Chromium unavailable: {exc}")
        yield b
        b.close()


@pytest.fixture(scope="module")
def base_url(site):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


def _open(browser, url, width=1280, **ctx):
    page = browser.new_context(viewport={"width": width, "height": 900}, **ctx).new_page()
    import os
    if os.environ.get("ENSO_CPU_THROTTLE"):     # imitate a slow CI runner
        page.context.new_cdp_session(page).send(
            "Emulation.setCPUThrottlingRate", {"rate": float(os.environ["ENSO_CPU_THROTTLE"])})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_selector("html[data-ready='true']", timeout=30000)
    return page, errors


TRACE = """([plot, meta]) => {
  const d = document.querySelector(`[data-plot='${plot}']`).data;
  const t = d.find(t => Object.entries(meta).every(([k, v]) => t.meta[k] === v));
  return t ? t.x.length : -1;
}"""


def _idle(page):
    page.wait_for_function("[...document.querySelectorAll('.panel')].every(p => p.getAttribute('aria-busy') === 'false')")


# ---- Phase diagrams -----------------------------------------------------------

def test_page_loads_without_errors_and_fills_readout(browser, base_url):
    page, errors = _open(browser, base_url + "index.html")
    assert errors == []
    assert page.text_content("[data-field='now.month']").strip()
    assert page.text_content("[data-field='now.observed_label']") == "SST, observed"
    assert page.text_content("[data-field='now.state']") in {"Warming", "Cooling"}
    assert "provisional" in page.text_content(".now")


def test_running_event_is_highlighted_on_opening(browser, base_url, site):
    import json
    data = json.loads((site / "data/phase/nino12.json").read_text(encoding="utf-8"))
    page, errors = _open(browser, base_url + "index.html")
    if 'data-default-event' not in page.content():
        pytest.skip("latest anomaly below the threshold")
    assert page.get_attribute("[data-event='2025-26']", "aria-pressed") == "true"
    ev = next(e for e in data["events"] if e["label"] == "2025-26")
    p, k = data["provisional_from"], data["ndots"]
    assert page.evaluate(TRACE, ["phase", {"role": "highlight", "provisional": False}]) == (p - ev["i0"]) * k + 1
    assert page.evaluate(TRACE, ["phase", {"role": "highlight", "provisional": True}]) == (ev["i1"] - p) * k + 1
    # Clear is remembered in the URL, so a reload does not bring it back.
    page.click("[data-action='clear']")
    assert "ev=" in page.url
    assert errors == []


def test_event_button_highlights_both_views(browser, base_url, site):
    import json
    data = json.loads((site / "data/phase/callao.json").read_text(encoding="utf-8"))
    ev = next(e for e in data["events"] if e["label"] == "1997-98")
    page, errors = _open(browser, base_url + "index.html?ds=callao&ev=")
    page.click("[data-event='1997-98']")
    months = ev["i1"] - ev["i0"] + 1
    assert page.evaluate(TRACE, ["phase", {"role": "highlight", "provisional": False}]) == (months - 1) * data["ndots"] + 1
    assert page.evaluate(TRACE, ["time", {"role": "highlight", "row": "T"}]) == months
    assert page.get_attribute("[data-event='1997-98']", "aria-pressed") == "true"
    assert page.is_visible(".key__highlight")
    page.click("[data-action='clear']")
    assert page.evaluate(TRACE, ["phase", {"role": "highlight", "provisional": False}]) == 0
    assert errors == []


def test_dragging_a_range_highlights_the_loop(browser, base_url):
    page, errors = _open(browser, base_url + "index.html?ds=nino34&ev=")
    box = page.locator("[data-plot='time'] .nsewdrag").first.bounding_box()
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + box["width"] * 0.30, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.45, y, steps=10)
    page.mouse.up()
    page.wait_for_timeout(300)
    assert page.evaluate(TRACE, ["phase", {"role": "highlight", "provisional": False}]) > 50
    assert page.is_visible(".key__highlight")
    assert errors == []


def test_hovering_the_time_series_marks_the_loop(browser, base_url):
    page, errors = _open(browser, base_url + "index.html")
    box = page.locator("[data-plot='time'] .nsewdrag").first.bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2, steps=8)
    page.wait_for_timeout(300)
    assert page.evaluate(TRACE, ["phase", {"role": "cursor"}]) == 1
    assert errors == []


def test_dataset_choice_goes_into_the_url(browser, base_url):
    page, errors = _open(browser, base_url + "index.html")
    page.select_option("select[name='ds']", "palau")
    _idle(page)
    assert "ds=palau" in page.url
    assert page.text_content("[data-field='now.observed_label']") == "Sea level, observed"
    assert errors == []


def test_theme_toggle_repaints_the_plots(browser, base_url):
    page, errors = _open(browser, base_url + "index.html", color_scheme="light")
    color = "() => document.querySelector(\"[data-plot='phase']\").data.find(t => t.meta.role === 'recent').line.color"
    light = page.evaluate(color)
    page.click("[data-theme-toggle]")
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    assert page.evaluate(color) != light
    assert errors == []


def test_phone_layout_has_no_modebar_and_no_horizontal_scroll(browser, base_url):
    page, errors = _open(browser, base_url + "index.html", width=390)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    assert page.locator("[data-plot='time'] .modebar").count() == 0
    assert errors == []


# ---- Compare -------------------------------------------------------------------

SLOT_COLOR = """(slot) => document.querySelector("[data-plot='phase']").data
  .find(t => t.meta.slot === slot && t.meta.role === 'recent').line.color"""


def test_compare_draws_each_slot_in_its_own_colour(browser, base_url):
    page, errors = _open(browser, base_url + "compare.html?a=nino12&b=callao&c=model")
    a, b = page.evaluate(SLOT_COLOR, "A"), page.evaluate(SLOT_COLOR, "B")
    assert a != b
    slots = page.evaluate("[...new Set(document.querySelector(\"[data-plot='phase']\").data.map(t => t.meta.slot))]")
    assert sorted(slots) == ["A", "B", "C"]
    assert page.is_visible("#compare [data-slot-key='C']")
    # Changing B keeps A's colour (colour follows the slot, not the rank).
    page.select_option("select[name='b']", "honolulu")
    _idle(page)
    assert page.evaluate(SLOT_COLOR, "A") == a
    assert "b=honolulu" in page.url
    assert errors == []


def test_compare_hover_marks_every_record(browser, base_url):
    page, errors = _open(browser, base_url + "compare.html?a=nino12&b=callao")
    box = page.locator("[data-plot='time'] .nsewdrag").first.bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2, steps=8)
    page.wait_for_timeout(300)
    assert page.evaluate(TRACE, ["phase", {"role": "cursor", "slot": "A"}]) == 1
    assert page.evaluate(TRACE, ["phase", {"role": "cursor", "slot": "B"}]) == 1
    assert errors == []


def test_compare_section_plays_through_the_months(browser, base_url):
    page, errors = _open(browser, base_url + "compare.html")
    page.click("[data-play='month']")
    page.wait_for_function("document.querySelector(\"select[name='month']\").value !== '0'", timeout=5000)
    page.click("[data-play='month']")
    assert page.get_attribute("[data-play='month']", "aria-pressed") == "false"
    assert errors == []


# ---- Duffing -----------------------------------------------------------------

def test_duffing_preset_drives_both_panels(browser, base_url):
    page, errors = _open(browser, base_url + "duffing.html")
    assert page.text_content("[data-field='facts.label']") == "El Niño fit (ALADO)"
    page.select_option("select[name='preset']", "chaos")
    _idle(page)
    assert page.text_content("[data-field='facts.label']") == "Chaotic benchmark"
    n = page.evaluate(TRACE, ["section", {"role": "points"}])
    assert n == 1500
    assert "preset=chaos" in page.url
    assert errors == []


def test_duffing_trajectory_hover_marks_the_time_series(browser, base_url):
    page, errors = _open(browser, base_url + "duffing.html")
    box = page.locator("[data-plot='time'] .nsewdrag").first.bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2, steps=8)
    page.wait_for_timeout(300)
    assert page.evaluate(TRACE, ["phase", {"role": "cursor"}]) == 1
    assert errors == []


# ---- Playing through time --------------------------------------------------------

# The playing tail and dot colours, and the theme's red and highlight blue.
PLAY_COLORS = """() => {
  const d = document.querySelector("[data-plot='phase']").data;
  const p = (role) => d.find(t => t.meta.role === role && t.meta.play && !t.meta.dots && !t.meta.provisional);
  return {tail: p('tail').line.color, head: p('head').marker.color};
}"""


def _theme(site, name="light"):
    import json
    return json.loads((site / "data/theme.json").read_text(encoding="utf-8"))[name]["roles"]


PLAY = """(extra) => {
  const d = document.querySelector("[data-plot='phase']").data;
  const f = (meta) => d.find(t => Object.entries({...meta, ...(extra || {})}).every(([k, v]) => t.meta[k] === v));
  const dot = f({role: 'head', play: true});
  const hist = d.filter(t => t.meta.role === 'history' && !t.meta.play && (!extra || !extra.slot || t.meta.slot === extra.slot));
  const len = (m) => { const t = f(m); return t ? t.x.length : -1; };
  return {
    dot: dot && dot.x.length ? [dot.x[0], dot.y[0]] : null,
    trace: len({role: 'trace', provisional: false, play: true}) + Math.max(len({role: 'trace', provisional: true, play: true}), 0),
    highlight: len({role: 'highlight', provisional: false}),
    tail: len({role: 'tail', provisional: false, play: true}),
    historyHidden: hist.every(t => t.visible === false),    // removed or hidden while playing
  };
}"""

TIME_CURSOR = """(meta) => {
  const t = document.querySelector("[data-plot='time']").data
    .find(t => Object.entries(meta).every(([k, v]) => t.meta[k] === v));
  return t && t.x.length ? String(t.x[0]) : null;
}"""


def _state(page):
    return page.get_attribute("[data-player]", "data-state")


def _pos(page):
    return int(page.input_value("[data-player-scrub]"))


def _wait_pos(page, above, timeout=10000):
    page.wait_for_function(f"+document.querySelector('[data-player-scrub]').value > {above}", timeout=timeout)


def _seek(page, value):
    page.evaluate("""(v) => { const s = document.querySelector('[data-player-scrub]');
      s.value = v; s.dispatchEvent(new Event('input')); }""", value)


def _loop_point(data, i):
    return [data["loop"]["x"][i], data["loop"]["y"][i]]


def test_playing_moves_the_dot_and_the_time_cursor(browser, base_url, site):
    import json
    data = json.loads((site / "data/phase/nino12.json").read_text(encoding="utf-8"))
    page, errors = _open(browser, base_url + "index.html?ev=", color_scheme="light")
    assert _state(page) == "idle" and page.is_hidden("[data-player-stamp]")
    page.click("[data-player-toggle]")
    assert _state(page) == "playing"
    _wait_pos(page, 10)
    roles = _theme(site)
    colors = page.evaluate(PLAY_COLORS)        # neutral, not the "latest 12 months" red
    assert colors == {"tail": roles["tail"]["line"], "head": roles["head"]["marker"]}
    assert roles["recent"]["line"] not in colors.values()
    before = page.evaluate(PLAY)
    cursor_before = page.evaluate(TIME_CURSOR, {"role": "cursor", "row": "T"})
    _wait_pos(page, _pos(page) + 15)
    after = page.evaluate(PLAY)
    assert after["dot"] != before["dot"]                            # the dot moves
    assert after["trace"] > before["trace"] > 0                     # the path builds up behind it
    assert 0 < after["tail"] <= data["play"]["tail"] + 1            # the tail stays 12 months long
    assert after["historyHidden"]                                   # the whole record is not shown yet
    assert page.evaluate(TIME_CURSOR, {"role": "cursor", "row": "T"}) != cursor_before   # time cursor follows
    assert page.is_visible("[data-player-stamp]")

    page.click("[data-player-toggle]")                              # pause
    assert _state(page) == "paused"
    i = _pos(page)
    page.wait_for_timeout(300)
    assert _pos(page) == i
    assert page.evaluate(PLAY)["dot"] == _loop_point(data, i)        # the dot is Python's loop point
    m = i // data["play"]["step"]
    assert page.text_content("[data-player-label]") == data["period_labels"][m]
    assert page.evaluate(TIME_CURSOR, {"role": "cursor", "row": "T"}).startswith(data["periods"][m])

    page.click("[data-theme-toggle]")                               # a repaint keeps the frame
    page.wait_for_timeout(300)
    assert page.evaluate(PLAY)["dot"] == _loop_point(data, i)

    page.click("[data-player-reset]")                               # back to the static view
    assert _state(page) == "idle"
    still = page.evaluate(PLAY)
    assert still["dot"] is None and still["trace"] == 0 and not still["historyHidden"]
    assert page.is_hidden("[data-player-stamp]")
    assert errors == []


def test_play_runs_only_the_highlighted_event(browser, base_url, site):
    import json
    data = json.loads((site / "data/phase/callao.json").read_text(encoding="utf-8"))
    ev = next(e for e in data["events"] if e["label"] == "1997-98")
    k = data["play"]["step"]
    page, errors = _open(browser, base_url + "index.html?ds=callao&ev=", color_scheme="light")
    page.click("[data-event='1997-98']")
    page.select_option("[data-player-speed]", "48")
    page.click("[data-player-toggle]")
    blue = _theme(site)["highlight"]["line"]
    assert page.evaluate(PLAY_COLORS) == {"tail": blue, "head": blue}     # the event's colour
    page.wait_for_function("document.querySelector('[data-player]').dataset.state === 'paused'", timeout=10000)
    scrub = page.locator("[data-player-scrub]")
    assert int(scrub.get_attribute("min")) == ev["i0"] * k
    assert int(scrub.get_attribute("max")) == _pos(page) == ev["i1"] * k     # stopped at the event's end
    end = page.evaluate(PLAY)
    assert end["dot"] == _loop_point(data, ev["i1"] * k)
    assert end["highlight"] == (ev["i1"] - ev["i0"]) * k + 1        # the event drawn in full, nothing else
    assert end["trace"] == 0 and not end["historyHidden"]            # the record stays as context
    # Playing again starts at the event's first month.
    page.select_option("[data-player-speed]", "3")
    page.click("[data-player-toggle]")
    page.wait_for_timeout(200)
    assert ev["i0"] * k <= _pos(page) < ev["i0"] * k + 3 * k
    # Clearing the event while playing carries on over the whole record.
    page.click("[data-action='clear']")
    assert _state(page) == "playing" and page.locator("[data-player-scrub]").get_attribute("min") == "0"
    assert page.evaluate(PLAY_COLORS)["tail"] == _theme(site)["tail"]["line"]   # neutral again
    assert errors == []


def test_changing_dataset_while_playing_keeps_the_month(browser, base_url):
    page, errors = _open(browser, base_url + "index.html?ev=")
    page.click("[data-player-toggle]")
    _wait_pos(page, 40)
    page.click("[data-player-toggle]")
    month = page.text_content("[data-player-label]")
    page.select_option("select[name='ds']", "callao")
    _idle(page)
    page.wait_for_timeout(200)
    assert _state(page) == "paused"
    assert page.text_content("[data-player-label]") == month
    assert page.evaluate(PLAY)["dot"] is not None
    assert errors == []


def test_dragging_the_slider_moves_the_dot(browser, base_url, site):
    import json
    data = json.loads((site / "data/phase/nino34.json").read_text(encoding="utf-8"))
    page, errors = _open(browser, base_url + "index.html?ds=nino34&ev=")
    _seek(page, 1000)
    assert _state(page) == "paused"
    assert page.evaluate(PLAY)["dot"] == _loop_point(data, 1000)
    assert page.evaluate(PLAY)["trace"] == 1001
    assert errors == []


def test_compare_plays_every_record_on_the_same_month(browser, base_url):
    page, errors = _open(browser, base_url + "compare.html?a=nino12&b=callao&c=model&ev=")
    a0, b0 = page.evaluate(PLAY, {"slot": "A"})["dot"], page.evaluate(PLAY, {"slot": "B"})["dot"]
    assert a0 is None and b0 is None
    page.click("[data-player-toggle]")
    _wait_pos(page, 60)
    page.click("[data-player-toggle]")
    a, b = page.evaluate(PLAY, {"slot": "A"}), page.evaluate(PLAY, {"slot": "B"})
    assert a["dot"] and b["dot"] and a["historyHidden"] and b["historyHidden"]
    # Both records at the same calendar month, the one the label names.
    ta = page.evaluate(TIME_CURSOR, {"role": "cursor", "slot": "A"})
    tb = page.evaluate(TIME_CURSOR, {"role": "cursor", "slot": "B"})
    assert ta == tb
    frame = page.evaluate("fetch('data/compare/frame.json').then(r => r.json())")
    month = frame["calendar"][_pos(page) // frame["play"]["step"]]
    assert ta.startswith(month)
    assert page.text_content("[data-player-label]") == frame["calendar_labels"][frame["calendar"].index(month)]
    # The model has no calendar: it has no play traces and stays drawn whole.
    c = page.evaluate(PLAY, {"slot": "C"})
    assert c["dot"] is None and c["trace"] == -1 and not c["historyHidden"]
    # Moving on keeps playing both: another frame, both dots moved.
    page.click("[data-player-toggle]")
    _wait_pos(page, _pos(page) + 20)
    assert page.evaluate(PLAY, {"slot": "A"})["dot"] != a["dot"]
    assert page.evaluate(PLAY, {"slot": "B"})["dot"] != b["dot"]
    assert errors == []


def test_compare_plays_only_the_highlighted_event(browser, base_url):
    page, errors = _open(browser, base_url + "compare.html?a=nino12&b=callao&ev=2015-16")
    page.select_option("[data-player-speed]", "48")
    page.click("[data-player-toggle]")
    page.wait_for_function("document.querySelector('[data-player]').dataset.state === 'paused'", timeout=10000)
    assert page.text_content("[data-player-label]") == "Jun 2016"
    assert page.evaluate(TIME_CURSOR, {"role": "cursor", "slot": "B"}).startswith("2016-06")
    assert errors == []


def test_duffing_trajectory_plays_and_keeps_playing_across_runs(browser, base_url):
    page, errors = _open(browser, base_url + "duffing.html")
    page.click("[data-player-toggle]")
    _wait_pos(page, 30)
    first = page.evaluate(PLAY)
    _wait_pos(page, _pos(page) + 30)
    second = page.evaluate(PLAY)
    assert second["dot"] != first["dot"] and second["trace"] > first["trace"] and second["historyHidden"]
    assert page.evaluate(TIME_CURSOR, {"role": "cursor", "row": "X"}) is not None
    assert page.text_content("[data-player-label]").startswith("Model year")
    page.select_option("select[name='fa']", "1.5")
    _idle(page)
    page.wait_for_timeout(200)
    assert _state(page) == "playing" and page.evaluate(PLAY)["dot"] is not None
    assert errors == []


def test_duffing_section_still_plays_its_phases(browser, base_url):
    page, errors = _open(browser, base_url + "duffing.html")
    page.click("[data-play='phase']")
    page.wait_for_function("document.querySelector(\"select[name='phase']\").value !== '0'", timeout=5000)
    page.click("[data-play='phase']")
    assert errors == []


def test_phone_player_fits(browser, base_url):
    page, errors = _open(browser, base_url + "index.html", width=390)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    box = page.locator("[data-player]").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390
    assert errors == []
