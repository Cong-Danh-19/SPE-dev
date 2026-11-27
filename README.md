<!-- coderabbit-ai-generated:v1 -->

# SPE · YY9B
Mô phỏng mạng CPU → I/O không chặn trên BkitEvsim cho ba cách tổ chức CPU: Event Loop, Bun và Loom. Bắt đầu từ [hướng dẫn chạy](A%20user%20manual/README.md), [thiết kế chính thức của nhóm](The%20Phase%201%20submission/Spe-Ass-Spec-YY9B.pdf) hoặc [báo cáo kết quả](SPE-dev-backup/results/phase1_design/report.html) <!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:c49146a60e9c16585a4a30c2818df8b2d12e7eb046a349c2ba5c7de2f2e72958 -->

(tải xuống và mở bằng trình duyệt).

## Kết quả theo thiết kế

Đã chạy 107 cấu hình × 10 seed. Tất cả các lượt đều bảo toàn request. Ở E1, với s = 1 ms và D = 50 ms:

| Mô hình | Tải cao nhất trên lưới đạt cả 4 ngưỡng (req/s) | Thông lượng tại tải 8.800 req/s | Tỷ lệ từ chối tại tải 8.800 req/s |
|---|---:|---:|---:|
| Event Loop | 950 | 997 | 88,70% |
| Bun, 8 hàng riêng | 7.500 | 7.973 | 8,30% |
| Loom, 1 hàng chung | 7.500 | 7.977 | 7,84% |

Các ngưỡng Bảng 1 là R < 100 ms, p99 < 300 ms, xác suất từ chối < 1% và X ≥ 95% tải gửi. Đây là kết quả của mô hình CPU–I/O. Mục E5 trong báo cáo liệt kê cả các chỉ số nằm ngoài ngưỡng kiểm chứng; phép đo bổ sung dùng seed độc lập.

<!-- /coderabbit-ai-generated:v1 -->
