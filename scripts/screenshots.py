"""Screenshot the built site at desktop and phone width, light and dark.

    python scripts/screenshots.py OUTDIR [--page index.html] [--query "ds=callao"]
           [--event 1997-98] [--seek 1330]

--seek stops the animation at that loop point (as if Play had run to it and
been paused), so a playing frame can be captured the same way every time.

Serves docs/ on a local port, so it needs no web server. Needs Playwright
with Chromium (pip install playwright && python -m playwright install chromium).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parents[1] / "docs"
SIZES = {"desktop": (1440, 1000), "phone": (390, 844)}


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--page", default="index.html")
    ap.add_argument("--query", default="")
    ap.add_argument("--event", default="", help="click this event button first")
    ap.add_argument("--hover", action="store_true", help="hover the time series at 1998")
    ap.add_argument("--seek", type=int, default=None,
                    help="show the animation paused at this loop point (data.play units)")
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    httpd, base = serve(DOCS)
    url = base + args.page + (f"?{args.query}" if args.query else "")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for size_name, (w, h) in SIZES.items():
                for scheme in ("light", "dark"):
                    ctx = browser.new_context(viewport={"width": w, "height": h},
                                              color_scheme=scheme, device_scale_factor=2)
                    page = ctx.new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(url)
                    page.wait_for_selector("html[data-ready='true']", timeout=30000)
                    if args.event:
                        page.click(f"[data-event='{args.event}']")
                    if args.seek is not None:
                        page.evaluate("""(v) => { const s = document.querySelector('[data-player-scrub]');
                          s.value = v; s.dispatchEvent(new Event('input')); }""", args.seek)
                    if args.hover:
                        box = page.locator("[data-plot='time'] .nsewdrag").first.bounding_box()
                        page.mouse.move(box["x"] + 5, box["y"] + 5)
                        page.mouse.move(box["x"] + box["width"] * 0.36, box["y"] + box["height"] * 0.5,
                                        steps=8)
                    page.wait_for_timeout(600)
                    name = f"{Path(args.page).stem}-{size_name}-{scheme}{args.suffix}.png"
                    # A full-page capture resizes the viewport, which clears Plotly's
                    # hover; hover shots capture the viewport only.
                    page.screenshot(path=str(args.out / name), full_page=not args.hover)
                    print(name, "errors:", errors or "none")
                    ctx.close()
            browser.close()
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
