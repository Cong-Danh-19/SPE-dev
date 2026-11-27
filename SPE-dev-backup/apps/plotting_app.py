"""[TV3] Đọc CSV kết quả DES của TV2 và xuất biểu đồ khoa học CI95 cùng phân tích §9–§10."""
import argparse
import sys
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy import stats

RESULTS = Path(__file__).resolve().parents[1] / "results"
FILES = {
    "e1": "e1_throughput_curves.csv",
    "e2": "e2_capacity_delay.csv",
    "e3": "e3_loom_vs_bun_sensitivity.csv",
    "e4": "e4_closed_loop.csv",
    "e5": "e5_special_scenarios.csv",
    "verification": "verification_summary.csv",
}
RAW_SEEDS_FILE = "raw_seed_runs.csv"
PARAMS = (
    "arch", "gamma", "c", "K", "s", "D", "kappa", "dist_cpu", "dist_io",
    "closed_C", "backend_limit", "heavy_prob", "heavy_mult", "routing", "think_time", "t_err",
)
METRICS = (
    "X", "R", "Pblock", "p95", "p99", "U", "X_err", "Wq", "W_cpu",
    "L_cpu", "L_io", "L_sys", "XR", "XRLittle",
)
NON_NEGATIVE = ("Pblock", "X", "X_err", "R", "Wq", "W_cpu", "p95", "p99", "L_cpu", "L_io", "L_sys", "U")
LOAD = "Tải đến γ (req/s)"
BLOCK = "Xác suất từ chối P_block (%)"
DPI = 240

# Bảng màu thống nhất theo hệ thống trên mọi biểu đồ.
COLORS = {
    "event_loop": "#2ca02c",
    "loom": "#1f77b4",
    "bun_1": "#ff7f0e",
    "bun_1.25": "#d62728",
    "bun_1.5": "#9467bd",
    "other": "#8c564b",
}


def require(df, *columns):
    if df.empty:
        raise ValueError("chưa có dòng dữ liệu")
    missing = sorted(set(columns) - set(df))
    if missing:
        raise ValueError("thiếu cột " + ", ".join(missing))


def require_ci(df, *metrics):
    require(df, *(f"{m}_{s}" for m in metrics for s in ("mean", "ci_low", "ci_high")))
    for metric in metrics:
        mean, low, high = (df[metric + s] for s in ("_mean", "_ci_low", "_ci_high"))
        valid = np.isfinite(mean) & np.isfinite(low) & np.isfinite(high) & mean.between(low, high)
        if not valid.all():
            raise ValueError(f"{metric} có {(~valid).sum()} dòng thiếu hoặc sai CI95 (cần ít nhất hai seed)")


def mean_ci(values):
    """Tính trung bình, SD và CI95 t-Student (m-1 bậc tự do) qua các seed độc lập (§3.4)."""
    values = pd.Series(values, dtype=float).dropna()
    m = len(values)
    if m == 0:
        return np.nan, np.nan, np.nan, np.nan
    mean = float(values.mean())
    if m == 1:
        return mean, 0.0, np.nan, np.nan
    std = float(values.std(ddof=1))
    half = float(stats.t.ppf(0.975, m - 1) * std / np.sqrt(m))
    return mean, std, mean - half, mean + half


def deduplicate_shared_pivots(frame, *, extra_keys=(), filename="", notes=None):
    """Gộp các dòng điểm gốc dùng chung giữa hai nhánh quét khi mọi chỉ số đo trùng khớp."""
    keys = [k for k in (*PARAMS, *extra_keys) if k in frame]
    if not keys or not frame.duplicated(keys).any():
        return frame
    check_cols = [
        c for c in frame.columns
        if any(c == m or c == f"{m}_mean" for m in NON_NEGATIVE) and pd.api.types.is_numeric_dtype(frame[c])
    ]
    for _, grp in frame.groupby(keys, dropna=False):
        if len(grp) <= 1:
            continue
        for col in check_cols:
            vals = grp[col].dropna().to_numpy(dtype=float)
            if len(vals) > 1 and not np.allclose(vals, vals[0], rtol=1e-9, atol=1e-11):
                # Giữ nguyên để bước kiểm tra cấu hình báo lỗi khi có hai dòng xung đột thực sự.
                return frame
    dedup = frame.drop_duplicates(subset=keys, keep="first").reset_index(drop=True)
    if notes is not None and filename:
        n_dup = len(frame) - len(dedup)
        notes.append(
            f"{filename} có {n_dup} dòng điểm gốc dùng chung giữa các nhánh quét "
            f"({len(dedup)} cấu hình tham số độc lập trên {len(frame)} dòng CSV); đã gộp điểm trùng khớp."
        )
    return dedup


def aggregate_seeds(frame):
    keys = [k for k in ("exp_id", "scenario", *PARAMS, "level", "K_per_core", "rho_ref") if k in frame]
    if not keys or frame.seed.isna().any() or frame.duplicated(keys + ["seed"]).any():
        raise ValueError("cấu hình/seed thiếu hoặc trùng, không thể tính CI95")
    rows = []
    for _, group in frame.groupby(keys, dropna=False, sort=True):
        row = group.iloc[0][keys].to_dict()
        row["n_seeds"] = len(group)
        for metric in METRICS:
            if metric in group:
                for suffix, value in zip(("mean", "std", "ci_low", "ci_high"), mean_ci(group[metric])):
                    row[f"{metric}_{suffix}"] = value
        for col in (c for c in group if c.startswith("ana_")):
            if group[col].nunique() > 1:
                raise ValueError(f"{col} thay đổi giữa các seed cùng cấu hình")
            row[col] = group[col].max()
        rows.append(row)
    return pd.DataFrame(rows)


def _validate_table_columns(raw):
    text_columns = {
        "exp_id", "scenario", "arch", "dist_cpu", "dist_io", "routing", "dispatcher_type",
        "system", "Model", "Load_Level", "Pass_5pct", "load", "exp",
    }
    for col in raw.columns.difference(text_columns):
        raw[col] = pd.to_numeric(raw[col], errors="raise")
    for col in ("c", "s", "kappa", "gamma"):
        if col in raw:
            values = raw[col].dropna()
            valid = values.ge(0) if col == "gamma" else values.gt(0)
            if not (valid & np.isfinite(values)).all():
                bound = "≥ 0" if col == "gamma" else "> 0"
                raise ValueError(f"{col} phải hữu hạn và {bound}")
    if "arch" in raw and not raw.arch.isin(["shared", "partitioned"]).all():
        raise ValueError("arch phải là shared hoặc partitioned")


def read_csv(path, key, *, notes=None):
    raw = pd.read_csv(path)
    require(raw)
    _validate_table_columns(raw)

    frame = raw.copy()
    seeded = "seed" in raw and any(m in raw for m in METRICS)
    if seeded:
        raw = deduplicate_shared_pivots(raw, extra_keys=("seed",))
        frame = raw.copy()
    else:
        frame = deduplicate_shared_pivots(frame, filename=path.name, notes=notes)
        if "n_seeds" in frame:
            intervals = [col for col in frame if col.endswith(("_ci_low", "_ci_high"))]
            frame.loc[~frame.n_seeds.ge(2), intervals] = np.nan
    if key == "e4":
        # Hệ kín: Sink chờ z sau thành công và t_err sau từ chối; runner TV2 dùng z = 0, t_err = 10 ms (§7.1).
        suffix = "" if seeded else "_mean"
        if {"X" + suffix, "R" + suffix} <= set(frame):
            if "XR" + suffix not in frame:
                frame["XR" + suffix] = frame["X" + suffix] * frame["R" + suffix]
            if "X_err" + suffix in frame and "XRLittle" + suffix not in frame:
                t_err = frame["t_err"] if "t_err" in frame else 0.010
                think = frame["think_time"] if "think_time" in frame else 0.0
                frame["XRLittle" + suffix] = (
                    frame["XR" + suffix] + frame["X_err" + suffix] * t_err + frame["X" + suffix] * think
                )
    if seeded:
        frame = aggregate_seeds(frame)
    return frame, raw


def attach_raw_seeds(input_dir, data, raw, notes):
    """Ghép dữ liệu từng seed từ raw_seed_runs.csv (nếu có) để tính CI95 của tích X·R và kiểm định ghép cặp."""
    seed_path = input_dir / RAW_SEEDS_FILE
    if not seed_path.is_file():
        return
    try:
        seeds_all = pd.read_csv(seed_path)
        require(seeds_all, "exp_id", "seed")
        _validate_table_columns(seeds_all)
    except (OSError, ValueError) as err:
        notes.append(f"{RAW_SEEDS_FILE} — {err}.")
        return

    for key in ("e1", "e2", "e3", "e4", "e5"):
        if data.get(key, pd.DataFrame()).empty:
            continue
        if "seed" in raw.get(key, pd.DataFrame()):
            continue
        sub = seeds_all[seeds_all["exp_id"].astype(str).str.lower() == key].copy()
        if sub.empty:
            continue
        sub = deduplicate_shared_pivots(sub, extra_keys=("seed",))
        raw[key] = sub

        if key == "e4" and {"X", "R"} <= set(sub):
            sub["XR"] = sub["X"] * sub["R"]
            if "X_err" in sub:
                t_err = sub["t_err"] if "t_err" in sub else 0.010
                think = sub["think_time"] if "think_time" in sub else 0.0
                sub["XRLittle"] = sub["XR"] + sub["X_err"] * t_err + sub["X"] * think
            raw[key] = sub
            join_keys = [k for k in PARAMS if k in data["e4"] and k in sub]
            if join_keys and not sub.duplicated([*join_keys, "seed"]).any():
                agg_rows = []
                for _, grp in sub.groupby(join_keys, dropna=False, sort=False):
                    rec = {k: grp.iloc[0][k] for k in join_keys}
                    for m in ("XR", "XRLittle"):
                        if m in grp:
                            for sfx, val in zip(("mean", "std", "ci_low", "ci_high"), mean_ci(grp[m])):
                                rec[f"{m}_{sfx}"] = val
                    agg_rows.append(rec)
                agg_df = pd.DataFrame(agg_rows)
                drop_old = [c for c in agg_df.columns if c not in join_keys and c in data["e4"].columns]
                merged = data["e4"].drop(columns=drop_old).merge(agg_df, on=join_keys, how="left")
                if len(merged) == len(data["e4"]):
                    data["e4"] = merged


def capacity(row):
    return row["c"] / (row["s"] * (row["kappa"] if row["arch"] == "partitioned" else 1.0))


def system_style(row, idx=0):
    """Trả về (mã màu, khóa sắp xếp) thống nhất cho Event loop, Loom và Bun."""
    arch = getattr(row, "arch", row["arch"] if isinstance(row, dict) else "shared")
    c = float(getattr(row, "c", row["c"] if isinstance(row, dict) else 1))
    kappa = float(getattr(row, "kappa", row["kappa"] if isinstance(row, dict) else 1.0))
    if arch == "shared" and c == 1:
        return COLORS["event_loop"], (0, c, 1.0)
    if arch == "shared":
        return COLORS["loom"], (1, c, 1.0)
    if np.isclose(kappa, 1.0):
        return COLORS["bun_1"], (2, c, kappa)
    if np.isclose(kappa, 1.25):
        return COLORS["bun_1.25"], (3, c, kappa)
    if np.isclose(kappa, 1.5):
        return COLORS["bun_1.5"], (4, c, kappa)
    return f"C{idx % 10}", (5, c, kappa)


def groups(df, x, *, omit=()):
    """Nhóm các cấu hình giữ cố định mọi tham số ngoài trục x và sắp theo thứ tự hệ thống."""
    require(df, x, "arch")
    keys = [k for k in PARAMS if k in df and k != x and k not in omit]
    varying = {k for k in keys if df[k].nunique(dropna=False) > 1}
    items = []
    for _, part in df.groupby(keys, dropna=False, sort=True):
        part = part.sort_values(x)
        row = part.iloc[0]
        if row.arch == "partitioned":
            label = "Bun"
        else:
            label = "Hàng chung" if x == "c" else ("Event loop" if row.get("c") == 1 else "Loom")
        symbols = {"gamma": "γ", "kappa": "κ", "dist_cpu": "CPU", "closed_C": "C", "heavy_prob": "p dài"}
        for k in keys:
            if k == "arch" or (k == "kappa" and row.arch == "shared"):
                continue
            if k not in varying and not (row.arch == "partitioned" and k == "kappa"):
                continue
            value = row[k]
            if k == "K" and isinstance(value, (int, float, np.number)) and value >= 10**9:
                value = "∞"
            elif k in ("D", "s", "t_err", "think_time"):
                value = f"{1000 * value:g} ms"
            elif isinstance(value, (int, float, np.number)):
                value = f"{value:g}"
            label += f" · {symbols.get(k, k)}={value}"
        if part[x].duplicated().any():
            raise ValueError(f"{label} có nhiều dòng tại cùng {x}, cần phân biệt cấu hình")
        _, order = system_style(row)
        num_key = tuple(
            (0, float(row[k])) if isinstance(row[k], (int, float, np.number)) and np.isfinite(row[k])
            else (1, str(row[k]))
            for k in keys
        )
        items.append(((*order, num_key, label), label, part))
    for _, label, part in sorted(items, key=lambda item: item[0]):
        yield label, part


