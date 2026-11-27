<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:3da6f78b9645f65c57b794e255da9c17cee4e7e8558e8694efd49b64045dc2e4 -->

# Hướng dẫn cài đặt, thực thi và đóng gói

Ma trận Phase 1 có thể chạy từng nhóm từ thư mục mã nguồn bằng `python -m apps.design_experiments_app --group E1` (E2, E3, E4 hoặc E6). Mỗi nhóm mặc định dùng 10 seed, ghi vào `results/phase1_design/` và tiếp tục từ checkpoint khi chạy lại cùng môi trường. Dữ liệu cũ cần chạy lại trước khi sử dụng làm kết quả cuối.

<!-- /coderabbit-ai-generated:v1 -->

Từ thư mục gốc `Spe-Ass-final-YY9B`, chuyển vào thư mục mã nguồn để chạy các lệnh ở mục 1–4.

```sh
cd SPE-dev-backup
```

Bảy tệp CSV bàn giao nằm trong `results/`. Để dựng lại hình và bảng từ các CSV này, thực hiện mục 1 và mục 3. Mục 2 dành cho việc chạy lại kiểm thử và mô phỏng.

## 1. Chuẩn bị môi trường

Dự án yêu cầu **Python 3.10 trở lên**. Thư viện lõi `bkitevsim/` đã đi kèm trong mã nguồn; các thư viện tính toán khoa học, vẽ biểu đồ và kiểm thử được liệt kê trong `requirements.txt`.

**Trên Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**Trên Linux hoặc macOS (POSIX shell):**

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Kiểm tra nhanh trình thông dịch Python đang hoạt động và giao diện dòng lệnh của ứng dụng vẽ biểu đồ:

```sh
python -c "import sys; print(sys.executable)"
python -m apps.plotting_app --help
```

> **Lưu ý trên Windows:** Nếu chính sách thực thi của PowerShell chặn `Activate.ps1`, có thể gọi trực tiếp `.\.venv\Scripts\python.exe` thay cho `python` ở mọi câu lệnh bên dưới. Để dùng các lệnh `make`, cài GNU Make (hoặc dùng `mingw32-make` đi kèm MSYS2/MinGW).


## 2. Kiểm thử mô hình và sinh dữ liệu thực nghiệm (TV1 & TV2)

Để chạy bộ **18 bài kiểm thử Verification & Invariants** tự động bằng `pytest` (kiểm chứng 6 mô hình hàng đợi đơn, mạng nối tiếp Tandem Loom/Bun, Định luật Little trên cả hệ mở lẫn hệ kín tải cao `C = 5.000`, định luật bảo toàn request, tính tái lập theo seed, tính tương đương hai bộ điều phối, kịch bản S8/S10 và warm-up động tại `ρ = 1,0`):

```sh
python -m pytest -v
```

Khi muốn chạy lại toàn bộ mô phỏng từ đầu và xuất mới 7 tệp CSV vào `results/` (quá trình chạy 18 cấu hình kiểm chứng × 15 seed và 124 cấu hình thực nghiệm × 10 seed):

```sh
python -m apps.benchmark_experiments_app
```

(Tương đương `make run-exp`; lưu ý lệnh này sẽ ghi đè 7 tệp CSV trong `results/`).

| Tệp CSV trong `results/` | Nội dung dữ liệu |
|---|---|
| `verification_summary.csv` | Đối chiếu 6 mô hình chuẩn × 3 mức tải (`low`, `mid`, `high`), `15` seed/cấu hình, gồm `X, W, L, P_block` kèm CI95 và `Pass_5pct`. |
| `e1_throughput_curves.csv` | Quét 11 mức tải `γ` (`200..10.000 req/s`) cho Event loop, Loom, Bun `κ = 1,0` và Bun `κ = 1,25` (`44` dòng). |
| `e2_capacity_delay.csv` | Quét sức chứa `K ∈ {16..800}` (`exp`/`det`, `c = 8`) và quét số core `c ∈ {1, 2, 4, 8, 16}` (`K = 200, exp`) tại `γ = 7.500 req/s` (`30` dòng). |
| `e3_loom_vs_bun_sensitivity.csv` | Quét chi phí `κ` (kèm mốc Loom `κ = 1`), quét độ trễ I/O `D ∈ {10, 50, 200} ms` và quét thời gian CPU `s ∈ {0,5; 1,0; 2,0} ms` (`16` dòng). |
| `e4_closed_loop.csv` | Hệ kín `C ∈ {100, 500, 1.500, 3.000, 5.000}` trên cả hai nhánh `K` hữu hạn và `K = ∞` cho 3 hệ (`30` dòng). |
| `e5_special_scenarios.csv` | Kịch bản giới hạn kết nối backend S8 (`backend_limit = 300`) và tác vụ CPU nặng S10 (`5%` request dài gấp `20` lần) (`4` dòng). |
| `raw_seed_runs.csv` | Dữ liệu chi tiết từng hạt giống (`1.240` dòng = `124` cấu hình × `10` seed `100..109`). |

## 3. Xuất biểu đồ khoa học và bản phân tích tự động (TV3)

Chạy lệnh `make plot` (hoặc gọi trực tiếp module Python bên dưới) để đọc 7 tệp CSV trong `results/` và sinh trọn bộ đầu ra ở cả hai định dạng **PNG** và **PDF** (độ phân giải `240 DPI`, PDF tái lập byte không gắn nhãn thời gian hệ thống):

