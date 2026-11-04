"""SSA (window 120 months) against the Fourier low-pass on NINO1+2: agreement, event peaks,
and an edge-revision hindcast (120 end dates, 1995-2024). Writes output/ssa_results.npz."""
from ssa_core import *
M = 120; NSEL = 20; PMIN = 20.0
s0 = load("nino12")

def methods(s):
    a, clim = anomaly(s); x = a.values; mu, sd = x.mean(), x.std(); xs = (x-mu)/sd; N = len(x)
    F = passa_baixa(10.0, 9.0, x)
    lam, E, X = ssa_eig(xs, M)
    ks = [k for k in range(NSEL) if eof_period(E[:, k]) >= PMIN]
    S = rc(X, E, ks, N)
    fc = lrf_extend(S, E, ks, M)[N:]
    ext = np.concatenate([xs, fc])
    Xe = np.lib.stride_tricks.sliding_window_view(ext, M)
    Se = rc(Xe, E, ks, len(ext))[:N]
    return dict(a=a, F=F, S=S*sd+mu, Se=Se*sd+mu, lam=lam, E=E, X=X, ks=ks, xs=xs, sd=sd, mu=mu)

full = methods(site_window(s0)); idx_full = full["a"].index
print("selected comps (full):", [k+1 for k in full["ks"]], [round(eof_period(full["E"][:,k]),1) for k in full["ks"]])
F, S = full["F"], full["S"]
print("corr(Fourier LP, SSA>=20mo) =", np.corrcoef(F, S)[0,1].round(3), " RMS diff =", np.sqrt(np.mean((F-S)**2)).round(3))
obs3 = full["a"].rolling(3, center=True).mean()
for lab, lo, hi in [("1982-83","1982-06","1983-09"),("1997-98","1997-06","1998-06"),("2015-16","2015-06","2016-06"),("2023-24","2023-03","2024-03"),("2025-26","2026-01","2026-10")]:
    sl = slice(pd.Period(lo,"M"), pd.Period(hi,"M"))
    m = (idx_full >= pd.Period(lo,"M")) & (idx_full <= pd.Period(hi,"M"))
    print(f"{lab}: obs(3mo) max {obs3.loc[sl].max():.2f}  Fourier {F[m].max():.2f}  SSA {S[m].max():.2f}  SSA+ext {full['Se'][m].max():.2f}")

# hindcast of edge revisions
ends = pd.period_range("1995-01", "2024-10", freq="M")[::3]
LAGS = 25
rev = {k: [] for k in ("F","S","Se")}
fin = {"F": pd.Series(F, idx_full), "S": pd.Series(S, idx_full), "Se": pd.Series(full["Se"], idx_full)}
for e in ends:
    r = methods(site_window(s0, e)); ix = r["a"].index
    for k in rev:
        est = pd.Series(r[k], ix)
        rev[k].append([est.iloc[-1-L] - fin[k].loc[ix[-1-L]] for L in range(LAGS)])
rms = {k: np.sqrt(np.mean(np.array(v)**2, axis=0)) for k, v in rev.items()}
for L in (0,3,6,10,12,18,24):
    if L < LAGS: print(f"lag {L:2d}: RMS revision  Fourier {rms['F'][L]:.3f}  SSA {rms['S'][L]:.3f}  SSA+forecast {rms['Se'][L]:.3f} °C")
np.savez(OUT / "ssa_results.npz", F=F, S=S, Se=full["Se"], a=full["a"].values, idx=idx_full.astype(str).values,
         rmsF=rms["F"], rmsS=rms["S"], rmsSe=rms["Se"], lam=full["lam"], E=full["E"], xs=full["xs"], sd=full["sd"], ks=np.array(full["ks"]))
