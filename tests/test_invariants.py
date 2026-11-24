from scenarios.config import SimConfig
from apps.simulator_app import run_simulation


def test_open_loop_littles_law_and_conservation():
    cfg = SimConfig(gamma=6000.0, c=8, K=120, s=1e-3, D=50e-3, n_req=40_000, seed=42)
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    little_lhs = m.L_sys
    little_rhs = m.X * m.R
    assert abs(little_lhs - little_rhs) / little_rhs < 0.03


def test_closed_loop_littles_law():
    C = 1500
    t_err = 0.01
    think_time = 0.005
    cfg = SimConfig(
        gamma=0.0, c=8, K=200, s=1e-3, D=50e-3,
        closed_C=C, t_err=t_err, think_time=think_time, n_req=50_000, seed=7
    )
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    X_ok = m.X
    X_err = m.n_rejected / m.T_obs
    estimated_C = X_ok * (m.R + think_time) + X_err * t_err
    assert abs(estimated_C - C) / C < 0.03


def test_seed_reproducibility():
    cfg1 = SimConfig(gamma=4000.0, c=8, K=100, s=1e-3, D=50e-3, n_req=20_000, seed=99)
    cfg2 = SimConfig(gamma=4000.0, c=8, K=100, s=1e-3, D=50e-3, n_req=20_000, seed=99)
    m1, m2 = run_simulation(cfg1), run_simulation(cfg2)
    assert m1.X == m2.X
    assert m1.R == m2.R
    assert m1.Pblock == m2.Pblock


def test_dispatcher_equivalence():
    cfg_seq = SimConfig(gamma=3000.0, c=8, K=100, s=1e-3, D=50e-3, dispatcher_type="sequential", seed=12)
    cfg_dist = SimConfig(gamma=3000.0, c=8, K=100, s=1e-3, D=50e-3, dispatcher_type="distributed_sequential", seed=12)
    m1, m2 = run_simulation(cfg_seq), run_simulation(cfg_dist)
    assert abs(m1.X - m2.X) / m1.X < 0.01
    assert abs(m1.R - m2.R) / m1.R < 0.01
