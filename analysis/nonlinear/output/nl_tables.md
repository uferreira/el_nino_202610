Window 1975-11 to 2026-10 (612 months); 500 surrogates for the data, 10 segments x 100 IAAFT surrogates per model.

## Nonlinearity, data

| Statistic | NINO1+2 | IAAFT 2.5–97.5% | p (IAAFT) | p (FT, Gaussian) |
|---|---|---|---|---|
| Skewness, raw anomaly | **1.36** | 1.36 to 1.36 | 1.000 | 0.004 |
| Skewness, filtered anomaly | **1.66** | 0.57 to 1.39 | 0.004 | 0.004 |
| Bimodality ΔBIC (1 vs 2 Gaussians), filtered | **212.95** | 28.87 to 146.37 | <0.002 | <0.002 |
| Asymmetry q95/|q05|, filtered | **2.86** | 1.35 to 2.37 | 0.004 | 0.004 |
| Time reversal, raw, lag 1 | **-0.10** | -0.48 to 0.46 | 0.707 | 0.271 |
| Time reversal, filtered, lag 6 | **0.80** | -0.40 to 0.42 | 0.004 | 0.004 |
| Prediction error NN / linear (h = 6) | **1.09** | 1.05 to 1.14 | 0.333 | 0.275 |

## Nonlinearity, models: median [min, max] over segments (share of segments rejecting the IAAFT null at 5%)

| Model | Skewness, raw anomaly | Skewness, filtered anomaly | Bimodality ΔBIC (1 vs 2 Gaussians), filtered | Asymmetry q95/|q05|, filtered | Time reversal, raw, lag 1 | Time reversal, filtered, lag 6 | Prediction error NN / linear (h = 6) |
|---|---|---|---|---|---|---|---|
| **NINO1+2** | **1.36** (p 1.000) | **1.66** (p 0.004) | **212.95** (p <0.002) | **2.86** (p 0.004) | **-0.10** (p 0.707) | **0.80** (p 0.004) | **1.09** (p 0.333) |
| Duffing chaotic (FA x1) | -0.05 [-0.21, 0.40] (0%) | 0.09 [-0.06, 0.48] (0%) | 126.50 [87.01, 210.00] (100%) | 1.13 [0.90, 1.94] (20%) | 0.62 [0.31, 0.78] (100%) | 0.51 [0.35, 0.81] (100%) | 0.23 [0.19, 0.25] (100%) |
| Duffing chaotic + noise 0.03 | 0.23 [-0.56, 0.64] (0%) | 0.23 [-0.61, 0.66] (0%) | 138.06 [43.68, 230.85] (100%) | 1.41 [0.39, 1.92] (40%) | -0.07 [-0.24, 0.21] (0%) | -0.10 [-0.36, 0.41] (30%) | 0.62 [0.55, 0.74] (100%) |
| Duffing periodic (FA x1.5) | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| Duffing periodic + noise 0.15 | 0.08 [-0.07, 0.16] (0%) | 0.54 [-0.33, 1.39] (10%) | 125.56 [44.61, 271.12] (90%) | 1.02 [0.72, 2.19] (40%) | -0.00 [-0.27, 0.06] (0%) | 0.02 [-0.64, 0.33] (10%) | 1.03 [0.99, 1.09] (80%) |
| AR(2) fitted | 0.12 [-0.24, 0.24] (0%) | 0.16 [-0.28, 0.41] (0%) | 1.60 [-13.95, 58.75] (30%) | 1.17 [0.76, 1.72] (10%) | -0.02 [-0.23, 0.07] (10%) | -0.12 [-0.30, 0.40] (0%) | 1.11 [1.07, 1.16] (10%) |
| Seasonal linear PAR(2) | -0.04 [-0.40, 0.42] (0%) | 0.06 [-0.53, 0.48] (0%) | -0.09 [-18.46, 22.56] (0%) | 0.98 [0.68, 1.17] (0%) | 0.03 [-0.14, 0.15] (0%) | -0.00 [-0.48, 0.69] (10%) | 1.12 [1.06, 1.17] (0%) |
| Recharge oscillator (LIM, T + Palau h, tau0 6) | -0.03 [-0.38, 0.14] (10%) | -0.02 [-0.76, 0.31] (10%) | -7.13 [-18.41, 50.12] (20%) | 0.99 [0.61, 1.27] (10%) | -0.06 [-0.30, 0.20] (10%) | 0.01 [-0.15, 0.16] (0%) | 1.09 [1.06, 1.13] (10%) |

## Seasonal locking, data

- El Niño peaks: n = 5, mean month 8.3, R = 0.58, Rayleigh p = 0.189
- La Niña troughs: n = 6, mean month 7.0, R = 0.46, Rayleigh p = 0.300
- Anomaly s.d. largest in month 7, max/min = 1.97

