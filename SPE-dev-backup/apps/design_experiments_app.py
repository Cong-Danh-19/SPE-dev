"""Run the Phase 1 design matrix; keep every seed and resume interrupted runs."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import random
import tempfile
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from apps.simulator_app import run_simulation
from scenarios.analytical import summarize_replications
from scenarios.config import SimConfig

GROUPS = ("E1", "E2", "E3", "E4", "E5", "E6")
METRICS = ("Pblock", "Pblock_cpu", "Pblock_io", "X", "X_err", "R", "Wq", "W_cpu", "p95", "p99", "L_cpu", "L_io", "L_sys", "U")


def design_plan():
    """Expand the Phase 1 matrix; Bun is an additional system in E1 and E3."""
    plan = []
    systems = (("EventLoop", "shared", 1, 1.0), ("Loom", "shared", 8, 1.0),
               ("Bun", "partitioned", 8, 1.0))

    def add(group, label, cfg, rho=None, kpc=None):
        plan.append(dict(group=group, scenario=label, cfg=cfg, rho_ref=rho, K_per_core=kpc))

    for name, arch, c, kappa in systems:
        for gamma in (200, 400, 600, 800, 950, 1100, 1500, 3000, 5000, 7500, 8800):
            add("E1", f"{name}_g{gamma}", SimConfig(gamma=gamma, c=c, K=100*c, arch=arch, kappa=kappa), kpc=100)
    for name, arch, c, kappa in systems[:2]:
        for population in (100, 1500, 5000):
            for kpc in (100, None):
                count = max(30000, 100*population) if kpc else 30000
                add("E2", f"{name}_C{population}_K{kpc or 'inf'}", SimConfig(
                    gamma=0, c=c, K=100*c if kpc else 10**9, closed_C=population,
                    t_err=0.01, n_req=count, arch=arch, kappa=kappa), kpc=kpc)
    for name, arch, c, kappa in systems[:3]:
        for delay in (0.01, 0.05, 0.2):
            for service in (0.0002, 0.001, 0.005):
                add("E3", f"{name}_D{delay}_s{service}", SimConfig(
                    gamma=160, c=c, K=100*c, s=service, D=delay,
                    arch=arch, kappa=kappa), kpc=100)
    for c in (1, 4, 8):
        for kpc in (10, 100, None):
            add("E4", f"c{c}_K{kpc or 'inf'}", SimConfig(
                gamma=0.95*c/0.001, c=c, K=kpc*c if kpc else 10**9), rho=0.95, kpc=kpc)
    from apps.benchmark_experiments_app import verification_cases
    for model, load, cfg, _ in verification_cases():
        add("E5", f"{model}_{load}", SimConfig(**{**asdict(cfg), "n_req": 30000}))
    for rho in (0.7, 1.1):
        for kpc in (10, 100):
            for c in (1, 8):
                add("E6", f"rho{rho}_K{kpc}_c{c}", SimConfig(
                    gamma=rho*c/0.001, c=c, K=kpc*c), rho=rho, kpc=kpc)
    return plan


def _write_csv(path, rows):
    if not rows:
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        try:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, path)


def run_group(group, out_dir, replications):
    plans = [p for p in design_plan() if p["group"] == group]
    tasks = [(p, seed) for p in plans for seed in range(1, replications + 1)]
    random.Random(2026).shuffle(tasks)
    root = Path(__file__).resolve().parent.parent
    files = [Path(__file__).resolve(), root / "apps/simulator_app.py", root / "apps/benchmark_experiments_app.py"]
    files += sorted((root / "scenarios").rglob("*.py"))
    files += sorted((root / "bkitevsim").rglob("*.py"))
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.read_bytes())
    environment = {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "pandas")}
    digest.update(json.dumps({"group": group, "replications": replications,
                              "python": sys.version, "dependencies": environment}, sort_keys=True).encode())
    fingerprint = digest.hexdigest()
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path, raw_path = out_dir / f"design_{group}_manifest.json", out_dir / f"design_{group}_raw.csv"
    if meta_path.exists():
        if json.loads(meta_path.read_text(encoding="utf-8"))["fingerprint"] != fingerprint:
            raise ValueError("Run inputs differ from the saved checkpoint; select a new output directory")
    elif raw_path.exists():
        raise ValueError("Checkpoint has no manifest; select a new output directory")
    else:
        meta_path.write_text(json.dumps({"fingerprint": fingerprint, "group": group, "replications": replications}, indent=2), encoding="utf-8")
    rows = list(csv.DictReader(raw_path.open(encoding="utf-8", newline=""))) if raw_path.exists() else []
    completed = {(r["scenario"], int(r["seed"])) for r in rows}
    if len(completed) != len(rows):
        raise ValueError("Duplicate checkpoint rows")
    for plan, seed in tasks:
        key = (plan["scenario"], seed)
        if key in completed:
            continue
        cfg = SimConfig(**{**asdict(plan["cfg"]), "seed": seed})
        m = run_simulation(cfg)
        if not m.conservation_ok:
            raise RuntimeError(f"Request conservation failed: {key}")
        row = {"exp_id": group, "scenario": plan["scenario"], "rho_ref": plan["rho_ref"],
               "K_per_core": plan["K_per_core"], **asdict(cfg), **asdict(m),
               "X_err": m.n_rejected / m.T_obs}
        rows.append(row)
        _write_csv(raw_path, rows)
        print(f"{group}: {len(rows)}/{len(tasks)} {key}", flush=True)
    if completed - {(p["scenario"], seed) for p, seed in tasks}:
        raise ValueError("Unexpected checkpoint rows")
    frame = pd.DataFrame(rows)
    for metric in METRICS:
        frame[metric] = pd.to_numeric(frame[metric])
    summaries = []
    for scenario, grp in frame.groupby("scenario", sort=True):
        entry = next(p for p in plans if p["scenario"] == scenario)
        row = {"exp_id": group, "scenario": scenario, "rho_ref": entry["rho_ref"],
               "K_per_core": entry["K_per_core"], **{k:v for k,v in asdict(entry["cfg"]).items() if k != "seed"}, "n_seeds": len(grp)}
        for metric in METRICS:
            stat = summarize_replications(grp[metric].tolist())
            for suffix in ("mean", "std", "ci_low", "ci_high", "half_width"):
                row[f"{metric}_{suffix}"] = stat[suffix]
        summaries.append(row)
    _write_csv(out_dir / f"design_{group}_summary.csv", summaries)
    if group == "E6":
        # plotting_app accepts per-seed input and computes the factorial ANOVA.
        _write_csv(out_dir / "e6_factorial.csv", rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=GROUPS, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("results/phase1_design"))
    parser.add_argument("--replications", type=int, default=10)
    args = parser.parse_args()
    if args.replications < 2:
        parser.error("at least two replications are required")
    run_group(args.group, args.out_dir, args.replications)


if __name__ == "__main__":
    main()
