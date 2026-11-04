"""Calibration: the QPFT diagnostics of qpft_tests.py applied to the Duffing El Nino fit
(chaotic, FA x1) and a periodic run (FA x1.5), with and without noise, in 51-year segments,
and to the NINO1+2 data. Shows which diagnostics can tell chaos from periodic + noise."""
from ssa_core import *  # also puts qpft on sys.path
import qpft
from scipy.integrate import solve_ivp
from qpft.transform import refine_frequency, direct, inverse
from ssa_core import OUT, load, site_window, anomaly
K1, K3, FA0, FF, B, W = 0.1218, -0.0305, 0.4873, np.deg2rad(-60), -0.3547, 0.5236
NSEG, NM = 6, 612

def run(fa_fac=1.0, sigma=0.0, seed=0):
    FA = FA0*fa_fac; T_end = 1200 + NSEG*NM
    if sigma == 0:
        f = lambda t, y: [y[1], K1*y[0] + K3*y[0]**3 + FA*np.cos(W*t - FF) + B*y[1]]
        sol = solve_ivp(f, (0, T_end), [0.5, 0.0], method="DOP853", rtol=1e-10, atol=1e-12, t_eval=np.arange(0, T_end))
        return sol.y[0][1200:]
    rng = np.random.default_rng(seed); dt = 0.01; n = int(T_end/dt); x, v = 0.5, 0.0; out = []
    sq = sigma*np.sqrt(dt)
    for i in range(n):
        t = i*dt
        if i % 100 == 0: out.append(x)
        a = K1*x + K3*x**3 + FA*np.cos(W*t - FF) + B*v
        x += v*dt; v += a*dt + sq*rng.standard_normal()
    return np.array(out[1200:])

def anomaly_m(y):
    m = np.arange(len(y)) % 12; c = np.array([y[m == k].mean() for k in range(12)]); return y - c[m]

def ferr(tt, y, f0, nsur=60, seed=0):
    T = len(tt)/12; f = refine_frequency(tt, y, f0, window="hann", half_width=1.5/T)[0]
    fit = direct(tt, y-y.mean(), [2*np.pi*f], method="lstsq"); res = y-y.mean()-inverse(fit, tt)
    g = np.clip(np.corrcoef(res[:-1], res[1:])[0,1], -0.99, 0.99); sd = res.std()*np.sqrt(1-g*g)
    rng = np.random.default_rng(seed); out = []
    for _ in range(nsur):
        e = np.zeros(len(tt)); w = rng.standard_normal(len(tt))*sd
        for i in range(1, len(tt)): e[i] = g*e[i-1] + w[i]
        out.append(refine_frequency(tt, inverse(fit, tt)+e, f, window="hann", half_width=1.5/T)[0])
    return f, np.std(out)

def diagnose(y_raw):
    N = len(y_raw); t = np.arange(N)/12; x = anomaly_m(y_raw)
    b = qpft.estimate_basis(t, x, 8)
    inter = sorted([(A, f) for f, A in zip(b["f"], b["A"]) if 0.08 < f < 0.8], reverse=True)
    if not inter: return dict(nlines=0, ratio=np.nan, f1=np.nan, drift_sig=np.nan, var_int=anomaly_m(y_raw).var()/y_raw.var())
    A1, f1 = inter[0]
    nlines = sum(1 for A, f in inter if A > 0.5*A1)
    ratio = inter[1][0]/A1 if len(inter) > 1 else 0.0
    h = N//2; r = []
    for sl in (slice(0, h), slice(h, N)):
        tt = t[sl]-t[sl][0]; r.append(ferr(tt, x[sl], f1))
    dsig = abs(r[1][0]-r[0][0])/np.hypot(r[0][1], r[1][1])
    return dict(nlines=nlines, ratio=ratio, f1=f1, drift_sig=dsig, drift=r[1][0]-r[0][0], var_int=x.var()/y_raw.var())

if __name__ == "__main__":
    s = site_window(load("nino12")).values
    d = diagnose(s)
    print(f"DATA nino12        : var share {d['var_int']:.2f} | lines>50% {d['nlines']} | f1 {d['f1']:.3f} cpy | drift {d['drift_sig']:.1f} sigma")
    for lab, fa, sg in [("chaotic x1.0", 1.0, 0.0), ("chaotic+noise .03", 1.0, 0.03), ("periodic x1.5", 1.5, 0.0),
                        ("periodic+noise .03", 1.5, 0.03), ("periodic+noise .15", 1.5, 0.15), ("periodic+noise .30", 1.5, 0.30)]:
        y = run(fa, sg, seed=1)
        res = [diagnose(y[k*NM:(k+1)*NM]) for k in range(NSEG)]
        f1 = [r["f1"] for r in res]; nl = [r["nlines"] for r in res]; ds = [r["drift_sig"] for r in res]
        print(f"{lab:19s}: var share {np.mean([r['var_int'] for r in res]):.2f} | lines>50% {nl} | f1 {np.round(f1,3).tolist()} | drift sigma {np.round(ds,1).tolist()}")
