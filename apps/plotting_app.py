"""Biểu đồ CI95 cho các thí nghiệm E1–E5."""
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import ScalarFormatter
import numpy as np
import pandas as pd

from scenarios.analytical import summarize_replications


# Giữ màu kiến trúc nhất quán qua các hình, thêm kiểu dấu cho bản in đen trắng.
LOOM, BUN, EVENT, BUN_UNIT = "#16678a", "#b35516", "#436447", "#8c528c"
MODELS = {"shared": ("Loom", LOOM, "o"), "partitioned": ("Bun", BUN, "s")}
E1_MODELS = {
    "EventLoop_c1": ("Event loop · c = 1", EVENT, "^"),
    "SpringLoom_c8": ("Loom · c = 8", LOOM, "o"),
    "Bun_c8_k1.0": ("Bun · κ = 1", BUN_UNIT, "D"),
    "Bun_c8_k1.25": ("Bun · κ = 1,25", BUN, "s"),
}
FILES = {
    "E1": "e1_throughput_curves.csv",
    "E2": "e2_capacity_delay.csv",
    "E3": "e3_loom_vs_bun_sensitivity.csv",
    "E4": "e4_closed_loop.csv",
    "E5": "e5_special_scenarios.csv",
}
INK, MUTED = "#172f3a", "#415965"


def read_csv(folder, filename):
    path = Path(folder) / filename
    if not path.is_file():
        raise FileNotFoundError(f"Thiếu {path} trong bộ CSV bàn giao.")
    return pd.read_csv(path)


def seed_note(*frames):
    counts = sorted({n for frame in frames for n in frame["n_seeds"].unique()})
    return "m = " + ", ".join(str(n) for n in counts) + " seed/cấu hình"


def page(title, subtitle, rows=2, height=8.5):
    fig, axes = plt.subplots(rows, 2, figsize=(12, height), squeeze=False)
    fig.subplots_adjust(left=.10, right=.975, top=1-1.68/height, bottom=1.04/height,
                        wspace=.28, hspace=.65)
    fig.text(.08, 1-.32/height, title, fontsize=19, fontweight="bold", color=INK, va="top")
    fig.text(.08, 1-.76/height, subtitle, fontsize=10.5, color=MUTED, va="top")
    return fig, axes


def legend(fig, handles):
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.076, 1-1.02/fig.get_figheight()),
               frameon=False, ncol=len(handles), fontsize=9.2, columnspacing=1.5,
               handlelength=2, borderaxespad=0)


def key(label, color, marker, linestyle="-"):
    return Line2D([], [], color=color, marker=marker, linestyle=linestyle, label=label,
                  markersize=4.8, linewidth=1.7)


def axis(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left", color=INK, fontweight="bold", fontsize=11, pad=8)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(labelsize=8.5, length=3, color=MUTED)
    ax.grid(axis="y", color="#d7e0e5", linewidth=.6)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["bottom", "left"]].set_color("#9aabb2")


def band(ax, rows, x, metric, color, marker, *, xscale=1, scale=1, linestyle="-"):
    """Dùng đúng CI của trung bình giữa các seed, kể cả với p95/p99."""
    rows = rows.sort_values(x)
    if rows.empty or rows[x].duplicated().any():
        raise ValueError(f"Thiếu điểm đo hoặc trùng {x} trong đường {metric}.")
    xs = rows[x].to_numpy(float) * xscale
    mean, low, high = interval(rows, metric, scale)
    ax.fill_between(xs, low, high, color=color, alpha=.16, linewidth=0)
    ax.plot(xs, mean, linestyle=linestyle, color=color, marker=marker, ms=4, lw=1.55)
    ax.vlines(xs, low, high, color=color, linewidth=.75)


def interval(rows, metric, scale=1):
    counts = rows["n_seeds"]
    if counts.isna().any() or counts.lt(2).any():
        raise ValueError(f"CI95 Student của {metric} cần ít nhất hai seed mỗi cấu hình.")
    cols = [f"{metric}_{suffix}" for suffix in ("mean", "ci_low", "ci_high")]
    values = rows[cols].to_numpy(dtype=float).T * scale
    mean, low, high = values
    if not np.isfinite(values).all() or np.any(low > mean) or np.any(mean > high):
        raise ValueError(f"Giá trị hoặc CI95 không hợp lệ cho {metric}.")
    return mean, low, high


