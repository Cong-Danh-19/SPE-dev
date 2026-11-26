import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from functools import partial
import os
import time
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scenarios.config import SimConfig, SimMetrics
from apps.simulator_app import run_simulation, run_replications
from scenarios import analytical as ana

METRICS = ["Pblock", "X", "X_err", "R", "Wq", "W_cpu", "W_io", "p95", "p99", "p95_cpu", "p99_cpu", "L_cpu", "L_io", "L_sys", "U"]


def evaluate_config(
    exp_id: str,
    scenario: str,
    cfg: SimConfig,
    n_seeds: int = 10,
    raw_collector: Optional[List[Dict]] = None,
    *, map_runs=map,
) -> Dict:
    config = {
        "exp_id": exp_id, "scenario": scenario, "arch": cfg.arch,
        "gamma": cfg.gamma, "c": cfg.c, "K": cfg.K, "effective_K": cfg.effective_K,
        "s": cfg.s, "D": cfg.D, "kappa": cfg.kappa, "dist_cpu": cfg.dist_cpu,
        "dist_io": cfg.dist_io, "routing": cfg.routing, "closed_C": cfg.closed_C,
        "t_err": cfg.t_err, "think_time": cfg.think_time, "n_req": cfg.n_req,
        "backend_limit": cfg.backend_limit if cfg.backend_limit is not None else -1,
        "heavy_prob": cfg.heavy_prob, "heavy_mult": cfg.heavy_mult,
    }
    runs: List[SimMetrics] = []
    configs = (SimConfig(**{**cfg.__dict__, "seed": 100 + i}) for i in range(n_seeds))
    for seed, m in enumerate(map_runs(run_simulation, configs), start=100):
        runs.append(m)
        if raw_collector is not None:
            counts = ("n_done", "n_arrived", "n_rejected", "n_rejected_cpu", "n_rejected_io",
                      "n_error_events", "n_sent", "warm_reqs", "t_warm", "T_obs")
            raw_collector.append({
                **config, "seed": seed,
                **{key: getattr(m, key) for key in (*METRICS, *counts)},
            })

    row = {**config, "n_seeds": n_seeds}

    for k in METRICS:
        vals = [getattr(r, k) for r in runs]
        stat = ana.summarize_replications(vals)
        row[f"{k}_mean"] = stat["mean"]
        row[f"{k}_std"] = stat["std"]
        row[f"{k}_ci_low"] = stat["ci_low"]
        row[f"{k}_ci_high"] = stat["ci_high"]
        row[f"{k}_half_width"] = stat["half_width"]

    equivalent_poisson = cfg.arch == "shared" or cfg.routing == "random" or cfg.c == 1
    stable = cfg.K < 10**9 or cfg.gamma < cfg.c / (
        cfg.s * (cfg.kappa if cfg.arch == "partitioned" else 1.0)
    )
    row["analytical_applicable"] = (
        cfg.closed_C == 0 and cfg.dist_cpu == "exp" and cfg.backend_limit is None
        and cfg.heavy_prob == 0.0 and equivalent_poisson and stable
    )
    if row["analytical_applicable"]:
        row.update(ana.tandem_analytical(cfg.gamma, cfg.c, cfg.K, cfg.s, cfg.D, cfg.arch, cfg.kappa))
    else:
        for ak in ["ana_Pblock", "ana_X", "ana_W_cpu", "ana_Wq", "ana_R", "ana_L_cpu", "ana_L_io", "ana_L_sys", "ana_U"]:
            row[ak] = np.nan

    return row


