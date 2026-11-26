<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:983b3661968935c99ab98cb57ea270169acfadc2ea73c9958658e4070bf8cd01 -->

# Cài đặt và chạy

Cần Python ≥ 3.10, cài bằng `python -m pip install -r requirements.txt` trong môi trường ảo. Lõi BkitEvsim đã nằm trong repo.

```bash
make test-fast      # Các ca hồi quy cho lỗi trong hai phiếu
make run-exp-fast   # Ba ca nhỏ, kiểm tra CSV trong results-local/
make test           # Toàn bộ pytest, gồm kiểm chứng thống kê nhiều seed
make run-exp        # Verification và E1–E5 đầy đủ, ghi vào results/
make plot           # Vẽ biểu đồ thông lượng E1 từ results/
make pack           # Đóng gói mã nguồn và kết quả
```

Chạy riêng một phần hoặc chạy thử trên ít seed:

```bash
python -m apps.benchmark_experiments_app --only E5 --seeds 2 --out-dir results-local/e5
python -m apps.benchmark_experiments_app --only verification --out-dir results-local/h8
python -m apps.benchmark_experiments_app --only E6 --out-dir results-local/e6
python -m apps.benchmark_experiments_app --only E1-convergence --out-dir results-local/convergence
```

Các chế độ tùy chọn mặc định ghi vào `results-local/`. Mỗi lần thử chọn thư mục riêng để giữ `raw_seed_runs.csv` của lần trước. `--quick` dùng để thử luồng chương trình; mẫu này không dùng để nghiệm thu thống kê. Hai tùy chọn dispatcher trong cấu hình DES hiện cùng dùng `BkSysCoEventLoop` cho LP coroutine; phép thử ở đây kiểm tra tính nhất quán của tùy chọn.

Để chạy đầy đủ và dùng nhiều lõi CPU, chạy `python -m apps.benchmark_experiments_app --jobs 2`. Mỗi tiến trình có bộ nhớ riêng; bắt đầu với 2 tiến trình nếu máy ít RAM. `--jobs` giữ nguyên số request, số seed và thứ tự dòng xuất CSV.

<!-- /coderabbit-ai-generated:v1 -->
