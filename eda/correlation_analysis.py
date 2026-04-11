"""
Correlation Analysis — heatmap + cross-correlation (exports vs IPI).
Run: python eda/correlation_analysis.py
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

os.makedirs("eda/charts", exist_ok=True)

plt.rcParams.update({
    "figure.dpi": 120,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def run(panel: pd.DataFrame):
    target_cols = ["industrial_production", "merchandise_exports", "cpi"]
    available   = [c for c in target_cols if c in panel.columns]

    if len(available) < 2:
        print("[WARN] Need at least 2 series for correlation analysis.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Singapore: Correlation Analysis", fontweight="bold")

    # --- Pearson heatmap (levels) ---
    corr = panel[available].dropna().corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlGn",
                center=0, ax=axes[0], square=True, linewidths=0.5)
    axes[0].set_title("Pearson Correlation (Levels)")

    # --- Cross-correlation: exports YoY vs IPI YoY ---
    if "merchandise_exports" in available and "industrial_production" in available:
        common = panel[["merchandise_exports", "industrial_production"]].dropna()
        exp_yoy = common["merchandise_exports"].pct_change(12).dropna()
        ipi_yoy = common["industrial_production"].pct_change(12).dropna()
        aligned = pd.concat([exp_yoy, ipi_yoy], axis=1).dropna()

        lags   = range(-12, 13)
        xcorr  = [aligned.iloc[:, 0].corr(aligned.iloc[:, 1].shift(lag)) for lag in lags]
        colors = ["steelblue" if x >= 0 else "salmon" for x in xcorr]

        axes[1].bar(lags, xcorr, color=colors)
        axes[1].axvline(0, color="black", linewidth=1)
        axes[1].axhline(0, color="black", linewidth=0.5, linestyle="--")
        axes[1].set_xlabel("Lag (months) — positive = exports lead IPI")
        axes[1].set_ylabel("Cross-Correlation")
        axes[1].set_title("Cross-Correlation: Exports YoY vs IPI YoY")

        peak_lag = list(lags)[int(np.argmax(xcorr))]
        print(f"\nPeak cross-correlation at lag={peak_lag} months")
        direction = "Exports LEAD IPI" if peak_lag > 0 else ("IPI LEADS exports" if peak_lag < 0 else "Simultaneous")
        print(f"Interpretation: {direction}")

    plt.tight_layout()
    out = "eda/charts/correlation_analysis.png"
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
