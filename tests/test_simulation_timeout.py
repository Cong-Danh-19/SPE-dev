import pytest

from apps.simulator_app import run_simulation
from scenarios.config import SimConfig


def test_closed_loop_reaches_request_budget_with_long_think_time():
    cfg = SimConfig(
        gamma=0, closed_C=1, n_req=5, warm_ratio=0,
        think_time=10, s=0.01, D=0, dist_cpu="det",
    )
    metrics = run_simulation(cfg)
    assert metrics.n_arrived == metrics.n_done == cfg.n_req
    assert metrics.T_obs == pytest.approx(4 * (cfg.think_time + cfg.s))
    assert metrics.conservation_ok


@pytest.mark.parametrize("arch", ["shared", "partitioned"])
def test_timeout_counts_each_outcome_once(arch):
    cfg = SimConfig(
        gamma=0, arch=arch, closed_C=3, n_req=3, warm_ratio=0,
        K=2, s=0.1, D=0, dist_cpu="det", request_timeout=0.15,
    )
    metrics = run_simulation(cfg)
    assert (metrics.n_done, metrics.n_rejected, metrics.n_timed_out) == (1, 1, 1)
    assert metrics.n_arrived == cfg.n_req
    assert metrics.Pblock == pytest.approx(1 / 3)
    assert metrics.conservation_ok


def test_closed_loop_retries_once_after_timeout_at_io_completion():
    cfg = SimConfig(
        gamma=0, closed_C=1, n_req=5, warm_ratio=0,
        s=0.125, D=0.125, dist_cpu="det", dist_io="det",
        request_timeout=0.25, t_err=0.125,
    )
    metrics = run_simulation(cfg)
    assert metrics.n_timed_out == metrics.n_arrived == cfg.n_req
    assert metrics.n_done == metrics.n_rejected == 0
    assert metrics.T_obs == pytest.approx(4 * (cfg.request_timeout + cfg.t_err))
    assert metrics.conservation_ok


def test_long_deadline_does_not_overtake_earlier_completions():
    cfg = SimConfig(
        gamma=0, closed_C=1, n_req=5, warm_ratio=0,
        s=0.01, D=0, dist_cpu="det", request_timeout=8192,
    )
    metrics = run_simulation(cfg)
    assert metrics.n_done == metrics.n_arrived == cfg.n_req
    assert metrics.n_timed_out == 0
    assert metrics.conservation_ok
