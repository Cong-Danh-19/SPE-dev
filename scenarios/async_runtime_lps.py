import random
from collections import deque
from typing import Optional
from bkitevsim.core import Event, BkSysLogicalProcessState
from bkitevsim.core.logical_coProcess import BkSysCoLogicalProcess
from .config import SRC_ID, DISP_ID, IO_ID, SINK_ID, WORKER_BASE_ID


class BaseSimLP(BkSysCoLogicalProcess):
    def __init__(self, lp_id: int, seed: int = 1, **kw):
        super().__init__(lp_id, BkSysLogicalProcessState(), lookahead=0.0)
        self.rng = random.Random(seed * 1009 + lp_id)

    def _send(self, now: float, dst: int, etype: str, payload: Optional[dict] = None, at: Optional[float] = None):
        self.send_event(Event(
            timestamp=now if at is None else at,
            sender_id=self.lp_id,
            receiver_id=dst,
            event_type=etype,
            payload=payload or {},
        ))

    async def coroutine_run(self):
        return


class SourceLP(BaseSimLP):
    def __init__(self, lp_id: int, seed: int = 1, gamma: float = 1.0,
                 n_req: int = 30_000, warm_reqs: int = 3000, closed_C: int = 0,
                 track_timeouts: bool = False, **kw):
        super().__init__(lp_id, seed)
        self.gamma = gamma
        self.n_req = n_req
        self.warm_reqs = warm_reqs
        self.closed_C = closed_C
        self.track_timeouts = track_timeouts
        self.sent = 0
        self.t_warm = 0.0
        self.t_last = 0.0

    async def coroutine_run(self):
        if self.closed_C > 0:
            for _ in range(self.closed_C):
                self._send(0.0, self.lp_id, "ARRIVAL", {}, at=0.0)
        else:
            self._send(0.0, self.lp_id, "ARRIVAL", {}, at=self.rng.expovariate(self.gamma))

    def handle_event(self, e: Event):
        t = e.timestamp
        if e.event_type in ("ARRIVAL", "NEXT"):
            if self.sent >= self.n_req:
                return
            self.sent += 1
            if self.sent == self.warm_reqs + 1:
                self.t_warm = t
            self.t_last = t
            if self.closed_C == 0 and e.event_type == "ARRIVAL" and self.sent < self.n_req:
                self._send(t, self.lp_id, "ARRIVAL", {}, at=t + self.rng.expovariate(self.gamma))
            payload = {"rid": self.sent, "t_arr": t}
            if self.track_timeouts:
                self._send(t, SINK_ID, "REQUEST_STARTED", payload)
            self._send(t, DISP_ID, "REQ", payload)


class SharedDispatcherLP(BaseSimLP):
    """Hàng chờ chung M/M/c/K (dùng cho Event loop c=1 và Spring Loom c=8)."""
    def __init__(self, lp_id: int, seed: int = 1, c: int = 1, K: int = 100, **kw):
        super().__init__(lp_id, seed)
        self.c = c
        self.K = K
        self.idle = list(range(c))
        self.Q = deque()
        self.n = 0
        self.trace = [(0.0, 0, 0)]

    def _log(self, t: float):
        self.trace.append((t, self.n, self.c - len(self.idle)))

    def handle_event(self, e: Event):
        t = e.timestamp
        if e.event_type == "REQ":
            if self.n >= self.K:
                self._send(t, SINK_ID, "REJECT", e.payload)
            else:
                self.n += 1
                if self.idle:
                    w = self.idle.pop()
                    payload = {**e.payload, "t_start": t}
                    self._send(t, WORKER_BASE_ID + w, "JOB", payload)
                else:
                    self.Q.append(e.payload)
                self._log(t)
        elif e.event_type == "IDLE":
            self.n -= 1
            w = e.payload["w"]
            if self.Q:
                nxt = self.Q.popleft()
                payload = {**nxt, "t_start": t}
                self._send(t, WORKER_BASE_ID + w, "JOB", payload)
            else:
                self.idle.append(w)
            self._log(t)


