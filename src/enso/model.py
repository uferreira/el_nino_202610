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

For every run it also computes the Lyapunov exponents (Benettin's method on
the variational equations, see ``lyapunov``) and classifies the motion:
largest exponent > 0 chaotic, about 0 quasi-periodic, < 0 periodic.

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
LYAP_METHOD = 3             # bump when the Lyapunov code changes, to recompute the cache


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


# ---------------------------------------------------------------------------
# Lyapunov exponents
# ---------------------------------------------------------------------------

def _augmented_rhs(t: float, z, params: dict) -> list[float]:
    """State (X, Y) plus two tangent vectors, flattened as [X, Y, a, b, c, d]
    with columns (a, b) and (c, d). Variational equation of the system:
    d(dX)/dt = dY, d(dY)/dt = (K1 + 3 K3 X^2) dX + B dY."""
    X, Y = z[0], z[1]
    dX, dY = duffing_rhs(t, (X, Y), params)
    j21 = params["K1"] + 3.0 * params["K3"] * X * X
    B = params["B"]
    a, b, c, d = z[2], z[3], z[4], z[5]
    return [dX, dY, b, j21 * a + B * b, d, j21 * c + B * d]


def _lyap_settings(cfg: Config) -> dict:
    return dict(cfg.models["duffing"]["lyapunov"])


def _integrator(ls: dict) -> dict:
    return {"method": ls.get("method", "RK45"), "rtol": float(ls["rtol"]), "atol": float(ls["atol"])}


def lyap_path(preset: str, factor: float, directory: Path = MODEL_DIR) -> Path:
    return Path(directory) / f"duffing-{preset}-x{factor:g}-lyapunov.json"


def _lyap_key(cfg: Config, preset: str, factor: float) -> dict:
    p = cfg.models["duffing"]["presets"][preset]
    return {"params": run_params(cfg, preset, factor), "x0": p["x0"], "y0": p["y0"],
            "transient_cycles": settings(cfg, preset)["transient_cycles"],
            "lyapunov": _lyap_settings(cfg), "method": LYAP_METHOD}


CHECK_FIELDS = ("integrator", "lambda1", "lambda2", "se", "converged", "regime", "sum_check")


