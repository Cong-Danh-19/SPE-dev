import pytest

from bkitevsim.core import Event
from bkitevsim.queues import LadderQueue
from apps.simulator_app import run_simulation
from scenarios.config import SimConfig


def event(t):
    return Event(timestamp=t, sender_id=0, receiver_id=0, event_type="test")


def test_queue_orders_and_removes_across_bucket_wrap():
    queue = LadderQueue(bucket_width=1.0, num_buckets=4)
    for t in (8.5, 3.5, 4.5, 1.5):
        queue.push(event(t))
    assert queue.peek_timestamp() == 1.5
    assert sorted(e.timestamp for e in queue.pop_events_after(4.0)) == [4.5, 8.5]
    assert [queue.pop().timestamp, queue.pop().timestamp] == [1.5, 3.5]
    assert queue.is_empty()


def test_closed_loop_uses_same_arrival_cohort_for_blocking_probability():
    result = run_simulation(SimConfig(
        gamma=0, closed_C=500, c=1, K=20, s=0.001, D=0.05,
        n_req=5000, warm_ratio=0.1, seed=7,
    ))
    assert result.n_arrived == 4500
    assert 0 < result.Pblock <= 1
    assert result.Pblock == pytest.approx(result.n_rejected_cohort / result.n_arrived)
    assert result.Pblock == pytest.approx(result.Pblock_cpu + result.Pblock_io)
    assert result.conservation_ok


def test_backend_rejections_are_counted_by_station():
    result = run_simulation(SimConfig(
        gamma=500, c=8, K=100, s=0.001, D=0.05, backend_limit=2,
        n_req=3000, seed=12,
    ))
    assert result.n_rejected_io > 0
    assert result.n_rejected_cohort == result.n_rejected_cpu + result.n_rejected_io
    assert result.Pblock == pytest.approx(result.Pblock_cpu + result.Pblock_io)
    assert result.conservation_ok


def test_partitioned_capacity_must_not_exceed_total_capacity():
    with pytest.raises(ValueError):
        run_simulation(SimConfig(gamma=1, c=8, K=4, arch="partitioned"))


@pytest.mark.parametrize("arrival,expected", [(1001, "timeout"), (1000, "message"), (1, "message")])
def test_event_deadline_is_simulated_time(arrival, expected):
    import asyncio
    from bkitevsim.core.logical_coProcess import BkSysCoEventLoop

    async def scenario():
        scheduler = BkSysCoEventLoop(end_time=2000)
        waiter = asyncio.create_task(scheduler.wait_for_event(0, "test", timeout=1000))
        await asyncio.sleep(0)
        scheduler.schedule_event(event(arrival))
        assert scheduler._advance_time_to_next_event()
        scheduler._process_events_at_current_time()
        if expected == "timeout":
            with pytest.raises(TimeoutError):
                await waiter
            assert scheduler.current_time == 1000
        else:
            assert (await waiter).timestamp == arrival
        assert not scheduler._event_deadlines

    asyncio.run(scenario())


def test_multiwait_uses_virtual_deadline_and_consumes_each_event_once():
    from bkitevsim.core.logical_coProcess import BkSysCoEventLoop, BkSysCoLogicalProcess

    seen = []

    class Receiver(BkSysCoLogicalProcess):
        async def coroutine_run(self):
            for kind in ("a", "b"):
                self.send_event(Event(1000, 0, 0, kind))
            seen.append((await self.wait_for_multiple(["b", "a"], timeout=1000)).event_type)
            seen.append((await self.wait_for("b", timeout=0)).event_type)
            with pytest.raises(TimeoutError):
                await self.wait_for_multiple(["a", "b"], timeout=5000)
            seen.append(self._event_loop.current_time)

    loop = BkSysCoEventLoop(end_time=7000)
    lp = Receiver(0)
    lp.set_event_loop(loop)
    loop.register_lp(lp)
    loop.run()
    assert seen == ["a", "b", 6000]
    assert not lp._pending_events and not loop._event_deadlines
    assert not any(loop._event_waiters.values())


@pytest.mark.parametrize("arch", ["shared", "partitioned"])
def test_every_request_resolves_once_within_cpu_limits(monkeypatch, arch):
    from apps import simulator_app as sim
    from scenarios.async_runtime_lps import SinkLP

    resolved = []
    deliver = SinkLP.handle_event
    run = sim._run_in_thread
    cpu_trace = []

    def collect_outcomes(lp, event):
        resolved.append(event.payload["rid"])
        return deliver(lp, event)

    def collect_trace(simulation):
        stats = run(simulation)
        cpu_trace.extend(simulation.get_lp(sim.DISP_ID).trace)
        return stats

    monkeypatch.setattr(SinkLP, "handle_event", collect_outcomes)
    monkeypatch.setattr(sim, "_run_in_thread", collect_trace)
    cfg = SimConfig(gamma=0, arch=arch, c=4, K=8, closed_C=500, n_req=5000)
    metrics = run_simulation(cfg)
    assert metrics.Pblock > 0
    assert sorted(resolved) == list(range(1, cfg.n_req + 1))
    assert all(0 <= busy <= min(cfg.c, count) and count <= cfg.K for _, count, busy in cpu_trace)
    assert all(a[0] <= b[0] for a, b in zip(cpu_trace, cpu_trace[1:]))
