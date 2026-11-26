import numpy as np
import pytest
from scenarios.config import SimConfig
from apps.simulator_app import run_simulation


def test_open_loop_littles_law_and_conservation():
    cfg = SimConfig(gamma=6000.0, c=8, K=120, s=1e-3, D=50e-3, n_req=40_000, seed=42)
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    assert abs(m.L_sys - m.X * m.R) / (m.X * m.R) < 0.03
    assert abs(m.L_cpu - m.X * m.W_cpu) / max(m.L_cpu, 1e-9) < 0.03


def test_closed_loop_littles_law():
    C = 1500
    t_err = 0.01
    think_time = 0.005
    cfg = SimConfig(
        gamma=0.0, c=8, K=200, s=1e-3, D=50e-3,
        closed_C=C, t_err=t_err, think_time=think_time, n_req=120_000, seed=7,
    )
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    assert m.T_obs > 0
    X_ok = m.X
    X_err = m.X_err
    estimated_C = X_ok * (m.R + think_time) + X_err * t_err
    assert abs(estimated_C - C) / C < 0.04


def test_non_blocking_io_behavior():
    """Với c=1, s=1ms, D=200ms (I/O gấp 200 lần CPU), tải 500 req/s (rho_cpu=0.5)
    phải thông suốt nhờ I/O non-blocking (không bị nghẽn theo lambda*(s+D)=100.5)."""
    cfg = SimConfig(
        gamma=500.0, c=1, K=100, s=1e-3, D=200e-3,
        arch="shared", n_req=25_000, seed=21,
    )
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    assert m.Pblock < 0.02
    assert abs(m.X - 500.0) / 500.0 < 0.05
    assert m.L_io > 50.0  # Số phiên I/O treo đồng thời lớn nhưng CPU vẫn rảnh để phục vụ


def test_zero_io_delay_bypasses_io_station():
    cfg = SimConfig(
        gamma=1000.0, c=4, K=100, s=5e-4, D=0.0,
        arch="shared", n_req=25_000, seed=33,
    )
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    assert m.L_io == 0.0
    assert abs(m.R - m.W_cpu) < 1e-9


def test_seed_reproducibility():
    cfg1 = SimConfig(gamma=4000.0, c=8, K=100, s=1e-3, D=50e-3, n_req=20_000, seed=99)
    cfg2 = SimConfig(gamma=4000.0, c=8, K=100, s=1e-3, D=50e-3, n_req=20_000, seed=99)
    m1, m2 = run_simulation(cfg1), run_simulation(cfg2)
    assert m1.conservation_ok is True and m2.conservation_ok is True
    assert m1.X == m2.X
    assert m1.R == m2.R
    assert m1.Pblock == m2.Pblock


def test_coroutine_lps_are_independent_of_dispatcher_option():
    cfg_seq = SimConfig(
        gamma=3000.0, c=8, K=100, s=1e-3, D=50e-3,
        dispatcher_type="sequential", n_req=20_000, seed=12,
    )
    cfg_dist = SimConfig(
        gamma=3000.0, c=8, K=100, s=1e-3, D=50e-3,
        dispatcher_type="distributed_sequential", n_req=20_000, seed=12,
    )
    m1, m2 = run_simulation(cfg_seq), run_simulation(cfg_dist)
    assert m1.conservation_ok is True and m2.conservation_ok is True
    assert abs(m1.X - m2.X) / m1.X < 0.01
    assert abs(m1.R - m2.R) / m1.R < 0.01


def test_special_scenarios_s8_and_s10():
    # S8: Giới hạn kết nối backend I/O
    cfg_s8 = SimConfig(
        gamma=7000.0, c=8, K=400, s=1e-3, D=50e-3,
        arch="shared", backend_limit=300, n_req=25_000, seed=55,
    )
    m_s8 = run_simulation(cfg_s8)
    assert m_s8.conservation_ok is True
    assert m_s8.L_io <= 300.0 + 1e-6

    # S10: Tác vụ CPU nặng bất thường trên Event Loop (c=1) vs Spring Loom (c=8)
    cfg_el = SimConfig(
        gamma=900.0, c=1, K=200, s=1e-3, D=10e-3,
        arch="shared", heavy_prob=0.05, heavy_mult=20.0, n_req=20_000, seed=77,
    )
    cfg_loom = SimConfig(
        gamma=900.0, c=8, K=800, s=1e-3, D=10e-3,
        arch="shared", heavy_prob=0.05, heavy_mult=20.0, n_req=20_000, seed=77,
    )
    m_el, m_loom = run_simulation(cfg_el), run_simulation(cfg_loom)
    assert m_el.conservation_ok is True and m_loom.conservation_ok is True
    assert m_loom.R < m_el.R
    
