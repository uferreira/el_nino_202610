"""Phase diagrams page: the loop (T, dT/dt) linked to its time series.

One JSON file per dataset holds both figures, the loop arrays used for
highlighting, and the readout text. All numbers and labels are produced
here; site.js only draws them, links hover and highlights, and paints
colours from the theme.

The last ``provisional_months`` of every filtered record will still change
as new observations arrive (METHODS.md, "Provisional end"): that stretch is
dashed on the loop and shaded on the time panel.
"""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from enso import series, status, weekly
from enso.config import Config, Dataset
from enso.phasespace import PhaseSeries, compute, month_label
from enso.site.figures import (axis_end, export, fmt, history_paths, nice_step, padded,
                                play_traces, rnd)
from enso.site.registry import Control, Option, Page, Panel, Player

RECENT_MONTHS = 12
# Animation speeds, in samples (months, or weeks) per second. Monthly: 6 plays
# the whole record in under two minutes, an El Niño in about three seconds;
# weekly: 26 weeks is the same pace.
SPEEDS = {
    "monthly": {"values": (3, 6, 12, 24, 48), "default": "6", "unit": "month"},
    "weekly": {"values": (13, 26, 52, 104, 208), "default": "26", "unit": "week"},
}
DASH = "4px,3px"
# Decimals kept in the JSON and shown to readers, per unit: (value, rate).
DECIMALS = {"°C": (3, 4), "mm": (1, 2)}
# Who publishes each source type, for "<source> last checked <date>".
SOURCE_NAMES = {"noaa_sst": "NOAA CPC", "uhslc": "UHSLC"}
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


_SERIES: dict[tuple[int, str], tuple[Config, PhaseSeries]] = {}


def phase_series(cfg: Config, key: str) -> PhaseSeries:
    """The analysed record, computed once per config (Compare reuses it)."""
    hit = _SERIES.get((id(cfg), key))
    if hit is None or hit[0] is not cfg:
        ds = cfg.dataset(key)
        ps = (weekly.to_phase_series(weekly.read(), ds, cfg) if ds.is_weekly
              else compute(series.read(key), ds, cfg.filter))
        hit = _SERIES[(id(cfg), key)] = (cfg, ps)
    return hit[1]


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------

def provisional_samples(ps: PhaseSeries, cfg: Config) -> int:
    """Samples in the provisional zone: 10 months, or the same span in weeks (43)."""
    return weekly.provisional_weeks(cfg.filter) if ps.weekly else cfg.filter.provisional_months


def provisional_span(ps: PhaseSeries, cfg: Config) -> str:
    return f"{provisional_samples(ps, cfg)} {'weeks' if ps.weekly else 'months'}"


def first_provisional(ps: PhaseSeries, cfg: Config) -> int:
    """Index of the first provisional sample."""
    return max(ps.n_months - provisional_samples(ps, cfg), 0)