| Statistic | NINO1+2 | IAAFT 2.5–97.5% | p (IAAFT) | p (FT, Gaussian) |
|---|---|---|---|---|
| El Niño peak month, Rayleigh R | **0.58** | 0.07 to 0.61 | 0.046 | 0.036 |
| La Niña trough month, Rayleigh R | **0.46** | 0.06 to 0.66 | 0.250 | 0.130 |
| Anomaly s.d. max/min over calendar months | **1.97** | 1.21 to 1.82 | 0.008 | <0.002 |

## Seasonal locking, models

| Model | El Niño peak month, Rayleigh R | La Niña trough month, Rayleigh R | Anomaly s.d. max/min over calendar months |
|---|---|---|---|
| **NINO1+2** | **0.58** (p 0.046) | **0.46** (p 0.250) | **1.97** (p 0.008) |
| Duffing chaotic (FA x1) | 1.00 [0.99, 1.00] (100%) | 0.97 [0.97, 0.97] (100%) | 3.02 [2.70, 3.38] (100%) |
| Duffing chaotic + noise 0.03 | 0.97 [0.95, 0.98] (100%) | 0.97 [0.93, 0.98] (100%) | 1.25 [1.23, 1.30] (100%) |
| Duffing periodic (FA x1.5) | n/a | n/a | n/a |
| Duffing periodic + noise 0.15 | 0.78 [0.28, 0.99] (80%) | 0.43 [0.14, 0.73] (50%) | 2.30 [1.75, 2.68] (80%) |
| AR(2) fitted | 0.33 [0.15, 0.42] (0%) | 0.44 [0.07, 0.59] (0%) | 1.29 [1.18, 1.42] (0%) |
| Seasonal linear PAR(2) | 0.53 [0.25, 0.86] (40%) | 0.43 [0.15, 0.73] (20%) | 2.00 [1.64, 2.11] (100%) |
| Recharge oscillator (LIM, T + Palau h, tau0 6) | 0.26 [0.11, 0.35] (0%) | 0.18 [0.09, 0.38] (0%) | 1.28 [1.16, 1.50] (0%) |

| Model | El Niño peaks per segment | Mean peak month | Segments with Rayleigh p < 0.05 | Segments bimodal (filtered) |
|---|---|---|---|---|
| Duffing chaotic (FA x1) | 10 [6, 11] | 8.0 | 10 of 10 | 10 of 10 |
| Duffing chaotic + noise 0.03 | 8 [4, 11] | 1.3 | 10 of 10 | 10 of 10 |
| Duffing periodic (FA x1.5) | n/a | n/a | n/a | n/a |
| Duffing periodic + noise 0.15 | 7 [6, 9] | 8.2 | 7 of 10 | 0 of 10 |
| AR(2) fitted | 8 [6, 10] | 6.9 | 0 of 10 | 4 of 10 |
| Seasonal linear PAR(2) | 8 [5, 10] | 9.3 | 4 of 10 | 2 of 10 |
| Recharge oscillator (LIM, T + Palau h, tau0 6) | 10 [6, 11] | 9.1 | 0 of 10 | 1 of 10 |

## Frequency locking, data

- Best m:n (ENSO cycles : years), filtered: 7:2; SSA pair: 9:2 (pair period 51.7 months)

| Statistic | NINO1+2 | IAAFT 2.5–97.5% | p (IAAFT) | p (FT, Gaussian) |
|---|---|---|---|---|
| Rotation number (cycles/yr), filtered | **0.25** | 0.20 to 0.32 | 0.818 | 0.615 |
| s.d. of rotation number, filtered | **0.05** | 0.03 to 0.10 | 0.543 | 0.491 |
| Best m:n sync index, filtered | **0.15** | 0.10 to 0.28 | 0.661 | 0.687 |
| Plateau fraction, filtered | **0.00** | 0.00 to 0.00 | 1.000 | 1.000 |
| Rotation number, SSA pair | **0.22** | 0.22 to 0.28 | 0.040 | 0.076 |
| s.d. of rotation number, SSA pair | **0.02** | 0.01 to 0.04 | 0.535 | 0.689 |
| Best m:n sync index, SSA pair | **0.19** | 0.10 to 0.54 | 0.679 | 0.671 |
| Plateau fraction, SSA pair | **0.00** | 0.00 to 0.28 | 1.000 | 1.000 |

## Frequency locking, models

