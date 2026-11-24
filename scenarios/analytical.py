import math
from typing import Dict, List
import numpy as np
from scipy import stats


def mm1(lam: float, mu: float) -> Dict[str, float]:
    rho = lam / mu
    if rho >= 1.0:
        return dict(Pblock=0.0, X=mu, rho=rho, stable=False, L=np.inf, W=np.inf, Wq=np.inf, U=1.0)
    W = 1.0 / (mu - lam)
    return dict(Pblock=0.0, X=lam, rho=rho, stable=True, L=rho / (1.0 - rho), W=W, Wq=W - 1.0 / mu, U=rho)


def mm1k(lam: float, mu: float, K: int) -> Dict[str, float]:
    return mmck(lam, mu, c=1, K=K)


def mminf(lam: float, mu: float) -> Dict[str, float]:
    return dict(Pblock=0.0, X=lam, L=lam / mu, W=1.0 / mu, Wq=0.0, U=0.0)


def erlang_c(c: int, a: float) -> float:
    rho = a / c
    if rho >= 1.0:
        return 1.0
    s = sum((a ** k) / math.factorial(k) for k in range(c))
    top = ((a ** c) / math.factorial(c)) / (1.0 - rho)
    return top / (s + top)


def erlang_b(c: int, a: float) -> float:
    B = 1.0
    for k in range(1, c + 1):
        B = (a * B) / (k + a * B)
    return B


def mmc(lam: float, mu: float, c: int) -> Dict[str, float]:
    a = lam / mu
    rho = a / c
    if rho >= 1.0:
        return dict(Pblock=0.0, X=c * mu, rho=rho, stable=False, Pwait=1.0, L=np.inf, W=np.inf, Wq=np.inf, U=1.0)
    pw = erlang_c(c, a)
    Wq = pw / (c * mu - lam)
    W = Wq + 1.0 / mu
    return dict(Pblock=0.0, X=lam, rho=rho, stable=True, Pwait=pw, L=lam * W, W=W, Wq=Wq, U=rho)


def mmcc(lam: float, mu: float, c: int) -> Dict[str, float]:
    """Mô hình Erlang-B (M/M/c/c, hàng chờ = 0)."""
    a = lam / mu
    pb = erlang_b(c, a)
    lam_eff = lam * (1.0 - pb)
    return dict(Pblock=pb, X=lam_eff, L=lam_eff / mu, W=1.0 / mu, Wq=0.0, U=lam_eff / (c * mu))


def mmck(lam: float, mu: float, c: int, K: int) -> Dict[str, float]:
    """Giải tích chính xác M/M/c/K (K >= c) tính trong không gian log tránh tràn số."""
    a = lam / mu
    lp = []
    for n in range(K + 1):
        if n <= c:
            lp.append(n * math.log(a) - math.lgamma(n + 1) if a > 0 else (0.0 if n == 0 else -math.inf))
        else:
            lp.append(n * math.log(a) - math.lgamma(c + 1) - (n - c) * math.log(c))
    m = max(lp)
    p = [math.exp(x - m) for x in lp]
    Z = sum(p)
    p = [x / Z for x in p]

    pK = p[K]
    L = sum(n * p[n] for n in range(K + 1))
    Lq = sum((n - c) * p[n] for n in range(c + 1, K + 1))
    lam_eff = lam * (1.0 - pK)
    W = L / lam_eff if lam_eff > 0 else 0.0
    Wq = Lq / lam_eff if lam_eff > 0 else 0.0
    return dict(
        Pblock=pK, X=lam_eff, L=L, Lq=Lq,
        W=W, Wq=Wq, U=lam_eff / (c * mu), P0=p[0]
    )


def tandem_analytical(lam: float, c: int, K: int, s: float, D: float,
                      arch: str = "shared", kappa: float = 1.0) -> Dict[str, float]:
    """Giải tích mạng nối tiếp CPU -> I/O cho Event Loop, Loom (shared) và Bun (partitioned)."""
    if arch == "partitioned":
        k_per_q = max(1, K // c)
        sub = mmck(lam / c, 1.0 / (kappa * s), 1, k_per_q)
        X = sub["X"] * c
        L_cpu = sub["L"] * c
        W_cpu, Wq, Pblock, U = sub["W"], sub["Wq"], sub["Pblock"], sub["U"]
    else:
        sub = mmck(lam, 1.0 / s, c, K)
        X, L_cpu, W_cpu, Wq, Pblock, U = sub["X"], sub["L"], sub["W"], sub["Wq"], sub["Pblock"], sub["U"]

    L_io = X * D
    R = W_cpu + D
    return dict(
        ana_Pblock=Pblock, ana_X=X, ana_W_cpu=W_cpu, ana_Wq=Wq, ana_R=R,
        ana_L_cpu=L_cpu, ana_L_io=L_io, ana_L_sys=L_cpu + L_io, ana_U=U
    )


def summarize_replications(values: List[float], confidence: float = 0.95) -> Dict[str, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    m = len(arr)
    if m == 0:
        return dict(mean=np.nan, std=np.nan, ci_low=np.nan, ci_high=np.nan, half_width=np.nan)
    mean = float(np.mean(arr))
    if m == 1:
        return dict(mean=mean, std=0.0, ci_low=mean, ci_high=mean, half_width=0.0)
    std = float(np.std(arr, ddof=1))
    h = float(stats.sem(arr) * stats.t.ppf((1.0 + confidence) / 2.0, m - 1))
    return dict(mean=mean, std=std, ci_low=mean - h, ci_high=mean + h, half_width=h)
