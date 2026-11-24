from dataclasses import dataclass
from typing import Optional

# Hằng số LP ID thống nhất cho toàn hệ thống
SRC_ID = 0
DISP_ID = 1
IO_ID = 2
SINK_ID = 3
WORKER_BASE_ID = 10


@dataclass
class SimConfig:
    """Tham số đầu vào cho một kịch bản mô phỏng DES."""
    gamma: float                        # Tốc độ đến tổng (req/s) - dùng cho open-loop
    c: int = 1                          # Số core / worker / carrier thread
    K: int = 100                        # Tổng sức chứa trạm CPU (đang chạy + hàng chờ)
    s: float = 1e-3                     # Thời gian phục vụ CPU trung bình (giây)
    D: float = 50e-3                    # Độ trễ I/O trung bình (giây), 0 = bỏ qua trạm I/O
    arch: str = "shared"                # "shared" (Event loop / Loom) | "partitioned" (Bun)
    kappa: float = 1.0                  # Hệ số chi phí CPU của kernel thread (Bun)
    dist_cpu: str = "exp"               # "exp" (mũ) | "det" (xác định)
    dist_io: str = "exp"                # "exp" (mũ) | "det" (xác định)
    n_req: int = 30_000                 # Tổng số request sinh ra
    warm_ratio: float = 0.10            # Tỉ lệ request khởi động tối thiểu
    closed_C: int = 0                   # 0 = open-loop; > 0 = số kết nối đồng thời (closed-loop)
    t_err: float = 1e-2                 # Thời gian chờ sau khi bị từ chối ở closed-loop (giây)
    think_time: float = 0.0             # Think time z ở closed-loop (giây)
    backend_limit: Optional[int] = None # None = M/M/inf; int = giới hạn kết nối backend (S8)
    heavy_prob: float = 0.0             # Xác suất gặp tác vụ CPU nặng (S10)
    heavy_mult: float = 20.0            # Hệ số nhân thời gian CPU của tác vụ nặng (S10)
    dispatcher_type: str = "sequential" # "sequential" | "distributed_sequential"
    seed: int = 1                       # Hạt giống ngẫu nhiên


@dataclass
class SimMetrics:
    """Chỉ số thu thập được từ một lần chạy mô phỏng đơn."""
    Pblock: float
    X: float
    R: float
    Wq: float
    W_cpu: float
    p95: float
    p99: float
    L_cpu: float
    L_io: float
    L_sys: float
    U: float
    events_processed: int
    wall_time: float
    n_done: int
    n_rejected: int
    n_arrived: int
    T_obs: float
    conservation_ok: bool