def lyapunov(cfg: Config, preset: str, factor: float, cycles: int | None = None,
             integrator: dict | None = None) -> dict:
    """Both Lyapunov exponents of one run, per forcing cycle.

    Benettin et al. (1980): integrate the trajectory with two tangent
    vectors, re-orthonormalise them (QR) after every forcing cycle and
    average the logarithms of the stretching factors. The trajectory starts
    from the preset's initial state after the transient. Since the
    divergence of the flow is B everywhere, lambda1 + lambda2 = B x period
    exactly; ``sum_check`` is the numerical error of that identity.

    ``factor`` may be any multiple of the preset's FA (the sweep script uses
    100 of them). ``integrator`` ({method, rtol, atol}) defaults to the
    config's; the robustness check passes ``lyapunov.check``.
    """
    ls = _lyap_settings(cfg)
    n = int(cycles or ls["cycles"])
    p = cfg.models["duffing"]["presets"][preset]
    params = run_params(cfg, preset, factor)
    T = 2 * math.pi / params["W"]
    t0 = settings(cfg, preset)["transient_cycles"] * T
    tol = integrator or _integrator(ls)

    sol = solve_ivp(duffing_rhs, (0.0, t0), [float(p["x0"]), float(p["y0"])], args=(params,), **tol)
    state = sol.y[:, -1]
    Q = np.eye(2)
    logs = np.zeros((n, 2))
    for i in range(n):
        ta, tb = t0 + i * T, t0 + (i + 1) * T
        z0 = [state[0], state[1], Q[0, 0], Q[1, 0], Q[0, 1], Q[1, 1]]
        sol = solve_ivp(_augmented_rhs, (ta, tb), z0, args=(params,), **tol)
        z = sol.y[:, -1]
        state = z[:2]
        M = np.array([[z[2], z[4]], [z[3], z[5]]])
        Q, R = np.linalg.qr(M)
        sign = np.sign(np.diag(R))
        Q, R = Q * sign, (R.T * sign).T
        logs[i] = np.log(np.diag(R))

    # Average over the second half only: transient chaos (seen in some runs
    # for hundreds of cycles) must not leak into the estimate.
    h = n // 2
    win = logs[h:]
    lam = win.mean(axis=0)                        # per forcing cycle
    nb = int(ls["blocks"])
    blocks = win[: len(win) - len(win) % nb, 0].reshape(nb, -1).mean(axis=1)
    se = float(blocks.std(ddof=1) / math.sqrt(nb))
    m = len(win)
    checkpoints = sorted({c for c in (m // 4, m // 2, 3 * m // 4, m) if c > 0})
    running = [{"cycles": h + c, "lambda1": float(win[:c, 0].mean())} for c in checkpoints]
    # Converged when the two halves of the window agree: each half-mean has a
    # standard error of about sqrt(2) se, their difference 2 se; allow 3 of those.
    a, b = win[: m // 2, 0].mean(), win[m // 2:, 0].mean()
    zero_band = float(ls["zero_band"])
    converged = bool(abs(a - b) <= max(3 * 2 * se, zero_band))
    return {
        "lambda1": float(lam[0]), "lambda2": float(lam[1]), "se": se,
        "per": "forcing cycle", "period": T, "integrator": dict(tol), "cycles": n, "window": [h + 1, n],
        "running": running, "converged": converged,
        "first_half_lambda1": float(logs[:h, 0].mean()),
        "sum_check": float(lam.sum() - params["B"] * T),
        "regime": classify(float(lam[0]), se, zero_band),
    }


def kaplan_yorke(lambda1: float, lambda2: float, se: float = 0.0) -> tuple[float, float]:
    """Kaplan-Yorke (Lyapunov) dimension of the Poincaré section, with its
    standard error from ``se`` of lambda1.

    The section is a 2-D map with exponents lambda1 >= lambda2 (per forcing
    cycle): D = 1 + lambda1 / |lambda2| when lambda1 >= 0 > lambda1 + lambda2,
    and 0 when lambda1 < 0 (the section is a finite set of points). Here
    lambda1 + lambda2 = B x period is fixed, so dD/dlambda1 = |s| / (lambda1 - s)^2
    with s = lambda1 + lambda2.
    """
    if lambda1 < 0:
        return 0.0, 0.0
    s = lambda1 + lambda2
    if s >= 0:
        return 2.0, 0.0
    d = 1.0 + lambda1 / abs(lambda2)
    return d, abs(s) / (lambda1 - s) ** 2 * se


def classify(lam: float, se: float, zero_band: float) -> str:
    """chaotic / quasi-periodic / periodic from the largest exponent."""
    margin = max(3 * se, zero_band)
    if lam > margin:
        return "chaotic"
    if lam < -margin:
        return "periodic"
    return "quasi-periodic"


def load_lyapunov(cfg: Config, preset: str, factor: float, directory: Path = MODEL_DIR,
                  compute_missing: bool = True) -> dict:
    path, key = lyap_path(preset, factor, directory), _lyap_key(cfg, preset, factor)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("key") == key:
            return data
    if not compute_missing:
        raise FileNotFoundError(f"{path} is missing or stale: run python -m enso.model")
    data = {"key": key, **lyapunov(cfg, preset, factor)}
    check = _lyap_settings(cfg).get("check")
    if check:
        c = lyapunov(cfg, preset, factor, integrator=_integrator(check))
        data["check"] = {k: c[k] for k in CHECK_FIELDS}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8", newline="\n")
    return data


def lyapunov_is_current(cfg: Config, preset: str, factor: float, directory: Path = MODEL_DIR) -> bool:
    path = lyap_path(preset, factor, directory)
    return path.exists() and json.loads(path.read_text(encoding="utf-8")).get("key") == _lyap_key(cfg, preset, factor)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="recompute every run")
    args = ap.parse_args(argv)
    cfg = load_config()
    for preset, factor in all_runs(cfg):
        if not args.force and is_current(cfg, preset, factor):
            continue
        r = integrate(cfg, preset, factor)
        save(r, _key(cfg, preset, factor))
        rep = f"repeats every {r.repeat}" if r.repeat else "no repeat found"
        print(f"ran     {preset} x{factor:g}: FA = {r.params['FA']:.4g}, {rep}", flush=True)
    for preset, factor in all_runs(cfg):
        if not args.force and lyapunov_is_current(cfg, preset, factor):
            continue
        if args.force and lyap_path(preset, factor).exists():
            lyap_path(preset, factor).unlink()
        L = load_lyapunov(cfg, preset, factor)
        conv = ", ".join(f"{c['lambda1']:+.4f}" for c in L["running"])
        print(f"lyap    {preset} x{factor:g}: lambda1 = {L['lambda1']:+.4f} +/- {L['se']:.4f} per cycle "
              f"({L['regime']}{'' if L['converged'] else ', NOT CONVERGED'}); running {conv}; "
              f"first half {L['first_half_lambda1']:+.4f}; lambda1+lambda2-B*T = {L['sum_check']:+.1e}"
              + (f"; {L['check']['integrator']['method']} {L['check']['lambda1']:+.4f}"
                 f" +/- {L['check']['se']:.4f}" if "check" in L else ""),
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
