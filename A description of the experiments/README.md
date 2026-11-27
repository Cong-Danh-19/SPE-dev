<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e43e34d54c750d56e5b0766d1489f75b32920f583b44f2fa3bf66655fb15f3f3 -->

# Ma trận thí nghiệm chính thức
Theo Bảng 9–10 của [PDF Phase 1](../The%20Phase%201%20submission/Spe-Ass-Spec-YY9B.pdf). [Mã chạy](../SPE-dev-backup/apps/design_experiments_app.py) dùng 10 seed (1–10) cho mỗi cấu hình; thứ tự chạy trong từng nhóm được xáo với seed 2026. Mỗi lượt sinh 30.000 request, trừ E2 hữu hạn dùng max(30.000, 100·C).

| Nhóm | Cấu hình | Yếu tố khảo sát |
|---|---:|---|
| E1 | 33 | Event Loop, Loom, Bun × 11 mức tải chung từ 200 đến 8.800 req/s. |
| E2 | 12 | Event Loop và Loom × C = 100, 1.500, 5.000 × 100 chỗ/core hoặc không giới hạn. |
| E3 | 27 | Ba hệ × D = 10, 50, 200 ms × s = 0,2; 1; 5 ms. Tải cố định 160 req/s. |
| E4 | 9 | c = 1, 4, 8 × K/core = 10, 100, ∞ ở tải tương đối 0,95. |
| E5 | 18 | Sáu mô hình trạm đơn × tải thấp, vừa, cao. |
| E6 | 8 | Giai thừa: tải tương đối 0,7/1,1 × K/core 10/100 × c 1/8. |

Tổng 107 cấu hình và 1.070 lượt. Bun cơ sở dùng κ = 1 để so tổ chức hàng đợi ở cùng năng lực CPU. Tệp dữ liệu, hình và phân tích mới nằm trong [phase1_design](../SPE-dev-backup/results/phase1_design). Các CSV ở cấp trên và `results/figures` là thực nghiệm mở rộng lịch sử của nhánh backup, với cách đo và cách đánh số khác; không gộp chúng vào 1.070 lượt.


<!-- /coderabbit-ai-generated:v1 -->