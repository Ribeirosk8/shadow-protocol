#!/usr/bin/env python3
"""
SHADOW-Net — Publication-Quality Figure Generator
===================================================
Generates charts from benchmark JSON results for the paper §V-A / §V-B.

Outputs:
  figures/fig1_cpu_latency_comparison.png
  figures/fig2_payload_reduction.png
  figures/fig3_latency_scaling.png
"""

import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless rendering
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ─────────────────────────────────────────────────────────────────────────────
# Style Configuration — Dark, premium aesthetic
# ─────────────────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor": "#0d1117",
    "axes.facecolor": "#161b22",
    "axes.edgecolor": "#30363d",
    "axes.labelcolor": "#e6edf3",
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "xtick.color": "#8b949e",
    "ytick.color": "#8b949e",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "text.color": "#e6edf3",
    "legend.facecolor": "#161b22",
    "legend.edgecolor": "#30363d",
    "legend.fontsize": 10,
    "legend.labelcolor": "#e6edf3",
    "grid.color": "#21262d",
    "grid.alpha": 0.6,
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.facecolor": "#0d1117",
    "savefig.pad_inches": 0.3,
})

# Tier colors — curated palette
COLORS = {
    "HIGH-POWER":     "#58a6ff",   # Blue
    "MEDIUM-POWER":   "#f0883e",   # Orange
    "CRITICAL-POWER": "#f85149",   # Red
}

TIER_LABELS = {
    "HIGH-POWER":     "High-Power\n(64-bit, SOC > 70%)",
    "MEDIUM-POWER":   "Medium-Power\n(48-bit, 30% < SOC ≤ 70%)",
    "CRITICAL-POWER": "Critical-Power\n(40-bit, SOC ≤ 30%)",
}

TIER_SHORT = {
    "HIGH-POWER":     "64-bit",
    "MEDIUM-POWER":   "48-bit",
    "CRITICAL-POWER": "40-bit",
}

OUT_DIR = "figures"
RESULTS_DIR = "results"


# ─────────────────────────────────────────────────────────────────────────────
# Data Loading
# ─────────────────────────────────────────────────────────────────────────────
def load_json(filename: str) -> dict:
    path = os.path.join(RESULTS_DIR, filename)
    with open(path) as f:
        return json.load(f)


