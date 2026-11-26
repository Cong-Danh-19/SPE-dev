# hk261_spe_BKsyspeEvsim — Đánh giá Hiệu năng Cơ chế Bất đồng bộ bằng Mô phỏng DES

Dự án mô phỏng hệ thống sự kiện rời rạc đánh giá 3 kiến trúc xử lý bất đồng bộ:
- **Event Loop** ($M/M/1/K$)
- **Bun Multi-Kernel Thread** ($N \times M/M/1/K$)
- **Spring Loom Virtual Thread** ($M/M/c/K$)

nối tiếp trạm I/O ($M/M/\infty$).

## 1. Cài đặt môi trường
```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash)
# source .venv/bin/activate       # Linux / macOS

pip install -r requirements.txt
```

## 2. Phân công thư mục cho 3 thành viên
- **Thành viên 1 (`feat/tv1-core-engine`):** `scenarios/config.py`, `scenarios/async_runtime_lps.py`, `apps/simulator_app.py`
- **Thành viên 2 (`feat/tv2-analytical-experiments`):** `scenarios/analytical.py`, `apps/benchmark_experiments_app.py`, `tests/test_models.py`, `tests/test_invariants.py`
- **Thành viên 3 (`feat/tv3-plotting-docs`):** `apps/plotting_app.py`, `docs/architecture.md`, `docs/user_manual.md`, `docs/diagrams/`

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:cae9e53b801a80ebe7b568c4f849bf2b5d53d042575ba5266c2bf01d19ba916b -->

## 3. Quy trình chạy

```bash
make test-fast      # Kiểm tra hồi quy nhanh
make run-exp-fast   # Thử luồng benchmark, ghi CSV thử vào results-local/
make test           # Toàn bộ test và kiểm chứng thống kê
make run-exp        # Verification và E1–E5 đầy đủ, ghi CSV vào results/
make plot           # Vẽ thông lượng E1 với CI95
make pack          # Đóng gói bài nộp
```

Xem [hướng dẫn chạy theo từng thí nghiệm](docs/user_manual.md) và [định nghĩa phép đo, phạm vi thí nghiệm](docs/experiments.md).

<!-- /coderabbit-ai-generated:v1 -->
