"""Figures from output/nl_results.json and output/nl_arrays.npz (written by nl_tests.py):
  output/nl_nonlinearity.png    surrogate distributions, data and model segments, per statistic
  output/nl_seasonal.png        event peak months and anomaly s.d. per calendar month
  output/nl_frequency.png       m:n phase differences, rotation number, plateau statistics
"""
import json
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from nl_core import OUT, RATIOS, TRIM, WIN_RHO

R = json.loads((OUT / "nl_results.json").read_text()); A = np.load(OUT / "nl_arrays.npz")
D = R["data"]; INK, MUTED, GRID = "#1f1f1e", "#8a897f", "#e4e3dc"
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]   # fixed categorical order
MK = ["o", "s", "^", "D", "v", "P"]
MODELS = [m for m in R["models"] if R["models"][m]["stats"]]               # skips the period-1 run
STYLE = {m: (PAL[i], MK[i]) for i, m in enumerate(MODELS)}
SHORT = {m: m.replace(" (FA x1)", "").replace("Duffing ", "Duffing ").replace(
    "Recharge oscillator (LIM, T + Palau h, tau0 6)", "Recharge osc. (LIM, Palau)") for m in MODELS}
MON = "JFMAMJJASOND"
plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK,
                     "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True})

def strip(ax, key, title, p):
    """Surrogate histogram (IAAFT filled, FT outline), data line, model segments as a strip below."""
    s1 = A[f"sur_iaaft_{key}"]; s2 = A[f"sur_ft_{key}"]
    vals = [s1, s2, [D[key]]] + [A[f"{m}|{key}"] for m in MODELS]
    lo, hi = np.nanpercentile(np.concatenate([np.ravel(v) for v in vals]), [0.5, 99.5]); pad = 0.05 * (hi - lo)
    bins = np.linspace(lo - pad, hi + pad, 40)
    h1, _, _ = ax.hist(s1[np.isfinite(s1)], bins, color="#b7d3f6", label="IAAFT surrogates")
    h2, _, _ = ax.hist(s2[np.isfinite(s2)], bins, histtype="step", color=MUTED, lw=1, label="FT (Gaussian) surrogates")
    top = max(h1.max(), h2.max()); ax.axvline(D[key], color=INK, lw=2, label="NINO1+2")
    for i, m in enumerate(MODELS):
        c, mk = STYLE[m]; y = -top * (0.12 + 0.11 * i)
        ax.scatter(A[f"{m}|{key}"], np.full(len(A[f"{m}|{key}"]), y), s=16, color=c, marker=mk,
                   edgecolor="white", linewidth=0.5, label=SHORT[m], zorder=3)
    ax.set_ylim(-top * (0.12 + 0.11 * len(MODELS)), top * 1.15); ax.set_yticks([])
    ax.set_title(f"{title}\np = {p}", fontsize=8.5, loc="left")

def fmt(v): return "n/a" if v != v else ("<0.002" if v < 0.002 else f"{v:.3f}")

# --------------------------------------------------------------- 1. nonlinearity
NL = [("skew_raw", "Skewness, raw anomaly"), ("skew_f", "Skewness, filtered"),
      ("dbic_f", "Bimodality ΔBIC, filtered"), ("asym_f", "Warm/cold asymmetry q95/|q05|"),
      ("trev_raw1", "Time reversal, raw, lag 1"), ("trev_f6", "Time reversal, filtered, lag 6"),
      ("pred", "Prediction error NN / linear")]
fig, axs = plt.subplots(2, 4, figsize=(13, 6.2), constrained_layout=True)
for ax, (k, t) in zip(axs.flat, NL):
    strip(ax, k, t, f"{fmt(R['p_iaaft'][k])} (IAAFT), {fmt(R['p_ft'][k])} (FT)")
axs.flat[-1].axis("off"); h, l = axs.flat[0].get_legend_handles_labels()
axs.flat[-1].legend(h, l, loc="center", frameon=False, title="Model dots: one per 51-year segment")
fig.suptitle("Nonlinearity tests, NINO1+2 Nov 1975 to Oct 2026, against 500 surrogates", x=0.01, ha="left", fontsize=10)
fig.savefig(OUT / "nl_nonlinearity.png", dpi=150); plt.close(fig)

