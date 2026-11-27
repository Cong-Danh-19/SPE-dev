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
