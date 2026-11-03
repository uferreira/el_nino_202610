"""Duffing simulation page: precomputed model runs (enso.model).

Two panels share the preset and forcing controls:

* Trajectory: the last stretch of the run as a loop (X, dX/dt), linked to
  its time series.
* Poincaré section: one long trajectory, one dot per forcing cycle, at a
  chosen phase of the forcing. Stepping the phase shows the attractor
  stretch and fold.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from enso import model
from enso.config import Config
from enso.phasespace import MONTH_NAMES
from enso.site.figures import MINUS, export, fmt, history_paths, padded, rnd
from enso.site.registry import Control, Option, Page, Panel

DEC = 4


def _m(cfg: Config) -> dict:
    return cfg.models["duffing"]


def _labels(cfg: Config, preset: str) -> dict:
    p = _m(cfg)["presets"][preset]
    if p.get("time_unit") == "month":
        return {"x": "X (model units)", "y": "dX/dt (per month)", "x_short": "X",
                "time": "Model year", "cycle": "year"}
    return {"x": "x", "y": "dx/dt", "x_short": "x", "time": "Forcing cycle", "cycle": "cycle"}


def _regime(run: model.ModelRun, cycles: int) -> str:
    if run.repeat == 1:
        return "Settles into a single loop: the section is one point, repeating every forcing cycle."
    if run.repeat:
        return (f"Settles into a cycle that repeats every {run.repeat} forcing cycles: "
                f"the section is {run.repeat} points.")
    return (f"Does not repeat within {cycles} forcing cycles: chaotic, or a cycle too long to see. "
            "The section never closes on a few points; it traces the attractor's folded cross-section.")


def facts(cfg: Config, preset: str, factor: float, run: model.ModelRun) -> dict:
    p = _m(cfg)["presets"][preset]
    q = run.params
    deg = "°"
    return {
        "label": p["label"],
        "note": p["note"],
        "equation": f"X″ = K1·X + K3·X³ + FA·cos(W·t {MINUS} FF) + B·X′",
        "K1": fmt(q["K1"], 4), "K3": fmt(q["K3"], 4),
        "FA": fmt(q["FA"], 4) + (f" (×{factor:g})" if factor != 1 else ""),
        "FF": fmt(q["FF"], 0) + deg, "B": fmt(q["B"], 4), "W": fmt(q["W"], 4),
        "regime": _regime(run, model.settings(cfg, preset)["section_cycles"]),
    }


# ---------------------------------------------------------------------------
# Trajectory panel
# ---------------------------------------------------------------------------

def trajectory(cfg: Config, preset: str, fa: str) -> dict:
    m = model.settings(cfg, preset)
    factor = float(fa)
    run = model.load(cfg, preset, factor)
    lab = _labels(cfg, preset)
    k, spc = m["ndots"], m["samples_per_cycle"]
    per_cycle = spc * k
    x, y = run.traj_x, run.traj_y

    # Hover labels, one per sample.
    ns = (len(x) - 1) // k + 1
    if lab["cycle"] == "year" and spc == 12:
        names = [f"Model year {j // spc + 1}, {MONTH_NAMES[j % spc][:3]}" for j in range(ns)]
    else:
        names = [f"Cycle {j // spc + 1}, phase {360 * (j % spc) // spc}°" for j in range(ns)]

    loop = go.Figure()
    loop.add_traces(history_paths(x, y, per_cycle, len(x) - 1, (DEC, DEC), width=1.0))
    loop.add_scatter(x=[], y=[], mode="markers", marker={"size": 12, "line": {"width": 2}},
                     hoverinfo="skip", meta={"role": "cursor"})
    loop.add_scatter(x=rnd(x[::k], DEC), y=rnd(y[::k], DEC), mode="markers",
                     marker={"size": 9, "opacity": 0}, customdata=names,
                     hovertemplate=(f"<b>%{{customdata}}</b><br>{lab['x_short']} %{{x:.3f}}"
                                    f"<br>rate %{{y:+.3f}}<extra></extra>"),
                     meta={"role": "hover"})
    loop.update_layout(
        margin={"l": 64, "r": 16, "t": 28, "b": 52}, showlegend=False,
        hovermode="closest", hoverdistance=20, dragmode="zoom", uirevision=f"{preset}",
        xaxis={"title": {"text": lab["x"]}, "range": padded(x), "nticks": 7},
        yaxis={"title": {"text": lab["y"]}, "range": padded(y), "nticks": 7},
        shapes=[{"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": 0, "y1": 0, "layer": "below"},
                {"type": "line", "xref": "x", "x0": 0, "x1": 0, "yref": "paper", "y0": 0, "y1": 1,
                 "layer": "below", "line": {"dash": "dot"}}],
    )

    t = run.traj_t[::k] + 1          # in forcing cycles, counting from 1
    time = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09)
    for row, (vals, name) in enumerate([(x[::k], lab["x_short"]), (y[::k], "rate")], start=1):
        rid = "X" if row == 1 else "V"
        time.add_scatter(x=rnd(t, 4), y=rnd(vals, DEC), mode="lines", line={"width": 1.25},
                         hovertemplate=f"{lab['time']} %{{x:.2f}}  {name} %{{y:.3f}}<extra></extra>",
                         meta={"role": "series", "row": rid}, row=row, col=1)
        time.add_scatter(x=[], y=[], mode="markers", marker={"size": 10, "line": {"width": 2}},
                         hoverinfo="skip", meta={"role": "cursor", "row": rid, "of": "series"}, row=row, col=1)
    time.update_layout(margin={"l": 64, "r": 16, "t": 28, "b": 44}, showlegend=False,
                       hovermode="x", hoverdistance=-1, dragmode="zoom", meta={"narrow_top": 8},
                       shapes=[{"type": "line", "xref": "x domain", "x0": 0, "x1": 1, "yref": yr,
                                "y0": 0, "y1": 0, "layer": "below"} for yr in ("y", "y2")])
    time.update_xaxes(range=[float(t[0]), float(t[-1])], showspikes=True, spikemode="across",
                      spikethickness=1, spikedash="solid")
    time.update_xaxes(showticklabels=False, ticks="", row=1, col=1)
    time.update_xaxes(title_text=lab["time"], row=2, col=1)
    time.update_yaxes(fixedrange=True, nticks=4)
    time.update_yaxes(title_text=lab["x_short"], row=1, col=1)
    time.update_yaxes(title_text=lab["y"].split(" ")[0], row=2, col=1)

    return {
        "key": f"{preset}-x{factor:g}",
        "facts": facts(cfg, preset, factor, run),
        "span": f"Last {m['trajectory_cycles']} forcing cycles of the run, after "
                f"{m['transient_cycles']} discarded.",
        "figures": {"phase": export(loop), "time": export(time)},
    }


# ---------------------------------------------------------------------------
# Section panel
# ---------------------------------------------------------------------------

def section(cfg: Config, preset: str, fa: str, phase: str) -> dict:
    m = model.settings(cfg, preset)
    factor = float(fa)
    run = model.load(cfg, preset, factor)
    lab = _labels(cfg, preset)
    j = int(phase)
    deg = 360 * j // m["phases"]
    pts = run.section[j]
    # Fixed ranges over every phase, so the axes do not jump while playing.
    allx, ally = run.section[..., 0].ravel(), run.section[..., 1].ravel()
    fig = go.Figure()
    fig.add_scatter(x=rnd(pts[:, 0], DEC), y=rnd(pts[:, 1], DEC), mode="markers",
                    marker={"size": 3.5}, meta={"role": "points"},
                    hovertemplate=f"{lab['cycle'].capitalize()} %{{pointNumber}}<br>"
                                  f"{lab['x_short']} %{{x:.3f}}, rate %{{y:+.3f}}<extra></extra>")
    fig.update_layout(
        margin={"l": 64, "r": 16, "t": 28, "b": 52}, showlegend=False,
        hovermode="closest", hoverdistance=8, dragmode="zoom", uirevision=f"{preset}-{fa}",
        xaxis={"title": {"text": lab["x"]}, "range": padded(allx), "nticks": 7},
        yaxis={"title": {"text": lab["y"]}, "range": padded(ally), "nticks": 7},
        shapes=[{"type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": 0, "y1": 0, "layer": "below"},
                {"type": "line", "xref": "x", "x0": 0, "x1": 0, "yref": "paper", "y0": 0, "y1": 1,
                 "layer": "below", "line": {"dash": "dot"}}],
    )
    when = f"{deg}° into each forcing cycle"
    if lab["cycle"] == "year":
        when += f" (start of {MONTH_NAMES[j][:3]} in model months)"
    return {
        "filename": f"duffing-{preset}-x{factor:g}-section-{deg}deg",
        "phase_label": when,
        "count": f"{len(pts):,}".replace(",", "\u202f") + " dots, one per forcing cycle, from one trajectory.",
        "regime": _regime(run, m["section_cycles"]),
        "figure": export(fig),
    }


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

def page(cfg: Config) -> Page:
    m = _m(cfg)
    presets = Control("preset", "Preset",
                      [Option(k, v["label"]) for k, v in m["presets"].items()],
                      next(iter(m["presets"])))
    fas = Control("fa", "Forcing amplitude",
                  [Option(f"{f:g}", f"×{f:g} of the preset" if f != 1 else "Preset value")
                   for f in m["fa_factors"]], "1")
    phases = Control("phase", "Phase of the forcing",
                     [Option(str(j), f"{360 * j // m['phases']}°") for j in range(m["phases"])],
                     "0", play=True)
    traj = Panel(id="trajectory", kind="trajectory-linked", title="Trajectory",
                 data="data/duffing/trajectory/{preset}/{fa}.json",
                 build=lambda preset, fa: trajectory(cfg, preset, fa))
    sec = Panel(id="section", kind="figure", title="Poincaré section",
                data="data/duffing/section/{preset}/{fa}/{phase}.json",
                build=lambda preset, fa, phase: section(cfg, preset, fa, phase),
                controls=[phases],
                caption=("One long trajectory, sampled once per forcing cycle at the chosen phase. "
                         "A cycle gives a few points; chaos gives a folded cloud."))
    return Page(
        slug="duffing",
        title="Duffing simulation",
        nav_label="Duffing",
        intro=("A forced double-well oscillator, the simplest model whose attractor resembles the "
               "observed ENSO loop. All runs are computed in Python; pick a preset and a forcing."),
        panels=[traj, sec],
        template="duffing.html",
        notes_html=NOTES,
        controls=[presets, fas],
    )


NOTES = """
<p>The potential V(X) = &minus;K1&middot;X&sup2;/2 &minus; K3&middot;X&#8308;/4 has two wells
when K1 &gt; 0 and K3 &lt; 0, read as the warm (El Niño) and cool (La Niña)
states. The periodic forcing, read as the annual trade-wind cycle, pushes the
state between the wells; damping (B &lt; 0) removes energy.</p>
<p>The El Niño fit uses the coefficients of the original Java applet. They
were not re-estimated from the records on this site, so it is a hypothesis to
compare with the observations (see the Compare page), not a validated fit.</p>
<p>Each run integrates one trajectory with scipy's RK45 (relative tolerance
1e-6), discards the first forcing cycles as transient, and keeps the rest.
The section shows that same trajectory once per forcing cycle; it is not a
cloud of different starting points. Runs are cached in the repository, so
the pages always show the same trajectory.</p>
"""
