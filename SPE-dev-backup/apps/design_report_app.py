"""Audit the final YY9B seed results and render a self-contained report."""
from itertools import combinations
from pathlib import Path
from html import escape
from base64 import b64encode
from io import BytesIO

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy import stats

from apps.design_experiments_app import design_plan, GROUPS
from apps.benchmark_experiments_app import verification_cases

RESULTS = Path(__file__).resolve().parents[1] / "results/phase1_design"


def load_group(group, root):
    frame = pd.read_csv(root / f"design_{group}_raw.csv")
    plans = [p for p in design_plan() if p["group"] == group]
    expected = {(p["scenario"], seed) for p in plans for seed in range(1, 11)}
    if set(zip(frame.scenario, frame.seed)) != expected or len(frame) != len(expected):
        raise ValueError(f"{group}: incomplete or duplicate seed data")
    for p in plans:
        rows = frame[frame.scenario == p["scenario"]]
        for k, value in vars(p["cfg"]).items():
            if k == "seed":
                continue
            ok = rows[k].isna() if value is None else rows[k].eq(value)
            if not ok.all():
                raise ValueError(f"{group}: unexpected {k} in {p['scenario']}")
    if not (frame.conservation_ok.all() and frame.Pblock.between(0, 1).all()
            and np.allclose(frame.Pblock, frame.n_rejected_cohort / frame.n_arrived)
            and np.isfinite(frame[["X", "R", "p99", "U"]]).all().all()):
        raise ValueError(f"{group}: invalid metrics")
    return frame


def figure(frame, x, y, series, xlabel, ylabel):
    fig = Figure(figsize=(7, 3.8), layout="constrained")
    ax = fig.subplots()
    for label, part in frame.groupby(series):
        stats_ = part.groupby(x)[y].agg(["mean", "sem", "count"]).sort_index()
        ax.errorbar(stats_.index, stats_["mean"], 
                    stats_["sem"] * stats.t.ppf(.975, stats_["count"] - 1),
                    marker="o", label=str(label), capsize=2)
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.legend()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=140)
    return '<img alt="' + escape(ylabel) + '" src="data:image/png;base64,' + b64encode(buf.getvalue()).decode() + '">'


