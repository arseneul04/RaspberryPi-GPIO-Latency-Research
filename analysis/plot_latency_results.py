#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate GPIO latency statistics and figures for the report's selected runs.

Run from the repository root with python3 analysis/plot_latency_results.py.
Outputs are written to analysis/generated unless --output-dir is supplied.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


DISPLAY_NAMES = {
    "raspberry_pi_os_receiver": "Raspberry Pi OS Receiver",
    "baremetal_polling": "Bare-Metal Polling",
    "baremetal_direct_interrupt": "Bare-Metal Direct Interrupt",
    "baremetal_task_queue": "Bare-Metal Task Queue",
    "baremetal_scheduler": "Bare-Metal Scheduler",
    "baremetal_cyclic_executive": "Bare-Metal Cyclic Executive",
    "baremetal_task_queue_scheduler": "Bare-Metal Task Queue + Scheduler",
    "baremetal_multicore": "Bare-Metal Multicore",
}

BLUE = "#2F80ED"
DARK_BLUE = "#1F4E79"
DARK_TEXT = "#111827"
MUTED_TEXT = "#4B5563"
GRID_COLOR = "#D1D5DB"
BORDER_COLOR = "#9CA3AF"
LIGHT_FILL = "#EFF6FF"


LatencyKey = Tuple[str, str]
LatencyData = Dict[LatencyKey, List[float]]


def safe_name(value: object) -> str:
    """Return a simple filesystem-safe name."""
    text = str(value).strip().lower()
    text = text.replace(".", "p")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def display_name(receiver: str) -> str:
    """Convert receiver IDs into readable names."""
    return DISPLAY_NAMES.get(receiver, receiver.replace("_", " ").title())


def parse_rate_for_sort(rate_hz: str) -> float:
    """Sort numeric rates numerically, with unknown rates at the end."""
    try:
        return float(rate_hz)
    except (TypeError, ValueError):
        return math.inf


def format_rate(rate_hz: str) -> str:
    """Pretty print a rate value."""
    try:
        value = float(rate_hz)
    except (TypeError, ValueError):
        return str(rate_hz)

    if value.is_integer():
        return str(int(value))
    return ("%.3f" % value).rstrip("0").rstrip(".")


def format_number(value: float, decimals: int = 2) -> str:
    """Format a number cleanly for labels."""
    if not math.isfinite(value):
        return "n/a"
    if abs(value) >= 1000:
        return "%.0f" % value
    if abs(value) >= 100:
        return "%.1f" % value
    return ("%%.%df" % decimals) % value