| Model | Rotation number (cycles/yr), filtered | s.d. of rotation number, filtered | Best m:n sync index, filtered | Plateau fraction, filtered |
|---|---|---|---|---|
| **NINO1+2** | **0.25** (p 0.818) | **0.05** (p 0.543) | **0.15** (p 0.661) | **0.00** (p 1.000) |
| Duffing chaotic (FA x1) | 0.31 [0.22, 0.35] (0%) | 0.06 [0.04, 0.10] (0%) | 0.41 [0.30, 0.47] (100%) | 0.00 [0.00, 0.00] (0%) |
| Duffing chaotic + noise 0.03 | 0.16 [0.09, 0.18] (40%) | 0.07 [0.04, 0.11] (0%) | 0.21 [0.16, 0.33] (30%) | 0.00 [0.00, 0.00] (0%) |
| Duffing periodic (FA x1.5) | n/a | n/a | n/a | n/a |
| Duffing periodic + noise 0.15 | 0.35 [0.24, 0.43] (0%) | 0.08 [0.05, 0.12] (0%) | 0.19 [0.13, 0.47] (30%) | 0.00 [0.00, 0.00] (0%) |
| AR(2) fitted | 0.20 [0.14, 0.29] (10%) | 0.08 [0.07, 0.11] (0%) | 0.15 [0.12, 0.31] (10%) | 0.00 [0.00, 0.00] (0%) |
| Seasonal linear PAR(2) | 0.22 [0.17, 0.25] (0%) | 0.07 [0.06, 0.10] (0%) | 0.15 [0.10, 0.22] (0%) | 0.00 [0.00, 0.00] (0%) |
| Recharge oscillator (LIM, T + Palau h, tau0 6) | 0.22 [0.16, 0.29] (10%) | 0.07 [0.05, 0.13] (0%) | 0.17 [0.11, 0.25] (10%) | 0.00 [0.00, 0.00] (0%) |

| Model | Rotation number, SSA pair | s.d. of rotation number, SSA pair | Best m:n sync index, SSA pair | Plateau fraction, SSA pair |
|---|---|---|---|---|
| **NINO1+2** | **0.22** (p 0.040) | **0.02** (p 0.535) | **0.19** (p 0.679) | **0.00** (p 1.000) |
| Duffing chaotic (FA x1) | 0.24 [0.19, 0.38] (0%) | 0.02 [0.01, 0.05] (0%) | 0.23 [0.12, 0.68] (30%) | 0.00 [0.00, 0.57] (10%) |
| Duffing chaotic + noise 0.03 | 0.26 [0.16, 0.31] (10%) | 0.02 [0.01, 0.13] (30%) | 0.19 [0.10, 0.30] (0%) | 0.00 [0.00, 0.17] (0%) |
| Duffing periodic (FA x1.5) | n/a | n/a | n/a | n/a |
| Duffing periodic + noise 0.15 | 0.34 [0.20, 0.38] (0%) | 0.04 [0.02, 0.09] (0%) | 0.17 [0.12, 0.32] (0%) | 0.00 [0.00, 0.15] (0%) |
| AR(2) fitted | 0.19 [0.03, 0.37] (20%) | 0.03 [0.02, 0.04] (0%) | 0.22 [0.09, 0.50] (10%) | 0.00 [0.00, 0.35] (10%) |
| Seasonal linear PAR(2) | 0.23 [0.09, 0.39] (0%) | 0.02 [0.01, 0.08] (10%) | 0.18 [0.10, 0.30] (0%) | 0.00 [0.00, 0.08] (0%) |
| Recharge oscillator (LIM, T + Palau h, tau0 6) | 0.21 [0.14, 0.33] (0%) | 0.03 [0.02, 0.04] (0%) | 0.21 [0.11, 0.45] (10%) | 0.00 [0.00, 0.25] (0%) |

## Model fits

- Duffing chaotic (FA x1): cal0 11, {'FA_factor': 1.0, 'sigma': 0.0}
- Duffing chaotic + noise 0.03: cal0 11, {'FA_factor': 1.0, 'sigma': 0.03}
- Duffing periodic (FA x1.5): cal0 11, {'FA_factor': 1.5, 'sigma': 0.0}
- Duffing periodic + noise 0.15: cal0 0, {'FA_factor': 1.5, 'sigma': 0.15}
- AR(2) fitted: cal0 10, {'phi': [1.017032800696454, -0.14364561120980246], 'sigma': 0.49106887065384314}
- Seasonal linear PAR(2): cal0 10, {'a1': [0.714, 0.869, 1.121, 0.932, 1.024, 1.105, 1.375, 1.093, 1.231, 1.302, 0.981, 0.893], 'a2': [-0.072, -0.167, -0.169, 0.091, -0.024, -0.126, -0.422, -0.218, -0.259, -0.33, -0.077, -0.02], 's': [0.349, 0.431, 0.473, 0.594, 0.524, 0.449, 0.377, 0.307, 0.35, 0.415, 0.405, 0.365], 'floquet': {'abs': [0.183, 0.0], 'arg_deg': [0.0, 180.0]}}
- Recharge oscillator (LIM, T + Palau h, tau0 6): cal0 10, {'corr_h_t_with_T_t_plus_k': {'-24': 0.26, '-12': 0.29, '-6': -0.05, '0': -0.37, '6': -0.19, '12': -0.09, '24': 0.11}, 'tau_test': {'1': {'decay_per_month': [0.106, 0.186], 'period_months': None}, '3': {'decay_per_month': [0.131, 0.215], 'period_months': None}, '6': {'decay_per_month': [0.175, 0.175], 'period_months': 231.7}, '9': {'decay_per_month': [0.178, 0.178], 'period_months': 89.2}}, 'tau0_used': 6}
