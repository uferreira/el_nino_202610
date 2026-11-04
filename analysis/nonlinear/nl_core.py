"""Shared helpers for the nonlinearity and phase-locking tests of NINO1+2 (analysis/nonlinear).

Reuses analysis/spectral: ssa_core (data loading, site window, climatology, SSA, the site's
Fourier low-pass) and the Duffing integrator duffing_calibration.run (which imports qpft, so
QPFT_PATH must point at the package as for the spectral scripts).

Every series goes through the same function `stats(anom, cal0)`:
  anom  monthly anomaly (612 months, monthly climatology of that segment removed)
  cal0  calendar month (0 = January) of the first sample
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "spectral"))
from ssa_core import np, pd, load, site_window, anomaly, passa_baixa, ssa_eig, rc, eof_period
import duffing_calibration as dc
from scipy.signal import hilbert
from scipy.spatial.distance import cdist

OUT = HERE / "output"; OUT.mkdir(exist_ok=True)
HN1, HN2 = 10.0, 9.0            # site filter (config.yaml)
NM = 612                        # 51 years, the data window
TRIM = 24                       # months dropped at each end for Hilbert phases
RATIOS = [(1, 2), (2, 5), (1, 3), (2, 7), (1, 4), (2, 9), (1, 5), (1, 6), (1, 7)]  # f_E/f_a = m/n
WIN_RHO, WIN_LOCK = 120, 120    # sliding windows (months) for rotation number and locking
GAMMA_LOCK = 0.9                # a window counts as a plateau if some m:n has gamma above this


# ---------------------------------------------------------------- data and anomalies
def seg_anomaly(y):
    """Remove the segment's own monthly climatology (as the site does for its window)."""
    m = np.arange(len(y)) % 12
    c = np.array([y[m == k].mean() for k in range(12)])
    return y - c[m], c

def data_anomaly(name="nino12"):
    s = site_window(load(name)); a, clim = anomaly(s)
    return a.values.astype(float), s.index[0].month - 1, s

def harmonic_phase(c, cal0):
    """Phase (rad) of the first annual harmonic of a 12-value climatology starting at cal0."""
    m = (cal0 + np.arange(12)) % 12
    z = np.sum(c * np.exp(-2j * np.pi * m / 12))
    return np.angle(z)


# ---------------------------------------------------------------- surrogates (Theiler et al. 1992)
def ft_surrogate(x, rng):
    """Phase-randomised surrogate: same periodogram, Gaussian (null: linear Gaussian process)."""
    X = np.fft.rfft(x - x.mean()); ph = rng.uniform(0, 2 * np.pi, len(X)); ph[0] = 0
    if len(x) % 2 == 0: ph[-1] = 0
    return np.fft.irfft(np.abs(X) * np.exp(1j * ph), len(x)) + x.mean()

def iaaft(x, rng, n_iter=200):
    """Iterative amplitude-adjusted FT surrogate (Schreiber & Schmitz 1996): same amplitude
    distribution exactly, same periodogram to within the iteration (null: linear Gaussian process
    seen through a static monotone transform)."""
    amp = np.abs(np.fft.rfft(x)); xs = np.sort(x)
    y = rng.permutation(x); prev = None
    for _ in range(n_iter):
        Y = np.fft.rfft(y); y = np.fft.irfft(amp * np.exp(1j * np.angle(Y)), len(x))
        r = np.argsort(np.argsort(y)); y = xs[r]
        if prev is not None and np.array_equal(r, prev): break
        prev = r
    return y


# ---------------------------------------------------------------- nonlinearity statistics
def skew(x):
    x = x - x.mean(); return float(np.mean(x**3) / np.mean(x**2)**1.5)

