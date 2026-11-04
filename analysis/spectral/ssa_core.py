"""Shared helpers for the spectral analyses of the NINO1+2 record (SSA, QPFT tests).

Paths: the data are read from <repo>/data/series/*.csv. The QPFT package is found through the
environment variable QPFT_PATH (default: ../../Al_nonlinear_waves/quasiperiodic_fourier relative
to the repository root, which is where it lives on the IMR PC).
"""
import os, sys
from pathlib import Path
import numpy as np, pandas as pd

REPO = Path(__file__).resolve().parents[2]
D = str(REPO / "data" / "series") + os.sep
OUT = Path(__file__).resolve().parent / "output"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "src"))
from enso.fourier import passa_baixa  # the site's own Fourier low-pass (same as el_nino.filter)
sys.path.insert(0, os.environ.get("QPFT_PATH", str(REPO.parents[1] / "Al_nonlinear_waves" / "quasiperiodic_fourier")))

def load(name):
    df = pd.read_csv(D + name + ".csv", comment="#")
    df["period"] = pd.PeriodIndex(df["period"], freq="M")
    return df.set_index("period")["value"]

def site_window(s, end=None, base=1975):
    end = s.index[-1] if end is None else end
    start_month = end.month % 12 + 1
    start = pd.Period(f"{base}-{start_month:02d}", "M")
    return s.loc[max(start, s.index[0]):end]

def anomaly(s):
    clim = s.groupby(s.index.month).transform("mean")
    return s - clim, clim

def ssa_eig(x, M):
    N = len(x); K = N - M + 1
    X = np.lib.stride_tricks.sliding_window_view(x, M)  # K x M
    C = X.T @ X / K
    lam, E = np.linalg.eigh(C)
    o = np.argsort(lam)[::-1]
    return lam[o], E[:, o], X

def rc(X, E, ks, N):
    """Reconstructed component for eigenvector set ks (diagonal averaging)."""
    M = E.shape[0]; K = X.shape[0]
    A = X @ E[:, ks]                    # K x len(ks)
    Z = A @ E[:, ks].T                  # K x M  (rank-r approx of X)
    out = np.zeros(N); cnt = np.zeros(N)
    for j in range(M):
        out[j:j+K] += Z[:, j]; cnt[j:j+K] += 1
    return out / cnt

def eof_period(e, nfft=8192):
    p = np.abs(np.fft.rfft(e - e.mean(), nfft))**2
    f = np.fft.rfftfreq(nfft, 1.0)
    i = np.argmax(p[1:]) + 1
    return 1 / f[i]

def ar1_mc(x, E, M, n=500, seed=0):
    rng = np.random.default_rng(seed)
    x = x - x.mean(); N = len(x)
    g = np.corrcoef(x[:-1], x[1:])[0, 1]
    s = np.sqrt(x.var() * (1 - g**2))
    out = np.empty((n, E.shape[1]))
    for i in range(n):
        y = np.empty(N + 200); y[0] = 0
        w = rng.standard_normal(N + 200) * s
        for t in range(1, N + 200): y[t] = g * y[t-1] + w[t]
        y = y[200:]
        Xs = np.lib.stride_tricks.sliding_window_view(y - y.mean(), M)
        Cs = Xs.T @ Xs / Xs.shape[0]
        out[i] = np.einsum("ij,jk,ki->i", E.T, Cs, E)
    return g, out

def lrf_extend(x, E, ks, h):
    """Recurrent SSA forecast (Golyandina): extend x by h steps using eigvecs ks."""
    P = E[:, ks]
    pi = P[-1, :]
    nu2 = (pi**2).sum()
    R = (P[:-1, :] @ pi) / (1 - nu2)    # coefficients for previous M-1 values
    y = list(x)
    M = E.shape[0]
    for _ in range(h):
        y.append(float(np.dot(R, y[-(M-1):])))
    return np.array(y)
