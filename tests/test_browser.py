"""The page in a real browser: loads, links views, switches theme.

Skipped when Playwright or its Chromium is not installed.
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
