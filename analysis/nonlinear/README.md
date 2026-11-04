# Nonlinearity and phase-locking tests of NINO1+2

Follow-up to `analysis/spectral` (November 2026). There, SSA and QPFT showed that NINO1+2 is consistent with the chaotic Duffing fit, but a linear AR(2) fitted to the data passes the same spectral tests. Spectra cannot separate chaos from linear noise. Here the question is answered with statistics a linear Gaussian process cannot produce (surrogate data, Theiler et al. 1992), and with seasonal and frequency phase locking, run identically on the data and on 51-year segments of the models.

Data window for everything: November 1975 to October 2026 (612 months), site climatology, site Fourier low-pass. Palau sea level for the recharge oscillator, same window.

## How to run

From this folder, with the repository's `.venv` (numpy, scipy, pandas, matplotlib) and `QPFT_PATH` set as for `analysis/spectral` (the Duffing integrator `duffing_calibration.run` is imported from there, and that module imports `qpft`):

```powershell
$env:QPFT_PATH = "C:\Users\a47575\projects\Al_nonlinear_waves\quasiperiodic_fourier"   # default if unset
..\..\.venv\Scripts\python.exe nl_tests.py     # about 6 min on 2 cores: writes output/nl_results.json, nl_arrays.npz
..\..\.venv\Scripts\python.exe nl_tables.py    # the tables below, from the json
..\..\.venv\Scripts\python.exe nl_figures.py   # the three figures
```

| Script | What it does |
|---|---|
| `nl_core.py` | Surrogates (FT, IAAFT), the test statistics, event and phase-locking statistics, the model generators (Duffing via `duffing_calibration.run`, AR(2), periodic AR(2), linear inverse model of T and Palau h) |
| `nl_tests.py` | Runs every statistic on the data (500 IAAFT + 500 FT surrogates) and on 10 segments of 612 months per model (100 IAAFT surrogates per segment) |
| `nl_tables.py` | Markdown tables from `output/nl_results.json` |
| `nl_figures.py` | `output/nl_nonlinearity.png`, `output/nl_seasonal.png`, `output/nl_frequency.png` |

## Methods

Same window (November 1975 to October 2026, 612 months) and climatology as the site: the monthly climatology of the window is removed; every model segment (612 months) has its own monthly climatology removed the same way. "Filtered" is the site's Fourier low-pass (`passa_baixa`, HN1 = 10, HN2 = 9) of the anomaly.

**Surrogates (Theiler et al. 1992).** FT: phase-randomised anomaly, same periodogram, Gaussian; null = linear Gaussian process. IAAFT (Schreiber & Schmitz 1996): same periodogram and exactly the same amplitude distribution; null = linear Gaussian process seen through a static monotone transform. Filtered statistics are computed by filtering each surrogate exactly as the data. p-values are rank-based, (count + 1)/(n + 1); two-sided for skewness, asymmetry, time reversal and the rotation number; one-sided in the nonlinear direction for bimodality (large ΔBIC), prediction (small ratio), seasonal locking and sync/plateau statistics (large).