def export_verification_table(out_dir: str, n_seeds: int = 15, *, map_runs=map):
    cases = [
        # M/M/1 (mu = 100): 3 mức tải rho = 0.4, 0.7, 0.85
        ("M/M/1", "low",  SimConfig(gamma=40,  c=1, K=10**9, s=0.01, D=0.0, n_req=40_000), ana.mm1(40, 100)),
        ("M/M/1", "mid",  SimConfig(gamma=70,  c=1, K=10**9, s=0.01, D=0.0, n_req=40_000), ana.mm1(70, 100)),
        ("M/M/1", "high", SimConfig(gamma=85,  c=1, K=10**9, s=0.01, D=0.0, n_req=45_000), ana.mm1(85, 100)),
        # M/M/1/K (mu = 100, K = 15): 3 mức tải
        ("M/M/1/K", "low",  SimConfig(gamma=60,  c=1, K=15, s=0.01, D=0.0, n_req=40_000), ana.mm1k(60, 100, 15)),
        ("M/M/1/K", "mid",  SimConfig(gamma=90,  c=1, K=15, s=0.01, D=0.0, n_req=40_000), ana.mm1k(90, 100, 15)),
        ("M/M/1/K", "high", SimConfig(gamma=110, c=1, K=15, s=0.01, D=0.0, n_req=40_000), ana.mm1k(110, 100, 15)),
        # M/M/inf (mu_io = 20): 3 mức tải
        ("M/M/inf", "low",  SimConfig(gamma=100, c=1, K=10**9, s=1e-9, D=0.05, n_req=40_000), ana.mminf(100, 20)),
        ("M/M/inf", "mid",  SimConfig(gamma=200, c=1, K=10**9, s=1e-9, D=0.05, n_req=40_000), ana.mminf(200, 20)),
        ("M/M/inf", "high", SimConfig(gamma=400, c=1, K=10**9, s=1e-9, D=0.05, n_req=40_000), ana.mminf(400, 20)),
        # M/M/c/c (c = 6, mu = 100): 3 mức tải
        ("M/M/c/c", "low",  SimConfig(gamma=300, c=6, K=6, s=0.01, D=0.0, n_req=40_000), ana.mmcc(300, 100, 6)),
        ("M/M/c/c", "mid",  SimConfig(gamma=500, c=6, K=6, s=0.01, D=0.0, n_req=40_000), ana.mmcc(500, 100, 6)),
        ("M/M/c/c", "high", SimConfig(gamma=700, c=6, K=6, s=0.01, D=0.0, n_req=40_000), ana.mmcc(700, 100, 6)),
        # M/M/c (c = 8, mu = 100): 3 mức tải
        ("M/M/c", "low",  SimConfig(gamma=400, c=8, K=10**9, s=0.01, D=0.0, n_req=40_000), ana.mmc(400, 100, 8)),
        ("M/M/c", "mid",  SimConfig(gamma=600, c=8, K=10**9, s=0.01, D=0.0, n_req=40_000), ana.mmc(600, 100, 8)),
        ("M/M/c", "high", SimConfig(gamma=720, c=8, K=10**9, s=0.01, D=0.0, n_req=45_000), ana.mmc(720, 100, 8)),
        # M/M/c/K (c = 8, K = 24, mu = 100): 3 mức tải
        ("M/M/c/K", "low",  SimConfig(gamma=600, c=8, K=24, s=0.01, D=0.0, n_req=40_000), ana.mmck(600, 100, 8, 24)),
        ("M/M/c/K", "mid",  SimConfig(gamma=750, c=8, K=24, s=0.01, D=0.0, n_req=40_000), ana.mmck(750, 100, 8, 24)),
        ("M/M/c/K", "high", SimConfig(gamma=850, c=8, K=24, s=0.01, D=0.0, n_req=40_000), ana.mmck(850, 100, 8, 24)),
    ]
    rows = []
    for name, load_lvl, cfg, th in cases:
        res = run_replications(cfg, n_seeds=n_seeds, map_runs=map_runs)
        l_key = "L_io" if name == "M/M/inf" else "L_cpu"
        w_key = "W_io" if name == "M/M/inf" else "W_cpu"

        sim_X, ana_X = res["X"]["mean"], th["X"]
        sim_W, ana_W = res[w_key]["mean"], th.get("W", cfg.s)
        sim_L, ana_L = res[l_key]["mean"], th["L"]
        sim_Pb, ana_Pb = res["Pblock"]["mean"], th.get("Pblock", 0.0)

        err_X = abs(sim_X - ana_X) / ana_X * 100.0
        err_W = abs(sim_W - ana_W) / ana_W * 100.0
        err_L = abs(sim_L - ana_L) / ana_L * 100.0
        abs_err_Pb = abs(sim_Pb - ana_Pb)
        pb_ok = (abs_err_Pb < 0.01) or (ana_Pb > 0 and abs_err_Pb / ana_Pb < 0.05)

        relative_ok = err_X < 5 and err_W < 5 and err_L < 5 and (
            abs_err_Pb / ana_Pb < 0.05 if ana_Pb else abs_err_Pb == 0
        )
        checks = (("X", ana_X), (w_key, ana_W), (l_key, ana_L), ("Pblock", ana_Pb))
        ci_ok = n_seeds >= 2 and all(
            res[key]["ci_low"] <= value <= res[key]["ci_high"] for key, value in checks
        )
        rows.append({
            "Model": name,
            "Load_Level": load_lvl,
            "gamma": cfg.gamma,
            "c": cfg.c,
            "K": cfg.K,
            "n_seeds": n_seeds,
            "Sim_X": round(sim_X, 4),
            "X_ci_low": round(res["X"]["ci_low"], 4),
            "X_ci_high": round(res["X"]["ci_high"], 4),
            "Ana_X": round(ana_X, 4),
            "Err_X_pct": round(err_X, 3),
            "Sim_W": round(sim_W, 6),
            "W_ci_low": round(res[w_key]["ci_low"], 6),
            "W_ci_high": round(res[w_key]["ci_high"], 6),
            "Ana_W": round(ana_W, 6),
            "Err_W_pct": round(err_W, 3),
            "Sim_L": round(sim_L, 4),
            "L_ci_low": round(res[l_key]["ci_low"], 4),
            "L_ci_high": round(res[l_key]["ci_high"], 4),
            "Ana_L": round(ana_L, 4),
            "Err_L_pct": round(err_L, 3),
            "Sim_Pblock": round(sim_Pb, 5),
            "Pblock_ci_low": round(res["Pblock"]["ci_low"], 5),
            "Pblock_ci_high": round(res["Pblock"]["ci_high"], 5),
            "Ana_Pblock": round(ana_Pb, 5),
            "AbsErr_Pblock": round(abs_err_Pb, 5),
            "RelErr_Pblock_pct": abs_err_Pb / ana_Pb * 100 if ana_Pb else np.nan,
            "Pass_relative_5pct": bool(relative_ok),
            "Pass_CI95": bool(ci_ok),
            "Pass_H8": bool(relative_ok and ci_ok),
            "Pass_5pct": bool((err_X < 5.0) and (err_W < 5.0) and (err_L < 5.0) and pb_ok),
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "verification_summary.csv"), index=False)
    print(df[["Model", "Load_Level", "Err_X_pct", "Err_W_pct", "Err_L_pct", "AbsErr_Pblock", "Pass_5pct", "Pass_H8"]].to_string(index=False))


