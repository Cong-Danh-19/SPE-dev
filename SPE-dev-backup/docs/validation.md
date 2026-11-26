# Ghi chú kiểm chứng và đánh giá kết quả Phase 2

Các số liệu dưới đây làm rõ cách đọc mục 4 của tài liệu kiến trúc và các bảng tổng hợp của TV3. [Kiến trúc và bảy câu hỏi nghiên cứu](architecture.md) · [Bảng phân tích thực nghiệm](../results/figures/analysis_summary.md)

## Thông lượng hệ kín E4

Cả 30 cấu hình E4 đều đạt tiêu chí kiểm tra của TV3. Chương trình đánh dấu một cấu hình vượt trần khi thông lượng trung bình mẫu cao hơn 103% công suất danh định, hoặc khi cận dưới của khoảng tin cậy 95% cao hơn công suất danh định. Chương trình cũng kiểm tra hệ thức Little với ngưỡng sai lệch 3%. [Phép kiểm tra trong ứng dụng TV3](../apps/plotting_app.py)

Ở dòng `EventLoop_Kinf_C5000`, một worker có thời gian phục vụ trung bình 1 ms, tương ứng công suất dài hạn 1.000 yêu cầu/giây. Thông lượng trung bình qua 10 seed là **1.000,47 yêu cầu/giây**. Khoảng tin cậy 95% từ **999,25 đến 1.001,69 yêu cầu/giây** chứa mốc 1.000. Trung bình mẫu cao hơn mốc khoảng 0,047% và cấu hình đạt tiêu chí trên. [Dữ liệu E4](../results/e4_closed_loop.csv)

## Sai số và khoảng tin cậy ở sáu mô hình trạm đơn

Cả 18 trường hợp đạt tiêu chí sai số của bộ kiểm chứng. Xét riêng thời gian trung bình tại trạm (`W`), nghiệm giải tích nằm trong khoảng tin cậy ở 15/18 trường hợp. Ba trường hợp còn lại thuộc mô hình M/M/∞. Giá trị mô phỏng khoảng 50,15 ms, so với nghiệm 50,00 ms. Đây là các trường hợp có sai số tương đối nhỏ dù khoảng tin cậy của trung bình mẫu nằm phía trên nghiệm. [Bảng kiểm chứng và các cận CI95](../results/verification_summary.csv)

## Cách đọc tỷ lệ từ chối ở S8

Ở kịch bản giới hạn 300 kết nối I/O, tỷ lệ từ chối trung bình là **16,42%** ở mô hình hàng chung và **17,10%** ở mô hình hàng riêng với κ = 1,25. Bộ mô phỏng chọn các yêu cầu thành công theo thời điểm rời hệ thống và chọn các yêu cầu bị từ chối theo thời điểm đến. Một yêu cầu có thể tới trước biên cửa sổ đo nhưng bị từ chối tại backend sau biên đó. Vì bộ đếm gộp cả hai nơi từ chối, hai tỷ lệ trên mô tả toàn hệ thống CPU–I/O. [Dữ liệu S8](../results/e5_special_scenarios.csv) · [Cửa sổ đo](../apps/simulator_app.py) · [Xử lý yêu cầu bị từ chối](../scenarios/async_runtime_lps.py)
