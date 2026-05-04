"""
Latency benchmark for Sentinel.

Parses server stdout for [Metrics] lines and computes latency stats.
Run Sentinel with output piped to a log file, then run this script against it.

Usage:
    # Capture server output while running:
    python main.py 2>&1 | tee sentinel.log

    # After triggering N PRs, run:
    python scripts/benchmark.py sentinel.log
"""

import re
import sys
import statistics


def parse_latencies(log_path: str) -> list[float]:
    pattern = re.compile(r"latency_to_interrupt=(\d+\.\d+)s")
    latencies = []
    with open(log_path) as f:
        for line in f:
            m = pattern.search(line)
            if m:
                latencies.append(float(m.group(1)))
    return latencies


def print_stats(latencies: list[float]) -> None:
    if not latencies:
        print("No [Metrics] latency lines found in log.")
        return

    latencies_sorted = sorted(latencies)
    n = len(latencies)
    p50 = statistics.median(latencies_sorted)
    p95 = latencies_sorted[int(n * 0.95)] if n >= 2 else latencies_sorted[-1]
    p99 = latencies_sorted[int(n * 0.99)] if n >= 2 else latencies_sorted[-1]

    print(f"\nSentinel Latency Benchmark ({n} runs)")
    print(f"{'─' * 35}")
    print(f"  min     {min(latencies):.2f}s")
    print(f"  avg     {statistics.mean(latencies):.2f}s")
    print(f"  p50     {p50:.2f}s")
    print(f"  p95     {p95:.2f}s")
    print(f"  p99     {p99:.2f}s")
    print(f"  max     {max(latencies):.2f}s")
    if n > 1:
        print(f"  stddev  {statistics.stdev(latencies):.2f}s")
    print(f"{'─' * 35}")
    print(f"  raw:    {[f'{x:.2f}' for x in latencies_sorted]}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/benchmark.py <sentinel.log>")
        sys.exit(1)
    latencies = parse_latencies(sys.argv[1])
    print_stats(latencies)
