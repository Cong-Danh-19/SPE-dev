<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:7f4682166a0c6433fe06301c6fe50dbf9dc312c2e35e48bf11ae638415f9db0c -->

# Thí nghiệm Phase 2

Đề CO3007 yêu cầu sáu mô hình hàng đợi, một mạng hàng đợi và phân tích độ nhạy. Dự án đáp ứng phần mô hình bằng các LP của BkitEvsim và mạng CPU → I/O. Thư mục `bkitevsim/` thuộc khung DES của đề. Phần mô hình riêng nằm chủ yếu trong `scenarios/` và `apps/simulator_app.py`.

## Lưới runner hiện hành

| Đầu ra | Cấu hình × seed mặc định | Nội dung |
|---|---:|---|
| Verification | 18 × 15 | Sáu mô hình trạm đơn, ba mức tải |
| E1 | 44 × 10 | 11 mức tải, Event Loop, Loom và hai giá trị κ của Bun |
| E2 | 30 × 10 | Quét K và c; ghi cả K danh nghĩa và sức chứa thực |
| E3 | 16 × 10 | Quét κ, D, s riêng từng yếu tố |
| E4 | 30 × 10 | Tải kín, năm mức C, ba hệ, K hữu hạn hoặc rất lớn |
| E5 | 4 × 10 | S8 giới hạn backend và S10 có tác vụ dài |
| E6 (chọn riêng) | 8 × 10 | Ma trận 2³ theo §8 của notebook: ρ, K/core, c |

Tổng mặc định là **1.510 lượt**, khoảng 88 triệu request. E4 chiếm 45 triệu request và có ca lên tới 500.000 request mỗi seed theo công thức thiết kế `100·C`. Phase 1 dùng số hiệu khác: E2 trong notebook là E4 của runner; phần kiểm chứng E5 của notebook nằm ở CSV Verification. E3 hiện quét từng yếu tố, chưa có lưới D × s đầy đủ. S9 cần chọn cấu hình theo mục tiêu và ràng buộc cụ thể. S10 so sánh hai cấu hình hoàn chỉnh (đổi cả c và K); để quy khác biệt cho tác vụ nặng cần thêm đối chứng cùng c, K và chỉ đổi `heavy_prob`.

## Phép đo

- Sau khi phát đủ request, hàng sự kiện chạy đến khi rỗng. Lượt chạy thiếu request, có request chưa xử lý hoặc không bảo toàn bị báo lỗi.
- `Pblock = (n_rejected_cpu + n_rejected_io) / n_arrived`, theo **thời điểm vào hệ** trong đoạn đóng `[t_warm, t_stop]`. Request đến trong cửa sổ vẫn được tính nếu bị từ chối sau `t_stop`. Các request có timestamp bằng ranh giới được tính cùng nhau; `warm_reqs` là số đã bỏ thực tế.
- `X` đếm hoàn tất thành công, `X_err` đếm lần phát sinh từ chối, theo **thời điểm sự kiện kết thúc** trong cùng đoạn. Do đó `n_done + n_rejected` có thể khác `n_arrived`. `p95/p99` đo phản hồi toàn hệ; `p95_cpu/p99_cpu` đo từ khi vào CPU đến khi rời CPU theo thời điểm rời CPU, kể cả request bị backend từ chối sau đó. Các cột trung bình `W_cpu/Wq` giữ nhóm hoàn tất toàn hệ để so với các CSV cũ; `W_io` đo riêng thời gian trong trạm I/O.
- `L_cpu`, `U`, `L_io` là trung bình theo thời gian, tích phân giữa các mốc thay đổi trạng thái. `K + X_max·D` là giới hạn cho trung bình trong giả thiết trạng thái dừng và I/O vô hạn, không phải giới hạn tức thời. Với S8 tải kín, nếu dùng Little cho số kết nối, cần tính cả thời gian trước khi backend từ chối.
- Bun có `effective_K = c·floor(K/c)` theo quy ước giữ các hàng bằng nhau. E2 với K=200, c=16: Bun có 192 chỗ, Loom có 200. So sánh cùng sức chứa thực nên dùng K chia hết cho c. Nghiệm Poisson không áp dụng cho Bun round-robin nhiều hàng, tải kín, CPU không mũ, tác vụ nặng hoặc backend hữu hạn.
- H8 (§8.1): `Pass_H8` đòi đồng thời sai số tương đối <5% và nghiệm nằm trong CI95 cho X, W, L, Pblock. Khi nghiệm Pblock bằng 0, yêu cầu số đo bằng 0; một seed không đủ lập CI95. `Pass_5pct` giữ quy tắc cũ (Pblock được phép sai khác dưới 1 điểm phần trăm) để đối chiếu. M/M/∞ so thời gian **tại I/O** với D.
- Warm-up gần bão hòa có thể lên tới 50% và vẫn chưa đủ cho K lớn tại ρ≈1. Dùng `--only E1-convergence` để so 45.000, 180.000, 720.000 request với cùng seed và warm-up 50%. Báo số đo vận hành trên cửa sổ hữu hạn và nghiệm trạng thái dừng riêng. Không dùng một lần chạy để kết luận về ngưỡng 100 ms.

CSV đã lưu trong Git được tạo trước khi sửa phép đo; hãy chạy lại trước khi trích các cột mới hay công bố kết quả.

<!-- /coderabbit-ai-generated:v1 -->
