<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:91f4d864bc45161bf4c5a4281aaed4622a3d477fd98553b696d0cd668dba212f -->

# Thí nghiệm và dữ liệu bàn giao

Các số liệu trong mục dưới là kết quả lịch sử từ phiên bản trước khi sửa phép đo. Ma trận Phase 1 mới chạy bằng `python -m apps.design_experiments_app --group E1` (tương tự E2, E3, E4, E6); dữ liệu cũ không xác nhận kết quả của phiên bản mới.

<!-- /coderabbit-ai-generated:v1 -->

Thư mục `results/` chứa **7 tệp CSV chuẩn** do `apps/benchmark_experiments_app.py` sinh tự động: 5 tệp thực nghiệm (`e1`–`e5`) gồm **124 dòng cấu hình** (tương ứng **120 cấu hình tham số độc lập**), tệp `raw_seed_runs.csv` lưu toàn bộ **1.240 lượt chạy từng seed** (`10` seed/cấu hình), và bảng kiểm chứng `verification_summary.csv` gồm **18 cấu hình trạm đơn** (`6` mô hình × `3` mức tải × `15` seed). Lưu ý thứ tự đánh số tệp `e2`/`e4`/`e5` của runner khác với ký hiệu mục trong notebook §8; bảng dưới đây ánh xạ chính xác từng tệp sang thiết kế và đầu ra biểu đồ của TV3. [Runner xuất dữ liệu](../SPE-dev-backup/apps/benchmark_experiments_app.py)

## 1. Danh mục thực nghiệm và cấu hình đã chạy

| Tệp kết quả trong `results/` | Mục thiết kế §8 | Số cấu hình và tham số khảo sát | Đầu ra trực quan hóa của TV3 |
|---|---|---|---|
| [e1_throughput_curves.csv](../SPE-dev-backup/results/e1_throughput_curves.csv) | **E1** · Quét tải đến bão hòa | **44 dòng** = `11` mức tải chung `γ ∈ {200, 500, 800, 1.000, 1.200, 2.000, 4.000, 6.000, 7.000, 8.000, 10.000}` req/s × `4` hệ (`EventLoop_c1` K=100; `SpringLoom_c8` K=800; `Bun_c8_k1.0` K=800; `Bun_c8_k1.25` K=800). `s = 1 ms, D = 50 ms`; `n_req = 30.000` (`γ < 6.000`) và `45.000` (`γ ≥ 6.000`). | `fig1_e1_throughput`, `fig2_latency`, lát cắt tải `fig3_blocking`, bản đồ nhiệt `fig4_utilization` |
| [e2_capacity_delay.csv](../SPE-dev-backup/results/e2_capacity_delay.csv) | **E4** · Sức chứa `K` và số core `c` | **30 dòng (28 cấu hình độc lập)** tại `γ = 7.500 req/s, s = 1 ms, D = 50 ms, n_req = 35.000`: (1) Nhánh `sweep_K`: `5` mức `K ∈ {16, 40, 80, 200, 800}` × `2` phân phối CPU (`exp`, `det`) × `2` hệ (`Loom κ=1`, `Bun κ=1,25`) ở `c = 8` (`20` dòng); (2) Nhánh `sweep_c`: `5` mức `c ∈ {1, 2, 4, 8, 16}` × `2` hệ (`shared κ=1`, `Bun κ=1,25`) ở `K = 200, exp` (`10` dòng, chung `2` điểm gốc `c = 8, K = 200, exp` với Nhánh 1). | Lát cắt `K` của `fig3_blocking`, `fig6_capacity`, `loom_vs_bun`, `sensitivity_c` |
| [e3_loom_vs_bun_sensitivity.csv](../SPE-dev-backup/results/e3_loom_vs_bun_sensitivity.csv) | **E3** · Độ nhạy `D`, `s` và kịch bản **S6** (`κ`) | **16 dòng (14 cấu hình độc lập)** tại `c = 8, K = 160, n_req = 30.000`: (1) Quét `κ ∈ {1,0; 1,25; 1,5}` cho Bun kèm `SpringLoom κ = 1,0` ở `γ = 7.000, s = 1 ms, D = 50 ms` (`4` dòng); (2) Quét `D ∈ {10, 50, 200} ms` × `2` hệ (`Loom κ=1`, `Bun κ=1,25`) ở `γ = 6.000, s = 1 ms` (`6` dòng); (3) Quét `s ∈ {0,5; 1,0; 2,0} ms` × `2` hệ ở `γ = 6.000, D = 50 ms` (`6` dòng, chung `2` điểm gốc `D = 50 ms, s = 1,0 ms` với Nhánh 2). | Bản đồ nhiệt `fig4_utilization`, `fig5_io_delay`, `sensitivity_kappa`, `sensitivity_s` |
| [e4_closed_loop.csv](../SPE-dev-backup/results/e4_closed_loop.csv) | **E2** · Hệ kín (`C` kết nối) | **30 dòng** = `5` mức kết nối `C ∈ {100, 500, 1.500, 3.000, 5.000}` × `3` hệ (`EventLoop c=1`, `Bun c=8 κ=1,25`, `SpringLoom c=8 κ=1`) × `2` nhánh bộ đệm: `K` hữu hạn (`K = 200` hoặc `800`, `n_req = max(40.000, 100·C)`) và `K = ∞` (`K = 10⁹`, `n_req = max(40.000, 40·C)`). `z = 0, t_err = 10 ms`. | `fig7_closed_loop` |
| [e5_special_scenarios.csv](../SPE-dev-backup/results/e5_special_scenarios.csv) | **§7.4** · Kịch bản mở rộng **S8** và **S10** | **4 dòng** (`n_req = 30.000`): `2` cấu hình S8 (`backend_limit = 300, γ = 7.000, c = 8, K = 400` cho `Loom κ=1` và `Bun κ=1,25`) + `2` cấu hình S10 (`γ = 900, heavy_prob = 5%, heavy_mult = 20` cho `EventLoop c=1, K=200` và `SpringLoom c=8, K=800`). | `s8_backend`, `s10_long_cpu` |
| [verification_summary.csv](../SPE-dev-backup/results/verification_summary.csv) | **E5** · Kiểm chứng từng trạm đơn | **18 dòng** = `6` mô hình (`M/M/1`, `M/M/1/K`, `M/M/∞`, `M/M/c/c`, `M/M/c`, `M/M/c/K`) × `3` mức tải (`low`, `mid`, `high`), mỗi dòng `15` seed (`1..15`), đối chiếu đồng thời `X, W, L, P_block` kèm CI95 (`Pass_5pct` đạt `18/18`). | Bảng [fig8_verification.md](../SPE-dev-backup/results/figures/fig8_verification.md) |
| [raw_seed_runs.csv](../SPE-dev-backup/results/raw_seed_runs.csv) | Dữ liệu gốc từng hạt giống | **1.240 dòng** = `124` cấu hình của `e1`–`e5` × `10` seed (`100..109`). Lưu các chỉ số gốc của từng lượt mô phỏng. | CI95 của tích `X·R` trong `fig7_closed_loop` và kiểm định ghép cặp §9.4 trong `analysis_summary.md` |