def phase_figure(ps: PhaseSeries, cfg: Config) -> dict:
    ds = ps.dataset
    dec = DECIMALS[ds.unit]
    dv, dr = dec
    sv, sr = SHOW[ds.unit]
    lab = axis_labels(ds)
    n, k = ps.n_months, ps.ndots
    p = first_provisional(ps, cfg)
    r = max(n - ps.recent, 0)
    labels = [month_label(q) + (" (provisional)" if i >= p else "") for i, q in enumerate(ps.periods)]

    fig = go.Figure()
    fig.add_traces(history_paths(ps.T, ps.V, ps.year_points, p * k, dec))
    fig.add_scatter(x=rnd(ps.T[p * k:], dv), y=rnd(ps.V[p * k:], dr), mode="lines",
                    line={"width": 1.25, "dash": DASH}, hoverinfo="skip",
                    meta={"role": "history", "provisional": True})
    for prov in (False, True):
        fig.add_scatter(x=[], y=[], mode="lines",
                        line={"width": 2.5, **({"dash": DASH} if prov else {})},
                        hoverinfo="skip", meta={"role": "highlight", "provisional": prov})
    fig.add_scatter(x=rnd(ps.T[r * k:p * k + 1], dv), y=rnd(ps.V[r * k:p * k + 1], dr), mode="lines",
                    line={"width": 2}, hoverinfo="skip", meta={"role": "recent"})
    fig.add_scatter(x=rnd(ps.T[max(p, r) * k:], dv), y=rnd(ps.V[max(p, r) * k:], dr), mode="lines",
                    line={"width": 2, "dash": DASH}, hoverinfo="skip",
                    meta={"role": "recent", "provisional": True})
    fig.add_scatter(x=rnd(ps.T_month[r:], dv), y=rnd(ps.V_month[r:], dr), mode="markers",
                    marker={"size": 5}, hoverinfo="skip", meta={"role": "recent"})
    fig.add_scatter(x=[round(float(ps.T[-1]), dv)], y=[round(float(ps.V[-1]), dr)],
                    mode="markers", marker={"size": 12, "line": {"width": 2}},
                    hoverinfo="skip", meta={"role": "now"})
    # Filled while playing: the path so far, the last 12 months behind the dot, the dot.
    fig.add_traces(play_traces(dash=DASH))
    fig.add_scatter(x=[], y=[], mode="markers", marker={"size": 13, "line": {"width": 2}},
                    hoverinfo="skip", meta={"role": "cursor"})
    # Invisible monthly markers: the hover targets (bigger than the line).
    fig.add_scatter(
        x=rnd(ps.T_month, dv), y=rnd(ps.V_month, dr), mode="markers",
        marker={"size": 10, "opacity": 0}, customdata=labels,
        hovertemplate=(f"<b>%{{customdata}}</b><br>{lab['value_short']} %{{x:.{sv}f}} {ds.unit}"
                       f"<br>Rate %{{y:+.{sr}f}} {ds.rate_unit}<extra></extra>"),
        meta={"role": "hover"},
    )

    if ds.quantity == "absolute":
        ref = float(ps.T.mean())
        ref_label = f"mean {fmt(ref, sv)}"
    else:
        ref, ref_label = 0.0, ""
    shapes = [
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": 0, "y1": 0, "layer": "below"},
        {"type": "line", "xref": "x", "x0": ref, "x1": ref, "yref": "paper", "y0": 0, "y1": 1,
         "layer": "below", "line": {"dash": "dot"}},
    ]
    xr, yr = padded(ps.T, extra_high=0.08), padded(ps.V, extra_high=0.04)
    # Label the current month on the side with more room, so it is never clipped.
    right_side = float(ps.T[-1]) > xr[0] + 0.7 * (xr[1] - xr[0])
    annotations = [{
        "x": float(ps.T[-1]), "y": float(ps.V[-1]), "xref": "x", "yref": "y",
        "name": "now", "text": month_label(ps.periods[-1]), "showarrow": False,
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
        xaxis={"title": {"text": lab["value"]}, "range": xr, "nticks": 7},
        yaxis={"title": {"text": lab["rate"]}, "range": yr, "nticks": 7},
        shapes=shapes,
        annotations=annotations,
    )
    return export(fig)


def time_figure(ps: PhaseSeries, cfg: Config) -> dict:
    """Two rows on one time axis: the value (thin grey full series and, on a
    secondary axis at the same scale, the bold filtered anomaly) and the rate."""
    ds = ps.dataset
    dv, dr = DECIMALS[ds.unit]
    sv, sr = SHOW[ds.unit]
    lab = axis_labels(ds)
    x = ps.periods
    p = first_provisional(ps, cfg)
    cycle = ps.has_seasonal_cycle
    unit = ds.unit
    recent = ps.recent
    day = "%d " if ps.weekly else ""        # a week is named by its date

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                        specs=[[{"secondary_y": cycle}], [{}]])

    def add(trace: dict, row: int, secondary: bool = False):
        fig.add_trace(go.Scatter(**trace), row=row, col=1,
                      secondary_y=secondary if (row == 1 and cycle) else None)

    def family(y, decimals, row: str, of: str, secondary: bool, row_i: int):
        """Highlight, recent tail, current point and cursor for one source line."""
        add({"x": [], "y": [], "mode": "lines", "line": {"width": 2.75}, "hoverinfo": "skip",
             "meta": {"role": "highlight", "row": row, "of": of}}, row_i, secondary)
        add({"x": x[-recent:], "y": rnd(y[-recent:], decimals), "mode": "lines",
             "line": {"width": 2.25}, "hoverinfo": "skip",
             "meta": {"role": "recent", "row": row, "of": of}}, row_i, secondary)
        add({"x": [x[-1]], "y": [round(float(y[-1]), decimals)], "mode": "markers",
             "marker": {"size": 8, "line": {"width": 1.5}}, "hoverinfo": "skip",
             "meta": {"role": "now", "row": row}}, row_i, secondary)
        add({"x": [], "y": [], "mode": "markers", "marker": {"size": 10, "line": {"width": 2}},
             "hoverinfo": "skip", "meta": {"role": "cursor", "row": row, "of": of}}, row_i, secondary)

    # Row 1: value.
    anomaly_label = "Anomaly" if cycle else lab["value_short"]
    if cycle:
        add({"x": x, "y": rnd(ps.T_month, dv), "mode": "lines", "line": {"width": 1},
             "hovertemplate": f"{lab['value_short']} %{{y:.{sv}f}} {unit}<extra></extra>",
             "meta": {"role": "series", "row": "T"}}, 1, False)
    add({"x": x, "y": rnd(ps.anomaly, dv), "mode": "lines", "line": {"width": 2},
         "hovertemplate": f"<b>%{{x|{day}%b %Y}}</b>  {anomaly_label} %{{y:+.{sv}f}} {unit}<extra></extra>",
         "meta": {"role": "anomaly", "row": "T"}}, 1, True)
    family(ps.anomaly, dv, "T", "anomaly", True, 1)

    # Row 2: rate.
    add({"x": x, "y": rnd(ps.V_month, dr), "mode": "lines", "line": {"width": 1.25},
         "hovertemplate": f"<b>%{{x|{day}%b %Y}}</b>  Rate %{{y:+.{sr}f}} {ds.rate_unit}<extra></extra>",
         "meta": {"role": "series", "row": "V"}}, 2)
    family(ps.V_month, dr, "V", "series", False, 2)

    # Axis names as plotly assigned them ("y", "y2", ...).
    y_anom = next(t.yaxis for t in fig.data if t.meta["role"] == "anomaly") or "y"
    y_rate = next(t.yaxis for t in fig.data if t.meta == {"role": "series", "row": "V"})
    ax = lambda name: "yaxis" + name[1:]  # "y3" -> "yaxis3"

    if cycle:
        # Same scale on both axes (one unit is the same height), anomaly zero at the series mean.
        m = float(ps.T_month.mean())
        lo = min(float(ps.T_month.min()), float(ps.anomaly.min()) + m)
        hi = max(float(ps.T_month.max()), float(ps.anomaly.max()) + m)
        pad = (hi - lo) * 0.06
        step = nice_step(hi - lo, 3)
        fig.layout["yaxis"].update(range=[lo - pad, hi + pad], tick0=0, dtick=step,
                                   title={"text": f"{lab['value_short']} ({unit})"})
        fig.layout[ax(y_anom)].update(range=[lo - pad - m, hi + pad - m], showgrid=False,
                                      tick0=0, dtick=step,
                                      title={"text": f"Anomaly ({unit})"})
    else:
        fig.layout["yaxis"].update(range=padded(ps.anomaly, 0.06),
                                   title={"text": f"{lab['value_short']} ({unit})"})
    fig.layout[ax(y_rate)].update(title={"text": lab["rate_short"]}, range=padded(ps.V_month, 0.06))

    # Provisional zone: shaded, labelled in the gap between the rows (no data there).
    x_end = axis_end(x[-1], 9)
    row1 = fig.layout["yaxis"].domain
    row2 = fig.layout[ax(y_rate)].domain
    gap_mid = (row1[0] + row2[1]) / 2
    shapes = [
        {"type": "line", "xref": "x domain", "x0": 0, "x1": 1, "yref": y_anom, "y0": 0, "y1": 0,
         "layer": "below", "line": {"dash": "dot"}},
        {"type": "line", "xref": "x domain", "x0": 0, "x1": 1, "yref": y_rate, "y0": 0, "y1": 0,
         "layer": "below"},
        {"type": "rect", "name": "provisional", "xref": "x", "yref": "paper", "layer": "below",
         "x0": x[p], "x1": x_end, "y0": 0, "y1": 1, "line": {"width": 0}},
    ]
    annotations = [{
        "x": x[p], "xref": "x", "y": gap_mid, "yref": "paper", "text": "provisional ▸",
        "showarrow": False, "xanchor": "right", "yanchor": "middle", "xshift": -2,
    }]

    fig.update_layout(
        margin={"l": 64, "r": 56 if cycle else 16, "t": 28, "b": 28},
        meta={"narrow_top": 8},   # phones: no PNG button, so no room needed above
        showlegend=False,
        hovermode="x",
        hoverdistance=-1,
        dragmode="select",
        selectdirection="h",
        uirevision=ds.key,
        shapes=shapes,
        annotations=annotations,
    )
    spikes = {"showspikes": True, "spikemode": "across", "spikesnap": "hovered data",
              "spikethickness": 1, "spikedash": "solid"}
    fig.update_xaxes(range=[x[0], x_end], **spikes)
    fig.update_xaxes(showticklabels=False, ticks="", row=1, col=1)
    fig.update_yaxes(fixedrange=True, nticks=4)
    return export(fig)


