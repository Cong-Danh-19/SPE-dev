import pytest
from scenarios.config import SimConfig
from apps.simulator_app import run_replications
from scenarios import analytical as ana


def rel_err(sim_val: float, ana_val: float) -> float:
    if abs(ana_val) < 1e-9:
        return abs(sim_val - ana_val)
    return abs(sim_val - ana_val) / abs(ana_val)


def assert_metric_close(
    stat: dict,
    ana_val: float,
    max_rel: float = 0.05,
    abs_floor: float = 0.005,
) -> None:
    """Chấp nhận sai số tương đối < max_rel HOẶC giá trị giải tích nằm trong CI95 / sai số tuyệt đối nhỏ."""
    sim_val = stat["mean"]
    hw = stat.get("half_width", 0.0) or 0.0
    assert (
        rel_err(sim_val, ana_val) < max_rel
        or abs(sim_val - ana_val) <= max(hw, abs_floor)
    ), (
        f"Sai lệch vượt ngưỡng: sim={sim_val:.6f}, ana={ana_val:.6f}, "
        f"rel_err={rel_err(sim_val, ana_val):.4f}, hw={hw:.6f}"
    )


def test_mm1():
    lam, s = 80.0, 0.01
    cfg = SimConfig(gamma=lam, c=1, K=10**9, s=s, D=0.0, n_req=30_000)
    res = run_replications(cfg, n_seeds=5)
    th = ana.mm1(lam, 1.0 / s)
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03
    assert_metric_close(res["W_cpu"], th["W"], max_rel=0.05)
    assert_metric_close(res["L_cpu"], th["L"], max_rel=0.05)


def test_mm1k():
    lam, s, K = 110.0, 0.01, 15
    cfg = SimConfig(gamma=lam, c=1, K=K, s=s, D=0.0, n_req=20_000)
    res = run_replications(cfg, n_seeds=5)
    th = ana.mm1k(lam, 1.0 / s, K)
    assert_metric_close(res["Pblock"], th["Pblock"], max_rel=0.05, abs_floor=0.005)
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03
    assert_metric_close(res["W_cpu"], th["W"], max_rel=0.05)


def test_mminf():
    lam, D = 200.0, 0.05
    cfg = SimConfig(gamma=lam, c=1, K=10**9, s=1e-9, D=D, n_req=15_000)
    res = run_replications(cfg, n_seeds=5)
    th = ana.mminf(lam, 1.0 / D)
    assert rel_err(res["L_io"]["mean"], th["L"]) < 0.05
    assert rel_err(res["R"]["mean"], th["W"]) < 0.03


def test_mmcc():
    lam, s, c = 500.0, 0.01, 6
    cfg = SimConfig(gamma=lam, c=c, K=c, s=s, D=0.0, n_req=20_000)
    res = run_replications(cfg, n_seeds=5)
    th = ana.mmcc(lam, 1.0 / s, c)
    assert_metric_close(res["Pblock"], th["Pblock"], max_rel=0.05, abs_floor=0.005)
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03


def test_mmc():
    lam, s, c = 600.0, 0.01, 8
    cfg = SimConfig(gamma=lam, c=c, K=10**9, s=s, D=0.0, n_req=25_000)
    res = run_replications(cfg, n_seeds=5)
    th = ana.mmc(lam, 1.0 / s, c)
    assert_metric_close(res["W_cpu"], th["W"], max_rel=0.05)
    assert_metric_close(res["L_cpu"], th["L"], max_rel=0.05)


def test_mmck():
    lam, s, c, K = 850.0, 0.01, 8, 24
    cfg = SimConfig(gamma=lam, c=c, K=K, s=s, D=0.0, n_req=20_000)
    res = run_replications(cfg, n_seeds=5)
    th = ana.mmck(lam, 1.0 / s, c, K)
    assert_metric_close(res["Pblock"], th["Pblock"], max_rel=0.05, abs_floor=0.005)
    assert rel_err(res["X"]["mean"], th["X"]) < 0.03
    assert_metric_close(res["L_cpu"], th["L"], max_rel=0.05)


@pytest.mark.parametrize(
    "arch,kappa,K,D,n_req",
    [
        ("shared", 1.0, 24, 10e-3, 25_000),
        ("partitioned", 1.25, 24, 10e-3, 25_000),
    ],
)
def test_tandem_loom_and_bun(arch, kappa, K, D, n_req):
    lam, c, s = 7000.0, 8, 1e-3
    cfg = SimConfig(
        gamma=lam, c=c, K=K, s=s, D=D,
        arch=arch, routing="random", kappa=kappa, n_req=n_req,
    )
    res = run_replications(cfg, n_seeds=5)
    th = ana.tandem_analytical(lam, c, K, s, D, arch=arch, kappa=kappa)

    assert_metric_close(res["Pblock"], th["ana_Pblock"], max_rel=0.05, abs_floor=0.005)
    assert rel_err(res["X"]["mean"], th["ana_X"]) < 0.03
    assert_metric_close(res["R"], th["ana_R"], max_rel=0.05)
    assert_metric_close(res["L_sys"], th["ana_L_sys"], max_rel=0.05)
    assert_metric_close(res["L_io"], th["ana_L_io"], max_rel=0.05)