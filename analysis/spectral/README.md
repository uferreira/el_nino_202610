# Spectral analyses of NINO1+2: SSA and QPFT

Exploratory analyses (November 2026) asking two questions about the El Niño record:

1. Is there a better way than the Fourier low-pass to extract the El Niño signal for the phase diagram?
2. Does the record look quasi-periodic (a torus of annual cycle × ENSO), chaotic (as the fitted Duffing model is), or noise-driven?

These scripts are analyses, not part of the website build. They read `data/series/nino12.csv`, use the site's own Fourier low-pass (`enso.fourier.passa_baixa`) and the QPFT package from the Osborne collaboration (`quasiperiodic_fourier`).

Data window for everything: November 1975 to October 2026 (612 months, the site's whole-cycle rule). Monthly climatology removed for anomalies, as in the site pipeline.

## How to run

From this folder, with the repository's `.venv` (needs numpy, scipy, pandas, matplotlib):

```powershell
$env:QPFT_PATH = "C:\Users\a47575\projects\Al_nonlinear_waves\quasiperiodic_fourier"   # default if unset
..\..\.venv\Scripts\python.exe ssa_vs_fourier.py       # about 2 min (120-end hindcast)
..\..\.venv\Scripts\python.exe ssa_figure.py           # writes output/ssa_vs_fourier_nino12.png
..\..\.venv\Scripts\python.exe qpft_tests.py           # about 1 min
..\..\.venv\Scripts\python.exe duffing_calibration.py  # about 5 min
..\..\.venv\Scripts\python.exe stochastic_null.py      # about 2 min
```

| Script | What it does |
|---|---|
| `ssa_core.py` | Shared helpers: data loading, site window, climatology, SSA (embedding, eigendecomposition, reconstruction), red-noise Monte Carlo, SSA recurrent forecast |
| `ssa_vs_fourier.py` | SSA (window M = 120 months) against the Fourier low-pass; edge-revision hindcast over 120 end dates (1995 to 2024) |
| `ssa_figure.py` | The five-panel figure `output/ssa_vs_fourier_nino12.png` |
| `qpft_tests.py` | NAFF lines, harmonic test, combination tones, frequency drift between record halves |
| `duffing_calibration.py` | The same diagnostics on the Duffing El Niño fit (chaotic) and a periodic run, with and without noise |
| `stochastic_null.py` | The same diagnostics on noise-driven linear oscillators (AR(2), AR(p) by AIC) fitted to the data |

## 1. SSA against the Fourier low-pass

**As a smoother, SSA is not better; the Fourier filter is validated.** The SSA components with periods above 20 months reproduce the Fourier low-pass with correlation 0.987 and RMS difference 0.16 °C. Event peaks agree within about 0.2 °C.

**At the end of the record, neither method removes the uncertainty.** RMS revision of the estimate at a given distance from the end, when later data arrive (120 hindcast end dates):

| Months before the end | 0 | 3 | 6 | 10 | 12 |
|---|---|---|---|---|---|
| Fourier low-pass (site) | 0.50 | 0.22 | 0.23 | 0.16 | 0.14 |
| SSA + recurrent forecast extension | 0.47 | 0.22 | 0.16 | 0.16 | 0.15 |
| SSA, plain | 0.46 | 0.34 | 0.26 | 0.23 | 0.23 |

SSA with forecast extension helps only 4 to 9 months back. The latest month is uncertain by about 0.5 °C with every method: this is a property of the data. The site's 10-month provisional zone is correct.

**What SSA adds is a decomposition with a significance test** (composite AR(1) null of Allen & Smith 1996, AR(1) fitted to the residual after removing the leading pair):

| Component | Period | Variance | Above red noise (97.5%) |
|---|---|---|---|
| Quasi-quadrennial pair | 52 months | 25% | yes (also without 2025-26) |
| Quasi-biennial | 27 months | 5% | yes |
| Pair | 18 months | 8% | yes; amplitude grows after 2000 |
| Pair | 11 months | small | yes |
| Low-frequency | 6 to 13 years | 28% | no, individually |

At the end of the record SSA assigns much of the 2025-26 warming to the low-frequency components; in the 52-month mode alone the current event is still small. This is partly an edge effect.

## 2. QPFT tests on the data

NAFF on raw SST (annual cycle included), resolution 1/T = 0.020 cycles/year:

| Period (months) | 12 | 43.5 | 34.4 | 102 | 56.7 | 66.1 | 25.5 | 17.8 | 28.7 |
|---|---|---|---|---|---|---|---|---|---|
| Amplitude (°C) | 2.85 | 0.62 | 0.43 | 0.38 | 0.38 | 0.35 | 0.33 | 0.28 | 0.24 |

- **The ENSO band is several comparable lines, not one.** SSA's 52-month pair is a band.
- **Harmonic test:** f_QB − 2 f_QQ = −0.005 ± 0.028 cycles/year (0.2 σ; ±1 σ from 200 AR(1) surrogates). Consistent with the 29-month mode being the second harmonic of the 57-month mode, but 51 years cannot rule out an independent mode.
- **Combination tones:** the 18-month line (0.674 cycles/year) does not match 1 ± f_QQ or 1 ± f_QB (mismatch 0.05 to 0.10 against an uncertainty of 0.005). The 11-month line (1.111) matches 1 + 0.118 within 1 σ, the ~9-year line: a decadally modulated seasonal cycle, which a fixed climatology cannot remove.
- **Frequency drift between halves (1975-2001 vs 2001-2026):** QQ 0.206 ± 0.018 → 0.279 ± 0.026 cycles/year (58 → 43 months, 2.3 σ); QB 0.482 ± 0.017 → 0.418 ± 0.025 (25 → 29 months, 2.1 σ). For the 43-month line the drift is only 0.3 σ: which line one follows matters, again because the band is split.

## 3. Calibration: what can these diagnostics distinguish?

Same diagnostics on six independent 51-year monthly segments per model. Duffing El Niño fit coefficients (K1 = 0.1218, K3 = −0.0305, B = −0.3547, W = 2π/12, FF = −60°); FA ×1 is chaotic (λ1 > 0), FA ×1.5 periodic. Noise is additive in the velocity equation (σ in model units).

| Case | Variance outside the annual cycle | Strongest interannual line (cycles/year) | Split band | Drift ≥ 2 σ |
|---|---|---|---|---|
| **NINO1+2 data** | 0.22 | 0.28 | yes (5 lines > half the largest) | depends on the line |
| Duffing chaotic | 0.14 | 0.19 to 0.42 | yes, mostly | 2 of 6 |
| Duffing chaotic + noise 0.03 | 0.39 | 0.10 to 0.27 | yes | 1 of 6 |
| Duffing periodic | 0.00 | none | no | n/a |
| Duffing periodic + noise 0.03 | 0.01 | scattered | yes | 3 of 6 |
| Duffing periodic + noise 0.15 to 0.30 | 0.16 to 0.19 | 0.55 to 0.77, or none | rarely | 0 of 12 |
| **Linear stochastic, AR(2) fitted to data** | 0.22 | 0.11 to 0.34 | yes (3 to 8 lines) | 1 of 6 |
| Linear stochastic, AR(3) by AIC | 0.23 | 0.11 to 0.34 | yes | 1 of 6 |

## 4. Conclusions

1. **Keep the Fourier low-pass** for the site and the phase diagrams. SSA confirms it and does not fix the end of the record.
2. **The data fall inside the chaotic Duffing model's range** on every spectral diagnostic, and outside the periodic Duffing's, even with noise: noise in the periodic double well excites its 16 to 22 month resonance, not the 2 to 5 year band.
3. **But a linear noise-driven model fitted to the data passes the same tests.** An AR(2) process (spectrally almost red, peak at 0.06 cycles/year) reproduces the variance share, the split band, the dominant 3 to 9 year lines and the drift. With 51 years, the spectral and QPFT diagnostics cannot distinguish deterministic chaos from linear stochastic dynamics. This is consistent with the long-standing chaos-versus-noise debate on ENSO and must be stated in the paper.
4. **The SSA significance of the 52-month pair against red noise** is the strongest spectral evidence for an oscillation beyond red noise; it is a different null (AR(1) on the residual) from the fitted AR(2)/AR(3) above.

## 5. Next steps

- **Nonlinearity tests, not spectra, are what can separate the Duffing from linear stochastic models.** Use surrogate data (IAAFT, Theiler et al. 1992) that keep the linear spectrum exactly, with statistics that a linear Gaussian process cannot produce: skewness and bimodality of the filtered anomaly (a double well predicts bimodality), El Niño/La Niña asymmetry, time-reversal asymmetry, nonlinear prediction error in delay coordinates.
- **Stochastic recharge oscillator with a measured heat content.** Fit the two-variable recharge oscillator to NINO1+2 SST and Palau sea level (proxy for western Pacific warm water volume), run it through the same diagnostics and the nonlinearity tests.
- **If the paper keeps the chaos claim,** it should rest on the nonlinearity tests plus the Lyapunov analysis of the fitted model, with this spectral section showing that the data are consistent with the model but not uniquely so.

## References

From memory, to be checked before citing: Vautard & Ghil 1989 (Physica D); Allen & Smith 1996 (J. Climate), Monte Carlo SSA; Ghil et al. 2002 (Rev. Geophys.); Jiang, Neelin & Ghil 1995 (Climate Dynamics); Laskar 1990 (Icarus), 1993 (Physica D); Golyandina, Nekrutkin & Zhigljavsky 2001, SSA forecasting; Jin 1997 (J. Atmos. Sci.); Penland & Sardeshmukh 1995 (J. Climate); Theiler et al. 1992 (Physica D), surrogate data; Stuecker et al. 2013 (Nature Geoscience).
