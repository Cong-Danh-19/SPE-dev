"""Repeat the qualitative asyncio demonstrations in Phase 1, section 1.4."""
import argparse
import asyncio
import csv
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


async def observe(delay):
    async def blocking():
        time.sleep(delay)

    start = time.perf_counter()
    for _ in range(3):
        await asyncio.sleep(delay)
    yield "sequential_io", 3 * delay, time.perf_counter() - start

    start = time.perf_counter()
    await asyncio.gather(*(asyncio.sleep(delay) for _ in range(3)))
    yield "concurrent_io", delay, time.perf_counter() - start

    start = time.perf_counter()
    await asyncio.gather(*(blocking() for _ in range(3)))
    yield "blocking_event_loop", 3 * delay, time.perf_counter() - start

    loop = asyncio.get_running_loop()
    for workers in (1, 3, 6):
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            await asyncio.gather(*(loop.run_in_executor(pool, time.sleep, delay) for _ in range(6)))
        yield f"thread_pool_{workers}", (6 // workers) * delay, time.perf_counter() - start


async def main(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["trial", "workload", "reference_seconds", "observed_seconds"])
        for trial in range(1, 4):
            async for workload, target, observed in observe(0.2):
                writer.writerow([trial, workload, target, observed])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/phase1_design/runtime_validation.csv"))
    asyncio.run(main(parser.parse_args().output))
