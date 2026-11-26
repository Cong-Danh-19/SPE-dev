import os
import time
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from scenarios.config import SimConfig, SimMetrics
from apps.simulator_app import run_simulation, run_replications
from scenarios import analytical as ana

METRICS = ["Pblock", "X", "X_err", "R", "Wq", "W_cpu", "p95", "p99", "L_cpu", "L_io", "L_sys", "U"]


def evaluate_config(
    exp_id: str,
    scenario: str,
    cfg: SimConfig,
    n_seeds: int = 10,
    raw_collector: Optional[List[Dict]] = None,
) -> Dict:
    runs: List[SimMetrics] = []
    for i in range(n_seeds):
        cfg_i = SimConfig(**{**cfg.__dict__, "seed": 100 + i})
        m = run_simulation(cfg_i)
        assert m.conservation_ok, f"Lỗi bảo toàn request tại {exp_id}/{scenario}/seed={cfg_i.seed}"
        runs.append(m)

        if raw_collector is not None:
            x_err_i = m.n_rejected / m.T_obs if m.T_obs > 0 else 0.0
            raw_collector.append({
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
                "seed": cfg_i.seed,
                "Pblock": m.Pblock,
                "X": m.X,
                "X_err": x_err_i,
                "R": m.R,
                "Wq": m.Wq,
                "W_cpu": m.W_cpu,
                "p95": m.p95,
                "p99": m.p99,
                "L_cpu": m.L_cpu,
                "L_io": m.L_io,
                "L_sys": m.L_sys,
                "U": m.U,
                "n_done": m.n_done,
                "n_rejected": m.n_rejected,
                "T_obs": m.T_obs,
            })

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
        res = run_replications(cfg, n_seeds=n_seeds)
        l_key = "L_io" if name == "M/M/inf" else "L_cpu"
        w_key = "R" if name == "M/M/inf" else "W_cpu"

        sim_X, ana_X = res["X"]["mean"], th["X"]
        sim_W, ana_W = res[w_key]["mean"], th.get("W", cfg.s)
        sim_L, ana_L = res[l_key]["mean"], th["L"]
        sim_Pb, ana_Pb = res["Pblock"]["mean"], th.get("Pblock", 0.0)

        err_X = abs(sim_X - ana_X) / ana_X * 100.0
        err_W = abs(sim_W - ana_W) / ana_W * 100.0
        err_L = abs(sim_L - ana_L) / ana_L * 100.0
        abs_err_Pb = abs(sim_Pb - ana_Pb)
        pb_ok = (abs_err_Pb < 0.01) or (ana_Pb > 0 and abs_err_Pb / ana_Pb < 0.05)

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
            "Pass_5pct": bool((err_X < 5.0) and (err_W < 5.0) and (err_L < 5.0) and pb_ok),
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "verification_summary.csv"), index=False)
    print(df[["Model", "Load_Level", "Err_X_pct", "Err_W_pct", "Err_L_pct", "AbsErr_Pblock", "Pass_5pct"]].to_string(index=False))


def run_e1_throughput_curves(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None) -> pd.DataFrame:
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
            rows.append(evaluate_config("E1", label, cfg, n_seeds=n_seeds, raw_collector=raw_collector))
    return pd.DataFrame(rows)


