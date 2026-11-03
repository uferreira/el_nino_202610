"""Phase diagrams page: the loop (T, dT/dt) linked to its two time series.

One JSON file per dataset holds both figures plus the readout text. All
numbers and labels are produced here; site.js only draws them, links hover
and highlights, and paints colours from the theme.
"""

from __future__ import annotations

from datetime import date

import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from enso import series
from enso.config import Config, Dataset
from enso.phasespace import PhaseSeries, compute, month_label
from enso.site.registry import Control, Option, Page, Panel

RECENT_MONTHS = 12
# Decimals kept in the JSON and shown to readers, per unit: (value, rate).
DECIMALS = {"°C": (3, 4), "mm": (1, 2)}
SHOW = {"°C": (2, 2), "mm": (0, 1)}


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def axis_labels(ds: Dataset) -> dict:
    if ds.group.key == "sst":
        name = "SST" if ds.quantity == "absolute" else "SST anomaly"
        rate_word = ("Warming", "Cooling")
    else:
        name = "Sea level"
        rate_word = ("Rising", "Falling")
    value = f"{name} ({ds.unit})"
    if ds.quantity == "record_mean":
        value = f"Sea level minus mean ({ds.unit})"
    return {
        "value": value,
        "value_short": name,
        "rate": f"Rate of change ({ds.rate_unit})",
        "rate_short": f"Rate ({ds.unit}/{ds.step[:2]})",
        "rate_word": rate_word,
    }


def _fmt(x: float, decimals: int, signed: bool = False) -> str:
    s = f"{x:+.{decimals}f}" if signed else f"{x:.{decimals}f}"
    return s.replace("-", "−")  # true minus sign: never read as a dash


def _round(a: np.ndarray, decimals: int) -> list[float]:
    return np.round(np.asarray(a, dtype=float), decimals).tolist()


def _export(fig: go.Figure) -> dict:
    """Figure as plain JSON, without plotly.py's default template: site.js
    applies the theme's template, so the default would only add weight."""
    out = fig.to_plotly_json()
    out["layout"].pop("template", None)
    return out


def _month_after(period: str, n: int) -> str:
    y, m = map(int, period.split("-"))
    y, m = divmod(y * 12 + m - 1 + n, 12)
    return f"{y:04d}-{m + 1:02d}"


def _padded(a: np.ndarray, frac: float = 0.06) -> list[float]:
    lo, hi = float(np.min(a)), float(np.max(a))
    pad = (hi - lo) * frac or 1.0
    return [lo - pad, hi + pad]


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def _reference_x(ps: PhaseSeries) -> tuple[float, str]:
    """Vertical reference on the loop: zero for anomalies, the mean otherwise."""
    if ps.dataset.quantity == "absolute":
        m = float(ps.T.mean())
        return m, f"mean {_fmt(m, SHOW[ps.dataset.unit][0])}"
    return 0.0, ""


