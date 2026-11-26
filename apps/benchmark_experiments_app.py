import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scenarios.config import SimConfig, SimMetrics
from apps.simulator_app import run_batch_simulations
from scenarios import analytical as ana

METRICS = [
    "Pblock", "Pblock_cpu", "Pblock_io", "X", "X_err", "R", "Wq", "W_cpu",
    "p95", "p99", "p95_cpu", "p99_cpu", "L_cpu", "L_io", "L_sys", "U"
]


def _config_key(cfg: SimConfig) -> Tuple:
    """Khóa định danh duy nhất theo tham số vật lý (bỏ qua seed và n_req) để chống chạy trùng."""
    return (
        cfg.arch, cfg.routing, cfg.gamma, cfg.c, cfg.K, cfg.s, cfg.D,
        cfg.kappa, cfg.dist_cpu, cfg.dist_io, cfg.closed_C, cfg.t_err,
        cfg.think_time, cfg.backend_limit, cfg.heavy_prob, cfg.heavy_mult,
        cfg.dispatcher_type,
    )


def _summarize_runs(exp_id: str, scenario: str, cfg: SimConfig, runs: List[SimMetrics]) -> Dict:
    k_eff = (cfg.c * max(1, cfg.K // cfg.c)) if cfg.arch == "partitioned" else cfg.K
    row = {
        "exp_id": exp_id,
        "scenario": scenario,
        "arch": cfg.arch,
        "routing": cfg.routing,
        "gamma": cfg.gamma,
        "c": cfg.c,
        "K": cfg.K,
        "K_eff": k_eff,
        "s": cfg.s,
        "D": cfg.D,
        "kappa": cfg.kappa,
        "dist_cpu": cfg.dist_cpu,
        "closed_C": cfg.closed_C,
        "backend_limit": cfg.backend_limit if cfg.backend_limit is not None else -1,
        "heavy_prob": cfg.heavy_prob,
        "n_seeds": len(runs),
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

    can_use_analytical = (
        cfg.closed_C == 0
        and cfg.dist_cpu == "exp"
        and cfg.backend_limit is None
        and cfg.heavy_prob == 0.0
        and (cfg.arch == "shared" or cfg.routing == "random")
    )
    if can_use_analytical:
        row.update(ana.tandem_analytical(cfg.gamma, cfg.c, cfg.K, cfg.s, cfg.D, cfg.arch, cfg.kappa))
    else:
        for ak in ["ana_Pblock", "ana_X", "ana_W_cpu", "ana_Wq", "ana_R", "ana_L_cpu", "ana_L_io", "ana_L_sys", "U"]:
            row[ak] = np.nan

    return row


@dataclass
class _ScenarioSpec:
    exp_id: str
    scenario: str
    cfg: SimConfig
    n_seeds: int


class BatchBenchmarkPlanner:
    """Gom toàn bộ kịch bản E1-E5, loại bỏ cấu hình trùng lặp và chạy song song đa nhân CPU."""

    def __init__(self):
        self.specs: List[_ScenarioSpec] = []
        self._unique_cfgs: Dict[Tuple, Tuple[SimConfig, int]] = {}

    def add(self, exp_id: str, scenario: str, cfg: SimConfig, n_seeds: int = 8) -> None:
        key = _config_key(cfg)
        self.specs.append(_ScenarioSpec(exp_id=exp_id, scenario=scenario, cfg=cfg, n_seeds=n_seeds))
        if key not in self._unique_cfgs:
            self._unique_cfgs[key] = (cfg, n_seeds)
        else:
            prev_cfg, prev_seeds = self._unique_cfgs[key]
            best_cfg = cfg if cfg.n_req > prev_cfg.n_req else prev_cfg
            self._unique_cfgs[key] = (best_cfg, max(prev_seeds, n_seeds))

    def execute(self, max_workers: Optional[int] = None) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
        # Tạo danh sách tác vụ duy nhất (config_key, seed), xếp n_req lớn chạy trước (LPT)
        work_items: List[Tuple[Tuple, int, SimConfig]] = []
        for key, (cfg, n_seeds) in self._unique_cfgs.items():
            for i in range(n_seeds):
                seed = 100 + i
                cfg_i = SimConfig(**{**cfg.__dict__, "seed": seed})
                work_items.append((key, seed, cfg_i))

        work_items.sort(key=lambda item: item[2].n_req, reverse=True)
        print(f"Tổng tác vụ duy nhất cần mô phỏng: {len(work_items)} runs (đã loại bỏ các cấu hình trùng)...")

        metrics_list = run_batch_simulations([w[2] for w in work_items], max_workers=max_workers)
        cache: Dict[Tuple[Tuple, int], SimMetrics] = {}
        for (key, seed, cfg_i), m in zip(work_items, metrics_list):
            assert m.conservation_ok, f"Lỗi bảo toàn request tại {key}/seed={seed}"
            cache[(key, seed)] = m

        exp_rows: Dict[str, List[Dict]] = {f"E{i}": [] for i in range(1, 6)}
        raw_rows: List[Dict] = []

        for spec in self.specs:
            key = _config_key(spec.cfg)
            runs = [cache[(key, 100 + i)] for i in range(spec.n_seeds)]
            exp_rows[spec.exp_id].append(_summarize_runs(spec.exp_id, spec.scenario, spec.cfg, runs))

            for i, m in enumerate(runs):
                x_err_i = m.n_rejected / m.T_obs if m.T_obs > 0 else 0.0
                raw_rows.append({
                    "exp_id": spec.exp_id,
                    "scenario": spec.scenario,
                    "arch": spec.cfg.arch,
                    "routing": spec.cfg.routing,
                    "gamma": spec.cfg.gamma,
                    "c": spec.cfg.c,
                    "K": spec.cfg.K,
                    "K_eff": m.K_eff,
                    "s": spec.cfg.s,
                    "D": spec.cfg.D,
                    "kappa": spec.cfg.kappa,
                    "dist_cpu": spec.cfg.dist_cpu,
                    "closed_C": spec.cfg.closed_C,
                    "backend_limit": spec.cfg.backend_limit if spec.cfg.backend_limit is not None else -1,
                    "heavy_prob": spec.cfg.heavy_prob,
                    "seed": 100 + i,
                    "Pblock": m.Pblock,
                    "Pblock_cpu": m.Pblock_cpu,
                    "Pblock_io": m.Pblock_io,
                    "X": m.X,
                    "X_err": x_err_i,
                    "R": m.R,
                    "Wq": m.Wq,
                    "W_cpu": m.W_cpu,
                    "p95": m.p95,
                    "p99": m.p99,
                    "p95_cpu": m.p95_cpu,
                    "p99_cpu": m.p99_cpu,
                    "L_cpu": m.L_cpu,
                    "L_io": m.L_io,
                    "L_sys": m.L_sys,
                    "U": m.U,
                    "n_done": m.n_done,
                    "n_rejected": m.n_rejected,
                    "n_rejected_cpu": m.n_rejected_cpu,
                    "n_rejected_io": m.n_rejected_io,
                    "n_arrived": m.n_arrived,
                    "T_obs": m.T_obs,
                })

        return {k: pd.DataFrame(v) for k, v in exp_rows.items()}, pd.DataFrame(raw_rows)


def export_verification_table(out_dir: str, n_seeds: int = 8):
    cases = [
        ("M/M/1", "low",  SimConfig(gamma=40,  c=1, K=10**9, s=0.01, D=0.0, n_req=20_000), ana.mm1(40, 100)),
        ("M/M/1", "mid",  SimConfig(gamma=70,  c=1, K=10**9, s=0.01, D=0.0, n_req=20_000), ana.mm1(70, 100)),
        ("M/M/1", "high", SimConfig(gamma=85,  c=1, K=10**9, s=0.01, D=0.0, n_req=25_000), ana.mm1(85, 100)),
        ("M/M/1/K", "low",  SimConfig(gamma=60,  c=1, K=15, s=0.01, D=0.0, n_req=20_000), ana.mm1k(60, 100, 15)),
        ("M/M/1/K", "mid",  SimConfig(gamma=90,  c=1, K=15, s=0.01, D=0.0, n_req=20_000), ana.mm1k(90, 100, 15)),
        ("M/M/1/K", "high", SimConfig(gamma=110, c=1, K=15, s=0.01, D=0.0, n_req=20_000), ana.mm1k(110, 100, 15)),
        ("M/M/inf", "low",  SimConfig(gamma=100, c=1, K=10**9, s=1e-9, D=0.05, n_req=20_000), ana.mminf(100, 20)),
        ("M/M/inf", "mid",  SimConfig(gamma=200, c=1, K=10**9, s=1e-9, D=0.05, n_req=20_000), ana.mminf(200, 20)),
        ("M/M/inf", "high", SimConfig(gamma=400, c=1, K=10**9, s=1e-9, D=0.05, n_req=20_000), ana.mminf(400, 20)),
        ("M/M/c/c", "low",  SimConfig(gamma=300, c=6, K=6, s=0.01, D=0.0, n_req=20_000), ana.mmcc(300, 100, 6)),
        ("M/M/c/c", "mid",  SimConfig(gamma=500, c=6, K=6, s=0.01, D=0.0, n_req=20_000), ana.mmcc(500, 100, 6)),
        ("M/M/c/c", "high", SimConfig(gamma=700, c=6, K=6, s=0.01, D=0.0, n_req=20_000), ana.mmcc(700, 100, 6)),
        ("M/M/c", "low",  SimConfig(gamma=400, c=8, K=10**9, s=0.01, D=0.0, n_req=20_000), ana.mmc(400, 100, 8)),
        ("M/M/c", "mid",  SimConfig(gamma=600, c=8, K=10**9, s=0.01, D=0.0, n_req=20_000), ana.mmc(600, 100, 8)),
        ("M/M/c", "high", SimConfig(gamma=720, c=8, K=10**9, s=0.01, D=0.0, n_req=25_000), ana.mmc(720, 100, 8)),
        ("M/M/c/K", "low",  SimConfig(gamma=600, c=8, K=24, s=0.01, D=0.0, n_req=20_000), ana.mmck(600, 100, 8, 24)),
        ("M/M/c/K", "mid",  SimConfig(gamma=750, c=8, K=24, s=0.01, D=0.0, n_req=20_000), ana.mmck(750, 100, 8, 24)),
        ("M/M/c/K", "high", SimConfig(gamma=850, c=8, K=24, s=0.01, D=0.0, n_req=25_000), ana.mmck(850, 100, 8, 24)),
    ]

    # Gom toàn bộ 18 * n_seeds runs vào 1 lần chạy song song duy nhất (tránh spawn pool 18 lần trên Windows)
    all_cfgs = [
        SimConfig(**{**cfg.__dict__, "seed": 1 + i})
        for _, _, cfg, _ in cases
        for i in range(n_seeds)
    ]
    all_runs = run_batch_simulations(all_cfgs)
    metric_keys = [
        "Pblock", "Pblock_cpu", "Pblock_io", "X", "R", "Wq", "W_cpu",
        "p95", "p99", "p95_cpu", "p99_cpu", "L_cpu", "L_io", "L_sys", "U"
    ]

    rows = []
    for idx, (name, load_lvl, cfg, th) in enumerate(cases):
        runs = all_runs[idx * n_seeds : (idx + 1) * n_seeds]
        for r in runs:
            assert r.conservation_ok, f"Lỗi bảo toàn request ở {name}/{load_lvl}"
        res = {k: ana.summarize_replications([getattr(r, k) for r in runs]) for k in metric_keys}

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
        rel_err_Pb = (abs_err_Pb / ana_Pb * 100.0) if ana_Pb > 0 else (0.0 if abs_err_Pb == 0 else np.inf)
        pb_ok = (abs_err_Pb < 0.01) or (rel_err_Pb < 5.0)

        in_ci_X = res["X"]["ci_low"] <= ana_X <= res["X"]["ci_high"]
        in_ci_W = res[w_key]["ci_low"] <= ana_W <= res[w_key]["ci_high"]
        in_ci_L = res[l_key]["ci_low"] <= ana_L <= res[l_key]["ci_high"]
        in_ci_Pb = (ana_Pb == 0.0 and sim_Pb == 0.0) or (res["Pblock"]["ci_low"] <= ana_Pb <= res["Pblock"]["ci_high"])
        strict_ok = bool(
            (err_X < 5.0 and in_ci_X)
            and (err_W < 5.0 and in_ci_W)
            and (err_L < 5.0 and in_ci_L)
            and (rel_err_Pb < 5.0 and in_ci_Pb)
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
            "Pass_5pct": bool((err_X < 5.0) and (err_W < 5.0) and (err_L < 5.0) and pb_ok),
            "Pass_strict_CI95": strict_ok,
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "verification_summary.csv"), index=False)
    print(df[["Model", "Load_Level", "Err_X_pct", "Err_W_pct", "Err_L_pct", "AbsErr_Pblock", "Pass_5pct", "Pass_strict_CI95"]].to_string(index=False))


def schedule_e1_throughput_curves(planner: BatchBenchmarkPlanner) -> None:
    gammas = [200, 500, 800, 1000, 1200, 2000, 4000, 6000, 7000, 8000, 10000]
    configs = [
        ("EventLoop_c1", "shared", 1, 100, 1.0),
        ("Bun_c8_k1.0", "partitioned", 8, 800, 1.0),
        ("Bun_c8_k1.25", "partitioned", 8, 800, 1.25),
        ("SpringLoom_c8", "shared", 8, 800, 1.0),
    ]
    for label, arch, c, K, kappa in configs:
        cap = c / (1e-3 * (kappa if arch == "partitioned" else 1.0))
        for g in gammas:
            rho = g / cap
            if label == "SpringLoom_c8" and g == 8000:
                n_req, seeds, warm = 80_000, 10, 0.25
            elif rho >= 2.0:
                # Vùng quá tải sâu: buffer bão hòa tức thì, giảm mẫu dư thừa
                n_req, seeds, warm = 12_000, 6, 0.15
            elif rho >= 0.75:
                n_req, seeds, warm = 30_000, 10, 0.15
            else:
                n_req, seeds, warm = 20_000, 6, 0.10
            cfg = SimConfig(gamma=g, c=c, K=K, s=1e-3, D=50e-3, arch=arch, kappa=kappa, n_req=n_req, warm_ratio=warm)
            planner.add("E1", label, cfg, n_seeds=seeds)


def schedule_e2_capacity_delay(planner: BatchBenchmarkPlanner) -> None:
    for K in [16, 40, 80, 200, 800]:
        n_req = 30_000 if K == 800 else 20_000
        for dist in ["exp", "det"]:
            seeds = 6 if dist == "det" else 8
            for arch in ["shared", "partitioned"]:
                eff_kappa = 1.25 if arch == "partitioned" else 1.0
                cfg = SimConfig(
                    gamma=7500.0, c=8, K=K, s=1e-3, D=50e-3,
                    arch=arch, kappa=eff_kappa, dist_cpu=dist, n_req=n_req,
                )
                planner.add("E2", f"sweep_K_{arch}_{dist}_K{K}_c8", cfg, n_seeds=seeds)

    # Tại c=8, cấu hình (K=200, dist="exp") trùng với sweep_K -> planner tự tái sử dụng cache
    for c in [1, 2, 4, 8, 16]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(
                gamma=7500.0, c=c, K=200, s=1e-3, D=50e-3,
                arch=arch, kappa=eff_kappa, dist_cpu="exp", n_req=20_000,
            )
            planner.add("E2", f"sweep_c_{arch}_exp_K200_c{c}", cfg, n_seeds=8)


def schedule_e3_sensitivity(planner: BatchBenchmarkPlanner) -> None:
    planner.add(
        "E3", "SpringLoom_kappa_1.0",
        SimConfig(gamma=7000.0, c=8, K=160, s=1e-3, D=50e-3, arch="shared", kappa=1.0, n_req=20_000),
        n_seeds=8,
    )
    for kappa in [1.0, 1.25, 1.5]:
        cfg = SimConfig(gamma=7000.0, c=8, K=160, s=1e-3, D=50e-3, arch="partitioned", kappa=kappa, n_req=20_000)
        planner.add("E3", f"Bun_kappa_{kappa}", cfg, n_seeds=8)

    for D in [10e-3, 50e-3, 200e-3]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(gamma=6000.0, c=8, K=160, s=1e-3, D=D, arch=arch, kappa=eff_kappa, n_req=20_000)
            planner.add("E3", f"{arch}_D_{int(D*1000)}ms", cfg, n_seeds=8)

    # Điểm cơ sở (s=1ms, D=50ms) trùng với vòng lặp D phía trên -> planner tự tái sử dụng cache
    for s in [0.5e-3, 1e-3, 2e-3]:
        for arch in ["shared", "partitioned"]:
            eff_kappa = 1.25 if arch == "partitioned" else 1.0
            cfg = SimConfig(gamma=6000.0, c=8, K=160, s=s, D=50e-3, arch=arch, kappa=eff_kappa, n_req=20_000)
            planner.add("E3", f"{arch}_s_{s*1000:.1f}ms", cfg, n_seeds=8)


def schedule_e4_closed_loop(planner: BatchBenchmarkPlanner) -> None:
    for C in [100, 500, 1500, 3000, 5000]:
        # 8 vòng lặp trọn vẹn qua toàn bộ C user (đủ hội tụ steady-state ở think_time=0)
        n_req_scale = max(20_000, 8 * C)
        for label, arch, c, K_fin, kappa in [
            ("EventLoop", "shared", 1, 200, 1.0),
            ("Bun", "partitioned", 8, 800, 1.25),
            ("SpringLoom", "shared", 8, 800, 1.0),
        ]:
            cfg_fin = SimConfig(
                gamma=0.0, c=c, K=K_fin, s=1e-3, D=50e-3, arch=arch, kappa=kappa,
                closed_C=C, t_err=10e-3, n_req=n_req_scale,
            )
            planner.add("E4", f"{label}_Kfin_C{C}", cfg_fin, n_seeds=8)

            cfg_inf = SimConfig(
                gamma=0.0, c=c, K=10**9, s=1e-3, D=50e-3, arch=arch, kappa=kappa,
                closed_C=C, t_err=10e-3, n_req=n_req_scale,
            )
            planner.add("E4", f"{label}_Kinf_C{C}", cfg_inf, n_seeds=8)


def schedule_e5_special_scenarios(planner: BatchBenchmarkPlanner) -> None:
    for arch in ["shared", "partitioned"]:
        eff_kappa = 1.25 if arch == "partitioned" else 1.0
        cfg = SimConfig(gamma=7000.0, c=8, K=400, s=1e-3, D=50e-3, arch=arch, kappa=eff_kappa, backend_limit=300, n_req=25_000)
        planner.add("E5", f"S8_backend_limit_{arch}", cfg, n_seeds=10)

    for label, arch, c, K, h_prob in [
        ("S10_EventLoop_blocked", "shared", 1, 200, 0.05),
        ("S10_SpringLoom_isolated", "shared", 8, 800, 0.05),
        ("S10_EventLoop_no_heavy", "shared", 1, 200, 0.0),
        ("S10_SpringLoom_K200", "shared", 8, 200, 0.05),
    ]:
        cfg = SimConfig(gamma=900.0, c=c, K=K, s=1e-3, D=50e-3, arch=arch, heavy_prob=h_prob, heavy_mult=20.0, n_req=25_000)
        planner.add("E5", label, cfg, n_seeds=10)


def main():
    os.makedirs("results", exist_ok=True)
    t0 = time.time()

    print("=== 1. Chạy Verification Summary (3 mức tải x 6 mô hình, 1 batch đa nhân CPU) ===")
    export_verification_table("results", n_seeds=8)

    print("\n=== 2. Lập lịch & Chạy song song Thực nghiệm E1 - E5 (đã khử trùng lặp) ===")
    planner = BatchBenchmarkPlanner()
    schedule_e1_throughput_curves(planner)
    schedule_e2_capacity_delay(planner)
    schedule_e3_sensitivity(planner)
    schedule_e4_closed_loop(planner)
    schedule_e5_special_scenarios(planner)

    exp_dfs, raw_df = planner.execute()

    file_map = {
        "E1": "results/e1_throughput_curves.csv",
        "E2": "results/e2_capacity_delay.csv",
        "E3": "results/e3_loom_vs_bun_sensitivity.csv",
        "E4": "results/e4_closed_loop.csv",
        "E5": "results/e5_special_scenarios.csv",
    }
    for exp_id, path in file_map.items():
        exp_dfs[exp_id].to_csv(path, index=False)
        print(f"-> Đã xuất {path}")

    raw_df.to_csv("results/raw_seed_runs.csv", index=False)
    print("-> Đã xuất results/raw_seed_runs.csv")

    print(f"\nHoàn tất toàn bộ sau {time.time() - t0:.1f}s! Dữ liệu đã lưu tại thư mục results/.")


if __name__ == "__main__":
    main()