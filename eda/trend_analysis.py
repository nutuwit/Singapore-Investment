"""
Trend Analysis — long-run trends for GDP, exports, IPI, CPI.
Run: python eda/trend_analysis.py
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

os.makedirs("eda/charts", exist_ok=True)

RECESSION_PERIODS = [
    ("2001-01", "2001-12"),
    ("2008-09", "2009-06"),
    ("2020-01", "2020-06"),
]

plt.rcParams.update({
    "figure.dpi": 120,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "sans-serif",
})


def shade_recessions(ax):
    for start, end in RECESSION_PERIODS:
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end),
                   alpha=0.12, color="red", label="_nolegend_")


def run(panel: pd.DataFrame):
    series_config = [
        ("industrial_production", "Industrial Production Index", "steelblue"),
        ("merchandise_exports",   "Merchandise Exports (SGD mn)",  "darkorange"),
        ("cpi",                   "CPI (2019=100)",                "forestgreen"),
    ]

    available = [(col, label, color)
                 for col, label, color in series_config
                 if col in panel.columns]

    if not available:
        print("[WARN] No series available in panel for trend analysis.")
        return

    fig, axes = plt.subplots(len(available), 1,
                             figsize=(14, 4 * len(available)), sharex=True)
    if len(available) == 1:
        axes = [axes]

    fig.suptitle("Singapore: Long-Run Economic Trends", fontsize=13, fontweight="bold")

    for ax, (col, label, color) in zip(axes, available):
        ax.plot(panel.index, panel[col], color=color, alpha=0.45,
                linewidth=1.0, label="Monthly")
        ma = panel[col].rolling(12, min_periods=6).mean()
        ax.plot(panel.index, ma, color=color, linewidth=2.0, label="12M MA")
        shade_recessions(ax)
        ax.set_ylabel(label, fontsize=9)
        ax.legend(fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    axes[-1].set_xlabel("Date")
    plt.tight_layout()
    out = "eda/charts/trend_analysis.png"
    plt.savefig(out, bbox_inches="tight")
    print(f"[OK] Saved -> {out}")
    plt.show()


if __name__ == "__main__":
    path = "data/processed/monthly_panel.csv"
    if not os.path.exists(path):
        print(f"[ERROR] Run pipeline first: {path} not found.")
    else:
        panel = pd.read_csv(path, parse_dates=["date"], index_col="date")
        run(panel)