def phase_figure(ps: PhaseSeries) -> dict:
    ds = ps.dataset
    dv, dr = DECIMALS[ds.unit]
    sv, sr = SHOW[ds.unit]
    lab = axis_labels(ds)
    n, k = ps.n_months, ps.ndots
    r0 = (n - RECENT_MONTHS) * k            # fine index where the recent tail starts
    labels = [month_label(p) for p in ps.periods]

    fig = go.Figure()
    fig.add_scatter(x=_round(ps.T, dv), y=_round(ps.V, dr), mode="lines",
                    line={"width": 1.25}, hoverinfo="skip", meta={"role": "history"})
    fig.add_scatter(x=[], y=[], mode="lines", line={"width": 2.5},
                    hoverinfo="skip", meta={"role": "highlight"})
    fig.add_scatter(x=_round(ps.T[r0:], dv), y=_round(ps.V[r0:], dr), mode="lines",
                    line={"width": 2}, hoverinfo="skip", meta={"role": "recent"})
    fig.add_scatter(x=_round(ps.T_month[-RECENT_MONTHS:], dv),
                    y=_round(ps.V_month[-RECENT_MONTHS:], dr), mode="markers",
                    marker={"size": 5}, hoverinfo="skip", meta={"role": "recent"})
    fig.add_scatter(x=[round(float(ps.T[-1]), dv)], y=[round(float(ps.V[-1]), dr)],
                    mode="markers", marker={"size": 12, "line": {"width": 2}},
                    hoverinfo="skip", meta={"role": "now"})
    fig.add_scatter(x=[], y=[], mode="markers", marker={"size": 13, "line": {"width": 2}},
                    hoverinfo="skip", meta={"role": "cursor"})
    # Invisible monthly markers: the hover targets (bigger than the line).
    fig.add_scatter(
        x=_round(ps.T_month, dv), y=_round(ps.V_month, dr), mode="markers",
        marker={"size": 10, "opacity": 0}, customdata=labels,
        hovertemplate=(f"<b>%{{customdata}}</b><br>{lab['value_short']} %{{x:.{sv}f}} {ds.unit}"
                       f"<br>Rate %{{y:+.{sr}f}} {ds.rate_unit}<extra></extra>"),
        meta={"role": "hover"},
    )

    ref, ref_label = _reference_x(ps)
    shapes = [
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": 0, "y1": 0, "layer": "below"},
        {"type": "line", "xref": "x", "x0": ref, "x1": ref, "yref": "paper", "y0": 0, "y1": 1,
         "layer": "below", "line": {"dash": "dot"}},
    ]
    # Label the current month on the side with more room, so it is never clipped.
    xr = _padded(ps.T)
    right_side = float(ps.T[-1]) > xr[0] + 0.7 * (xr[1] - xr[0])
    annotations = [{
        "x": float(ps.T[-1]), "y": float(ps.V[-1]), "xref": "x", "yref": "y",
        "text": month_label(ps.periods[-1]), "showarrow": False,
        "xanchor": "right" if right_side else "left", "yanchor": "bottom",
        "xshift": -8 if right_side else 8, "yshift": 4,
    }]
    if ref_label:
        annotations.append({"x": ref, "y": 1, "xref": "x", "yref": "paper", "text": ref_label,
                            "showarrow": False, "xanchor": "left", "yanchor": "top", "xshift": 4})

    fig.update_layout(
        # l + r == t + b keeps the plot area square; t leaves room for the PNG button.
        margin={"l": 64, "r": 16, "t": 28, "b": 52},
        showlegend=False,
        hovermode="closest",
        hoverdistance=24,
        dragmode="zoom",
        uirevision=ds.key,
        xaxis={"title": {"text": lab["value"]}, "range": _padded(ps.T), "nticks": 7},
        yaxis={"title": {"text": lab["rate"]}, "range": _padded(ps.V), "nticks": 7},
        shapes=shapes,
        annotations=annotations,
    )
    return _export(fig)


def time_figure(ps: PhaseSeries) -> dict:
    ds = ps.dataset
    dv, dr = DECIMALS[ds.unit]
    sv, sr = SHOW[ds.unit]
    lab = axis_labels(ds)
    x = ps.periods
    rows = [("T", ps.T_month, dv, sv, lab["value_short"], ds.unit),
            ("V", ps.V_month, dr, sr, "Rate", ds.rate_unit)]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.07)
    for i, (row, y, d, s, name, unit) in enumerate(rows, start=1):
        fmt = f"+.{s}f" if row == "V" else f".{s}f"
        fig.add_scatter(x=x, y=_round(y, d), mode="lines", line={"width": 1.25},
                        hovertemplate=f"<b>%{{x|%b %Y}}</b>  {name} %{{y:{fmt}}} {unit}<extra></extra>",
                        meta={"role": "series", "row": row}, row=i, col=1)
        fig.add_scatter(x=[], y=[], mode="lines", line={"width": 2.5}, hoverinfo="skip",
                        meta={"role": "highlight", "row": row}, row=i, col=1)
        fig.add_scatter(x=x[-RECENT_MONTHS:], y=_round(y[-RECENT_MONTHS:], d), mode="lines",
                        line={"width": 2}, hoverinfo="skip",
                        meta={"role": "recent", "row": row}, row=i, col=1)
        fig.add_scatter(x=[x[-1]], y=[round(float(y[-1]), d)], mode="markers",
                        marker={"size": 8, "line": {"width": 1.5}}, hoverinfo="skip",
                        meta={"role": "now", "row": row}, row=i, col=1)
        fig.add_scatter(x=[], y=[], mode="markers", marker={"size": 10, "line": {"width": 2}},
                        hoverinfo="skip", meta={"role": "cursor", "row": row}, row=i, col=1)

    ref, _ = _reference_x(ps)
    fig.update_layout(
        margin={"l": 64, "r": 16, "t": 28, "b": 28},
        showlegend=False,
        hovermode="x",
        hoverdistance=-1,
        dragmode="select",
        selectdirection="h",
        uirevision=ds.key,
        shapes=[
            {"type": "line", "xref": "x domain", "x0": 0, "x1": 1, "yref": "y", "y0": ref, "y1": ref,
             "layer": "below", "line": {"dash": "dot"}},
            {"type": "line", "xref": "x2 domain", "x0": 0, "x1": 1, "yref": "y2", "y0": 0, "y1": 0,
             "layer": "below"},
        ],
    )
    spikes = {"showspikes": True, "spikemode": "across", "spikesnap": "hovered data",
              "spikethickness": 1, "spikedash": "solid"}
    # A little room after the last month so the current-month marker is not clipped.
    end_pad = _month_after(x[-1], 6)
    fig.update_xaxes(range=[x[0], end_pad], **spikes)
    fig.update_xaxes(showticklabels=False, ticks="", row=1, col=1)
    fig.update_yaxes(fixedrange=True, nticks=4)
    fig.update_yaxes(title_text=lab["value_short"] + f" ({ds.unit})", row=1, col=1)
    fig.update_yaxes(title_text=lab["rate_short"], row=2, col=1)
    return _export(fig)