def load_all():
    """Load all benchmark results and return sorted by matrix size."""
    files = [
        ("4×4",   "benchmark_summary.json"),
        ("8×8",   "benchmark_8x8.json"),
        ("16×16", "benchmark_16x16.json"),
        ("32×32", "benchmark_32x32.json"),
    ]
    data = []
    for label, fname in files:
        d = load_json(fname)
        d["label"] = label
        cells = int(label.split("×")[0]) ** 2
        d["cells"] = cells
        data.append(d)
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: CPU Latency Comparison (Grouped Bar Chart)
# ─────────────────────────────────────────────────────────────────────────────
def fig1_cpu_latency(all_data):
    """Grouped bar chart: median CPU latency per tier across matrix sizes."""
    fig, ax = plt.subplots(figsize=(12, 6))

    matrix_labels = [d["label"] for d in all_data]
    tier_names = ["HIGH-POWER", "MEDIUM-POWER", "CRITICAL-POWER"]
    n_groups = len(matrix_labels)
    n_bars = len(tier_names)
    bar_width = 0.22
    x = np.arange(n_groups)

    for i, tier in enumerate(tier_names):
        medians = []
        ci95s = []
        for d in all_data:
            t = next(t for t in d["tiers"] if t["tier"] == tier)
            medians.append(t["median_us"])
            ci95s.append(t["ci95_us"])

        offset = (i - 1) * bar_width
        bars = ax.bar(
            x + offset, medians, bar_width,
            label=TIER_SHORT[tier],
            color=COLORS[tier],
            edgecolor="#0d1117",
            linewidth=0.8,
            yerr=ci95s,
            capsize=4,
            error_kw={"elinewidth": 1.2, "capthick": 1.2, "color": "#8b949e"},
            zorder=3,
        )
        # Value labels on bars
        for bar, val in zip(bars, medians):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(ci95s) * 0.3,
                f"{val:.0f}",
                ha="center", va="bottom",
                fontsize=8, color="#8b949e", fontweight="bold",
            )

    ax.set_xlabel("Matrix Size (Discretized Flight-Path Grid)", fontweight="bold")
    ax.set_ylabel("Median CPU Latency (µs)", fontweight="bold")
    ax.set_title(
        "SHADOW-Net §V-A — SMPC Matrix Addition: CPU Latency by SOC Tier",
        fontsize=15, fontweight="bold", pad=15,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(matrix_labels, fontsize=12)
    ax.legend(title="SecInt Bit-Width", title_fontsize=11, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    # Annotation
    ax.annotate(
        "Near-identical latencies across tiers\n--> step-down is a pure E_radio gain",
        xy=(0, medians[0] if len(medians) > 0 else 0),
        xytext=(1.5, max(t["median_us"] for t in all_data[-1]["tiers"]) * 0.55),
        fontsize=9, color="#7ee787", fontstyle="italic",
        arrowprops=dict(arrowstyle="->", color="#7ee787", lw=1.2),
        bbox=dict(boxstyle="round,pad=0.4", fc="#161b22", ec="#7ee787", alpha=0.9),
    )

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "fig1_cpu_latency_comparison.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✅ {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: Wireless Payload Reduction (Stacked Visualization)
# ─────────────────────────────────────────────────────────────────────────────
def fig2_payload_reduction(all_data):
    """Horizontal bar chart showing payload bytes per tier for each matrix."""
    fig, ax = plt.subplots(figsize=(12, 5))

    tier_names = ["CRITICAL-POWER", "MEDIUM-POWER", "HIGH-POWER"]
    matrix_labels = [d["label"] for d in all_data]
    y = np.arange(len(matrix_labels))
    bar_height = 0.22

    for i, tier in enumerate(tier_names):
        payloads = []
        for d in all_data:
            t = next(t for t in d["tiers"] if t["tier"] == tier)
            payloads.append(t["payload_bytes"])

        offset = (i - 1) * bar_height
        bars = ax.barh(
            y + offset, payloads, bar_height,
            label=f"{TIER_SHORT[tier]} ({tier.replace('-', ' ').title()})",
            color=COLORS[tier],
            edgecolor="#0d1117",
            linewidth=0.8,
            zorder=3,
        )
        for bar, val in zip(bars, payloads):
            ax.text(
                bar.get_width() + 50,
                bar.get_y() + bar.get_height() / 2,
                f"{val:,} B",
                ha="left", va="center",
                fontsize=9, color=COLORS[tier], fontweight="bold",
            )

    ax.set_yticks(y)
    ax.set_yticklabels(matrix_labels, fontsize=12)
    ax.set_xlabel("SMPC Payload Size (Bytes)", fontweight="bold")
    ax.set_title(
        "SHADOW-Net §V-B — Wireless Payload Reduction per SMPC Round",
        fontsize=15, fontweight="bold", pad=15,
    )
    ax.legend(title="SecInt Bit-Width", title_fontsize=11, loc="lower right")
    ax.grid(axis="x", linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    # 37.5% annotation
    high_32 = next(t for t in all_data[-1]["tiers"] if t["tier"] == "HIGH-POWER")["payload_bytes"]
    crit_32 = next(t for t in all_data[-1]["tiers"] if t["tier"] == "CRITICAL-POWER")["payload_bytes"]
    mid_x = (high_32 + crit_32) / 2
    ax.annotate(
        "37.5% reduction\n(8,192 --> 5,120 B)",
        xy=(crit_32, y[-1] - bar_height),
        xytext=(mid_x + 1500, y[-1] - bar_height - 1.0),
        fontsize=10, color="#f85149", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#f85149", lw=1.5),
        bbox=dict(boxstyle="round,pad=0.4", fc="#161b22", ec="#f85149", alpha=0.9),
    )

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "fig2_payload_reduction.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✅ {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3: Latency Scaling Trend (Line Chart)
# ─────────────────────────────────────────────────────────────────────────────
def fig3_latency_scaling(all_data):
    """Line chart showing how latency scales with matrix size per tier."""
    fig, ax = plt.subplots(figsize=(10, 6))

    tier_names = ["HIGH-POWER", "MEDIUM-POWER", "CRITICAL-POWER"]
    cells_list = [d["cells"] for d in all_data]

    for tier in tier_names:
        medians = []
        for d in all_data:
            t = next(t for t in d["tiers"] if t["tier"] == tier)
            medians.append(t["median_us"])

        ax.plot(
            cells_list, medians,
            marker="o", markersize=8,
            linewidth=2.5,
            color=COLORS[tier],
            label=TIER_SHORT[tier],
            zorder=3,
        )
        # Point labels
        for cx, val in zip(cells_list, medians):
            ax.annotate(
                f"{val:,.0f} µs",
                (cx, val),
                textcoords="offset points",
                xytext=(0, 14),
                ha="center", fontsize=8, color=COLORS[tier],
                fontweight="bold",
            )

    ax.set_xlabel("Matrix Cells (N × N)", fontweight="bold")
    ax.set_ylabel("Median CPU Latency (µs)", fontweight="bold")
    ax.set_title(
        "SHADOW-Net — CPU Latency Scaling with Grid Resolution",
        fontsize=15, fontweight="bold", pad=15,
    )
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=10)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f"{y:,.0f}"))
    ax.legend(title="SecInt Bit-Width", title_fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "fig3_latency_scaling.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✅ {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("\n  SHADOW-Net — Generating Publication Figures\n")

    all_data = load_all()

    fig1_cpu_latency(all_data)
    fig2_payload_reduction(all_data)
    fig3_latency_scaling(all_data)

    print(f"\n  📊 All figures saved to ./{OUT_DIR}/\n")


if __name__ == "__main__":
    main()
