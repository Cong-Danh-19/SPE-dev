# Hướng dẫn chạy và đóng gói Phase 2

Sau khi giải nén `Spe-Ass-final-YY9B.zip`, mở thư mục `Spe-Ass-final-YY9B/`. Mỗi mục Phase 2 có một PDF riêng. Mở `Validation and evaluation/Validation-and-evaluation.pdf` để xem kết quả kiểm chứng, bảy câu hỏi nghiên cứu và các biểu đồ. Các hình PNG/PDF cũng có ở `SPE-dev-demo/results/figures/`.

Để chạy chương trình, mở terminal ở `Spe-Ass-final-YY9B/`, nhập lệnh sau rồi thực hiện các bước bên dưới.

```sh
cd SPE-dev-demo
```

## Cài đặt

Dùng Python 3.11 trở lên. Để đóng gói bài nộp bằng `make pack`, cài thêm GNU Make. Thư viện mô phỏng BkitEvsim đi kèm trong thư mục `bkitevsim/`.

**Windows PowerShell**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Nếu PowerShell hạn chế kích hoạt môi trường, có thể dùng các lệnh Python trực tiếp trong bảng bên dưới, thay `python` bằng `.\.venv\Scripts\python.exe`.

**Linux, macOS hoặc Git Bash**

```bash
python -m venv .venv
source .venv/bin/activate       # Linux, macOS
# source .venv/Scripts/activate # Git Bash trên Windows
python -m pip install -r requirements.txt
```

## Các lệnh và đầu ra

| Lệnh Make | Lệnh Python | Đầu ra |
| --- | --- | --- |
| `make install` | `python -m pip install -r requirements.txt` | Cài các thư viện. |
| `make test` | `python -X utf8 -m pytest -v tests` | Kết quả của 19 kiểm thử mô hình và bất biến. |
| `make run-exp` | `python -X utf8 -u -m apps.benchmark_experiments_app` | Bộ chạy ghi sáu bảng tổng hợp và một tệp dữ liệu từng seed vào `results/`. |
| `make plot` | `python -X utf8 -m apps.plotting_app` | Đọc CSV đã có, xuất hình PNG 300 dpi và PDF vector. |
| `make pack` | — | Kiểm tra thành phần và CRC, tạo `Spe-Ass-final-YY9B.zip` cạnh thư mục `Spe-Ass-final-YY9B/`. |

Các biểu đồ và báo cáo dùng sáu bảng tổng hợp trong `results/` và dữ liệu từng seed trong `results/raw_seed_runs.csv`. Hai lệnh sau vẽ lại hình rồi đóng gói bài nộp cùng năm PDF Phase 2.

```bash
make plot
make pack
```

Các lệnh `make run-exp` và `make all-pipeline` ghi lại CSV. Lệnh vẽ đọc `results/raw_seed_runs.csv`. Trong ZIP, tệp này nằm ở `SPE-dev-demo/results/raw_seed_runs.csv`.

## Chạy một cấu hình riêng

Ví dụ sau đo mô hình hàng chung với 8 worker, 160 chỗ tại CPU, γ=7.000 request/s và I/O trung bình 50 ms. Mở trình thông dịch bằng `python` từ thư mục `SPE-dev-demo/`.

```python
from apps.simulator_app import run_simulation
from scenarios.config import SimConfig

cfg = SimConfig(gamma=7000, c=8, K=160, s=0.001, D=0.05,
                arch="shared", n_req=20000, seed=100)
m = run_simulation(cfg)
print(m.X, m.R * 1000, m.Pblock, m.conservation_ok)
```

Với seed 100, kết quả làm tròn là 6.988,93 request/s, 51,73 ms, tỷ lệ từ chối 0 và `True` cho kiểm tra bảo toàn request. Để mô phỏng Bun cùng công suất, dùng `arch="partitioned", routing="random", kappa=1.0`. Để thử hệ kín, đặt `gamma=0, closed_C=1500, t_err=0.01`. Hàm `run_replications` trong `apps.simulator_app` nhận `cfg, n_seeds=10, start_seed=100` và trả trung bình, độ lệch chuẩn cùng CI95 của từng chỉ số. Trên Windows, đặt lời gọi chạy nhiều seed trong khối `if __name__ == "__main__":` của một tệp Python rồi chạy tệp đó.

## Tra số liệu và hình

| Cần đọc | Tệp hoặc nhóm hình |
| --- | --- |
| Trần thông lượng khi tăng γ | `e1_throughput_curves.csv`, hình `fig1_e1_throughput` |
| Từ chối và R, p95, p99 khi đổi K | `e2_capacity_delay.csv`, hình `fig2_e2_capacity_delay` |
| Loom/Bun, ảnh hưởng κ, D, s, c | `e3_loom_vs_bun_sensitivity.csv` và phép quét c của E2, hình `fig3_e3_sensitivity` |
| Little hệ kín, S8 và S10 | `e4_closed_loop.csv`, `e5_special_scenarios.csv`, hình `fig4a_e4_closed_loop` và `fig4b_e5_bottlenecks` |
| Kiểm chứng và tính lại CI | `verification_summary.csv` và `raw_seed_runs.csv` |

Trong CSV tổng hợp, `R_mean` là độ trễ trung bình tính bằng giây. `R_ci_low` và `R_ci_high` là hai cận CI95. Trường `ana_*` để trống ở những cấu hình mà bộ chạy không áp dụng công thức. Với bộ kết quả ở thư mục khác, dùng `python -X utf8 -m apps.plotting_app --results-dir <thu_muc_csv> --fig-dir <thu_muc_hinh>`. Khi có `raw_seed_runs.csv` cùng bộ kết quả, hàng cuối của hình E4 kiểm tra định luật Little trên từng seed. Khi bộ dữ liệu riêng chỉ có năm bảng E1–E5, hàng này hiển thị độ trễ R. [Định nghĩa chỉ số](../../A%20description%20of%20the%20workload/Workload.pdf) · [Ma trận E1–E5](../../A%20description%20of%20the%20experiments/Experiments.pdf)

Ví dụ dưới đây tính lại dòng Loom với C=1.500 và K=800 trong bảng Little. Mỗi seed cho một ước lượng số kết nối, từ đó tính được trung bình và CI95.

```python
import pandas as pd
from scenarios.analytical import summarize_replications

runs = pd.read_csv("results/raw_seed_runs.csv")
loom = runs.query("exp_id == 'E4' and scenario == 'SpringLoom_Kfin_C1500'")
population = loom.X * loom.R + 0.010 * loom.X_err
print(summarize_replications(population.tolist()))
```

Với tám seed bàn giao, trung bình là 1.290,85 kết nối, CI95 từ 1.283,82 đến 1.297,89. Có thể đối chiếu khoảng này với mức đặt C = 1.500 trên hình `fig4a_e4_closed_loop`.
