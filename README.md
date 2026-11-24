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
# Copy thư mục lõi bkitevsim từ template đề tài vào ./bkitevsim/
```

## 2. Phân công thư mục cho 3 thành viên
- **Thành viên 1 (`feat/tv1-core-engine`):** `scenarios/config.py`, `scenarios/async_runtime_lps.py`, `apps/simulator_app.py`
- **Thành viên 2 (`feat/tv2-analytical-experiments`):** `scenarios/analytical.py`, `apps/benchmark_experiments_app.py`, `tests/test_models.py`, `tests/test_invariants.py`
- **Thành viên 3 (`feat/tv3-plotting-docs`):** `apps/plotting_app.py`, `docs/architecture.md`, `docs/user_manual.md`, `docs/diagrams/`

## 3. Quy trình chạy chuẩn
```bash
make test          # Chạy kiểm thử Verification (sai số giải tích < 5% & bất biến hệ thống)
make run-exp       # Chạy thực nghiệm E1-E5 và xuất CSV ra results/
make plot          # Vẽ biểu đồ CI95 ra results/figures/
make pack          # Đóng gói tệp nộp bài Spe-Ass-final-<GroupName>.zip
```
