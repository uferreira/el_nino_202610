"""Duffing / double-well model runs, precomputed in Python.

    python -m enso.model            # compute any run whose cache is missing or stale
    python -m enso.model --force    # recompute every run

The equation and right-hand side are ported unchanged from
el_nino/src/el_nino/duffing.py (Python translation of the Java applet
DoubleWell.21.5):

    X'' = K1 X + K3 X^3 + FA cos(W t - FF) + B X'

Each run integrates ONE long trajectory (scipy RK45, as before). After
``transient_cycles`` forcing cycles are discarded, it keeps:

* the Poincaré section: the state once per forcing cycle, at each of
  ``phases`` phases of the forcing, for ``section_cycles`` cycles;
* the last ``trajectory_cycles`` cycles on a fine time grid, for the loop.

Runs are cached in data/model/ (committed). A chaotic trajectory depends on
the last bit of every floating-point operation, so recomputing on another
machine or library version gives a different (equally valid) trajectory;
the cache keeps the published site reproducible.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from enso.config import ROOT, Config, load_config

MODEL_DIR = ROOT / "data" / "model"
RTOL, ATOL = 1e-6, 1e-8     # as el_nino.duffing.solve_duffing
REPEAT_MAX = 24             # longest cycle (in forcing periods) we look for


def duffing_rhs(t: float, state, params: dict) -> list[float]:
    """Right-hand side, ported from el_nino.duffing.duffing_rhs."""
    X, Y = state[0], state[1]
    K0 = params.get("K0", 0.0)
    K1 = params.get("K1", 0.0)
    K2 = params.get("K2", 0.0)
    K3 = params.get("K3", 0.0)
    K4 = params.get("K4", 0.0)
    K5 = params.get("K5", 0.0)
    FA = params.get("FA", 0.0)
    FF = params.get("FF", 0.0)
    FA2 = params.get("FA2", 0.0)
    FF2 = params.get("FF2", 0.0)
    B = params.get("B", 0.0)
    W = params.get("W", 2.0 * math.pi / 12.0)
    FF_rad = FF * math.pi / 180.0
    FF2_rad = FF2 * math.pi / 180.0
    dYdt = (
        K0 + K1 * X + K2 * X * X + K3 * X * X * X + K4 * X * X * X * X + K5 * X * X * X * X * X
        + FA * math.cos(FF_rad) * math.cos(W * t)
        + FA * math.sin(FF_rad) * math.sin(W * t)
        + FA2 * math.cos(FF2_rad) * math.cos(2.0 * W * t)
        + FA2 * math.sin(FF2_rad) * math.sin(2.0 * W * t)
        + B * Y
    )
    return [Y, dYdt]


PARAM_KEYS = ("K1", "K3", "FA", "FF", "B", "W")


@dataclass
class ModelRun:
    preset: str
    factor: float
    params: dict              # the coefficients actually integrated (FA scaled)
    section: np.ndarray       # (phases, section_cycles, 2): X, dX/dt
    traj_t: np.ndarray        # fine grid, in forcing cycles from the start of the stretch
    traj_x: np.ndarray
    traj_y: np.ndarray
    repeat: int | None        # cycle length in forcing periods, None if none found

    @property
    def period(self) -> float:
        return 2 * math.pi / self.params["W"]


SETTING_KEYS = ("transient_cycles", "section_cycles", "trajectory_cycles",
                "samples_per_cycle", "ndots", "phases")


def settings(cfg: Config, preset: str) -> dict:
    """Run settings: the model defaults, overridden by the preset where it says so."""
    m = cfg.models["duffing"]
    p = m["presets"][preset]
    return {k: p.get(k, m[k]) for k in SETTING_KEYS}


def run_params(cfg: Config, preset: str, factor: float) -> dict:
    p = cfg.models["duffing"]["presets"][preset]
    params = {k: float(p[k]) for k in PARAM_KEYS}
    params["FA"] = round(params["FA"] * factor, 10)
    return params


def _key(cfg: Config, preset: str, factor: float) -> str:
    p = cfg.models["duffing"]["presets"][preset]
    return json.dumps({"params": run_params(cfg, preset, factor), "x0": p["x0"], "y0": p["y0"],
                       "settings": settings(cfg, preset), "rtol": RTOL, "atol": ATOL}, sort_keys=True)


def cache_path(preset: str, factor: float, directory: Path = MODEL_DIR) -> Path:
    return Path(directory) / f"duffing-{preset}-x{factor:g}.npz"


def find_repeat(section0: np.ndarray, scale: float, tail: int = 300) -> int | None:
    """Smallest n such that the section repeats every n forcing cycles, to
    within 1e-4 of ``scale`` (the size of the whole trajectory)."""
    pts = section0[-tail:]
    for n in range(1, min(REPEAT_MAX, len(pts) // 2) + 1):   # need at least two repeats
        if np.max(np.abs(pts[n:] - pts[:-n])) < 1e-4 * scale:
            return n
    return None


def integrate(cfg: Config, preset: str, factor: float) -> ModelRun:
    s = settings(cfg, preset)
    p = cfg.models["duffing"]["presets"][preset]
    params = run_params(cfg, preset, factor)
    T = 2 * math.pi / params["W"]
    c0, nsec, ntraj = s["transient_cycles"], s["section_cycles"], s["trajectory_cycles"]
    per_cycle = s["samples_per_cycle"] * s["ndots"]

    k = np.arange(nsec)[:, None]
    j = np.arange(s["phases"])[None, :] / s["phases"]
    t_sec = ((c0 + k + j) * T).T.ravel()                        # phase-major
    first = c0 + nsec - ntraj
    t_traj = (first + np.arange(ntraj * per_cycle + 1) / per_cycle) * T
    t_eval = np.unique(np.concatenate([t_sec, t_traj]))

    sol = solve_ivp(duffing_rhs, (0.0, float(t_eval[-1])), [float(p["x0"]), float(p["y0"])],
                    method="RK45", t_eval=t_eval, args=(params,), rtol=RTOL, atol=ATOL)
    if not sol.success:
        raise RuntimeError(f"{preset} x{factor}: {sol.message}")
    X, Y = sol.y
    i_sec = np.searchsorted(t_eval, t_sec)
    i_traj = np.searchsorted(t_eval, t_traj)
    section = np.stack([X[i_sec], Y[i_sec]], axis=-1).reshape(s["phases"], nsec, 2)
    tx, ty = X[i_traj], Y[i_traj]
    scale = float(np.ptp(tx) + np.ptp(ty)) or 1.0
    return ModelRun(preset, factor, params, section,
                    traj_t=t_traj / T - first, traj_x=tx, traj_y=ty,
                    repeat=find_repeat(section[0], scale))


def save(r: ModelRun, key: str, directory: Path = MODEL_DIR) -> Path:
    path = cache_path(r.preset, r.factor, directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, key=np.array(key), section=r.section, traj_t=r.traj_t,
                        traj_x=r.traj_x, traj_y=r.traj_y,
                        repeat=np.array(-1 if r.repeat is None else r.repeat))
    return path


def load(cfg: Config, preset: str, factor: float, directory: Path = MODEL_DIR,
         compute_missing: bool = True) -> ModelRun:
    """The cached run, recomputed first if missing or made with other settings."""
    path, key = cache_path(preset, factor, directory), _key(cfg, preset, factor)
    if path.exists():
        z = np.load(path)
        if str(z["key"]) == key:
            rep = int(z["repeat"])
            return ModelRun(preset, factor, run_params(cfg, preset, factor), z["section"],
                            z["traj_t"], z["traj_x"], z["traj_y"], None if rep < 0 else rep)
    if not compute_missing:
        raise FileNotFoundError(f"{path} is missing or stale: run python -m enso.model")
    r = integrate(cfg, preset, factor)
    save(r, key, directory)
    return r


def is_current(cfg: Config, preset: str, factor: float, directory: Path = MODEL_DIR) -> bool:
    path = cache_path(preset, factor, directory)
    return path.exists() and str(np.load(path)["key"]) == _key(cfg, preset, factor)


def all_runs(cfg: Config) -> list[tuple[str, float]]:
    m = cfg.models["duffing"]
    return [(p, float(f)) for p in m["presets"] for f in m["fa_factors"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="recompute every run")
    args = ap.parse_args(argv)
    cfg = load_config()
    for preset, factor in all_runs(cfg):
        if not args.force and is_current(cfg, preset, factor):
            print(f"cached  {preset} x{factor:g}")
            continue
        r = integrate(cfg, preset, factor)
        save(r, _key(cfg, preset, factor))
        rep = f"repeats every {r.repeat}" if r.repeat else "no repeat found"
        print(f"ran     {preset} x{factor:g}: FA = {r.params['FA']:.4g}, {rep}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
