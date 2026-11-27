import asyncio
import concurrent.futures
from typing import Dict, List
import numpy as np
from bkitevsim.core import Simulation, SimulationOptions
from scenarios.config import (
    SimConfig, SimMetrics, SRC_ID, DISP_ID, IO_ID, SINK_ID, WORKER_BASE_ID
)
from scenarios.async_runtime_lps import (
    SourceLP, SharedDispatcherLP, PartitionedDispatcherLP, WorkerLP, IoLP, SinkLP
)
from scenarios.analytical import summarize_replications

MODELS = {
    "SourceLP": SourceLP,
    "SharedDispatcherLP": SharedDispatcherLP,
    "PartitionedDispatcherLP": PartitionedDispatcherLP,
    "WorkerLP": WorkerLP,
    "IoLP": IoLP,
    "SinkLP": SinkLP,
}


def _run_in_thread(sim: Simulation) -> dict:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return sim.run()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(sim.run).result()


def _time_average(trace: list, col: int, t_warm: float, t_stop: float) -> float:
    T = t_stop - t_warm
    if T <= 0 or not trace:
        return 0.0
    arr = np.asarray(trace, dtype=float)
    t = arr[:, 0]
    v = arr[:, col]
    t1 = np.minimum(np.append(t[1:], t_stop), t_stop)
    t0 = np.maximum(t, t_warm)
    return float(np.sum(v * np.clip(t1 - t0, 0.0, None)) / T)


