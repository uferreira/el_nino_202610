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


def _open(browser, url, **ctx):
    page = browser.new_context(viewport={"width": 1280, "height": 900}, **ctx).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_selector("html[data-ready='true']", timeout=30000)
    return page, errors


TRACE = """([plot, role, row]) => {
  const d = document.querySelector(`[data-plot='${plot}']`).data;
  const t = d.find(t => t.meta.role === role && (row === null || t.meta.row === row));
  return t.x.length;
}"""


def test_page_loads_without_errors_and_fills_readout(browser, base_url):
    page, errors = _open(browser, base_url + "index.html")
    assert errors == []
    assert page.text_content("[data-field='now.month']").strip()
    assert page.text_content("[data-field='now.state']") in {"Warming", "Cooling"}


def test_event_button_highlights_both_views(browser, base_url, site):
    import json
    data = json.loads((site / "data/phase/callao.json").read_text(encoding="utf-8"))
    ev = next(e for e in data["events"] if e["label"] == "1997-98")
    page, errors = _open(browser, base_url + "index.html?ds=callao")
    page.click("[data-event='1997-98']")
    months = ev["i1"] - ev["i0"] + 1
    assert page.evaluate(TRACE, ["phase", "highlight", None]) == (months - 1) * data["ndots"] + 1
    assert page.evaluate(TRACE, ["time", "highlight", "T"]) == months
    assert page.get_attribute("[data-event='1997-98']", "aria-pressed") == "true"
    assert page.is_visible(".key__highlight")
    page.click("[data-action='clear']")
    assert page.evaluate(TRACE, ["phase", "highlight", None]) == 0
    assert errors == []


def test_dragging_a_range_highlights_the_loop(browser, base_url):
    page, errors = _open(browser, base_url + "index.html?ds=nino34")
    box = page.locator("[data-plot='time'] .nsewdrag").first.bounding_box()
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + box["width"] * 0.30, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.45, y, steps=10)
    page.mouse.up()
    page.wait_for_timeout(300)
    assert page.evaluate(TRACE, ["phase", "highlight", None]) > 50
    assert page.is_visible(".key__highlight")
    assert errors == []


def test_hovering_the_time_series_marks_the_loop(browser, base_url):
    page, errors = _open(browser, base_url + "index.html")
    box = page.locator("[data-plot='time'] .nsewdrag").first.bounding_box()
    page.mouse.move(box["x"] + 5, box["y"] + 5)
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2, steps=8)
    page.wait_for_timeout(300)
    assert page.evaluate(TRACE, ["phase", "cursor", None]) == 1
    assert errors == []


def test_dataset_choice_goes_into_the_url(browser, base_url):
    page, errors = _open(browser, base_url + "index.html")
    page.select_option("select[name='ds']", "palau")
    page.wait_for_function("document.querySelector('.panel').getAttribute('aria-busy') === 'false'")
    assert "ds=palau" in page.url
    assert page.text_content("[data-field='now.value_label']") == "Sea level"
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
