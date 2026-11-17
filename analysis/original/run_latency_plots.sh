#!/usr/bin/env bash
set -euo pipefail

# Run this script from inside your latency_results folder.
# It deletes old plots and regenerates clean 300 DPI graphs.

cd "$(dirname "$0")"
rm -rf plots
python3 plot_latency_results.py . --dpi 300 --formats png
