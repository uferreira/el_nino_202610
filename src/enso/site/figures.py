"""Small helpers shared by the page modules: rounding, ranges, labels, and
the per-period history paths of a loop."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

MINUS = "−"  # true minus sign: never read as a dash


def export(fig: go.Figure) -> dict:
    """Figure as plain JSON, without plotly.py's default template: site.js
    applies the theme's template, so the default would only add weight."""
    out = fig.to_plotly_json()
    out["layout"].pop("template", None)
    return out


def rnd(a, decimals: int) -> list[float]:
    return np.round(np.asarray(a, dtype=float), decimals).tolist()


def fmt(x: float, decimals: int, signed: bool = False) -> str:
    s = f"{x:+.{decimals}f}" if signed else f"{x:.{decimals}f}"
    return s.replace("-", MINUS)


def padded(a, frac: float = 0.08, extra_high: float = 0.0) -> list[float]:
    """Data range plus a margin; ``extra_high`` adds room at the top end
    (where the latest point and its label often sit)."""
    lo, hi = float(np.nanmin(a)), float(np.nanmax(a))
    span = (hi - lo) or 1.0
    return [lo - span * frac, hi + span * (frac + extra_high)]


def month_after(period: str, n: int) -> str:
    y, m = map(int, period.split("-"))
    y, m = divmod(y * 12 + m - 1 + n, 12)
    return f"{y:04d}-{m + 1:02d}"


def history_paths(x, y, step: int, stop: int, decimals: tuple[int, int], meta: dict | None = None,
                  width: float = 1.0) -> list[dict]:
    """The loop from index 0 to ``stop`` (inclusive) as one path per ``step``
    points. Separate paths let a translucent colour build up where the
    trajectory passes again, so density shows; a single path would not."""
    dx, dy = decimals
    out = []
    for a in range(0, stop, step):
        b = min(a + step, stop)
        out.append(go.Scatter(
            x=rnd(x[a:b + 1], dx), y=rnd(y[a:b + 1], dy), mode="lines",
            line={"width": width}, hoverinfo="skip",
            meta={"role": "history", **(meta or {})},
        ))
    return out


def nice_step(span: float, target: int = 4) -> float:
    """A round tick step (1, 2 or 5 times a power of ten) giving about ``target`` ticks."""
    raw = span / max(target, 1)
    mag = 10 ** np.floor(np.log10(raw))
    for m in (1, 2, 5, 10):
        if m * mag >= raw:
            return float(m * mag)
    return float(10 * mag)
