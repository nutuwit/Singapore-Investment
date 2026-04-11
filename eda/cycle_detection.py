"""
Cycle Detection — semiconductor/export cycles using HP filter + peak/trough detection.
Run: python eda/cycle_detection.py
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import signal

os.makedirs("eda/charts", exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 120,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def run(panel: pd.DataFrame, col: str = "merchandise_exports"):
    if col not in panel.columns:
        print(f"[WARN] '{col}' not in panel.")
        return

    try:
        import statsmodels.api as sm
    except ImportError:
        print("[ERROR] Install statsmodels: pip install statsmodels")
        return

    yoy = panel[col].dropna().pct_change(12) * 100
    yoy = yoy.dropna()

    cycle, trend = sm.tsa.filters.hpfilter(yoy, lamb=14400)  # lambda=14400 for monthly

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle("Singapore: Export Cycle Detection (HP Filter)", fontweight="bold")

    ax1.plot(yoy.index, yoy, color="steelblue", linewidth=1.2, alpha=0.7,
             label="YoY Export Growth (%)")
    ax1.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax1.set_ylabel("YoY Growth (%)")
    ax1.legend(fontsize=8)

    ax2.plot(cycle.index, cycle, color="darkorange", linewidth=1.5)
    ax2.fill_between(cycle.index, cycle, 0,
                     where=(cycle >= 0), alpha=0.3, color="green", label="Expansion")
    ax2.fill_between(cycle.index, cycle, 0,
                     where=(cycle < 0),  alpha=0.3, color="red",   label="Contraction")
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_ylabel("Cyclical Component")

    peaks,   _ = signal.find_peaks( cycle.values, prominence=2)
    troughs, _ = signal.find_peaks(-cycle.values, prominence=2)

    ax2.scatter(cycle.index[peaks],   cycle.iloc[peaks],
                color="green", zorder=5, s=60, marker="^", label="Peak")
    ax2.scatter(cycle.index[troughs], cycle.iloc[troughs],
                color="red",   zorder=5, s=60, marker="v", label="Trough")
    ax2.legend(fontsize=8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    out = "eda/charts/cycle_detection.png"
    plt.savefig(out, bbox_inches="tight")
    print(f"[OK] Saved -> {out}")

    print("\nPEAKS:")
    for p in cycle.index[peaks]:
        print(f"  {p.strftime('%Y-%m')}  value={cycle[p]:.2f}")
    print("TROUGHS:")
    for t in cycle.index[troughs]:
        print(f"  {t.strftime('%Y-%m')}  value={cycle[t]:.2f}")

    plt.show()


if __name__ == "__main__":
    path = "data/processed/monthly_panel.csv"
    if not os.path.exists(path):
        print(f"[ERROR] Run pipeline first: {path} not found.")
    else:
        panel = pd.read_csv(path, parse_dates=["date"], index_col="date")
        run(panel)
