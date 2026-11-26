# SPE-dev-demo

Mã mô phỏng DES so sánh Event Loop với một worker, Spring Loom với một hàng CPU chung và Bun với nhiều hàng CPU riêng. Các mô hình nối tiếp trạm I/O. Các cấu hình thực nghiệm và kết quả được trình bày trong [mô tả thí nghiệm](../A%20description%20of%20the%20experiments/Experiments.pdf) và [báo cáo kiểm chứng và đánh giá](../Validation%20and%20evaluation/Validation-and-evaluation.pdf).

## Cây thư mục

```text
SPE-dev-demo/
├── .venv/                          # Môi trường Python tạo trên máy khi cài đặt
├── bkitevsim/                      # Lõi mô phỏng, bộ điều phối và hàng đợi sự kiện
├── design/
│   ├── design.ipynb
│   └── Spe-Ass-Spec-YY9B.pdf
├── scenarios/
│   ├── __init__.py
│   ├── config.py
│   ├── async_runtime_lps.py
│   └── analytical.py
├── apps/
│   ├── __init__.py
│   ├── synchronous_sequential_app.py
│   ├── distributed_sequential_app.py
│   ├── simulator_app.py
│   ├── benchmark_experiments_app.py
│   └── plotting_app.py
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   └── test_invariants.py
├── results/
│   ├── .gitkeep
│   ├── verification_summary.csv
│   ├── e1_throughput_curves.csv
│   ├── e2_capacity_delay.csv
│   ├── e3_loom_vs_bun_sensitivity.csv
│   ├── e4_closed_loop.csv
│   ├── e5_special_scenarios.csv
│   ├── raw_seed_runs.csv
│   └── figures/                    # Năm biểu đồ, mỗi hình có bản PNG và PDF
│       └── .gitkeep
├── docs/
│   ├── architecture.md
│   ├── user_manual.md
│   └── diagrams/
│       ├── .gitkeep
│       ├── architecture.svg
│       └── classes.svg
├── exam/
│   └── .gitkeep
├── Makefile
├── requirements.txt
├── LICENSE
└── README.md
```

Thư mục `design/` chứa [notebook thiết kế](design/design.ipynb) và [bản thiết kế Phase 1](design/Spe-Ass-Spec-YY9B.pdf). Sáu bảng tổng hợp ở mốc `ff8df35` gồm một bảng kiểm chứng và năm bảng E1–E5. [Dữ liệu từng seed](results/raw_seed_runs.csv) nằm cùng thư mục với các bảng này.

## Chạy trên dữ liệu bàn giao

Từ thư mục chứa tệp này, cài môi trường theo [hướng dẫn sử dụng](docs/user_manual.md). Các lệnh sau chạy 19 kiểm thử mô hình và bất biến, vẽ lại hình và đóng gói bằng GNU Make.

```sh
python -X utf8 -m pytest -v tests
python -X utf8 -m apps.plotting_app
make pack
```

Dùng `make pack` để đóng gói mã nguồn, kết quả, năm PDF và [bản nộp Phase 1](../The%20Phase%201%20submission/Spe-Ass-Spec-YY9B.pdf). `make run-exp` và `make all-pipeline` chạy lại thí nghiệm và ghi lại CSV. Có thể dùng bản sao của dự án khi cần so sánh một lần chạy mới với số liệu bàn giao.

Các tài liệu Phase 2 mô tả nguồn tải, cửa sổ đo và các cấu hình E1–E5 trong CSV bàn giao. [Workload Phase 2](../A%20description%20of%20the%20workload/Workload.pdf) · [Thí nghiệm Phase 2](../A%20description%20of%20the%20experiments/Experiments.pdf)

[Cấu trúc bài nộp](../README.md) · [Kiểm chứng và đánh giá](../Validation%20and%20evaluation/Validation-and-evaluation.pdf) · [Kiến trúc và bảy câu hỏi nghiên cứu](docs/architecture.md)