# ---------------------------------------------------------------------------
# Readout and events
# ---------------------------------------------------------------------------

def readout(ps: PhaseSeries, cfg: Config) -> dict:
    ds = ps.dataset
    sv, sr = SHOW[ds.unit]
    lab = axis_labels(ds)
    V = float(ps.V[-1])
    last = ps.periods[-1]
    w = ps.window
    fetched = date.fromisoformat(ps.fetched) if ps.fetched else None
    window = f"{month_label(w['start'])} to {month_label(w['end'])}"
    notes = []
    if ps.weekly and ps.has_seasonal_cycle:
        notes.append(f"Anomaly: against the seasonal cycle of {window}, a mean plus "
                     f"{w['harmonics']} annual harmonics fitted to the weeks.")
        notes.append("Each point is a week, named by its middle day (Wednesday); the rate is per month.")
    elif ps.has_seasonal_cycle:
        month_name = month_label(last, short=False).split()[0]
        notes.append(f"Anomaly: against the {window} average for {month_name}.")
    if ds.quantity == "record_mean":
        notes.append(f"Sea level is relative to its {window} mean.")
    notes.append(f"The rate and the last {provisional_span(ps, cfg)} of the loop "
                 f"are provisional: they will change as new data arrive.")
    return {
        "month": ("Week centred on " if ps.weekly else "") + month_label(last, short=False),
        "observed_label": f"{lab['value_short']}, observed",
        "observed": f"{fmt(float(ps.observed[-1]), sv)} {ds.unit}",
        "anomaly": (f"{fmt(float(ps.observed_anomaly[-1]), sv, signed=True)} {ds.unit}"
                    if ps.has_seasonal_cycle else None),
        "rate": f"{fmt(V, sr, signed=True)} {ds.rate_unit}",
        "state": lab["rate_word"][0] if V >= 0 else lab["rate_word"][1],
        "rising": V >= 0,
        "note": " ".join(notes),
        "through": month_label(last, short=False),
        "updated": f"{fetched.day} {fetched:%b %Y}" if fetched else "unknown",
        # Last successful download (data/status), new month or not: a date
        # that stops moving means the update has stopped running.
        "source_name": SOURCE_NAMES.get(ds.source["type"], ds.source["type"]),
        "checked": status.checked_label(ds.source["type"], ds.key) or "never recorded",
    }


