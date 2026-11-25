import pytest

from apps.simulator_app import run_simulation
from scenarios.config import SimConfig


def test_loom_throughput_excludes_completions_after_last_arrival():
    cfg = SimConfig(gamma=0, closed_C=5000, c=8, K=800, n_req=40_000, seed=100)
    metrics = run_simulation(cfg)

    assert metrics.T_obs == pytest.approx(0.09)
    assert metrics.X * metrics.T_obs == pytest.approx(358)
    assert metrics.n_done == 1510
    assert metrics.n_rejected == 38_490
    assert metrics.conservation_ok


def test_closed_loop_rejection_rate_excludes_late_backend_rejection():
    cfg = SimConfig(
        gamma=0, closed_C=2, K=2, n_req=3, warm_ratio=0,
        s=0.125, D=1, dist_cpu="det", backend_limit=0, t_err=0.125,
    )
    metrics = run_simulation(cfg)

    assert metrics.T_obs == pytest.approx(0.25)
    assert metrics.X_err * metrics.T_obs == pytest.approx(2)
    assert metrics.n_rejected == 3
    assert metrics.conservation_ok
