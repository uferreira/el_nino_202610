"""Nonlinearity (Theiler surrogates) and phase-locking tests on NINO1+2 and, identically, on
51-year segments of the Duffing fit (chaotic, periodic), linear stochastic nulls and the
recharge oscillator with Palau sea level. Writes output/nl_results.json and output/nl_arrays.npz;
nl_tables.py prints the tables, nl_figures.py draws the figures.

    python nl_tests.py            # about 6 min on 2 cores
"""
import json, time
from concurrent.futures import ProcessPoolExecutor
from nl_core import *

NSUR_DATA, NSUR_SEG, NSEG = 500, 100, 10
TAU0 = 6          # LIM lag (months): the shortest at which the fitted L oscillates
KEYS = NL_KEYS + PL_KEYS
KEEP = ["mon_nino", "mon_nina", "sdm", "rho_series_f", "rho_series_ssa"]


def model_segments():
    """{name: (list of 612-month anomaly segments, cal0, info)} for every model."""
    x, cal0, s = data_anomaly(); dclim = seg_anomaly(s.values)[1]; n = NSEG * NM; M = {}
    for lab, fa, sg in [("Duffing chaotic (FA x1)", 1.0, 0.0), ("Duffing chaotic + noise 0.03", 1.0, 0.03),
                        ("Duffing periodic (FA x1.5)", 1.5, 0.0), ("Duffing periodic + noise 0.15", 1.5, 0.15)]:
        y = duffing_series(fa, sg, NSEG)
        segs = [seg_anomaly(y[k * NM:(k + 1) * NM])[0] for k in range(NSEG)]
        M[lab] = (segs, model_cal0(y[:NM], dclim, cal0), dict(FA_factor=fa, sigma=sg))
    xm = x - x.mean(); rng = np.random.default_rng(11)
    phi, s2 = fit_ar(xm, 2)
    M["AR(2) fitted"] = ([seg_anomaly(v)[0] for v in sim_ar(phi, s2, n, rng).reshape(NSEG, NM)], cal0,
                         dict(phi=phi.tolist(), sigma=float(np.sqrt(s2))))
    P = fit_par2(xm, cal0)
    M["Seasonal linear PAR(2)"] = ([seg_anomaly(v)[0] for v in sim_par2(P, n, cal0, rng).reshape(NSEG, NM)], cal0,
                                   dict(a1=P[:, 0].round(3).tolist(), a2=P[:, 1].round(3).tolist(),
                                        s=P[:, 2].round(3).tolist(), floquet=floquet_par2(P)))
    # recharge oscillator: T = NINO1+2 anomaly, h = Palau sea level anomaly (linear trend removed)
    hp = site_window(load("palau")); ha = anomaly(hp)[0].values; tt = np.arange(len(ha))
    ha = ha - np.polyval(np.polyfit(tt, ha, 1), tt)
    sc = np.array([xm.std(), ha.std()]); Z = np.column_stack([xm, ha]) / sc
    L, Ps = fit_lim(Z, TAU0)
    T = sim_var1(Ps, n, cal0, rng)[:, 0] * sc[0]
    M[f"Recharge oscillator (LIM, T + Palau h, tau0 {TAU0})"] = (
        [seg_anomaly(v)[0] for v in T.reshape(NSEG, NM)], cal0, ro_info(Z))
    return M


def floquet_par2(P):
    """Annual monodromy matrix of the PAR(2) companion form: |multipliers| and period (months)."""
    Mo = np.eye(2)
    for a1, a2, _ in P: Mo = np.array([[a1, a2], [1, 0]]) @ Mo
    ev = np.linalg.eigvals(Mo)
    return dict(abs=np.abs(ev).round(3).tolist(), arg_deg=np.degrees(np.angle(ev)).round(1).tolist())

def ro_info(Z):
    """Lead-lag correlation of Palau h and T, and the LIM eigenvalues for several tau0 (the
    Penland tau test: a linear Markov model gives the same L for every tau0)."""
    lag = {k: round(float(np.corrcoef(Z[:len(Z) - k, 1], Z[k:, 0])[0, 1]) if k >= 0 else
                    float(np.corrcoef(Z[-k:, 1], Z[:len(Z) + k, 0])[0, 1]), 2) for k in (-24, -12, -6, 0, 6, 12, 24)}
    tt = {}
    for t0 in (1, 3, 6, 9):
        ev = np.linalg.eigvals(fit_lim(Z, t0)[0]); w = abs(ev[0].imag)
        tt[t0] = dict(decay_per_month=[round(float(-e.real), 3) for e in ev],
                      period_months=round(2 * np.pi / w, 1) if w > 1e-6 else None)
    return dict(corr_h_t_with_T_t_plus_k=lag, tau_test=tt, tau0_used=TAU0)