def run_simulation(cfg: SimConfig) -> SimMetrics:
    """Chạy một lượt mô phỏng DES hoàn chỉnh và trả về các metric sau warm-up."""
    if cfg.arch not in ("shared", "partitioned") or cfg.routing not in ("random", "rr"):
        raise ValueError("Invalid architecture or routing")
    if cfg.c < 1 or cfg.K < 1 or (cfg.arch == "partitioned" and cfg.K < cfg.c) or cfg.s <= 0 or cfg.kappa <= 0 or cfg.D < 0:
        raise ValueError("Invalid capacity or service time")
    if cfg.n_req < 2 or not 0 <= cfg.warm_ratio < 1 or cfg.closed_C < 0:
        raise ValueError("Invalid request count, warm-up or closed population")
    if cfg.closed_C == 0 and cfg.gamma <= 0:
        raise ValueError("Open-loop arrival rate must be positive")
    if cfg.t_err < 0 or cfg.think_time < 0 or (cfg.backend_limit is not None and cfg.backend_limit < 1):
        raise ValueError("Invalid retry, think time or backend capacity")
    if cfg.dist_cpu not in ("exp", "det") or cfg.dist_io not in ("exp", "det"):
        raise ValueError("Invalid service distribution")
    if not 0 <= cfg.heavy_prob <= 1 or cfg.heavy_mult <= 0:
        raise ValueError("Invalid heavy-task parameters")
    eff_s = cfg.s * (cfg.kappa if cfg.arch == "partitioned" else 1.0)
    cap_rate = cfg.c / eff_s

    warm_reqs = int(cfg.n_req * cfg.warm_ratio)
    if cfg.adaptive_warmup and cfg.closed_C == 0 and cfg.K < 10**6 and cfg.gamma >= 0.85 * cap_rate:
        excess = max(cfg.gamma - cap_rate, 0.05 * cap_rate)
        fill_reqs = int(3.0 * cfg.K * cfg.gamma / excess)
        warm_reqs = max(warm_reqs, min(fill_reqs, int(0.5 * cfg.n_req)))

    if cfg.closed_C > 0:
        cycle_t = eff_s + cfg.D + max(cfg.think_time, cfg.t_err)
        t_end = 3.5 * cfg.n_req * max(cycle_t / cfg.closed_C, eff_s / cfg.c) + 50.0 * cycle_t
    else:
        t_end = 3.5 * (cfg.n_req / cfg.gamma) + 50.0 * (eff_s + cfg.D)

    opts = SimulationOptions(
        end_time=t_end,
        dispatcher=cfg.dispatcher_type,
        bucket_width=max(t_end / 900.0, 1e-3),
    )
    sim = Simulation(opts, models=MODELS)
    sim.create_lp(SRC_ID, "SourceLP", seed=cfg.seed, gamma=cfg.gamma,
                  n_req=cfg.n_req, warm_reqs=warm_reqs, closed_C=cfg.closed_C)

    disp_model = "PartitionedDispatcherLP" if cfg.arch == "partitioned" else "SharedDispatcherLP"
    sim.create_lp(DISP_ID, disp_model, seed=cfg.seed, c=cfg.c, K=cfg.K, routing=cfg.routing)

    if cfg.D > 0:
        sim.create_lp(IO_ID, "IoLP", seed=cfg.seed, D=cfg.D,
                      dist_io=cfg.dist_io, backend_limit=cfg.backend_limit)

    sim.create_lp(SINK_ID, "SinkLP", seed=cfg.seed, closed=(cfg.closed_C > 0),
                  t_err=cfg.t_err, think_time=cfg.think_time)

    for k in range(cfg.c):
        sim.create_lp(WORKER_BASE_ID + k, "WorkerLP", seed=cfg.seed, s=eff_s, D=cfg.D,
                      dist_cpu=cfg.dist_cpu, heavy_prob=cfg.heavy_prob, heavy_mult=cfg.heavy_mult)

    stats = _run_in_thread(sim)
    src = sim.get_lp(SRC_ID)
    disp = sim.get_lp(DISP_ID)
    sink = sim.get_lp(SINK_ID)
    io = sim.get_lp(IO_ID) if cfg.D > 0 else None

    if src.sent != cfg.n_req or len(sink.records) + len(sink.rejected) != src.sent:
        raise RuntimeError("Simulation ended before all requests were generated and resolved")

    t_warm = src.t_warm
    t_stop = src.t_last
    T_obs = t_stop - t_warm

    # Lọc các request hoàn thành theo thời điểm rời hệ thống (t_arr + R) nằm trong [t_warm, t_stop]
    obs_done = [r for r in sink.records if t_warm <= (r[0] + r[1]) <= t_stop]
    # Cohort membership uses request IDs, so ties at the warm-up timestamp
    # cannot cause the numerator and denominator to count different arrivals.
    cohort_rej = [r for r in sink.rejected if r[0] > warm_reqs]
    obs_rej = [r for r in sink.rejected if t_warm <= r[2] <= t_stop]

    n_done = len(obs_done)
    n_rej = len(obs_rej)
    n_obs = src.sent - warm_reqs
    n_rej_cpu = sum(r[3] == "cpu" for r in cohort_rej)
    n_rej_io = sum(r[3] == "io" for r in cohort_rej)
    has_done = n_done > 0

    R_arr = np.array([r[1] for r in obs_done]) if has_done else np.array([])
    Wcpu_arr = np.array([r[2] for r in obs_done]) if has_done else np.array([])
    Wq_arr = np.array([r[3] for r in obs_done]) if has_done else np.array([])

    L_cpu = _time_average(disp.trace, 1, t_warm, t_stop)
    U = _time_average(disp.trace, 2, t_warm, t_stop) / cfg.c
    L_io = _time_average(io.trace, 1, t_warm, t_stop) if io else 0.0

    cpu_pending = int(disp.trace[-1][1]) if disp.trace else 0
    io_pending = io.n if io else 0
    total_accounted = len(sink.records) + len(sink.rejected) + cpu_pending + io_pending
    conservation_ok = (total_accounted == src.sent)

    return SimMetrics(
        Pblock=(len(cohort_rej) / n_obs) if n_obs > 0 else np.nan,
        X=(n_done / T_obs) if T_obs > 0 else np.nan,
        R=float(R_arr.mean()) if has_done else np.nan,
        Wq=float(Wq_arr.mean()) if has_done else np.nan,
        W_cpu=float(Wcpu_arr.mean()) if has_done else np.nan,
        p95=float(np.percentile(R_arr, 95)) if has_done else np.nan,
        p99=float(np.percentile(R_arr, 99)) if has_done else np.nan,
        L_cpu=L_cpu,
        L_io=L_io,
        L_sys=L_cpu + L_io,
        U=U,
        events_processed=stats["events_processed"],
        wall_time=stats["wall_time"],
        n_done=n_done,
        n_rejected=n_rej,
        n_arrived=n_obs,
        T_obs=T_obs,
        conservation_ok=conservation_ok,
        p99_cpu=float(np.percentile(Wcpu_arr, 99)) if has_done else np.nan,
        n_rejected_cohort=len(cohort_rej),
        n_rejected_cpu=n_rej_cpu,
        n_rejected_io=n_rej_io,
        Pblock_cpu=n_rej_cpu / n_obs,
        Pblock_io=n_rej_io / n_obs,
    )


def run_replications(base_cfg: SimConfig, n_seeds: int = 10, start_seed: int = 1) -> Dict[str, Dict[str, float]]:
    """Chạy lặp n_seeds hạt giống và trả về thống kê kèm khoảng tin cậy 95%."""
    runs: List[SimMetrics] = []
    for i in range(n_seeds):
        cfg_i = SimConfig(**{**base_cfg.__dict__, "seed": start_seed + i})
        res = run_simulation(cfg_i)
        assert res.conservation_ok, f"Lỗi bảo toàn request ở seed={cfg_i.seed}"
        runs.append(res)

    metric_keys = ["Pblock", "X", "R", "Wq", "W_cpu", "p95", "p99", "L_cpu", "L_io", "L_sys", "U"]
    return {k: summarize_replications([getattr(r, k) for r in runs]) for k in metric_keys}