def percentile(values: Sequence[float], percent: float) -> float:
    """Use the lower order statistic, as in the final report's P95 and P99."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[math.floor((len(ordered) - 1) * percent / 100)]


def mean_or_nan(values: Sequence[float]) -> float:
    return statistics.mean(values) if values else float("nan")


def median_or_nan(values: Sequence[float]) -> float:
    return statistics.median(values) if values else float("nan")


def stdev_or_zero(values: Sequence[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def load_latencies(raw_dir: Path, manifest_path: Path) -> LatencyData:
    """Use one report-selected file per receiver and rate, with only successful trials."""
    latencies: LatencyData = {}
    with manifest_path.open(newline="", encoding="utf-8") as manifest:
        for run in csv.DictReader(manifest):
            key = (run["receiver"], run["rate_hz"])
            if key in latencies:
                raise ValueError(f"Repeated receiver/rate in {manifest_path}: {key}")
            path = raw_dir / run["file"]
            samples = []
            recorded = 0
            with path.open(newline="", encoding="utf-8") as handle:
                # The interrupted OS run ends with a block of NUL padding.
                for row in csv.DictReader(line.rstrip("\0") for line in handle):
                    recorded += 1
                    if (row["receiver"], row["rate_hz"]) != key:
                        raise ValueError(f"Unexpected receiver or rate on row {recorded} of {path}")
                    if row["success"] == "1":
                        samples.append(int(row["latency_ns"]) / 1000)
            if recorded != int(run["recorded_trials"]) or len(samples) != int(run["successes"]):
                raise ValueError(f"Trial counts disagree with the run manifest for {path}")
            if not samples:
                raise ValueError(f"No successful trials in selected run {path}")
            latencies[key] = samples
    return latencies


def sorted_latency_items(latencies: LatencyData) -> List[Tuple[LatencyKey, List[float]]]:
    """Sort by rate first, then receiver name."""
    return sorted(
        latencies.items(),
        key=lambda item: (parse_rate_for_sort(item[0][1]), display_name(item[0][0]).lower()),
    )


def unique_rates(latencies: LatencyData) -> List[str]:
    return sorted({rate for _, rate in latencies.keys()}, key=parse_rate_for_sort)


def apply_plot_style(plt) -> None:
    """Apply a clean style without requiring extra packages."""
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("default")

    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": BORDER_COLOR,
            "axes.labelcolor": DARK_TEXT,
            "axes.titlecolor": DARK_TEXT,
            "axes.titlesize": 15,
            "axes.labelsize": 11,
            "xtick.color": MUTED_TEXT,
            "ytick.color": MUTED_TEXT,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 8,
            "grid.color": GRID_COLOR,
            "grid.linewidth": 0.7,
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
        }
    )


def save_figure(fig, out_path: Path, dpi: int, formats: Sequence[str]) -> None:
    """Save the same figure in one or more formats."""
    for file_format in formats:
        file_format = file_format.lower().lstrip(".")
        target = out_path.with_suffix("." + file_format)
        fig.savefig(target, dpi=dpi)
        print("Wrote %s" % target)


def add_legend_below(ax, columns: int = 2, y_offset: float = -0.20) -> None:
    """Place legends below charts so they do not cover plotted data."""
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, y_offset),
        ncol=max(1, columns),
        frameon=True,
        fancybox=True,
        framealpha=0.95,
        borderpad=0.8,
        columnspacing=1.2,
        handlelength=2.4,
    )


def clipped_limit(values: Sequence[float], clip_percentile: float) -> float:
    """Return the x-axis limit for clipping, with room on the right."""
    if not values:
        return 1.0

    maximum = max(values)
    if clip_percentile >= 100:
        limit = maximum
    else:
        limit = percentile(values, clip_percentile)

    if limit <= 0:
        return maximum if maximum > 0 else 1.0

    return limit * 1.05


def stats_text_for_values(values: Sequence[float], hidden_count: int = 0) -> str:
    """Build the text used in the stats box."""
    lines = [
        "Count: %d" % len(values),
        "Mean: %s microseconds" % format_number(mean_or_nan(values)),
        "Median: %s microseconds" % format_number(median_or_nan(values)),
        "95th percentile: %s microseconds" % format_number(percentile(values, 95)),
        "99th percentile: %s microseconds" % format_number(percentile(values, 99)),
        "Max: %s microseconds" % format_number(max(values) if values else float("nan")),
        "Std dev: %s microseconds" % format_number(stdev_or_zero(values)),
    ]

    if hidden_count > 0:
        lines.append("Outliers beyond axis: %d" % hidden_count)

    return "\n".join(lines)


def write_summary_stats(results_dir: Path, latencies: LatencyData) -> Path:
    """Write a clean summary CSV for reports."""
    out_path = results_dir / "latency_summary_stats.csv"
    fieldnames = [
        "receiver",
        "display_name",
        "rate_hz",
        "count",
        "mean_microseconds",
        "median_microseconds",
        "95th_percentile_microseconds",
        "99th_percentile_microseconds",
        "min_microseconds",
        "max_microseconds",
        "std_dev_microseconds",
    ]

    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for (receiver, rate_hz), values in sorted_latency_items(latencies):
            writer.writerow(
                {
                    "receiver": receiver,
                    "display_name": display_name(receiver),
                    "rate_hz": rate_hz,
                    "count": len(values),
                    "mean_microseconds": "%.6f" % mean_or_nan(values),
                    "median_microseconds": "%.6f" % median_or_nan(values),
                    "95th_percentile_microseconds": "%.6f" % percentile(values, 95),
                    "99th_percentile_microseconds": "%.6f" % percentile(values, 99),
                    "min_microseconds": "%.6f" % min(values),
                    "max_microseconds": "%.6f" % max(values),
                    "std_dev_microseconds": "%.6f" % stdev_or_zero(values),
                }
            )

    print("Wrote %s" % out_path)
    return out_path


def plot_histograms(plt, latencies: LatencyData, plot_dir: Path, args) -> None:
    """Create one histogram per receiver/rate pair."""
    for (receiver, rate_hz), values in sorted_latency_items(latencies):
        x_limit = clipped_limit(values, args.clip_x_percentile)
        visible_values = [value for value in values if value <= x_limit]
        hidden_count = len(values) - len(visible_values)

        if not visible_values:
            visible_values = list(values)
            hidden_count = 0

        fig, ax = plt.subplots(figsize=(12.5, 6.6))

        ax.hist(
            visible_values,
            bins=args.bins,
            color=BLUE,
            edgecolor=DARK_BLUE,
            linewidth=0.75,
            alpha=0.88,
        )

        ax.set_title(
            "Latency Histogram: %s at %s Hz" % (display_name(receiver), format_rate(rate_hz)),
            pad=14,
            fontweight="bold",
        )
        ax.set_xlabel("Latency (microseconds)")
        ax.set_ylabel("Count")
        ax.set_xlim(left=0, right=x_limit)
        ax.grid(True, axis="y", alpha=0.45)
        ax.grid(False, axis="x")

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

        stat_lines = stats_text_for_values(values, hidden_count=hidden_count)
        ax.text(
            1.02,
            0.98,
            stat_lines,
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=8.5,
            linespacing=1.35,
            bbox=dict(
                boxstyle="round,pad=0.50",
                facecolor="white",
                edgecolor=BORDER_COLOR,
                alpha=0.98,
            ),
        )

        median_value = median_or_nan(values)
        percentile_95 = percentile(values, 95)
        percentile_99 = percentile(values, 99)

        marker_specs = [
            (median_value, "Median"),
            (percentile_95, "95th percentile"),
            (percentile_99, "99th percentile"),
        ]

        y_top = ax.get_ylim()[1]
        for index, (marker_value, marker_label) in enumerate(marker_specs):
            if math.isfinite(marker_value) and marker_value <= x_limit:
                ax.axvline(marker_value, color=DARK_BLUE, linestyle="--", linewidth=1.2, alpha=0.75)
                ax.text(
                    marker_value,
                    y_top * (0.96 - index * 0.07),
                    marker_label,
                    rotation=90,
                    va="top",
                    ha="right",
                    fontsize=7.5,
                    color=DARK_BLUE,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.70, pad=1.0),
                )

        fig.tight_layout(rect=[0.0, 0.0, 0.76, 1.0])
        out_path = plot_dir / ("%s_%shz_histogram" % (safe_name(receiver), safe_name(format_rate(rate_hz))))
        save_figure(fig, out_path, args.dpi, args.formats)
        plt.close(fig)


def plot_combined_ecdf(plt, latencies: LatencyData, plot_dir: Path, args) -> None:
    """Plot all ECDF curves on one comparison chart."""
    all_values: List[float] = []
    for values in latencies.values():
        all_values.extend(values)

    x_limit = clipped_limit(all_values, args.ecdf_clip_x_percentile)

    fig, ax = plt.subplots(figsize=(13.5, 7.3))
    for (receiver, rate_hz), values in sorted_latency_items(latencies):
        ordered = sorted(values)
        y_values = [(index + 1) / float(len(ordered)) for index in range(len(ordered))]
        ax.plot(
            ordered,
            y_values,
            linewidth=1.9,
            alpha=0.95,
            label="%s (%s Hz)" % (display_name(receiver), format_rate(rate_hz)),
        )

    ax.set_title("Latency Distribution Comparison", pad=14, fontweight="bold")
    ax.set_xlabel("Latency (microseconds)")
    ax.set_ylabel("Cumulative probability")
    ax.set_ylim(0, 1.02)
    ax.set_xlim(left=0, right=x_limit)
    ax.grid(True, alpha=0.38)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    columns = 2 if len(latencies) <= 8 else 3
    add_legend_below(ax, columns=columns, y_offset=-0.20)
    fig.tight_layout(rect=[0.0, 0.14, 1.0, 1.0])

    out_path = plot_dir / "combined_latency_distribution"
    save_figure(fig, out_path, args.dpi, args.formats)
    plt.close(fig)


def plot_ecdf_by_rate(plt, latencies: LatencyData, plot_dir: Path, args) -> None:
    """Create one ECDF chart per rate."""
    for rate_hz in unique_rates(latencies):
        series = [
            (receiver, values)
            for (receiver, current_rate), values in sorted_latency_items(latencies)
            if current_rate == rate_hz
        ]

        if not series:
            continue

        all_values: List[float] = []
        for _, values in series:
            all_values.extend(values)
        x_limit = clipped_limit(all_values, args.ecdf_clip_x_percentile)

        fig, ax = plt.subplots(figsize=(13.0, 7.0))
        for receiver, values in series:
            ordered = sorted(values)
            y_values = [(index + 1) / float(len(ordered)) for index in range(len(ordered))]
            ax.plot(
                ordered,
                y_values,
                linewidth=2.2,
                alpha=0.95,
                label=display_name(receiver),
            )

        ax.set_title(
            "Latency Distribution Comparison at %s Hz" % format_rate(rate_hz),
            pad=14,
            fontweight="bold",
        )
        ax.set_xlabel("Latency (microseconds)")
        ax.set_ylabel("Cumulative probability")
        ax.set_ylim(0, 1.02)
        ax.set_xlim(left=0, right=x_limit)
        ax.grid(True, alpha=0.38)

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

        columns = 2 if len(series) <= 8 else 3
        add_legend_below(ax, columns=columns, y_offset=-0.20)
        fig.tight_layout(rect=[0.0, 0.14, 1.0, 1.0])

        out_path = plot_dir / ("combined_latency_distribution_%shz" % safe_name(format_rate(rate_hz)))
        save_figure(fig, out_path, args.dpi, args.formats)
        plt.close(fig)


def plot_boxplots_by_rate(plt, latencies: LatencyData, plot_dir: Path, args) -> None:
    """Create one boxplot per rate to compare spread and outliers."""
    for rate_hz in unique_rates(latencies):
        series = [
            (display_name(receiver), values)
            for (receiver, current_rate), values in sorted_latency_items(latencies)
            if current_rate == rate_hz
        ]

        if not series:
            continue

        labels = [name for name, _ in series]
        data = [values for _, values in series]

        fig_width = max(11.5, 1.0 * len(labels) + 5.5)
        fig, ax = plt.subplots(figsize=(fig_width, 7.0))

        boxplot_kwargs = dict(
            patch_artist=True,
            showmeans=True,
            meanline=True,
            widths=0.55,
            medianprops=dict(color=DARK_BLUE, linewidth=2.0),
            meanprops=dict(color=DARK_TEXT, linewidth=1.7, linestyle="--"),
            whiskerprops=dict(color=DARK_BLUE, linewidth=1.2),
            capprops=dict(color=DARK_BLUE, linewidth=1.2),
            flierprops=dict(
                marker="o",
                markersize=3,
                markerfacecolor=BLUE,
                markeredgecolor=DARK_BLUE,
                alpha=0.35,
            ),
        )

        try:
            box = ax.boxplot(data, tick_labels=labels, **boxplot_kwargs)
        except TypeError:
            # Older matplotlib versions use labels instead of tick_labels.
            box = ax.boxplot(data, labels=labels, **boxplot_kwargs)

        for patch in box["boxes"]:
            patch.set_facecolor(BLUE)
            patch.set_edgecolor(DARK_BLUE)
            patch.set_alpha(0.62)
            patch.set_linewidth(1.2)

        ax.set_title(
            "Latency Spread by System at %s Hz" % format_rate(rate_hz),
            pad=14,
            fontweight="bold",
        )
        ax.set_xlabel("Receiver")
        ax.set_ylabel("Latency (microseconds)")
        ax.grid(True, axis="y", alpha=0.42)
        ax.grid(False, axis="x")

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

        ax.tick_params(axis="x", rotation=28)
        for label in ax.get_xticklabels():
            label.set_horizontalalignment("right")

        fig.tight_layout()
        out_path = plot_dir / ("latency_boxplot_%shz" % safe_name(format_rate(rate_hz)))
        save_figure(fig, out_path, args.dpi, args.formats)
        plt.close(fig)


def plot_mean_bar_charts_by_rate(plt, latencies: LatencyData, plot_dir: Path, args) -> None:
    """Create one mean-latency bar chart per rate."""
    for rate_hz in unique_rates(latencies):
        series = [
            (display_name(receiver), values)
            for (receiver, current_rate), values in sorted_latency_items(latencies)
            if current_rate == rate_hz
        ]

        if not series:
            continue

        labels = [name for name, _ in series]
        means = [mean_or_nan(values) for _, values in series]

        fig_width = max(11.5, 0.95 * len(labels) + 5.0)
        fig, ax = plt.subplots(figsize=(fig_width, 6.7))
        bars = ax.bar(
            range(len(labels)),
            means,
            color=BLUE,
            edgecolor=DARK_BLUE,
            linewidth=0.8,
            alpha=0.88,
        )

        ax.set_title(
            "Mean Latency by System at %s Hz" % format_rate(rate_hz),
            pad=14,
            fontweight="bold",
        )
        ax.set_xlabel("Receiver")
        ax.set_ylabel("Latency (microseconds)")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=28, ha="right")
        ax.grid(True, axis="y", alpha=0.42)
        ax.grid(False, axis="x")

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

        y_top = max(means) if means else 1.0
        if y_top <= 0:
            y_top = 1.0
        ax.set_ylim(0, y_top * 1.18)

        for bar, value in zip(bars, means):
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                bar.get_height() + y_top * 0.025,
                format_number(value),
                ha="center",
                va="bottom",
                fontsize=8,
                color=DARK_TEXT,
            )

        fig.tight_layout()
        out_path = plot_dir / ("mean_latency_bar_chart_%shz" % safe_name(format_rate(rate_hz)))
        save_figure(fig, out_path, args.dpi, args.formats)
        plt.close(fig)


def plot_percentile_trends(plt, latencies: LatencyData, plot_dir: Path, args) -> None:
    """Plot median, 95th percentile, and 99th percentile versus send rate."""
    metrics = [
        ("median", "Median", lambda values: median_or_nan(values)),
        ("95th_percentile", "95th percentile", lambda values: percentile(values, 95)),
        ("99th_percentile", "99th percentile", lambda values: percentile(values, 99)),
    ]

    receivers = sorted({receiver for receiver, _ in latencies.keys()}, key=lambda item: display_name(item).lower())

    for metric_file_name, metric_label, metric_function in metrics:
        fig, ax = plt.subplots(figsize=(13.0, 7.0))
        plotted = False

        for receiver in receivers:
            points: List[Tuple[float, float]] = []
            for rate_hz in unique_rates(latencies):
                values = latencies.get((receiver, rate_hz))
                if not values:
                    continue
                rate_value = parse_rate_for_sort(rate_hz)
                if not math.isfinite(rate_value):
                    continue
                points.append((rate_value, metric_function(values)))

            if not points:
                continue

            points.sort(key=lambda item: item[0])
            x_values = [point[0] for point in points]
            y_values = [point[1] for point in points]

            ax.plot(
                x_values,
                y_values,
                marker="o",
                markersize=4.5,
                linewidth=2.0,
                alpha=0.95,
                label=display_name(receiver),
            )
            plotted = True

        if not plotted:
            plt.close(fig)
            continue

        ax.set_title("%s Latency by Rate" % metric_label, pad=14, fontweight="bold")
        ax.set_xlabel("Rate (Hz)")
        ax.set_ylabel("Latency (microseconds)")
        ax.grid(True, alpha=0.38)

        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

        columns = 2 if len(receivers) <= 8 else 3
        add_legend_below(ax, columns=columns, y_offset=-0.20)
        fig.tight_layout(rect=[0.0, 0.14, 1.0, 1.0])

        out_path = plot_dir / ("%s_latency_by_rate" % metric_file_name)
        save_figure(fig, out_path, args.dpi, args.formats)
        plt.close(fig)


def validate_formats(formats: Iterable[str]) -> List[str]:
    allowed = {"png", "pdf", "svg"}
    cleaned = []
    for item in formats:
        value = item.lower().lstrip(".")
        if value not in allowed:
            raise SystemExit("Unsupported format '%s'. Use one or more of: png, pdf, svg." % item)
        if value not in cleaned:
            cleaned.append(value)
    return cleaned or ["png"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create professional latency graphs from CSV results.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "analysis" / "generated",
        help="Directory for the statistics CSV and a plots subdirectory.",
    )
    parser.add_argument(
        "--bins",
        type=int,
        default=50,
        help="Number of bins for each histogram. Default: 50.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Image resolution for saved plots. Default: 300.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["png"],
        help="Output formats: png, pdf, svg. Default: png.",
    )
    parser.add_argument(
        "--clip-x-percentile",
        type=float,
        default=99.5,
        help="Histogram x-axis clipping percentile. Use 100 to show all values. Default: 99.5.",
    )
    parser.add_argument(
        "--ecdf-clip-x-percentile",
        type=float,
        default=99.5,
        help="Distribution plot x-axis clipping percentile. Use 100 to show all values. Default: 99.5.",
    )
    parser.add_argument(
        "--skip-boxplots",
        action="store_true",
        help="Do not generate boxplot charts.",
    )
    parser.add_argument(
        "--skip-bar-charts",
        action="store_true",
        help="Do not generate mean latency bar charts.",
    )
    args = parser.parse_args()

    if args.bins < 1:
        raise SystemExit("--bins must be at least 1.")
    if args.dpi < 72:
        raise SystemExit("--dpi should be at least 72.")
    if not (0 < args.clip_x_percentile <= 100):
        raise SystemExit("--clip-x-percentile must be greater than 0 and less than or equal to 100.")
    if not (0 < args.ecdf_clip_x_percentile <= 100):
        raise SystemExit("--ecdf-clip-x-percentile must be greater than 0 and less than or equal to 100.")

    args.formats = validate_formats(args.formats)
    return args


def main() -> None:
    args = parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise SystemExit(
            "matplotlib is required for plotting. Install it with: "
            "python3 -m pip install matplotlib"
        ) from error

    apply_plot_style(plt)

    latencies = load_latencies(
        REPO_ROOT / "data" / "raw_csv",
        REPO_ROOT / "analysis_tables" / "canonical_main_results_lower.csv",
    )
    if not latencies:
        raise SystemExit("The canonical run manifest contains no runs.")

    output_dir = args.output_dir.expanduser().resolve()
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    write_summary_stats(output_dir, latencies)
    plot_histograms(plt, latencies, plot_dir, args)
    plot_combined_ecdf(plt, latencies, plot_dir, args)
    plot_ecdf_by_rate(plt, latencies, plot_dir, args)

    if not args.skip_boxplots:
        plot_boxplots_by_rate(plt, latencies, plot_dir, args)

    if not args.skip_bar_charts:
        plot_mean_bar_charts_by_rate(plt, latencies, plot_dir, args)

    plot_percentile_trends(plt, latencies, plot_dir, args)

    print("Done. Plots are in: %s" % plot_dir)


if __name__ == "__main__":
    main()
