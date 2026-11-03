"""Duffing model runs (enso.model)."""

import math

import numpy as np
import pytest

from enso import model
from enso.config import load_config

CFG = load_config()


def test_rhs_is_the_forced_double_well():
    p = {"K1": 0.12, "K3": -0.03, "FA": 0.5, "FF": -60.0, "B": -0.35, "W": 0.5236}
    t, X, Y = 7.3, 1.1, -0.4
    expect = (p["K1"] * X + p["K3"] * X ** 3 + p["FA"] * math.cos(p["W"] * t - math.radians(p["FF"]))
              + p["B"] * Y)
    dX, dY = model.duffing_rhs(t, [X, Y], p)
    assert dX == Y and dY == pytest.approx(expect, rel=1e-12)


def test_find_repeat():
    two = np.tile([[0.0, 1.0], [1.0, 0.0]], (200, 1))
    assert model.find_repeat(two, scale=2.0) == 2
    rng = np.random.default_rng(0)
    assert model.find_repeat(rng.normal(size=(400, 2)), scale=2.0) is None


@pytest.mark.parametrize("preset,factor", model.all_runs(CFG))
def test_cache_is_current_for_every_run(preset, factor):
    """The committed runs match config.yaml; otherwise run python -m enso.model."""
    assert model.is_current(CFG, preset, factor)


@pytest.mark.parametrize("preset", ["alado", "chaos"])
def test_section_and_trajectory_come_from_one_trajectory(preset):
    """The kept trajectory is the end of the same run the section samples:
    at each whole forcing cycle they hold the same state."""
    s = model.settings(CFG, preset)
    run = model.load(CFG, preset, 1.0, compute_missing=False)
    per_cycle = s["samples_per_cycle"] * s["ndots"]
    at_cycle_start = np.stack([run.traj_x[::per_cycle], run.traj_y[::per_cycle]], axis=-1)
    # Section phase 0, last trajectory_cycles cycles (the trajectory has one more point: the end).
    np.testing.assert_allclose(run.section[0][-s["trajectory_cycles"]:], at_cycle_start[:-1], atol=1e-9)
    assert run.section.shape == (s["phases"], s["section_cycles"], 2)


def test_a_small_run_reproduces_its_own_cache(tmp_path, monkeypatch):
    """Integration end to end on a short run: saved, then loaded unchanged."""
    import copy
    from dataclasses import replace
    models = copy.deepcopy(CFG.models)
    models["duffing"].update(transient_cycles=5, section_cycles=20, trajectory_cycles=4)
    for p in models["duffing"]["presets"].values():
        p.pop("trajectory_cycles", None)
    cfg = replace(CFG, models=models)
    a = model.load(cfg, "alado", 1.0, directory=tmp_path)
    b = model.load(cfg, "alado", 1.0, directory=tmp_path, compute_missing=False)
    np.testing.assert_array_equal(a.section, b.section)
    assert model.cache_path("alado", 1.0, tmp_path).exists()


# ---- Lyapunov exponents -------------------------------------------------------

def test_periodic_case_has_a_negative_exponent():
    """FA x1.5 of the El Niño fit locks onto the forcing (one point per section)."""
    L = model.lyapunov(CFG, "alado", 1.5, cycles=80)
    assert L["regime"] == "periodic" and L["lambda1"] < 0


def test_chaotic_benchmark_has_a_positive_exponent():
    """x'' + 0.02x' - x + x^3 = 3 sin t is the textbook strange attractor."""
    L = model.lyapunov(CFG, "chaos", 1.0, cycles=300)
    assert L["regime"] == "chaotic" and L["lambda1"] > 0.2


@pytest.mark.parametrize("preset,factor", model.all_runs(CFG))
def test_exponents_are_cached_converged_and_sum_to_the_divergence(preset, factor):
    assert model.lyapunov_is_current(CFG, preset, factor)
    L = model.load_lyapunov(CFG, preset, factor, compute_missing=False)
    assert L["converged"]
    # The flow's divergence is B everywhere: lambda1 + lambda2 = B x period.
    assert abs(L["sum_check"]) < 1e-6
    # lambda1 is the larger, except within noise when the two are equal (a
    # periodic orbit with complex Floquet multipliers: both are B x period / 2).
    assert L["lambda1"] >= L["lambda2"] - 3 * L["se"]


@pytest.mark.parametrize("preset,factor", model.all_runs(CFG))
def test_classification_agrees_with_the_section_repeat_check(preset, factor):
    """Periodic by the exponent <=> the long section run repeats (within 24 cycles)."""
    L = model.load_lyapunov(CFG, preset, factor, compute_missing=False)
    run = model.load(CFG, preset, factor, compute_missing=False)
    assert (L["regime"] == "periodic") == (run.repeat is not None)


def test_classify_bands():
    assert model.classify(0.5, 0.01, 0.01) == "chaotic"
    assert model.classify(-0.5, 0.01, 0.01) == "periodic"
    assert model.classify(0.005, 0.001, 0.01) == "quasi-periodic"
    assert model.classify(0.05, 0.03, 0.01) == "quasi-periodic"   # within 3 SE of zero


def test_spiralling_periodic_orbits_have_equal_exponents():
    """A stable periodic orbit with complex Floquet multipliers contracts
    equally in every direction: lambda1 = lambda2 = B x period / 2."""
    for preset, factor in [("alado", 1.5), ("chaos", 1.25), ("chaos", 1.5)]:
        L = model.load_lyapunov(CFG, preset, factor, compute_missing=False)
        half = model.run_params(CFG, preset, factor)["B"] * L["period"] / 2
        assert L["lambda1"] == pytest.approx(half, abs=3 * L["se"] + 2e-3)
