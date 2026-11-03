"""Largest Lyapunov exponent against forcing amplitude, for one Duffing preset.

    python scripts/lyapunov_sweep.py                    # El Niño fit, FA x0.5 to x1.5, 100 steps
    python scripts/lyapunov_sweep.py --steps 20 --jobs 4
    python scripts/lyapunov_sweep.py --plot-only        # redraw the figure from the CSV

Each point is a full run of enso.model.lyapunov (same transient, cycles,
integrator and classification as the published runs), so the five published
factors reappear in the sweep with the same values. Writes, in data/model/:

    lyapunov-sweep-<preset>.csv   factor, FA, lambda1, lambda2, se, converged, regime, D
    lyapunov-sweep-<preset>.png   lambda1 (per forcing cycle) against FA

Not on the site yet. Needs matplotlib (pip install -e ".[scripts]").
"""

from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from enso import model
from enso.config import load_config
from enso.site.theme import TOKENS

FIELDS = ("factor", "FA", "lambda1", "lambda2", "se", "converged", "regime", "D", "D_se")


def out_paths(preset: str) -> tuple[Path, Path]:
    stem = model.MODEL_DIR / f"lyapunov-sweep-{preset}"
    return stem.with_suffix(".csv"), stem.with_suffix(".png")


def one(args: tuple[str, float]) -> dict:
    preset, factor = args
    cfg = load_config()
    L = model.lyapunov(cfg, preset, factor)
    D, dse = model.kaplan_yorke(L["lambda1"], L["lambda2"], L["se"])
    return {"factor": factor, "FA": model.run_params(cfg, preset, factor)["FA"],
            "lambda1": L["lambda1"], "lambda2": L["lambda2"], "se": L["se"],
            "converged": int(L["converged"]), "regime": L["regime"], "D": D, "D_se": dse}


def sweep(preset: str, lo: float, hi: float, steps: int, jobs: int) -> list[dict]:
    factors = [round(f, 6) for f in np.linspace(lo, hi, steps + 1)]
    rows = []
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for i, r in enumerate(pool.map(one, [(preset, f) for f in factors]), start=1):
            rows.append(r)
            print(f"{i:4d}/{len(factors)}  x{r['factor']:.3f}  lambda1 {r['lambda1']:+.4f} "
                  f"+/- {r['se']:.4f}  {r['regime']}{'' if r['converged'] else ' (not settled)'}",
                  flush=True)
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="\n", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([f"{r['factor']:.6g}", f"{r['FA']:.6g}", f"{r['lambda1']:.6f}",
                        f"{r['lambda2']:.6f}", f"{r['se']:.6f}", r["converged"], r["regime"],
                        f"{r['D']:.4f}", f"{r['D_se']:.4f}"])


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [{k: (v if k == "regime" else float(v)) for k, v in row.items()}
                for row in csv.DictReader(f)]


def plot(rows: list[dict], cfg, preset: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = TOKENS["light"]
    colour = {"chaotic": t["slot-b"], "periodic": t["slot-a"], "quasi-periodic": t["slot-c"]}
    fa0 = float(cfg.models["duffing"]["presets"][preset]["FA"])
    label = cfg.models["duffing"]["presets"][preset]["label"]
    published = [float(f) for f in cfg.models["duffing"]["fa_factors"]]

    plt.rcParams.update({"font.size": 10, "axes.edgecolor": t["muted"],
                         "axes.labelcolor": t["text"], "xtick.color": t["text-2"],
                         "ytick.color": t["text-2"], "axes.spines.top": False,
                         "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.axhline(0, color=t["zero"], lw=1, zorder=0)
    for f in published:
        ax.axvline(f * fa0, color=t["zero"], lw=0.8, ls=":", zorder=0)
    x = np.array([r["FA"] for r in rows])
    y = np.array([r["lambda1"] for r in rows])
    ax.plot(x, y, color=t["muted"], lw=0.8, zorder=1)
    for regime, c in colour.items():
        sel = [i for i, r in enumerate(rows) if r["regime"] == regime]
        if not sel:
            continue
        ax.errorbar(x[sel], y[sel], yerr=[3 * rows[i]["se"] for i in sel], fmt="o", ms=4,
                    color=c, ecolor=c, elinewidth=0.8, capsize=0, label=regime, zorder=2)
    ax.set_xlabel(f"Forcing amplitude FA (preset {fa0:g}; dotted: the published runs)")
    ax.set_ylabel("Largest Lyapunov exponent λ₁ (per forcing cycle)")
    ax.set_title(f"{label}: λ₁ against forcing amplitude (bars: 3 SE)",
                 loc="left", color=t["text"], fontsize=11)
    ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    fig.savefig(path, facecolor=t["bg"])
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preset", default="alado")
    ap.add_argument("--lo", type=float, default=0.5, help="lowest FA factor")
    ap.add_argument("--hi", type=float, default=1.5, help="highest FA factor")
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--jobs", type=int, default=None, help="worker processes (default: all cores)")
    ap.add_argument("--plot-only", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config()
    csv_path, png_path = out_paths(args.preset)
    if args.plot_only:
        rows = read_csv(csv_path)
    else:
        rows = sweep(args.preset, args.lo, args.hi, args.steps, args.jobs)
        write_csv(rows, csv_path)
        # The published runs must reappear unchanged.
        for f in cfg.models["duffing"]["fa_factors"]:
            hit = [r for r in rows if abs(r["factor"] - float(f)) < 1e-9]
            if hit:
                pub = model.load_lyapunov(cfg, args.preset, float(f), compute_missing=False)
                print(f"published x{float(f):g}: {pub['lambda1']:+.4f}, sweep {hit[0]['lambda1']:+.4f}")
    plot(rows, cfg, args.preset, png_path)
    print(f"wrote {csv_path.relative_to(model.ROOT)} and {png_path.relative_to(model.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