def gmm_dbic(x, n_iter=300):
    """BIC(1 Gaussian) - BIC(2-Gaussian mixture) on standardised x (positive: 2 preferred), and
    whether the fitted mixture density has two maxima."""
    x = (x - x.mean()) / x.std(); n = len(x)
    ll1 = np.sum(-0.5 * x**2 - 0.5 * np.log(2 * np.pi))
    best = None
    for q in (0.2, 0.5, 0.8):                       # a few starts
        mu = np.quantile(x, [q / 2, 0.5 + q / 2]); sd = np.array([0.7, 0.7]); w = np.array([.5, .5])
        llo = -np.inf
        for _ in range(n_iter):
            p = w * np.exp(-0.5 * ((x[:, None] - mu) / sd)**2) / (sd * np.sqrt(2 * np.pi)) + 1e-300
            ll = np.log(p.sum(1)).sum(); g = p / p.sum(1, keepdims=True)
            if ll - llo < 1e-6: break
            llo = ll
            w = g.mean(0); mu = (g * x[:, None]).sum(0) / g.sum(0)
            sd = np.sqrt((g * (x[:, None] - mu)**2).sum(0) / g.sum(0)).clip(0.05)
        if best is None or ll > best[0]: best = (ll, w, mu, sd)
    ll2, w, mu, sd = best
    dbic = (-2 * ll1 + 2 * np.log(n)) - (-2 * ll2 + 5 * np.log(n))
    g = np.linspace(-4, 4, 801)
    dens = (w * np.exp(-0.5 * ((g[:, None] - mu) / sd)**2) / sd).sum(1)
    nmax = int(np.sum((dens[1:-1] > dens[:-2]) & (dens[1:-1] > dens[2:])))
    return float(dbic), nmax >= 2

def asym(xf):
    """El Nino / La Nina amplitude asymmetry: 95th percentile over |5th percentile|."""
    q05, q95 = np.quantile(xf - np.median(xf), [0.05, 0.95]); return float(q95 / -q05)

def trev(x, tau):
    """Time-reversal asymmetry: skewness of increments at lag tau."""
    d = x[tau:] - x[:-tau]; return float(np.mean(d**3) / np.mean(d**2)**1.5)

def pred_ratio(x, m=4, tau=3, h=6, k=8, excl=12):
    """Nearest-neighbour (locally constant, k neighbours) over linear AR error, same delay
    coordinates (m lags spaced tau months), horizon h months. Out-of-sample: neighbours within
    excl months excluded, linear by leave-one-out. Below 1: nonlinear structure helps."""
    x = (x - x.mean()) / x.std()
    idx = np.arange((m - 1) * tau, len(x) - h)
    E = np.stack([x[idx - j * tau] for j in range(m)], 1); y = x[idx + h]
    D = cdist(E, E); ii = np.arange(len(idx)); D[np.abs(ii[:, None] - ii[None, :]) < excl] = np.inf
    nn = np.argpartition(D, k, axis=1)[:, :k]; e_nn = np.sqrt(np.mean((y[nn].mean(1) - y)**2))
    A = np.column_stack([E, np.ones(len(idx))]); beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    H = np.einsum("ij,ji->i", A, np.linalg.pinv(A)); r = (y - A @ beta) / (1 - H)
    return float(e_nn / np.sqrt(np.mean(r**2)))


# ---------------------------------------------------------------- phase locking
def events(xf, xr, sign=+1, on=0.5, peak=1.0):
    """Event peak indices: runs where sign*xf > on*sd with sign*max > peak*sd; peak month is the
    extreme of the 3-month running mean of the raw anomaly inside the run."""
    sd = xf.std(); z = sign * xf / sd; r3 = sign * np.convolve(xr, np.ones(3) / 3, "same")
    out = []; i = 0; N = len(z)
    while i < N:
        if z[i] > on:
            j = i
            while j < N and z[j] > on: j += 1
            if z[i:j].max() > peak and i > 0 and j < N:      # whole events only
                out.append(i + int(np.argmax(r3[i:j])))
            i = j
        else: i += 1
    return np.array(out, int)

def rayleigh(months):
    """Rayleigh test on calendar months (0..11): n, R, mean month (1..12), p (Zar 1999 approx)."""
    n = len(months)
    if n < 2: return dict(n=n, R=np.nan, month=np.nan, p=np.nan)
    z = np.exp(2j * np.pi * months / 12).mean(); R = abs(z); Rn = n * R
    p = np.exp(np.sqrt(1 + 4 * n + 4 * (n * n - Rn * Rn)) - (1 + 2 * n))
    return dict(n=n, R=float(R), month=float((np.angle(z) / (2 * np.pi) * 12) % 12 + 1), p=float(min(p, 1)))

def monthly_sd(x, cal0):
    m = (cal0 + np.arange(len(x))) % 12
    return np.array([x[m == k].std() for k in range(12)])

