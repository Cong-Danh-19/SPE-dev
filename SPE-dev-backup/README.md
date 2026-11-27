<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:6bc70d9ff864deb412b05d5dc8155703588d2822080d369fd19e136db274de7e -->

# hk261_spe_BKsyspeEvsim — Đánh giá hiệu năng các cơ chế bất đồng bộ

Các CSV và biểu đồ có sẵn được tạo bởi phiên bản trước khi sửa cách đếm từ chối. Chúng là số liệu lịch sử; hãy chạy lại và kiểm chứng trước khi dùng làm kết quả cho mã hiện tại. Notebook Phase 1 nằm trong `design/design.ipynb`.

<!-- /coderabbit-ai-generated:v1 -->

Dự án môn **Đánh giá Hiệu năng Hệ thống (CO3007)** xây dựng bộ mô phỏng sự kiện rời rạc (DES) trên framework `bkitevsim` để phân tích định lượng ba kiến trúc xử lý bất đồng bộ: **Event Loop** đơn luồng (`M/M/1/K`), **Bun Multi-Kernel Thread** hàng đợi riêng (`N × M/M/1/K`) và **Spring Loom Virtual Thread** hàng đợi chung (`M/M/c/K`) nối tiếp trạm chờ I/O không chặn (`M/M/∞` hoặc giới hạn kết nối `M/M/c/c`).

- **Mô hình, kiểm chứng và kết quả** — Sơ đồ luồng sự kiện, biểu đồ lớp UML, ánh xạ thiết kế §8 sang CSV và lời giải định lượng cho bảy câu hỏi nghiên cứu nằm trong [tài liệu kiến trúc](docs/architecture.md).
- **Cài đặt, thực thi và đóng gói** — Quy trình chi tiết cho Windows PowerShell, Linux và macOS nằm trong [hướng dẫn sử dụng](../A%20user%20manual/README.md).
- **Mô hình tải và thiết kế thực nghiệm** — Đơn vị đo, phân phối, tham số và lưới quét của từng tệp dữ liệu nằm trong [mô tả workload](../A%20description%20of%20the%20workload/README.md) và [danh mục thí nghiệm](../A%20description%20of%20the%20experiments/README.md).
- **Hồ sơ nộp bài** — Năm mục tài liệu Phase 2 nằm ở cấp gốc của repo. Tài liệu Phase 1 nằm trong [thư mục Phase 1](../The%20Phase%201%20submission/).

## Tái tạo biểu đồ và phân tích từ bộ dữ liệu chuẩn

Thư mục `results/` lưu trữ **7 tệp CSV chuẩn**:
- Năm tệp thực nghiệm (`e1`–`e5`) gồm **124 dòng cấu hình** (tương ứng **120 cấu hình tham số độc lập**, mỗi cấu hình lặp `10` seed `100..109`).
- Tệp `raw_seed_runs.csv` lưu toàn bộ **1.240 lượt chạy từng seed** để tính khoảng tin cậy 95% (CI95) chính xác cho tích `X·R` ở hệ kín và thực hiện kiểm định ghép cặp Common Random Numbers.
- Tệp `verification_summary.csv` đối chiếu **18 cấu hình trạm đơn** (`6` mô hình × `3` mức tải × `15` seed `1..15`, đạt `18/18` tiêu chí sai số `< 5%`).

Từ thư mục gốc chứa `Makefile`, chạy lệnh dưới đây để đọc các CSV sẵn có và xuất **13 biểu đồ khoa học ở cả hai định dạng PNG và PDF** (26 tệp ảnh), bảng kiểm chứng [fig8_verification.md](results/figures/fig8_verification.md) và báo cáo phân tích tự động [analysis_summary.md](results/figures/analysis_summary.md):

```sh
python -m apps.plotting_app --input-dir results --output-dir results/figures --formats png,pdf
```

## Các lệnh chính của dự án

| Lệnh | Chức năng | Đầu ra |
|---|---|---|
| `python -m pytest -v` | Thực thi bộ 18 kiểm thử tự động (6 mô hình đơn, Tandem, Little open/closed-loop, bảo toàn request, tái lập seed, tương đương dispatcher, S8/S10, warm-up `ρ=1`) | Kết quả kiểm thử `pytest` (`18 passed`) |
| `make run-exp` | Chạy lại toàn bộ bảng kiểm chứng và thực nghiệm E1–E5 (TV2) | Ghi mới 7 tệp CSV trong `results/` |
| `make plot` | Đọc dữ liệu từ `results/` và sinh trọn bộ hình PNG/PDF cùng bảng phân tích (TV3) | 26 tệp ảnh PNG/PDF, `fig8_verification.md` và `analysis_summary.md` trong `results/figures/` |
| Đóng gói cả repo sau khi có Phase 1 | Xem mục 5 trong [hướng dẫn sử dụng](../A%20user%20manual/README.md) | `Spe-Ass-final-YY9B.zip` |

Trên Windows có thể gọi `mingw32-make` (hoặc `make` nếu đã cài GNU Make). Target `make all-pipeline` chạy tuần tự `test` → `run-exp` → `plot`. Khi chỉ muốn tái tạo hình vẽ từ bộ CSV bàn giao mà không chạy lại mô phỏng, dùng `make plot` hoặc câu lệnh `python -m apps.plotting_app` ở trên.

## Phân công và cấu trúc thành phần

| Thành viên | Phụ trách | Tệp sở hữu chính |
|---|---|---|
| TV1 · Core DES Engine & Queuing Models | Sáu Logical Process, chế độ open/closed-loop, cửa sổ đo theo thời điểm hoàn tất và warm-up động vùng cận bão hòa (`ρ ≥ 0,85`) | `scenarios/config.py`, `scenarios/async_runtime_lps.py`, `apps/simulator_app.py` |
| TV2 · Analytical Models, Verification & Runner | Nghiệm giải tích không gian log, bộ kiểm thử `pytest` 18 ca và ứng dụng xuất 7 tệp CSV đa hạt giống | `scenarios/analytical.py`, `tests/`, `apps/benchmark_experiments_app.py`, `results/*.csv` |
| TV3 · Visualization, Analysis & Packaging | Ứng dụng trực quan hóa 13 biểu đồ CI95 và kiểm định ghép cặp, sơ đồ kiến trúc/UML, tài liệu Phase 2 và đóng gói `pack` | `apps/plotting_app.py`, `results/figures/`, `docs/`, `Makefile`, `README.md` |

Framework lõi `bkitevsim/` được giữ nguyên từ bộ mã nguồn của môn học CO3007. Vui lòng xem điều khoản sử dụng tại [LICENSE](LICENSE).
