#!/usr/bin/env python3
"""
SHADOW-Net: Cryptographic Engine — SWaP-Aware Dynamic SMPC Matrix Addition
============================================================================
Paper:  "SHADOW-Net: Delay-Aware Dynamic SMPC and Opportunistic Caching
         in Privacy-Preserving FANETs"
Author: Amauri Ribeiro

Implements Section IV-A (SWaP-Aware Dynamic Field Scaling) and
Section V-A (Microbenchmark: Cryptographic CPU Latency).

A matrix cell only needs an 8-bit operand to account for up to 255
colliding drones; the remaining bits are security padding whose size
is governed by the UAV's State of Charge (SOC).

Usage (single-party mode):
    python shadow_smpc.py --soc 85          # High-Power   → 64-bit shares
    python shadow_smpc.py --soc 50          # Medium-Power → 48-bit shares
    python shadow_smpc.py --soc 20          # Critical     → 40-bit shares
    python shadow_smpc.py --soc 50 --rows 8 --cols 8   # custom matrix size

Multi-party (3 parties in separate terminals):
    python shadow_smpc.py --soc 85 -M3 -I0
    python shadow_smpc.py --soc 85 -M3 -I1
    python shadow_smpc.py --soc 85 -M3 -I2
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from typing import List

from mpyc.runtime import mpc


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_ROWS = 4          # Matrix rows  (flight-path grid Y)
DEFAULT_COLS = 4          # Matrix cols  (flight-path grid X)
SOC_HIGH_THRESHOLD = 70   # SOC > 70%  → 64-bit
SOC_MED_THRESHOLD = 30    # SOC > 30%  → 48-bit,  else → 40-bit

BIT_HIGH = 64             # High-Power   security padding
BIT_MED = 48              # Medium-Power security padding
BIT_LOW = 40              # Critical     security padding


# ─────────────────────────────────────────────────────────────────────────────
# SWaP-Aware Dynamic Field Scaling  (Paper §IV-A)
# ─────────────────────────────────────────────────────────────────────────────
def get_secure_int_type(soc: int):
    """Return the MPyC SecureInteger *class* whose bit-length matches
    the current State of Charge tier.

    A matrix cell only needs 8 useful bits (values 0-255).  The rest
    is cryptographic entropy / security padding that SHADOW-Net scales
    dynamically to conserve E_cpu and E_radio.

    Returns
    -------
    tuple[type, int, str]
        (SecInt class, bit_length, tier_label)
    """
    if soc > SOC_HIGH_THRESHOLD:
        bits = BIT_HIGH
        tier = "HIGH-POWER"
    elif soc > SOC_MED_THRESHOLD:
        bits = BIT_MED
        tier = "MEDIUM-POWER"
    else:
        bits = BIT_LOW
        tier = "CRITICAL-POWER"

    sec_type = mpc.SecInt(bits)
    return sec_type, bits, tier


# ─────────────────────────────────────────────────────────────────────────────
# Matrix Utilities
# ─────────────────────────────────────────────────────────────────────────────
def generate_binary_matrix(rows: int, cols: int) -> List[List[int]]:
    """Generate a 2D binary matrix representing a discretised drone
    flight-path occupancy grid (Paper §I, §III).
    1 = cell occupied by the drone's planned trajectory.
    0 = cell unoccupied.
    """
    return [[random.randint(0, 1) for _ in range(cols)] for _ in range(rows)]


def print_matrix(label: str, matrix: List[List[int]]) -> None:
    """Pretty-print a 2D matrix with a label."""
    print(f"\n{'─' * 40}")
    print(f"  {label}")
    print(f"{'─' * 40}")
    for row in matrix:
        print("  " + "  ".join(f"{v:>3}" for v in row))


# ─────────────────────────────────────────────────────────────────────────────
# SMPC Matrix Addition  (Paper §IV-A, §V-A)
# ─────────────────────────────────────────────────────────────────────────────
async def shadow_smpc_matrix_add(
    soc: int,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
) -> None:
    """Perform an SMPC matrix addition between two binary flight-path
    matrices using the dynamically-scaled SecInt type.

    This implements the microbenchmark described in §V-A:
      • Two 2D binary matrices are generated (one per drone).
      • Each element is secret-shared using the SOC-appropriate SecInt.
      • Element-wise addition is computed under MPC.
      • Results are revealed and wall-clock CPU latency is recorded.
    """
    # ── 1. Determine cryptographic tier ─────────────────────────────────
    sec_type, bit_len, tier = get_secure_int_type(soc)

    print("=" * 60)
    print("  SHADOW-Net  —  SWaP-Aware Dynamic SMPC Engine")
    print("=" * 60)
    print(f"  SOC             : {soc}%")
    print(f"  Power Tier      : {tier}")
    print(f"  SecInt Bit-Width: {bit_len}-bit")
    print(f"  Matrix Size     : {rows} × {cols}")
    print(f"  Payload Δ vs 64b: {((64 - bit_len) / 64) * 100:.1f}% reduction")
    print("=" * 60)

    # ── 2. Start MPyC runtime ───────────────────────────────────────────
    await mpc.start()

    # ── 3. Generate binary flight-path matrices ─────────────────────────
    # In a real deployment each drone holds ONE matrix; here we simulate
    # both locally (single-party mode / §V-A microbenchmark).
    matrix_a = generate_binary_matrix(rows, cols)
    matrix_b = generate_binary_matrix(rows, cols)

    print_matrix("Drone-Alpha  Flight-Path Matrix (A)", matrix_a)
    print_matrix("Drone-Bravo  Flight-Path Matrix (B)", matrix_b)

    # ── 4. Secret-share every element ───────────────────────────────────
    sec_a = [[sec_type(matrix_a[r][c]) for c in range(cols)] for r in range(rows)]
    sec_b = [[sec_type(matrix_b[r][c]) for c in range(cols)] for r in range(rows)]

    # ── 5. SMPC Matrix Addition (under MPC) ─────────────────────────────
    t_start = time.perf_counter_ns()

    sec_result = [
        [sec_a[r][c] + sec_b[r][c] for c in range(cols)]
        for r in range(rows)
    ]

    # ── 6. Reveal (reconstruct) the result ──────────────────────────────
    result_futures = [mpc.output(sec_result[r]) for r in range(rows)]
    result_rows = [await row_future for row_future in result_futures]

    t_end = time.perf_counter_ns()

    # Convert SecInt objects to plain ints for display
    result_matrix = [[int(cell) for cell in row] for row in result_rows]

    # ── 7. Telemetry ────────────────────────────────────────────────────
    latency_us = (t_end - t_start) / 1_000  # nanoseconds → microseconds
    latency_ms = latency_us / 1_000          # → milliseconds

    print_matrix("SMPC Result  (A + B)  —  Collision Map", result_matrix)

    # Identify collision cells (value ≥ 2)
    collisions = sum(
        1 for r in range(rows) for c in range(cols) if result_matrix[r][c] >= 2
    )

    print(f"\n{'─' * 40}")
    print(f"  TELEMETRY")
    print(f"{'─' * 40}")
    print(f"  Collision cells detected : {collisions} / {rows * cols}")
    print(f"  CPU Latency (MPC core)   : {latency_us:,.0f} µs  ({latency_ms:,.2f} ms)")
    print(f"  Bit-width used           : {bit_len}-bit SecInt")
    print(f"  Wireless payload / cell  : {bit_len} bits  ({bit_len // 8} bytes)")
    print(f"  Payload reduction vs 64b : {((64 - bit_len) / 64) * 100:.1f}%")
    if collisions > 0:
        print(f"  ⚠  EVASIVE MANEUVER REQUIRED — {collisions} conflict(s)")
    else:
        print(f"  ✓  Airspace CLEAR — no trajectory conflicts")
    print(f"{'─' * 40}\n")

    # ── 8. Shutdown ─────────────────────────────────────────────────────
    await mpc.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry-Point
# ─────────────────────────────────────────────────────────────────────────────
def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    NOTE: MPyC injects its own CLI flags (-M, -I, --ssl, etc.) which
    are consumed by ``mpc.run()``.  We parse only SHADOW-Net args from
    ``sys.argv`` and leave the rest for MPyC.
    """
    parser = argparse.ArgumentParser(
        description="SHADOW-Net: SWaP-Aware Dynamic SMPC Matrix Addition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "SOC Tiers (Section IV-A):\n"
            "  SOC > 70%%   → 64-bit SecInt  (High-Power)\n"
            "  30 < SOC ≤ 70%% → 48-bit SecInt  (Medium-Power)\n"
            "  SOC ≤ 30%%  → 40-bit SecInt  (Critical-Power)\n"
        ),
    )
    parser.add_argument(
        "--soc",
        type=int,
        default=100,
        help="State of Charge (0-100).  Drives dynamic key-scaling.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS,
        help=f"Matrix row count (default: {DEFAULT_ROWS}).",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=DEFAULT_COLS,
        help=f"Matrix column count (default: {DEFAULT_COLS}).",
    )
    return parser


def main() -> None:
    # Separate known SHADOW-Net args from MPyC-specific args
    parser = build_arg_parser()
    shadow_args, remaining = parser.parse_known_args()

    # Validate SOC range
    if not 0 <= shadow_args.soc <= 100:
        print(f"ERROR: --soc must be 0-100 (got {shadow_args.soc})", file=sys.stderr)
        sys.exit(1)

    # Restore remaining args for MPyC's internal parser
    sys.argv = [sys.argv[0]] + remaining

    # Execute the async SMPC computation
    mpc.run(
        shadow_smpc_matrix_add(
            soc=shadow_args.soc,
            rows=shadow_args.rows,
            cols=shadow_args.cols,
        )
    )


if __name__ == "__main__":
    main()