def ssa_pair(x, M=120, lo=30, hi=90):
    """Reconstruct the leading SSA oscillatory pair with period in [lo, hi] months (the 52-month
    pair in the data). Returns (rc, period) or (None, nan)."""
    lam, E, X = ssa_eig(x - x.mean(), M)
    per = [eof_period(E[:, k]) for k in range(12)]
    for k in range(11):
        p1, p2 = per[k], per[k + 1]
        if lo <= p1 <= hi and lo <= p2 <= hi and abs(p1 - p2) / (p1 + p2) * 2 < 0.25:
            return rc(X, E, [k, k + 1], len(x)), 0.5 * (p1 + p2)
    return None, np.nan

def phase_stats(y, cal0, keep=False):
    """Hilbert phase of y against the annual phase: rotation number in sliding windows (cycles of
    ENSO per year), whole-record m:n synchronisation index, fraction of windows on a plateau."""
    if y is None or not np.isfinite(y).all() or y.std() == 0:
        return dict(rho=np.nan, rho_sd=np.nan, gamma=np.nan, ratio=np.nan, plateau=np.nan)
    phE = np.unwrap(np.angle(hilbert(y - y.mean())))
    t = np.arange(len(y)); phA = 2 * np.pi * (cal0 + t) / 12
    sl = slice(TRIM, len(y) - TRIM); pE, pA, tt = phE[sl], phA[sl], t[sl]
    rho = [np.polyfit(tt[i:i + WIN_RHO], pE[i:i + WIN_RHO], 1)[0] * 12 / (2 * np.pi)
           for i in range(0, len(tt) - WIN_RHO + 1, 12)]
    G = np.array([abs(np.mean(np.exp(1j * (n * pE - m * pA)))) for m, n in RATIOS])
    starts = range(0, len(tt) - WIN_LOCK + 1, 6)
    gw = np.array([[abs(np.mean(np.exp(1j * (n * pE[i:i + WIN_LOCK] - m * pA[i:i + WIN_LOCK]))))
                    for m, n in RATIOS] for i in starts])
    d = dict(rho=float(np.mean(rho)), rho_sd=float(np.std(rho)), gamma=float(G.max()),
             ratio="%d:%d" % RATIOS[int(G.argmax())][::-1], plateau=float(np.mean(gw.max(1) > GAMMA_LOCK)))
    if keep: d.update(phE=phE, phA=phA, rho_series=np.array(rho), gw=gw)
    return d


# ---------------------------------------------------------------- all statistics for one series
NL_KEYS = ["skew_raw", "skew_f", "dbic_f", "asym_f", "trev_raw1", "trev_f6", "pred"]
PL_KEYS = ["R_nino", "R_nina", "var_ratio", "rho_f", "rho_sd_f", "gamma_f", "plateau_f",
           "rho_ssa", "rho_sd_ssa", "gamma_ssa", "plateau_ssa"]
# one-sided direction of the departure from linearity (+1: large is nonlinear, -1: small), 0 = two-sided
SIDE = dict(skew_raw=0, skew_f=0, dbic_f=1, asym_f=0, trev_raw1=0, trev_f6=0, pred=-1,
            R_nino=1, R_nina=1, var_ratio=1, rho_f=0, rho_sd_f=0, gamma_f=1, plateau_f=1,
            rho_ssa=0, rho_sd_ssa=0, gamma_ssa=1, plateau_ssa=1)

def stats(x, cal0, phases=True, keep=False):
    x = x - x.mean(); xf = passa_baixa(HN1, HN2, x)
    db, bim = gmm_dbic(xf)
    d = dict(skew_raw=skew(x), skew_f=skew(xf), dbic_f=db, bimodal_f=bim, asym_f=asym(xf),
             trev_raw1=trev(x, 1), trev_f6=trev(xf, 6), pred=pred_ratio(x))
    m = (cal0 + np.arange(len(x))) % 12
    for lab, sg in (("nino", 1), ("nina", -1)):
        mon = m[events(xf, x, sg)]; r = rayleigh(mon); d.update({f"{k}_{lab}": v for k, v in r.items()})
        if keep: d[f"mon_{lab}"] = mon
    sdm = monthly_sd(x, cal0); d.update(var_ratio=float(sdm.max() / sdm.min()), var_peak=int(sdm.argmax()) + 1)
    if phases:
        pf = phase_stats(xf, cal0, keep); y2, per = ssa_pair(x); ps = phase_stats(y2, cal0, keep)
        d.update({f"{k}_f": v for k, v in pf.items()}); d.update({f"{k}_ssa": v for k, v in ps.items()})
        d["ssa_period"] = per
    if keep: d.update(xf=xf, sdm=sdm)
    return d