def theory(ax, rows, x, metric, color, scale=1):
    # Cột giá trị giải tích để trống khi giả thiết của mô hình không thỏa mãn.
    values = rows.dropna(subset=[f"ana_{metric}"])
    ax.plot(values[x], values[f"ana_{metric}"] * scale, linestyle="none", marker="x",
            ms=7, mew=1.1, color=color, zorder=4)


def save(fig, folder, name, caption):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        fig.text(.08, .28/fig.get_figheight(), caption, color=MUTED, fontsize=8.5, va="bottom")
        for ext in ("png", "pdf"):
            fig.savefig(folder / f"{name}.{ext}", dpi=300, facecolor="white")
    finally:
        plt.close(fig)


def plot_e1_throughput(res_dir="results", fig_dir="results/figures"):
    df = read_csv(res_dir, FILES["E1"])
    fig, axes = page("Thông lượng và độ trễ khi tải tăng",
                     "E1   ·   s = 1 ms, D = 50 ms, K = 100 chỗ/core. Hai mô hình Bun dùng 8 core.",
                     rows=3, height=11.5)
    legend(fig, [key(*style) for style in E1_MODELS.values()] + [key("Giải tích", INK, "x", "none")])
    panels = [
        ("X", "Thông lượng hoàn thành", "X (req/s)", 1),
        ("Pblock", "Xác suất từ chối", "P_block (%)", 100),
        ("R", "Độ trễ trung bình", "R (ms)", 1000),
        ("p99", "Độ trễ phân vị 99", "p99 (ms)", 1000),
    ]
    for ax, (metric, title, ylabel, scale) in zip(axes[:2].flat, panels):
        axis(ax, title, "Tải đến γ (req/s)", ylabel)
        for scenario, (_, color, marker) in E1_MODELS.items():
            rows = df[df.scenario == scenario]
            band(ax, rows, "gamma", metric, color, marker, scale=scale)
            if metric in ("X", "Pblock"):
                theory(ax, rows, "gamma", metric, color, scale)

    grid = axes[2, 0].get_subplotspec().get_gridspec()
    for ax in axes[2]:
        ax.remove()
    heat = fig.add_subplot(grid[2, :])
    util = df.pivot(index="scenario", columns="gamma", values="U_mean").loc[list(E1_MODELS)] * 100
    heat.imshow(util, aspect="auto", cmap="Blues", vmin=0, vmax=100, interpolation="nearest")
    heat.set_xticks(range(len(util.columns)), [f"{g:g}" for g in util.columns])
    heat.set_yticks(range(len(util)), ["Event loop", "Loom", "Bun κ=1", "Bun κ=1,25"])
    heat.set_xlabel("Tải đến γ (req/s)", fontsize=9)
    heat.tick_params(length=0, labelsize=8.5)
    heat.set_title("Mức sử dụng CPU trung bình U (%)", loc="left", color=INK,
                   fontsize=11, fontweight="bold", pad=8)
    for (y, x), value in np.ndenumerate(util.to_numpy()):
        heat.text(x, y, f"{value:.0f}", ha="center", va="center",
                  color="white" if value > 64 else INK, fontsize=8.5)
    for spine in heat.spines.values():
        spine.set_visible(False)
    save(fig, fig_dir, "fig1_e1_throughput",
         f"Đường và dải màu biểu diễn trung bình và CI95 Student giữa các seed ({seed_note(df)}). "
         "Ô nhiệt ghi trung bình, làm tròn đến 1%.")


