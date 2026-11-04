"""Null model: a noise-driven linear oscillator fitted to the data (univariate stand-in for the
stochastic recharge oscillator / LIM), run through the same QPFT diagnostics as duffing_calibration.py."""
import numpy as np
from ssa_core import OUT, load, site_window, anomaly
from duffing_calibration import diagnose, NSEG, NM

s = site_window(load("nino12")); a, clim = anomaly(s); x = a.values - a.values.mean()

def fit_ar(x, p):
    r = np.array([np.dot(x[:len(x)-k], x[k:])/len(x) for k in range(p+1)])
    R = np.array([[r[abs(i-j)] for j in range(p)] for i in range(p)])
    phi = np.linalg.solve(R, r[1:p+1]); s2 = r[0] - phi @ r[1:p+1]
    return phi, s2

def aic(x, p):
    phi, s2 = fit_ar(x, p); return len(x)*np.log(s2) + 2*p

def ar_peak(phi):
    f = np.linspace(0.005, 0.5, 4000)  # cycles/month
    H = 1 - sum(phi[k]*np.exp(-2j*np.pi*f*(k+1)) for k in range(len(phi)))
    return 12*f[np.argmax(1/np.abs(H)**2)]

pbest = min(range(1, 25), key=lambda p: aic(x, p))
clim12 = clim.values[:12]; cm = np.array([clim[clim.index.month == m].iloc[0] for m in range(1, 13)])
for lab, p in [("AR(2) oscillator", 2), (f"AR({pbest}) by AIC", pbest)]:
    phi, s2 = fit_ar(x, p)
    rng = np.random.default_rng(3); n = NSEG*NM + 600; y = np.zeros(n); e = rng.standard_normal(n)*np.sqrt(s2)
    for t in range(p, n): y[t] = phi @ y[t-p:t][::-1] + e[t]
    y = y[600:]; res = []
    for k in range(NSEG):
        seg = y[k*NM:(k+1)*NM] + cm[(np.arange(NM) + s.index[0].month - 1) % 12]
        res.append(diagnose(seg))
    f1 = [r["f1"] for r in res]; nl = [r["nlines"] for r in res]; ds = [r["drift_sig"] for r in res]
    print(f"{lab:18s}: spectral peak {ar_peak(phi):.3f} cpy | var share {np.mean([r['var_int'] for r in res]):.2f} | lines>50% {nl} | f1 {np.round(f1,3).tolist()} | drift σ {np.round(ds,1).tolist()}")
