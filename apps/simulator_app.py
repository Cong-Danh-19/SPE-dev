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
    eff_s = cfg.s * (cfg.kappa if cfg.arch == "partitioned" else 1.0)
    cap_rate = cfg.c / eff_s

    warm_reqs = int(cfg.n_req * cfg.warm_ratio)
    if cfg.closed_C == 0 and cfg.K < 10**6 and cfg.gamma >= 0.85 * cap_rate:
        excess = max(cfg.gamma - cap_rate, 0.05 * cap_rate)
        fill_reqs = int(3.0 * cfg.effective_K * cfg.gamma / excess)
        warm_reqs = max(warm_reqs, min(fill_reqs, int(0.5 * cfg.n_req)))

    # The source limits arrivals. Let the event queue drain even for long think times.
    opts = SimulationOptions(end_time=float("inf"), dispatcher=cfg.dispatcher_type,
                             bucket_width=max(eff_s, 1e-3))
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

    t_warm = src.t_warm
    t_stop = src.t_last
    T_obs = t_stop - t_warm

    # Pblock uses the arrival cohort; X and X_err use terminal event timestamps.
    if (src.sent != cfg.n_req or disp.n or (io and io.n)
            or len(sink.records) + len(sink.rejected) != src.sent):
        raise RuntimeError(f"Mô phỏng chưa hoàn tất: phát {src.sent}/{cfg.n_req} request")

    obs_done = [r for r in sink.records if t_warm <= r[0] <= t_stop]
    n_rej_cpu = n_rej_io = n_errors = 0
    for arrival, rejected_at, stage in sink.rejected:
        if t_warm <= arrival <= t_stop:
            n_rej_cpu += stage == "cpu"
            n_rej_io += stage == "io"
        n_errors += t_warm <= rejected_at <= t_stop

    n_done = len(obs_done)
    n_rej = n_rej_cpu + n_rej_io
    n_obs = src.sent - src.n_before_warm
    if n_done:
        R_arr, Wcpu_arr, Wq_arr, Wio_arr = np.asarray(obs_done)[:, 1:5].T
        p95, p99 = np.percentile(R_arr, [95, 99])
    # A downstream rejection still completed service at CPU.
    cpu_delays = [r[2] for r in sink.records if t_warm <= r[5] <= t_stop]
    cpu_delays.extend(delay for t, delay in sink.cpu_completed_before_io_reject
                      if t_warm <= t <= t_stop)
    p95_cpu, p99_cpu = np.percentile(cpu_delays, [95, 99]) if cpu_delays else (np.nan, np.nan)

    L_cpu = _time_average(disp.trace, 1, t_warm, t_stop)
    U = _time_average(disp.trace, 2, t_warm, t_stop) / cfg.c
    L_io = _time_average(io.trace, 1, t_warm, t_stop) if io else 0.0

    return SimMetrics(
        Pblock=(n_rej / n_obs) if n_obs > 0 else np.nan,
        X=(n_done / T_obs) if T_obs > 0 else np.nan,
        R=float(R_arr.mean()) if n_done else np.nan,
        Wq=float(Wq_arr.mean()) if n_done else np.nan,
        W_cpu=float(Wcpu_arr.mean()) if n_done else np.nan,
        p95=float(p95) if n_done else np.nan,
        p99=float(p99) if n_done else np.nan,
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
        conservation_ok=True,
        X_err=n_errors / T_obs if T_obs > 0 else np.nan,
        n_rejected_cpu=n_rej_cpu,
        n_rejected_io=n_rej_io,
        n_error_events=n_errors,
        n_sent=src.sent,
        warm_reqs=src.n_before_warm,
        t_warm=t_warm,
        p95_cpu=float(p95_cpu),
        p99_cpu=float(p99_cpu),
        W_io=float(Wio_arr.mean()) if n_done else np.nan,
    )


def run_replications(
    base_cfg: SimConfig, n_seeds: int = 10, start_seed: int = 1, *, map_runs=map,
) -> Dict[str, Dict[str, float]]:
    """Chạy lặp n_seeds hạt giống và trả về thống kê kèm khoảng tin cậy 95%."""
    configs = (SimConfig(**{**base_cfg.__dict__, "seed": start_seed + i}) for i in range(n_seeds))
    runs: List[SimMetrics] = list(map_runs(run_simulation, configs))

    metric_keys = ["Pblock", "X", "R", "Wq", "W_cpu", "p95", "p99", "W_io", "L_cpu", "L_io", "L_sys", "U"]
    return {k: summarize_replications([getattr(r, k) for r in runs]) for k in metric_keys}