def main():
    data = {g: load_group(g, RESULTS) for g in GROUPS}
    out = ['<!doctype html><html lang="vi"><meta charset="utf-8"><title>Kết quả YY9B</title>',
           '<style>body{font:16px system-ui;max-width:980px;margin:2em auto;padding:1em}table{border-collapse:collapse}th,td{padding:.4em;border:1px solid #ccc}img{max-width:100%}</style>',
           '<h1>YY9B · Kết quả thực nghiệm Phase 2</h1>',
           '<p>107 cấu hình × 10 seed theo Bảng 9–10 của bản thiết kế. Thời gian trong CSV tính bằng giây. Các khoảng tin cậy dùng phân phối t trên các seed. Cả ba hệ là mô hình hàng đợi; Bun dùng κ = 1 trong phép so sánh cùng công suất.</p>']
    e1 = data["E1"].assign(system=lambda f: f.scenario.str.split("_").str[0])
    out += ['<h2>E1 · Tải và bão hòa</h2>', figure(e1, "gamma", "X", "system", "Tải (req/s)", "Thông lượng (req/s)"),
            figure(e1, "gamma", "p99", "system", "Tải (req/s)", "p99 (s)")]
    peak = e1[e1.gamma == 8800].groupby("system")[["X","Pblock","R","p99","U"]].mean()
    out += ['<p>Ở tải 8.800 req/s, trần CPU danh nghĩa là 1.000 req/s cho Event Loop và 8.000 cho hai hệ đa nhân. Bảng đo tại tải này:</p>', peak.to_html(float_format=lambda v:f"{v:.4g}")]
    e2 = data["E2"].assign(little=lambda f: f.X*f.R + f.X_err*f.t_err)
    pop = e2.groupby(["scenario","closed_C"])[["Pblock","little"]].mean().reset_index()
    pop["error_pct"] = 100*abs(pop.little/pop.closed_C - 1)
    out += ['<h2>E2 · Hệ kín</h2><p>So sánh X·R + X_err·t_err với C. Ở K vô hạn, chỉ 30.000 lượt gửi theo thiết kế; cửa sổ quan sát ngắn so với thời gian chờ tại C lớn có thể làm sai lệch ước lượng.</p>',pop.to_html(index=False)]
    e3 = data["E3"].assign(system=lambda f: f.scenario.str.split("_").str[0])
    out += ['<h2>E3 · CPU và I/O ở 160 req/s</h2><p>Giữ s = 1 ms để cô lập ảnh hưởng của D đến R. Worker được giải phóng trước lúc chờ I/O.</p>',
            figure(e3[e3.s == .001], "D", "R", "system", "D (s)", "R (s)")]
    e4 = data["E4"].copy()
    e4["K/core"] = e4.K_per_core.fillna("∞").astype(str)
    out += ['<h2>E4 · Sức chứa ở tải tương đối 0,95</h2>',figure(e4,"c","Pblock","K/core","Số worker","Xác suất từ chối")]
    verify = []
    for model, load, cfg, theory in verification_cases():
        part = data["E5"][data["E5"].scenario == model+"_"+load]
        for k,col in (("X","X"),("L","L_io" if model=="M/M/inf" else "L_cpu"),("W","R" if model=="M/M/inf" else "W_cpu"),("Pblock","Pblock")):
            m,s = part[col].mean(), part[col].sem()
            lo,hi = m-stats.t.ppf(.975,9)*s,m+stats.t.ppf(.975,9)*s
            target = theory[k]
            delta = abs(m-target)/abs(target) if target else abs(m-target)
            verify.append(dict(model=model,load=load,metric=k,mean=m,theory=target,low=lo,high=hi,pass_design=(delta < .05 if target else m==0) and lo<=target<=hi))
    v=pd.DataFrame(verify)
    v.to_csv(RESULTS/"verification.csv",index=False)
    failed=v[~v.pass_design]
    out += ['<h2>E5 · Kiểm chứng trạm đơn</h2>',f'<p>{len(v)-len(failed)}/{len(v)} phép đối chiếu đạt cả ngưỡng sai số và CI95. Khi lý thuyết bằng 0 yêu cầu quan sát bằng 0. Với xác suất chặn hiếm, sai số tương đối nhạy với số sự kiện; CI95 trên mười seed không đảm bảo bao phủ mọi nghiệm. Những dòng sau chưa đạt:</p>',failed.to_html(index=False)]
    e6=data["E6"]
    # Seeds are shared across the eight cells: estimate paired factorial contrasts.
    contrasts=[]
    for metric in ("X","R","Pblock"):
        for size in (1,2,3):
            for factors in combinations(("rho_ref","K_per_core","c"),size):
                signs=np.prod([np.where(e6[f]==e6[f].max(),1,-1) for f in factors],axis=0)
                d=(e6[metric]*signs).groupby(e6.seed).sum()/4
                t,p=stats.ttest_1samp(d,0.)
                contrasts.append(dict(metric=metric,effect=" × ".join(factors),estimate=d.mean(),F=t*t,df1=1,df2=9,p=p))
    out += ['<h2>E6 · Tương tác giữa tải, bộ đệm và số worker</h2><p>Hiệu ứng là chênh lệch trung bình giữa hai mức mã hóa. Kiểm định tương phản trong từng seed (F = t², bậc tự do 1 và 9) giữ ghép cặp giữa tám ô dùng chung seed.</p>',pd.DataFrame(contrasts).to_html(index=False)]
    out += ['<h2>Giới hạn validation</h2><p>Đối chiếu nghiệm giải tích kiểm tra việc hiện thực mô hình. Các xu hướng nghẽn CPU, chờ I/O và chia hàng là bằng chứng định tính; chưa đo trực tiếp các runtime thật. Đánh giá chéo của nhóm khác thuộc Phase 3.</p></html>']
    (RESULTS/"report.html").write_text("\n".join(out),encoding="utf-8")


if __name__ == "__main__":
    main()
