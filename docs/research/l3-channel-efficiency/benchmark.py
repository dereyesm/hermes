#!/usr/bin/env python3
"""
L3 Channel Efficiency — Serialization Benchmark
HERMES Research | ARC-5322 §14 compact vs verbose throughput

Measures serialize/deserialize throughput for both wire formats across
varying payload sizes. All measurements use the reference implementation.

Usage:
    python3 benchmark.py
    python3 benchmark.py --iterations 100000
"""

import argparse
import json
import time
from datetime import date

# Add reference implementation to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "reference" / "python"))

from hermes.message import (
    Message,
    create_message,
    parse_line,
    validate_compact,
    validate_message,
)


def bench_serialize(msg: Message, iterations: int) -> dict:
    """Benchmark verbose vs compact serialization."""
    # Verbose
    start = time.perf_counter_ns()
    for _ in range(iterations):
        msg.to_jsonl()
    verbose_ns = time.perf_counter_ns() - start

    # Compact
    start = time.perf_counter_ns()
    for _ in range(iterations):
        msg.to_compact_jsonl()
    compact_ns = time.perf_counter_ns() - start

    return {
        "verbose_ns": verbose_ns,
        "compact_ns": compact_ns,
        "verbose_per_msg_us": verbose_ns / iterations / 1000,
        "compact_per_msg_us": compact_ns / iterations / 1000,
        "speedup": verbose_ns / compact_ns if compact_ns > 0 else 0,
    }


def bench_deserialize(msg: Message, iterations: int) -> dict:
    """Benchmark verbose vs compact deserialization."""
    verbose_line = msg.to_jsonl()
    compact_line = msg.to_compact_jsonl()

    # Verbose
    start = time.perf_counter_ns()
    for _ in range(iterations):
        parse_line(verbose_line)
    verbose_ns = time.perf_counter_ns() - start

    # Compact
    start = time.perf_counter_ns()
    for _ in range(iterations):
        parse_line(compact_line)
    compact_ns = time.perf_counter_ns() - start

    return {
        "verbose_ns": verbose_ns,
        "compact_ns": compact_ns,
        "verbose_per_msg_us": verbose_ns / iterations / 1000,
        "compact_per_msg_us": compact_ns / iterations / 1000,
        "speedup": verbose_ns / compact_ns if compact_ns > 0 else 0,
    }


def bench_size(msg: Message) -> dict:
    """Measure wire size for both formats."""
    verbose = msg.to_jsonl()
    compact = msg.to_compact_jsonl()
    payload_len = len(msg.msg)
    return {
        "verbose_bytes": len(verbose),
        "compact_bytes": len(compact),
        "savings_bytes": len(verbose) - len(compact),
        "savings_pct": (len(verbose) - len(compact)) / len(verbose) * 100,
        "verbose_efficiency": payload_len / len(verbose) * 100,
        "compact_efficiency": payload_len / len(compact) * 100,
    }


def main():
    parser = argparse.ArgumentParser(
        description="HERMES Compact Wire Format — Serialization Benchmark",
    )
    parser.add_argument(
        "--iterations", "-n", type=int, default=50000,
        help="Number of iterations per benchmark (default: 50000)",
    )
    args = parser.parse_args()
    n = args.iterations
    w = 80

    print()
    print("=" * w)
    print("  HERMES COMPACT WIRE FORMAT — SERIALIZATION BENCHMARK")
    print(f"  Iterations: {n:,} per test")
    print("=" * w)

    payloads = [20, 60, 120]

    for payload_size in payloads:
        msg = create_message(
            src="momoshod", dst="nymyka", type="state",
            msg="x" * payload_size, ts=date(2026, 3, 15),
        )

        size = bench_size(msg)
        ser = bench_serialize(msg, n)
        deser = bench_deserialize(msg, n)

        print()
        print(f"  --- Payload: {payload_size} bytes ---")
        print()
        print(f"  Wire size:")
        print(f"    Verbose: {size['verbose_bytes']} B  "
              f"(efficiency: {size['verbose_efficiency']:.1f}%)")
        print(f"    Compact: {size['compact_bytes']} B  "
              f"(efficiency: {size['compact_efficiency']:.1f}%)")
        print(f"    Savings: {size['savings_bytes']} B  "
              f"({size['savings_pct']:.1f}%)")
        print()
        print(f"  Serialize ({n:,} iterations):")
        print(f"    Verbose: {ser['verbose_per_msg_us']:.2f} us/msg")
        print(f"    Compact: {ser['compact_per_msg_us']:.2f} us/msg")
        print(f"    Speedup: {ser['speedup']:.2f}x")
        print()
        print(f"  Deserialize ({n:,} iterations):")
        print(f"    Verbose: {deser['verbose_per_msg_us']:.2f} us/msg")
        print(f"    Compact: {deser['compact_per_msg_us']:.2f} us/msg")
        print(f"    Speedup: {deser['speedup']:.2f}x")

    # Throughput at 120B
    msg120 = create_message(
        src="momoshod", dst="nymyka", type="state",
        msg="x" * 120, ts=date(2026, 3, 15),
    )
    ser120 = bench_serialize(msg120, n)

    print()
    print("=" * w)
    print("  THROUGHPUT SUMMARY (120B payload)")
    print("=" * w)
    v_throughput = 1_000_000 / ser120["verbose_per_msg_us"]
    c_throughput = 1_000_000 / ser120["compact_per_msg_us"]
    print(f"  Verbose:  {v_throughput:,.0f} msg/sec serialize")
    print(f"  Compact:  {c_throughput:,.0f} msg/sec serialize")
    print()
    print("  Note: Both formats are negligible vs LLM inference (seconds).")
    print("  The value of compact is wire efficiency, not CPU speed.")
    print()


if __name__ == "__main__":
    main()