def run_e2_capacity_delay(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None) -> pd.DataFrame:
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
                rows.append(evaluate_config("E2", f"sweep_K_{arch}_{dist}_K{K}_c8", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    # Nhánh 2: Quét số luồng c (cố định K = 200, phân phối mũ)
    for c in [1, 2, 4, 8, 16]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(
                gamma=7500.0, c=c, K=200, s=1e-3, D=50e-3,
                arch=arch, kappa=eff_kappa, dist_cpu="exp", n_req=35_000,
            )
            rows.append(evaluate_config("E2", f"sweep_c_{arch}_exp_K200_c{c}", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    return pd.DataFrame(rows)


def run_e3_sensitivity(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None) -> pd.DataFrame:
    rows = []
    # 1. Quét chi phí điều phối kappa (kèm mốc chuẩn SpringLoom kappa=1.0)
    rows.append(evaluate_config(
        "E3", "SpringLoom_kappa_1.0",
        SimConfig(gamma=7000.0, c=8, K=160, s=1e-3, D=50e-3, arch="shared", kappa=1.0),
        n_seeds=n_seeds, raw_collector=raw_collector,
    ))
    for kappa in [1.0, 1.25, 1.5]:
        cfg = SimConfig(gamma=7000.0, c=8, K=160, s=1e-3, D=50e-3, arch="partitioned", kappa=kappa)
        rows.append(evaluate_config("E3", f"Bun_kappa_{kappa}", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    # 2. Quét độ trễ I/O D (sửa kappa = 1.0 cho shared, 1.25 cho partitioned)
    for D in [10e-3, 50e-3, 200e-3]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(gamma=6000.0, c=8, K=160, s=1e-3, D=D, arch=arch, kappa=eff_kappa)
            rows.append(evaluate_config("E3", f"{arch}_D_{int(D*1000)}ms", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    # 3. Quét thời gian xử lý CPU s (phân biệt I/O-bound vs CPU-bound)
    for s in [0.5e-3, 1e-3, 2e-3]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(gamma=6000.0, c=8, K=160, s=s, D=50e-3, arch=arch, kappa=eff_kappa)
            rows.append(evaluate_config("E3", f"{arch}_s_{s*1000:.1f}ms", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    return pd.DataFrame(rows)


def run_e4_closed_loop(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None) -> pd.DataFrame:
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
            rows.append(evaluate_config("E4", f"{label}_Kfin_C{C}", cfg_fin, n_seeds=n_seeds, raw_collector=raw_collector))

            # Nhánh B: K/core = vô cực (K = 10^9)
            n_req_inf = max(40_000, 40 * C)
            cfg_inf = SimConfig(
                gamma=0.0, c=c, K=10**9, s=1e-3, D=50e-3, arch=arch, kappa=kappa,
                closed_C=C, t_err=10e-3, n_req=n_req_inf,
            )
            rows.append(evaluate_config("E4", f"{label}_Kinf_C{C}", cfg_inf, n_seeds=n_seeds, raw_collector=raw_collector))

    return pd.DataFrame(rows)


def run_e5_special_scenarios(n_seeds: int = 10, raw_collector: Optional[List[Dict]] = None) -> pd.DataFrame:
    rows = []
    for arch in ["shared", "partitioned"]:
        eff_kappa = 1.25 if arch == "partitioned" else 1.0
        cfg = SimConfig(gamma=7000.0, c=8, K=400, s=1e-3, D=50e-3, arch=arch, kappa=eff_kappa, backend_limit=300)
        rows.append(evaluate_config("E5", f"S8_backend_limit_{arch}", cfg, n_seeds=n_seeds, raw_collector=raw_collector))

    for label, arch, c, K in [
        ("S10_EventLoop_blocked", "shared", 1, 200),
        ("S10_SpringLoom_isolated", "shared", 8, 800),
    ]:
        cfg = SimConfig(gamma=900.0, c=c, K=K, s=1e-3, D=50e-3, arch=arch, heavy_prob=0.05, heavy_mult=20.0)
        rows.append(evaluate_config("E5", label, cfg, n_seeds=n_seeds, raw_collector=raw_collector))
    return pd.DataFrame(rows)


def main():
    os.makedirs("results", exist_ok=True)
    t0 = time.time()
    raw_runs: List[Dict] = []

    print("=== 1. Chạy Verification Summary (3 mức tải x 6 mô hình) ===")
    export_verification_table("results", n_seeds=15)

    print("\n=== 2. Chạy Thực nghiệm E1 - E5 & Lưu dữ liệu từng seed ===")
    run_e1_throughput_curves(n_seeds=10, raw_collector=raw_runs).to_csv("results/e1_throughput_curves.csv", index=False)
    print("-> Đã xuất results/e1_throughput_curves.csv")

    run_e2_capacity_delay(n_seeds=10, raw_collector=raw_runs).to_csv("results/e2_capacity_delay.csv", index=False)
    print("-> Đã xuất results/e2_capacity_delay.csv")

    run_e3_sensitivity(n_seeds=10, raw_collector=raw_runs).to_csv("results/e3_loom_vs_bun_sensitivity.csv", index=False)
    print("-> Đã xuất results/e3_loom_vs_bun_sensitivity.csv")

    run_e4_closed_loop(n_seeds=10, raw_collector=raw_runs).to_csv("results/e4_closed_loop.csv", index=False)
    print("-> Đã xuất results/e4_closed_loop.csv")

    run_e5_special_scenarios(n_seeds=10, raw_collector=raw_runs).to_csv("results/e5_special_scenarios.csv", index=False)
    print("-> Đã xuất results/e5_special_scenarios.csv")

    pd.DataFrame(raw_runs).to_csv("results/raw_seed_runs.csv", index=False)
    print("-> Đã xuất results/raw_seed_runs.csv (dữ liệu từng seed cho kiểm định ghép cặp & ANOVA)")

    print(f"\nHoàn tất toàn bộ sau {time.time() - t0:.1f}s! Dữ liệu đã lưu tại thư mục results/.")


if __name__ == "__main__":
    main()