def capacity_ticks(ax, levels, label):
    """K = 10⁹ biểu diễn bộ đệm vô hạn trong runner và notebook."""
    ax.set_xticks(range(len(levels)), ["∞" if np.isinf(v) else f"{v:g}" for v in levels])
    ax.set_xlabel(label)


def axis(ax, xlabel, ylabel):
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.grid(alpha=0.25, linestyle="-", linewidth=0.6)
    ax.set_axisbelow(True)


def legend(ax, **kw):
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        by_label = {}
        for h, l in zip(handles, labels):
            by_label.setdefault(l, h)
        defaults = dict(fontsize=8, framealpha=0.92)
        defaults.update(kw)
        ax.legend(by_label.values(), by_label.keys(), **defaults)


def curve(ax, df, x, metric, label, *, color=None, ls="-", marker="o", mfc=None, xscale=1, yscale=1):
    require(df, x, metric + "_mean")
    df = df.sort_values(x)
    xs = df[x].to_numpy(float) * xscale
    ys = df[metric + "_mean"].to_numpy(float) * yscale
    if not (np.isfinite(xs) & np.isfinite(ys)).any():
        raise ValueError(f"{x}/{metric}_mean thiếu giá trị hữu hạn")
    line, = ax.plot(
        xs, ys, linestyle=ls, marker=marker, ms=4.2, lw=1.7,
        label=label, color=color, markerfacecolor=mfc if mfc is not None else color,
    )
    low, high = metric + "_ci_low", metric + "_ci_high"
    if low in df and high in df:
        lo = df[low].to_numpy(float) * yscale
        hi = df[high].to_numpy(float) * yscale
        valid = np.isfinite(lo) & np.isfinite(hi)
        if (valid & ((lo > ys) | (hi < ys))).any():
            raise ValueError(f"CI95 của {metric} không bao giá trị trung bình")
        ax.fill_between(xs, lo, hi, color=line.get_color(), alpha=0.16)
        ax.vlines(xs[valid], lo[valid], hi[valid], color=line.get_color(), lw=0.95)
    return line


def knee(df):
    """Tải đầu tiên trước bước có thông lượng tăng dưới 2% so với bước trước (§9)."""
    ordered = df.sort_values("gamma").dropna(subset=["gamma", "X_mean"])
    x = ordered.X_mean.to_numpy()
    steps = np.flatnonzero((x[:-1] > 0) & (x[1:] < x[:-1] * 1.02))
    if len(steps):
        i = steps[0]
        return ordered.iloc[i], ordered.iloc[i + 1]
    return None


def fig1_throughput(df):
    require(df, "arch", "c", "s", "kappa", "gamma")
    require_ci(df, "X")
    fig, ax = plt.subplots(figsize=(10.2, 6.4), layout="constrained")
    limits = {}
    has_knee = False
    for i, (label, part) in enumerate(groups(df, "gamma")):
        row = part.iloc[0]
        color, _ = system_style(row, i)
        curve(ax, part, "gamma", "X", label, color=color)
        formula = "N/(κ·s)" if row.arch == "partitioned" else ("1/s" if row.c == 1 else "c/s")
        limits.setdefault(capacity(row), set()).add(formula)
        pair = knee(part)
        if pair is not None:
            has_knee = True
            start, confirm = pair
            ax.scatter(
                start.gamma, start.X_mean, s=110, marker="D", facecolors="none",
                edgecolors=color, linewidths=1.5, zorder=5,
            )
            ax.scatter(
                confirm.gamma, confirm.X_mean, s=55, marker="x",
                color=color, linewidths=1.5, zorder=5,
            )

    x_min, x_max = df.gamma.min(), df.gamma.max()
    for cap, formulas in sorted(limits.items()):
        tag = " = ".join(sorted(formulas))
        ax.axhline(cap, ls="--", color="0.45", lw=1.0, zorder=1)
        ax.annotate(
            f"Trần {tag} = {cap:g} req/s",
            xy=(0.99, cap), xycoords=ax.get_yaxis_transform(),
            xytext=(0, 5), textcoords="offset points",
            ha="right", va="bottom", fontsize=8, color="0.28",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.82),
        )

    g = np.array([x_min, x_max])
    ax.plot(g, 0.95 * g, ":", color="0.35", lw=1.3, label="Ngưỡng X = 0,95·γ")

    handles, labels = ax.get_legend_handles_labels()
    if has_knee:
        handles.extend([
            Line2D([], [], ls="none", marker="D", ms=7, mfc="none", mec="0.25", mew=1.4,
                   label="Knee (§9, đầu bước tăng < 2%)"),
            Line2D([], [], ls="none", marker="x", ms=6.5, color="0.25", mew=1.4,
                   label="Tải xác nhận mức tăng < 2%"),
        ])
        labels.extend(["Knee (§9, đầu bước tăng < 2%)", "Tải xác nhận mức tăng < 2%"])
    handles.append(Line2D([], [], ls="--", color="0.45", lw=1.0, label="Trần lý thuyết CPU"))
    labels.append("Trần lý thuyết CPU")

    axis(ax, LOAD, "Thông lượng thành công X (req/s)")
    ax.set_title("Hình 1. Thông lượng X và điểm bão hòa theo tải γ (CI95)")
    ax.legend(handles, labels, fontsize=8, framealpha=0.92, loc="upper left")
    return fig


def fig2_latency(df):
    require_ci(df, "R", "p95", "p99")
    fig, axes = plt.subplots(3, 1, figsize=(9.4, 9.2), sharex=True, layout="constrained")
    series = list(groups(df, "gamma"))
    x_max = df.gamma.max()
    for ax, metric, name in zip(axes, ["R", "p95", "p99"], ["trung bình", "p95", "p99"]):
        for i, (label, part) in enumerate(series):
            color, _ = system_style(part.iloc[0], i)
            curve(ax, part, "gamma", metric, label, color=color, yscale=1000)
        if metric in ("R", "p99"):
            level = 100 if metric == "R" else 300
            ax.axhline(level, color="0.35", ls="--", lw=1.1)
            ax.annotate(
                f"Ngưỡng {level} ms",
                xy=(x_max, level), xytext=(-6, 4), textcoords="offset points",
                ha="right", fontsize=8, color="0.28",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8),
            )
        axis(ax, LOAD if metric == "p99" else "", f"R {name} (ms)")
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(Line2D([], [], ls="--", color="0.35", lw=1.1))
    labels.append("Ngưỡng §1.3 (100 ms / 300 ms)")
    fig.suptitle("Hình 2. Thời gian phản hồi trung bình, p95 và p99 theo tải γ (CI95)")
    fig.legend(handles, labels, loc="outside lower center", ncol=3, fontsize=8.2, frameon=True, framealpha=0.95)
    return fig


def fig3_blocking(e1, e2, notes):
    panels = []
    for df, x, source, xlabel in [
        (e1, "gamma", "E1 CSV", LOAD),
        (e2, "K", "E2 CSV", "Tổng sức chứa CPU K (request)"),
    ]:
        try:
            require(df, "gamma", x, "ana_Pblock")
            exp = df[df.ana_Pblock.notna()]
            require_ci(exp, "Pblock")
            series = sweeps(exp, x) or list(groups(exp, x))
            panels.append((x, xlabel, series))
            if x == "K" and exp.gamma.nunique() > 1:
                by_load = sweeps(exp, "gamma")
                if by_load:
                    panels.append(("gamma", LOAD, by_load))
        except ValueError as err:
            notes.append(f"Hình 3, {source} — {err}.")
    if not panels:
        raise ValueError("thiếu lát cắt có Pblock mô phỏng và giải tích")
    fig, axes = plt.subplots(
        len(panels), 1, figsize=(10, 4.0 * len(panels)), squeeze=False, layout="constrained"
    )
    for ax, (x, xlabel, series) in zip(axes.flat, panels):
        discrete = x == "K" and any((part.K >= 10**9).any() for _, part in series)
        levels = sorted({v if v < 10**9 else np.inf for _, part in series for v in part.K}) if discrete else []
        for i, (label, part) in enumerate(series):
            color, _ = system_style(part.iloc[0], i)
            fixed, fixed_label = ("K", "K") if x == "gamma" else ("gamma", "γ")
            if fixed in part and f"{fixed_label}=" not in label:
                fval = part[fixed].iloc[0]
                fstr = "∞" if fixed == "K" and fval >= 10**9 else f"{fval:g}"
                label += f" · {fixed_label}={fstr}"
            plot_x = x
            if discrete:
                part = part.assign(position=part.K.clip(upper=10**9).replace(10**9, np.inf).map(levels.index))
                plot_x = "position"
            part = part.sort_values(plot_x)
            curve(ax, part, plot_x, "Pblock", label, color=color, yscale=100)
            ax.plot(part[plot_x], 100 * part.ana_Pblock, "x--", ms=4.5, lw=1.1, color=color)
        ax.plot([], [], "x--", color="0.35", label="Giải tích (cùng màu với mô phỏng)")
        ax.axhline(1, color="0.35", ls=":", lw=1.2, label="Ngưỡng 1%")
        axis(ax, xlabel, BLOCK)
        if discrete:
            capacity_ticks(ax, levels, xlabel)
        legend(ax)
    fig.suptitle("Hình 3. Xác suất từ chối P_block theo tải γ và sức chứa K (CI95 vs giải tích)")
    return fig


def fig4_utilization(e1, e3, notes):
    panels = []
    for source, df in [("Quét tải (E1)", e1), ("Quét tham số (E3)", e3)]:
        try:
            require(df, "U_mean", "gamma")
            df = df.dropna(subset=["U_mean", "gamma"])
            items = list(groups(df, "gamma"))
            if not items:
                raise ValueError("chưa có cấu hình")
            if not {"U_ci_low", "U_ci_high"} <= set(df):
                notes.append(f"Hình 4, {source} — thiếu U_ci_low hoặc U_ci_high, ô chỉ ghi U trung bình.")
            panels.append((source, items, sorted(df.gamma.dropna().unique())))
        except ValueError as err:
            notes.append(f"Hình 4, {source} — {err}.")
    if not panels:
        raise ValueError("thiếu U_mean theo cấu hình và tải")

    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#efefef")
    sizes = [max(2.6, 0.50 * len(items) + 1.4) for _, items, _ in panels]
    max_cols = max(len(loads) for _, _, loads in panels)
    width = max(10.0, 4.3 + 0.86 * max_cols)
    cell_fs = 6.7 if max_cols >= 11 else 7.2
    fig, axes = plt.subplots(
        len(panels), 1, figsize=(width, sum(sizes)), squeeze=False,
        height_ratios=sizes, layout="constrained",
    )
    for ax, (source, items, loads) in zip(axes.flat, panels):
        matrix = np.full((len(items), len(loads)), np.nan)
        for i, (_, part) in enumerate(items):
            for row in part.itertuples():
                j = loads.index(row.gamma)
                matrix[i, j] = 100.0 * row.U_mean
                if np.isfinite(row.U_mean):
                    text = f"{100 * row.U_mean:.1f}"
                    lo, hi = getattr(row, "U_ci_low", np.nan), getattr(row, "U_ci_high", np.nan)
                    if np.isfinite(lo) and np.isfinite(hi):
                        text += f"\n[{100 * lo:.1f}, {100 * hi:.1f}]"
                    ax.text(
                        j, i, text, ha="center", va="center", fontsize=cell_fs,
                        color="white" if row.U_mean < 0.48 else "black",
                    )
        for i in range(len(items)):
            for j in range(len(loads)):
                if np.isnan(matrix[i, j]):
                    ax.text(j, i, "—", ha="center", va="center", fontsize=8, color="0.55")
        img = ax.imshow(matrix, aspect="auto", vmin=0, vmax=100, cmap=cmap, interpolation="nearest")
        ax.set(
            xticks=range(len(loads)), xticklabels=[f"{g:g}" for g in loads], xlabel=LOAD,
            yticks=range(len(items)), yticklabels=[label for label, _ in items], title=source,
        )
    fig.colorbar(img, ax=list(axes.flat), label="Hiệu suất CPU U (%)", shrink=0.82)
    fig.suptitle("Hình 4. Bản đồ nhiệt hiệu suất CPU U theo hệ và tải · ô ghi U (%) và [CI95]")
    return fig


