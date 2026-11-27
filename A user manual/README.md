<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:64bf996bff2c00e94013071ca48fb51b7c5b380427f29eef27cbfe5a0faa1308 -->

# Hướng dẫn chạy và đóng gói
Từ gốc repo, vào `SPE-dev-backup`. Dùng Python 3.11+ với môi trường ảo; môi trường kiểm thử bản này dùng Python 3.14.4. Trên Linux/macOS:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
make design-report
make pack GROUP=YY9B
```

Trên Windows, kích hoạt môi trường bằng `.venv\Scripts\Activate.ps1`. Nếu không có GNU Make, chạy `python -m apps.design_experiments_app --group E1` cho từng nhóm E1, E2, E3, E4, E5, E6, <!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:eb87a39e3f31d88c2ac85594f44b023150dc527d47f7841c1e777594c065657e -->

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:176234d6ac2826b690e5061824b5fc9f521f02abce9d2e352914d74efe27783f -->

sau đó chạy `python -m apps.verification_followup_app` (đo lại tất cả các cấu hình E5 còn chỉ số ngoài ngưỡng với 120.000 request/lượt và seed 101–110), `python -m apps.runtime_validation_app`, `python -m apps.design_report_app` và `python -m apps.package_submission --group YY9B`. Để dựng lại báo cáo từ các CSV có sẵn, dùng `make report`.

<!-- /coderabbit-ai-generated:v1 -->

<!-- /coderabbit-ai-generated:v1 -->

**Đọc kết quả:** mở `results/phase1_design/report.html` trong trình duyệt, xem CSV chi tiết trong cùng thư mục. Mỗi nhóm có dữ liệu từng seed, bảng trung bình/CI95 và manifest. Để dùng kết quả đi kèm chỉ cần mở báo cáo; không cần cài môi trường hay chạy lại. Để chạy mới trong môi trường khác, chuyển thư mục `results/phase1_design` cũ ra ngoài cây bàn giao trước khi chạy. Chỉ tiếp tục checkpoint khi mã, phiên bản Python và thư viện khớp. Chạy từng nhóm nối tiếp trên máy ít bộ nhớ.

**Nộp bài:** `Spe-Ass-final-YY9B.zip` được tạo ở gốc repo. Kiểm tra bằng `python -m zipfile -t ../Spe-Ass-final-YY9B.zip` từ thư mục mã nguồn. Gói gồm PDF Phase 1, năm mục tài liệu Phase 2 và mã nguồn kèm kết quả. Đánh giá chéo của nhóm khác thực hiện riêng ở Phase 3.


<!-- /coderabbit-ai-generated:v1 -->