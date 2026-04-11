"""
Volatility Analysis — rolling 12M std dev of YoY growth rates.
Run: python eda/volatility_analysis.py
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
})


def shade_recessions(ax):
    for start, end in RECESSION_PERIODS:
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end),
                   alpha=0.12, color="red", label="_nolegend_")


def run(panel: pd.DataFrame):
    target_cols = ["industrial_production", "merchandise_exports", "cpi"]
    available   = [c for c in target_cols if c in panel.columns]

    if not available:
        print("[WARN] No series available for volatility analysis.")
        return

    fig, axes = plt.subplots(len(available), 1,
                             figsize=(14, 4 * len(available)), sharex=True)
    if len(available) == 1:
        axes = [axes]

    fig.suptitle("Singapore: Rolling 12M Volatility (YoY Growth Std Dev)", fontweight="bold")

    for ax, col in zip(axes, available):
        yoy = panel[col].pct_change(12) * 100
        vol = yoy.rolling(12, min_periods=6).std()

        ax.fill_between(vol.index, vol, alpha=0.35, color="steelblue")
        ax.plot(vol.index, vol, color="navy", linewidth=1.2)
        shade_recessions(ax)
        ax.set_ylabel(f"{col}\n(std dev %)", fontsize=9)

        # Annotate peak volatility
        if not vol.dropna().empty:
            peak_date = vol.idxmax()
            peak_val  = vol.max()
            ax.annotate(
                f"Peak: {peak_date.strftime('%Y-%m')} ({peak_val:.1f}%)",
                xy=(peak_date, peak_val),
                xytext=(peak_date + pd.DateOffset(months=8), peak_val * 0.88),
                arrowprops=dict(arrowstyle="->", color="red"),
                fontsize=8, color="red",
            )

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].set_xlabel("Date")
    plt.tight_layout()
    out = "eda/charts/volatility_analysis.png"
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