def fig6_capacity(df):
    require(df, "gamma", "arch", "c", "K", "s", "kappa")
    require_ci(df, "Pblock")
    work = df.copy()
    work["q"] = (work.K / work.c).mask(work.K >= 10**9, np.inf)
    work["rho_ref"] = (work.gamma / work.apply(capacity, axis=1)).round(10)

    # Kiểm tra lưới đầy đủ c × K/c ở cùng ρ_ref (§8 E4); nếu là hai lát cắt OFAT (quét K và quét c) thì vẽ 2 khung song song.
    grid_panels = [
        ((arch, rho), frame)
        for (arch, rho), frame in work.groupby(["arch", "rho_ref"], sort=True)
        if frame["q"].nunique() >= 2 and frame["c"].nunique() >= 2
    ]
    if grid_panels:
        fig, axes = plt.subplots(
            len(grid_panels), 1, figsize=(9.2, 3.8 * len(grid_panels)), squeeze=False, layout="constrained"
        )
        for ax, ((arch, rho), frame) in zip(axes.flat, grid_panels):
            levels = sorted(frame.q.unique())
            for i, (label, part) in enumerate(sweeps(frame, "q", omit=("K", "gamma"))):
                row = part.iloc[0]
                color, _ = system_style(row, i)
                is_det = str(getattr(row, "dist_cpu", "exp")) == "det"
                if "c=" not in label:
                    label += f" · c={row.c:g}"
                curve(
                    ax, part.assign(position=part.q.map(levels.index)), "position", "Pblock",
                    label, color=color, ls="--" if is_det else "-", marker="s" if is_det else "o",
                    mfc="white" if is_det else color, yscale=100,
                )
            ax.axhline(1, color="0.35", ls=":", lw=1.2, label="Ngưỡng 1%")
            ax.set_title(f"{'Hàng riêng (Bun)' if arch == 'partitioned' else 'Hàng chung (Loom)'} · ρ_ref = {rho:g}")
            axis(ax, "Sức chứa trên mỗi core K/c (request/core)", BLOCK)
            capacity_ticks(ax, levels, ax.get_xlabel())
            legend(ax)
        fig.suptitle("Hình 6. Xác suất từ chối P_block theo số core c và sức chứa K/c (CI95)")
        return fig

    k_sweeps = sweeps(work, "K", omit=("q", "rho_ref"))
    c_sweeps = sweeps(work, "c", omit=("q", "rho_ref"))
    if not k_sweeps and not c_sweeps:
        raise ValueError("cần ít nhất hai mức K hoặc hai mức c để vẽ Hình 6")

    ncols = int(bool(k_sweeps)) + int(bool(c_sweeps))
    fig, axes = plt.subplots(1, ncols, figsize=(5.8 * ncols, 4.9), squeeze=False, layout="constrained")
    col_idx = 0

    if k_sweeps:
        ax_k = axes[0, col_idx]
        col_idx += 1
        q_levels = sorted({v for _, p in k_sweeps for v in (p.K / p.c).mask(p.K >= 10**9, np.inf)})
        for i, (label, part) in enumerate(k_sweeps):
            row = part.iloc[0]
            color, _ = system_style(row, i)
            is_det = str(getattr(row, "dist_cpu", "exp")) == "det"
            q_vals = (part.K / part.c).mask(part.K >= 10**9, np.inf)
            curve(
                ax_k, part.assign(position=q_vals.map(q_levels.index)), "position", "Pblock",
                label, color=color, ls="--" if is_det else "-", marker="s" if is_det else "o",
                mfc="white" if is_det else color, yscale=100,
            )
        ax_k.axhline(1, color="0.35", ls=":", lw=1.2, label="Ngưỡng 1%")
        c0, g0 = k_sweeps[0][1]["c"].iloc[0], k_sweeps[0][1]["gamma"].iloc[0]
        ax_k.set_title(f"Quét sức chứa K/c (cố định c={c0:g}, γ={g0:g} req/s)")
        axis(ax_k, "Sức chứa trên mỗi core K/c (request/core)", BLOCK)
        capacity_ticks(ax_k, q_levels, ax_k.get_xlabel())
        legend(ax_k)

    if c_sweeps:
        ax_c = axes[0, col_idx]
        c_levels = sorted({int(v) if float(v).is_integer() else float(v) for _, p in c_sweeps for v in p.c})
        has_ana = False
        for i, (label, part) in enumerate(c_sweeps):
            row = part.iloc[0]
            color = COLORS["loom"] if row.arch == "shared" else system_style(row, i)[0]
            pos_part = part.assign(position=part.c.map(c_levels.index))
            curve(ax_c, pos_part, "position", "Pblock", label, color=color, yscale=100)
            if "ana_Pblock" in pos_part and pos_part["ana_Pblock"].notna().all():
                has_ana = True
                ax_c.plot(pos_part["position"], 100 * pos_part["ana_Pblock"], "x--", ms=4.5, lw=1.1, color=color)
        if has_ana:
            ax_c.plot([], [], "x--", color="0.35", label="Giải tích (cùng màu)")
        ax_c.axhline(1, color="0.35", ls=":", lw=1.2, label="Ngưỡng 1%")
        k0, g0 = c_sweeps[0][1]["K"].iloc[0], c_sweeps[0][1]["gamma"].iloc[0]
        k_str = "∞" if k0 >= 10**9 else f"{k0:g}"
        ax_c.set_title(f"Quét số core c (cố định K={k_str}, γ={g0:g} req/s)")
        ax_c.set_xticks(range(len(c_levels)), [f"{v:g}" for v in c_levels])
        axis(ax_c, "Số core / worker c", BLOCK)
        legend(ax_c)

    fig.suptitle("Hình 6. Xác suất từ chối P_block theo sức chứa K/c và số core c (CI95)")
    return fig


