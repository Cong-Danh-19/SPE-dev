# Mô hình Workload và đơn vị các đại lượng đo

Workload của dự án biểu diễn luồng yêu cầu đi vào máy chủ bất đồng bộ: mỗi request đến trạm CPU, xếp hàng chờ nếu mọi worker đang bận, sử dụng CPU đúng một lần rồi chuyển sang trạm chờ I/O. Worker được giải phóng ngay khi kết thúc pha CPU để nhận request kế tiếp. Ở cấu hình cơ sở, trạm I/O có số chỗ vô hạn (`M/M/∞`) nên nhiều yêu cầu có thể chờ dữ liệu đồng thời mà không giữ CPU. [Sơ đồ luồng sự kiện](../Architecture%20and%20class%20diagrams/architecture.svg)

## 1. Hai cơ chế sinh tải

| Chế độ tải | Quy tắc phát yêu cầu tại `SourceLP` | Tệp dữ liệu áp dụng |
|---|---|---|
| **Hệ mở (Open-loop)** | Khoảng thời gian giữa hai lần đến liên tiếp tuân theo phân phối mũ độc lập với tốc độ trung bình `γ` (request/giây). Tốc độ gửi không phụ thuộc vào trạng thái hàng đợi hay thời điểm hoàn tất của các request trước. | `e1`, `e2`, `e3`, `e5` và `verification_summary.csv` (`closed_C = 0`) |
| **Hệ kín (Closed-loop)** | Duy trì đúng `C` kết nối đồng thời khởi phát tại `t = 0`. Mỗi kết nối chỉ gửi yêu cầu tiếp theo sau khi nhận phản hồi hoàn tất cộng thời gian nghĩ `z = 0`, hoặc sau độ trễ chờ thử lại `t_err = 10 ms` nếu bị từ chối. Giá trị `gamma = 0` trong CSV đánh dấu chế độ hệ kín. | `e4_closed_loop.csv` (`closed_C ∈ {100, 500, 1.500, 3.000, 5.000}`) |

Ở hệ mở, đặt cùng `γ` nghĩa là áp cùng lưu lượng yêu cầu đầu vào cho mọi kiến trúc (ví dụ `γ = 7.500 req/s` trong `E2`). Ở hệ kín, lưu lượng thực tế đập vào cửa CPU phụ thuộc ngược vào tốc độ hoàn tất `X` lẫn tốc độ quay vòng từ chối `X_err`. [Chi tiết các kịch bản thực nghiệm](../A%20description%20of%20the%20experiments/README.md)

## 2. Hệ tham số cấu hình mô hình

| Tham số | Ý nghĩa vật lý và miền giá trị trong bộ dữ liệu |
|---|---|
| `c`, `K` | `c` là số worker / carrier thread / kernel thread (`c = 1` cho Event loop; `c = 8` cho cấu hình chuẩn của Loom và Bun; quét `c ∈ {1, 2, 4, 8, 16}` ở nhánh 2 của `E2`). `K` là tổng sức chứa của trạm CPU gồm cả request đang xử lý và đang xếp hàng (`K = 10⁹` biểu diễn bộ đệm vô hạn `K = ∞` trong `verification_summary.csv` và nhánh `Kinf` của `E4`). Với Bun, mỗi hàng riêng có sức chứa `max(1, K // c)`. |
| `s`, `κ` | `s` là thời gian phục vụ CPU cơ sở trung bình (`s = 1 ms` ở hầu hết thực nghiệm; quét `s ∈ {0,5; 1,0; 2,0} ms` ở `E3`; `s = 10 ms` ở các ca kiểm chứng trạm CPU đơn). Hệ số `κ` nhân thời gian CPU của Bun thành `s_eff = κ · s` (`κ = 1,0` cho hàng chung Loom/Event loop; Bun dùng `κ = 1,25` mặc định và khảo sát `κ ∈ {1,0; 1,25; 1,5}` ở `E1`, `E3`). |
| `D` | Thời gian chờ I/O trung bình (`D = 50 ms` cơ sở; quét `D ∈ {10, 50, 200} ms` ở `E3`; `D = 0` khi tách riêng trạm CPU để kiểm chứng). |
| `dist_cpu`, `dist_io`, `routing` | `exp` lấy mẫu phân phối mũ; `det` dùng thời gian phục vụ tất định không đổi (khảo sát cho CPU ở nhánh `sweep_K` của `E2`). Bun mặc định chia tải ngẫu nhiên đều `routing = "random"` (tách dòng Poisson thành `c` dòng con tốc độ `γ / c`) và hỗ trợ tùy chọn `routing = "rr"` (Round-Robin). |
| `backend_limit`, `heavy_prob`, `heavy_mult` | Tham số kịch bản đặc biệt trong `E5`: **S8** đặt `backend_limit = 300` chỗ tại trạm I/O (`M/M/300/300`, giá trị `-1` trong CSV biểu diễn không giới hạn); **S10** đặt xác suất `heavy_prob = 0,05` (`5%` request gặp tác vụ CPU nặng gấp `heavy_mult = 20` lần). |

