"""
Master pipeline runner.

Usage:
  python pipeline/run_pipeline.py               # full run
  python pipeline/run_pipeline.py --source mas  # single source
  python pipeline/run_pipeline.py --dry-run     # validate imports only

Called by GitHub Actions on the 1st of every month.
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Allow imports from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROCESSED_DIR = "data/processed"
LOG_PATH      = "data/pipeline_log.json"
os.makedirs(PROCESSED_DIR, exist_ok=True)


def log_run(results: dict, duration_s: float):
    """Append a run summary to pipeline_log.json."""
    entry = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": round(duration_s, 1),
        "datasets": {
            name: {
                "rows":   len(df) if hasattr(df, "__len__") else 0,
                "status": "ok" if (hasattr(df, "__len__") and len(df) > 0) else "empty",
            }
            for name, df in results.items()
        },
    }

    log = []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH) as f:
            log = json.load(f)
    log.append(entry)

    with open(LOG_PATH, "w") as f:
        json.dump(log[-50:], f, indent=2)   # keep last 50 runs

    print(f"\nRun logged -> {LOG_PATH}")
    return entry


def run(sources: list[str] | None = None, dry_run: bool = False):
    t_start = datetime.utcnow()
    print(f"\n{'='*60}")
    print(f"Pipeline start: {t_start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}")

    if dry_run:
        print("[DRY RUN] Validating imports only...")
        from pipeline.fetch_singstat  import fetch_all_singstat
        from pipeline.fetch_mas       import fetch_all_mas
        from pipeline.fetch_worldbank import fetch_all_worldbank
        print("[DRY RUN] All imports OK.")
        return

    all_results = {}
    sources = sources or ["singstat", "mas", "worldbank"]

    if "singstat" in sources:
        print("\n--- SingStat ---")
        from pipeline.fetch_singstat import fetch_all_singstat
        all_results.update(fetch_all_singstat())

    if "mas" in sources:
        print("\n--- MAS ---")
        from pipeline.fetch_mas import fetch_all_mas
        all_results.update(fetch_all_mas())

    if "worldbank" in sources:
        print("\n--- World Bank ---")
        from pipeline.fetch_worldbank import fetch_all_worldbank
        all_results.update(fetch_all_worldbank())

    # Write a combined summary CSV per source group
    import pandas as pd
    for name, df in all_results.items():
        if df.empty:
            continue
        out = os.path.join(PROCESSED_DIR, f"{name}.csv")
        df.to_csv(out, index=False)

    duration = (datetime.utcnow() - t_start).total_seconds()
    entry    = log_run(all_results, duration)

    print(f"\n{'='*60}")
    print(f"Pipeline done in {duration:.1f}s")
    for name, info in entry["datasets"].items():
        status = "OK" if info["status"] == "ok" else "EMPTY"
        print(f"  [{status}] {name}: {info['rows']} rows")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source",  nargs="+", choices=["singstat", "mas", "worldbank"],
                        help="Run only specific sources")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate imports without fetching data")
    args = parser.parse_args()
    run(sources=args.source, dry_run=args.dry_run)