def pvalue(s0, sur, side):
    sur = np.asarray([v for v in sur if np.isfinite(v)], float)
    if not np.isfinite(s0) or len(sur) == 0: return np.nan
    n = len(sur); ge = (np.sum(sur >= s0) + 1) / (n + 1); le = (np.sum(sur <= s0) + 1) / (n + 1)
    return float(ge if side > 0 else le if side < 0 else min(1, 2 * min(ge, le)))

def surrogate_test(x, cal0, nsur, kind="iaaft", seed=0, phases=True):
    rng = np.random.default_rng(seed); make = iaaft if kind == "iaaft" else ft_surrogate
    keys = NL_KEYS + (PL_KEYS if phases else ["R_nino", "R_nina", "var_ratio"])
    S = {k: [] for k in keys}
    for _ in range(nsur):
        d = stats(make(x, rng), cal0, phases)
        for k in keys: S[k].append(d[k])
    return {k: np.array(v, float) for k, v in S.items()}


# ---------------------------------------------------------------- models
def duffing_series(fa_fac, sigma=0.0, nseg=10, seed=1):
    """Monthly x of the Duffing El Nino fit (dc.run), nseg 612-month segments after the transient.
    The model's month 0 is mapped to the calendar month that aligns its mean annual cycle with
    the NINO1+2 climatology (first-harmonic phase)."""
    dc.NSEG = nseg
    return dc.run(fa_fac, sigma, seed)

def model_cal0(y, data_clim, data_cal0):
    c = seg_anomaly(y)[1]
    if np.ptp(c) == 0: return data_cal0
    dphi = harmonic_phase(c, 0) - harmonic_phase(data_clim, data_cal0)
    # model month j sits at calendar month j + s with s from the phase difference
    return int(round(dphi / (2 * np.pi) * 12)) % 12

def fit_ar(x, p):
    r = np.array([np.dot(x[:len(x) - k], x[k:]) / len(x) for k in range(p + 1)])
    R = np.array([[r[abs(i - j)] for j in range(p)] for i in range(p)])
    phi = np.linalg.solve(R, r[1:p + 1]); return phi, r[0] - phi @ r[1:p + 1]

def sim_ar(phi, s2, n, rng, burn=600):
    p = len(phi); y = np.zeros(n + burn); e = rng.standard_normal(n + burn) * np.sqrt(s2)
    for t in range(p, n + burn): y[t] = phi @ y[t - p:t][::-1] + e[t]
    return y[burn:]

def fit_par2(x, cal0):
    """Periodic AR(2): x_t = a1(m) x_{t-1} + a2(m) x_{t-2} + s(m) e_t, m = calendar month of t."""
    m = (cal0 + np.arange(len(x))) % 12; P = np.zeros((12, 3))
    for k in range(12):
        t = np.where(m == k)[0]; t = t[t >= 2]
        A = np.column_stack([x[t - 1], x[t - 2]]); b, *_ = np.linalg.lstsq(A, x[t], rcond=None)
        P[k] = b[0], b[1], np.std(x[t] - A @ b)
    return P

def sim_par2(P, n, cal0, rng, burn=600):
    y = np.zeros(n + burn); m0 = (cal0 - burn) % 12
    for t in range(2, n + burn):
        a1, a2, s = P[(m0 + t) % 12]; y[t] = a1 * y[t - 1] + a2 * y[t - 2] + s * rng.standard_normal()
    return y[burn:]

def fit_lim(Z, tau0):
    """Linear inverse model (Penland & Sardeshmukh 1995) of z = (T, h): dz/dt = L z + noise,
    L = log(C(tau0) C(0)^-1)/tau0. Returns L and the monthly propagator and noise factor in the
    form sim_var1 takes (12 identical months)."""
    from scipy.linalg import logm, expm
    C0 = Z.T @ Z / len(Z); Ct = Z[tau0:].T @ Z[:-tau0] / (len(Z) - tau0)
    L = logm(Ct @ np.linalg.inv(C0)).real / tau0; G = expm(L)
    S1 = C0 - G @ C0 @ G.T                      # keeps the observed covariance stationary
    return L, [(G, np.linalg.cholesky(S1))] * 12

def sim_var1(Ps, n, cal0, rng, burn=600):
    z = np.zeros(2); out = np.empty((n + burn, 2)); m0 = (cal0 - burn) % 12
    for t in range(n + burn):
        out[t] = z; A, L = Ps[(m0 + t) % 12]; z = A @ z + L @ rng.standard_normal(2)
    return out[burn:]
