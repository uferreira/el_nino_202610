"""Duffing simulation page: precomputed model runs (enso.model).

Two panels share the preset and forcing controls:

* Trajectory: the last stretch of the run as a loop (X, dX/dt), linked to
  its time series.
* Poincaré section: one long trajectory, one dot per forcing cycle, at a
  chosen phase of the forcing. Stepping the phase shows the attractor
  stretch and fold.
"""

from __future__ import annotations

import math

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


def _regime(run: model.ModelRun, L: dict) -> dict:
    """Classification by the largest Lyapunov exponent, in words."""
    lam, se = L["lambda1"], L["se"]
    times = math.exp(lam)
    if L["regime"] == "chaotic":
        text = (f"\u03bb\u2081 > 0: nearby trajectories separate, about {times:.1f} times "
                f"further apart every forcing cycle. Chaotic.")
    elif L["regime"] == "periodic":
        cyc = (f"a cycle of {run.repeat} forcing period{'s' if run.repeat > 1 else ''}"
               if run.repeat else "a cycle longer than 24 forcing periods")
        text = f"\u03bb\u2081 < 0: nearby trajectories converge onto {cyc}. Periodic."
    else:
        text = ("\u03bb\u2081 \u2248 0: trajectories neither separate nor converge; motion on a torus. "
                "Quasi-periodic.")
    if not L["converged"]:
        text += " The estimate has not settled; treat this class as tentative."
    return {"class": L["regime"], "text": text}


def _lyapunov_facts(cfg: Config, preset: str, L: dict) -> dict:
    lam, se = L["lambda1"], L["se"]
    per_month = ""
    if cfg.models["duffing"]["presets"][preset].get("time_unit") == "month":
        per_month = f" ({fmt(lam / L['period'], 4, signed=True)} per month)"
    a, b = L["window"]
    D, dse = model.kaplan_yorke(lam, L["lambda2"], se)
    if lam < 0:
        dim, dim_note = "0", "a finite set of points"
    else:
        dim, dim_note = f"{D:.3f} \u00b1 {dse:.3f}", "1 + \u03bb\u2081 / |\u03bb\u2082| of the section"
    c = L.get("check")
    check = ""
    if c:
        it = c["integrator"]
        check = (f" Robustness: {it['method']} at rtol {it['rtol']:.0e} gives "
                 f"{fmt(c['lambda1'], 3, signed=True)} \u00b1 {c['se']:.3f} "
                 f"({L['integrator']['method']} at rtol {L['integrator']['rtol']:.0e}: "
                 f"{fmt(lam, 3, signed=True)}).")
    running = ", ".join(f"{fmt(c['lambda1'], 3, signed=True)}" for c in L["running"])
    at = ", ".join(str(c["cycles"]) for c in L["running"])
    return {
        "lambda": f"{fmt(lam, 3, signed=True)} \u00b1 {se:.3f}",
        "lambda_unit": f"per forcing cycle{per_month}",
        "convergence": (f"Mean over cycles {a} to {b}, after the transient and a first half "
                        f"discarded. Running estimate {running} at cycles {at}"
                        f"{'' if L['converged'] else ' (not settled)'}. "
                        f"Check: \u03bb\u2081 + \u03bb\u2082 equals B times the period to "
                        f"{abs(L['sum_check']):.0e}.{check}"),
        "dimension": dim,
        "dimension_note": dim_note,
        "lambda_check": fmt(c["lambda1"], 3, signed=True) if c else "",
    }


def facts(cfg: Config, preset: str, factor: float, run: model.ModelRun) -> dict:
    p = _m(cfg)["presets"][preset]
    q = run.params
    deg = "\u00b0"
    L = model.load_lyapunov(cfg, preset, factor)
    return {
        "label": p["label"],
        "note": p["note"],
        "equation": f"X\u2033 = K1\u00b7X + K3\u00b7X\u00b3 + FA\u00b7cos(W\u00b7t\u00a0{MINUS}\u00a0FF) + B\u00b7X\u2032",
        "K1": fmt(q["K1"], 4), "K3": fmt(q["K3"], 4),
        "FA": fmt(q["FA"], 4) + (f" (\u00d7{factor:g})" if factor != 1 else ""),
        "FF": fmt(q["FF"], 0) + deg, "B": fmt(q["B"], 4), "W": fmt(q["W"], 4),
        "regime": _regime(run, L),
        **_lyapunov_facts(cfg, preset, L),
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
    # Axes: the union of all the phase sections (not the loop), the same for
    # every phase so they do not jump while playing.
    allx, ally = run.section[..., 0].ravel(), run.section[..., 1].ravel()
    fig = go.Figure()
    fig.add_scatter(x=rnd(pts[:, 0], DEC), y=rnd(pts[:, 1], DEC), mode="markers",
                    marker={"size": 3.5}, meta={"role": "points"},
                    hovertemplate=f"{lab['cycle'].capitalize()} %{{pointNumber}}<br>"
                                  f"{lab['x_short']} %{{x:.3f}}, rate %{{y:+.3f}}<extra></extra>")
    fig.update_layout(
        margin={"l": 64, "r": 16, "t": 28, "b": 52}, showlegend=False,
        hovermode="closest", hoverdistance=8, dragmode="zoom", uirevision=f"{preset}-{fa}",
        xaxis={"title": {"text": lab["x"]}, "range": padded(allx, 0.04), "nticks": 7},
        yaxis={"title": {"text": lab["y"]}, "range": padded(ally, 0.04), "nticks": 7},
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
        "regime": _regime(run, model.load_lyapunov(cfg, preset, factor)),
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
                         "A periodic run gives a few points; a chaotic one, a folded set of points."))
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