def fig8_verification(df, path):
    base_cols = [
        "Model", "n_seeds", "Sim_X", "Ana_X", "Err_X_pct",
        "Sim_Pblock", "Ana_Pblock", "Sim_L", "Ana_L", "Err_L_pct", "Pass_5pct",
    ]
    require(df, *base_cols)
    order = {"M/M/1": 0, "M/M/1/K": 1, "M/M/c": 2, "M/M/c/K": 3, "M/M/c/c": 4, "M/M/inf": 5}
    lvl_order = {"low": 0, "mid": 1, "high": 2}
    lvl_label = {"low": "Thấp", "mid": "Trung bình", "high": "Cao"}

    rich = {
        "Load_Level", "gamma", "c", "K", "Sim_W", "Ana_W", "Err_W_pct",
        "X_ci_low", "X_ci_high", "W_ci_low", "W_ci_high",
        "L_ci_low", "L_ci_high", "Pblock_ci_low", "Pblock_ci_high",
    } <= set(df)

    work = df.assign(
        _mord=df["Model"].map(lambda m: order.get(m, 99)),
        _lord=df["Load_Level"].map(lambda l: lvl_order.get(str(l).lower(), 99)) if "Load_Level" in df else 0,
    ).sort_values(["_mord", "_lord", "Model"])

    if not rich:
        lines = [
            "# Hình 8. Đối chiếu mô phỏng với giải tích theo node",
            "",
            "X tính bằng req/s, L tính bằng request (`L_IO` cho `M/M/inf`, `L_CPU` cho các node còn lại). "
            "Xác suất và sai số tương đối tính bằng %.",
            "",
            "| Node | Seed (m) | X mô phỏng | X giải tích | δX (%) | P_block mô phỏng (%) | P_block giải tích (%) | δP_block (%) | L mô phỏng | L giải tích | δL (%) | Đạt < 5% |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
        ]
        n_pass = 0
        for r in work.itertuples():
            err = f"{100 * abs(r.Sim_Pblock - r.Ana_Pblock) / r.Ana_Pblock:.3g}" if r.Ana_Pblock > 0 else "—"
            flag = str(r.Pass_5pct).lower()
            passed = {"true": "Đạt", "false": "Chưa đạt"}.get(flag, "—")
            if flag == "true":
                n_pass += 1
            lines.append(
                f"| {r.Model} | {r.n_seeds:g} | {r.Sim_X:g} | {r.Ana_X:g} | {r.Err_X_pct:g} "
                f"| {100 * r.Sim_Pblock:g} | {100 * r.Ana_Pblock:g} | {err} | {r.Sim_L:g} "
                f"| {r.Ana_L:g} | {r.Err_L_pct:g} | {passed} |"
            )
        max_ex, max_el = work["Err_X_pct"].max(), work["Err_L_pct"].max()
        lines.extend([
            "",
            f"Tổng hợp: {n_pass}/{len(work)} cấu hình đạt cờ `Pass_5pct` (δX max = {max_ex:.3g}%, δL max = {max_el:.3g}%).",
        ])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    lines = [
        "# Hình 8. Đối chiếu mô phỏng với giải tích trên 6 mô hình hàng đợi chuẩn (§8.1)",
        "",
        "Mỗi mô hình được kiểm chứng ở **3 mức tải** (Thấp, Trung bình, Cao) với `m` hạt giống độc lập. "
        "`X` tính bằng req/s; `W` tính bằng ms (`R` cho `M/M/inf`, `W_CPU` cho 5 mô hình CPU); "
        "`L` tính bằng request (`L_IO` cho `M/M/inf`, `L_CPU` cho 5 mô hình CPU); `P_block` tính bằng %. "
        "Cờ `Pass_5pct` yêu cầu đồng thời `δX < 5%`, `δW < 5%`, `δL < 5%` và sai lệch `P_block` đạt ngưỡng (`|ΔP_block| < 1` điểm % hoặc `δP_block < 5%`).",
        "",
        r"| Mô hình | Tải (γ req/s) | (c, K) | m | X mô phỏng [CI95] / Lý thuyết (δX%) | W mô phỏng [CI95] / Lý thuyết ms (δW%) | L mô phỏng [CI95] / Lý thuyết (δL%) | P_block mô phỏng [CI95] / Lý thuyết % (\|ΔP_b\| đ.%) | Kết quả |",
        "| --- | --- | :---: | ---: | --- | --- | --- | --- | :---: |",
    ]
    n_pass = 0
    in_ci = {"X": 0, "W": 0, "L": 0, "Pblock": 0}
    for r in work.itertuples():
        flag = str(r.Pass_5pct).lower() == "true"
        if flag:
            n_pass += 1
        if r.X_ci_low - 1e-9 <= r.Ana_X <= r.X_ci_high + 1e-9:
            in_ci["X"] += 1
        if r.W_ci_low - 1e-9 <= r.Ana_W <= r.W_ci_high + 1e-9:
            in_ci["W"] += 1
        if r.L_ci_low - 1e-9 <= r.Ana_L <= r.L_ci_high + 1e-9:
            in_ci["L"] += 1
        if r.Pblock_ci_low - 1e-9 <= r.Ana_Pblock <= r.Pblock_ci_high + 1e-9:
            in_ci["Pblock"] += 1

        k_str = "∞" if r.K >= 10**9 else f"{r.K:g}"
        c_str = "∞" if r.Model == "M/M/inf" else f"{r.c:g}"
        lvl_txt = lvl_label.get(str(r.Load_Level).lower(), str(r.Load_Level))
        abs_pb_pct = 100 * abs(r.Sim_Pblock - r.Ana_Pblock)

        x_cell = f"{r.Sim_X:.2f} [{r.X_ci_low:.2f}, {r.X_ci_high:.2f}] / {r.Ana_X:.2f} ({r.Err_X_pct:.3g}%)"
        w_cell = (
            f"{1000 * r.Sim_W:.3f} [{1000 * r.W_ci_low:.3f}, {1000 * r.W_ci_high:.3f}] "
            f"/ {1000 * r.Ana_W:.3f} ({r.Err_W_pct:.3g}%)"
        )
        l_cell = f"{r.Sim_L:.3f} [{r.L_ci_low:.3f}, {r.L_ci_high:.3f}] / {r.Ana_L:.3f} ({r.Err_L_pct:.3g}%)"
        pb_cell = (
            f"{100 * r.Sim_Pblock:.3f} [{100 * r.Pblock_ci_low:.3f}, {100 * r.Pblock_ci_high:.3f}] "
            f"/ {100 * r.Ana_Pblock:.3f} ({abs_pb_pct:.3g})"
        )
        lines.append(
            f"| {r.Model} | {lvl_txt} ({r.gamma:g}) | ({c_str}, {k_str}) | {r.n_seeds:g} "
            f"| {x_cell} | {w_cell} | {l_cell} | {pb_cell} | {'Đạt' if flag else 'Chưa đạt'} |"
        )

    pos_pb5 = work[work["Ana_Pblock"] >= 0.05]
    rel_pb5_max = (
        float((100 * (pos_pb5["Sim_Pblock"] - pos_pb5["Ana_Pblock"]).abs() / pos_pb5["Ana_Pblock"]).max())
        if not pos_pb5.empty else 0.0
    )
    lines.extend([
        "",
        f"**Tổng hợp kiểm chứng ({len(work)} cấu hình = 6 mô hình × 3 mức tải):**",
        f"- **Đạt ngưỡng sai số (`Pass_5pct`):** `{n_pass}/{len(work)}` cấu hình đạt đồng thời trên cả 4 đại lượng (`δX max = {work['Err_X_pct'].max():.3g}%`, `δW max = {work['Err_W_pct'].max():.3g}%`, `δL max = {work['Err_L_pct'].max():.3g}%`, `|ΔP_block| max = {100 * work['AbsErr_Pblock'].max():.3g}` điểm % < 1 điểm %; với các cấu hình `Ana_Pblock ≥ 5%`, `δP_block max = {rel_pb5_max:.3g}%`).",
        f"- **Độ phủ CI95 chứa giá trị lý thuyết:** `X`: `{in_ci['X']}/{len(work)}`, `L`: `{in_ci['L']}/{len(work)}`, `P_block`: `{in_ci['Pblock']}/{len(work)}`, `W`: `{in_ci['W']}/{len(work)}` (ba dòng `M/M/inf` có `W` mô phỏng ≈ `50,147 ms` so với `50,000 ms`, lệch chỉ `0,295%` do phương sai mẫu hữu hạn trên cùng tập seed `1..15`).",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sweeps(df, factor, *, omit=()):
    """Chỉ nối các cấu hình giữ nguyên mọi tham số khác khi thay đổi factor."""
    if df.empty:
        return []
    return [
        (name, part.sort_values(factor))
        for name, part in groups(df, factor, omit=omit)
        if part[factor].nunique() >= 2
    ]


def fig5_delay(df):
    require(df, "arch", "c", "K", "gamma", "kappa", "s", "D")
    require_ci(df, "R")
    series = sweeps(df, "D")
    if not series:
        raise ValueError("cần ít nhất hai mức D ở cùng cấu hình CPU và tải γ")
    fig, (latency, offset) = plt.subplots(1, 2, figsize=(11.2, 4.8), layout="constrained")
    has_wcpu = False
    for i, (name, part) in enumerate(series):
        color, _ = system_style(part.iloc[0], i)
        curve(latency, part, "D", "R", name, xscale=1000, yscale=1000, color=color)
        shift = part.copy()
        # D là hằng số tại mỗi cấu hình nên CI(R − D) = CI(R) − D.
        for suffix in ("mean", "ci_low", "ci_high"):
            shift[f"R_{suffix}"] -= shift["D"]
        curve(offset, shift, "D", "R", name, xscale=1000, yscale=1000, color=color)
        if "W_cpu_mean" in part and part["W_cpu_mean"].notna().any():
            has_wcpu = True
            offset.plot(part["D"] * 1000, part["W_cpu_mean"] * 1000, ":", lw=1.4, color=color)
    d = pd.concat([part["D"] for _, part in series]) * 1000
    latency.plot([d.min(), d.max()], [d.min(), d.max()], "--", color="0.4", label="Đường R = D")
    if has_wcpu:
        offset.plot([], [], ":", lw=1.4, color="0.35", label="W_CPU đo tại trạm (cùng màu)")
    for ax, ylabel in [(latency, "Thời gian phản hồi R (ms)"), (offset, "Phần chênh R − D (ms)")]:
        axis(ax, "Độ trễ I/O D (ms)", ylabel)
        legend(ax)
    fig.suptitle("Hình 5. Ảnh hưởng của độ trễ I/O D (R tăng đúng D; phần chênh là W_CPU)")
    return fig


def fig_loom_vs_bun(df):
    """So sánh trực tiếp hàng chung (Spring Loom) với hàng riêng (Bun) trên cùng trục X, P_block, R."""
    require(df, "arch", "c", "K", "gamma", "s", "D", "kappa")
    require_ci(df, "X", "Pblock", "R")
    matched = []
    for (gamma, c, s, D), sub in df.groupby(["gamma", "c", "s", "D"], sort=True):
        if c <= 1:
            continue
        k_series = sweeps(sub, "K")
        archs = {p["arch"].iloc[0] for _, p in k_series}
        if {"shared", "partitioned"} <= archs:
            sub_k = pd.concat([p for _, p in k_series], ignore_index=True)
            matched.append(((gamma, c, s, D), sub_k))
    if not matched:
        raise ValueError("thiếu cặp cấu hình Loom (shared) và Bun (partitioned) cùng γ, c, s, D và ≥ 2 mức K")
    (gamma, c, s, D), sub = matched[0]
    discrete = (sub["K"] >= 10**9).any()
    levels = sorted({v if v < 10**9 else np.inf for v in sub["K"]}) if discrete else []

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.7), layout="constrained")
    specs = [
        ("X", "Thông lượng thành công X (req/s)", 1.0),
        ("Pblock", BLOCK, 100.0),
        ("R", "Thời gian phản hồi trung bình R (ms)", 1000.0),
    ]
    series = list(groups(sub, "K"))
    for ax, (metric, ylabel, scale) in zip(axes, specs):
        for i, (label, part) in enumerate(series):
            row = part.iloc[0]
            color, _ = system_style(row, i)
            is_det = str(getattr(row, "dist_cpu", "exp")) == "det"
            plot_x = "K"
            if discrete:
                part = part.assign(position=part.K.clip(upper=10**9).replace(10**9, np.inf).map(levels.index))
                plot_x = "position"
            curve(
                ax, part, plot_x, metric, label, color=color,
                ls="--" if is_det else "-", marker="s" if is_det else "o",
                mfc="white" if is_det else color, yscale=scale,
            )
        if metric == "X":
            ax.axhline(gamma, color="0.4", ls=":", lw=1.1, label=f"Tải đến γ = {gamma:g}")
        elif metric == "Pblock":
            ax.axhline(1, color="0.35", ls=":", lw=1.2, label="Ngưỡng 1%")
        elif metric == "R":
            ax.axhline(100, color="0.35", ls=":", lw=1.2, label="Ngưỡng 100 ms")
        axis(ax, "Tổng sức chứa CPU K (request)", ylabel)
        if discrete:
            capacity_ticks(ax, levels, ax.get_xlabel())
    handles, labels = axes[0].get_legend_handles_labels()
    # Chỉ giữ các chuỗi hệ thống trong legend chung, còn đường ngưỡng gắn nhãn trực tiếp cạnh đường.
    sys_h = [h for h, l in zip(handles, labels) if not l.startswith("Tải đến")]
    sys_l = [l for l in labels if not l.startswith("Tải đến")]
    for ax, y_line, tag, dy, va in [
        (axes[0], gamma, f"Tải γ = {gamma:g} req/s", -6, "top"),
        (axes[1], 1.0, "Ngưỡng 1%", 5, "bottom"),
        (axes[2], 100.0, "Ngưỡng 100 ms", -6, "top"),
    ]:
        ax.annotate(
            tag, xy=(0.985, y_line), xycoords=ax.get_yaxis_transform(),
            xytext=(0, dy), textcoords="offset points", ha="right", va=va,
            fontsize=7.8, color="0.28",
            bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.84),
        )
    fig.suptitle(
        f"So sánh trực tiếp Spring Loom và Bun theo sức chứa K (c={c:g}, γ={gamma:g} req/s, s={1000*s:g} ms, D={1000*D:g} ms, CI95)"
    )
    fig.legend(sys_h, sys_l, loc="outside lower center", ncol=min(4, len(sys_l)), fontsize=8.2, framealpha=0.95)
    return fig


def fig_kappa(df):
    require(df, "arch", "s", "c", "K", "gamma", "D", "kappa")
    require_ci(df, "X")
    series = sweeps(df[df["arch"] == "partitioned"], "kappa")
    if not series:
        raise ValueError("cần ít nhất hai mức κ của Bun ở cùng cấu hình và tải γ")
    has_pb = {"Pblock_mean", "Pblock_ci_low", "Pblock_ci_high"} <= set(df)
    ncols = 2 if has_pb else 1
    fig, axes = plt.subplots(1, ncols, figsize=(5.9 * ncols, 4.8), squeeze=False, layout="constrained")
    ax_x = axes[0, 0]

    # Tìm mốc đối chứng Spring Loom (shared, κ=1) có cùng (γ, c, K, s, D) nếu có trong CSV E3.
    ref_row = series[0][1].iloc[0]
    loom_ref = df[
        (df["arch"] == "shared")
        & np.isclose(df["gamma"], ref_row["gamma"])
        & (df["c"] == ref_row["c"])
        & (df["K"] == ref_row["K"])
        & np.isclose(df["s"], ref_row["s"])
        & np.isclose(df["D"], ref_row["D"])
    ]

    for i, (name, part) in enumerate(series):
        color = COLORS["bun_1"] if i == 0 else f"C{i % 10}"
        curve(ax_x, part, "kappa", "X", name, color=color)
        ax_x.plot(
            part["kappa"], part.apply(capacity, axis=1), "--", color=color,
            label="Trần N/(κ·s)" if i == 0 else "_nolegend_",
        )
        if i == 0:
            ax_x.axhline(part["gamma"].iloc[0], ls=":", color="0.45", lw=1.1,
                         label=f"Tải đến γ = {part['gamma'].iloc[0]:g} req/s")
    if not loom_ref.empty:
        lr = loom_ref.iloc[0]
        ax_x.axhline(lr["X_mean"], ls="-.", color=COLORS["loom"], lw=1.4,
                     label=f"Loom hàng chung (κ=1): {lr['X_mean']:.0f} req/s")
    axis(ax_x, "Hệ số chi phí CPU κ (không thứ nguyên)", "Thông lượng thành công X (req/s)")
    legend(ax_x)

    if has_pb:
        ax_p = axes[0, 1]
        for i, (name, part) in enumerate(series):
            color = COLORS["bun_1"] if i == 0 else f"C{i % 10}"
            curve(ax_p, part, "kappa", "Pblock", name, color=color, yscale=100)
        if not loom_ref.empty and "Pblock_mean" in loom_ref:
            lr = loom_ref.iloc[0]
            ax_p.axhline(100 * lr["Pblock_mean"], ls="-.", color=COLORS["loom"], lw=1.4,
                         label=f"Loom hàng chung (κ=1): {100 * lr['Pblock_mean']:.2f}%")
        ax_p.axhline(1, ls=":", color="0.35", lw=1.2, label="Ngưỡng 1%")
        axis(ax_p, "Hệ số chi phí CPU κ (không thứ nguyên)", BLOCK)
        legend(ax_p)

    fig.suptitle("Độ nhạy của Bun theo hệ số chi phí đồng bộ κ và mốc đối chứng Loom (CI95)")
    return fig


def fig_service(df):
    require(df, "gamma", "s", "D", "arch", "K", "c", "kappa")
    require_ci(df, "X", "Wq")
    # Ưu tiên lát cắt E3 §8 với γ·s = 0,8; nếu không có thì xét lát cắt cố định γ và D của runner E3.
    work = df.assign(_gs=(df["gamma"] * df["s"]).round(8))
    preferred = work[np.isclose(work["_gs"], 0.8)]
    series = sweeps(preferred, "s", omit=("gamma", "_gs"))
    load_desc = "γ = 0,8/s"
    if not series:
        series = sweeps(df, "s")
        if series:
            g_vals = sorted({p["gamma"].iloc[0] for _, p in series})
            load_desc = f"γ = {g_vals[0]:g} req/s" if len(g_vals) == 1 else "cùng tải γ"
    if not series:
        for gs, block in work.groupby("_gs", sort=True):
            cand = sweeps(block, "s", omit=("gamma", "_gs"))
            if cand:
                series, load_desc = cand, f"γ·s = {gs:g}"
                break
    if not series:
        raise ValueError("thiếu quét s với D cố định (cần ≥ 2 mức s)")

    has_pb = {"Pblock_mean", "Pblock_ci_low", "Pblock_ci_high"} <= set(df)
    specs = [
        ("X", "Thông lượng thành công X (req/s)", 1.0),
        ("Wq", "Thời gian chờ hàng CPU W_q (ms)", 1000.0),
    ]
    if has_pb:
        specs.append(("Pblock", BLOCK, 100.0))
    fig, axes = plt.subplots(1, len(specs), figsize=(4.5 * len(specs), 4.7), layout="constrained")
    for ax, (metric, unit, scale) in zip(np.atleast_1d(axes), specs):
        for i, (name, part) in enumerate(series):
            color, _ = system_style(part.iloc[0], i)
            curve(ax, part, "s", metric, name, xscale=1000, yscale=scale, color=color)
            if metric == "X":
                s_grid = np.linspace(part["s"].min(), part["s"].max(), 80)
                r0 = part.iloc[0]
                eff_k = r0["kappa"] if r0["arch"] == "partitioned" else 1.0
                ax.plot(1000 * s_grid, r0["c"] / (eff_k * s_grid), "--", lw=1.0, alpha=0.65, color=color,
                        label="Trần c/(κ·s)" if i == 0 else "_nolegend_")
        if metric == "Pblock":
            ax.axhline(1, ls=":", color="0.35", lw=1.2, label="Ngưỡng 1%")
        axis(ax, "Thời gian phục vụ CPU s (ms)", unit)
        legend(ax)
    fig.suptitle(f"Độ nhạy theo thời gian phục vụ CPU s ở tải {load_desc} (I/O-bound → CPU-bound, CI95)")
    return fig


