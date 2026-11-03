# Methods

Every number on the site is computed in Python from `config.yaml` and the
committed records; the pages only draw it.

## Records

| Dataset | Source | Shown as |
|---|---|---|
| NINO1+2 | NOAA CPC `sstoi.indices`, absolute SST (1975 to 1981 from the legacy file) | °C, seasonal cycle kept |
| NINO3, NINO3.4, NINO4 | NOAA CPC anomaly columns (NOAA's own climatology) | °C anomaly |
| Callao, La Libertad, Honolulu, Palau | UHSLC hourly tide gauges (Fast Delivery, extended with RAPID), monthly means needing 50% of hours | mm, seasonal cycle kept, minus the window mean |

Download and monthly averaging are ported unchanged from `el_nino`
(`src/enso/download.py`). Internal gaps of a few months are filled there and
flagged (`gap_filled` in `data/series/*.csv`).

## Filter

Ported unchanged from `el_nino` (`src/enso/fourier.py`; checked against the
Fortran loops in `tests/test_fourier.py`, and identical to the old pipeline's
output on the same input):

1. The analysis window ends at the latest month and starts in 1975, in the
   month after the end month, so it spans whole 12-month cycles.
2. For records with a seasonal cycle, the window's monthly climatology is
   removed, the anomaly is low-pass filtered (half-range sine expansion,
   HN1 = 10, HN2 = 9: full periods under about 18 to 20 months removed), and
   the climatology is added back. NOAA anomalies are filtered directly.
3. The filtered series is Fourier-interpolated to 5 points per month and
   differentiated analytically, giving dT/dt.

The time panel's bold line is the filtered anomaly from step 2, before the
climatology is added back.

## Provisional end

**`provisional_months: 10`: filtered values within 10 months of the end are
revised by 1.5 to 3 times more than older ones when new months arrive,
which matches the filter's longest half-period, HN1 = 10 months.**

The filter's detrending pins the last filtered value to the latest
observation, so the end of the record is constrained by one point instead of
by neighbours on both sides. `scripts/hindcast.py` measures the effect: it
cuts the record at 60 past end months, reruns the analysis, and compares
each run's values with what the full record now gives. RMS revision, as a
fraction of the series' standard deviation (data of November 2026):

| Months before the end | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 16 | 20 | 24 |
|---|---|---|---|---|---|---|---|---|---|---|
| NINO1+2 value | 0.25 | 0.12 | 0.10 | 0.10 | 0.09 | 0.07 | 0.05 | 0.07 | 0.04 | 0.03 |
| NINO3.4 value | 0.50 | 0.23 | 0.21 | 0.25 | 0.21 | 0.13 | 0.09 | 0.13 | 0.06 | 0.07 |
| Callao value | 0.51 | 0.30 | 0.22 | 0.23 | 0.21 | 0.16 | 0.15 | 0.16 | 0.13 | 0.14 |
| NINO3.4 rate | 1.26 | 0.94 | 0.57 | 0.30 | 0.32 | 0.38 | 0.33 | 0.14 | 0.20 | 0.10 |

Values settle to a background level (about 0.05 to 0.15; the window start
also moves with the end) after 10 to 12 months. Rates are noisier and keep
some revision a little longer, which is why the readout always calls the
latest rate provisional. The readout shows the observed value of the latest
month, not a filtered one.

## Running event

**`current_event.threshold: 1.0` °C**: the 2025-26 highlight is switched on
when the latest monthly NINO1+2 anomaly is at least 1.0 °C.

The value is borrowed from ENFEN's coastal El Niño index (ICEN; ENFEN, Nota
Técnica ENFEN 01-2012, **to verify**: citation from memory), whose categories are weak 0.4 to 1.0, moderate 1.0 to 1.7,
strong 1.7 to 3.0 and extraordinary above 3.0 °C. It is used here only as a
trigger. Our value is **not an ICEN**: the ICEN is a 3-month running mean of
ERSST anomalies of NINO1+2, while ours is a single month of NOAA OISST
(`sstoi.indices`) against the analysis window's climatology for that
calendar month, so it is never reported as an ICEN class. In September 2026
it is +4.60 °C (NOAA's own anomaly, against 1991 to 2020: +4.69 °C).

## Compare: normalisation

Each record is drawn as x_n = (x − mean) / σx and y_n = (dx/dt) / σx, with
the mean and the sample standard deviation σx of its filtered values over its
window (as in the old `compare.html`). Using σx on both axes keeps each
loop's shape, so a taller loop moves faster relative to its own typical
swing. The alternative y / σ(dx/dt) was rejected: it makes every loop equally
tall and hides that difference.

The time strip instead shows each record's filtered anomaly (step 2 of the
filter, seasonal cycle removed) divided by that anomaly's own standard
deviation, so events line up across records whatever their seasonal swing.
The model has no real calendar and is left off the time strip.