# --------------------------------------------------------------- 2. seasonal locking
fig, axs = plt.subplots(1, 3, figsize=(13, 3.8), constrained_layout=True)
mon = np.arange(12)
for ax, lab, name in [(axs[0], "nino", "El Niño peak month"), (axs[1], "nina", "La Niña trough month")]:
    dm = A[f"data_mon_{lab}"]
    ax.bar(mon, np.bincount(dm, minlength=12) / max(len(dm), 1), color="#cfcdc4", width=0.8,
           label=f"NINO1+2 (n = {len(dm)})")
    for m in MODELS:
        v = A[f"{m}|mon_{lab}"]; c, mk = STYLE[m]
        if len(v): ax.plot(mon, np.bincount(v, minlength=12) / len(v), color=c, marker=mk, ms=4, lw=1.5,
                           label=f"{SHORT[m]} (n = {len(v)})")
    ax.set_xticks(mon, list(MON)); ax.set_ylabel("Fraction of events")
    ax.set_title(f"{name}: NINO1+2 bars (n = {len(dm)}), models pooled over segments", loc="left", fontsize=8.5)
ax = axs[2]; sd = A["data_sdm"]
ax.plot(mon, sd / sd.mean(), color=INK, lw=2.5, label="NINO1+2")
for m in MODELS:
    v = A[f"{m}|sdm"]; v = v / v.mean(1, keepdims=True); c, mk = STYLE[m]
    ax.plot(mon, np.median(v, 0), color=c, marker=mk, ms=4, lw=1.5, label=SHORT[m])
ax.set_xticks(mon, list(MON)); ax.set_ylabel("Anomaly s.d. / its annual mean")
ax.set_title(f"Anomaly s.d. by calendar month (models: median of segments)\n"
             f"data max/min {D['var_ratio']:.2f}, p = {fmt(R['p_iaaft']['var_ratio'])} (IAAFT)", loc="left", fontsize=8.5)
ax.legend(frameon=False, fontsize=7)
fig.savefig(OUT / "nl_seasonal.png", dpi=150); plt.close(fig)

# --------------------------------------------------------------- 3. frequency locking
fig = plt.figure(figsize=(13, 7.4), constrained_layout=True); gs = fig.add_gridspec(2, 3)
ax = fig.add_subplot(gs[0, :2]); x = A["data_x"]; N = len(x); yr = 1975 + 10 / 12 + np.arange(N) / 12
phE, phA = A["data_phE_f"], A["data_phA_f"]; sl = slice(TRIM, N - TRIM)
for i, (m, n) in enumerate(RATIOS):
    psi = (n * phE - m * phA) / (2 * np.pi); psi = psi - psi[sl][0]
    ax.plot(yr[sl], psi[sl], lw=1.4, color=plt.cm.cividis(i / (len(RATIOS) - 1)), label=f"{m}/{n}")
ax.set_ylabel("(n φ_E − m φ_a) / 2π  (cycles)"); ax.set_xlabel("Year")
ax.set_title("ENSO phase (Hilbert, filtered) minus m/n x annual phase;\n"
             "n:m locking would show as a horizontal stretch", loc="left", fontsize=8.5)
ax.legend(ncol=9, frameon=False, fontsize=7, title="f_E = m/n cycles per year",
          title_fontsize=7, loc="upper left")
ax = fig.add_subplot(gs[0, 2]); yc = 1975 + 10 / 12 + (TRIM + WIN_RHO / 2 + 12 * np.arange(len(A["data_rho_series_f"]))) / 12
for m in (MODELS[0], "Seasonal linear PAR(2)"):
    v = A[f"{m}|rho_series_f"]; c, mk = STYLE[m]
    ax.fill_between(yc, np.nanmin(v, 0), np.nanmax(v, 0), color=c, alpha=0.2, lw=0, label=f"{SHORT[m]}, segment range")
for r in sorted({m / n for m, n in RATIOS}): ax.axhline(r, color=MUTED, lw=0.6, ls=":")
ax.plot(yc, A["data_rho_series_f"], color=INK, lw=2.2, label="NINO1+2, filtered")
ax.plot(yc, A["data_rho_series_ssa"], color=INK, lw=1.2, ls="--", label="NINO1+2, SSA 52-month pair")
ax.set_ylabel("Rotation number (ENSO cycles per year)"); ax.set_xlabel("Window centre (10-year windows)")
ax.set_title("Rotation number in 10-year windows\ndotted: m/n of the tested ratios", loc="left", fontsize=8.5)
ax.legend(frameon=False, fontsize=7)
for j, (k, t) in enumerate([("gamma_f", "Best m:n sync index (whole record), filtered"),
                            ("gamma_ssa", "Best m:n sync index (whole record), SSA pair"),
                            ("rho_sd_f", "s.d. of rotation number, filtered")]):
    strip(fig.add_subplot(gs[1, j]), k, t, f"{fmt(R['p_iaaft'][k])} (IAAFT), {fmt(R['p_ft'][k])} (FT)")
fig.get_axes()[-3].legend(frameon=False, fontsize=6.5, loc="upper right")
fig.suptitle("Frequency locking of ENSO to the annual cycle", x=0.01, ha="left", fontsize=10)
fig.savefig(OUT / "nl_frequency.png", dpi=150); plt.close(fig)
print("figures written to", OUT)
