"""
SingStat TableBuilder API fetcher.

Uses urllib.request with browser-like headers — required by SingStat's API.
Technique from: https://tablebuilder.singstat.gov.sg/view-api/for-developers

API endpoint:
  GET https://tablebuilder.singstat.gov.sg/api/table/tabledata/{tableId}

Query parameters:
  seriesNoORrowNo  str   Series number (Time Series) or row number (Cross-Sectional).
                         Use "1.1", "1.2", etc. Omit to get all series.
  offset           int   Number of records to skip (default 0). For pagination.
  limit            int   Max records returned. Hard cap is 3000.
  sortBy           str   Sort field + direction, e.g. "rowtext asc", "key desc".
  timeFilter       str   Filter to a specific period, e.g. "2023 1H", "2022 Q1".
  between          str   Filter values to a range, e.g. "0, 9000" (URL-encode comma).
  search           str   Text search within row labels.

JSON response structure:
  {
    "Data": {
      "row": [
        {
          "rowText":  "<series label>",
          "seriesNo": "<series number, e.g. 1.1>",
          "columns": [
            {"key": "<period, e.g. '2023 1H'>", "value": "<numeric string>"},
            ...
          ]
        },
        ...
      ],
      "totalRow": 42        ← total number of series rows in the table (use for pagination)
    }
  }

Pagination note:
  offset paginates over *series rows*, not individual data points.
  A table with 42 series and 300 time periods = 42 rows, each with 300 columns.
  With limit=3000 most tables fit in a single request.
  Use totalRow to compute required pages upfront instead of probing with an empty fetch.
"""

import json
import os
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = "https://tablebuilder.singstat.gov.sg/api/table/tabledata"
META_URL = "https://tablebuilder.singstat.gov.sg/api/table/metadata"
RAW_DIR  = "data/raw/singstat"

# Browser-like headers required by SingStat — plain requests without these get blocked.
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept":     "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Tables to fetch: { dataset_name: { tableId, seriesNoORrowNo (optional), ... } }
SINGSTAT_TABLES = {
    "gdp_expenditure": {
        "tableId":        "M015831",
        "seriesNoORrowNo": None,   # fetch all series
        "limit":          3000,
        "sortBy":         "key asc",
    },
    "industrial_production": {
        "tableId":        "M212881",
        "seriesNoORrowNo": None,
        "limit":          3000,
        "sortBy":         "key asc",
    },
    "merchandise_exports": {
        "tableId":        "M780141",
        "seriesNoORrowNo": None,
        "limit":          3000,
        "sortBy":         "key asc",
    },
    "cpi": {
        "tableId":        "M212911",
        "seriesNoORrowNo": None,
        "limit":          3000,
        "sortBy":         "key asc",
    },
}

os.makedirs(RAW_DIR, exist_ok=True)


# ── Core fetch helpers ─────────────────────────────────────────────────────────

def _build_url(table_id: str, params: dict) -> str:
    """Build the full API URL with encoded query parameters."""
    # Remove None values; urlencode handles the rest
    clean = {k: v for k, v in params.items() if v is not None}
    return f"{BASE_URL}/{table_id}?{urlencode(clean)}"


def _get(url: str, retries: int = 3, backoff: float = 2.0) -> dict:
    """
    HTTP GET using urllib.request with browser headers.
    Retries on transient errors with exponential backoff.
    """
    for attempt in range(1, retries + 1):
        try:
            req  = Request(url, headers=HEADERS)
            raw  = urlopen(req, timeout=30).read()
            return json.loads(raw)
        except HTTPError as e:
            print(f"  [HTTP {e.code}] {url} (attempt {attempt}/{retries})")
            if e.code in (400, 403, 404):
                raise   # Non-retryable
        except URLError as e:
            print(f"  [URLError] {e.reason} (attempt {attempt}/{retries})")
        except json.JSONDecodeError as e:
            print(f"  [JSONError] {e} (attempt {attempt}/{retries})")

        if attempt < retries:
            time.sleep(backoff ** attempt)

    raise RuntimeError(f"Failed to fetch after {retries} attempts: {url}")


# ── Metadata ───────────────────────────────────────────────────────────────────

def fetch_metadata(table_id: str) -> dict:
    """
    Fetch table metadata: title, unit, frequency, series descriptions.
    Endpoint: GET /api/table/metadata/{tableId}
    """
    url  = f"{META_URL}/{table_id}"
    req  = Request(url, headers=HEADERS)
    raw  = urlopen(req, timeout=30).read()
    meta = json.loads(raw)
    return meta


