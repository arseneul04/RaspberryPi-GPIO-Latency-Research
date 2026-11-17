# Reproduce the latency figures

With Python 3.10 or newer, run these commands from the repository root. A virtual environment is optional.

```bash
python3 -m pip install -r analysis/requirements.txt
python3 analysis/plot_latency_results.py
```

The command writes `analysis/generated/latency_summary_stats.csv` and 44 PNG files in `analysis/generated/plots/`. The CSV contains sample counts, mean, median, P95, P99, minimum, maximum and sample standard deviation in microseconds. The figures include a histogram for each of the 28 receiver/rate combinations and comparisons across receivers and rates. For full-range distribution plots, add `--clip-x-percentile 100 --ecdf-clip-x-percentile 100`. The default axes clip long tails to reveal the main distribution. All samples contribute to the statistics.

### Which runs are included?

The script reads the raw files named by the [final report’s run table](../analysis_tables/canonical_main_results_lower.csv). It includes 27,918 successful trials across 28 runs. At 1 Hz the Raspberry Pi OS receiver recorded 918 of 1,000 planned trials. The earlier [aggregate points file](../data/latency_points.csv) is headerless and omits this partial run. The two extra polling and cyclic-executive attempts and the five multicore attempts are in the [complete run inventory](../analysis_tables/all_uploaded_run_inventory.csv). The multicore attempts recorded zero successful responses, so they have no latency distribution.

The [original plotting scripts](original/) are preserved for reference. The plotting code and chart styles come from the internship’s `plot_latency_results.py`. The repository version selects runs from the report’s table, reads successful latencies in nanoseconds from each raw file, converts to microseconds, and writes to a separate output directory. It uses the report’s lower-order P95 and P99 estimator. For a sorted list of length `n`, percentile `p` selects the zero-based index `floor((n − 1) × p / 100)`. The median uses the average of the middle two observations when the count is even. The original plotting script used linear interpolation for percentiles, so freshly generated plots can differ from the [archived PNGs](../plots/).

For a different export format or destination, run `python3 analysis/plot_latency_results.py --help`. The Bash shortcut `bash analysis/run_latency_plots.sh` accepts the same arguments.

### Rebuild the README chart

The README’s 1 kHz chart reads the checked-in canonical table. From the repository root, run the following command after installing the dependencies above.

```bash
python3 analysis/plot_1khz.py analysis_tables/canonical_main_results_lower.csv docs/figures/latency-1khz.png
```
