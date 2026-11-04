"""Figure: SSA spectrum with red-noise test, edge revisions, the two smoothed signals, SSA
components and the 52-month mode's phase plane. Run ssa_vs_fourier.py first."""
from ssa_core import *
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
r = np.load(OUT / "ssa_results.npz", allow_pickle=True)
idx = pd.PeriodIndex(r["idx"], freq="M"); t = idx.year + (idx.month-0.5)/12
a, F, S, Se = r["a"], r["F"], r["S"], r["Se"]
xs, sd = r["xs"], float(r["sd"]); N = len(xs); M = 120
lam, E, X = ssa_eig(xs, M)
g, mc = ar1_mc(xs - rc(X, E, [0,1], N), E, M, n=500, seed=1)
lo, hi = np.percentile(mc, [2.5, 97.5], axis=0)
P = np.array([eof_period(E[:,k]) for k in range(20)])
QQ = rc(X,E,[0,1],N)*sd; R1 = rc(X,E,[0],N)*sd; R2 = rc(X,E,[1],N)*sd
QB = rc(X,E,[7],N)*sd; DEC = rc(X,E,[2,3,4,6],N)*sd; C18 = rc(X,E,[8,9],N)*sd

BLUE, ORANGE, AQUA, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#1f2328", "#6b7280", "#e5e7eb"
plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left"})
fig = plt.figure(figsize=(13, 11.5), dpi=150)
gs = fig.add_gridspec(3, 2, height_ratios=[1, 1.05, 1.15], hspace=0.42, wspace=0.22)

ax = fig.add_subplot(gs[0,0]); k = np.arange(1, 21)
ax.fill_between(k, lo[:20], hi[:20], color=GRID, step="mid", label="Red noise (AR1), 95% range")
sig = lam[:20] > hi[:20]
ax.plot(k[~sig], lam[:20][~sig], "o", ms=6, mfc="white", mec=MUTED, label="Not significant")
ax.plot(k[sig], lam[:20][sig], "o", ms=7, color=BLUE, label="Above red noise (97.5%)")
for kk, lab in [(2,"52-month pair"),(8,"27 mo"),(10,"18-month pair"),(15,"11-month pair")]:
    ax.annotate(lab, (kk, lam[kk-1]), xytext=(6,6), textcoords="offset points", fontsize=8.5, color=INK)
ax.set_yscale("log"); ax.set_xlabel("SSA component (window 120 months)"); ax.set_ylabel("Variance (eigenvalue)")
ax.set_title("A. SSA spectrum of NINO1+2 anomalies"); ax.legend(frameon=False, fontsize=8.5); ax.set_xticks([1,5,10,15,20])

ax = fig.add_subplot(gs[0,1]); L = np.arange(len(r["rmsF"]))
ax.plot(L, r["rmsF"], color=BLUE, lw=2, label="Fourier low-pass (current)")
ax.plot(L, r["rmsS"], color=MUTED, lw=1.5, ls="--", label="SSA, plain")
ax.plot(L, r["rmsSe"], color=ORANGE, lw=2, label="SSA + forecast extension")
ax.axvspan(0, 10, color=GRID, alpha=0.6, lw=0); ax.text(0.4, 0.47, "site's provisional zone", fontsize=8, color=MUTED)
ax.set_xlabel("Months before the end of the record"); ax.set_ylabel("RMS revision (°C)")
ax.set_title("B. How much the end changes later (hindcast, 120 ends 1995 to 2024)"); ax.legend(frameon=False, fontsize=8.5); ax.set_ylim(0, 0.55)

ax = fig.add_subplot(gs[1,:])
ax.plot(t, a, color="#c4c8ce", lw=0.8, label="Observed anomaly")
ax.plot(t, F, color=BLUE, lw=1.8, label="Fourier low-pass (current)")
ax.plot(t, S, color=ORANGE, lw=1.6, label="SSA, components > 20 months")
ax.axhline(0, color=MUTED, lw=0.6)
ax.set_ylabel("NINO1+2 anomaly (°C)"); ax.set_xlim(1975.8, 2027)
ax.set_title(f"C. Same signal from two methods: correlation {np.corrcoef(F,S)[0,1]:.3f}, RMS difference {np.sqrt(np.mean((F-S)**2)):.2f} °C")
ax.legend(frameon=False, ncol=3, fontsize=8.5, loc="upper left")

ax = fig.add_subplot(gs[2,0]); off = 0
for y, c, lab in [(QQ, BLUE, f"Quasi-quadrennial pair, {P[0]:.0f} mo ({100*(lam[0]+lam[1])/lam.sum():.0f}% var)"),
                  (QB, ORANGE, f"Quasi-biennial, {P[7]:.0f} mo ({100*lam[7]/lam.sum():.0f}%)"),
                  (C18, AQUA, f"18-month pair, {P[8]:.0f} mo ({100*(lam[8]+lam[9])/lam.sum():.0f}%)"),
                  (DEC, MUTED, f"Low-frequency, 6 to 13 yr ({100*(lam[2]+lam[3]+lam[4]+lam[6])/lam.sum():.0f}%)")]:
    ax.plot(t, y - off, color=c, lw=1.5); ax.text(1976, -off + 1.0, lab, fontsize=8.5, color=INK)
    ax.axhline(-off, color=GRID, lw=0.6); off += 3.0
ax.set_yticks([]); ax.set_xlim(1975.8, 2027); ax.spines["left"].set_visible(False)
ax.set_title("D. What the Fourier filter lumps together (SSA components, °C, offset)")

ax = fig.add_subplot(gs[2,1])
w = 2*np.pi/P[0]; R1 = QQ; R2 = np.gradient(QQ)/w
ax.plot(R1, R2, color="#c4c8ce", lw=0.7)
for lab, lo_, hi_, c in [("1982-83","1981-06","1984-06",INK),("1997-98","1996-06","1999-06",BLUE),("2015-16","2014-06","2017-06",AQUA),("2025-26","2025-01","2026-10",ORANGE)]:
    m = (idx >= pd.Period(lo_,"M")) & (idx <= pd.Period(hi_,"M"))
    ax.plot(R1[m], R2[m], color=c, lw=2, label=lab)
ax.plot(R1[-1], R2[-1], "o", color=ORANGE, ms=8, mec="white")
ax.axhline(0, color=GRID, lw=0.6); ax.axvline(0, color=GRID, lw=0.6); ax.set_aspect("equal", "datalim")
ax.set_xlabel("52-month mode (°C)"); ax.set_ylabel("Its rate ÷ ω (°C), quarter period ahead"); ax.legend(frameon=False, fontsize=8.5, loc="upper left")
ax.set_title("E. The 52-month mode alone: amplitude and phase")
fig.savefig(OUT / "ssa_vs_fourier_nino12.png", bbox_inches="tight", dpi=150)
print("QQ var %", 100*(lam[0]+lam[1])/lam.sum(), "periods", P[:10].round(1), "AR1 g", g)