def events(ps: PhaseSeries, cfg: Config) -> list[dict]:
    """Each event as the first and last sample inside its months (for a
    weekly record: the first week in its first month, the last in its last)."""
    out = []
    months = [q[:7] for q in ps.periods]
    first, last = months[0], months[-1]
    for ev in cfg.events:
        end = ev.end or last
        if end < first or ev.start > last:
            continue
        start, end = max(ev.start, first), min(end, last)
        running = " (running)" if ev.end is None else ""
        out.append({
            "label": ev.label,
            "i0": next(i for i, q in enumerate(months) if q >= start),
            "i1": max(i for i, q in enumerate(months) if q <= end),
            "range": f"{month_label(start)} to {month_label(end)}{running}",
        })
    return out


def play_info(ps: PhaseSeries) -> dict:
    """What the animation needs, in loop points: a speed unit (a month, or a
    week), a sample, the 12-month tail; and the speed choices in that unit."""
    s = SPEEDS["weekly" if ps.weekly else "monthly"]
    return {"unit": ps.ndots, "step": ps.ndots, "tail": ps.recent * ps.ndots,
            "unit_name": s["unit"], "speed_default": s["default"],
            "speeds": [{"value": str(v), "label": f"{v} {s['unit']}s/s"} for v in s["values"]]}