def run_e1_throughput_curves(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None, *, evaluate=evaluate_config) -> pd.DataFrame:
    rows = []
    # 11 mức tải theo thiết kế §8 (bổ sung điểm 7000 trước vùng bão hòa 8000)
    gammas = [200, 500, 800, 1000, 1200, 2000, 4000, 6000, 7000, 8000, 10000]
    configs = [
        ("EventLoop_c1", "shared", 1, 100, 1.0),
        ("Bun_c8_k1.0", "partitioned", 8, 800, 1.0),
        ("Bun_c8_k1.25", "partitioned", 8, 800, 1.25),
        ("SpringLoom_c8", "shared", 8, 800, 1.0),
    ]
    for label, arch, c, K, kappa in configs:
        for g in gammas:
            n_req = 45_000 if g >= 6000 else 30_000
            cfg = SimConfig(gamma=g, c=c, K=K, s=1e-3, D=50e-3, arch=arch, kappa=kappa, n_req=n_req)
            rows.append(evaluate("E1", label, cfg, n_seeds=n_seeds, raw_collector=raw_collector))
    return pd.DataFrame(rows)


def run_e2_capacity_delay(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None, *, evaluate=evaluate_config) -> pd.DataFrame:
    rows = []
    # Nhánh 1: Quét sức chứa K (cố định c = 8)
    for K in [16, 40, 80, 200, 800]:
        for dist in ["exp", "det"]:
            for arch in ["shared", "partitioned"]:
                eff_kappa = 1.25 if arch == "partitioned" else 1.0
                cfg = SimConfig(
                    gamma=7500.0, c=8, K=K, s=1e-3, D=50e-3,
                    arch=arch, kappa=eff_kappa, dist_cpu=dist, n_req=35_000,
                )
                rows.append(evaluate("E2", f"sweep_K_{arch}_{dist}_K{K}_c8", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    # Nhánh 2: Quét số luồng c (cố định K = 200, phân phối mũ)
    for c in [1, 2, 4, 8, 16]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(
                gamma=7500.0, c=c, K=200, s=1e-3, D=50e-3,
                arch=arch, kappa=eff_kappa, dist_cpu="exp", n_req=35_000,
            )
            rows.append(evaluate("E2", f"sweep_c_{arch}_exp_K200_c{c}", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    return pd.DataFrame(rows)


def run_e3_sensitivity(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None, *, evaluate=evaluate_config) -> pd.DataFrame:
    rows = []
    # 1. Quét chi phí điều phối kappa (kèm mốc chuẩn SpringLoom kappa=1.0)
    rows.append(evaluate(
        "E3", "SpringLoom_kappa_1.0",
        SimConfig(gamma=7000.0, c=8, K=160, s=1e-3, D=50e-3, arch="shared", kappa=1.0),
        n_seeds=n_seeds, raw_collector=raw_collector,
    ))
    for kappa in [1.0, 1.25, 1.5]:
        cfg = SimConfig(gamma=7000.0, c=8, K=160, s=1e-3, D=50e-3, arch="partitioned", kappa=kappa)
        rows.append(evaluate("E3", f"Bun_kappa_{kappa}", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    # 2. Quét độ trễ I/O D (sửa kappa = 1.0 cho shared, 1.25 cho partitioned)
    for D in [10e-3, 50e-3, 200e-3]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(gamma=6000.0, c=8, K=160, s=1e-3, D=D, arch=arch, kappa=eff_kappa)
            rows.append(evaluate("E3", f"{arch}_D_{int(D*1000)}ms", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    # 3. Quét thời gian xử lý CPU s (phân biệt I/O-bound vs CPU-bound)
    for s in [0.5e-3, 1e-3, 2e-3]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(gamma=6000.0, c=8, K=160, s=s, D=50e-3, arch=arch, kappa=eff_kappa)
            rows.append(evaluate("E3", f"{arch}_s_{s*1000:.1f}ms", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    return pd.DataFrame(rows)


def run_e4_closed_loop(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None, *, evaluate=evaluate_config) -> pd.DataFrame:
    rows = []
    for C in [100, 500, 1500, 3000, 5000]:
        for label, arch, c, K_fin, kappa in [
            ("EventLoop", "shared", 1, 200, 1.0),
            ("Bun", "partitioned", 8, 800, 1.25),
            ("SpringLoom", "shared", 8, 800, 1.0),
        ]:
            # Nhánh A: K hữu hạn với n_req = max(40_000, 100 * C)
            n_req_fin = max(40_000, 100 * C)
            cfg_fin = SimConfig(
                gamma=0.0, c=c, K=K_fin, s=1e-3, D=50e-3, arch=arch, kappa=kappa,
                closed_C=C, t_err=10e-3, n_req=n_req_fin,
            )
            rows.append(evaluate("E4", f"{label}_Kfin_C{C}", cfg_fin, n_seeds=n_seeds, raw_collector=raw_collector))

            # Nhánh B: K/core = vô cực (K = 10^9)
            n_req_inf = max(40_000, 40 * C)
            cfg_inf = SimConfig(
                gamma=0.0, c=c, K=10**9, s=1e-3, D=50e-3, arch=arch, kappa=kappa,
                closed_C=C, t_err=10e-3, n_req=n_req_inf,
            )
            rows.append(evaluate("E4", f"{label}_Kinf_C{C}", cfg_inf, n_seeds=n_seeds, raw_collector=raw_collector))

    return pd.DataFrame(rows)


def run_e5_special_scenarios(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None, *, evaluate=evaluate_config) -> pd.DataFrame:
    rows = []
    for arch in ["shared", "partitioned"]:
        eff_kappa = 1.25 if arch == "partitioned" else 1.0
        cfg = SimConfig(gamma=7000.0, c=8, K=400, s=1e-3, D=50e-3, arch=arch, kappa=eff_kappa, backend_limit=300)
        rows.append(evaluate("E5", f"S8_backend_limit_{arch}", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    for label, arch, c, K in [
        ("S10_EventLoop_blocked", "shared", 1, 200),
        ("S10_SpringLoom_isolated", "shared", 8, 800),
    ]:
        cfg = SimConfig(gamma=900.0, c=c, K=K, s=1e-3, D=50e-3, arch=arch, heavy_prob=0.05, heavy_mult=20.0)
        rows.append(evaluate("E5", label, cfg, n_seeds=n_seeds, raw_collector=raw_collector))
    return pd.DataFrame(rows)


def run_e1_convergence(n_seeds: int, raw_collector: List[Dict], *, evaluate=evaluate_config) -> pd.DataFrame:
    """Compare finite windows near critical load using the same seeds."""
    return pd.DataFrame([
        evaluate("E1-convergence", "SpringLoom_c8", SimConfig(
            gamma=8000, c=8, K=800, n_req=n_req, warm_ratio=0.5,
        ), n_seeds, raw_collector)
        for n_req in (45_000, 180_000, 720_000)
    ])


def run_e6_factorial(n_seeds: int, raw_collector: List[Dict], *, evaluate=evaluate_config) -> pd.DataFrame:
    return pd.DataFrame([
        evaluate("E6", f"rho{rho}_Kcore{k}_c{c}", SimConfig(
            gamma=rho * c / 1e-3, c=c, K=k * c,
        ), n_seeds, raw_collector)
        for rho in (0.7, 1.1) for k in (10, 100) for c in (1, 8)
    ])


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("Cần một số nguyên dương")
    return value


def main():
    experiments = {
        "E1": (run_e1_throughput_curves, "e1_throughput_curves.csv"),
        "E2": (run_e2_capacity_delay, "e2_capacity_delay.csv"),
        "E3": (run_e3_sensitivity, "e3_loom_vs_bun_sensitivity.csv"),
        "E4": (run_e4_closed_loop, "e4_closed_loop.csv"),
        "E5": (run_e5_special_scenarios, "e5_special_scenarios.csv"),
        "E6": (run_e6_factorial, "e6_factorial.csv"),
        "E1-convergence": (run_e1_convergence, "e1_convergence.csv"),
    }
    parser = argparse.ArgumentParser(description="Chạy benchmark mô phỏng DES")
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--only", nargs="+", choices=["verification", *experiments])
    select.add_argument("--quick", action="store_true", help="Kiểm tra luồng CSV với ba ca nhỏ")
    parser.add_argument("--seeds", type=positive_int, help="Đổi số seed (mặc định 10; verification 15)")
    parser.add_argument("--out-dir", help="Thư mục đầu ra; mặc định results/ hoặc results-local/ cho lần chạy tùy chọn")
    parser.add_argument("--jobs", type=positive_int, default=1, help="Số seed chạy song song bằng tiến trình")
    args = parser.parse_args()
    custom = args.only or args.quick or args.seeds is not None
    out_dir = args.out_dir or ("results-local" if custom else "results")
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.perf_counter()
    raw_runs: List[Dict] = []

    with ProcessPoolExecutor(max_workers=args.jobs) if args.jobs > 1 else nullcontext() as pool:
        map_runs = pool.map if pool is not None else map
        evaluate = partial(evaluate_config, map_runs=map_runs)
        if args.quick:
            rows = [
                evaluate("quick", label, cfg, args.seeds or 1, raw_runs)
                for label, cfg in [
                    ("open", SimConfig(gamma=2000, c=4, n_req=3000)),
                    ("closed", SimConfig(gamma=0, closed_C=200, n_req=3000)),
                    ("S8", SimConfig(gamma=7000, c=8, K=80, arch="partitioned",
                                     backend_limit=100, n_req=3000)),
                ]
            ]
            pd.DataFrame(rows).to_csv(os.path.join(out_dir, "quick_summary.csv"), index=False)
        else:
            for name in dict.fromkeys(args.only or ["verification", "E1", "E2", "E3", "E4", "E5"]):
                print(f"=== Chạy {name} ===", flush=True)
                if name == "verification":
                    export_verification_table(out_dir, n_seeds=args.seeds or 15, map_runs=map_runs)
                else:
                    run, filename = experiments[name]
                    run(args.seeds or 10, raw_runs, evaluate=evaluate).to_csv(os.path.join(out_dir, filename), index=False)

    if raw_runs:
        pd.DataFrame(raw_runs).to_csv(os.path.join(out_dir, "raw_seed_runs.csv"), index=False)
    print(f"Hoàn tất sau {time.perf_counter() - t0:.1f}s; dữ liệu tại {out_dir}/.")


if __name__ == "__main__":
    main()