## Duffing model

X″ = K1·X + K3·X³ + FA·cos(W·t − FF) + B·X′ (right-hand side ported unchanged
from `el_nino/src/el_nino/duffing.py`), integrated with scipy RK45
(rtol 1e-6, atol 1e-8).

- Presets: the El Niño fit (the Java applet's coefficients, not re-fitted)
  and the chaotic benchmark x″ + 0.02x′ − x + x³ = 3 sin t. Five forcing
  amplitudes each (0.5 to 1.5 times the preset).
- Each run is **one long trajectory**: 100 forcing cycles discarded, then
  1500 cycles kept. The Poincaré section is that trajectory sampled once per
  forcing cycle at a chosen phase (12 phases), not a cloud of starting points.
- **Lyapunov exponents** (Benettin et al. 1980): the trajectory is integrated
  with two tangent vectors through the variational equations
  δX′ = δY, δY′ = (K1 + 3K3·X²)·δX + B·δY (RK45, rtol 1e-9), and the vectors
  are re-orthonormalised (QR) once per forcing cycle. 1500 cycles are
  integrated after the transient; the first half is discarded as well,
  because some runs stay chaotic for hundreds of cycles before settling
  (transient chaos), and the exponents are the mean over the second half.
  The standard error comes from 20 blocks. The estimate counts as converged
  when the two halves of that window agree within 6 standard errors (or the
  zero band). Built-in check: the flow's divergence is B everywhere, so
  λ1 + λ2 = B × period exactly; every run meets it to about 1e-9. A second
  check: a stable periodic orbit whose Floquet multipliers are complex
  (it spirals in) has λ1 = λ2 = B × period / 2. The El Niño fit at ×1.5
  (−2.128 = −0.35465 × 12 / 2) and the chaotic benchmark at ×1.25 and ×1.5
  (−0.063 ≈ −0.02 × 2π / 2) show exactly that.
- **Robustness**: every run is estimated a second time with another
  integrator (DOP853) at a 10 times tighter tolerance (rtol 1e-10,
  atol 1e-12), from its own trajectory. For the El Niño fit at ×1 this gives
  λ1 = +0.668 ± 0.007 per forcing cycle against +0.655 ± 0.009 with RK45
  (1.1 combined standard errors apart). Periodic runs agree to the 4th
  decimal; every run keeps its class. The page shows both values.
- **Kaplan-Yorke dimension** of the Poincaré section (a 2-D map with
  exponents λ1 ≥ λ2 per cycle): D = 1 + λ1 / |λ2| when λ1 > 0, and 0 when
  λ1 < 0 (the section is a finite set of points). Its standard error follows
  from λ1's, since λ1 + λ2 = B × period is fixed. The El Niño fit at ×1:
  D = 1.13; the chaotic benchmark at ×1: D = 1.81. A dimension close to 1
  is why the strongly damped El Niño fit's section looks like a curve.
- **Classification** by the largest exponent λ1, per forcing cycle:
  chaotic if λ1 > max(3 SE, 0.01), periodic if λ1 < −max(3 SE, 0.01),
  quasi-periodic otherwise. A separate check on the section run (points
  recurring after n cycles, n up to 24) gives the period of periodic runs;
  it agrees with the classification for every run.
- **Sweep** (not on the site yet): `scripts/lyapunov_sweep.py` repeats the
  estimate for the El Niño fit at 101 forcing amplitudes, ×0.5 to ×1.5 in
  steps of 0.01, and writes `data/model/lyapunov-sweep-alado.csv` and `.png`.
  The five published factors come back with identical values. Chaos fills
  bands at ×0.59 to ×0.65, ×0.67 to ×0.79, ×0.81 to ×0.84, ×0.86 to ×0.94
  and ×0.96 to ×1.04, separated by narrow periodic windows (single steps at
  ×0.66, ×0.80, ×0.85 and ×0.95); from ×1.05 up every run is periodic. The
  preset (×1) lies in the last band, 5% from a periodic window on either
  side, so the fit's chaos is real but not robust to a small change in FA. Where λ1 crosses zero at an
  isolated amplitude (×1.12, labelled quasi-periodic by the rule above) the
  run sits at a bifurcation of a periodic orbit, not on a torus.
- Runs are cached in `data/model/` (`python -m enso.model`). A chaotic
  trajectory depends on every last bit of floating-point arithmetic, so the
  cache, not a rerun on another machine, defines the published pages.