def seg_job(args):
    name, k, x, cal0 = args
    if x.std() < 1e-2:          # no interannual variability (period-1 orbit): tests undefined
        return name, k, None, None, None
    d = stats(x, cal0, keep=True)
    S = surrogate_test(x, cal0, NSUR_SEG, "iaaft", seed=100 + k)
    p = {key: pvalue(d[key], S[key], SIDE[key]) for key in S}
    keep = {kk: np.asarray(d[kk]) for kk in KEEP if kk in d}
    return name, k, {kk: d[kk] for kk in KEYS + ["bimodal_f", "p_nino", "p_nina", "month_nino",
                                                  "month_nina", "n_nino", "n_nina", "ssa_period"]}, p, keep


def data_job(args):
    kind, seed = args; x, cal0, _ = data_anomaly()
    return kind, surrogate_test(x, cal0, NSUR_DATA, kind, seed)


if __name__ == "__main__":
    t0 = time.time()
    x, cal0, s = data_anomaly()
    d0 = stats(x, cal0, keep=True)
    M = model_segments()
    jobs = [(name, k, seg, c0) for name, (segs, c0, _) in M.items() for k, seg in enumerate(segs)]
    with ProcessPoolExecutor() as ex:
        dat = dict(ex.map(data_job, [("iaaft", 1), ("ft", 2)]))
        res = list(ex.map(seg_job, jobs, chunksize=2))
    print(f"done in {time.time() - t0:.0f} s")

    R = dict(window=f"{s.index[0]} to {s.index[-1]}", n_months=len(x), nsur_data=NSUR_DATA,
             nsur_segment=NSUR_SEG, nseg=NSEG,
             data={k: (v if isinstance(v, (str, bool)) else float(v)) for k, v in d0.items()
                   if np.ndim(v) == 0},
             p_iaaft={k: pvalue(d0[k], dat["iaaft"][k], SIDE[k]) for k in KEYS},
             p_ft={k: pvalue(d0[k], dat["ft"][k], SIDE[k]) for k in KEYS},
             sur_range_iaaft={k: np.nanpercentile(dat["iaaft"][k], [2.5, 50, 97.5]).round(3).tolist() for k in KEYS},
             models={})
    arrays = {f"sur_iaaft_{k}": dat["iaaft"][k] for k in KEYS}
    arrays.update({f"sur_ft_{k}": dat["ft"][k] for k in KEYS})
    for kk in ["xf", "sdm", "mon_nino", "mon_nina", "phE_f", "phA_f", "rho_series_f", "phE_ssa", "rho_series_ssa"]:
        if kk in d0 and d0[kk] is not None: arrays[f"data_{kk}"] = np.asarray(d0[kk])
    arrays["data_x"] = x; arrays["data_cal0"] = cal0
    for name, (segs, c0, info) in M.items():
        rows = [r for r in res if r[0] == name]; ok = [r for r in rows if r[2] is not None]
        m = dict(info=info, cal0=c0, nseg=len(rows), nseg_tested=len(ok), stats={})
        if ok:
            for key in KEYS + ["n_nino", "month_nino", "p_nino", "ssa_period"]:
                v = np.array([r[2][key] for r in ok], float)
                m["stats"][key] = dict(median=float(np.nanmedian(v)), lo=float(np.nanmin(v)), hi=float(np.nanmax(v)))
                if key in KEYS:
                    pv = np.array([r[3][key] for r in ok], float)
                    m["stats"][key]["reject05"] = float(np.mean(pv[np.isfinite(pv)] < 0.05)) if np.isfinite(pv).any() else np.nan
                    arrays[f"{name}|{key}"] = v
            m["bimodal_segments"] = int(sum(r[2]["bimodal_f"] for r in ok))
            m["rayleigh_p05_segments"] = int(sum((r[2]["p_nino"] < 0.05) for r in ok))
            arrays[f"{name}|sdm"] = np.array([r[4]["sdm"] for r in ok])
            arrays[f"{name}|mon_nino"] = np.concatenate([r[4]["mon_nino"] for r in ok])
            arrays[f"{name}|mon_nina"] = np.concatenate([r[4]["mon_nina"] for r in ok])
            for kk in ("rho_series_f", "rho_series_ssa"):
                arrays[f"{name}|{kk}"] = np.array([r[4][kk] if kk in r[4] and r[4][kk].ndim else
                                                   np.full(len(d0[kk]), np.nan) for r in ok])
        R["models"][name] = m
    (OUT / "nl_results.json").write_text(json.dumps(R, indent=1, default=float))
    np.savez_compressed(OUT / "nl_arrays.npz", **arrays)
    print("wrote", OUT / "nl_results.json")
