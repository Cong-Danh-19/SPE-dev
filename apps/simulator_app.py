import asyncio
import concurrent.futures
import multiprocessing as mp
import os
from typing import Dict, List, Optional
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


def _run_sim(sim: Simulation) -> dict:
    """Chạy trực tiếp nếu chưa có event loop; chỉ bọc ThreadPool khi chạy trong Jupyter."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return sim.run()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(sim.run).result()


def _time_average_arrays(t_list: list, v_list: list, t_warm: float, t_stop: float) -> float:
    T = t_stop - t_warm
    if T <= 0 or not t_list:
        return 0.0
    t = np.asarray(t_list, dtype=float)
    v = np.asarray(v_list, dtype=float)
    t1 = np.minimum(np.append(t[1:], t_stop), t_stop)
    t0 = np.maximum(t, t_warm)
    return float(np.sum(v * np.clip(t1 - t0, 0.0, None)) / T)


def run_simulation(cfg: SimConfig) -> SimMetrics:
    """Chạy một lượt mô phỏng DES hoàn chỉnh và trả về các metric sau warm-up."""
    if cfg.arch not in ("shared", "partitioned"):
        raise ValueError(f"Kiến trúc không hợp lệ: {cfg.arch!r} (chỉ nhận 'shared' hoặc 'partitioned')")
    if cfg.routing not in ("random", "rr"):
        raise ValueError(f"Định tuyến không hợp lệ: {cfg.routing!r} (chỉ nhận 'random' hoặc 'rr')")

    eff_s = cfg.s * (cfg.kappa if cfg.arch == "partitioned" else 1.0)
    cap_rate = cfg.c / eff_s
    k_eff = (cfg.c * max(1, cfg.K // cfg.c)) if cfg.arch == "partitioned" else cfg.K

    warm_reqs = int(cfg.n_req * cfg.warm_ratio)
    if cfg.closed_C == 0 and cfg.K < 10**6 and cfg.gamma >= 0.85 * cap_rate:
        excess = max(cfg.gamma - cap_rate, 0.05 * cap_rate)
        fill_reqs = int(3.0 * cfg.K * cfg.gamma / excess)
        warm_reqs = max(warm_reqs, min(fill_reqs, int(0.5 * cfg.n_req)))

    if cfg.closed_C > 0:
        cycle_t = eff_s + cfg.D + max(cfg.think_time, cfg.t_err)
        t_end = 3.5 * cfg.n_req * max(cycle_t / cfg.closed_C, eff_s / cfg.c) + 50.0 * cycle_t
    else:
        t_end = 3.5 * (cfg.n_req / cfg.gamma) + 50.0 * (eff_s + cfg.D)

    # Giữ trung bình ~4 request (~32 sự kiện)/bucket để LadderQueue duy trì O(1)
    opts = SimulationOptions(
        end_time=t_end,
        dispatcher=cfg.dispatcher_type,
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

    stats = _run_sim(sim)
    src = sim.get_lp(SRC_ID)
    disp = sim.get_lp(DISP_ID)
    sink = sim.get_lp(SINK_ID)
    io = sim.get_lp(IO_ID) if cfg.D > 0 else None

    t_warm = src.t_warm
    t_stop = src.t_last
    T_obs = t_stop - t_warm

    obs_done = [r for r in sink.records if t_warm <= (r[0] + r[1]) <= t_stop]
    n_arr_cohort = src.arrived_obs
    obs_rej = [r for r in sink.rejected if t_warm <= r[0] <= t_stop]

    n_done = len(obs_done)
    n_rej = len(obs_rej)
    n_rej_cpu = sum(1 for r in obs_rej if r[2] == "cpu")
    n_rej_io = sum(1 for r in obs_rej if r[2] == "io")
    has_done = n_done > 0

    R_arr = np.array([r[1] for r in obs_done]) if has_done else np.array([])
    Wcpu_arr = np.array([r[2] for r in obs_done]) if has_done else np.array([])
    Wq_arr = np.array([r[3] for r in obs_done]) if has_done else np.array([])

    L_cpu = _time_average_arrays(disp.trace_t, disp.trace_n, t_warm, t_stop)
    U = _time_average_arrays(disp.trace_t, disp.trace_busy, t_warm, t_stop) / cfg.c
    L_io = _time_average_arrays(io.trace_t, io.trace_n, t_warm, t_stop) if io else 0.0

    cpu_pending = int(disp.trace_n[-1]) if disp.trace_n else 0
    io_pending = io.n if io else 0
    total_accounted = len(sink.records) + len(sink.rejected) + cpu_pending + io_pending
    conservation_ok = (total_accounted == src.sent)

    return SimMetrics(
        Pblock=(n_rej / n_arr_cohort) if n_arr_cohort > 0 else np.nan,
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
        n_arrived=n_arr_cohort,
        T_obs=T_obs,
        conservation_ok=conservation_ok,
        n_rejected_cpu=n_rej_cpu,
        n_rejected_io=n_rej_io,
        Pblock_cpu=(n_rej_cpu / n_arr_cohort) if n_arr_cohort > 0 else np.nan,
        Pblock_io=(n_rej_io / n_arr_cohort) if n_arr_cohort > 0 else np.nan,
        p95_cpu=float(np.percentile(Wcpu_arr, 95)) if has_done else np.nan,
        p99_cpu=float(np.percentile(Wcpu_arr, 99)) if has_done else np.nan,
        K_eff=k_eff,
        n_sent=src.sent,
        completed_target=(src.sent >= cfg.n_req),
    )


def run_batch_simulations(configs: List[SimConfig], max_workers: Optional[int] = None) -> List[SimMetrics]:
    """Chạy song song một danh sách SimConfig trên nhiều nhân CPU (giữ đúng thứ tự đầu vào)."""
    if not configs:
        return []
    workers = max_workers or max(1, (os.cpu_count() or 4) - 1)
    if len(configs) == 1 or workers <= 1 or mp.current_process().daemon:
        return [run_simulation(c) for c in configs]

    workers = min(workers, len(configs))
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(run_simulation, configs, chunksize=1))
    except (PermissionError, OSError):
        return [run_simulation(c) for c in configs]


def run_replications(base_cfg: SimConfig, n_seeds: int = 10, start_seed: int = 1) -> Dict[str, Dict[str, float]]:
    """Chạy lặp n_seeds hạt giống song song và trả về thống kê kèm khoảng tin cậy 95%."""
    cfgs = [SimConfig(**{**base_cfg.__dict__, "seed": start_seed + i}) for i in range(n_seeds)]
    runs = run_batch_simulations(cfgs)
    for cfg_i, res in zip(cfgs, runs):
        assert res.conservation_ok, f"Lỗi bảo toàn request ở seed={cfg_i.seed}"

    metric_keys = [
        "Pblock", "Pblock_cpu", "Pblock_io", "X", "R", "Wq", "W_cpu",
        "p95", "p99", "p95_cpu", "p99_cpu", "L_cpu", "L_io", "L_sys", "U"
    ]
    return {k: summarize_replications([getattr(r, k) for r in runs]) for k in metric_keys}