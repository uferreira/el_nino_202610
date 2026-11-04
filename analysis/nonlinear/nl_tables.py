"""Markdown tables from output/nl_results.json (written by nl_tests.py)."""
import json
from pathlib import Path
R = json.loads((Path(__file__).resolve().parent / "output" / "nl_results.json").read_text())
D, PI, PF, SR, MODELS = R["data"], R["p_iaaft"], R["p_ft"], R["sur_range_iaaft"], R["models"]
NL = [("skew_raw", "Skewness, raw anomaly"), ("skew_f", "Skewness, filtered anomaly"),
      ("dbic_f", "Bimodality ΔBIC (1 vs 2 Gaussians), filtered"), ("asym_f", "Asymmetry q95/|q05|, filtered"),
      ("trev_raw1", "Time reversal, raw, lag 1"), ("trev_f6", "Time reversal, filtered, lag 6"),
      ("pred", "Prediction error NN / linear (h = 6)")]
SEAS = [("R_nino", "El Niño peak month, Rayleigh R"), ("R_nina", "La Niña trough month, Rayleigh R"),
        ("var_ratio", "Anomaly s.d. max/min over calendar months")]
FREQ = [("rho_f", "Rotation number (cycles/yr), filtered"), ("rho_sd_f", "s.d. of rotation number, filtered"),
        ("gamma_f", "Best m:n sync index, filtered"), ("plateau_f", "Plateau fraction, filtered"),
        ("rho_ssa", "Rotation number, SSA pair"), ("rho_sd_ssa", "s.d. of rotation number, SSA pair"),
        ("gamma_ssa", "Best m:n sync index, SSA pair"), ("plateau_ssa", "Plateau fraction, SSA pair")]

def f(v, n=2): return "n/a" if v is None or v != v else f"{v:.{n}f}"
def p(v): return "n/a" if v is None or v != v else ("<0.002" if v < 0.002 else f"{v:.3f}")

def data_table(rows):
    print("| Statistic | NINO1+2 | IAAFT 2.5–97.5% | p (IAAFT) | p (FT, Gaussian) |\n|---|---|---|---|---|")
    for k, lab in rows:
        lo, _, hi = SR[k]; print(f"| {lab} | **{f(D[k])}** | {f(lo)} to {f(hi)} | {p(PI[k])} | {p(PF[k])} |")

def model_table(rows):
    print("| Model | " + " | ".join(lab for _, lab in rows) + " |\n|" + "---|" * (len(rows) + 1))
    print("| **NINO1+2** | " + " | ".join(f"**{f(D[k])}** (p {p(PI[k])})" for k, _ in rows) + " |")
    for name, m in MODELS.items():
        if not m["stats"]: print(f"| {name} | " + " | ".join("n/a" for _ in rows) + " |"); continue
        c = [f"{f(m['stats'][k]['median'])} [{f(m['stats'][k]['lo'])}, {f(m['stats'][k]['hi'])}] "
             f"({100 * m['stats'][k]['reject05']:.0f}%)" for k, _ in rows]
        print(f"| {name} | " + " | ".join(c) + " |")

print(f"Window {R['window']} ({R['n_months']} months); {R['nsur_data']} surrogates for the data, "
      f"{R['nseg']} segments x {R['nsur_segment']} IAAFT surrogates per model.\n")
print("## Nonlinearity, data\n"); data_table(NL)
print("\n## Nonlinearity, models: median [min, max] over segments (share of segments rejecting the IAAFT null at 5%)\n"); model_table(NL)
print("\n## Seasonal locking, data\n")
for lab in ("nino", "nina"):
    print(f"- {'El Niño peaks' if lab == 'nino' else 'La Niña troughs'}: n = {D['n_' + lab]:.0f}, mean month {f(D['month_' + lab], 1)}, "
          f"R = {f(D['R_' + lab])}, Rayleigh p = {p(D['p_' + lab])}")
print(f"- Anomaly s.d. largest in month {D['var_peak']:.0f}, max/min = {f(D['var_ratio'])}\n")
data_table(SEAS)
print("\n## Seasonal locking, models\n"); model_table(SEAS)
print("\n| Model | El Niño peaks per segment | Mean peak month | Segments with Rayleigh p < 0.05 | Segments bimodal (filtered) |\n|---|---|---|---|---|")
for name, m in MODELS.items():
    if not m["stats"]: print(f"| {name} | n/a | n/a | n/a | n/a |"); continue
    s = m["stats"]
    print(f"| {name} | {f(s['n_nino']['median'], 0)} [{f(s['n_nino']['lo'], 0)}, {f(s['n_nino']['hi'], 0)}] | "
          f"{f(s['month_nino']['median'], 1)} | {m['rayleigh_p05_segments']} of {m['nseg_tested']} | {m['bimodal_segments']} of {m['nseg_tested']} |")
print("\n## Frequency locking, data\n")
print(f"- Best m:n (ENSO cycles : years), filtered: {D['ratio_f']}; SSA pair: {D['ratio_ssa']} (pair period {f(D['ssa_period'], 1)} months)\n")
data_table(FREQ)
print("\n## Frequency locking, models\n"); model_table(FREQ[:4]); print(); model_table(FREQ[4:])
print("\n## Model fits\n")
for name, m in MODELS.items(): print(f"- {name}: cal0 {m['cal0']}, {m['info']}")
