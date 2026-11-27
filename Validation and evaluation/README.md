<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:c47f72ee5d54752fb875df732da68fce216cd31d57141540cab6e9fb08acc1e3 -->

# Kiểm chứng và đánh giá
Mở [báo cáo Phase 2](../SPE-dev-backup/results/phase1_design/report.html) bằng trình duyệt. Mục E5 đối chiếu X, W, L và xác suất từ chối với nghiệm giải tích ở 18 cấu hình; mục mạng nối tiếp đối chiếu R, số request tại I/O và xác suất từ chối. Tệp [verification.csv](../SPE-dev-backup/results/phase1_design/verification.csv) và [tandem.csv](../SPE-dev-backup/results/phase1_design/tandem.csv) lưu cả những phép đối chiếu ngoài ngưỡng. E2 kiểm tra định luật Little trên kết nối đang xử lý và kết nối chờ thử lại.

Kiểm thử trong [tests](../SPE-dev-backup/tests) bao gồm thứ tự timestamp, bảo toàn request, khả năng tái lập, hành vi I/O không giữ worker và từ chối khi quá tải. Đây là verification. Validation ở đây dựa trên các xu hướng hiệu năng trong các kịch bản của nhóm: tải tăng, bộ đệm hữu hạn và I/O dài. <!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:3686ef4dccc2da165b0e91f613a8c3a3079055da1436f954d15e83c9efb6bbd0 -->

Ví dụ asyncio tại §1.4 của design được đo lại ba lần bằng đồng hồ thật: [dữ liệu đối chứng](../SPE-dev-backup/results/phase1_design/runtime_validation.csv). Đây là phép đo cơ chế chờ I/O, chưa phải benchmark của Node.js, Bun hoặc Spring Loom.

<!-- /coderabbit-ai-generated:v1 -->


<!-- /coderabbit-ai-generated:v1 -->