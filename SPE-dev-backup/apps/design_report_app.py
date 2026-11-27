"""Audit the final YY9B seed results and render a self-contained report."""
from apps.report_artifacts import report_hashes
import json
from itertools import combinations
from pathlib import Path
from html import escape
from base64 import b64encode
from io import BytesIO

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from scipy import stats

from scenarios.analytical import tandem_analytical
from apps.design_experiments_app import design_plan, GROUPS
from apps.verification_followup_app import compare

RESULTS = Path(__file__).resolve().parents[1] / "results/phase1_design"


def load_group(group, root):
    frame = pd.read_csv(root / f"design_{group}_raw.csv", float_precision="round_trip")
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
            and (frame.n_arrived == frame.n_req - (frame.warm_ratio * frame.n_req).astype(int)).all()
            and np.allclose(frame.Pblock, frame.n_rejected_cohort / frame.n_arrived)
            and np.isfinite(frame[["X", "R", "p99", "U"]]).all().all()):
        raise ValueError(f"{group}: invalid metrics")
    summary = pd.read_csv(root / f"design_{group}_summary.csv").set_index("scenario").sort_index()
    from apps.design_experiments_app import METRICS
    means = frame.groupby("scenario")[list(METRICS)].mean().sort_index()
    if not summary.index.equals(means.index) or not summary.n_seeds.eq(10).all():
        raise ValueError(f"{group}: inconsistent scenario summary")
    for metric in METRICS:
        if not np.allclose(summary[metric+"_mean"], means[metric], rtol=1e-10, atol=1e-14):
            raise ValueError(f"{group}: summary differs from raw {metric}")
    return frame


def embed(fig, label):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=140)
    return '<img alt="' + escape(label) + '" src="data:image/png;base64,' + b64encode(buf.getvalue()).decode() + '">'


def heatmap(frame, x, series, name):
    pivot = frame.pivot_table(index=series, columns=x, values="U")
    fig = Figure(figsize=(8, 3.1), layout="constrained")
    ax = fig.subplots()
    image = ax.imshow(pivot.to_numpy(), vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)), [str(x) for x in pivot.columns], rotation=30)
    ax.set_yticks(range(len(pivot)), pivot.index)
    ax.set_xlabel(name)
    fig.colorbar(image, ax=ax, label="U")
    return embed(fig, "Utilization CPU")


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
    return embed(fig, ylabel)


