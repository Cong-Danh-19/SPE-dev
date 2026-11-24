import os
import time
from typing import Dict, List
import pandas as pd
import numpy as np
from scenarios.config import SimConfig, SimMetrics
from apps.simulator_app import run_simulation, run_replications
from scenarios import analytical as ana

METRICS = ["Pblock", "X", "X_err", "R", "Wq", "W_cpu", "p95", "p99", "L_cpu", "L_io", "L_sys", "U"]


def evaluate_config(exp_id: str, scenario: str, cfg: SimConfig, n_seeds: int = 10) -> Dict:
    runs: List[SimMetrics] = []
    for i in range(n_seeds):
        cfg_i = SimConfig(**{**cfg.__dict__, "seed": 100 + i})
        m = run_simulation(cfg_i)
        assert m.conservation_ok, f"Lỗi bảo toàn request tại {exp_id}/{scenario}/seed={cfg_i.seed}"
        runs.append(m)

    row = {
        "exp_id": exp_id,
        "scenario": scenario,
        "arch": cfg.arch,
        "gamma": cfg.gamma,
        "c": cfg.c,
        "K": cfg.K,
        "s": cfg.s,
        "D": cfg.D,
        "kappa": cfg.kappa,
        "dist_cpu": cfg.dist_cpu,
        "closed_C": cfg.closed_C,
        "backend_limit": cfg.backend_limit if cfg.backend_limit is not None else -1,
        "heavy_prob": cfg.heavy_prob,
        "n_seeds": n_seeds,
    }

    for k in METRICS:
        if k == "X_err":
            vals = [r.n_rejected / r.T_obs if r.T_obs > 0 else 0.0 for r in runs]
        else:
            vals = [getattr(r, k) for r in runs]
        stat = ana.summarize_replications(vals)
        row[f"{k}_mean"] = stat["mean"]
        row[f"{k}_std"] = stat["std"]
        row[f"{k}_ci_low"] = stat["ci_low"]
        row[f"{k}_ci_high"] = stat["ci_high"]
        row[f"{k}_half_width"] = stat["half_width"]

    if cfg.closed_C == 0 and cfg.dist_cpu == "exp" and cfg.backend_limit is None and cfg.heavy_prob == 0.0:
        row.update(ana.tandem_analytical(cfg.gamma, cfg.c, cfg.K, cfg.s, cfg.D, cfg.arch, cfg.kappa))
    else:
        for ak in ["ana_Pblock", "ana_X", "ana_W_cpu", "ana_Wq", "ana_R", "ana_L_cpu", "ana_L_io", "ana_L_sys", "ana_U"]:
            row[ak] = np.nan

    return row


def export_verification_table(out_dir: str, n_seeds: int = 15):
    cases = [
        ("M/M/1", SimConfig(gamma=80, c=1, K=10**9, s=0.01, D=0.0, n_req=40_000), ana.mm1(80, 100)),
        ("M/M/1/K", SimConfig(gamma=110, c=1, K=15, s=0.01, D=0.0, n_req=40_000), ana.mm1k(110, 100, 15)),
        ("M/M/inf", SimConfig(gamma=200, c=1, K=10**9, s=1e-9, D=0.05, n_req=40_000), ana.mminf(200, 20)),
        ("M/M/c/c", SimConfig(gamma=500, c=6, K=6, s=0.01, D=0.0, n_req=40_000), ana.mmcc(500, 100, 6)),
        ("M/M/c", SimConfig(gamma=600, c=8, K=10**9, s=0.01, D=0.0, n_req=40_000), ana.mmc(600, 100, 8)),
        ("M/M/c/K", SimConfig(gamma=850, c=8, K=24, s=0.01, D=0.0, n_req=40_000), ana.mmck(850, 100, 8, 24)),
    ]
    rows = []
    for name, cfg, th in cases:
        res = run_replications(cfg, n_seeds=n_seeds)
        metric_key = "L_io" if name == "M/M/inf" else "L_cpu"
        sim_L = res[metric_key]["mean"]
        ana_L = th["L"]
        err_L = abs(sim_L - ana_L) / ana_L * 100.0
        rows.append({
            "Model": name,
            "n_seeds": n_seeds,
            "Sim_X": round(res["X"]["mean"], 4),
            "Ana_X": round(th["X"], 4),
            "Err_X_pct": round(abs(res["X"]["mean"] - th["X"]) / th["X"] * 100.0, 3),
            "Sim_Pblock": round(res["Pblock"]["mean"], 5),
            "Ana_Pblock": round(th["Pblock"], 5),
            "Sim_L": round(sim_L, 4),
            "Ana_L": round(ana_L, 4),
            "Err_L_pct": round(err_L, 3),
            "Pass_5pct": err_L < 5.0,
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "verification_summary.csv"), index=False)
    print(df.to_string(index=False))