def fig_cores(df):
    require(df, "gamma", "s", "D", "arch", "K", "c", "kappa", "dist_cpu")
    require_ci(df, "X", "U")
    work = df.copy()
    work["_rho"] = (work["gamma"] / work.apply(capacity, axis=1)).round(8)
    work["_q"] = (work["K"] / work["c"]).mask(work["K"] >= 10**9, np.inf)

    # Ưu tiên ρ_ref cố định theo E4 §8; nếu không có thì xét quét c ở cùng (γ, K) trong E2 của runner.
    rho_order = sorted(work["_rho"].dropna().unique(), key=lambda r: (not np.isclose(r, 0.95), r))
    series, mode_desc = [], ""
    for rho_val in rho_order:
        cand = []
        sub = work[np.isclose(work["_rho"], rho_val)]
        for q, block in sub.groupby("_q", sort=True):
            for _, part in sweeps(block, "c", omit=("gamma", "K", "_rho", "_q")):
                r = part.iloc[0]
                q_str = "∞" if np.isinf(q) else f"{q:g}"
                label = (
                    f"{'Hàng chung' if r.arch == 'shared' else 'Bun'}, K/c={q_str}, "
                    f"{r.dist_cpu}, s={r.s * 1000:g} ms, D={r.D * 1000:g} ms"
                )
                if r.arch == "partitioned":
                    label += f", κ={r.kappa:g}"
                cand.append((label, part))
        if cand:
            series, mode_desc = cand, f"tải tương đối ρ_ref = {rho_val:g}"
            break

    if not series:
        cand = sweeps(df, "c")
        if cand:
            series = cand
            r0 = cand[0][1].iloc[0]
            k_str = "∞" if r0.K >= 10**9 else f"{r0.K:g}"
            mode_desc = f"γ = {r0.gamma:g} req/s, K = {k_str}"

    if not series:
        raise ValueError("thiếu quét c (cần ≥ 2 mức core ở cùng điều kiện đối chứng)")

    has_r = {"R_mean", "R_ci_low", "R_ci_high"} <= set(df)
    specs = [("X", "Thông lượng thành công X (req/s)", 1.0)]
    if has_r:
        specs.append(("R", "Thời gian phản hồi R (ms)", 1000.0))
    specs.append(("U", "Hiệu suất CPU U (%)", 100.0))

    fig, axes = plt.subplots(1, len(specs), figsize=(4.5 * len(specs), 4.7), layout="constrained")
    for ax, (metric, unit, scale) in zip(np.atleast_1d(axes), specs):
        for i, (name, part) in enumerate(series):
            r0 = part.iloc[0]
            color = COLORS["loom"] if r0.arch == "shared" else system_style(r0, i)[0]
            curve(ax, part, "c", metric, name, yscale=scale, color=color)
        if metric == "X" and len({p["gamma"].iloc[0] for _, p in series}) == 1:
            g0 = series[0][1]["gamma"].iloc[0]
            ax.axhline(g0, ls=":", color="0.4", lw=1.1, label=f"Tải đến γ = {g0:g} req/s")
        elif metric == "R":
            ax.axhline(100, ls="--", color="0.35", lw=1.1, label="Ngưỡng 100 ms")
        axis(ax, "Số core / worker c", unit)
        legend(ax)
    fig.suptitle(f"Độ nhạy theo số core c tại {mode_desc} (CI95)")
    return fig


def fig7_closed(df):
    require(df, "closed_C", "arch", "K", "c", "X_mean", "R_mean")
    closed = df[df["closed_C"] > 0]
    require_ci(closed, "Pblock")
    has_err = "XRLittle_mean" in closed and closed["XRLittle_mean"].notna().any()
    little = "X·(R + z)" if "think_time" in closed and closed.think_time.ne(0).any() else "X·R"
    panels = [("XR", "Chu kỳ thành công (trong server)", "X·R (kết nối)")]
    if has_err:
        panels.append(("XRLittle", "Tính cả chu kỳ lỗi (toàn hệ kín)", little + " + X_err·t_err (kết nối)"))
    panels.append(("Pblock", "Tỉ lệ yêu cầu bị từ chối", "Tỉ lệ lỗi (%)"))

    fig, axes = plt.subplots(1, len(panels), figsize=(4.8 * len(panels), 5.0), layout="constrained")
    series = list(groups(closed, "closed_C"))
    has_kinf = any((part["K"] >= 10**9).any() for _, part in series) and any((part["K"] < 10**9).any() for _, part in series)
    limits = [closed["closed_C"].min(), closed["closed_C"].max()]
    for ax, (metric, title, ylabel) in zip(axes, panels):
        reject = metric == "Pblock"
        for i, (name, part) in enumerate(series):
            r0 = part.iloc[0]
            color, _ = system_style(r0, i)
            is_inf = has_kinf and r0.K >= 10**9
            curve(
                ax, part, "closed_C", metric, name, color=color,
                ls="--" if is_inf else "-", marker="s" if is_inf else "o",
                mfc="white" if is_inf else color, yscale=100 if reject else 1,
            )
        if reject:
            ax.axhline(1, color="0.35", linestyle=":", lw=1.2, label="Ngưỡng 1%")
        else:
            ax.plot(limits, limits, ":", color="0.30", lw=1.3, label="Đường y = C")
        axis(ax, "Số kết nối đồng thời C", ylabel)
        ax.set_title(title)
        legend(ax, fontsize=7.5)

    title = "Hình 7. Định luật Little và tỉ lệ lỗi ở hệ kín (closed-loop)"
    notes = []
    if "XR_ci_low" in closed and closed["XR_ci_low"].notna().all():
        notes.append("CI95 tính trực tiếp từ tích trên từng seed")
    else:
        notes.append("X·R tính từ hai trung bình (CI95 của tích cần dữ liệu từng seed)")
    if has_err:
        max_dev = float((100 * (closed["XRLittle_mean"] - closed["closed_C"]).abs() / closed["closed_C"]).max())
        notes.append(f"sai lệch Little tối đa {max_dev:.2f}% trên {len(closed)} cấu hình")
    if notes:
        title += "\n(" + "; ".join(notes) + ")"
    fig.suptitle(title)
    return fig


def special_scenario(df, case, factor, metrics):
    require(df, factor, "scenario", "arch", "c", "K", "gamma")
    part = df[df[factor] > 0].sort_values(["gamma", "c", "arch", "K", factor, "scenario"])
    if part.empty:
        raise ValueError(f"thiếu cấu hình {case} ({factor} > 0)")
    require_ci(part, *(metric for metric, _, _, _ in metrics))

    labels, colors = [], []
    for i, row in enumerate(part.itertuples()):
        name = "Bun" if row.arch == "partitioned" else ("Event loop" if row.c == 1 else "Loom")
        if row.arch == "partitioned" and hasattr(row, "kappa"):
            name += f" (κ={row.kappa:g})"
        condition = (
            f"Backend {row.backend_limit:g} chỗ" if case == "S8" else f"CPU dài {100 * row.heavy_prob:g}%"
        )
        labels.append(f"{name} · c={row.c:g}\nK={row.K:g} · γ={row.gamma:g} req/s\n{condition}")
        colors.append(system_style(row, i)[0])

    x = np.arange(len(part))
    fig, axes = plt.subplots(1, len(metrics), figsize=(max(9.2, len(part) * 3.5), 4.8), layout="constrained")
    for ax, (metric, ylabel, scale, limit) in zip(axes, metrics):
        mean = (part[f"{metric}_mean"] * scale).to_numpy()
        low = (part[f"{metric}_ci_low"] * scale).to_numpy()
        high = (part[f"{metric}_ci_high"] * scale).to_numpy()
        unit = "%" if scale == 100 else " ms"
        for xi, m, lo, hi, col in zip(x, mean, low, high, colors):
            ax.errorbar(xi, m, yerr=[[m - lo], [hi - m]], fmt="o", ms=6, capsize=5, lw=1.6, color=col)
            ax.annotate(
                f"{m:.2f}{unit}", xy=(xi, hi), xytext=(0, 6), textcoords="offset points",
                ha="center", va="bottom", fontsize=8.2, color="0.2",
            )
        ax.errorbar([], [], yerr=[[]], fmt="o", color="0.3", capsize=4, label="Mô phỏng (CI95)")
        ax.axhline(limit, color="0.35", linestyle="--", lw=1.1, label=f"Ngưỡng {limit:g}{unit}")
        ax.set_xticks(x, labels, fontsize=8.5)
        ax.set_xlim(-0.5, len(x) - 0.5)
        ymax = max(float(np.nanmax(high)), float(limit))
        ymin = min(float(np.nanmin(low)), float(limit))
        pad = max(0.14 * (ymax - ymin), 0.1 * ymax, 1.0)
        ax.set_ylim(max(0.0, ymin - 0.12 * pad), ymax + pad)
        axis(ax, "Cấu hình đo", ylabel)
        legend(ax)
    return fig


def fig_s8(df):
    fig = special_scenario(
        df, "S8", "backend_limit",
        [
            ("Pblock", "Xác suất từ chối toàn hệ thống (%)", 100, 1),
            ("R", "Thời gian phản hồi trung bình (ms)", 1000, 100),
        ],
    )
    fig.suptitle("S8. Giới hạn kết nối ở trạm backend M/M/c/c (CI95)")
    return fig


def fig_s10(df):
    fig = special_scenario(
        df, "S10", "heavy_prob",
        [
            ("R", "Thời gian phản hồi trung bình (ms)", 1000, 100),
            ("p99", "Phân vị p99 của thời gian phản hồi (ms)", 1000, 300),
        ],
    )
    fig.suptitle("S10. Ảnh hưởng của request CPU dài lên độ trễ (CI95)")
    return fig


def _analysis_groups(frame, factor, *, omit=()):
    """Bỏ nhóm trùng lặp mơ hồ tại cùng trục factor, giữ các cấu hình độc lập."""
    keys = [k for k in PARAMS if k in frame and k != factor and k not in omit]
    duplicate = frame.duplicated([*keys, factor], keep=False)
    if duplicate.any():
        ids = frame.groupby(keys, dropna=False).ngroup()
        frame = frame[~ids.isin(ids[duplicate])]
    if not frame.empty:
        yield from groups(frame, factor, omit=omit)


