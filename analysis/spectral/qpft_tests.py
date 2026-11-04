"""QPFT tests on NINO1+2: NAFF lines, harmonic test (f_QB = 2 f_QQ?), combination tones
with the annual cycle, and frequency drift between the two halves of the record."""
from ssa_core import *  # also puts qpft on sys.path
import qpft
from qpft.transform import refine_frequency, direct, inverse
s = site_window(load("nino12")); a, clim = anomaly(s)
N = len(s); t = np.arange(N) / 12.0           # years; "Hz" == cycles/year
sst, x = s.values, a.values
T = N / 12

# 1. NAFF on raw SST (annual cycle included)
b = qpft.estimate_basis(t, sst, 10)
print(f"1) NAFF lines in raw SST (T={T:.1f} yr, resolution 1/T={1/T:.3f} cpy)")
for f, A in sorted(zip(b["f"], b["A"]), key=lambda z: -z[1]):
    print(f"   f={f:6.3f} cpy  period={12/f:6.1f} mo  A={A:.2f} °C")

# helper: frequency + uncertainty by AR1 surrogates around a fitted line model
def f_with_err(tt, y, f0s, nsur=200, seed=0):
    fs = [refine_frequency(tt, y, f0, window="hann", half_width=1.5/(len(tt)/12))[0] for f0 in f0s]
    fit = direct(tt, y - y.mean(), 2*np.pi*np.array(fs), method="lstsq")
    res = (y - y.mean()) - inverse(fit, tt); g = np.corrcoef(res[:-1], res[1:])[0,1]; sd = res.std()*np.sqrt(1-g*g)
    rng = np.random.default_rng(seed); out = []
    for _ in range(nsur):
        e = np.empty(len(tt)); e[0] = rng.standard_normal()*res.std()
        w = rng.standard_normal(len(tt))*sd
        for i in range(1, len(tt)): e[i] = g*e[i-1] + w[i]
        ys = inverse(fit, tt) + e
        out.append([refine_frequency(tt, ys, f, window="hann", half_width=1.5/(len(tt)/12))[0] for f in fs])
    out = np.array(out)
    return np.array(fs), out.std(axis=0), out

# 2. harmonic test on the anomaly
fs, err, sur = f_with_err(t, x, [0.232, 0.44, 0.667, 1.10])
print("\n2) Lines in the anomaly (Hann-refined, ±1σ from 200 AR1 surrogates)")
for f, e in zip(fs, err): print(f"   f={f:.4f} ± {e:.4f} cpy   period {12/f:.1f} mo")
d = sur[:,1] - 2*sur[:,0]; d0 = fs[1] - 2*fs[0]
print(f"   f_QB - 2 f_QQ = {d0:+.4f} ± {d.std():.4f} cpy  ->  {abs(d0)/d.std():.1f} σ")

# 3. combination tones
fE, fB = fs[0], fs[1]
print("\n3) Combination tones (annual = 1 cpy)")
for lab, f in [("18-mo line", fs[2]), ("11-mo line", fs[3])]:
    cands = {"1-fQQ": 1-fE, "1+fQQ": 1+fE, "1-fQB": 1-fB, "1+fQB": 1+fB, "1-2fQQ": 1-2*fE, "fQQ+fQB": fE+fB, "2fQB": 2*fB}
    best = sorted(cands.items(), key=lambda kv: abs(kv[1]-f))[:2]
    print(f"   {lab} f={f:.3f}: nearest " + ", ".join(f"{k}={v:.3f} (Δ={f-v:+.3f})" for k,v in best))

# 4. drift between halves
h = N//2
print("\n4) Frequency drift, first vs second half (each ~25.5 yr)")
for lab, f0 in [("QQ", 0.232), ("QB", 0.44)]:
    r = []
    for sl in (slice(0,h), slice(h,N)):
        tt = t[sl]-t[sl][0]; y = x[sl]
        f1, e1, _ = f_with_err(tt, y, [f0], nsur=150); r.append((f1[0], e1[0]))
    dd = r[1][0]-r[0][0]; ee = np.hypot(r[0][1], r[1][1])
    print(f"   {lab}: {r[0][0]:.3f}±{r[0][1]:.3f} -> {r[1][0]:.3f}±{r[1][1]:.3f} cpy  (periods {12/r[0][0]:.0f} -> {12/r[1][0]:.0f} mo); drift {dd:+.3f} = {abs(dd)/ee:.1f} σ")
