# Kiến trúc Hệ thống Mô phỏng (Phase 2)

## 1. Sơ đồ khối các Logical Process (LP)
- `SourceLP` (`ID=0`) -> `SharedDispatcherLP` / `PartitionedDispatcherLP` (`ID=1`) -> `WorkerLP` (`ID=10..10+c-1`) -> `IoLP` (`ID=2`) -> `SinkLP` (`ID=3`).

## 2. Phân tích định lượng 7 câu hỏi nghiên cứu
*(Thành viên 3 điền bảng tổng hợp số liệu từ `results/*.csv` và giải thích tại đây)*