**Statistics.**
- Skewness of the raw and filtered anomaly. With IAAFT the raw skewness is identical in every surrogate by construction, so only FT tests it.
- Bimodality: ΔBIC = BIC(1 Gaussian) − BIC(2-Gaussian mixture, EM) of the standardised filtered anomaly; also whether the fitted mixture density has two maxima. Absolute BIC values are meaningless for autocorrelated data; only the comparison with surrogates is used.
- Warm/cold asymmetry: 95th percentile over |5th percentile| of the filtered anomaly (around its median).
- Time-reversal asymmetry: skewness of increments, <(x(t+τ) − x(t))³>/<(x(t+τ) − x(t))²>^(3/2); raw anomaly τ = 1, filtered τ = 6 months.
- Nonlinear prediction: delay vectors of the standardised raw anomaly (m = 4, delay 3 months), horizon 6 months. Locally constant predictor (mean of 8 nearest neighbours, neighbours within 12 months of the target excluded) over a linear AR in the same coordinates (leave-one-out). A ratio below 1 means the nonlinear predictor is better.
- Seasonal locking: El Niño events = runs of the filtered anomaly above 0.5 s.d. with a maximum above 1 s.d. (whole runs only, not cut by the record ends); peak month = maximum of the 3-month running mean of the raw anomaly inside the run. La Niña the same with the sign reversed. Rayleigh test on the calendar months (Zar's approximation for p); also tested against the surrogates through R. Anomaly s.d. per calendar month, statistic max/min.
- Frequency locking: φ_E = Hilbert phase of the filtered anomaly and, separately, of the leading SSA pair with period 30 to 90 months (window 120 months; the 52-month pair in the data); φ_a = 2π (calendar month)/12. 24 months dropped at each end. Rotation number = slope of φ_E against time in 10-year windows (step 1 year), in ENSO cycles per year. Synchronisation index γ_{m/n} = |<exp i(n φ_E − m φ_a)>| for f_E/f_a = m/n in {1/2, 2/5, 1/3, 2/7, 1/4, 2/9, 1/5, 1/6, 1/7}; reported: the largest γ over the whole record, and the fraction of 10-year windows (step 6 months) in which some m/n has γ > 0.9 (a plateau).

**Models.** Ten segments of 612 months each (510 model years after the transient).
- Duffing El Niño fit (K1 = 0.1218, K3 = −0.0305, B = −0.3547, W = 2π/12, FF = −60°), `duffing_calibration.run`: FA ×1 (chaotic), FA ×1 with noise σ = 0.03, FA ×1.5 (periodic) and FA ×1.5 with noise σ = 0.15 (the noise level at which the periodic run has the data's share of variance outside the annual cycle, spectral README §3). The model's month 0 is placed at the calendar month that aligns the first harmonic of its mean annual cycle with that of NINO1+2 (December for the deterministic runs).
- AR(2) fitted to the anomaly (Yule-Walker), as in `stochastic_null.py`.
- Seasonal linear null: periodic AR(2), x(t) = a1(m) x(t−1) + a2(m) x(t−2) + s(m) e(t), all three coefficients per calendar month m, least squares on the anomaly. Seasonally varying growth rate and noise.
- Recharge oscillator: linear inverse model (Penland & Sardeshmukh 1995) of z = (T, h), T = NINO1+2 anomaly, h = Palau sea-level anomaly (same window, monthly climatology removed, linear trend removed), both standardised; L = log(C(τ0) C(0)⁻¹)/τ0 and noise chosen so the model keeps the observed covariance. τ0 = 6 months (see the τ test below).

## 1. Nonlinearity tests

Data against 500 IAAFT and 500 FT surrogates. With 500 surrogates the smallest possible two-sided p is 0.004 (data outside all surrogates).

| Statistic | NINO1+2 | IAAFT 2.5 to 97.5% | p (IAAFT) | p (FT, Gaussian) |
|---|---|---|---|---|
| Skewness, raw anomaly | **1.36** | 1.36 (fixed by construction) | n/a | 0.004 |
| Skewness, filtered anomaly | **1.66** | 0.57 to 1.39 | 0.004 | 0.004 |
| Non-Gaussian shape ΔBIC (1 vs 2 Gaussians), filtered | **213** | 29 to 146 | < 0.002 | < 0.002 |
| Bimodal (mixture density with two maxima), filtered | **no** | | | |
| Warm/cold asymmetry q95/\|q05\|, filtered | **2.86** | 1.35 to 2.37 | 0.004 | 0.004 |
| Time reversal, raw anomaly, lag 1 | **−0.10** | −0.48 to 0.46 | 0.71 | 0.27 |
| Time reversal, filtered, lag 6 | **0.80** | −0.40 to 0.42 | 0.004 | 0.004 |
| Prediction error, nearest neighbours / linear AR (6 months ahead) | **1.09** | 1.05 to 1.14 | 0.33 | 0.28 |

Models: median [min, max] over 10 segments of 612 months, and in brackets the share of segments that reject their own IAAFT null at 5% (100 surrogates per segment).

| Model | Skewness, filtered | ΔBIC, filtered | Bimodal segments | Asymmetry q95/\|q05\| | Time reversal, raw, lag 1 | Time reversal, filtered, lag 6 | NN / linear error |
|---|---|---|---|---|---|---|---|
| **NINO1+2** | **1.66** | **213** | **no** | **2.86** | **−0.10** | **0.80** | **1.09** |
| Duffing chaotic (FA ×1) | 0.09 [−0.06, 0.48] (0%) | 127 [87, 210] (100%) | 10 of 10 | 1.13 [0.90, 1.94] (20%) | 0.62 [0.31, 0.78] (100%) | 0.51 [0.35, 0.81] (100%) | 0.23 [0.19, 0.25] (100%) |
| Duffing chaotic + noise 0.03 | 0.23 [−0.61, 0.66] (0%) | 138 [44, 231] (100%) | 10 of 10 | 1.41 [0.39, 1.92] (40%) | −0.07 [−0.24, 0.21] (0%) | −0.10 [−0.36, 0.41] (30%) | 0.62 [0.55, 0.74] (100%) |
| Duffing periodic (FA ×1.5) | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| Duffing periodic + noise 0.15 | 0.54 [−0.33, 1.39] (10%) | 126 [45, 271] (90%) | 0 of 10 | 1.02 [0.72, 2.19] (40%) | 0.00 [−0.27, 0.06] (0%) | 0.02 [−0.64, 0.33] (10%) | 1.03 [0.99, 1.09] (80%) |
| AR(2) fitted | 0.16 [−0.28, 0.41] (0%) | 1.6 [−14, 59] (30%) | 4 of 10 | 1.17 [0.76, 1.72] (10%) | −0.02 [−0.23, 0.07] (10%) | −0.12 [−0.30, 0.40] (0%) | 1.11 [1.07, 1.16] (10%) |
| Seasonal linear, PAR(2) | 0.06 [−0.53, 0.48] (0%) | −0.1 [−18, 23] (0%) | 2 of 10 | 0.98 [0.68, 1.17] (0%) | 0.03 [−0.14, 0.15] (0%) | 0.00 [−0.48, 0.69] (10%) | 1.12 [1.06, 1.17] (0%) |
| Recharge oscillator (LIM, T and Palau h) | −0.02 [−0.76, 0.31] (10%) | −7.1 [−18, 50] (20%) | 1 of 10 | 0.99 [0.61, 1.27] (10%) | −0.06 [−0.30, 0.20] (10%) | 0.01 [−0.15, 0.16] (0%) | 1.09 [1.06, 1.13] (10%) |

The FA ×1.5 run is a period-1 orbit (anomaly s.d. 0.0003 model units): it has no interannual variability and the tests are undefined. Its noisy version is the meaningful "periodic" case.

Figure: `output/nl_nonlinearity.png` (surrogate histograms, data line, one dot per model segment).

- **NINO1+2 is not a linear Gaussian process, nor a static transform of one.** Filtered skewness, warm/cold asymmetry and the filtered time-reversal asymmetry (fast warming, slower cooling) lie outside all 500 IAAFT and all 500 FT surrogates. These four statistics are correlated (they all respond to the few large warm events, above all 1982-83 and 1997-98), so they are one finding, not four; with 18 statistics tested, p = 0.004 is the rank limit of 500 surrogates, not a sharper value.
- **None of the models reproduces this asymmetry.** All of them, the chaotic Duffing included, have filtered skewness near 0 and q95/|q05| near 1. The noise-free Duffing matches only the filtered time reversal (0.51 against 0.80).
- **The data show no deterministic predictability.** Nearest neighbours in delay space predict worse than the linear AR, as for every linear model (1.06 to 1.17). The chaotic Duffing gives 0.23 in every segment; with noise 0.03, 0.62.
- **The data are unimodal.** The ΔBIC is large because the distribution is skewed, not because it has two modes. Every Duffing chaotic segment, with or without noise, is bimodal (the double well).

## 2. Phase locking

### a) Seasonal

| | NINO1+2 | p (IAAFT) | Duffing chaotic | Duffing chaotic + noise 0.03 | Duffing periodic + noise 0.15 | AR(2) | Seasonal PAR(2) | Recharge osc. (LIM) |
|---|---|---|---|---|---|---|---|---|
| El Niño peaks per 51 years | 5 | | 10 [6, 11] | 8 [4, 11] | 7 [6, 9] | 8 [6, 10] | 8 [5, 10] | 10 [6, 11] |
| Mean peak month | 8.3 (Aug) | | 8.0 (Aug) | 1.3 (Jan) | 8.2 (Aug) | 6.9 | 9.3 | 9.1 |
| Rayleigh R, El Niño peaks | 0.58 (Rayleigh p 0.19) | 0.046 | 1.00 [0.99, 1.00] | 0.97 [0.95, 0.98] | 0.78 [0.28, 0.99] | 0.33 [0.15, 0.42] | 0.53 [0.25, 0.86] | 0.26 [0.11, 0.35] |
| Segments with Rayleigh p < 0.05 | no | | 10 of 10 | 10 of 10 | 7 of 10 | 0 of 10 | 4 of 10 | 0 of 10 |
| Rayleigh R, La Niña troughs | 0.46 (n 6, p 0.30) | 0.25 | 0.97 | 0.97 | 0.43 | 0.44 | 0.43 | 0.18 |
| Anomaly s.d. max/min over calendar months | 1.97 (max July) | 0.008 | 3.02 [2.70, 3.38] | 1.25 [1.23, 1.30] | 2.30 [1.75, 2.68] | 1.29 [1.18, 1.42] | 2.00 [1.64, 2.11] | 1.28 [1.16, 1.50] |

The Duffing month 0 is placed in December, which aligns the model's mean annual cycle with that of NINO1+2 (first harmonic).

Figure: `output/nl_seasonal.png`.

- **The data's seasonality of variance is real** (p = 0.008 against stationary surrogates) and the **seasonal linear null reproduces it** (PAR(2): 2.00 against 1.97, same mid-year maximum). Event peak months in the data are loosely clustered (R = 0.58 from only 5 events; Rayleigh p = 0.19, surrogate p = 0.046), again like PAR(2).
- **The chaotic Duffing is locked like a strobe.** Every El Niño in every segment peaks in the same month (R = 1.00); the data are far looser. The mean month (August) happens to agree with the data. Noise 0.03 keeps the locking (R = 0.97) but moves it to January and removes the seasonality of variance.

### b) Frequency locking

| | NINO1+2 | p (IAAFT) | Duffing chaotic | Duffing chaotic + noise | Duffing periodic + noise | AR(2) | PAR(2) | LIM |
|---|---|---|---|---|---|---|---|---|
| Rotation number, filtered (cycles/yr) | 0.25 | 0.82 | 0.31 [0.22, 0.35] | 0.16 [0.09, 0.18] | 0.35 [0.24, 0.43] | 0.20 [0.14, 0.29] | 0.22 [0.17, 0.25] | 0.22 [0.16, 0.29] |
| s.d. over 10-year windows, filtered | 0.05 | 0.54 | 0.06 [0.04, 0.10] | 0.07 [0.04, 0.11] | 0.08 [0.05, 0.12] | 0.08 [0.07, 0.11] | 0.07 [0.06, 0.10] | 0.07 [0.05, 0.13] |
| Best m:n sync index γ, filtered | 0.15 (2/7) | 0.66 | 0.41 [0.30, 0.47] (100%) | 0.21 [0.16, 0.33] (30%) | 0.19 [0.13, 0.47] (30%) | 0.15 [0.12, 0.31] (10%) | 0.15 [0.10, 0.22] (0%) | 0.17 [0.11, 0.25] (10%) |
| Rotation number, SSA 52-month pair | 0.22 | 0.04 | 0.24 [0.19, 0.38] | 0.26 [0.16, 0.31] | 0.34 [0.20, 0.38] | 0.19 [0.03, 0.37] | 0.23 [0.09, 0.39] | 0.21 [0.14, 0.33] |
| Best m:n sync index γ, SSA pair | 0.19 (2/9) | 0.68 | 0.23 [0.12, 0.68] (30%) | 0.19 [0.10, 0.30] (0%) | 0.17 [0.12, 0.32] (0%) | 0.22 [0.09, 0.50] (10%) | 0.18 [0.10, 0.30] (0%) | 0.21 [0.11, 0.45] (10%) |
| Plateau fraction (10-yr windows with γ > 0.9), filtered | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 | 0 |

Figure: `output/nl_frequency.png` (n φ_E − m φ_a for the nine ratios, rotation number in 10-year windows, sync-index distributions).

- **No n:m plateau in the data.** The phase differences drift for every ratio; the flattest, f_E = 1/4 cycle per year (4-year ENSO), still wanders over 5 cycles in 47 years (net drift 1.9 cycles); the others drift by 8 to 39 cycles. The rotation number moves from 0.17 (early 1990s) to 0.36 (around 2010) cycles per year, inside the range of every model. Whole-record synchronisation (0.15) is what surrogates give (p = 0.66).
- **The noise-free Duffing shows partial locking** (γ = 0.41, above its own surrogates in all 10 segments); noise 0.03 already removes most of it.
- The plateau fraction is 0 for everything: 10-year windows hold only 2 to 3 ENSO cycles and γ > 0.9 is never reached. The statistic is uninformative at this record length. The SSA-pair rotation number p = 0.04 is a single marginal result among 18 and is not taken as evidence.

## 3. Recharge oscillator with Palau sea level

- Palau h is anticorrelated with T at lag 0 (−0.37) and at h leading by 6 months (−0.19); T leads h positively by 12 to 24 months (+0.29, +0.26). Palau behaves as the west Pacific response to ENSO (discharge, then recovery), not as a precursor of the next event at these lags.
- **The LIM fails Penland's τ test.** Its L is non-oscillatory at τ0 = 1 and 3 months (decay 0.11 and 0.19 per month), oscillatory at τ0 = 6 (period 232 months) and 9 (89 months), with decay near 0.18 per month. A two-variable linear Markov model of (T, Palau h) is not consistent with the data. With τ0 = 6 the fitted oscillator is overdamped (e-folding 6 months against a 19-year period): in practice damped red noise, and it behaves like the AR(2) in every test.
- An equatorial heat content (warm water volume, 5°S to 5°N, Meinen & McPhaden 2000) is the standard h and would be the next try.

## 4. What discriminates chaos from noise, and what the data say

Calibration over the model segments (rejection rates above, or separation of the values):

| Test | Separates the chaotic Duffing from the linear nulls? | NINO1+2 sides with |
|---|---|---|
| Nonlinear prediction (NN / linear) | **yes**, cleanly (0.23 and 0.62 against 1.06 to 1.17) | linear (1.09) |
| Time reversal, raw, lag 1 | yes, noise-free only (0.62 against about 0) | linear (−0.10) |
| Bimodality (two modes, filtered) | **yes** (10 of 10 against 1 to 4 of 10) | linear (unimodal) |
| Seasonal locking of event peaks (Rayleigh R) | **yes** (0.97 to 1.00 against 0.26 to 0.53) | seasonal linear (0.58) |
| Seasonality of variance | yes, but the Duffing is too strong (3.0) or too weak with noise (1.25) | seasonal linear (1.97 against 2.00) |
| m:n sync index γ, filtered | yes, noise-free only (0.41 against 0.15 to 0.17) | linear (0.15) |
| Time reversal, filtered, lag 6 | yes, noise-free only | Duffing, partly (0.80 against 0.51) |
| Skewness, warm/cold asymmetry | **no**: no model produces it | none of the models |
| ΔBIC (non-Gaussian shape) | yes, but it detects any nonlinearity (periodic + noise too) and is somewhat liberal (AR(2): 3 of 10 segments reject) | none: the data's large value comes from skewness |
| Rotation number, its drift, plateau fraction, SSA-pair γ | **no** | all models |

Conclusions:

1. **NINO1+2 is nonlinear.** The amplitude and time asymmetry of the filtered anomaly cannot come from a linear Gaussian process, even seen through a static nonlinear transform (IAAFT). This is a firm result.
2. **But it carries no signature of low-dimensional deterministic chaos.** Every test that separates the chaotic Duffing fit from linear noise in 51-year segments (prediction, bimodality, tight seasonal locking, m:n synchronisation, raw time reversal) puts the data on the side of the linear stochastic models. The noise-free fit differs from the data on all of them in 10 of 10 segments; with noise 0.03 it still differs on prediction, bimodality and seasonal locking in 10 of 10.
3. **The fitted Duffing also misses the nonlinearity the data do have.** It makes no warm skewness and no warm/cold asymmetry, and its events are bimodal and strobe-locked where the data are unimodal, skewed and loosely locked.
4. **The seasonal linear null (periodic AR(2)) reproduces the seasonal statistics** (variance by calendar month, loose event locking, no frequency locking) but not the asymmetry. What the data need is a stochastic model with a nonlinearity that makes warm events larger and faster than cold ones (state-dependent noise, nonlinear damping or a nonlinear recharge oscillator), not low-noise chaos.
5. **For the paper:** with these tests, the claim that El Niño is the deterministic chaos of a forced double well is not supported by 51 years of NINO1+2. The Duffing can be offered as a conceptual model whose spectrum and phase portrait are consistent with the data (spectral README), but the nonlinearity tests reject its deterministic, noise-free form, and say that 51 years cannot show chaos once the noise is large enough to remove the predictability.

## 5. Next steps

- **Noise sweep of the Duffing fit** (σ from 0.03 up to where the NN/linear ratio reaches 1): find whether any noise level matches the data on prediction, bimodality and locking at once, and whether it then produces any skewness.
- **Nonlinear stochastic nulls** with the observed asymmetry: a recharge oscillator with state-dependent (multiplicative) noise or a quadratic term (Levine & Jin 2017 type), through the same tests. The test that should decide is whether they reproduce skewness, asymmetry and the filtered time reversal together.
- **Warm water volume instead of Palau** for the recharge oscillator.
- **Robustness of the asymmetry results** without 1982-83 and 1997-98 (they dominate skewness in a 612-month record).

## References

From memory, to be checked before citing: Theiler, Eubank, Longtin, Galdrikian & Farmer 1992 (Physica D), surrogate data; Schreiber & Schmitz 1996 (Phys. Rev. Lett.), IAAFT; Sugihara & May 1990 (Nature), nonlinear prediction; Kaplan & Glass 1993 / Diks et al. 1995, time-reversal tests; Zar 1999 (Biostatistical Analysis), Rayleigh test; Rosenblum, Pikovsky & Kurths 1996 and Tass et al. 1998 (Phys. Rev. Lett.), n:m phase synchronisation; Jin, Neelin & Ghil 1994 (Science) and Tziperman, Stone, Cane & Jarosh 1994 (Science), ENSO frequency locking and the devil's staircase; Stein, Timmermann, Schneider, Jin & Stuecker 2014 (J. Climate), seasonal synchronisation; Penland & Sardeshmukh 1995 (J. Climate), LIM and the τ test; Jin 1997 (J. Atmos. Sci.), recharge oscillator; Meinen & McPhaden 2000 (J. Climate), warm water volume; Burgers & Stephenson 1999 (Geophys. Res. Lett.), ENSO skewness; An & Jin 2004 (J. Climate), nonlinear dynamical heating and asymmetry; Levine & Jin 2017 (J. Atmos. Sci.), multiplicative noise in the recharge oscillator.