def plot_e2_capacity(df, folder):
    data = df[df.scenario.str.startswith("sweep_K_")]
    fig, axes = page("Sức chứa hàng CPU và độ trễ đuôi",
                     "E2   ·   γ = 7.500 req/s, c = 8, s = 1 ms, D = 50 ms. Loom κ = 1, Bun κ = 1,25.")
    styles = {"exp": ("CPU mũ", "-"), "det": ("CPU xác định", "--")}
    handles = [key(f"{label}, {desc}", color, marker, ls)
               for label, color, marker in MODELS.values() for desc, ls in styles.values()]
    legend(fig, handles + [key("Giải tích (CPU mũ)", INK, "x", "none")])
    panels = [("Pblock", "Xác suất từ chối", "P_block (%)", 100),
              ("R", "Độ trễ trung bình", "R (ms)", 1000),
              ("p95", "Độ trễ phân vị 95", "p95 (ms)", 1000),
              ("p99", "Độ trễ phân vị 99", "p99 (ms)", 1000)]
    for ax, (metric, title, ylabel, scale) in zip(axes.flat, panels):
        axis(ax, title, "Sức chứa tổng K (request, thang log)", ylabel)
        for arch, (_, color, marker) in MODELS.items():
            for dist, (_, ls) in styles.items():
                rows = data[(data.arch == arch) & (data.dist_cpu == dist)]
                band(ax, rows, "K", metric, color, marker, scale=scale, linestyle=ls)
                if dist == "exp" and metric in ("Pblock", "R"):
                    theory(ax, rows, "K", metric, color, scale)
        ax.set_xscale("log")
        ax.set_xticks(sorted(data.K.unique()))
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.minorticks_off()
    save(fig, folder, "fig2_e2_capacity_delay",
         f"Dải màu biểu diễn CI95 Student ({seed_note(data)}). R, p95 và p99 tính trên các request hoàn thành. "
         "Mỗi phân vị được tính riêng từng seed rồi lấy trung bình.")


def plot_e3_sensitivity(e3, e2, folder):
    fig, axes = page("Độ nhạy của Loom và Bun",
                     "E3 và phép quét c của E2   ·   Tải đến γ tính bằng req/s. Mỗi ô nối các điểm trong cùng một phép quét.")
    legend(fig, [key(*style) for style in MODELS.values()])
    ax = axes[0, 0]
    axis(ax, "Chi phí đồng bộ κ  ·  γ = 7.000, K = 160", "Hệ số κ của Bun", "X (req/s)")
    kappas = e3[e3.scenario.str.contains("_kappa_")]
    bun = kappas[kappas.arch == "partitioned"]
    band(ax, bun, "kappa", "X", BUN, "s")
    loom = kappas[kappas.arch == "shared"]
    if len(loom) != 1:
        raise ValueError("Phép quét κ cần một cấu hình Loom làm mốc.")
    (mean,), (low,), (high,) = interval(loom, "X")
    ax.axhspan(low, high, color=LOOM, alpha=.16, linewidth=0)
    ax.axhline(mean, color=LOOM, ls="--", lw=1.5)
    ax.plot(loom.kappa, [mean], "o", color=LOOM, ms=4)
    ax.set_xticks(sorted(bun.kappa))
    sweeps = [
        (axes[0, 1], e3[e3.scenario.str.contains("_D_")], "D", "R", 1000, 1000,
         "Độ trễ I/O  ·  γ = 6.000, K = 160", "D (ms)", "R (ms)"),
        (axes[1, 0], e3[e3.scenario.str.contains("_s_")], "s", "X", 1000, 1,
         "Thời gian CPU  ·  γ = 6.000, K = 160", "s (ms)", "X (req/s)"),
        (axes[1, 1], e2[e2.scenario.str.startswith("sweep_c_")], "c", "Pblock", 1, 100,
         "Số core  ·  γ = 7.500, K = 200", "Số core c", "P_block (%)"),
    ]
    for ax, data, x, metric, xscale, scale, title, xlabel, ylabel in sweeps:
        axis(ax, title, xlabel, ylabel)
        for arch, (_, color, marker) in MODELS.items():
            band(ax, data[data.arch == arch], x, metric, color, marker, xscale=xscale, scale=scale)
        ax.set_xticks(sorted(data[x].unique() * xscale))
    save(fig, folder, "fig3_e3_sensitivity",
         f"Dải màu biểu diễn CI95 Student ({seed_note(e3, sweeps[-1][1])}). Nét đứt xanh đánh dấu "
         "mốc Loom ở κ = 1.\n"
         "Khi quét D, s hoặc c, Bun dùng κ = 1,25. Ở c = 16, 16 hàng riêng của Bun chứa tổng cộng 192 request.")


