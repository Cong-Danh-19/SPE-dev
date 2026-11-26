# Kiểm chứng và đánh giá hiệu năng

Bộ kiểm chứng đối chiếu sáu mô hình trạm đơn với nghiệm giải tích ở ba mức tải. Mỗi cấu hình dùng 15 hạt giống. Cả 18 cấu hình đạt tiêu chí về sai số của thông lượng, thời gian trung bình tại trạm, số yêu cầu tại trạm và xác suất từ chối. Trong E1–E3, 86 cấu hình phân biệt đều có sai lệch dưới 3% khi đối chiếu các hệ thức Little tại CPU, I/O và toàn hệ thống, cùng mức bận của CPU. [Bảng kiểm chứng 18 cấu hình](../SPE-dev-backup/results/figures/fig8_verification.md) · [Đối chiếu theo từng chỉ số](../SPE-dev-backup/results/figures/analysis_summary.md)

## Kết quả các thí nghiệm

| Thí nghiệm | Kết quả từ dữ liệu bàn giao |
|---|---|
| E1 · Tải tới hạn | Trên lưới tải đã chạy, mức đến cao nhất đồng thời đạt bốn ngưỡng vận hành là 800 yêu cầu/giây với Event loop, 8.000 với Loom, 7.000 với Bun κ = 1 và 6.000 với Bun κ = 1,25. Ở mức 8.000, độ trễ trung bình của Loom là 82,52 ms, so với nghiệm dừng 100,36 ms. [Dữ liệu E1](../SPE-dev-backup/results/e1_throughput_curves.csv) |
| E2 · Sức chứa bộ đệm | Ở tải 7.500 yêu cầu/giây với Bun, 8 worker, CPU mũ và κ = 1,25, tăng K từ 16 lên 800 giảm tỷ lệ từ chối từ 38,72% xuống 15,27%. Độ trễ trung bình của yêu cầu hoàn tất tăng từ 52,19 lên 169,26 ms. [Dữ liệu E2](../SPE-dev-backup/results/e2_capacity_delay.csv) |
| E3 · Hàng chung và hàng riêng | Với cùng 8 worker, K = 160, κ = 1 và tải 7.000 yêu cầu/giây, độ trễ trung bình là 51,95 ms ở hàng chung và 56,88 ms ở hàng riêng. Tỷ lệ từ chối quan sát được lần lượt là 0% và 0,909%. [Dữ liệu E3](../SPE-dev-backup/results/e3_loom_vs_bun_sensitivity.csv) |
| E4 · Tải hệ kín | Cả 30 cấu hình có sai lệch dưới 3% khi đối chiếu dân số kết nối với tổng thời gian phản hồi và chờ thử lại theo định luật Little. Sai lệch cao nhất là 0,646%. [Dữ liệu E4](../SPE-dev-backup/results/e4_closed_loop.csv) |
| E5 · Nghẽn I/O và tác vụ CPU nặng | Ở S8, hai mô hình đạt xấp xỉ 5.854 và 5.796 yêu cầu/giây dưới giới hạn 300 kết nối backend. Ở S10, với 5% tác vụ dùng CPU lâu gấp 20 lần, độ trễ trung bình của Event loop là 432,44 ms và của Loom là 52,15 ms. Hai cấu hình S10 khác nhau cả số worker và sức chứa CPU. [Dữ liệu E5](../SPE-dev-backup/results/e5_special_scenarios.csv) |

Bốn ngưỡng vận hành của E1 dùng trung bình đo qua 10 hạt giống ở mỗi điểm tải. Chúng yêu cầu tỷ lệ từ chối dưới 1%, độ trễ trung bình dưới 100 ms, p99 dưới 300 ms và thông lượng thành công đạt ít nhất 95% tốc độ đến. Các tên Event loop, Bun và Loom chỉ những kiến trúc hàng đợi được mô hình hóa trong bộ mô phỏng. [Bảy câu hỏi nghiên cứu và kết quả chi tiết](../SPE-dev-backup/docs/architecture.md) · [Thiết kế thực nghiệm](../A%20description%20of%20the%20experiments/README.md)

## Thông lượng hệ kín E4

Cả 30 cấu hình E4 đều đạt tiêu chí kiểm tra của TV3. Chương trình đánh dấu một cấu hình vượt trần khi thông lượng trung bình mẫu cao hơn 103% công suất danh định, hoặc khi cận dưới của khoảng tin cậy 95% cao hơn công suất danh định. Chương trình cũng kiểm tra hệ thức Little với ngưỡng sai lệch 3%. [Phép kiểm tra trong ứng dụng TV3](../SPE-dev-backup/apps/plotting_app.py)

Ở dòng `EventLoop_Kinf_C5000`, một worker có thời gian phục vụ trung bình 1 ms, tương ứng công suất dài hạn 1.000 yêu cầu/giây. Thông lượng trung bình qua 10 seed là **1.000,47 yêu cầu/giây**. Khoảng tin cậy 95% từ **999,25 đến 1.001,69 yêu cầu/giây** chứa mốc 1.000. Trung bình mẫu cao hơn mốc khoảng 0,047% và cấu hình đạt tiêu chí trên. [Dữ liệu E4](../SPE-dev-backup/results/e4_closed_loop.csv)

## Sai số và khoảng tin cậy ở sáu mô hình trạm đơn

Cả 18 trường hợp đạt tiêu chí sai số của bộ kiểm chứng. Xét riêng thời gian trung bình tại trạm (`W`), nghiệm giải tích nằm trong khoảng tin cậy ở 15/18 trường hợp. Ba trường hợp còn lại thuộc mô hình M/M/∞. Giá trị mô phỏng khoảng 50,15 ms, so với nghiệm 50,00 ms. Đây là các trường hợp có sai số tương đối nhỏ dù khoảng tin cậy của trung bình mẫu nằm phía trên nghiệm. [Bảng kiểm chứng và các cận CI95](../SPE-dev-backup/results/verification_summary.csv)

## Cách đọc tỷ lệ từ chối ở S8

Ở kịch bản giới hạn 300 kết nối I/O, tỷ lệ từ chối trung bình là **16,42%** ở mô hình hàng chung và **17,10%** ở mô hình hàng riêng với κ = 1,25. Bộ mô phỏng chọn các yêu cầu thành công theo thời điểm rời hệ thống và chọn các yêu cầu bị từ chối theo thời điểm đến. Một yêu cầu có thể tới trước biên cửa sổ đo nhưng bị từ chối tại backend sau biên đó. Vì bộ đếm gộp cả hai nơi từ chối, hai tỷ lệ trên mô tả toàn hệ thống CPU–I/O. [Dữ liệu S8](../SPE-dev-backup/results/e5_special_scenarios.csv) · [Cửa sổ đo](../SPE-dev-backup/apps/simulator_app.py) · [Xử lý yêu cầu bị từ chối](../SPE-dev-backup/scenarios/async_runtime_lps.py)
