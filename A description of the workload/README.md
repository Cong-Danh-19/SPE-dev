<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:e62c4ae0d09928d4d7332059c0af3e5210a5cba1f2498469e4cca1d64f7855fe -->

# Workload và cửa sổ quan sát

Ở hệ mở, nguồn gửi request theo quá trình Poisson với tốc độ λ request/giây. Ở hệ kín, C client khởi phát đồng thời; sau khi thành công client gửi lại ngay, sau từ chối chờ 10 ms thời gian mô phỏng. Mỗi request được phục vụ CPU một lần, trả worker, rồi chờ I/O độc lập. Mô hình cơ sở dùng thời gian CPU và I/O phân phối mũ.

Event Loop có một worker. Loom có hàng FIFO chung cho tám worker. Bun chia ngẫu nhiên đều sang tám hàng FIFO riêng. K tính cả request chờ và đang phục vụ, K/core là sức chứa mỗi core; giá trị 10⁹ thay cho vô hạn trong các thí nghiệm hữu hạn này. Phân bố worker và hệ số κ là giả định mô hình. Chi tiết cấu hình: [Bảng 9–10 của nhóm](../The%20Phase%201%20submission/Spe-Ass-Spec-YY9B.pdf).

Mỗi lượt đo loại đúng 10% request đầu theo số thứ tự. Pblock dùng số request bị từ chối chia cho tổng số đến trong cùng nhóm sau warm-up, kể cả khi nhiều request có cùng timestamp. Pblock_cpu và Pblock_io phân biệt trạm từ chối. X và X_err đếm các lần hoàn tất hoặc từ chối **xảy ra trong cửa sổ thời gian đo**, chia cho độ dài cửa sổ (req/s). Số request ở biên vì vậy có thể khác số request trong nhóm dùng để tính Pblock.

R, p95, p99 là độ trễ đầu cuối của các request hoàn tất trong cửa sổ; W_cpu, Wq lần lượt là thời gian tại trạm CPU và thời gian chờ trước khi được cấp worker. Đơn vị là giây. L_cpu, L_io và U lấy trung bình theo thời gian từ trace trạng thái. Trong báo cáo, mỗi điểm là trung bình qua 10 seed; CI95 dùng phân phối t, 9 bậc tự do. Các ngưỡng SLO không phải điều kiện để một lượt mô phỏng hợp lệ: khi tải vượt công suất, tỷ lệ bị từ chối tăng là một kết quả cần giải thích.


<!-- /coderabbit-ai-generated:v1 -->