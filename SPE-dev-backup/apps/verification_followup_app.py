"""Recheck E5 misses with a longer observation and independent seeds."""
from dataclasses import replace
from pathlib import Path
import gc

import pandas as pd
from scipy.stats import t

from apps.benchmark_experiments_app import verification_cases
from apps.simulator_app import run_simulation

ROOT = Path(__file__).resolve().parents[1] / "results" / "phase1_design"


def verification_row(model, load, metric, samples, theory):
    mean, sem = samples.mean(), samples.sem()
    width = t.ppf(.975, len(samples) - 1) * sem
    diff = abs(mean - theory)
    rare = metric == "Pblock" and 0 < theory < .01
    within_tol = diff < .01 if rare else (diff < .05 * theory if theory else mean == 0)
    within_ci = mean - width <= theory <= mean + width
    return dict(model=model, load=load, metric=metric, mean=mean, theory=theory,
                low=mean-width, high=mean+width, absolute_error=diff,
                within_ci=within_ci, within_tolerance=within_tol, pass_design=within_tol and within_ci)


def compare(frame):
    rows = []
    for model, load, _, ref in verification_cases():
        seed_rows = frame[frame.scenario == model + "_" + load]
        if seed_rows.empty:
            continue
        for metric, col in (("X", "X"), ("L", "L_io" if model == "M/M/inf" else "L_cpu"),
                            ("W", "R" if model == "M/M/inf" else "W_cpu"), ("Pblock", "Pblock")):
            rows.append(verification_row(model, load, metric, seed_rows[col], ref[metric]))
    return pd.DataFrame(rows)


def main():
    official = pd.read_csv(ROOT / "design_E5_raw.csv", float_precision="round_trip")
    baseline = compare(official)
    rows = []
    for model, load, cfg, _ in verification_cases():
        part = baseline[(baseline.model == model) & (baseline.load == load)]
        if part.pass_design.all():
            continue
        for seed in range(101, 111):
            m = run_simulation(replace(cfg, seed=seed, n_req=120000, adaptive_warmup=False))
            if not m.conservation_ok:
                raise RuntimeError(f"Failed conservation: {model}, {load}, {seed}")
            rows.append(dict(scenario=model+"_"+load, seed=seed, n_req=120000, X=m.X,
                             L_io=m.L_io, L_cpu=m.L_cpu, R=m.R, W_cpu=m.W_cpu, Pblock=m.Pblock))
            gc.collect()
        print(model, load, flush=True)
    columns = ["scenario", "seed", "n_req", "X", "L_io", "L_cpu", "R", "W_cpu", "Pblock"]
    pd.DataFrame(rows, columns=columns).to_csv(ROOT / "verification_followup_raw.csv", index=False)


if __name__ == "__main__":
    main()