def build_dataset(cfg: Config, key: str) -> dict:
    ps = phase_series(cfg, key)
    ds = ps.dataset
    w = ps.window
    dv, dr = DECIMALS[ds.unit]
    return {
        "dataset": {"key": ds.key, "label": ds.label, "long_label": ds.long_label,
                    "source": ps.source},
        "periods": ps.periods,
        "period_labels": [month_label(p) for p in ps.periods],
        "ndots": ps.ndots,
        "provisional_from": first_provisional(ps, cfg),
        "provisional_months": cfg.filter.provisional_months,
        "provisional_samples": provisional_samples(ps, cfg),
        "provisional_span": provisional_span(ps, cfg),
        "cadence": ps.cadence,
        "recent_months": RECENT_MONTHS,
        "window": (f"{month_label(w['start'])} to {month_label(w['end'])}, "
                   + (f"{w['n_weeks']} weeks" if ps.weekly else f"{w['n_months']} months")),
        "gap_filled_months": int(ps.gap_filled.sum()),
        "loop": {"x": rnd(ps.T, dv), "y": rnd(ps.V, dr)},
        "now": readout(ps, cfg),
        "events": events(ps, cfg),
        # Animation, in loop points: per speed unit (a month, or a week), per
        # sample, and the tail behind the dot (12 months).
        "play": play_info(ps),
        "figures": {"phase": phase_figure(ps, cfg), "time": time_figure(ps, cfg)},
    }


def default_event(cfg: Config) -> dict:
    """The running event to highlight on opening, when its index is past the threshold."""
    ce = cfg.current_event
    if ce is None:
        return {}
    latest = float(phase_series(cfg, ce.dataset).observed_anomaly[-1])
    return {"default-event": ce.label} if latest >= ce.threshold else {}


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
month-to-month noise. NINO1+2 and sea level keep their seasonal cycle, so
they also trace a small loop every year; the bold line in the time panel is
the same filtered record with the seasonal cycle taken out, so El Niño
events stand out.</p>
<p>The filter ends exactly on the latest observation, and the last months of
the filtered record move as new months arrive. That stretch is dashed on the
loop and shaded in the time panel (METHODS.md in the repository explains
how long it is and why).</p>
<p>Drag across the time series to highlight a period; double-click or Clear
removes it. Hover either view to find the same month in the other.</p>
<p>NINO1+2 weekly is NOAA's weekly OISST analysed the same way in weekly
units: a point per week (named by its Wednesday), the cutoffs in weeks, the
rate still per month, and the provisional end of the same length in time
(43 weeks). Its seasonal cycle is a fit of four annual harmonics.</p>
<p>Play draws the loop through time: a dot moves month by month (week by week
for NINO1+2 weekly, with its speeds in weeks per second), the last
12 months trail behind it in red, and the path it has drawn builds up
behind. The time panel marks the same month. With an El Niño (or a dragged
period) highlighted, Play runs only that period. The slider moves to any
month; the reset button returns to the whole record.</p>
"""


# The speeds the page starts with (monthly); site.js swaps in the weekly ones
# (weeks per second) when a weekly dataset is chosen (data.play.speeds).
MONTH_SPEEDS = Player(
    speeds=[Option(str(v), f"{v} months/s") for v in SPEEDS["monthly"]["values"]],
    default=SPEEDS["monthly"]["default"], unit="month",
)


def page(cfg: Config) -> Page:
    panel = Panel(
        player=MONTH_SPEEDS,
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
        attrs=default_event(cfg),
    )