## 2. Quy trình tổng hợp thống kê và kiểm định

- **Khoảng tin cậy trên từng cấu hình:** mỗi cấu hình trong `e1`–`e5` chạy `10` hạt giống cố định `100..109` (kiểm chứng `assert m.conservation_ok` sau từng lượt), từ đó tính trung bình mẫu, độ lệch chuẩn `s` (`ddof = 1`) và khoảng tin cậy 95% theo phân phối t-Student (`df = 9`). Với các kịch bản hệ mở dùng phân phối mũ và backend vô hạn, runner đính kèm các cột nghiệm giải tích chính xác `ana_*`. [Hàm giải tích và CI95](../SPE-dev-backup/scenarios/analytical.py)
- **Khai thác dữ liệu từng seed (`raw_seed_runs.csv`):**
  1. Ở hệ kín (`E4`), `plotting_app.py` nhân trực tiếp `XR = X · R` và `XRLittle = X · R + X_err · t_err` trong từng hạt giống rồi mới ước lượng trung bình và CI95 qua 10 hạt giống, thay vì nhân hai giá trị trung bình rời rạc.
  2. Khi so sánh Spring Loom và Bun trên cùng điều kiện tải (`E1`, `E2`, `E3`), hai hệ nhận cùng chuỗi sự kiện ngẫu nhiên từ tập seed `100..109` (*Common Random Numbers*), cho phép thực hiện đồng thời kiểm định t ghép cặp trên hiệu số từng seed (`p_pair`), kiểm định phi tham số Mann–Whitney U (`MW p`) và kích thước hiệu ứng Cohen's `d`.
  3. Với hai cặp dòng điểm gốc xuất hiện ở cả hai nhánh quét trong `e2` (`c = 8, K = 200, exp`) và `e3` (`D = 50 ms, s = 1,0 ms`), bộ phân tích tự động xác minh các chỉ số trùng khít tuyệt đối rồi gộp lại để không nhân đôi trọng số trong các bảng tổng hợp §9.2–§9.4.

## 3. Ghi chú về phạm vi thực nghiệm

- Các phép quét `s` (tại `γ = 6.000 req/s` cố định trong `E3`) và quét `c` (tại `γ = 7.500 req/s, K = 200` cố định trong `E2`) được thiết kế theo lát cắt thay đổi từng yếu tố một (OFAT) trên cùng dòng tải tuyệt đối để quan sát trực tiếp quá trình chuyển pha từ thiếu tài nguyên sang dư tài nguyên.
- Thí nghiệm giai thừa `2³` (**E6** trong notebook §8) nằm ngoài danh mục 6 CSV của bản phân công TV2 (`Assign_tasks.docx`); mã nguồn `apps/plotting_app.py` đã cài đặt sẵn hàm `_factorial` để tự động xuất bảng ANOVA ngay khi bổ sung tệp `e6*.csv`.

Toàn bộ kết quả phân tích định lượng được trình bày tại [tài liệu kiến trúc và đánh giá](../SPE-dev-backup/docs/architecture.md) và [bản phân tích tự động](../SPE-dev-backup/results/figures/analysis_summary.md).