Với trạm I/O không chặn vô hạn chỗ, trần thông lượng thành công dài hạn chỉ do trạm CPU quy định: `X_max = 1 / s` cho Event loop, `c / s` cho Loom và `c / (κ · s)` cho Bun (`s` tính bằng giây; ví dụ `c = 8, s = 1 ms` cho `X_max = 8.000 req/s` ở Loom và `6.400 req/s` ở Bun khi `κ = 1,25`). [Định nghĩa SimConfig](../SPE-dev-backup/scenarios/config.py) · [Hiện thực các LP](../SPE-dev-backup/scenarios/async_runtime_lps.py)

## 3. Ý nghĩa và đơn vị các cột kết quả CSV

| Cột chỉ số | Đơn vị | Định nghĩa đo lường trên cửa sổ `[t_warm, t_stop]` |
|---|---|---|
| `X`, `X_err` | request/giây | Số request hoàn thành (`t_warm ≤ t_arr + R ≤ t_stop`) và số request bị từ chối (`t_warm ≤ t_arr ≤ t_stop`) chia cho độ dài cửa sổ quan sát `T_obs = t_stop − t_warm`. |
| `Pblock`, `U` | Tỉ phần `[0, 1]` | `Pblock = n_rej / (n_done + n_rej)` là xác suất bị từ chối quan sát được; `U` là mức sử dụng trung bình theo thời gian của trạm CPU đã chuẩn hóa theo số worker `c`. Khi vẽ biểu đồ và trình bày bảng, hai đại lượng này được nhân `100` để đổi sang `%`. |
| `R`, `W_cpu`, `Wq` | giây | Trung bình trên các request hoàn thành trong cửa sổ đo: `R` là tổng thời gian phản hồi từ lúc đến tới lúc rời hệ thống; `W_cpu` là thời gian lưu lại trạm CPU (chờ + phục vụ); `Wq` là thời gian xếp hàng chờ worker rảnh. Nhân `1.000` để đổi sang `ms`. |
| `p95`, `p99` | giây | Phân vị thứ 95 và 99 của `R` tính trong từng lượt chạy; cột `p95_mean`, `p99_mean` là trung bình của phân vị đó qua `m` hạt giống. |
| `L_cpu`, `L_io`, `L_sys` | request | Số lượng request trung bình theo thời gian (tích phân đường bậc thang chia cho `T_obs`) tại trạm CPU, tại trạm I/O và trên toàn hệ thống (`L_sys = L_cpu + L_io`). |

Trong 5 CSV tổng hợp `e1`–`e5`, các hậu tố `_mean`, `_std`, `_ci_low`, `_ci_high`, `_half_width` biểu thị trung bình, độ lệch chuẩn mẫu, cận dưới, cận trên và nửa bề rộng khoảng tin cậy 95% (t-Student) qua `n_seeds = 10` hạt giống; các cột tiền tố `ana_*` là nghiệm giải tích tương ứng. Tệp `raw_seed_runs.csv` lưu trị số gốc chưa gộp của từng `seed` kèm `n_done`, `n_rejected`, `T_obs`.

Bộ mô phỏng đặt tỉ lệ khởi động tối thiểu `warm_ratio = 10%` và tự động mở rộng số request khởi động lên tới `50%` đối với các cấu hình hệ mở hữu hạn ở vùng cận bão hòa hoặc quá tải (`γ ≥ 0,85 · c / s_eff`). Nhờ lọc đồng bộ cả tích phân trạng thái (`L`, `U`) lẫn các sự kiện hoàn tất/từ chối đúng trong khoảng `[t_warm, t_stop]`, mọi hệ thức Định luật Little trên hệ mở và hệ kín đều khớp chặt chẽ. [Cài đặt phép đo](../SPE-dev-backup/apps/simulator_app.py) · [Kết quả kiểm chứng](../Validation%20and%20evaluation/README.md)