# ── Table data ─────────────────────────────────────────────────────────────────

def fetch_singstat_table(
    table_id:          str,
    dataset_name:      str,
    series_no:         str | None = None,
    offset:            int        = 0,
    limit:             int        = 3000,
    sort_by:           str        = "key asc",
    time_filter:       str | None = None,
    between:           str | None = None,
    search:            str | None = None,
) -> pd.DataFrame:
    """
    Fetch a SingStat TableBuilder dataset and return a tidy DataFrame.

    Handles pagination automatically: if the response contains exactly `limit`
    rows, it re-fetches with incremented offset until exhausted.

    Returns
    -------
    pd.DataFrame with columns:
        date      (str)   — period label from the API, e.g. "2023 1H", "2022 Q3"
        variable  (str)   — series/row label (rowText)
        seriesNo  (str)   — series number, e.g. "1.1"
        value     (float) — numeric value (NaN where API returns "na" or "")
    """
    all_rows: list[dict] = []
    current_offset       = offset
    total_rows: int | None = None          # populated from first response

    while True:
        params = {
            "seriesNoORrowNo": series_no,
            "offset":          current_offset,
            "limit":           limit,
            "sortBy":          sort_by,
            "timeFilter":      time_filter,
            "between":         between,
            "search":          search,
        }
        url  = _build_url(table_id, params)
        print(f"  Fetching {dataset_name} (offset={current_offset}"
              + (f"/{total_rows}" if total_rows is not None else "") + f"): {url}")
        data = _get(url)

        data_block = data.get("Data", {})
        rows       = data_block.get("row", [])

        if not rows:
            break

        # Read totalRow from first response so we know upfront how many pages are needed
        if total_rows is None:
            total_rows = data_block.get("totalRow")

        # Flatten: each row has N columns (time periods)
        for row in rows:
            row_text      = row.get("rowText", "")
            series_no_val = row.get("seriesNo", "")
            for col in row.get("columns", []):
                raw_val = col.get("value", "")
                try:
                    value = float(raw_val)
                except (ValueError, TypeError):
                    value = float("nan")  # "na", "", blanks

                all_rows.append({
                    "date":     col.get("key", ""),
                    "variable": row_text,
                    "seriesNo": series_no_val,
                    "value":    value,
                })

        current_offset += len(rows)

        # Stop when all series rows have been fetched
        if total_rows is not None and current_offset >= total_rows:
            break
        # Fallback: stop when a partial page is returned (no totalRow field)
        if len(rows) < limit:
            break

    if not all_rows:
        print(f"  [WARN] No data returned for {dataset_name}")
        return pd.DataFrame(columns=["date", "variable", "seriesNo", "value"])

    df = pd.DataFrame(all_rows)

    # Save raw JSON + CSV
    out_csv  = os.path.join(RAW_DIR, f"{dataset_name}.csv")
    out_json = os.path.join(RAW_DIR, f"{dataset_name}.json")
    df.to_csv(out_csv, index=False)
    with open(out_json, "w") as f:
        json.dump(all_rows, f, indent=2)

    print(f"  [OK] {dataset_name}: {len(df)} records -> {out_csv}")
    return df


# ── Fetch all ──────────────────────────────────────────────────────────────────

def fetch_all_singstat() -> dict[str, pd.DataFrame]:
    """Fetch every table defined in SINGSTAT_TABLES."""
    results = {}
    for name, cfg in SINGSTAT_TABLES.items():
        print(f"\n--- {name} ({cfg['tableId']}) ---")
        try:
            results[name] = fetch_singstat_table(
                table_id     = cfg["tableId"],
                dataset_name = name,
                series_no    = cfg.get("seriesNoORrowNo"),
                limit        = cfg.get("limit", 3000),
                sort_by      = cfg.get("sortBy", "key asc"),
                time_filter  = cfg.get("timeFilter"),
                between      = cfg.get("between"),
                search       = cfg.get("search"),
            )
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            results[name] = pd.DataFrame()

    return results


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test with Merchandise Exports of Machinery & Equipment
    print("=== Single-table test (Merchandise Exports of Machinery & Equipment) ===")
    df = fetch_singstat_table(
        table_id     = "M451121",
        dataset_name = "merch_exports_machinery_test",
        limit        = 3000,        # single page; we'll slice for display
        sort_by      = "key desc",  # most recent first
    )
    print(df.head(10).to_string(index=False))

    # Uncomment to fetch all tables:
    # fetch_all_singstat()