def _consistency_checks(data, raw):
    """Kiểm tra nhất quán §9.2: Định luật Little, U vs X·s_eff/c, trần X_max và cận dưới CI95."""
    lines = [
        "## Kiểm tra nhất quán (§9.2 — Định luật Little, hiệu suất U và trần X_max)",
        "",
        "Kiểm tra trên các cấu hình độc lập của từng CSV: open-loop đối chiếu `L_CPU ≈ X·W_CPU`, `L_IO ≈ X·D`, "
        "`L_sys ≈ X·R` và `U ≈ X·s_eff/c` (ngưỡng 3% theo §8.1, loại các cấu hình có `backend_limit` hoặc `heavy_prob`); "
        "closed-loop đối chiếu `X·R + X_err·t_err ≈ C` (kèm CI95 theo từng seed nếu có) và điều kiện vật lý `X ≤ X_max`.",
        "",
    ]
    open_rows = []
    seed_notes = []
    for key in ("e1", "e2", "e3", "e5"):
        df = data.get(key, pd.DataFrame())
        if df.empty or "arch" not in df:
            continue
        sub = df.copy()
        if "closed_C" in sub:
            sub = sub[sub["closed_C"] <= 0]
        if "backend_limit" in sub:
            sub = sub[sub["backend_limit"].isna() | (sub["backend_limit"] <= 0)]
        if "heavy_prob" in sub:
            sub = sub[sub["heavy_prob"].isna() | (sub["heavy_prob"] == 0)]
        if sub.empty:
            continue
        checks = []
        if {"L_cpu_mean", "X_mean", "W_cpu_mean"} <= set(sub):
            valid = sub[sub["L_cpu_mean"] > 0]
            if not valid.empty:
                dev = 100 * (valid["L_cpu_mean"] - valid["X_mean"] * valid["W_cpu_mean"]).abs() / valid["L_cpu_mean"]
                checks.append(("Little CPU", len(dev), dev.max(), int((dev <= 3.0).sum())))
        if {"L_io_mean", "X_mean", "D"} <= set(sub):
            valid = sub[(sub["D"] > 0) & (sub["L_io_mean"] > 0)]
            if not valid.empty:
                dev = 100 * (valid["L_io_mean"] - valid["X_mean"] * valid["D"]).abs() / valid["L_io_mean"]
                checks.append(("Little I/O", len(dev), dev.max(), int((dev <= 3.0).sum())))
        if {"L_sys_mean", "X_mean", "R_mean"} <= set(sub):
            valid = sub[sub["L_sys_mean"] > 0]
            if not valid.empty:
                dev = 100 * (valid["L_sys_mean"] - valid["X_mean"] * valid["R_mean"]).abs() / valid["L_sys_mean"]
                checks.append(("Little hệ thống", len(dev), dev.max(), int((dev <= 3.0).sum())))
        if {"U_mean", "X_mean", "c", "s", "kappa"} <= set(sub):
            valid = sub[sub["U_mean"] > 0]
            if not valid.empty:
                u_exp = valid["X_mean"] / valid.apply(capacity, axis=1)
                dev = 100 * (valid["U_mean"] - u_exp).abs() / valid["U_mean"]
                checks.append(("U vs X/X_max", len(dev), dev.max(), int((dev <= 3.0).sum())))
        for name, n, max_dev, n_ok in checks:
            open_rows.append(f"| {key} | {name} | {n} | {max_dev:.3g}% | {n_ok}/{n} |")

        r_df = raw.get(key, pd.DataFrame())
        if "seed" in r_df and {"L_sys", "X", "R"} <= set(r_df):
            r_sub = r_df.copy()
            if "closed_C" in r_sub:
                r_sub = r_sub[r_sub["closed_C"] <= 0]
            if "backend_limit" in r_sub:
                r_sub = r_sub[r_sub["backend_limit"].isna() | (r_sub["backend_limit"] <= 0)]
            if "heavy_prob" in r_sub:
                r_sub = r_sub[r_sub["heavy_prob"].isna() | (r_sub["heavy_prob"] == 0)]
            r_sub = r_sub[r_sub["L_sys"] > 0]
            if not r_sub.empty:
                s_dev = 100 * (r_sub["L_sys"] - r_sub["X"] * r_sub["R"]).abs() / r_sub["L_sys"]
                seed_notes.append(f"`{key}` ({int((s_dev <= 3.0).sum())}/{len(s_dev)} lượt, max `{s_dev.max():.3g}%`)")

    if open_rows:
        lines += [
            "| Tệp open-loop | Kiểm tra | n cấu hình độc lập | Lệch max (%) | Đạt ≤ 3% |",
            "|---|---|---:|---:|---:|",
            *open_rows,
            "",
        ]
    if seed_notes:
        lines.append("- Kiểm tra Little hệ thống (`L_sys ≈ X·R`) trên từng lượt seed độc lập: " + ", ".join(seed_notes) + ".")

    # S8 invariant: L_io <= backend_limit
    e5 = data.get("e5", pd.DataFrame())
    if not e5.empty and {"backend_limit", "L_io_mean"} <= set(e5):
        s8 = e5[e5["backend_limit"] > 0]
        if not s8.empty:
            ok_s8 = (s8["L_io_mean"] <= s8["backend_limit"]).all()
            lines.append(
                f"- Kịch bản S8 (`backend_limit` hữu hạn): `L_io_mean` tối đa = {s8['L_io_mean'].max():.2f} "
                f"≤ giới hạn {s8['backend_limit'].min():g} ({'đạt' if ok_s8 else 'vi phạm'})."
            )

    # Closed-loop Little check and physical X <= X_max check
    e4 = data.get("e4", pd.DataFrame())
    if not e4.empty and {"closed_C", "X_mean", "R_mean", "XRLittle_mean", "c", "s", "kappa", "arch"} <= set(e4):
        cl = e4[e4["closed_C"] > 0].copy()
        if not cl.empty:
            cl["dev_pct"] = 100 * (cl["XRLittle_mean"] - cl["closed_C"]) / cl["closed_C"]
            cl["X_max"] = cl.apply(capacity, axis=1)
            if "X_ci_low" in cl:
                cl["over_cap"] = (cl["X_mean"] > cl["X_max"] * 1.03) | (cl["X_ci_low"] > cl["X_max"])
            else:
                cl["over_cap"] = cl["X_mean"] > cl["X_max"] * 1.03
            anomalies = cl[(cl["dev_pct"].abs() > 3.0) | cl["over_cap"]]
            n_ok = len(cl) - len(anomalies)
            max_abs_dev = float(cl["dev_pct"].abs().max())
            lines.append(
                f"- Hệ kín E4 (`e4_closed_loop.csv`): `{n_ok}/{len(cl)}` cấu hình đạt đồng thời Little ≤ 3% "
                f"(sai lệch tuyệt đối tối đa `{max_abs_dev:.3g}%`) và không vi phạm trần vật lý `X_max`."
            )
            if not anomalies.empty:
                lines += [
                    "",
                    "| Cấu hình E4 bất thường | C | X đo / X_max (req/s) | X·R + X_err·t_err | Lệch Little (%) | Ghi chú |",
                    "|---|---:|---:|---:|---:|---|",
                ]
                for r in anomalies.itertuples():
                    note = "X vượt trần vật lý" if r.over_cap else "Lệch Little > 3%"
                    lines.append(
                        f"| {r.scenario} | {r.closed_C:g} | {r.X_mean:.1f} / {r.X_max:g} "
                        f"| {r.XRLittle_mean:.1f} | {r.dev_pct:+.2f}% | {note} |"
                    )

    # Check negative CI lower bounds on non-negative metrics
    neg_notes = []
    for key in ("e1", "e2", "e3", "e4", "e5"):
        df = data.get(key, pd.DataFrame())
        if df.empty:
            continue
        for m in NON_NEGATIVE:
            col = f"{m}_ci_low"
            if col in df and (df[col] < 0).any():
                neg_notes.append(f"{key}.{m} ({int((df[col] < 0).sum())} dòng, min={df[col].min():.3g})")
    if neg_notes:
        lines.append(
            "- Cận dưới CI95 đối xứng âm (do biến không âm rất gần 0): " + "; ".join(neg_notes) + "."
        )
    return lines


def _sensitivity(data):
    """Xếp hạng biên độ (max − min) trong các lát cắt chỉ thay đổi đúng một yếu tố."""
    lines = [
        "## Xếp hạng độ nhạy (§9.7)",
        "",
        "Với mỗi chỉ số, xếp theo biên độ lớn nhất (`max − min`) trong các lát cắt chỉ đổi đúng một yếu tố "
        "(OFAT: giữ nguyên các tham số còn lại; ưu tiên lát cắt chuẩn hóa `ρ_ref, K/core` cho `c` hoặc `γ·s` cho `s` nếu có, "
        "nếu không dùng lát cắt cố định `γ, K, D` trong CSV). Thứ hạng phản ánh dải tham số đã khảo sát.",
    ]
    sweep_plan = {"e1": ["gamma"], "e2": ["K", "c"], "e3": ["kappa", "D", "s", "c"], "e4": ["closed_C"]}
    names = {"gamma": "γ", "K": "K", "c": "c", "kappa": "κ", "D": "D", "s": "s", "closed_C": "C"}
    responses = {
        "X": (1, "req/s"), "R": (1000, "ms"), "Pblock": (100, "điểm %"),
        "Wq": (1000, "ms"), "U": (100, "điểm %"),
    }
    ranges = {m: {} for m in responses}
    for key, factors in sweep_plan.items():
        frame = data.get(key, pd.DataFrame())
        controls_needed = {
            "arch", "gamma", "c", "K", "s", "D", "kappa", "dist_cpu",
            "closed_C", "backend_limit", "heavy_prob",
        }
        if not controls_needed <= set(frame):
            continue
        for factor in factors:
            if factor not in frame or frame[factor].nunique() < 2:
                continue
            sample = frame.dropna(subset=sorted(controls_needed)).copy()
            candidate_modes = []
            if factor == "c":
                s_norm = sample.copy()
                s_norm["_q"] = (s_norm.K / s_norm.c).mask(s_norm.K >= 10**9, np.inf)
                s_norm["_rho"] = (s_norm.gamma / s_norm.apply(capacity, axis=1)).round(9)
                candidate_modes.append((s_norm, ["_q", "_rho"], ("K", "gamma", "_q", "_rho")))
                candidate_modes.append((sample, [], ()))
            elif factor == "s":
                s_norm = sample.copy()
                s_norm["_load"] = (s_norm.gamma * s_norm.s).round(9)
                candidate_modes.append((s_norm, ["_load"], ("gamma", "_load")))
                candidate_modes.append((sample, [], ()))
            else:
                candidate_modes.append((sample, [], ()))

            for mode_df, controls, omit in candidate_modes:
                found_any = False
                slices = mode_df.groupby(controls, dropna=False) if controls else [(None, mode_df)]
                for _, section in slices:
                    for _, sweep in _analysis_groups(section, factor, omit=omit):
                        if sweep[factor].nunique() < 2:
                            continue
                        found_any = True
                        for metric, (scale, _) in responses.items():
                            col = metric + "_mean"
                            if col not in sweep:
                                continue
                            values = sweep[[factor, col]].replace([np.inf, -np.inf], np.nan).dropna()
                            if values[factor].nunique() < 2 or values[factor].duplicated().any():
                                continue
                            effect = float(scale * (values[col].max() - values[col].min()))
                            ranges[metric][factor] = max(effect, ranges[metric].get(factor, 0.0))
                if found_any:
                    break

    for metric, (_, unit) in responses.items():
        order = sorted(ranges[metric].items(), key=lambda item: -item[1])
        lines.append(
            f"- {metric} ({unit}) — "
            + (", ".join(f"{names[k]} {v:.4g}" for k, v in order) or "chưa có lát cắt đủ mức.")
        )
    available = set().union(*(set(v) for v in ranges.values()))
    missing = [names[k] for k in names if k not in available]
    if missing:
        lines.append("Chưa xếp hạng được " + ", ".join(missing) + " do thiếu quét có đối chứng.")
    return lines


def _welch_cohen_from_stats(m1, s1, n1, m2, s2, n2):
    """Kiểm định Welch hai phía và Cohen's d từ thống kê tổng hợp (mean, std, n)."""
    if min(n1, n2) < 2 or not np.isfinite([m1, s1, m2, s2]).all() or min(s1, s2) < 0:
        return None
    if s1 == 0 and s2 == 0:
        return "Welch p=1, d=0 (SD=0)" if np.isclose(m1, m2) else "SD=0 (khác biệt tất định)"
    pval = float(stats.ttest_ind_from_stats(m1, s1, n1, m2, s2, n2, equal_var=False).pvalue)
    sp = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    d_str = f"{(m1 - m2) / sp:.3g}" if sp > 0 else "KXĐ"
    return f"Welch p={pval:.3g}, d={d_str}"


