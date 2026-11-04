"""Compare page: up to three records on one normalised phase plane.

Normalisation (decided: option A, as the old compare.html):

    x_n = (x - mean) / sigma_x        y_n = (dx/dt) / sigma_x

with mean and sigma_x (sample standard deviation) of the filtered record
over its analysis window. Dividing both axes by the same sigma_x keeps each
loop's shape, so the height of a loop still says how fast that record
moves, in units of its own typical swing per month.

A weekly record (NINO1+2 weekly) is on the same plane and the same calendar:
its periods are dates, its loop has a point per week, and it carries ``cal_map``
(the loop point it shows at each point of the shared monthly calendar), so
monthly and weekly NINO1+2 play side by side.

Files: one JSON per dataset (and one for the model) holding ready-made
traces, plus data/compare/frame.json with the layouts. site.js places the
chosen datasets into the frame and colours them by slot (A, B, C); every
number, trace and label is made here.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

import datetime as dt

from enso import model
from enso.config import Config
from enso.phasespace import MONTH_NAMES, month_label
from enso.site.figures import MINUS, export, history_paths, month_after, padded, play_traces, rnd
from enso.site.pages.phase import DASH, MONTH_SPEEDS, RECENT_MONTHS, first_provisional, phase_series
from enso.site.registry import Control, Option, Page, Panel

MODEL_KEY = "model"
DEC = (3, 4)
SLOT_DEFAULTS = {"a": "nino12", "b": "callao", "c": "none"}
X_TITLE = f"(x {MINUS} mean) / σx"
Y_TITLE = "(dx/dt) / σx, per month"


# ---------------------------------------------------------------------------
# One normalised record
# ---------------------------------------------------------------------------

class Norm:
    """A record on the normalised plane: fine loop, monthly points, periods."""

    def __init__(self, key, label, periods, T, V, ndots, provisional_from, mean, sigma,
                 short=None, anomaly=None, weekly=False, year_points=None, recent=12):
        self.key, self.label, self.periods, self.ndots = key, label, periods, ndots
        self.weekly = weekly
        self.year_points = year_points or 12 * ndots     # loop points per history path
        self.recent = recent                              # samples in the latest 12 months
        self.short = short or label
        # Time strip: the filtered anomaly (seasonal cycle removed) over its own
        # standard deviation; None for the model, which has no real calendar.
        self.anom = None if anomaly is None else np.asarray(anomaly) / float(np.std(anomaly, ddof=1))
        self.provisional_from = provisional_from      # month index, or None (model)
        self.mean, self.sigma = mean, sigma
        self.x = (np.asarray(T) - mean) / sigma
        self.y = np.asarray(V) / sigma
        self.xm, self.ym = self.x[::ndots], self.y[::ndots]


def observed(cfg: Config, key: str) -> Norm:
    ps = phase_series(cfg, key)
    T = ps.T
    return Norm(key, ps.dataset.label, ps.periods, T, ps.V, ps.ndots,
                first_provisional(ps, cfg), float(T.mean()), float(T.std(ddof=1)), anomaly=ps.anomaly,
                weekly=ps.weekly, year_points=ps.year_points, recent=ps.recent)


def model_record(cfg: Config) -> Norm:
    """The model's last stretch, one sample per month, laid on the same
    calendar months as NINO1+2 (the model's own calendar is arbitrary)."""
    m = cfg.models["duffing"]
    run = model.load(cfg, m["compare_preset"], 1.0)
    ref = phase_series(cfg, cfg.datasets[0].key)
    st = model.settings(cfg, m["compare_preset"])
    spc, k = st["samples_per_cycle"], st["ndots"]
    if spc != 12 or k != ref.ndots:
        raise ValueError("Compare needs the model sampled monthly with the same ndots as the data")
    j0 = int(ref.periods[0][5:7]) - 1           # first sample in the same calendar month
    n = ref.n_months
    a, b = j0 * k, (j0 + n - 1) * k + 1
    if b > len(run.traj_x):
        raise ValueError("model trajectory_cycles too short for the Compare window")
    T, V = run.traj_x[a:b], run.traj_y[a:b]
    label = cfg.models["duffing"]["presets"][m["compare_preset"]]["label"]
    return Norm(MODEL_KEY, f"Duffing model, {label}", ref.periods, T, V, k, None,
                float(T.mean()), float(T.std(ddof=1)), short="Duffing model")


def all_records(cfg: Config) -> list[Norm]:
    return [observed(cfg, d.key) for d in cfg.datasets] + [model_record(cfg)]


# ---------------------------------------------------------------------------
# Traces for one record (no colours: site.js paints them by slot)
# ---------------------------------------------------------------------------

def loop_traces(r: Norm) -> list[dict]:
    k, n = r.ndots, len(r.periods)
    p = r.provisional_from if r.provisional_from is not None else n - 1
    dx, dy = DEC
    out = [t.to_plotly_json() for t in history_paths(r.x, r.y, r.year_points, p * k, DEC, width=1.0)]
    for t in out:
        t["opacity"] = 0.3       # per-year paths: overlaps build up density
    if r.provisional_from is not None:
        out.append(go.Scatter(x=rnd(r.x[p * k:], dx), y=rnd(r.y[p * k:], dy), mode="lines",
                              line={"width": 1.25, "dash": DASH}, opacity=0.6, hoverinfo="skip",
                              meta={"role": "history", "provisional": True}).to_plotly_json())
    for prov in (False, True):
        out.append(go.Scatter(x=[], y=[], mode="lines",
                              line={"width": 3, **({"dash": DASH} if prov else {})},
                              hoverinfo="skip", meta={"role": "highlight", "provisional": prov}).to_plotly_json())
    if r.provisional_from is not None:        # observed records: latest 12 months and now
        rr = max(n - r.recent, 0)
        out += [
            go.Scatter(x=rnd(r.x[rr * k:p * k + 1], dx), y=rnd(r.y[rr * k:p * k + 1], dy), mode="lines",
                       line={"width": 2}, hoverinfo="skip", meta={"role": "recent"}),
            go.Scatter(x=rnd(r.x[max(p, rr) * k:], dx), y=rnd(r.y[max(p, rr) * k:], dy), mode="lines",
                       line={"width": 2, "dash": DASH}, hoverinfo="skip",
                       meta={"role": "recent", "provisional": True}),
            go.Scatter(x=[round(float(r.x[-1]), dx)], y=[round(float(r.y[-1]), dy)], mode="markers",
                       marker={"size": 11, "line": {"width": 2}}, hoverinfo="skip", meta={"role": "now"}),
        ]
        # Filled while playing (the model has no calendar, so it does not play).
        out += play_traces(trace_opacity=0.6, dash=DASH)
        out = [t if isinstance(t, dict) else t.to_plotly_json() for t in out]
    out.append(go.Scatter(x=[], y=[], mode="markers", marker={"size": 12, "line": {"width": 2}},
                          hoverinfo="skip", meta={"role": "cursor"}).to_plotly_json())
    labels = [month_label(q) for q in r.periods]
    out.append(go.Scatter(
        x=rnd(r.xm, dx), y=rnd(r.ym, dy), mode="markers", marker={"size": 9, "opacity": 0},
        customdata=[[f"{r.label}, {lab}", q] for lab, q in zip(labels, r.periods)],
        hovertemplate=f"<b>%{{customdata[0]}}</b><br>%{{x:.2f}} σ, rate %{{y:+.2f}} σ/month<extra></extra>",
        meta={"role": "hover"}).to_plotly_json())
    return out


def label_annotation(r: Norm) -> dict:
    """Name the record on the plot, next to its latest point (observed) or
    its right-most point (model)."""
    if r.provisional_from is not None:
        i = len(r.x) - 1
        return {"x": float(r.x[i]), "y": float(r.y[i]), "xref": "x", "yref": "y", "text": r.short,
                "showarrow": False, "xanchor": "left", "yanchor": "bottom", "xshift": 8, "yshift": 4}
    i = int(np.argmax(r.y))       # model: above its highest point, centred
    return {"x": float(r.x[i]), "y": float(r.y[i]), "xref": "x", "yref": "y", "text": r.short,
            "showarrow": False, "xanchor": "center", "yanchor": "bottom", "yshift": 6}


def time_traces(r: Norm) -> list[dict]:
    if r.anom is None:
        return []
    dx = DEC[0]
    return [
        go.Scatter(x=r.periods, y=rnd(r.anom, dx), mode="lines", line={"width": 1.5},
                   name=r.label, hovertemplate=f"%{{y:+.2f}} σ<extra>{r.label}</extra>",
                   meta={"role": "series"}).to_plotly_json(),
        go.Scatter(x=[], y=[], mode="lines", line={"width": 3}, hoverinfo="skip",
                   meta={"role": "highlight"}).to_plotly_json(),
        # The month being played.
        go.Scatter(x=[], y=[], mode="markers", marker={"size": 9, "line": {"width": 2}},
                   hoverinfo="skip", meta={"role": "cursor"}).to_plotly_json(),
    ]


def section_traces(r: Norm) -> list[list[dict]]:
    """Twelve traces, one per calendar month: one dot per year."""
    out = []
    months = np.array([int(q[5:7]) for q in r.periods])
    years = [q[:4] for q in r.periods]
    for m in range(1, 13):
        idx = np.flatnonzero(months == m)
        if r.weekly:       # the week nearest the middle of the month, one per year
            best = {}
            for i in idx:
                near = abs(int(r.periods[i][8:10]) - 15)
                if years[i] not in best or near < best[years[i]][0]:
                    best[years[i]] = (near, i)
            idx = np.array(sorted(i for _, i in best.values()), dtype=int)
        out.append([go.Scatter(
            x=rnd(r.xm[idx], DEC[0]), y=rnd(r.ym[idx], DEC[1]), mode="markers",
            marker={"size": 7, "line": {"width": 1}}, customdata=[years[i] for i in idx],
            hovertemplate=f"<b>{r.label}</b>, {MONTH_NAMES[m - 1][:3]} %{{customdata}}<extra></extra>",
            meta={"role": "dot"}).to_plotly_json()])
    return out


def calendar_months(records: list[Norm]) -> tuple[list[str], int]:
    """The shared animation calendar: every month any observed record has, and
    the loop points per month (the monthly records' ndots)."""
    timed = [r for r in records if r.anom is not None]
    first = min(r.periods[0][:7] for r in timed)
    last = max(r.periods[-1][:7] for r in timed)
    ks = {r.ndots for r in timed if not r.weekly}
    if len(ks) != 1:
        raise ValueError("Compare's animation needs every monthly record with the same ndots")
    calendar = [first]
    while calendar[-1] < last:
        calendar.append(month_after(calendar[-1], 1))
    return calendar, ks.pop()


def _weekly_positions(r: Norm, calendar: list[str], k: int, points: int) -> np.ndarray:
    """The loop point (a week) of weekly record ``r`` at each of the first
    ``points`` calendar points (k per month, the first at the middle of its
    month). -1 before the record starts; its last week after it ends."""
    t0 = dt.date.fromisoformat(calendar[0] + "-15")
    days = np.arange(points) * (30.4375 / k)
    weeks = ((t0 - dt.date.fromisoformat(r.periods[0])).days + days) / 7.0
    return np.where(weeks < -0.5, -1, np.minimum(np.rint(weeks), len(r.periods) - 1)).astype(int)


def last_point(r: Norm, calendar: list[str], k: int) -> int:
    """The last calendar point at which record ``r`` has data (its latest
    sample): a monthly record ends with its last month, a weekly one when the
    calendar reaches its last week, which can be a little after the middle of
    the last calendar month. The shared player runs to the latest of the
    chosen records, so every dot reaches its record's end."""
    if r.weekly:
        j = _weekly_positions(r, calendar, k, (len(calendar) + 3) * k)
        return int(np.argmax(j == len(r.periods) - 1))
    return (calendar.index(r.periods[0][:7]) + len(r.periods) - 1) * k


def calendar_map(r: Norm, calendar: list[str], k: int) -> list[int]:
    """For a weekly record: its loop point at each calendar point, up to the
    later of the calendar's last month and the record's own end."""
    points = max((len(calendar) - 1) * k, last_point(r, calendar, k)) + 1
    return _weekly_positions(r, calendar, k, points).tolist()


def build_record(cfg: Config, r: Norm, calendar: tuple[list[str], int] | None = None) -> dict:
    p = r.provisional_from
    on_calendar = r.anom is not None
    return {
        "key": r.key,
        "label": r.label,
        "periods": r.periods,
        "ndots": r.ndots,
        "provisional_from": p,
        "provisional_start": r.periods[p] if p is not None else None,
        "norm": {"mean": round(r.mean, 4), "sigma": round(r.sigma, 4)},
        "loop": {"x": rnd(r.x, DEC[0]), "y": rnd(r.y, DEC[1])},
        "month": {"x": rnd(r.xm, DEC[0]), "y": rnd(r.ym, DEC[1])},
        "label_annotation": label_annotation(r),
        # Axis extents with margins; the page uses the union over the chosen records.
        "extent": {"x": padded(r.x, 0.05, extra_high=0.18), "y": padded(r.y, 0.06),
                   "ta": None if r.anom is None else padded(r.anom, 0.06)},
        "calendar": on_calendar,       # on the time strip, linked by date
        "weekly": r.weekly,
        # Loop points per sample and the 12-month tail, in this record's own points.
        "play": {"step": r.ndots, "tail": r.recent * r.ndots},
        "cal_map": calendar_map(r, *calendar) if (r.weekly and calendar) else None,
        "cal_last": last_point(r, *calendar) if (on_calendar and calendar) else None,
        "traces": {"loop": loop_traces(r), "time": time_traces(r), "section": section_traces(r)},
    }


# ---------------------------------------------------------------------------
# Frame: the layouts, with fixed ranges covering every record
# ---------------------------------------------------------------------------

def build_frame(cfg: Config, records: list[Norm]) -> dict:
    xs = np.concatenate([r.x for r in records])
    ys = np.concatenate([r.y for r in records])
    xr, yr = padded(xs, 0.05, extra_high=0.12), padded(ys, 0.05)
    zero = [
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": 0, "y1": 0, "layer": "below"},
        {"type": "line", "xref": "x", "x0": 0, "x1": 0, "yref": "paper", "y0": 0, "y1": 1, "layer": "below",
         "line": {"dash": "dot"}},
    ]
    square = {"margin": {"l": 64, "r": 16, "t": 28, "b": 52}, "showlegend": False,
              "xaxis": {"title": {"text": X_TITLE}, "range": xr, "nticks": 7},
              "yaxis": {"title": {"text": Y_TITLE}, "range": yr, "nticks": 7},
              "shapes": zero}
    loop = go.Figure(layout={**square, "hovermode": "closest", "hoverdistance": 20,
                             "dragmode": "zoom", "uirevision": "compare"})
    section = go.Figure(layout={**square, "hovermode": "closest", "hoverdistance": 12,
                                "dragmode": "zoom", "uirevision": "compare-section"})

    timed = [r for r in records if r.anom is not None]
    calendar, k = calendar_months(records)
    first, last = calendar[0], calendar[-1]
    time_end = month_after(last, 9)
    time = go.Figure(layout={
        "margin": {"l": 64, "r": 16, "t": 28, "b": 28}, "showlegend": False,
        "hovermode": "x unified", "dragmode": "select", "selectdirection": "h", "uirevision": "compare",
        "xaxis": {"range": [first, time_end], "showspikes": True, "spikemode": "across",
                  "spikethickness": 1, "spikedash": "solid", "hoverformat": "%b %Y"},
        "yaxis": {"title": {"text": "Filtered anomaly / σ"}, "fixedrange": True, "nticks": 5,
                  "range": padded(np.concatenate([r.anom for r in timed]), 0.06)},
        "shapes": [{"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": 0, "y1": 0,
                    "layer": "below"}],
        "meta": {"narrow_top": 8},
    })
    events = []
    for ev in cfg.events:
        end = ev.end or last
        running = " (running)" if ev.end is None else ""
        events.append({"label": ev.label, "start": ev.start, "end": end,
                       "range": f"{month_label(ev.start)} to {month_label(end)}{running}"})
    # One calendar for the shared animation: every month any observed record has.
    return {"loop": export(loop), "time": export(time), "section": export(section),
            "time_end": time_end, "events": events,
            "calendar": calendar, "calendar_labels": [month_label(q) for q in calendar],
            "play": {"unit": k, "step": k, "tail": RECENT_MONTHS * k}}


def files(cfg: Config) -> dict:
    records = {}

    def rec(key):          # computed once, on first use
        if not records:
            for r in all_records(cfg):
                records[r.key] = r
        return records[key]

    keys = [d.key for d in cfg.datasets] + [MODEL_KEY]
    out = {"data/compare/frame.json": lambda: build_frame(cfg, [rec(k) for k in keys])}
    for key in keys:
        out[f"data/compare/{key}.json"] = (
            lambda key=key: build_record(cfg, rec(key), calendar_months([rec(k) for k in keys])))
    return out


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def slot_controls(cfg: Config) -> list[Control]:
    options = [Option(d.key, d.label, d.group.label) for d in cfg.datasets]
    label = cfg.models["duffing"]["presets"][cfg.models["duffing"]["compare_preset"]]["label"]
    options.append(Option(MODEL_KEY, f"Duffing model, {label}", "Model"))
    none = [Option("none", "None", "")]
    return [
        Control("a", "Record A", options, SLOT_DEFAULTS["a"]),
        Control("b", "Record B", options, SLOT_DEFAULTS["b"]),
        Control("c", "Record C", none + options, SLOT_DEFAULTS["c"]),
    ]


NOTES = f"""
<p>Each record is put on the same dimensionless plane:
x<sub>n</sub> = (x {MINUS} mean) / σ<sub>x</sub> and
y<sub>n</sub> = (dx/dt) / σ<sub>x</sub>, with the mean and standard deviation
σ<sub>x</sub> of that record's filtered values over its analysis window. Both axes
use the same σ<sub>x</sub>, so each loop keeps its shape: a taller loop
is a record that moves faster relative to its own typical swing.</p>
<p>The time strip shows each record's filtered anomaly (seasonal cycle
removed) divided by that anomaly's own standard deviation, so El Niño events
line up across records whatever their units or seasonal swing. The model has
no real calendar, so it is on the loops and the section but not on the time
strip.</p>
<p>Play runs every chosen record on the same calendar: one dot per record,
each at the same month, with its last 12 months trailing behind and its
path building up; the time strip marks that month on each record. A
highlighted El Niño or dragged period plays alone. The model has no
calendar, so it stays drawn whole and does not move.</p>
<p>The annual section keeps one point per year, in the chosen calendar month.
Records that share a seasonal rhythm cluster in the same part of the plane
for the same month.</p>
"""


def page(cfg: Config) -> Page:
    from enso.site.pages.phase import default_event
    months = [Option(str(i), name) for i, name in enumerate(MONTH_NAMES)]
    loops = Panel(id="compare", kind="compare-linked", title="Loops on a normalised plane",
                  data="data/compare/{a}.json", files=lambda: files(cfg), player=MONTH_SPEEDS)
    section = Panel(id="compare-section", kind="compare-section", title="Annual section",
                    data="data/compare/{a}.json", files=lambda: {},
                    controls=[Control("month", "Month", months, "0", play=True)],
                    caption=("One point per year in the chosen month, for each record, on the same "
                             "normalised plane as the loops."))
    return Page(
        slug="compare",
        title="Compare datasets",
        nav_label="Compare",
        intro=("Up to three records on one dimensionless phase plane, each scaled by its own "
               "standard deviation so their shapes and timing can be compared."),
        panels=[loops, section],
        template="compare.html",
        notes_html=NOTES,
        controls=slot_controls(cfg),
        attrs=default_event(cfg),
    )
