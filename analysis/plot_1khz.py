"""Draw the June 1 kHz comparison from canonical_main_results_lower.csv."""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator


def draw(table, output):
    with table.open(newline="", encoding="utf-8-sig") as handle:
        rows = [row for row in csv.DictReader(handle) if float(row["rate_hz"]) == 1000]
    rows.sort(key=lambda row: (row["receiver"] != "raspberry_pi_os_receiver",
                               float(row["mean_us"])))
    counts = {int(row["successes"]) for row in rows}
    if len(counts) != 1 or len(rows) != 7:
        raise ValueError("Expected the seven June 1 kHz runs with equal sample sizes.")

    ink, muted, teal, violet = "#152838", "#536676", "#08786E", "#69479B"
    fig = plt.figure(figsize=(12.4, 6.5), facecolor="white")
    ax = fig.add_axes([0.36, 0.16, 0.405, 0.56])
    ax.set_xscale("log")
    ax.set_xlim(4.8, 1150)
    ax.set_ylim(6.55, -0.55)
    ticks = [5, 10, 30, 100, 300, 1000]
    ax.set_xticks(ticks, [f"{tick:,}" for tick in ticks], fontsize=12, color=muted)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.tick_params(axis="x", length=0, pad=8)
    ax.set_yticks([])
    ax.grid(axis="x", color="#DCE5EA", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.text(0.035, 0.915, "GPIO response latency at 1 kHz",
             fontsize=27, weight="bold", color=ink)
    fig.text(0.035, 0.852, f"{counts.pop():,} successful trials per receiver"
             "  ·  Software timing on the stimulus Raspberry Pi", fontsize=14, color=muted)
    fig.text(0.035, 0.752, "Receiver", fontsize=13, color=ink, weight="bold")
    fig.text(0.867, 0.752, "Mean (µs)", ha="right", fontsize=13, color=teal, weight="bold")
    fig.text(0.972, 0.752, "P99 (µs)", ha="right", fontsize=13, color=violet, weight="bold")

    for index, row in enumerate(rows):
        mean, p99 = float(row["mean_us"]), float(row["p99_us"])
        ax.hlines(index, mean, p99, color="#9AACB7", linewidth=2.5, zorder=2)
        ax.plot(mean, index, "o", color=teal, markersize=9, zorder=3)
        ax.plot(p99, index, "D", color=violet, markersize=7, zorder=3)
        y = fig.transFigure.inverted().transform(ax.transData.transform((mean, index)))[1]
        label = row["receiver_display"].replace("Raspberry Pi OS receiver", "Raspberry Pi OS (Python)")
        fig.text(0.035, y, label, color=ink, fontsize=13.5, va="center")
        fig.text(0.867, y, f"{mean:,.2f}", color=teal, fontsize=14, va="center", ha="right")
        fig.text(0.972, y, f"{p99:,.2f}", color=violet, fontsize=14, va="center", ha="right")

    ax.set_xlabel("Latency (µs, logarithmic scale)", labelpad=11, fontsize=12, color=muted)
    ax.plot([], [], "o", color=teal, label="Mean")
    ax.plot([], [], "D", color=violet, label="99th percentile")
    ax.legend(loc="lower left", bbox_to_anchor=(-0.04, 1.005), frameon=False,
              ncol=2, columnspacing=1, handletextpad=0.2, fontsize=12, labelcolor=ink)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    draw(args.table, args.output)