def _compare_architectures(data, raw):
    lines = [
        "## So sánh Spring Loom với Bun (§9.4)",
        "",
        "Ghép cùng tải, `c`, `K`, `s`, `D` và điều kiện phục vụ (`κ = 1` so thuần túy cấu trúc hàng đợi ở cùng năng lực CPU; "
        "`κ > 1` gồm thêm chi phí đồng bộ kernel thread của Bun). Khi có dữ liệu từng seed (`100..109`, Common Random Numbers), "
        "báo hiệu số ghép cặp `Δ = Loom − Bun`, kiểm định t ghép cặp `p_pair`, Mann–Whitney `p_MW` và kích thước hiệu ứng Cohen's `d`.",
        "",
    ]
    keys = [
        "gamma", "c", "K", "s", "D", "dist_cpu", "closed_C", "backend_limit",
        "heavy_prob", "dist_io", "routing", "heavy_mult", "think_time", "t_err",
    ]
    head = [
        "| Tệp / điều kiện | κ Bun | Chỉ số | Loom [CI95] | Bun [CI95] | So sánh thống kê |",
        "|---|---:|---|---:|---:|---|",
    ]
    rows = []
    used_seeded = False
    used_aggregated_welch = False
    for key in ("e1", "e2", "e3"):
        frame = data.get(key, pd.DataFrame())
        if not {"arch", "kappa", *keys[:5]} <= set(frame):
            continue
        original = raw.get(key, pd.DataFrame())
        shared = frame[(frame.arch == "shared") & (frame.c > 1)]
        for _, loom in shared.iterrows():
            match = frame.arch.eq("partitioned")
            for col in keys:
                if col in frame:
                    match &= frame[col].eq(loom[col]) | (frame[col].isna() & pd.isna(loom[col]))
            for _, bun in frame[match].iterrows():
                samples = []
                for row in (loom, bun):
                    if original is None or "seed" not in original:
                        break
                    mask = pd.Series(True, index=original.index)
                    for col in ["arch", "kappa", *keys]:
                        if col in original and col in row:
                            mask &= original[col].eq(row[col]) | (original[col].isna() & pd.isna(row[col]))
                    reps = original.loc[mask].sort_values("seed")
                    if reps.empty or reps.seed.isna().any() or reps.seed.duplicated().any():
                        break
                    samples.append(reps)

                for metric in ("X", "R", "Pblock"):
                    col = metric + "_mean"
                    if col not in frame or not np.isfinite([loom[col], bun[col]]).all():
                        continue
                    scale, unit = {"X": (1, "req/s"), "R": (1000, "ms"), "Pblock": (100, "%")}[metric]
                    low, high, std_col = metric + "_ci_low", metric + "_ci_high", metric + "_std"
                    if {low, high} <= set(frame) and np.isfinite([r[c] for r in (loom, bun) for c in (low, high)]).all():
                        values = [
                            f"{r[col] * scale:.4g} [{r[low] * scale:.4g}, {r[high] * scale:.4g}]"
                            for r in (loom, bun)
                        ]
                    else:
                        values = [f"{r[col] * scale:.4g}" for r in (loom, bun)]

                    decision = "Thiếu CI95 hoặc seed."
                    if len(samples) == 2 and all(metric in r for r in samples):
                        s_a = samples[0][["seed", metric]].dropna()
                        s_b = samples[1][["seed", metric]].dropna()
                        a = s_a[metric].to_numpy(dtype=float) * scale
                        b = s_b[metric].to_numpy(dtype=float) * scale
                        if min(len(a), len(b)) >= 2:
                            used_seeded = True
                            mw_p = float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
                            pooled_var = ((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                            sd = np.sqrt(pooled_var / (len(a) + len(b) - 2))
                            if sd == 0:
                                d_str = "0 (SD=0)" if np.isclose(a.mean(), b.mean()) else "KXĐ (SD=0)"
                            else:
                                d_str = f"{(a.mean() - b.mean()) / sd:.3g}"
                            paired = s_a.merge(s_b, on="seed", suffixes=("_l", "_b"))
                            if len(paired) >= 2:
                                diff = (paired[f"{metric}_l"] - paired[f"{metric}_b"]).to_numpy(dtype=float) * scale
                                d_sd = diff.std(ddof=1)
                                p_pair = 1.0 if d_sd == 0 and np.isclose(diff.mean(), 0.0) else (
                                    0.0 if d_sd == 0 else float(stats.ttest_rel(paired[f"{metric}_l"], paired[f"{metric}_b"]).pvalue)
                                )
                                decision = f"Δ={diff.mean():+.3g}, p_pair={p_pair:.3g}, MW p={mw_p:.3g}, d={d_str}"
                            else:
                                decision = f"Mann–Whitney p={mw_p:.3g}, d={d_str}"
                    if decision.startswith("Thiếu") and {low, high} <= set(frame):
                        if np.isfinite([r[c] for r in (loom, bun) for c in (low, high)]).all():
                            overlap = max(loom[low], bun[low]) <= min(loom[high], bun[high])
                            decision = "CI95 giao nhau" if overlap else "CI95 tách nhau"
                            if {std_col, "n_seeds"} <= set(frame):
                                stat_text = _welch_cohen_from_stats(
                                    loom[col], loom[std_col], int(loom["n_seeds"]),
                                    bun[col], bun[std_col], int(bun["n_seeds"]),
                                )
                                if stat_text:
                                    decision += f"; {stat_text}"
                                    used_aggregated_welch = True
                    desc = (
                        f"{key}, γ={loom.gamma:g}, c={loom.c:g}, K={loom.K:g}, "
                        f"s={1000 * loom.s:g} ms, D={1000 * loom.D:g} ms"
                    )
                    if "dist_cpu" in loom:
                        desc += f", {loom.dist_cpu}"
                    rows.append(
                        f"| {desc} | {bun.kappa:g} | {metric} ({unit}) | {values[0]} | {values[1]} | {decision} |"
                    )
    if not rows:
        return lines + ["Chưa có cặp cấu hình đủ thông tin."]
    footnote = "Dấu của `Δ` và Cohen's `d` tính theo chiều `Loom − Bun` (`Δ < 0` ở `R` và `P_block` nghĩa là Loom thấp hơn/tốt hơn). "
    if used_seeded:
        footnote += (
            "`p_pair` là p-value kiểm định t hai phía ghép cặp theo đúng `seed` (khử phương sai dòng đến chung — Common Random Numbers); "
            "`MW p` là kiểm định phi tham số Mann–Whitney U hai mẫu."
        )
    elif used_aggregated_welch:
        footnote += (
            "CSV chỉ lưu thống kê tổng hợp nên dùng kiểm định Welch hai mẫu độc lập làm tham khảo bảo thủ."
        )
    return lines + head + rows + ["", footnote]


def _factorial(frame):
    lines = ["## E6 — ANOVA 2³ (§9.7)", ""]
    if frame is None or frame.empty:
        return lines + [
            "Ngoài phạm vi 6 CSV chuẩn của bản phân công Phase 2 (`Assign_tasks.docx` giao E1–E5); "
            "hàm phân tích đã sẵn sàng tự động chạy ANOVA 2³ ngay khi có tệp `e6*.csv`."
        ]
    f = frame.copy()
    if "c" not in f:
        return lines + ["Thiếu c trong E6."]
    if "rho_ref" not in f:
        if "level" in f:
            f["rho_ref"] = f.level
        elif {"gamma", "s"} <= set(f):
            f["rho_ref"] = f.gamma * f.s / f.c
    if "K_per_core" not in f and "K" in f:
        f["K_per_core"] = f.K / f.c
    axes = ["rho_ref", "K_per_core", "c"]
    if not set(axes) <= set(f):
        return lines + ["Thiếu ρ_ref hoặc K/core trong E6."]
    for col, target in {"arch": "shared", "dist_cpu": "exp", "closed_C": 0, "heavy_prob": 0}.items():
        if col in f:
            f = f[f[col] == target]
    for col, target in [("D", 0.05), ("s", 0.001)]:
        if col in f:
            f = f[np.isclose(f[col], target)]
    if "backend_limit" in f:
        f = f[f.backend_limit.isna() | (f.backend_limit == -1)]
    f["rho_ref"] = f.rho_ref.round(8)
    levels = [(0.7, 1.1), (10, 100), (1, 8)]
    cells = pd.MultiIndex.from_product(levels, names=axes)
    f = f.set_index(axes)
    f = f[f.index.isin(cells)]
    if len(f.index.unique()) != 8:
        return lines + ["Thiếu ít nhất một trong tám ô (ρ_ref, K/core, c) theo §8; chưa thể tính ANOVA."]
    lines += [
        "Các hiệu ứng là tương phản hai mức, với phương sai sai số gộp từ các seed trong từng ô.", "",
        "| Chỉ số | Hiệu ứng | df1 | df2 | F | p |", "|---|---|---:|---:|---:|---:|",
    ]
    signs = np.array([[-1 if x == pair[0] else 1 for x, pair in zip(point, levels)] for point in cells])
    completed = 0
    for metric in ("X", "R", "Pblock"):
        if metric in f and "seed" in f:
            runs = f[[metric, "seed"]].replace([np.inf, -np.inf], np.nan).dropna().reset_index()
            if runs.duplicated([*axes, "seed"]).any():
                continue
            est = runs.groupby(axes)[metric].agg(["mean", "std", "count"]).reindex(cells)
        elif {metric + "_mean", metric + "_std", "n_seeds"} <= set(f) and f.index.is_unique:
            est = f[[metric + "_mean", metric + "_std", "n_seeds"]].reindex(cells).copy()
            est.columns = ["mean", "std", "count"]
        else:
            continue
        if not np.isfinite(est).all().all() or (est["count"] < 2).any() or (est["std"] < 0).any():
            continue
        n = est["count"].to_numpy()
        df = n.sum() - 8
        mse = np.dot(n - 1, est["std"] ** 2) / df
        if mse <= 0:
            continue
        for bits in ((0,), (1,), (2,), (0, 1), (0, 2), (1, 2), (0, 1, 2)):
            contrast = signs[:, bits].prod(axis=1) @ est["mean"]
            test = contrast**2 / (mse * (1 / n).sum())
            name = " × ".join(("ρ_ref", "K/core", "c")[i] for i in bits)
            lines.append(f"| {metric} | {name} | 1 | {df:g} | {test:.4g} | {stats.f.sf(test, 1, df):.4g} |")
        completed += 1
    return lines if completed else lines[:-4] + ["Thiếu lặp, cỡ mẫu, SD hoặc phương sai dư dương để ước lượng kiểm định."]


def analysis(data, raw):
    if all(frame.empty for frame in data.values()):
        return [
            "## Phân tích §9", "",
            "Chưa có số đo để xác định knee, kiểm tra nhất quán, so sánh Loom với Bun, "
            "đánh giá nút cổ chai, sai số hay độ nhạy.", "",
            *_factorial(None),
        ]

    lines = [
        "## Bão hòa và nút cổ chai (§9.5–§9.6)", "",
        "Với `γ` tăng dần, đánh dấu tải trước bước đầu có `X_i < 1,02·X_{i-1}` (§9, hàm `knee`). "
        "Cột cuối cho biết tải cao nhất trong lưới E1 còn đồng thời đạt 4 ngưỡng §1.3 "
        "(`P_block < 1%`, `R < 100 ms`, `p99 < 300 ms`, `X ≥ 0,95·γ`).", "",
        "| Hệ / cấu hình | γ knee → γ xác nhận (req/s) | X tại knee / X_max (req/s) | U_CPU cao nhất | γ tăng P_block đầu tiên | γ đạt 1% đầu tiên | γ max đạt 4 ngưỡng §1.3 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    e1 = data.get("e1", pd.DataFrame())
    starts = len(lines)
    peaks, onsets = {}, {}
    if {"gamma", "arch"} <= set(e1):
        for label, sample in _analysis_groups(e1, "gamma"):
            series = sample.dropna(subset=["gamma"])
            if series.empty:
                continue
            change = knee(series) if "X_mean" in series else None
            cap_val = capacity(series.iloc[0]) if {"c", "s", "kappa"} <= set(series) else np.nan
            cap = f"{cap_val:.4g}" if np.isfinite(cap_val) else "—"
            interval = "chưa thấy" if "X_mean" in series else "thiếu X_mean"
            if change is not None:
                interval = f"{change[0].gamma:g} → {change[1].gamma:g}"
            measured = (
                f"{change[0].X_mean:.4g} ({100 * change[0].X_mean / cap_val:.1f}%)"
                if change is not None and np.isfinite(cap_val)
                else (f"{change[0].X_mean:.4g}" if change is not None else "—")
            )
            busy = series.dropna(subset=["U_mean"]) if "U_mean" in series else series.iloc[:0]
            utilization = "—"
            if not busy.empty:
                row = busy.loc[busy.U_mean.idxmax()]
                utilization = f"{row.U_mean:.2%} ở γ={row.gamma:g}"
                peaks[label] = row.U_mean
            pb = series.dropna(subset=["Pblock_mean"]) if "Pblock_mean" in series else series.iloc[:0]
            rises = pb[pb.Pblock_mean.diff() > 0] if not pb.empty else pb
            above = pb[pb.Pblock_mean >= 0.01] if not pb.empty else pb
            onset = "—"
            if not rises.empty:
                onsets[label] = rises.gamma.iloc[0]
                onset = f"{onsets[label]:g}"
            threshold = f"{above.gamma.iloc[0]:g}" if not above.empty else "—"
            sla_max = "—"
            if {"Pblock_mean", "R_mean", "p99_mean", "X_mean"} <= set(series):
                ok_sla = series[
                    (series["Pblock_mean"] < 0.01)
                    & (series["R_mean"] < 0.100)
                    & (series["p99_mean"] < 0.300)
                    & (series["X_mean"] >= 0.95 * series["gamma"])
                ]
                sla_max = f"{ok_sla['gamma'].max():g}" if not ok_sla.empty else "không đạt"
            lines.append(
                f"| {label} | {interval} | {measured} / {cap} | {utilization} | {onset} | {threshold} | {sla_max} |"
            )
    if len(lines) == starts:
        lines = [lines[0], "", "Chưa có quét tải E1 đủ dữ liệu."]
    if peaks:
        names = ", ".join(k for k, v in peaks.items() if v == max(peaks.values()))
        lines += ["", f"CPU đạt U cao nhất ở {names} ({max(peaks.values()):.2%})."]
    if onsets:
        names = ", ".join(k for k, v in onsets.items() if v == min(onsets.values()))
        lines += ["", f"P_block bắt đầu tăng sớm nhất ở {names}, tại γ={min(onsets.values()):g} req/s."]
    lines += [
        "",
        "U chỉ đo tại trạm CPU. Trong mô hình I/O vô hạn (`M/M/∞`), trạm CPU đặt trần thông lượng. "
        "Kịch bản S8 xuất `P_block` toàn hệ nên chưa tách riêng tỉ lệ từ chối giữa CPU và backend.",
        "",
        *_consistency_checks(data, raw),
        "",
        "## Sai lệch mô phỏng và giải tích (§9.3)",
        "",
        "`δ = 100·|mô phỏng − giải tích| / |giải tích|`. Để tránh sai số giả 100% khi mẫu số lý thuyết tiệm cận 0 "
        "(ví dụ `ana_Pblock ≈ 10⁻¹⁰⁰` ở tải thấp), phép tính sai số tương đối chỉ xét cấu hình có "
        "`ana_Pblock ≥ 10⁻³` (0,1%) và `ana_Wq ≥ 10⁻⁶ s` (0,001 ms); sai số tuyệt đối của các dòng bị loại được nêu bên dưới.",
        "",
    ]

    comparisons = []
    excluded_abs = {}
    for key in ("e1", "e2", "e3"):
        frame = data.get(key, pd.DataFrame())
        strata = [(key + " (toàn bộ)", frame)]
        if key == "e1" and {"arch", "c", "s", "kappa", "gamma"} <= set(frame) and not frame.empty:
            low, near = [], []
            for _, group in _analysis_groups(frame, "gamma"):
                sample = group.dropna(subset=["gamma", "s", "c", "kappa"])
                if not sample.empty:
                    low.append(sample.iloc[0])
                    near.append(sample.loc[(sample.gamma / capacity(sample.iloc[0]) - 1).abs().idxmin()])
            strata.extend([("e1 (tải thấp)", pd.DataFrame(low)), ("e1 (gần trần)", pd.DataFrame(near))])
        for label, sample in strata:
            for metric in ("X", "R", "Pblock", "U", "W_cpu", "Wq", "L_cpu", "L_io", "L_sys"):
                mean, theory = metric + "_mean", "ana_" + metric
                if not {mean, theory} <= set(sample):
                    continue
                valid = sample[[mean, theory]].replace([np.inf, -np.inf], np.nan).dropna()
                floor = 1e-3 if metric == "Pblock" else (1e-6 if metric == "Wq" else 0.0)
                tiny = valid[valid[theory].abs() <= floor]
                if label.endswith("(toàn bộ)") and not tiny.empty and metric in ("Pblock", "Wq"):
                    max_abs = float((tiny[mean] - tiny[theory]).abs().max())
                    excluded_abs[f"{key}.{metric}"] = (len(tiny), max_abs)
                valid = valid[valid[theory].abs() > floor]
                if not valid.empty:
                    errors = 100 * (valid[mean] / valid[theory] - 1).abs()
                    lo, hi = metric + "_ci_low", metric + "_ci_high"
                    covered = "—"
                    if {lo, hi} <= set(sample):
                        aligned = sample.loc[valid.index, [lo, hi, theory]].dropna()
                        if len(aligned):
                            count = aligned[theory].between(aligned[lo], aligned[hi]).sum()
                            covered = f"{count}/{len(aligned)}"
                    tandem = str(int((errors < 3).sum())) if metric in ("Pblock", "R", "L_io") else "—"
                    comparisons.append(
                        f"| {label} | {metric} | {len(valid)} | {errors.mean():.4g} "
                        f"| {errors.max():.4g} | {tandem} | {covered} |"
                    )
    lines += (
        [
            "| Tệp / tải | Chỉ số | n cấu hình | δ TB (%) | δ max (%) | δ < 3% (tandem §8.1) | Lý thuyết trong CI95 |",
            "|---|---|---:|---:|---:|---:|---:|",
            *comparisons,
        ]
        if comparisons
        else ["Chưa có cặp mô phỏng và giải tích."]
    )
    if excluded_abs:
        summary_tiny = ", ".join(
            f"{k}: {n} dòng (|sim−ana| max = {v * (100 if k.endswith('Pblock') else 1000):.4g} "
            f"{'điểm %' if k.endswith('Pblock') else 'ms'})"
            for k, (n, v) in sorted(excluded_abs.items())
        )
        lines += ["", f"Các dòng dưới ngưỡng mẫu số khả quan sát: {summary_tiny}."]
    lines += [
        "",
        "Hình 8 (`fig8_verification.md`) trình bày kiểm chứng 18 cấu hình trạm đơn (6 mô hình × 3 mức tải, ngưỡng < 5%). "
        "Lưu ý ở `e1 (gần trần)` (`SpringLoom_c8` tại đúng điểm tới hạn `γ = 8000, ρ = 1, K = 800`), thời gian hồi phục dừng "
        "của quá trình khuếch tán có biên phản xạ tỉ lệ với `O(K²/μ) ≈ 80 s` (~640.000 request), nên trong lượt chạy 45.000 request "
        "(đã bật warm-up động 50%), `R` đạt `82,52 ms` so với nghiệm dừng `100,36 ms` (`-17,8%`) và `L_CPU` đạt `261,99` so với `402,38` (`-34,9%`) (§7.5, §9.8).",
        "",
    ]
    return lines + _sensitivity(data) + [""] + _compare_architectures(data, raw) + [""] + _factorial(raw.get("e6"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RESULTS, help="Thư mục CSV của TV2")
    parser.add_argument("--output-dir", type=Path, help="Mặc định: figures/ trong thư mục đầu vào")
    parser.add_argument(
        "--formats", nargs="+", default=["png"], metavar="png,pdf",
        help="Định dạng ảnh: png, pdf hoặc cả hai",
    )
    args = parser.parse_args(argv)
    formats = list(dict.fromkeys(v.lower() for arg in args.formats for v in arg.split(",")))
    if not set(formats) <= {"png", "pdf"}:
        parser.error("--formats chỉ hỗ trợ png và pdf")
    output = args.output_dir or args.input_dir / "figures"
    output.mkdir(parents=True, exist_ok=True)

    files = FILES.copy()
    notes, written = [], []
    factorials = sorted(args.input_dir.glob("e6*.csv"))
    if len(factorials) == 1:
        files["e6"] = factorials[0].name
    elif factorials:
        notes.append("E6 có nhiều CSV ứng viên, cần xác định tệp giai thừa.")

    data, raw = {}, {}
    for key, filename in files.items():
        try:
            data[key], raw[key] = read_csv(args.input_dir / filename, key, notes=notes)
        except (OSError, ValueError) as err:
            reason = "chưa có tệp" if isinstance(err, FileNotFoundError) else str(err)
            notes.append(f"{filename} — {reason}.")
            data[key], raw[key] = pd.DataFrame(), pd.DataFrame()

    attach_raw_seeds(args.input_dir, data, raw, notes)

    capacity_data = data["e2"]
    if "c" in capacity_data and capacity_data.c.nunique() == 1:
        notes.append(
            f"Hình 6 chỉ có c={capacity_data.c.dropna().iloc[0]:g} trong {FILES['e2']}. "
            "Có thể so K trong từng hệ; tác động riêng của c cần thêm các mức core."
        )
    if "gamma" in capacity_data and capacity_data.gamma.nunique() == 1:
        notes.append(
            f"Hình 3 dùng lát cắt K tại γ={capacity_data.gamma.dropna().iloc[0]:g} req/s. "
            "Hai lát cắt theo γ và K là hai phép quét độc lập."
        )
    if "XRLittle_mean" in data["e4"] and "t_err" not in data["e4"]:
        delay = " và z = 0" if "think_time" not in data["e4"] else ""
        notes.append(f"Hình 7 dùng t_err = 10 ms{delay} theo cấu hình E4 của runner (§7.1).")

    # Các hình cốt lõi (§10) cùng các hình độ nhạy & so sánh trực tiếp Nhóm 3/4.
    cores_source = data["e2"] if ("c" in data["e2"] and data["e2"].c.nunique() >= 2) else (
        data["e3"] if ("c" in data["e3"] and data["e3"].c.nunique() >= 2) else data["e2"]
    )
    figures = [
        ("fig1_e1_throughput", fig1_throughput, [data["e1"]]),
        ("fig2_latency", fig2_latency, [data["e1"]]),
        ("fig3_blocking", fig3_blocking, [data["e1"], data["e2"], notes]),
        ("fig4_utilization", fig4_utilization, [data["e1"], data["e3"], notes]),
        ("fig5_io_delay", fig5_delay, [data["e3"]]),
        ("fig6_capacity", fig6_capacity, [data["e2"]]),
        ("fig7_closed_loop", fig7_closed, [data["e4"]]),
        ("loom_vs_bun", fig_loom_vs_bun, [data["e2"]]),
        ("sensitivity_kappa", fig_kappa, [data["e3"]]),
        ("sensitivity_s", fig_service, [data["e3"]]),
        ("sensitivity_c", fig_cores, [cores_source]),
        ("s8_backend", fig_s8, [data["e5"]]),
        ("s10_long_cpu", fig_s10, [data["e5"]]),
    ]
    table = "fig8_verification.md"
    summary_path = output / "analysis_summary.md"
    owned_names = {f"{stem}.{fmt}" for stem, _, _ in figures for fmt in ("png", "pdf")} | {table}
    previous = set()
    if summary_path.is_file():
        old_lines = summary_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if old_lines[:1] == ["# Phân tích kết quả DES"]:
            previous = {n for n in owned_names if f"- [{n}]({n})" in old_lines and (output / n).is_file()}

    retained = []
    for stem, draw, inputs in figures:
        try:
            fig = draw(*inputs)
            for fmt in ("png", "pdf"):
                name = f"{stem}.{fmt}"
                if fmt not in formats and name not in previous:
                    if fmt == "png" and "pdf" in formats:
                        # Tính bố cục nhất quán như khi xuất PNG trước PDF.
                        initial_dpi = fig.dpi
                        fig.set_dpi(DPI)
                        fig.draw_without_rendering()
                        fig.set_dpi(initial_dpi)
                    continue
                # Bỏ dấu thời gian để cùng CSV xuất cùng PDF (tái lập byte).
                metadata = {"CreationDate": None, "ModDate": None} if fmt == "pdf" else None
                if fmt in formats:
                    fig.savefig(output / name, dpi=DPI, metadata=metadata)
                    written.append(name)
                else:
                    with BytesIO() as buffer:
                        fig.savefig(buffer, format=fmt, dpi=DPI, metadata=metadata)
                        if buffer.getvalue() == (output / name).read_bytes():
                            retained.append(name)
        except ValueError as err:
            notes.append(f"Bỏ qua {stem} — {err}.")
        finally:
            plt.close("all")

    try:
        fig8_verification(data["verification"], output / table)
        written.append(table)
    except ValueError as err:
        notes.append(f"Bỏ qua {table} — {err}.")

    summary = ["# Phân tích kết quả DES", "", "## Đầu ra của lần chạy", ""]
    summary.extend(f"- [{name}]({name})" for name in written)
    if not written:
        summary.append("Chưa đủ dữ liệu để xuất hình hoặc bảng đối chiếu.")
    if retained:
        summary += ["", "## Định dạng từ lần trước khớp với dữ liệu hiện tại", ""]
        summary.extend(f"- [{name}]({name})" for name in retained)
    if notes:
        summary += ["", "## Phạm vi dữ liệu và ghi chú xử lý", "", *[f"- {s}" for s in notes]]
    summary += ["", *analysis(data, raw)]

    for stale in previous.difference(written, retained):
        (output / stale).unlink(missing_ok=True)
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")

    for message in notes:
        print(message)
    print(f"Đã xuất {len(written)} tệp hình/bảng và analysis_summary.md vào {output}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
