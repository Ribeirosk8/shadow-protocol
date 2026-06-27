#!/usr/bin/env python3
"""
SHADOW-Net — Microbenchmark Harness (Paper §V-A)
==================================================
Runs the SMPC matrix addition across all three SOC tiers with N iterations
each, collecting wall-clock CPU latency under Docker SWaP constraints.

Outputs a structured CSV + formatted table suitable for direct inclusion
in the paper's microbenchmark results.

Usage:
    python3 benchmark_harness.py --iterations 30 --rows 4 --cols 4
    python3 benchmark_harness.py --iterations 50 --rows 8 --cols 8
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import List

from mpyc.runtime import mpc


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
SOC_TIERS = [
    {"soc": 85,  "bits": 64, "tier": "HIGH-POWER",     "label": "SOC > 70%"},
    {"soc": 50,  "bits": 48, "tier": "MEDIUM-POWER",    "label": "30% < SOC ≤ 70%"},
    {"soc": 20,  "bits": 40, "tier": "CRITICAL-POWER",  "label": "SOC ≤ 30%"},
]

DEFAULT_ITERATIONS = 30
DEFAULT_ROWS = 4
DEFAULT_COLS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TierResult:
    soc: int
    bits: int
    tier: str
    label: str
    payload_bytes: int
    payload_reduction_pct: float
    latencies_us: List[float] = field(default_factory=list)

    @property
    def mean_us(self) -> float:
        return statistics.mean(self.latencies_us)

    @property
    def stdev_us(self) -> float:
        return statistics.stdev(self.latencies_us) if len(self.latencies_us) > 1 else 0.0

    @property
    def median_us(self) -> float:
        return statistics.median(self.latencies_us)

    @property
    def min_us(self) -> float:
        return min(self.latencies_us)

    @property
    def max_us(self) -> float:
        return max(self.latencies_us)

    @property
    def mean_ms(self) -> float:
        return self.mean_us / 1000.0

    @property
    def stdev_ms(self) -> float:
        return self.stdev_us / 1000.0

    @property
    def ci95_us(self) -> float:
        """95% confidence interval half-width (t ≈ 1.96 for large n)."""
        n = len(self.latencies_us)
        if n < 2:
            return 0.0
        return 1.96 * (self.stdev_us / math.sqrt(n))


# ─────────────────────────────────────────────────────────────────────────────
# Core SMPC Benchmark
# ─────────────────────────────────────────────────────────────────────────────
def generate_binary_matrix(rows: int, cols: int) -> List[List[int]]:
    return [[random.randint(0, 1) for _ in range(cols)] for _ in range(rows)]


async def run_single_iteration(
    sec_type, rows: int, cols: int
) -> float:
    """Execute one SMPC matrix addition and return latency in microseconds."""
    matrix_a = generate_binary_matrix(rows, cols)
    matrix_b = generate_binary_matrix(rows, cols)

    # Secret-share
    sec_a = [[sec_type(matrix_a[r][c]) for c in range(cols)] for r in range(rows)]
    sec_b = [[sec_type(matrix_b[r][c]) for c in range(cols)] for r in range(rows)]

    # ── Timed region: MPC addition + output ─────────────────────────────
    t0 = time.perf_counter_ns()

    sec_result = [
        [sec_a[r][c] + sec_b[r][c] for c in range(cols)]
        for r in range(rows)
    ]
    result_futures = [mpc.output(sec_result[r]) for r in range(rows)]
    for fut in result_futures:
        await fut

    t1 = time.perf_counter_ns()
    # ────────────────────────────────────────────────────────────────────

    return (t1 - t0) / 1_000.0  # ns → µs


async def run_benchmark(
    iterations: int, rows: int, cols: int
) -> List[TierResult]:
    """Run the full benchmark across all SOC tiers."""

    await mpc.start()

    results: List[TierResult] = []

    for tier_cfg in SOC_TIERS:
        bits = tier_cfg["bits"]
        sec_type = mpc.SecInt(bits)
        payload_bytes = (bits * rows * cols) // 8
        reduction = ((64 - bits) / 64) * 100.0

        tier_result = TierResult(
            soc=tier_cfg["soc"],
            bits=bits,
            tier=tier_cfg["tier"],
            label=tier_cfg["label"],
            payload_bytes=payload_bytes,
            payload_reduction_pct=reduction,
        )

        # Warmup (3 iterations, discarded)
        for _ in range(3):
            await run_single_iteration(sec_type, rows, cols)

        # Measured iterations
        for i in range(iterations):
            lat = await run_single_iteration(sec_type, rows, cols)
            tier_result.latencies_us.append(lat)

        results.append(tier_result)

    await mpc.shutdown()
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Output Formatters
# ─────────────────────────────────────────────────────────────────────────────
def print_paper_table(results: List[TierResult], iterations: int, rows: int, cols: int) -> None:
    """Print a formatted table suitable for LaTeX / paper inclusion."""
    print()
    print("=" * 95)
    print("  SHADOW-Net §V-A — Microbenchmark: Cryptographic CPU Latency")
    print(f"  Environment : Docker (cpus=0.50, mem=1g) — Raspberry Pi 4 Emulation")
    print(f"  Matrix Size : {rows}×{cols}  |  Iterations: {iterations}  |  Warmup: 3")
    print("=" * 95)
    print()

    # Header
    header = (
        f"{'SOC Tier':<20} {'Bits':>4} {'Payload':>8} {'Δ 64b':>7} "
        f"{'Mean (µs)':>11} {'± CI95':>10} {'σ (µs)':>9} "
        f"{'Med (µs)':>10} {'Min':>9} {'Max':>9} {'Mean (ms)':>10}"
    )
    print(header)
    print("─" * 95)

    for r in results:
        row = (
            f"{r.tier:<20} {r.bits:>4} {r.payload_bytes:>6} B {r.payload_reduction_pct:>5.1f}% "
            f"{r.mean_us:>11.1f} {r.ci95_us:>9.1f} {r.stdev_us:>9.1f} "
            f"{r.median_us:>10.1f} {r.min_us:>9.1f} {r.max_us:>9.1f} {r.mean_ms:>10.3f}"
        )
        print(row)

    print("─" * 95)
    print()

    # Speedup summary
    high = results[0]
    for r in results[1:]:
        speedup = ((high.mean_us - r.mean_us) / high.mean_us) * 100
        print(f"  {r.tier} vs HIGH-POWER: Δ latency = {speedup:+.1f}%")

    print()


def write_csv(results: List[TierResult], filepath: str, iterations: int, rows: int, cols: int) -> None:
    """Write raw latency data to CSV for external analysis."""
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "tier", "soc", "bits", "payload_bytes", "reduction_pct",
            "iteration", "latency_us", "latency_ms"
        ])
        for r in results:
            for i, lat in enumerate(r.latencies_us):
                writer.writerow([
                    r.tier, r.soc, r.bits, r.payload_bytes,
                    f"{r.payload_reduction_pct:.1f}",
                    i + 1, f"{lat:.2f}", f"{lat / 1000:.4f}"
                ])
    print(f"  📄 Raw data written to: {filepath}")


def write_json_summary(results: List[TierResult], filepath: str, iterations: int, rows: int, cols: int) -> None:
    """Write aggregated summary to JSON."""
    summary = {
        "benchmark": "SHADOW-Net §V-A Microbenchmark",
        "environment": "Docker (cpus=0.50, mem=1g) — RPi4 Emulation",
        "matrix_size": f"{rows}x{cols}",
        "iterations": iterations,
        "warmup": 3,
        "tiers": []
    }
    for r in results:
        summary["tiers"].append({
            "tier": r.tier,
            "label": r.label,
            "soc": r.soc,
            "bits": r.bits,
            "payload_bytes": r.payload_bytes,
            "payload_reduction_pct": round(r.payload_reduction_pct, 1),
            "mean_us": round(r.mean_us, 2),
            "stdev_us": round(r.stdev_us, 2),
            "ci95_us": round(r.ci95_us, 2),
            "median_us": round(r.median_us, 2),
            "min_us": round(r.min_us, 2),
            "max_us": round(r.max_us, 2),
            "mean_ms": round(r.mean_ms, 4),
        })

    with open(filepath, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  📊 Summary JSON written to: {filepath}")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="SHADOW-Net Microbenchmark Harness (Paper §V-A)"
    )
    parser.add_argument("--iterations", "-n", type=int, default=DEFAULT_ITERATIONS,
                        help=f"Measured iterations per tier (default: {DEFAULT_ITERATIONS})")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS,
                        help=f"Matrix rows (default: {DEFAULT_ROWS})")
    parser.add_argument("--cols", type=int, default=DEFAULT_COLS,
                        help=f"Matrix cols (default: {DEFAULT_COLS})")
    parser.add_argument("--csv", type=str, default="/app/results/benchmark_raw.csv",
                        help="Output CSV path")
    parser.add_argument("--json", type=str, default="/app/results/benchmark_summary.json",
                        help="Output JSON summary path")

    args, remaining = parser.parse_known_args()
    sys.argv = [sys.argv[0]] + remaining

    # Ensure output directory exists
    for path in [args.csv, args.json]:
        os.makedirs(os.path.dirname(path), exist_ok=True)

    results = mpc.run(run_benchmark(args.iterations, args.rows, args.cols))

    print_paper_table(results, args.iterations, args.rows, args.cols)
    write_csv(results, args.csv, args.iterations, args.rows, args.cols)
    write_json_summary(results, args.json, args.iterations, args.rows, args.cols)

    print()
    print("  ✅ Benchmark complete. Use the CSV for plots and the JSON for the paper table.")
    print()


if __name__ == "__main__":
    main()