def closed_population(e4, raw):
    """Tính C ước lượng trên từng seed để giữ hiệp phương sai của X với R."""
    runs = raw.loc[raw.exp_id == "E4", ["scenario", "seed", "X", "R", "X_err"]].copy()
    if (runs.seed.isna().any() or runs.duplicated(["scenario", "seed"]).any()
            or not np.isfinite(runs[["X", "R", "X_err"]]).all().all()):
        raise ValueError("Dữ liệu seed E4 bị trùng hoặc thiếu chỉ số.")
    counts = runs.groupby("scenario").size()
    sizes = e4.set_index("scenario")["n_seeds"]
    if not counts.sort_index().equals(sizes.sort_index()):
        raise ValueError("Số seed E4 trong raw_seed_runs.csv và e4_closed_loop.csv không khớp.")
    # Cấu hình của schedule_e4_closed_loop: think_time = 0, t_err = 10 ms.
    runs["population"] = runs.X * runs.R + .010 * runs.X_err
    stats = pd.DataFrame.from_dict(
        {scenario: summarize_replications(group.population.tolist())
         for scenario, group in runs.groupby("scenario")}, orient="index")
    return e4.join(stats.add_prefix("population_"), on="scenario", validate="one_to_one")


def plot_e4_closed(e4, raw, folder):
    data = closed_population(e4, raw) if raw is not None else e4
    fig, axes = page("Hệ kín dưới tải đồng thời",
                     "E4   ·   D = 50 ms, s = 1 ms. Think time bằng 0, thời gian chờ sau từ chối bằng 10 ms.",
                     rows=4, height=13)
    fig.subplots_adjust(bottom=1.34 / fig.get_figheight())
    models = {"EventLoop": ("Event loop", EVENT, "^"), "SpringLoom": MODELS["shared"],
              "Bun": MODELS["partitioned"]}
    handles = [key(*style) for style in models.values()]
    panels = [("X", "Thông lượng", "X (req/s)", 1),
              ("X_err", "Tốc độ từ chối", "X_err (req/s)", 1),
              ("Pblock", "Tỷ lệ từ chối ghi trong CSV", "P_block (%)", 100)]
    invalid = ~data.Pblock_mean.between(0, 1)
    if raw is None:
        panels.append(("R", "Độ trễ trung bình", "R (ms)", 1000))
        source_note = "CSV tổng hợp cung cấp CI95 cho R. Phép kiểm tra Little theo seed cần raw_seed_runs.csv."
    else:
        handles.append(key("Giá trị C", INK, "", "--"))
        panels.append(("population", "Kiểm tra định luật Little", "X·R + 0,01·X_err (request)", 1))
        deviation = (100 * (data.population_mean - data.closed_C).abs() / data.closed_C).max()
        percent = f"{deviation:.2f}".replace(".", ",")
        source_note = (f"Sai lệch lớn nhất của ước lượng Little so với C là {percent}% "
                       f"trên {len(data)} cấu hình. Tích X·R tính riêng từng seed.")
    legend(fig, handles)
    for j, (regime, label) in enumerate([("Kfin", "K hữu hạn"), ("Kinf", "K = 10⁹")]):
        part = data[data.scenario.str.contains(f"_{regime}_")]
        for i, (metric, title, ylabel, scale) in enumerate(panels):
            ax = axes[i, j]
            axis(ax, f"{title}  ·  {label}", "Số kết nối đồng thời C", ylabel)
            if metric == "population":
                cs = sorted(part.closed_C.unique())
                ax.plot(cs, cs, ls="--", color=INK, lw=1.1)
            for system, (_, color, marker) in models.items():
                band(ax, part[part.scenario.str.startswith(f"{system}_")], "closed_C", metric, color, marker, scale=scale)
            if metric == "Pblock" and invalid.loc[part.index].any():
                outliers = part[invalid.loc[part.index]]
                ax.axhline(100, color=MUTED, linestyle=":", linewidth=1)
                ax.scatter(outliers.closed_C, 100 * outliers.Pblock_mean, s=60,
                           facecolors="none", edgecolors="#962b2b", zorder=5)
            ax.set_xticks(sorted(part.closed_C.unique()))
            if metric in ("Pblock", "X_err") and part[metric + "_mean"].eq(0).all():
                ax.set_ylim(-.05, 1)
    note = (f"Vòng đỏ đánh dấu {invalid.sum()} giá trị trung bình nằm ngoài miền xác suất [0%, 100%].\n"
            if invalid.any() else "")
    save(fig, folder, "fig4a_e4_closed_loop",
         f"Dải màu biểu diễn CI95 Student ({seed_note(data)}). K hữu hạn bằng 200 cho Event loop và 800 cho Loom/Bun. "
         + "\n" + note + source_note)