def run_e1_throughput_curves(n_seeds: int = 10) -> pd.DataFrame:
    rows = []
    gammas = [200, 500, 800, 1000, 1200, 2000, 4000, 6000, 8000, 10000]
    configs = [
        ("EventLoop_c1", "shared", 1, 100, 1.0),
        ("Bun_c8_k1.0", "partitioned", 8, 800, 1.0),
        ("Bun_c8_k1.25", "partitioned", 8, 800, 1.25),
        ("SpringLoom_c8", "shared", 8, 800, 1.0),
    ]
    for label, arch, c, K, kappa in configs:
        for g in gammas:
            cfg = SimConfig(gamma=g, c=c, K=K, s=1e-3, D=50e-3, arch=arch, kappa=kappa, n_req=30_000)
            rows.append(evaluate_config("E1", label, cfg, n_seeds=n_seeds))
    return pd.DataFrame(rows)


def run_e2_capacity_delay(n_seeds: int = 10) -> pd.DataFrame:
    rows = []
    for K in [16, 40, 80, 200, 800]:
        for dist in ["exp", "det"]:
            for arch in ["shared", "partitioned"]:
                cfg = SimConfig(gamma=7500.0, c=8, K=K, s=1e-3, D=50e-3, arch=arch, dist_cpu=dist, n_req=35_000)
                rows.append(evaluate_config("E2", f"{arch}_{dist}_K{K}", cfg, n_seeds=n_seeds))
    return pd.DataFrame(rows)


def run_e3_sensitivity(n_seeds: int = 10) -> pd.DataFrame:
    rows = []
    for kappa in [1.0, 1.25, 1.5]:
        cfg = SimConfig(gamma=7000.0, c=8, K=160, s=1e-3, D=50e-3, arch="partitioned", kappa=kappa)
        rows.append(evaluate_config("E3", f"Bun_kappa_{kappa}", cfg, n_seeds=n_seeds))
    for D in [10e-3, 50e-3, 200e-3]:
        for arch in ["shared", "partitioned"]:
            cfg = SimConfig(gamma=6000.0, c=8, K=160, s=1e-3, D=D, arch=arch, kappa=1.25)
            rows.append(evaluate_config("E3", f"{arch}_D_{int(D*1000)}ms", cfg, n_seeds=n_seeds))
    return pd.DataFrame(rows)


def run_e4_closed_loop(n_seeds: int = 10) -> pd.DataFrame:
    rows = []
    for C in [100, 500, 1500, 3000, 5000]:
        for label, arch, c, K, kappa in [
            ("EventLoop", "shared", 1, 200, 1.0),
            ("Bun", "partitioned", 8, 800, 1.25),
            ("SpringLoom", "shared", 8, 800, 1.0),
        ]:
            cfg = SimConfig(gamma=0.0, c=c, K=K, s=1e-3, D=50e-3, arch=arch, kappa=kappa,
                            closed_C=C, t_err=10e-3, n_req=40_000)
            rows.append(evaluate_config("E4", f"{label}_C{C}", cfg, n_seeds=n_seeds))
    return pd.DataFrame(rows)


def run_e5_special_scenarios(n_seeds: int = 10) -> pd.DataFrame:
    rows = []
    for arch in ["shared", "partitioned"]:
        cfg = SimConfig(gamma=7000.0, c=8, K=400, s=1e-3, D=50e-3, arch=arch, backend_limit=300)
        rows.append(evaluate_config("E5", f"S8_backend_limit_{arch}", cfg, n_seeds=n_seeds))

    for label, arch, c, K in [
        ("S10_EventLoop_blocked", "shared", 1, 200),
        ("S10_SpringLoom_isolated", "shared", 8, 800),
    ]:
        cfg = SimConfig(gamma=900.0, c=c, K=K, s=1e-3, D=50e-3, arch=arch, heavy_prob=0.05, heavy_mult=20.0)
        rows.append(evaluate_config("E5", label, cfg, n_seeds=n_seeds))
    return pd.DataFrame(rows)


def main():
    os.makedirs("results", exist_ok=True)
    t0 = time.time()

    print("=== 1. Chạy Verification Summary ===")
    export_verification_table("results", n_seeds=15)

    print("\n=== 2. Chạy Thực nghiệm E1 - E5 ===")
    run_e1_throughput_curves(n_seeds=10).to_csv("results/e1_throughput_curves.csv", index=False)
    run_e2_capacity_delay(n_seeds=10).to_csv("results/e2_capacity_delay.csv", index=False)
    run_e3_sensitivity(n_seeds=10).to_csv("results/e3_loom_vs_bun_sensitivity.csv", index=False)
    run_e4_closed_loop(n_seeds=10).to_csv("results/e4_closed_loop.csv", index=False)
    run_e5_special_scenarios(n_seeds=10).to_csv("results/e5_special_scenarios.csv", index=False)

    print(f"\nHoàn tất toàn bộ sau {time.time() - t0:.1f}s! Dữ liệu đã lưu tại thư mục results/.")


if __name__ == "__main__":
    main()