class PartitionedDispatcherLP(BaseSimLP):
    """Hàng chờ riêng từng kernel thread N x M/M/1/K (dùng cho Bun)."""
    def __init__(self, lp_id: int, seed: int = 1, c: int = 8, K: int = 800,
                 routing: str = "random", **kw):
        super().__init__(lp_id, seed)
        self.c = c
        self.k_per_worker = max(1, K // c)
        self.routing = routing
        self.busy = [False] * c
        self.queues = [deque() for _ in range(c)]
        self.counts = [0] * c
        self.rr_idx = 0
        self.trace = [(0.0, 0, 0)]

    @property
    def n(self) -> int:
        """Tổng số request đang xử lý + đang chờ trên tất cả các hàng đợi con."""
        return sum(self.counts)
    
    def _log(self, t: float):
        self.trace.append((t, sum(self.counts), sum(1 for b in self.busy if b)))

    def handle_event(self, e: Event):
        t = e.timestamp
        if e.event_type == "REQ":
            if self.routing == "rr":
                w = self.rr_idx
                self.rr_idx = (self.rr_idx + 1) % self.c
            else:
                w = self.rng.randrange(self.c)
            if self.counts[w] >= self.k_per_worker:
                self._send(t, SINK_ID, "REJECT", e.payload)
            else:
                self.counts[w] += 1
                if not self.busy[w]:
                    self.busy[w] = True
                    payload = {**e.payload, "t_start": t}
                    self._send(t, WORKER_BASE_ID + w, "JOB", payload)
                else:
                    self.queues[w].append(e.payload)
                self._log(t)
        elif e.event_type == "IDLE":
            w = e.payload["w"]
            self.counts[w] -= 1
            if self.queues[w]:
                nxt = self.queues[w].popleft()
                payload = {**nxt, "t_start": t}
                self._send(t, WORKER_BASE_ID + w, "JOB", payload)
            else:
                self.busy[w] = False
            self._log(t)


class WorkerLP(BaseSimLP):
    def __init__(self, lp_id: int, seed: int = 1, s: float = 1e-3, D: float = 50e-3,
                 dist_cpu: str = "exp", heavy_prob: float = 0.0, heavy_mult: float = 20.0, **kw):
        super().__init__(lp_id, seed)
        self.s = s
        self.D = D
        self.dist_cpu = dist_cpu
        self.heavy_prob = heavy_prob
        self.heavy_mult = heavy_mult

    def _sample_service(self) -> float:
        mean_s = self.s * (self.heavy_mult if (self.heavy_prob > 0 and self.rng.random() < self.heavy_prob) else 1.0)
        if self.dist_cpu == "det":
            return mean_s
        return self.rng.expovariate(1.0 / mean_s)

    def handle_event(self, e: Event):
        t = e.timestamp
        if e.event_type == "JOB":
            dur = self._sample_service()
            payload = {**e.payload, "t_cpu_end": t + dur}
            self._send(t, self.lp_id, "SERVED", payload, at=t + dur)
        elif e.event_type == "SERVED":
            if self.D > 0:
                self._send(t, IO_ID, "IO_REQ", e.payload)
            else:
                self._send(t, SINK_ID, "DONE", e.payload)
            self._send(t, DISP_ID, "IDLE", {"w": self.lp_id - WORKER_BASE_ID})


class IoLP(BaseSimLP):
    """Trạm chờ I/O M/M/inf (hoặc M/M/c/c khi cấu hình backend_limit cho S8)."""
    def __init__(self, lp_id: int, seed: int = 1, D: float = 50e-3,
                 dist_io: str = "exp", backend_limit: Optional[int] = None, **kw):
        super().__init__(lp_id, seed)
        self.D = D
        self.dist_io = dist_io
        self.backend_limit = backend_limit
        self.n = 0
        self.trace = [(0.0, 0)]

    def handle_event(self, e: Event):
        t = e.timestamp
        if e.event_type == "IO_REQ":
            if self.backend_limit is not None and self.n >= self.backend_limit:
                self._send(t, SINK_ID, "REJECT", e.payload)
                return
            self.n += 1
            self.trace.append((t, self.n))
            dur = self.D if self.dist_io == "det" else self.rng.expovariate(1.0 / self.D)
            self._send(t, self.lp_id, "IO_FIN", e.payload, at=t + dur)
        elif e.event_type == "IO_FIN":
            self.n -= 1
            self.trace.append((t, self.n))
            self._send(t, SINK_ID, "DONE", e.payload)


class SinkLP(BaseSimLP):
    def __init__(self, lp_id: int, seed: int = 1, closed: bool = False,
                 t_err: float = 1e-2, think_time: float = 0.0,
                 request_timeout: Optional[float] = None, **kw):
        super().__init__(lp_id, seed)
        self.closed = closed
        self.t_err = t_err
        self.think_time = think_time
        self.request_timeout = request_timeout
        self.pending = set()
        self.records = []
        self.rejected = []
        self.timed_out = []

    def handle_event(self, e: Event):
        t = e.timestamp
        p = e.payload
        if self.request_timeout is not None:
            rid = p["rid"]
            if e.event_type == "REQUEST_STARTED":
                self.pending.add(rid)
                self._send(t, self.lp_id, "TIMEOUT", p, at=t + self.request_timeout)
                return
            if e.event_type not in ("DONE", "REJECT", "TIMEOUT") or rid not in self.pending:
                return
            # The first terminal event wins. CPU and I/O release resources normally.
            self.pending.remove(rid)

        if e.event_type == "DONE":
            t_arr = p["t_arr"]
            t_start = p.get("t_start", t_arr)
            t_cpu_end = p.get("t_cpu_end", t)
            self.records.append((t_arr, t - t_arr, t_cpu_end - t_arr, t_start - t_arr))
            if self.closed:
                self._send(t, SRC_ID, "NEXT", {}, at=t + self.think_time)
        elif e.event_type in ("REJECT", "TIMEOUT"):
            outcomes = self.rejected if e.event_type == "REJECT" else self.timed_out
            outcomes.append(p["t_arr"])
            if self.closed:
                self._send(t, SRC_ID, "NEXT", {}, at=t + self.t_err)