def categories(ax, rows, groups, labels):
    """So sánh các kịch bản rời rạc qua điểm trung bình và thanh CI95."""
    xs = np.arange(len(rows))
    offsets = np.linspace(-.13, .13, len(groups)) if len(groups) > 1 else [0]
    for offset, (metric, scale, color, marker) in zip(offsets, groups):
        mean, low, high = interval(rows, metric, scale)
        ax.errorbar(xs + offset, mean, yerr=[mean-low, high-mean], fmt=marker,
                    color=color, ms=6, capsize=4, elinewidth=1.3)
    ax.set_xticks(xs, labels)
    ax.set_xlim(-.5, len(rows)-.5)


def plot_e5_special(df, folder):
    fig, axes = page("Nghẽn ở backend và tác vụ CPU nặng",
                     "E5   ·   S8 giới hạn kết nối backend. S10 tăng 20 lần thời gian CPU trung bình của tác vụ nặng.")
    s8 = df[df.scenario.str.startswith("S8_")].set_index("arch").loc[["shared", "partitioned"]]
    s10_ids = ["S10_EventLoop_no_heavy", "S10_EventLoop_blocked", "S10_SpringLoom_K200", "S10_SpringLoom_isolated"]
    s10 = df.set_index("scenario").loc[s10_ids]
    s8labels = ["Loom · κ=1", "Bun · κ=1,25"]
    s10labels = ["EL · 0%\nK=200", "EL · 5%\nK=200", "Loom · 5%\nK=200", "Loom · 5%\nK=800"]
    legend(fig, [key("Toàn hệ", INK, "o", "none"), key("CPU", BUN, "s", "none"), key("I/O", LOOM, "D", "none")])
    axis(axes[0, 0], "S8  ·  Thông lượng hoàn thành", "Backend giới hạn 300 kết nối", "X (req/s)")
    categories(axes[0, 0], s8, [("X", 1, INK, "o")], s8labels)
    axis(axes[0, 1], "S8  ·  Vị trí từ chối", "Backend giới hạn 300 kết nối", "Từ chối / số đến (%)")
    categories(axes[0, 1], s8, [("Pblock", 100, INK, "o"), ("Pblock_cpu", 100, BUN, "s"),
                                ("Pblock_io", 100, LOOM, "D")], s8labels)
    axis(axes[1, 0], "S10  ·  Xác suất từ chối", "Kiến trúc, tỉ lệ tác vụ nặng và K", "P_block (%)")
    categories(axes[1, 0], s10, [("Pblock", 100, INK, "o")], s10labels)
    axis(axes[1, 1], "S10  ·  Độ trễ phân vị 99", "Kiến trúc, tỉ lệ tác vụ nặng và K", "p99 (ms)")
    categories(axes[1, 1], s10, [("p99", 1000, INK, "o"), ("p99_cpu", 1000, BUN, "s")], s10labels)
    save(fig, folder, "fig4b_e5_bottlenecks",
         f"Điểm và thanh sai số biểu diễn trung bình và CI95 Student ({seed_note(df)}). EL = Event loop. "
         "S8 dùng γ = 7.000 req/s, c = 8, K = 400. S10 dùng γ = 900 req/s.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Plot the four figure groups for experiments E1-E5.")
    parser.add_argument("--results-dir", type=Path, default=Path("results"), help="Input CSV directory")
    parser.add_argument("--fig-dir", type=Path, help="Output directory (default: <results-dir>/figures)")
    args = parser.parse_args(argv)
    dest = args.fig_dir or args.results_dir / "figures"
    try:
        e2, e3, e4, e5 = [read_csv(args.results_dir, FILES[exp]) for exp in ("E2", "E3", "E4", "E5")]
        raw_path = args.results_dir / "raw_seed_runs.csv"
        raw = pd.read_csv(raw_path) if raw_path.is_file() else None
        dest.mkdir(parents=True, exist_ok=True)
        # Chỉ công bố bộ hình sau khi vẽ thành công cả bốn nhóm.
        with TemporaryDirectory(dir=dest) as tmp:
            plot_e1_throughput(args.results_dir, tmp)
            plot_e2_capacity(e2, tmp)
            plot_e3_sensitivity(e3, e2, tmp)
            plot_e4_closed(e4, raw, tmp)
            plot_e5_special(e5, tmp)
            for path in Path(tmp).iterdir():
                path.replace(dest / path.name)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Lỗi vẽ biểu đồ: {exc}\n")
    print(f"Saved 5 PNG figures (300 dpi) and 5 PDF figures to {dest}.")


if __name__ == "__main__":
    main()
