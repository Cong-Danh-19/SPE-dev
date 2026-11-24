"""[TV3] Ứng dụng trực quan hóa kết quả từ thư mục results/*.csv ra results/figures/."""
import os
import pandas as pd
import matplotlib.pyplot as plt


def plot_e1_throughput(res_dir: str = "results", fig_dir: str = "results/figures"):
    csv_path = os.path.join(res_dir, "e1_throughput_curves.csv")
    if not os.path.exists(csv_path):
        print(f"Bỏ qua {csv_path} (chưa có dữ liệu)")
        return
    df = pd.read_csv(csv_path)
    plt.figure(figsize=(8, 5))
    for scenario, grp in df.groupby("scenario"):
        grp = grp.sort_values("gamma")
        plt.plot(grp["gamma"], grp["X_mean"], marker="o", label=scenario)
        plt.fill_between(grp["gamma"], grp["X_ci_low"], grp["X_ci_high"], alpha=0.2)
    plt.xlabel("Tốc độ đến γ (req/s)")
    plt.ylabel("Thông lượng X (req/s)")
    plt.title("E1: Thông lượng theo tải với khoảng tin cậy 95%")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(fig_dir, "fig1_e1_throughput.png"), dpi=300)
    plt.close()


def main():
    os.makedirs("results/figures", exist_ok=True)
    plot_e1_throughput()
    # TODO [TV3]: Bổ sung hàm vẽ cho E2, E3, E4, E5
    print("Đã xuất biểu đồ vào results/figures/.")


if __name__ == "__main__":
    main()
