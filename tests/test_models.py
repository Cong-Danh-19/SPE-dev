import pytest
from scenarios.config import SimConfig
from apps.simulator_app import run_replications
from scenarios import analytical as ana


def rel_err(sim_val: float, ana_val: float) -> float:
    if ana_val == 0:
        return abs(sim_val)
    return abs(sim_val - ana_val) / abs(ana_val)


def test_mm1():
    lam, s = 80.0, 0.01
    cfg = SimConfig(gamma=lam, c=1, K=10**9, s=s, D=0.0, n_req=40_000)
    res = run_replications(cfg, n_seeds=10)
    th = ana.mm1(lam, 1.0 / s)
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03
    assert rel_err(res["W_cpu"]["mean"], th["W"]) < 0.05
    assert rel_err(res["L_cpu"]["mean"], th["L"]) < 0.05


def test_mm1k():
    lam, s, K = 110.0, 0.01, 15
    cfg = SimConfig(gamma=lam, c=1, K=K, s=s, D=0.0, n_req=40_000)
    res = run_replications(cfg, n_seeds=10)
    th = ana.mm1k(lam, 1.0 / s, K)
    assert rel_err(res["Pblock"]["mean"], th["Pblock"]) < 0.05
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03
    assert rel_err(res["W_cpu"]["mean"], th["W"]) < 0.05


def test_mminf():
    lam, D = 200.0, 0.05
    cfg = SimConfig(gamma=lam, c=1, K=10**9, s=1e-9, D=D, n_req=40_000)
    res = run_replications(cfg, n_seeds=10)
    th = ana.mminf(lam, 1.0 / D)
    assert rel_err(res["L_io"]["mean"], th["L"]) < 0.05
    assert rel_err(res["R"]["mean"], th["W"]) < 0.03


def test_mmcc():
    lam, s, c = 500.0, 0.01, 6
    cfg = SimConfig(gamma=lam, c=c, K=c, s=s, D=0.0, n_req=40_000)
    res = run_replications(cfg, n_seeds=10)
    th = ana.mmcc(lam, 1.0 / s, c)
    assert rel_err(res["Pblock"]["mean"], th["Pblock"]) < 0.05
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03


def test_mmc():
    lam, s, c = 600.0, 0.01, 8
    cfg = SimConfig(gamma=lam, c=c, K=10**9, s=s, D=0.0, n_req=40_000)
    res = run_replications(cfg, n_seeds=10)
    th = ana.mmc(lam, 1.0 / s, c)
    assert rel_err(res["W_cpu"]["mean"], th["W"]) < 0.05
    assert rel_err(res["L_cpu"]["mean"], th["L"]) < 0.05


def test_mmck():
    lam, s, c, K = 850.0, 0.01, 8, 24
    cfg = SimConfig(gamma=lam, c=c, K=K, s=s, D=0.0, n_req=40_000)
    res = run_replications(cfg, n_seeds=10)
    th = ana.mmck(lam, 1.0 / s, c, K)
    assert rel_err(res["Pblock"]["mean"], th["Pblock"]) < 0.05
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03
    assert rel_err(res["L_cpu"]["mean"], th["L"]) < 0.05


@pytest.mark.parametrize("arch,kappa", [("shared", 1.0), ("partitioned", 1.25)])
def test_tandem_loom_and_bun(arch, kappa):
    lam, c, K, s, D = 5000.0, 8, 80, 1e-3, 50e-3
    cfg = SimConfig(gamma=lam, c=c, K=K, s=s, D=D, arch=arch, kappa=kappa, n_req=40_000)
    res = run_replications(cfg, n_seeds=10)
    th = ana.tandem_analytical(lam, c, K, s, D, arch=arch, kappa=kappa)
    assert rel_err(res["Pblock"]["mean"], th["ana_Pblock"]) < 0.05
    assert rel_err(res["X"]["mean"], th["ana_X"]) < 0.03
    assert rel_err(res["R"]["mean"], th["ana_R"]) < 0.05
    assert rel_err(res["L_sys"]["mean"], th["ana_L_sys"]) < 0.05