# ---------------------------------------------------------------------------
# Readout and events
# ---------------------------------------------------------------------------

def readout(ps: PhaseSeries) -> dict:
    ds = ps.dataset
    sv, sr = SHOW[ds.unit]
    lab = axis_labels(ds)
    T, V = float(ps.T[-1]), float(ps.V[-1])
    last = ps.periods[-1]
    fetched = date.fromisoformat(ps.fetched) if ps.fetched else None
    return {
        "month": month_label(last, short=False),
        "value_label": lab["value_short"],
        "value": f"{_fmt(T, sv)} {ds.unit}",
        "rate": f"{_fmt(V, sr, signed=True)} {ds.rate_unit}",
        "state": lab["rate_word"][0] if V >= 0 else lab["rate_word"][1],
        "rising": V >= 0,
        "observed": f"{_fmt(float(ps.observed[-1]), sv)} {ds.unit}",
        "through": month_label(last, short=False),
        "updated": f"{fetched.day} {fetched:%b %Y}" if fetched else "unknown",
    }


def events(ps: PhaseSeries, cfg: Config) -> list[dict]:
    out = []
    first, last = ps.periods[0], ps.periods[-1]
    for ev in cfg.events:
        if ev.end < first or ev.start > last:
            continue
        start, end = max(ev.start, first), min(ev.end, last)
        out.append({
            "label": ev.label,
            "i0": ps.periods.index(start),
            "i1": ps.periods.index(end),
            "range": f"{month_label(start)} to {month_label(end)}",
        })
    return out


def build_dataset(cfg: Config, key: str) -> dict:
    ds = cfg.dataset(key)
    ps = compute(series.read(key), ds, cfg.filter)
    w = ps.window
    return {
        "dataset": {"key": ds.key, "label": ds.label, "long_label": ds.long_label,
                    "source": ps.source},
        "periods": ps.periods,
        "period_labels": [month_label(p) for p in ps.periods],
        "ndots": ps.ndots,
        "recent_months": RECENT_MONTHS,
        "window": f"{month_label(w['start'])} to {month_label(w['end'])}, {w['n_months']} months",
        "gap_filled_months": int(ps.gap_filled.sum()),
        "now": readout(ps),
        "events": events(ps, cfg),
        "figures": {"phase": phase_figure(ps), "time": time_figure(ps)},
    }


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def dataset_control(cfg: Config) -> Control:
    return Control(
        name="ds",
        label="Dataset",
        options=[Option(d.key, d.label, d.group.label) for d in cfg.datasets],
        default=cfg.datasets[0].key,
    )


NOTES = """
<p>Each point of the loop is one moment of the record: its horizontal
position is the filtered value, its vertical position how fast that value
is changing. A warm event therefore runs clockwise: above the zero line
moving right while it builds, across the zero line at its peak, then below
the zero line moving left as it decays.</p>
<p>The record is low-pass filtered (Fourier, full periods shorter than about
18 to 20 months removed) so the loop shows interannual ENSO variability, not
month-to-month noise. NINO1+2 keeps its seasonal cycle, so it also traces a
small loop every year. The last months of any filtered record can still move
a little as new observations arrive.</p>
<p>Drag across the time series to highlight that stretch of the loop;
double-click to clear. Hover either view to find the same month in the other.</p>
"""


def page(cfg: Config) -> Page:
    panel = Panel(
        id="phase",
        kind="phase-linked",
        title="Phase diagram",
        data="data/phase/{ds}.json",
        build=lambda ds: build_dataset(cfg, ds),
        controls=[dataset_control(cfg)],
    )
    return Page(
        slug="index",
        title="Phase diagrams",
        nav_label="Phase diagrams",
        intro=("Each record drawn against its own rate of change. "
               "Right of centre is warm or high, above zero is rising; El Niño events run as wide clockwise loops."),
        panels=[panel],
        template="phase.html",
        notes_html=NOTES,
    )
