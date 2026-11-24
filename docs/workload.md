# Mô tả workload

Workload là chuỗi request đến web server, định nghĩa bởi mô hình tải, mức tải và kịch bản dịch vụ. Mỗi request gồm một đoạn CPU (trung bình `s`) rồi một lần chờ I/O (trung bình `D`), cả hai phân phối mũ.

## Mô hình tải

| Mô hình | Cách sinh | Dùng ở |
|---|---|---|
| open-loop | Poisson với tốc độ γ (req/s), không phụ thuộc phản hồi | E1, E3, E4, E6, E7, validation |
| closed-loop | C kết nối; mỗi kết nối gửi request kế tiếp ngay khi nhận phản hồi (think time 0). Bị từ chối thì chờ `t_err = 10 ms` | E2 |

Quy tắc so sánh nhiều hệ: dùng **cùng tải tuyệt đối γ**. Ở E1 γ lấy từ một danh sách chung `{200, 400, 600, 800, 950, 1100, 1500, 3000, 5000, 7500, 8800}` req/s (event loop bão hòa ở 1.000, Loom và Bun ở 8.000). Ở E3, mỗi cặp `(D, s)` dùng γ = 0,8/s (0,8 lần trần của hệ yếu nhất).

## Kịch bản dịch vụ

| Kịch bản | s | D | Ý nghĩa |
|---|---|---|---|
| I/O-bound | 0,2 ms | 50 ms | chờ I/O chiếm gần hết thời gian |
| CPU-bound | 5 ms | 1 ms | trần là c/s |
| hỗn hợp (cơ sở) | 1 ms | 50 ms | gần request thực |

`s` và `D` do nhóm đặt theo kịch bản và quét độ nhạy (E3); không lấy trực tiếp từ sample.

## Tham số cơ sở

`s = 1 ms`, `D = 50 ms`, `K/core = 100` (tổng K = 100·c), `c` = 1 (event loop) hoặc 8 (Loom, Bun), κ = 1, 10 hạt giống, 30.000 request mỗi lần chạy, bỏ 10% đầu (warm-up).

## Chỉ số

Thông lượng `X`, thời gian phản hồi trung bình `R` và `p95`, `p99`, xác suất bị từ chối `P_block`, mức sử dụng CPU `U`, số request trung bình ở CPU `L_cpu` và ở I/O `L_io`, tỉ lệ lỗi `X_err` (closed-loop). Mỗi lần chạy còn ghi `n_sent`, `conserved` (bảo toàn request) và `inv_ok` (bất biến).
