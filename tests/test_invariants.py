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
    # Allow the finite observation window to reach steady-state cycle rates.
    cfg = SimConfig(
        gamma=0.0, c=8, K=200, s=1e-3, D=50e-3,
        closed_C=C, t_err=t_err, think_time=think_time, n_req=100_000, seed=7,
    )
    m = run_simulation(cfg)
    assert m.conservation_ok is True
    assert m.T_obs > 0
    estimated_C = m.X * (m.R + think_time) + m.X_err * t_err
    assert abs(estimated_C - C) / C < 0.03


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


def test_dispatcher_equivalence():
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