```sh
python -m apps.plotting_app --input-dir results --output-dir results/figures --formats png,pdf
```

Nếu muốn xuất thử sang một thư mục kiểm tra riêng mà không chạm vào `results/figures/`:

```sh
python -m apps.plotting_app --input-dir results --output-dir ../../co3007-figures-check --formats png,pdf
```

| Tham số dòng lệnh | Chức năng |
|---|---|
| `--input-dir` | Thư mục chứa các tệp CSV đầu vào (mặc định: `results/`). |
| `--output-dir` | Thư mục ghi ảnh và bảng Markdown (mặc định: `<input-dir>/figures`). |
| `--formats` | Danh sách định dạng ảnh cần xuất: `png`, `pdf` hoặc `png,pdf` (mặc định khi gọi CLI không tham số: `png`; target `make plot` truyền sẵn `png,pdf`). |

Bộ dữ liệu chuẩn sinh đầy đủ **13 biểu đồ khoa học** (26 tệp PNG/PDF), bảng kiểm chứng **H8** và báo cáo phân tích tự động **analysis_summary.md** (không có biểu đồ nào của E1–E5 bị khuyết):

| Nhóm biểu đồ (theo phân công TV3) | Tệp đầu ra trong `results/figures/` | Ý nghĩa phân tích |
|---|---|---|
| **Nhóm 1 · Thông lượng & bão hòa** | `fig1_e1_throughput.{png,pdf}` | Đường cong thông lượng `X` theo tải `γ`, đường ngưỡng `0,95·γ`, trần lý thuyết CPU và điểm gãy `knee` (§9). |
| **Nhóm 2 · Từ chối, độ trễ đuôi & mức bận** | `fig2_latency`, `fig3_blocking`, `fig4_utilization` (`.png`, `.pdf`) | Độ trễ trung bình `R`, `p95`, `p99` so với ngưỡng `100 / 300 ms`; đối chiếu `P_block` mô phỏng vs giải tích; bản đồ nhiệt hiệu suất `U` kèm `[CI95]`. |
| **Nhóm 3 · Loom vs Bun & độ nhạy `κ, D, s, c, K`** | `loom_vs_bun`, `fig5_io_delay`, `fig6_capacity`, `sensitivity_kappa`, `sensitivity_s`, `sensitivity_c` (`.png`, `.pdf`) | Đối chiếu trực tiếp hàng chung vs hàng riêng; chứng minh `R = W_CPU + D`; tách tác động của sức chứa `K/c`, số core `c`, chi phí đồng bộ `κ` và thời gian CPU `s`. |
| **Nhóm 4 · Hệ kín, kịch bản nghẽn & kiểm chứng** | `fig7_closed_loop`, `s8_backend`, `s10_long_cpu` (`.png`, `.pdf`), `fig8_verification.md`, `analysis_summary.md` | Kiểm chứng Định luật Little hệ kín trên cả `K` hữu hạn và `K = ∞` (CI95 theo từng seed); nghẽn backend S8 và CPU dài S10; bảng kiểm chứng 18 cấu hình trạm đơn và kiểm định ghép cặp toàn cục. |

## 4. Xử lý sự cố thường gặp

| Tình huống | Nguyên nhân và cách khắc phục |
|---|---|
| `make test` báo không tìm thấy lệnh `pytest` | Môi trường ảo `.venv` chưa được kích hoạt trên `PATH`. Hãy kích hoạt `.venv` hoặc chạy `python -m pytest -v`. |
| Trên Windows không có lệnh `make` | Dùng `mingw32-make <target>` hoặc chạy trực tiếp các câu lệnh `python -m ...` tương ứng ở Mục 2 và Mục 3. |
| Lỗi `ModuleNotFoundError: No module named 'apps'` | Đang đứng sai thư mục làm việc. Chuyển (`cd`) về thư mục `SPE-dev-backup` chứa `Makefile` và `apps/`. |
| Thiếu tệp hình hoặc cột khi thử CSV tùy chỉnh | Mở `results/figures/analysis_summary.md`, đọc mục *"Phạm vi dữ liệu và ghi chú xử lý"* ở đầu tệp để biết chính xác tệp hoặc cột nào đang thiếu. |

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e41aac5f7cfadd09bc73830c1e2d75c74206b8f3255bf6a2a3c1f1ba333d18d0 -->

## 5. Đóng gói bản nộp

Từ `SPE-dev-backup`, chạy `make pack GROUP=YY9B`. Lệnh tạo `Spe-Ass-final-YY9B.zip` ở gốc repo, bao gồm bảy thư mục, notebook và PDF Phase 1; mã đóng gói kiểm tra tính toàn vẹn ZIP và các tài liệu bắt buộc. Kiểm tra rằng dữ liệu và báo cáo đã được chạy lại, kiểm chứng theo thiết kế trước khi nộp.

```sh
make pack GROUP=YY9B
python -m zipfile -t ../Spe-Ass-final-YY9B.zip
python -m zipfile -l ../Spe-Ass-final-YY9B.zip
```


<!-- /coderabbit-ai-generated:v1 -->
Mã nguồn được sử dụng trong phạm vi học phần CO3007. [Điều khoản sử dụng](../SPE-dev-backup/LICENSE)
