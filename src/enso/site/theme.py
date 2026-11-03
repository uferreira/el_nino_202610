"""The one palette. It is written out twice, from the same values:

* docs/assets/tokens.css: CSS custom properties for the page
* docs/data/theme.json:   a Plotly template + trace colours per theme

Figures built in Python carry no colours in their layout. Each trace names
its ``meta.role`` (history, recent, highlight, ...) and site.js paints it
from theme.json, so switching light/dark never needs a rebuild.

Recent (red) and highlight (blue) were checked with the dataviz palette
validator against each background: CVD separation >= 22, contrast >= 3:1.
The three Compare slot colours pass the validator as a set in both themes
(all pairs); slot C in light mode is below 3:1 contrast, so every slot is
also named by a text label on the plot.
"""

from __future__ import annotations

import json

FONT_SANS = '"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif'
FONT_MONO = '"IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace'

TOKENS = {
    "light": {
        "bg": "#ffffff",
        "surface": "#f4f5f7",
        "border": "#e1e4e8",
        "text": "#14171c",
        "text-2": "#4a525d",
        "muted": "#6b7481",
        "accent": "#1d63c9",
        # Whole record on the loop: thin and translucent, drawn one year per
        # path, so where years overlap the grey builds up and density shows.
        "history": "rgba(74, 82, 93, 0.30)",
        "series": "#a9b0b9",      # time panel: full series, thin
        "anomaly": "#2b3139",     # time panel: filtered interannual anomaly, bold
        "points": "rgba(20, 23, 28, 0.55)",  # Poincaré section dots
        "recent": "#d1332b",      # latest 12 months
        "highlight": "#1d63c9",   # event or dragged range
        "band": "rgba(29, 99, 201, 0.10)",
        "provisional": "rgba(20, 23, 28, 0.05)",
        "zero": "#d3d7dc",
        "cursor": "#14171c",
        "slot-a": "#2a78d6",      # Compare slots: validated as a set
        "slot-b": "#eb6834",
        "slot-c": "#1baf7a",
    },
    "dark": {
        "bg": "#121418",
        "surface": "#1a1d22",
        "border": "#2b3038",
        "text": "#e7e9ec",
        "text-2": "#aab2bc",
        "muted": "#8a929d",
        "accent": "#4a8fe8",
        "history": "rgba(170, 178, 188, 0.26)",
        "series": "#5a616b",
        "anomaly": "#d4d8dd",
        "points": "rgba(231, 233, 236, 0.55)",
        "recent": "#e8524a",
        "highlight": "#4a8fe8",
        "band": "rgba(74, 143, 232, 0.16)",
        "provisional": "rgba(231, 233, 236, 0.06)",
        "zero": "#353b44",
        "cursor": "#e7e9ec",
        "slot-a": "#3987e5",
        "slot-b": "#d95926",
        "slot-c": "#199e70",
    },
}

# Which token colours each trace role. "ring" is the gap drawn round the
# current-month marker so it stands off the lines beneath it.
ROLES = {
    "history": {"line": "history"},
    "series": {"line": "series"},
    "anomaly": {"line": "anomaly"},
    "points": {"marker": "points"},
    "dot": {"marker": "points", "ring": "bg"},   # Compare section dots (slot colour)
    "highlight": {"line": "highlight"},
    "recent": {"line": "recent", "marker": "recent"},
    "now": {"marker": "recent", "ring": "bg"},
    "cursor": {"marker": "bg", "ring": "cursor"},
    "hover": {},
}
SLOTS = {"A": "slot-a", "B": "slot-b", "C": "slot-c"}


def plotly_template(theme: str) -> dict:
    t = TOKENS[theme]
    axis = {
        "showgrid": False,
        "zeroline": False,
        "showline": True,
        "linecolor": t["border"],
        "linewidth": 1,
        "ticks": "outside",
        "ticklen": 4,
        "tickcolor": t["border"],
        "tickfont": {"family": FONT_MONO, "size": 11, "color": t["muted"]},
        "title": {"font": {"family": FONT_SANS, "size": 12, "color": t["text-2"]}},
        "showspikes": False,
    }
    return {
        "layout": {
            "font": {"family": FONT_SANS, "size": 12, "color": t["text"]},
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "xaxis": axis,
            "yaxis": axis,
            "hoverlabel": {
                "bgcolor": t["bg"],
                "bordercolor": t["border"],
                "font": {"family": FONT_SANS, "size": 12, "color": t["text"]},
            },
            "annotationdefaults": {"font": {"family": FONT_MONO, "size": 11, "color": t["text-2"]}},
            "shapedefaults": {"line": {"color": t["zero"], "width": 1}},
            "selectiondefaults": {"line": {"color": t["accent"], "width": 1}},
            "newselection": {"line": {"color": t["accent"], "width": 1, "dash": "dot"}},
            "activeselection": {"fillcolor": t["band"], "opacity": 1},
        }
    }


def theme_json() -> str:
    out = {}
    for name, t in TOKENS.items():
        roles = {}
        for role, parts in ROLES.items():
            roles[role] = {part: t[token] for part, token in parts.items()}
        out[name] = {
            "template": plotly_template(name),
            "roles": roles,
            "band": t["band"],
            "provisional": t["provisional"],
            "zero": t["zero"],
            "bg": t["bg"],
            "slots": {k: t[v] for k, v in SLOTS.items()},
        }
    return json.dumps(out, indent=1, ensure_ascii=False)


def tokens_css() -> str:
    def block(t: dict) -> str:
        return "\n".join(f"  --{k}: {v};" for k, v in t.items())

    light, dark = block(TOKENS["light"]), block(TOKENS["dark"])
    return (
        "/* Generated by enso.site.theme. Do not edit by hand. */\n"
        f":root {{\n  color-scheme: light;\n{light}\n"
        f"  --font-sans: {FONT_SANS};\n  --font-mono: {FONT_MONO};\n}}\n"
        "@media (prefers-color-scheme: dark) {\n"
        f"  :root:not([data-theme=\"light\"]) {{\n    color-scheme: dark;\n"
        + "\n".join("  " + line for line in dark.splitlines())
        + "\n  }\n}\n"
        f":root[data-theme=\"dark\"] {{\n  color-scheme: dark;\n{dark}\n}}\n"
    )
