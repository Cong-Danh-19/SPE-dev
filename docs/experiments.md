# Mô tả thí nghiệm

Kế hoạch nằm trong `asyncsim/experiments.py` (hàm `build_plan`); mỗi cấu hình chạy với 10 hạt giống cố định, thứ tự chạy được ngẫu nhiên hóa (`random_state = 2026`).

| # | Thí nghiệm | Factor đổi | Giữ cố định | Số cấu hình | Trả lời |
|---|---|---|---|---|---|
| E1 | Quét tải tới bão hòa | γ ∈ {200 … 8.800} req/s; hệ ∈ {EventLoop, Bun, Loom} | s = 1 ms, D = 50 ms, K/core = 100 | 33 | hệ nào bão hòa trước; hàng chung (Loom) so với hàng riêng (Bun) |
| E2 | Closed-loop | C ∈ {100; 1.500; 5.000} × K/core ∈ {100; ∞}; 3 hệ | s, D; t_err = 10 ms; n_req = max(30.000; 100·C) khi K hữu hạn | 18 | tỉ lệ lỗi và Little khi C > K |
| E3 | Độ trễ I/O và thời gian CPU | D ∈ {10; 50; 200 ms} × s ∈ {0,2; 1; 5 ms}; 3 hệ | γ = 0,8/s | 27 | R tăng đúng D; CPU-bound hay I/O-bound |
| E4 | Số core và dung lượng | c ∈ {1; 4; 8} × K/core ∈ {10; 100; ∞} | ρ_ref = 0,95 | 9 | ảnh hưởng của c, K lên P_block và R |
| E5 | Validation | 6 mô hình node đơn × 3 mức tải; tandem; closed-loop | – | 36+ kiểm tra | mô phỏng so với giải tích (`validate.py`) |
| E6 | Giai thừa 2³ | ρ_ref {0,7; 1,1} × K/core {10; 100} × c {1; 8} | – | 8 | tương tác giữa các yếu tố |
| E7 | Độ nhạy κ của Bun (kịch bản S6) | κ ∈ {1; 1,25; 1,5} × γ ∈ {4.000; 5.000; 6.000; 7.500} | – | 12 | κ dịch điểm bão hòa của Bun |

Tổng: **1.070 lần chạy** (E1–E4, E6, E7) cộng bộ validation.

## Quy trình mỗi lần chạy

1. Khởi tạo `Simulation` với các LP theo `layout`.
2. Chạy đến khi `SourceLP` gửi đủ `n_req` request và hệ thống rỗng.
3. Bỏ 10% đầu (warm-up), tính chỉ số trên cửa sổ còn lại; trung bình theo thời gian cho `L_cpu`, `U`, `L_io`.
4. Kiểm tra bảo toàn request (`sent = done + rejected + remaining`) và bất biến (số bận ≤ c, số ở hệ CPU ≤ K). Lần chạy vi phạm bị loại ở bước phân tích.
5. Với open-loop, ghi thêm dự đoán giải tích (`th_X`, `th_R`, `th_Pblock`, `th_U`) để đối chiếu.

## Phân tích (`asyncsim/analysis.py`)

Trung bình và khoảng tin cậy 95% (t-Student, 9 bậc tự do khi 10 hạt giống) theo từng cấu hình; điểm bão hòa của E1; hiệu ứng chính và tương tác của E6; bảy hình và `report.md`.

| Hình | Nội dung | Thí nghiệm |
|---|---|---|
| 1 | thông lượng theo tải, mô phỏng và giải tích | E1 |
| 2 | R trung bình và p99 theo tải | E1 |
| 3 | P_block theo K, mô phỏng và giải tích | E4 |
| 4 | bản đồ nhiệt U theo (hệ, tải) | E1 |
| 5 | R theo D | E3 |
| 6 | bản đồ nhiệt P_block theo (c, K/core) | E4 |
| 7 | Little và tỉ lệ lỗi theo C | E2 |