def test_closed_loop_high_load_no_ceiling_violation():
    """Đảm bảo ở tải hệ kín cao (C=5000, K=200), thông lượng X không vượt trần CPU c/s=8000."""
    C = 5000
    t_err = 0.01
    cfg = SimConfig(
        gamma=0.0, c=8, K=200, s=1e-3, D=50e-3,
        closed_C=C, t_err=t_err, think_time=0.0, n_req=120_000, seed=17,
    )
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    assert m.X <= (cfg.c / cfg.s) * 1.02
    X_err = m.X_err
    estimated_C = m.X * m.R + X_err * t_err
    assert abs(estimated_C - C) / C < 0.05


def test_saturation_rho_one_dynamic_warmup():
    """Đảm bảo tại đúng điểm bão hòa rho=1.0 (gamma=8000, c=8, s=1ms), warm-up động được kích hoạt."""
    cfg = SimConfig(
        gamma=8000.0, c=8, K=160, s=1e-3, D=50e-3,
        arch="shared", n_req=25_000, seed=42,
    )
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    assert m.warm_reqs == 9_600
    assert m.R > 0.055

def test_closed_loop_drains_after_long_think_time():
    m = run_simulation(SimConfig(
        gamma=0, closed_C=1, think_time=1, D=0, dist_cpu="det", n_req=1000,
    ))
    assert m.n_sent == 1000
    assert m.warm_reqs == 100
    assert m.n_arrived == 900
    assert m.t_warm == pytest.approx(100 * 1.001)
    assert m.T_obs == pytest.approx(899 * 1.001)
    assert m.conservation_ok


def test_s8_arrival_cohort_and_station_rejections():
    m = run_simulation(SimConfig(
        gamma=7000, c=8, K=400, arch="partitioned", kappa=1.25,
        backend_limit=300, seed=101,
    ))
    # Independent reproduction of TV1's seed 101 case.
    assert m.n_arrived == 16_000
    assert (m.n_rejected_cpu, m.n_rejected_io) == (1560, 1165)
    assert m.Pblock == 2725 / 16_000
    assert m.n_error_events == 2763
    assert m.X_err == m.n_error_events / m.T_obs
    assert m.p99_cpu < m.p99


def test_round_robin_report_excludes_poisson_reference():
    from apps.benchmark_experiments_app import evaluate_config

    raw = []
    row = evaluate_config("test", "rr", SimConfig(
        gamma=2000, c=2, K=3, D=0, arch="partitioned", routing="rr", n_req=200,
    ), n_seeds=1, raw_collector=raw)
    assert row["analytical_applicable"] is False
    assert np.isnan(row["ana_Pblock"])
    assert row["effective_K"] == raw[0]["effective_K"] == 2
    assert raw[0]["n_rejected_cpu"] == raw[0]["n_rejected"]
    assert raw[0]["n_rejected_io"] == 0


def test_ladder_queue_orders_past_legacy_bucket_cycle():
    from bkitevsim.core import Event
    from bkitevsim.queues import LadderQueue

    queue = LadderQueue(bucket_width=1, num_buckets=4)
    for ts, label in [(8, "future"), (3, "first"), (3, "second"), (4, "next")]:
        queue.push(Event(ts, 0, 1, label))
    assert queue.peek_timestamp() == 3
    assert [e.event_type for e in queue.pop_events_after(4)] == ["future"]
    assert [queue.pop().event_type for _ in range(3)] == ["first", "second", "next"]


def test_cpu_percentile_includes_jobs_rejected_by_backend():
    m = run_simulation(SimConfig(
        gamma=0, closed_C=1, n_req=100, D=0.05, backend_limit=0, dist_cpu="det",
    ))
    assert m.Pblock == 1 and m.n_done == 0
    assert m.n_rejected_io == m.n_arrived
    assert np.isnan(m.p99)
    assert m.p95_cpu == pytest.approx(0.001)
    assert m.p99_cpu == pytest.approx(0.001)