def main():
    data = {g: load_group(g, RESULTS) for g in GROUPS}
    out = ['<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kết quả YY9B</title>',
           '<style>*{box-sizing:border-box}body{font:16px/1.55 system-ui;color:#162c36;max-width:980px;margin:auto;padding:1em 2em 4em}h1,h2,h3{line-height:1.25}h2{margin-top:2em;border-top:1px solid #b6cbd2;padding-top:.8em}table{display:block;max-width:100%;overflow-x:auto;border-collapse:collapse;font-size:.9em;font-variant-numeric:tabular-nums}th,td{padding:.35em .65em;border:1px solid #cedadf}th{background:#e5f0f2}img{display:block;max-width:100%;height:auto}a{color:#065b76}nav a{margin-right:1em}@media print{@page{size:A4;margin:12mm}body{font-size:10pt;margin:0;padding:0}nav{display:none}img{max-height:85mm;break-inside:avoid}table{display:table;font-size:7pt}td,th{padding:.12em .2em}h2,h3{break-after:avoid}tr{break-inside:avoid}}</style>',
           '<h1>YY9B · Kết quả thực nghiệm Phase 2</h1>',
           '<nav aria-label="Mục lục">' + ' '.join(f'<a href="#{g}">{g}</a>' for g in GROUPS) + ' <a href="#validation">Validation</a></nav>',
           '<p>107 cấu hình × 10 seed theo Bảng 9–10 của bản thiết kế. Thời gian trong CSV tính bằng giây. Các khoảng tin cậy dùng phân phối t trên các seed. Cả ba hệ là mô hình hàng đợi; Bun dùng κ = 1 trong phép so sánh cùng công suất.</p>']
    e1 = data["E1"].assign(system=lambda f: f.scenario.str.split("_").str[0])
    out += ['<h2 id="E1">E1 · Tải và bão hòa</h2>', figure(e1, "gamma", "X", "system", "Tải (req/s)", "Thông lượng (req/s)"),
            heatmap(e1, "gamma", "system", "Tải (req/s)"),
            figure(e1,"gamma","R","system","Tải (req/s)","R (s)"),
            figure(e1, "gamma", "p99", "system", "Tải (req/s)", "p99 (s)")]
    at_load = e1[e1.gamma == 7500].groupby("system")[["Wq","Pblock"]].mean()
    out += [f'<p>Ở 7.500 req/s và cùng tám worker, chờ CPU trung bình là {at_load.loc["Bun","Wq"]*1000:.2f} ms với hàng riêng (Bun) và {at_load.loc["Loom","Wq"]*1000:.2f} ms với hàng chung (Loom). Hàng chung cho phép worker rảnh nhận ngay request tiếp theo.</p>']
    peak = e1[e1.gamma == 8800].groupby("system")[["X","Pblock","R","p99","U"]].mean()
    out += ['<p>Ở tải 8.800 req/s, trần CPU danh nghĩa là 1.000 req/s cho Event Loop và 8.000 cho hai hệ đa nhân. Bảng đo tại tải này:</p>', peak.to_html(float_format=lambda v:f"{v:.4g}")]
    e2 = data["E2"].assign(XR=lambda f: f.X*f.R, little=lambda f: f.X*f.R + f.X_err*f.t_err)
    pop = e2.groupby(["scenario","closed_C"])[["Pblock","XR","little","L_sys"]].mean().reset_index()
    pop["error_pct"] = 100*abs(pop.little/pop.closed_C - 1)
    out += ['<h2 id="E2">E2 · Hệ kín</h2><p>So sánh X·R + X_err·t_err với C. Ở K vô hạn, chỉ 30.000 lượt gửi theo thiết kế; cửa sổ quan sát ngắn so với thời gian chờ tại C lớn có thể làm sai lệch ước lượng.</p>',pop.to_html(index=False)]
    boundary = pop[pop.scenario.str.endswith("Kinf") & (pop.closed_C == 5000)]
    out += [f'<p>Với C = 5.000 và K không giới hạn, 3.000 request warm-up nằm trong đợt gửi đồng thời tại t = 0. Cửa sổ vì vậy còn gồm cả giai đoạn khởi động. X·R ở hai hệ lệch {boundary.error_pct.min():.1f}–{boundary.error_pct.max():.1f}% so với C; số request trung bình tính trực tiếp theo thời gian (L_sys) là {boundary.L_sys.mean():,.1f}. R lấy ở các lượt đã hoàn tất nên bỏ sót phần thời gian của các lượt còn dở ở cuối cửa sổ. Không dùng hai ước lượng X·R này để kết luận trạng thái dừng.</p>']
    e2["system_K"] = e2.scenario.str.replace(r"_C[0-9]+", "", regex=True)
    out += [figure(e2, "closed_C", "XR", "system_K", "C", "X·R (request)"),
            figure(e2, "closed_C", "little", "system_K", "C", "X·R + X_err·t_err"),
            figure(e2, "closed_C", "Pblock", "system_K", "C", "Xác suất từ chối")]
    e3 = data["E3"].assign(system=lambda f: f.scenario.str.split("_").str[0])
    io_means = e3[e3.s == .001].groupby(["system", "D"])[["R", "X"]].mean()
    out += ['<h2 id="E3">E3 · CPU và I/O ở 160 req/s</h2><p>Giữ s = 1 ms để cô lập ảnh hưởng của D đến R. Worker được giải phóng trước lúc chờ I/O.</p>',
            figure(e3[e3.s == .001], "D", "R", "system", "D (s)", "R (s)")]
    io_changes = io_means.xs(.2, level="D") - io_means.xs(.01, level="D")
    out += [f'<p>Khi tăng D từ 10 lên 200 ms ở s = 1 ms, R tăng từ {io_changes.R.min()*1000:.1f} đến {io_changes.R.max()*1000:.1f} ms tùy hệ. Chênh lệch thông lượng lớn nhất chỉ {io_changes.X.abs().max():.2f} req/s: I/O kéo dài thời gian chờ nhưng không chiếm worker.</p>']
    out += [heatmap(e3, "s", "system", "s (giây), trung bình qua D")]
    long_io = e3[e3.D == .2].groupby("scenario")[["W_cpu", "p99_cpu", "Pblock", "X"]].mean()
    long_io["pass_slo"] = (long_io.W_cpu < .05) & (long_io.p99_cpu < .25) & (long_io.Pblock < .01) & (long_io.X >= .95*160)
    out += ['<p>Riêng D = 200 ms: áp ngưỡng thời gian tại CPU (trung bình &lt; 50 ms, p99 &lt; 250 ms) cùng ngưỡng từ chối và thông lượng của Bảng 1. Các thời gian trong bảng tính bằng giây.</p>', long_io.to_html()]
    e4 = data["E4"].copy()
    e4["K/core"] = e4.K_per_core.astype("object").fillna("∞").astype(str)
    out += ['<h2 id="E4">E4 · Sức chứa ở tải tương đối 0,95</h2>',figure(e4,"c","Pblock","K/core","Số worker","Xác suất từ chối")]
    # For the unbounded configuration the stationary blocking probability is zero.
    from scenarios.analytical import mmck
    comparison = []
    for scenario, grp in e4.groupby("scenario"):
        r = grp.iloc[0]
        pb = 0 if pd.isna(r.K_per_core) else mmck(r.gamma, 1/r.s, int(r.c), int(r.K))["Pblock"]
        comparison.append({"scenario":scenario, "lambda":r.gamma, "Pblock_DES":grp.Pblock.mean(), "Pblock_theory":pb})
    out += [pd.DataFrame(comparison).to_html(index=False)]
    v = compare(data["E5"])
    v.to_csv(RESULTS/"verification.csv",index=False)
    failed=v[~v.pass_design]
    out += ['<h2 id="E5">E5 · Kiểm chứng trạm đơn</h2>',f'<p>{len(v)-len(failed)}/{len(v)} phép đối chiếu đạt cả ngưỡng sai số và CI95. Khi lý thuyết bằng 0 yêu cầu quan sát bằng 0. Với xác suất chặn hiếm, sai số tương đối nhạy với số sự kiện; CI95 trên mười seed không đảm bảo bao phủ mọi nghiệm. Có {int((~v.within_ci).sum())} trị lý thuyết nằm ngoài CI95. Các metric cùng trạm dùng chung chuỗi request nên các sai lệch có thể đi cùng nhau. Những dòng sau chưa đạt:</p>',failed.to_html(index=False),
            '<p><a href="verification.csv">Toàn bộ 72 phép so sánh và khoảng tin cậy</a>.</p>']
    follow = pd.read_csv(RESULTS / "verification_followup_raw.csv", float_precision="round_trip")
    expected = {(r.model + "_" + r.load, seed) for r in failed.itertuples() for seed in range(101, 111)}
    if len(follow) != len(expected) or set(zip(follow.scenario, follow.seed)) != expected or not (follow.n_req == 120000).all():
        raise ValueError("Incomplete independent E5 follow-up")
    if expected:
        repeat = failed[["model", "load", "metric", "mean"]].merge(compare(follow), on=["model", "load", "metric"], suffixes=("_original","_repeat"))
        out += ['<h3>Đối chứng độc lập cho các ô E5 chưa đạt</h3>',
                f'<p>Chạy lại tất cả {len(expected)//10} cấu hình có ít nhất một chỉ số chưa đạt: 120.000 request/lượt, seed 101–110 và warm-up 10%. Bảng chỉ hiển thị những chỉ số chưa đạt trên ma trận gốc. {repeat.pass_design.sum()}/{len(repeat)} đạt ngưỡng trong phép đo bổ sung. Dữ liệu này tách riêng; không thay thế bất kỳ seed chính thức nào. <a href="verification_followup_raw.csv">Dữ liệu từng lượt</a>.</p>', repeat.to_html(index=False)]
    blocking = v[v.metric == "Pblock"]
    loss = blocking[blocking.model.isin(["M/M/1/K", "M/M/c/K"])]
    if not loss.empty:
        fig = Figure(figsize=(8, 4), layout="constrained")
        ax = fig.subplots()
        axis = np.arange(len(loss))
        ax.errorbar(axis, loss["mean"], yerr=[loss["mean"]-loss.low, loss.high-loss["mean"]], fmt="o", label="DES ± CI95")
        ax.scatter(axis, loss.theory, marker="x", label="Giải tích")
        ax.set_xticks(axis, loss.model + " " + loss.load, rotation=25)
        ax.set_ylabel("Pblock")
        ax.legend()
        out.append(embed(fig, "Xác suất từ chối: DES và giải tích"))
    checks = []
    for scenario, grp in data["E3"].groupby("scenario"):
        r = grp.iloc[0]
        ref = tandem_analytical(r.gamma, int(r.c), int(r.K), r.s, r.D, r.arch, r.kappa)
        for metric in ("R", "L_io", "Pblock"):
            obs, target = grp[metric].mean(), ref["ana_"+metric]
            error = abs(obs-target)/target if target > 0 else (0 if obs == target else np.inf)
            checks.append(dict(scenario=scenario, metric=metric, observed=obs, theory=target,
                               relative_error=error, absolute_error=abs(obs-target), pass_3pct=(abs(obs-target) < .01 if metric=="Pblock" and target < .01 else error < .03)))
    checks = pd.DataFrame(checks)
    checks.to_csv(RESULTS/"tandem.csv", index=False)
    out += ['<h3>Kiểm chứng mạng nối tiếp</h3>',
            f'<p>{checks.pass_3pct.sum()}/{len(checks)} phép đối chiếu trung bình E3 với nghiệm giải tích đạt sai số dưới 3%. Theo Bảng 1, dùng sai số tuyệt đối cho Pblock nhỏ: trong báo cáo này, khi Pblock lý thuyết dưới 1%, ngưỡng là một điểm phần trăm. CSV ghi cả sai số tương đối và tuyệt đối. <a href="tandem.csv">Từng phép đo</a>.</p>']
    rows = []
    for scenario, grp in data["E1"].groupby("scenario"):
        r=grp.mean(numeric_only=True)
        rows.append(dict(scenario=scenario, gamma=r.gamma, Pblock=r.Pblock,
                         R_ms=r.R*1000, p99_ms=r.p99*1000, throughput_ratio=r.X/r.gamma,
                         ok=(r.Pblock < .01 and r.R < .100 and r.p99 < .300 and r.X/r.gamma >= .95)))
    thresholds=pd.DataFrame(rows)
    thresholds.to_csv(RESULTS/"slo.csv",index=False)
    thresholds["system"]=thresholds.scenario.str.split("_").str[0]
    best=thresholds[thresholds.ok].groupby("system").gamma.max()
    out += ['<h3>Ngưỡng vận hành</h3><p>Tải cao nhất trên lưới đạt đồng thời bốn ngưỡng về tỷ lệ lỗi, độ trễ trung bình, p99 và thông lượng (req/s):</p>',best.to_frame().to_html()]
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
    out += ['<h2 id="E6">E6 · Tương tác giữa tải, bộ đệm và số worker</h2><p>Hiệu ứng là chênh lệch trung bình giữa hai mức mã hóa. Kiểm định tương phản trong từng seed (F = t², bậc tự do 1 và 9) giữ ghép cặp giữa tám ô dùng chung seed.</p>',pd.DataFrame(contrasts).to_html(index=False)]
    strongest = max((x for x in contrasts if x["metric"] == "X" and "×" in x["effect"]), key=lambda x: abs(x["estimate"]))
    out += [f'<p>Với thông lượng, tương tác có độ lớn lớn nhất trên lưới là {strongest["effect"]} ({strongest["estimate"]:+.1f} req/s). Các hiệu ứng chỉ áp dụng cho hai mức của từng yếu tố đã khảo sát.</p>']
    runtime = pd.read_csv(RESULTS/"runtime_validation.csv")
    workloads = {"concurrent_io", "sequential_io", "blocking_event_loop", "thread_pool_1", "thread_pool_3", "thread_pool_6"}
    if len(runtime) != 18 or set(zip(runtime.workload, runtime.trial)) != {(w, i) for w in workloads for i in (1, 2, 3)}:
        raise ValueError("Incomplete reference observations")
    times = runtime.groupby("workload")[["reference_seconds", "observed_seconds"]].median()
    out += ['<h2 id="validation">Validation · Workload đối chứng</h2><p>Lặp lại minh họa ở §1.4 của design bằng Python asyncio: mỗi tác vụ chờ 0,2 giây. Bảng là trung vị ba lần đo bằng đồng hồ thật. Chờ I/O đồng thời cho phép các khoảng chờ chồng lấp; chặn luồng event loop khiến chúng cộng dồn. So sánh này kiểm tra giả định về chờ I/O ở mức cơ chế.</p>',times.to_html(),'<p><a href="runtime_validation.csv">Dữ liệu đối chứng</a></p>']
    out += ['<h2>Giới hạn validation</h2><p>Đối chiếu nghiệm giải tích kiểm tra việc hiện thực mô hình. Các xu hướng nghẽn CPU, chờ I/O và chia hàng là bằng chứng định tính; chưa đo trực tiếp các runtime thật. Đánh giá chéo của nhóm khác thuộc Phase 3.</p></html>']
    (RESULTS/"report.html").write_text("\n".join(out),encoding="utf-8")
    hashes = report_hashes(RESULTS)
    (RESULTS / "audit-manifest.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
