from dataclasses import dataclass
import math
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
    routing: str = "random"             # "random" (Poisson split) | "rr" (Round-Robin)
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

    @property
    def effective_K(self) -> int:
        return self.K // self.c * self.c if self.arch == "partitioned" else self.K

    def __post_init__(self):
        if self.arch not in {"shared", "partitioned"} or self.routing not in {"random", "rr"}:
            raise ValueError("Invalid CPU architecture or routing")
        if self.dist_cpu not in {"exp", "det"} or self.dist_io not in {"exp", "det"}:
            raise ValueError("Invalid service distribution")
        if self.dispatcher_type not in {"sequential", "distributed_sequential"}:
            raise ValueError("Invalid dispatcher option")
        if self.c < 1 or self.K < 1 or (self.arch == "partitioned" and self.K < self.c):
            raise ValueError("CPU capacity must be positive and Bun needs at least one slot per worker")
        if self.n_req < 1 or not 0 <= self.warm_ratio < 1 or self.closed_C < 0:
            raise ValueError("Invalid request count, warm-up ratio or closed-loop population")
        for name in ("gamma", "s", "D", "kappa", "t_err", "think_time", "heavy_prob", "heavy_mult"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if (self.closed_C == 0 and self.gamma == 0
                or self.s == 0 or self.kappa == 0 or self.heavy_mult == 0
                or self.heavy_prob > 1 or (self.backend_limit is not None and self.backend_limit < 0)):
            raise ValueError("Invalid arrival, service or backend parameters")


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
    X_err: float
    n_rejected_cpu: int
    n_rejected_io: int
    n_error_events: int
    n_sent: int
    warm_reqs: int
    t_warm: float
    p95_cpu: float
    p99_cpu: float
    W_io: float
